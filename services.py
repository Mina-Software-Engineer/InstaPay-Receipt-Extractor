import base64
import json
import mimetypes
import os
from datetime import datetime

try:
    from perplexity import Perplexity
except ImportError:
    Perplexity = None


class OcrService:
    """Extract InstaPay receipt fields with the Perplexity Agent API."""

    EXTRACTION_MODEL = "anthropic/claude-opus-4-6"

    @staticmethod
    def _image_data_url(image_path):
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        supported = {"image/png", "image/jpeg", "image/webp", "image/gif"}
        if mime_type not in supported:
            mime_type = "image/jpeg"
        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _response_text(response):
        text = getattr(response, "output_text", None)
        if text:
            return str(text).strip()
        output = getattr(response, "output", None) or []
        for message in output:
            for content in getattr(message, "content", None) or []:
                text_value = getattr(content, "text", None)
                if text_value:
                    return str(text_value).strip()
                if isinstance(content, dict) and content.get("text"):
                    return str(content["text"]).strip()
        return ""

    @staticmethod
    def _parse_json(text):
        text = str(text or "").strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
        return json.loads(text)

    @staticmethod
    def process_receipt(image_path, api_key=None):
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"Receipt image not found: {image_path}")
        if Perplexity is None:
            raise RuntimeError("Perplexity SDK is not installed. Activate the application environment and run: python -m pip install --upgrade perplexityai")
        if not api_key:
            raise ValueError("Perplexity API Key is not configured. Please add it in Admin Settings.")

        prompt = """
        Read the receipt visually and extract the following 7 fields precisely.
        Return a JSON object matching the supplied schema and no other content.
        Do not use web search, outside knowledge, guesses, or fabricated values.
        First locate the printed labels on the receipt, then read the value on the same line or the immediately following line.
        Preserve the exact characters that are visible, except for the normalization explicitly requested below.

        Rules:
        - money_value: read the numeric transfer amount immediately to the left of the printed EGP currency label; remove thousands separators only.
        - account_number: read the recipient account number/label under the recipient account name ending with @instapay. Never return the sender account from From, even if it is easier to read.
        - receipt_number: read the value after the printed Reference label.
        - receipt_date: read the value after the printed Date label and format it as DD MMM YYYY HH:MM AM/PM.
        - note: copy all visible text after the printed Note label, possibly empty.
        - note_name: return only the visible letters/words in Note after excluding any digits, trimmed.
        - note_number: return only the digits visibly present in Note. Return an empty string when no digits are visible. Never invent, infer, or calculate a number.
        - If a field is unreadable, return an empty string rather than guessing.
        """
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "money_value": {"type": "string"},
                "account_number": {"type": "string"},
                "receipt_number": {"type": "string"},
                "receipt_date": {"type": "string"},
                "note": {"type": "string"},
                "note_name": {"type": "string"},
                "note_number": {"type": "string"},
            },
            "required": [
                "money_value", "account_number", "receipt_number", "receipt_date",
                "note", "note_name", "note_number",
            ],
        }

        try:
            client = Perplexity(api_key=api_key)
            responses_api = getattr(client, "responses", None)
            create_response = getattr(responses_api, "create", None)
            if not callable(create_response):
                raise RuntimeError("The installed Perplexity SDK is incompatible. Reinstall it with: python -m pip install --upgrade perplexityai")
            response = create_response(
                model=OcrService.EXTRACTION_MODEL,
                input=[
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": OcrService._image_data_url(image_path)},
                        ],
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "instapay_receipt", "schema": schema},
                },
                max_output_tokens=1000,
            )
            text_response = OcrService._response_text(response)
            data = OcrService._parse_json(text_response)
            data["receipt_number"] = data.get("receipt_number") or f"REC-{int(datetime.now().timestamp())}"
            data["receipt_date"] = data.get("receipt_date") or datetime.now().strftime("%d %b %Y %I:%M %p")
            data["account_number"] = data.get("account_number") or "N/A"
            data["money_value"] = str(data.get("money_value") or "0.00").replace(",", "")
            data["note"] = str(data.get("note") or "").strip()
            data["note_name"] = str(data.get("note_name") or "").strip()
            data["note_number"] = str(data.get("note_number") or "").strip()
            data["raw_text"] = f"Perplexity Agent API Extracted Data:\n{json.dumps(data, indent=2)}"
            return data
        except Exception as exc:
            raise RuntimeError(f"Perplexity API extraction failed: {exc}") from exc


class OutlookService:
    @staticmethod
    def send_excel_report(excel_paths, zip_path, recipients):
        """Open Outlook and attach all receipt-date Excel reports and the image ZIP."""
        if isinstance(recipients, str):
            recipients = [item.strip() for item in recipients.replace(",", ";").split(";") if item.strip()]
        recipients = [str(item).strip() for item in recipients if str(item).strip()]
        if not recipients:
            raise ValueError("No email recipients are selected in Settings.")
        if isinstance(excel_paths, str):
            excel_paths = [excel_paths]
        excel_paths = [os.path.abspath(path) for path in excel_paths if path]
        if not excel_paths:
            raise FileNotFoundError("No Excel reports were generated.")
        missing_excel = [path for path in excel_paths if not os.path.exists(path)]
        if missing_excel:
            raise FileNotFoundError(f"Excel report not found at {missing_excel[0]}")
        try:
            import win32com.client
            outlook = None
            dispatch_errors = []
            for dispatcher in (win32com.client.DispatchEx, win32com.client.Dispatch):
                try:
                    outlook = dispatcher("Outlook.Application")
                    break
                except Exception as dispatch_exc:
                    dispatch_errors.append(str(dispatch_exc))
            if outlook is None:
                details = dispatch_errors[-1] if dispatch_errors else "Unknown COM error"
                raise RuntimeError(
                    "Classic Outlook could not be started through Windows COM. "
                    "Make sure classic Outlook is installed and configured, not only New Outlook. "
                    f"Details: {details}"
                )
            mail = outlook.CreateItem(0)
            mail.To = "; ".join(recipients)
            mail.Subject = f"InstaPay Receipts Report & Images - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            mail.Body = "Please find attached the consolidated InstaPay Receipts Excel report and the archive of receipt photos."
            for excel_path in excel_paths:
                mail.Attachments.Add(excel_path)
            if zip_path and os.path.exists(zip_path):
                mail.Attachments.Add(os.path.abspath(zip_path))
            mail.Display(False)
            return True
        except ImportError:
            raise RuntimeError("The 'pywin32' library is not properly installed. Please run: pip install pywin32")
        except Exception as exc:
            raise RuntimeError(f"Outlook operation failed: {exc}\n\nTip: Ensure Outlook is open and no dialog boxes are active.")
