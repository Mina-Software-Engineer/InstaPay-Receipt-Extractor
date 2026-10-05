# InstaPay Receipt Register (Python Version)

A professional Windows desktop application for receiving InstaPay receipt images, extracting account numbers, receipt numbers, receipt date/time, and money values via OCR, validating each field against business rules, and maintaining a consolidated Excel report with optional Outlook email integration.

## Key Architecture & Manual Review Workflow

As requested, the application ensures strict separation between automated OCR extraction and final verification:

1. **Receipt Selection**: The operator chooses a receipt image file (PNG, JPG, JPEG, BMP). The app displays a scaled image preview and records the source path without duplicating image files.
2. **OCR Extraction**: Clicking **Run OCR Extraction** processes the image (supporting bilingual English and Arabic receipts) and extracts candidate values into editable form controls.
3. **Manual Review and Correction**: The operator visually compares the extracted values against the receipt preview. Any incorrect value can be edited directly in the input fields.
4. **Verify & Save**: Clicking **Verify & Save** triggers domain validation using the values currently shown in the editable inputs. OCR output alone never triggers persistence, duplicate checks, Excel updates, or email sending.
5. **Persistence & Reporting**: Accepted receipts are stored in a local SQLite database (`.instapay_receipts/instapay.db`), `Instapay_Receipts.xlsx` is regenerated automatically, and the report is optionally sent via classic Outlook.

---

## Installation & Running from Source

### Prerequisites
* **Python 3.10** or newer.
* **Microsoft Windows** (recommended for native PySide6 UI and classic Outlook integration).

### Setup Steps
1. Clone or copy the `instapay_app` directory to your Windows machine.
2. Open a terminal inside the directory and create a virtual environment:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment and install dependencies:
   * On Windows Command Prompt:
     ```bash
     venv\Scripts\activate
     pip install -r requirements.txt
     ```
   * On PowerShell:
     ```bash
     .\venv\Scripts\Activate.ps1
     pip install -r requirements.txt
     ```
4. Run the application:
   ```bash
   python app.py
   ```

---

## Configuration & Data Management

* **Settings**: Open **Settings & Accounts** to configure:
  * **Approved Account Numbers**: Add all authorized InstaPay account numbers. Unapproved accounts will be rejected upon verification.
  * **Outlook Recipient Email**: Set the destination email address for Excel reports.
* **Data Folder**: Click **Open Data Folder** in the application to access `%LOCALAPPDATA%\.instapay_receipts` (or home directory on non-Windows environments), where the SQLite database, settings, and `Instapay_Receipts.xlsx` are securely stored.
* **Outlook Integration**: Email sending uses the locally installed, signed-in classic Outlook desktop client via Windows COM automation (`pywin32`). No Outlook passwords are stored by the app.

---

## Automated Testing

To run the test suite (validating database persistence, domain validation rules, and Excel report generation):

```bash
pip install pytest pytest-qt
PYTHONPATH=. pytest
```
