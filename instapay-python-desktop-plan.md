# Implementation Plan: Python-Based InstaPay Receipt Register

## Goal

Replace or build the **InstaPay Receipt Register** as a Windows desktop application written in **Python**. The application will accept a receipt image, run bilingual English/Arabic OCR, display the receipt and all extracted candidate values to the user, let the user correct each value manually, and only then validate and save the accepted record. Each successful save will update a consolidated Excel workbook and support on-demand or automatic sending through locally installed classic Outlook.

> **Core rule:** OCR produces editable suggestions. It never saves, rejects, updates Excel, or sends email by itself. The user compares the displayed values with the image, corrects them if necessary, and explicitly selects **Verify & save**.

## Recommended technical architecture

| Layer | Recommended technology | Responsibility |
|---|---|---|
| Desktop UI | **PySide6 (Qt for Python)** | A modern native Windows interface, image preview, editable data-entry form, dialogs, accessibility, and asynchronous task feedback. |
| OCR engine | **PaddleOCR** with Arabic and English models, evaluated against receipt samples | Local bilingual OCR returning recognized text and bounding boxes. The implementation will retain a replaceable OCR adapter so Tesseract can be substituted if reliability or packaging size proves preferable. |
| Field extraction | Python regex/parsing module | Derive account number, receipt number, date/time, and money candidates from OCR text, including English/Arabic labels and Arabic/Western digit normalization. |
| Validation | Python domain/service module | Normalize entered values; validate date/time, positive money, approved account, and receipt-number uniqueness. |
| Local data | `sqlite3` (standard library) | Persist approved accounts, user settings, accepted receipt records, and safe schema migrations. |
| Excel reporting | `openpyxl` | Regenerate `Instapay_Receipts.xlsx` deterministically after each accepted save. |
| Outlook automation | `pywin32` / Outlook COM | Compose/send through installed and signed-in **classic Outlook** without storing Outlook credentials. |
| Packaging | PyInstaller, optionally wrapped by Inno Setup | Produce a Windows executable and installer, including OCR runtime/model resources and clear prerequisites. |
| Test suite | `pytest`, with `pytest-qt` for UI tests where valuable | Unit tests for parsing, validation, database, reporting, and targeted workflow tests. |

**PySide6** is the planned user-interface framework because it provides reliable image viewing, form controls, layout responsiveness, native desktop behavior, and a practical asynchronous worker pattern for longer OCR operations. This selection avoids a browser/Electron dependency while keeping the code entirely Python-based.

## User workflow and screen design

| Step | User experience | Application behavior |
|---|---|---|
| 1. Choose image | The user selects a receipt image using **Select receipt image**. | Display the image preview and source path; clear prior pending-review inputs and errors. Receipt files are referenced, not copied. |
| 2. Extract with OCR | The user chooses **Read receipt**; the screen shows a clear progress state. | Run OCR in a background worker so the window remains responsive. Return raw recognized text plus four candidate fields. |
| 3. Manually review | The screen presents the image beside **Review OCR results**, with editable prefilled inputs: account number, receipt number, receipt date/time, and money value. Optionally expandable raw OCR text supports comparison. | Retain input edits independently from OCR candidates. Missing or low-confidence candidates remain editable rather than blocking the user. |
| 4. Verify & save | The user corrects any values, then presses **Verify & save**. | Validate the current field values only. Return clear per-field errors while preserving all typed corrections. |
| 5. Complete | A confirmation describes the saved receipt and Excel result. | On successful persistence, rebuild the Excel file; then send it automatically only when that setting is enabled. On-demand **Send Excel report** remains available. |

The form will make the review state visually explicit. OCR status and verification status will be separate, preventing users from mistaking a completed OCR job for an accepted receipt. A new receipt selection will reset the pending review to avoid accidental cross-receipt saves. Rerunning OCR for the same image will require confirmation if it would overwrite user edits.

## Implementation phases

### Phase 1 — Inspect inputs and establish project foundation

Confirm whether an existing Node/Electron codebase and test receipts are available, then create or reorganize a Python project structure without retaining Electron runtime dependencies. Capture the current SQLite schema, Excel column order, settings behavior, and any accepted extraction patterns so the rewrite remains compatible where necessary.

