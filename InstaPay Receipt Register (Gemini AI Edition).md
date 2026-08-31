# InstaPay Receipt Register (Gemini AI Edition)

A professional Windows desktop application for receiving InstaPay receipt images, extracting receipt data using **Google Gemini AI**, validating each field against business rules, and maintaining a consolidated Excel report with optional Outlook email integration.

## Key Features & Manual Review Workflow

1. **Receipt Selection**: Choose a receipt image (PNG, JPG, JPEG). The app displays a scaled image preview.
2. **Gemini AI Extraction**: Clicking **Extract with Gemini AI** sends the image to Google's multimodal AI model (`gemini-1.5-flash`), which accurately parses:
   * **Money Value** (number to the left of "EGP")
   * **Account Name** (ending with `@instapay`)
   * **Account Number/Label** (line below account name)
   * **Receipt Number / Reference**
   * **Receipt Date/Time** (formatted as `DD MMM YYYY HH:MM AM/PM`)
   * **Note** (extracted even if empty)
3. **Manual Review and Correction**: The operator visually compares extracted values against the preview and can edit any field before verification.
4. **Verify & Save**: Validates normalized values against the approved accounts list and checks for duplicate receipt numbers.
5. **Reporting & Email**: Saves to local SQLite, regenerates `Instapay_Receipts.xlsx`, and optionally emails the report via classic Outlook.

---

## Installation & Setup

1. **Prerequisites**: Python 3.10+ installed on Windows.
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Get a Free Gemini API Key**:
   * Visit [Google AI Studio](https://aistudio.google.com/) to generate a free API key.
4. **Configure the App**:
   * Run `python app.py`.
   * Click **Settings & API Key**, paste your Gemini API Key and Outlook recipient email, and save.
5. **Run the App**:
   ```bash
   python app.py
   ```
