import json
import mimetypes
import os
import re
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None


class OcrService:
    """Read receipt text with Azure Vision OCR and parse InstaPay-specific fields locally."""

    API_VERSION = "2024-02-01"

    @staticmethod
    def _raise_http_error(response, provider_name="Azure Vision"):
        detail = response.text[:1000].strip()
        try:
            payload = response.json()
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    detail = error.get("message") or error.get("code") or detail
                elif isinstance(error, str):
                    detail = error
        except ValueError:
            pass
        raise RuntimeError(f"{provider_name} request failed with HTTP {response.status_code}: {detail}")

    @staticmethod
    def _clean_line(value):
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _extract_ocr_lines(payload):
        read_result = payload.get("readResult") or payload.get("read") or {}
        lines = []
        for block in read_result.get("blocks") or []:
            for line in block.get("lines") or []:
                text = OcrService._clean_line(line.get("text"))
                if text:
                    lines.append(text)
        if not lines:
            for page in read_result.get("pages") or []:
                for line in page.get("lines") or []:
                    text = OcrService._clean_line(line.get("text"))
                    if text:
                        lines.append(text)
        if not lines and payload.get("content"):
            lines = [OcrService._clean_line(line) for line in str(payload["content"]).splitlines() if OcrService._clean_line(line)]
        return lines

    ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
    LABELS = {
        "reference": r"(?:^|\s)(?:reference|المرجع)\s*[:：-]?",
        "date": r"(?:^|\s)(?:date|التاريخ)\s*[:：-]?",
        "note": r"(?:^|\s)(?:note|ملاحظة)\s*[:：-]?",
        "to": r"(?:^|\s)(?:to|إلى|الى)\s*[:：-]?",
        "from": r"(?:^|\s)(?:from|من)\s*[:：-]?",
    }

    @staticmethod
    def _ascii_digits(value):
        return str(value or "").translate(OcrService.ARABIC_DIGITS)

    @staticmethod
    def _strip_edges(value):
        return OcrService._clean_line(value).strip(" :：|-–—")

    @staticmethod
    def _line_value(lines, label_pattern):
        """Return a label's same-line value, supporting RTL OCR label ordering."""
        pattern = re.compile(label_pattern, re.IGNORECASE)
        for index, line in enumerate(lines):
            match = pattern.search(line)
            if not match:
                continue
            before = OcrService._strip_edges(line[:match.start()])
            after = OcrService._strip_edges(line[match.end():])
            # Arabic OCR commonly returns the value before a right-aligned label.
            value = after or before
            if value:
                return value, index
            for following in lines[index + 1: index + 3]:
                if following and not re.search(r"(?:reference|المرجع|date|التاريخ|note|ملاحظة)", following, re.IGNORECASE):
                    return OcrService._strip_edges(following), index
            return "", index
        return "", -1

    @staticmethod
    def _normalize_date(value):
        value = OcrService._strip_edges(value)
        if not value:
            return ""
        value = OcrService._ascii_digits(value)
        value = re.sub(r"\s+", " ", value)
        formats = (
            "%d %b %Y %I:%M %p", "%d %B %Y %I:%M %p",
            "%d-%m-%Y %I:%M %p", "%d/%m/%Y %I:%M %p",
            "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M",
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        )
        for date_format in formats:
            try:
                return datetime.strptime(value, date_format).strftime("%d %b %Y %I:%M %p")
            except ValueError:
                continue
        return value

    @staticmethod
    def _find_label_index(lines, label_pattern):
        pattern = re.compile(label_pattern, re.IGNORECASE)
        for index, line in enumerate(lines):
            if pattern.search(line):
                return index
        return -1

    @staticmethod
    def _recipient_account(lines):
        """Prefer the account in the To/إلى block; never select the From/من account."""
        to_index = OcrService._find_label_index(lines, OcrService.LABELS["to"])
        from_index = OcrService._find_label_index(lines, OcrService.LABELS["from"])
        if to_index >= 0:
            end = len(lines)
            for marker in (OcrService.LABELS["reference"], OcrService.LABELS["date"], OcrService.LABELS["note"]):
                marker_index = OcrService._find_label_index(lines[to_index + 1:], marker)
                if marker_index >= 0:
                    end = min(end, to_index + 1 + marker_index)
            candidates = lines[to_index + 1:end]
            # The numeric account line is the strongest signal in the recipient block.
            numeric = []
            for position, candidate in enumerate(candidates):
                digits = re.sub(r"\D", "", OcrService._ascii_digits(candidate))
                if len(digits) >= 8 and not re.search(r"(?:egp|جنيه|reference|date|note|التاريخ|المرجع|ملاحظة)", candidate, re.IGNORECASE):
                    numeric.append((position, candidate))
            if numeric:
                return OcrService._strip_edges(numeric[-1][1])
            # Fallback for a nonnumeric account label directly below To/إلى.
            for candidate in candidates:
                if candidate and not re.search(r"@\s*instapay\b|bank|بنك", candidate, re.IGNORECASE):
                    return OcrService._strip_edges(candidate)
            return ""

        # English-only legacy layout: account number/label follows the @instapay line.
        for index, line in enumerate(lines):
            if re.search(r"@\s*instapay\b", line, re.IGNORECASE):
                for candidate in lines[index + 1:index + 3]:
                    if candidate and not re.search(r"@\s*instapay\b", candidate, re.IGNORECASE):
                        return OcrService._strip_edges(candidate)
        return ""

    @staticmethod
    def _parse_instapay(lines):
        joined = "\n".join(lines)
        joined_digits = OcrService._ascii_digits(joined)
        money_match = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:EGP|جنيه|ج\.م)", joined_digits, re.IGNORECASE)
        money_value = money_match.group(1).replace(",", "") if money_match else ""

        account_number = OcrService._recipient_account(lines)
        receipt_number, _ = OcrService._line_value(lines, OcrService.LABELS["reference"])
        receipt_date, _ = OcrService._line_value(lines, OcrService.LABELS["date"])
        note, _ = OcrService._line_value(lines, OcrService.LABELS["note"])
        note = OcrService._strip_edges(note)
        note_ascii = OcrService._ascii_digits(note)
        note_number_match = re.search(r"\d[\d\s-]*", note_ascii)
        note_number = re.sub(r"\D", "", note_number_match.group(0)) if note_number_match else ""
        note_name = re.sub(r"[0-9٠-٩۰-۹]", "", note)
        note_name = re.sub(r"[^\w\u0600-\u06FF@ ._-]", " ", note_name)
        note_name = OcrService._clean_line(note_name).strip("-_: ")

        return {
            "money_value": money_value,
            "account_number": account_number,
            "receipt_number": OcrService._strip_edges(receipt_number),
            "receipt_date": OcrService._normalize_date(receipt_date),
            "note": note,
            "note_name": note_name,
            "note_number": note_number,
        }

    @staticmethod
    def process_receipt(image_path, api_key=None, endpoint=None):
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"Receipt image not found: {image_path}")
        if requests is None:
            raise RuntimeError("The requests package is not installed. Run: python -m pip install --upgrade requests")
        vision_key = str(api_key or "").strip()
        vision_endpoint = str(endpoint or os.getenv("AZURE_VISION_ENDPOINT", "")).strip().rstrip("/")
        if not vision_key:
            raise ValueError("Azure Vision API key is not configured. Add it in Admin Settings.")
        if not vision_endpoint:
            raise ValueError("Azure Vision endpoint is not configured. Add it in Admin Settings.")

        analyze_url = f"{vision_endpoint}/computervision/imageanalysis:analyze"
        params = {"api-version": OcrService.API_VERSION, "features": "read"}
        mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
        try:
            with open(image_path, "rb") as image_file:
                response = requests.post(
                    analyze_url,
                    params=params,
                    headers={
                        "Ocp-Apim-Subscription-Key": vision_key,
                        "Content-Type": mime_type,
                    },
                    data=image_file,
                    timeout=(20, 120),
                )
            if not response.ok:
                OcrService._raise_http_error(response)
            payload = response.json()
            lines = OcrService._extract_ocr_lines(payload)
            if not lines:
                raise RuntimeError("Azure Vision returned no readable text from the receipt image.")
            data = OcrService._parse_instapay(lines)
            data["raw_text"] = "Azure Vision OCR:\n" + "\n".join(lines) + "\n\nParsed fields:\n" + json.dumps(data, indent=2, ensure_ascii=False)
            return data
        except Exception as exc:
            raise RuntimeError(f"Azure Vision OCR extraction failed: {exc}") from exc


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