Set up a Python environment and dependency manifest (for example, `pyproject.toml` with locked, versioned dependencies), directory conventions, logging, application data path resolution for Windows, and a reproducible test configuration. The data directory will use an appropriate per-user Windows location such as `%LOCALAPPDATA%/InstaPayReceiptRegister` and will contain the SQLite file, settings, OCR model cache/resources as applicable, logs, and `Instapay_Receipts.xlsx`.

### Phase 2 — Build the domain and persistence layers first

Implement a dependency-free domain layer consisting of receipt data models, digit normalization (Arabic-Indic and Western numerals), field normalization, and explicit validation result objects. Build the SQLite repository and a versioned schema to support:

| Stored entity | Key fields and purpose |
|---|---|
| Approved accounts | Canonical account number; used as the allowlist during final verification. |
| Application settings | Outlook recipient email, automatic-send preference, and non-sensitive UI/configuration values. |
| Accepted receipt record | Unique receipt number; approved account; accepted receipt date/time; positive money value; source image path; raw OCR text; creation timestamp. |

Database insertion will enforce receipt-number uniqueness in addition to checking it in the UI/service layer, closing race conditions and ensuring a duplicate cannot be silently accepted. The account approval check, valid date/time requirement, and positive money requirement will be enforced in the Python service layer immediately before persistence.

### Phase 3 — Implement OCR and receipt-field extraction

Create a replaceable `OcrService` interface, initially backed by the selected local bilingual OCR engine. The service will return a structured result containing the full recognized text, lines/regions when available, warnings, and extraction candidates—not a final receipt record.

Build a parser that handles expected English and Arabic receipt labels, common punctuation/spacing variation, Arabic/Western digit conversion, decimal separators, and date/time patterns. Keep OCR extraction rules configurable and testable rather than embedding them in UI code. Use a curated, de-identified test set of receipt images/text fixtures to refine extraction accuracy.

The first-run model/language resource behavior will be explicit: the application may download required OCR resources once over the internet and will show a status/error message if the download fails. Thereafter it will use locally cached resources. The packaging phase will evaluate bundling model resources versus downloading them to balance installer size against offline-first installation.

### Phase 4 — Develop the review-first PySide6 interface

Implement the main application window and supporting settings dialog using PySide6. The receipt-processing page will include:

| UI area | Required controls/behavior |
|---|---|
| Receipt selection and preview | Image file picker, readable source path, scaled preview with optional zoom/open-original action. |
| OCR controls | **Read receipt** action, progress indicator, cancel/retry behavior where supported, and human-readable errors. |
| OCR review form | Four clearly labeled editable fields, prefilled from OCR candidates; optional expandable raw OCR transcript. |
| Validation feedback | Inline, field-specific errors and summary status; no loss of manual entries on failure. |
| Final action | A distinct **Verify & save** button, enabled only once an image is selected and an OCR attempt is complete or the user has manually entered review values. |
| Reporting actions | **Open data folder** and **Send Excel report** controls, with an explicit email status message. |

The interface will retain user corrections through routine repainting and failed validation. It will not overwrite them with background OCR completion. All slow tasks—OCR, Excel rebuild, and Outlook automation—will run off the UI thread and return results safely to the main window.

### Phase 5 — Connect verification, report generation, and email

Implement a `ReceiptVerificationService` called only by **Verify & save**. It will normalize the editable form values, validate them, confirm the account is approved, check duplicate receipt number, and write a single accepted receipt record in a database transaction. It will return structured errors mapped to the corresponding form fields.

After a successful transaction, a reporting service will rebuild `Instapay_Receipts.xlsx` from accepted SQLite records using `openpyxl`. The output will preserve a stable, documented column schema and write atomically where practical so a failed write does not corrupt the previous report.

Implement a narrow Windows-only Outlook adapter using `pywin32`. It will request the configured recipient from settings, attach the current workbook, and invoke classic Outlook through its local COM interface. It will never ask for or store an Outlook password. The UI will distinguish successful database save from email success: an Outlook security prompt, absent client, or policy block will be reported accurately without rolling back a valid receipt record and report. Automatic sending will occur only after a successful verified save when enabled; manual send will be available independently.

### Phase 6 — Settings, privacy, and resilience

Provide a settings dialog for managing the approved-account list, Outlook recipient, automatic-send preference, and relevant behavior such as OCR resource state. Account-number entry will normalize formats and prevent accidental empty/duplicate allowlist rows.

