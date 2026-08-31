import os
import json
import sys
from datetime import datetime
from PIL import Image

try:
    from google import genai
except ImportError:
    genai = None

class OcrService:
    @staticmethod
    def process_receipt(image_path, api_key=None):
        """
        Uses the Google GenAI SDK with gemini-3.1-flash-lite (with a legacy fallback if unavailable)
        to analyze the receipt image and extract structured data.
        """
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"Receipt image not found: {image_path}")

        if genai is None:
            raise RuntimeError("google-genai library is not installed. Please run 'pip install google-genai'.")

        if not api_key:
            raise ValueError("Gemini API Key is not configured. Please add your API Key in Settings.")

        try:
            client = genai.Client(api_key=api_key)
            img = Image.open(image_path)
            
            prompt = """
            Analyze this InstaPay receipt image and extract the following 7 fields precisely in JSON format:
            1. "money_value": The numeric transfer amount to the left of "EGP" (e.g., "70" or "1500.00").
            2. "account_number": The recipient account number/label from the "To" section only. Prefer the recipient's @instapay handle/number shown under "To". NEVER return the sender's @instapay handle or sender label from the "From" section.
            3. "receipt_number": The reference/receipt number located after the word "Reference".
            4. "receipt_date": The date and time located after the word "Date:" (formatted as DD MMM YYYY HH:MM AM/PM).
            5. "note": The complete text following the word "Note" (can be empty string if nothing is written).
            6. "note_name": The letters/words in the Note section, excluding the numeric validation number. Return the text exactly as visible, trimmed. If no name/text is visible, return an empty string.
            7. "note_number": The numeric validation number visible inside the Note section. Return only the digits of that number. If no number is visible, return an empty string. Do not invent a number.

            Important layout rule: the receipt has both "From" and "To" sections. Extract account_number from the recipient in the "To" section, not from "From". For example, if From contains "sender@instapay" and To contains "recipient@instapay", return "recipient@instapay".

            Return ONLY valid JSON with these exact keys:
            {
              "money_value": "",
              "account_number": "",
              "receipt_number": "",
              "receipt_date": "",
              "note": "",
              "note_name": "",
              "note_number": ""
            }
            """
            
            try:
                response = client.models.generate_content(
                    model="gemini-3.1-flash-lite",
                    contents=[prompt, img]
                )
            except Exception:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[prompt, img]
                )
            
            text_response = response.text.strip()
            
            if "```json" in text_response:
                text_response = text_response.split("```json")[1].split("```")[0]
            elif "```" in text_response:
                text_response = text_response.split("```")[1].split("```")[0]
            
            text_response = text_response.strip()
            data = json.loads(text_response)
            
            data["receipt_number"] = data.get("receipt_number", f"REC-{int(datetime.now().timestamp())}")
            data["receipt_date"] = data.get("receipt_date", datetime.now().strftime("%d %b %Y %I:%M %p"))
            data["account_number"] = data.get("account_number", "N/A")
            data["money_value"] = data.get("money_value", "0.00")
            data["note"] = data.get("note", "")
            data["note_name"] = str(data.get("note_name", "")).strip()
            data["note_number"] = str(data.get("note_number", "")).strip()

            data["raw_text"] = f"Gemini API Extracted Data:\n{json.dumps(data, indent=2)}"
            return data

        except Exception as e:
            raise RuntimeError(f"Gemini API extraction failed: {str(e)}")

class OutlookService:
    @staticmethod
    def send_excel_report(excel_paths, zip_path, recipients):
        """
        Opens Outlook and attaches all receipt-date Excel reports and the Receipt Images
        ZIP archive. Uses .Display() for user review before sending.
        """
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
            
            try:
                outlook = win32com.client.Dispatch("Outlook.Application")
            except Exception:
                raise RuntimeError("Could not open Outlook. Please ensure classic Outlook is installed and running.")

            mail = outlook.CreateItem(0)
            mail.To = "; ".join(recipients)
            mail.Subject = f"InstaPay Receipts Report & Images - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            mail.Body = "Please find attached the consolidated InstaPay Receipts Excel report and the archive of receipt photos."
            
                        # Attach each receipt-date Excel report
            for excel_path in excel_paths:
                mail.Attachments.Add(excel_path)

            # Attach Images ZIP if exists

            if zip_path and os.path.exists(zip_path):
                mail.Attachments.Add(os.path.abspath(zip_path))
            
            mail.Display()
            return True
            
        except ImportError:
            raise RuntimeError("The 'pywin32' library is not properly installed. Please run: pip install pywin32")
        except Exception as e:
            raise RuntimeError(f"Outlook operation failed: {str(e)}\n\nTip: Ensure Outlook is open and no dialog boxes are active.")