Maintain the stated privacy contract. Receipt image files will not be copied; the database will retain the selected source path, raw OCR text, and accepted fields only. The application will expose **Open data folder** and document that users should keep this folder protected. Application logs will avoid writing complete receipt OCR contents or sensitive account/money values unless diagnostic logging is deliberately enabled with appropriate notice.

Add practical resilience features: recoverable OCR errors, clear handling for moved/deleted source images, read-only/locked Excel output, unavailable Outlook, database backup/migration protection, and disabled double-submission while a save is active.

### Phase 7 — Test, package, and document

Build automated tests that exercise the system without live Outlook or network dependencies. Use a mockable OCR adapter and email adapter so tests are deterministic.

| Test area | Required coverage |
|---|---|
| Normalization/extraction | Arabic and Western digits; English/Arabic label variations; date/time and money parsing; missing/ambiguous candidates. |
| Manual-review contract | OCR candidates populate editable fields; users can overwrite every field; user changes are what is submitted. |
| Validation | Empty or malformed values, invalid date/time, zero/negative money, unapproved account, and duplicate receipt number each produce actionable error feedback and no record. |
| Persistence/reporting | Valid receipt saves exactly once, Excel includes accepted normalized values, duplicate database insertion is rejected, and existing data survives migration. |
| Side-effect ordering | OCR alone causes no persistence/report/email; Excel/email run only after a successful verified save. |
| Outlook adapter | Attachment, recipient, and error handling are tested against a mocked COM interface; Windows smoke testing covers a real classic Outlook setup. |
| UI workflow | Receipt selection/reset, OCR loading/error state, manual correction retention, keyboard focus, and disabled double-click save behavior. |

Package the Python application with PyInstaller, test the packaged executable on a clean Windows system, and then produce a Windows installer. Update the README with Python setup/run commands, packaging commands, OCR first-run expectation, classic Outlook limitations, data location, and the mandatory review-before-save workflow.

## Acceptance criteria

The Python application will be considered complete when all of the following are true:

1. It runs as a native Windows desktop program with no Node.js or Electron runtime requirement.
2. Selecting and processing a receipt displays both the image and editable OCR candidates for account number, receipt number, receipt date/time, and money value.
3. A user can correct any candidate manually, and the current edited values—not the original OCR output—are what **Verify & save** validates and stores.
4. The system rejects unapproved accounts, duplicate receipt numbers, invalid/missing date-time values, and non-positive monetary values without saving or triggering Excel/email side effects.
5. A successful save writes the local SQLite record, updates `Instapay_Receipts.xlsx`, and performs the configured Outlook action after—not before—successful persistence.
6. Receipt image files are not copied, sensitive data has a defined protected local storage location, and Outlook credentials are not stored.
7. Tests cover the core extraction, correction, validation, persistence, reporting, and side-effect sequencing behaviors, and the packaged application is smoke-tested on Windows.

## Assumptions, decisions, and open risks

This plan assumes the target platform is Windows, classic Outlook remains the required mail client, and the current requirement is a new Python rewrite rather than a partial migration of the existing Electron user interface. It selects **PySide6**, **SQLite**, **openpyxl**, **pywin32**, and a local bilingual OCR engine as the baseline; these choices can be adapted after reviewing actual receipt samples and existing data files.

The principal technical risk is bilingual receipt extraction reliability, especially for layout-specific Arabic labels and stylized/low-quality images. The planned mitigation is to treat OCR as an assistive candidate generator, surface raw text and image preview for manual checking, retain test fixtures for all receipt formats, and keep parsing/OCR behind replaceable interfaces.

A secondary risk is Outlook COM availability: it requires Windows and the locally installed, signed-in classic Outlook client, and organizational policy may prompt or prevent automatic sends. The implementation will communicate that outcome clearly and preserve the saved record and Excel output regardless.

The current source tree and sample receipt images were not available in the workspace during planning. After approval, the first execution step will inspect or obtain them to preserve compatible fields, Excel format, and any existing local SQLite data where required.

## Deliverables after approval

The implementation phase will provide the Python source project, dependency and packaging configuration, automated tests, Windows executable/installer instructions (and installer artifact when the environment supports a Windows build), updated README, and a concise verification report describing tested flows and any environment-specific limitations.
