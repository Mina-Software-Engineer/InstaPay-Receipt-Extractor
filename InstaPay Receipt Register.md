# InstaPay Receipt Register
## Application Feature and Functional Overview

**Prepared for:** A Large Food-Industrial Company  
**Application type:** Windows desktop application  
**Primary purpose:** Receipt capture, AI-assisted data extraction, human verification, validation, reporting, and controlled Outlook distribution

---

## 1. Executive Summary

The **InstaPay Receipt Register** is a Windows desktop application designed to help a company receive, process, verify, store, and report InstaPay receipt transactions in a controlled and repeatable way.

The application uses an Azure Computer Vision OCR service configured to read receipt images and extract the key transaction information. The extracted values are displayed on screen for a staff member to compare against the original receipt and correct when necessary. The record is not accepted until the required fields pass validation and the user confirms the information.

After verification, the application stores the transaction locally, organizes the daily output, creates an Excel report, creates a ZIP archive containing the relevant receipt images, and opens an Outlook email draft with the reports attached. This provides the company with a practical workflow for reducing manual data entry, improving consistency, and maintaining a consolidated record of receipt-based transactions.

> The application is an **AI-assisted registration and control system**, not an autonomous approval system. Human review remains part of the process before a receipt is saved.

---

## 2. Main Application Function

The main function of the application is to convert InstaPay receipt photographs into validated business records.

The operator selects one or more receipt images. The application sends each image to Azure Computer Vision OCR for extraction of the money value, recipient account number or label, receipt number, receipt date and time, Note text, and the numeric value contained in the Note. The results are shown in editable fields next to the image preview. The operator compares the extracted data with the receipt, corrects any inaccurate value, and selects **Save and Send**.

The application then validates the records against required rules and approved company-controlled lists. Valid records are saved in the local SQLite database and included in the appropriate daily report. The resulting Excel file and receipt-image ZIP archive are opened as attachments in a new Outlook draft for review by the designated recipients.

---

## 3. Core Features

### 3.1 Multi-Receipt Image Selection

The operator can select multiple receipt images in one operation rather than processing each file independently. Supported image formats include common formats such as PNG, JPG, JPEG, and BMP.

Selected receipts appear in a vertical thumbnail panel. Each thumbnail shows its sequence and processing status, allowing the operator to move between receipts and review the batch efficiently.

### 3.2 AI-Powered Receipt Data Extraction

The application uses an Azure Computer Vision OCR service as the primary extraction service. The model receives the receipt image and a purpose-built extraction instruction that requests structured transaction data.

The extraction fields are:

| Field | Description |
|---|---|
| Money Value | The transfer amount located next to or before the EGP currency label. Commas and numeric formatting are handled during validation. |
| Account Number/Label | The recipient account number or InstaPay label from the **To** section. The application is instructed not to use the sender’s account from the From section. |
| Receipt Number | The reference or receipt number shown after the Reference label. |
| Receipt Date/Time | The date and time shown on the receipt, with the expected display format of `DD MMM YYYY HH:MM AM/PM`. |
| Note | The complete Note text, which may contain a required business number. |
| Internal Note Number | The number extracted from inside the Note for validation. It is not displayed as a separate user field. |

The AI response is expected as JSON, which allows the application to map the extracted values into the review form. Defensive parsing and application-level validation remain in place because AI output must be checked before it becomes an official record.

### 3.3 Human Review and Manual Correction

The extracted values are displayed on the operator’s screen beside the selected receipt image. The operator can compare the original receipt with the extracted information and manually correct any field before verification.

This review step is particularly important for blurred photographs, unusual receipt layouts, Arabic or English text, low image quality, and account labels that may be visually similar. The application preserves the practical balance between automation and human control.

### 3.4 Contained Image Preview

The selected receipt is shown in a dedicated image-preview area. The preview keeps the image’s aspect ratio and scales it within the available user-interface area without allowing large source images to push the interface outside the window.

The preview automatically refreshes when the operator selects another thumbnail or resizes the application window.

### 3.5 Required-Field and Data Validation

Before saving, the application validates the transaction data. Validation is designed to prevent incomplete, duplicated, or unauthorized records from entering the company’s register.

The validation process includes:

| Validation control | Purpose |
|---|---|
| Required receipt number | Prevents saving a record without a reference number. |
| Duplicate receipt detection | Prevents a receipt number already stored in the database from being saved again. It also detects duplicates within the current batch. |
| Approved account validation | Confirms that the extracted or manually corrected recipient account number or label exists in the company-approved account list. |
| Positive money value | Confirms that the amount is numeric and greater than zero. Commas in values such as `25,000` are normalized before numeric validation. |
| Date and time validation | Confirms that the receipt date/time is present and follows the expected format. |
| Note-number requirement | Confirms that a number is present inside the Note when required. |
| Approved Note-number validation | Compares the Note number against the approved Note-number list maintained by the company. |

If a batch contains an error, the application selects the first receipt with an issue, displays the relevant record, and shows the validation message beside the affected field. The operator can correct the record and attempt the save again.

### 3.6 Approved Account Management

Authorized users can manage the list of approved recipient accounts or labels in Settings. Accounts may be added or removed, and the list is stored locally in the application database.

This control helps the company limit accepted receipts to recognized recipients and provides a configurable validation layer without changing the application code.

### 3.7 Approved Note-Number Management

The Settings window allows authorized users to add and remove approved Note numbers. These values are stored in the local database and are used to validate the number extracted from the Note field.

The Note number is intentionally not shown as a separate review field. The operator sees one Note field, while the application extracts the numeric portion internally for validation. The approved Note-number list can also be exported to an Excel report.

### 3.8 Multiple Email Recipient Management

The application supports multiple Outlook recipients. In Settings, users can:

- Add email addresses.
- Validate the basic email format before saving.
- Select or unselect recipients using checkboxes.
- Remove selected recipient entries.
- Send reports only to the currently enabled recipients.

This allows different departments, supervisors, finance personnel, or management recipients to receive the daily report according to the company’s operating procedure.

### 3.9 Local SQLite Persistence

The application uses SQLite for local persistence. The database stores receipt records, approved accounts, approved Note numbers, email recipients, application settings, and related transaction metadata.

Each saved receipt record can include the receipt number, recipient account or label, receipt date/time, money value, Note text, internal Note number, image path, and extracted raw response information. The receipt number is protected as a unique value in the database.

### 3.10 Daily Excel Reporting

After a successful save, the application generates a date-based Excel report containing the accepted receipt records. The reporting structure is designed to accommodate receipt dates that may be older than the date on which the records are entered.

The daily output follows a folder-based structure similar to:

```text
10-Aug-2026/
11-Aug-2026/
    Instapay_Receipts_11_Aug_2026.xlsx
    Instapay_Receipt_Images_11_Aug_2026.zip
```

The report folder is based on the reporting day, while the Excel data can contain receipts recorded from older dates.

### 3.11 Receipt-Image ZIP Archive

The application creates a separate ZIP archive containing the receipt images associated with the saved records. This keeps the Excel data report separate from the image archive while allowing both to be distributed together.

The ZIP archive provides a convenient way for the company to retain or transmit supporting receipt evidence alongside the structured transaction data.

### 3.12 Outlook Integration

The application integrates with the installed classic Outlook desktop client through Windows automation. It creates an email draft addressed to the enabled recipients and attaches:

1. The Excel receipt report.
2. The ZIP archive containing the receipt images.

The application uses Outlook’s **Display** behavior, allowing the user to review the draft before it is sent. The application does not store an Outlook password.

Successful use requires a compatible classic Outlook installation, a signed-in Outlook account, and company policies that permit the required automation behavior.

### 3.13 Windows Production Packaging

The project includes production packaging preparation for Windows. The PyInstaller specification supports creation of an executable and includes the application assets required at runtime, including the EDITA logo and contact icons.

The project also includes an installer-oriented structure for distributing the application to Windows workstations. The target experience is to provide an executable and setup package so that ordinary users do not need to install Python or the project’s development dependencies manually.

### 3.14 Settings and Configuration

The Settings window centralizes operational configuration, including:

- Azure Vision endpoint and API key.
- Approved recipient account numbers or labels.
- Approved Note numbers.
- Enabled Outlook email recipients.

This allows the same application build to be configured for different departments or operating teams without modifying the source code.

### 3.15 Data-Folder Access

The application provides an **Open Data Folder** action so authorized users can reach the location where the local database, reports, and generated output are stored.

This simplifies operational support, backup procedures, and controlled inspection of generated files.

### 3.16 Contact Developer Window

The left sidebar includes a **Contact Us** button. It opens a **Contact Developer** window containing clickable contact methods for WhatsApp, Facebook, and LinkedIn.

The contact buttons include supplied icons, gray text, tooltips, hover effects, centered labels, and smooth opening and closing transitions.

---

## 4. End-to-End Operating Workflow

The normal workflow for a staff member is as follows:

| Step | Operator action | Application result |
|---:|---|---|
| 1 | Open the application | The receipt register interface is displayed. |
| 2 | Select receipt images | Multiple images are loaded into the thumbnail panel. |
| 3 | Select Extract Data | The application processes each receipt sequentially using Azure Computer Vision OCR. |
| 4 | Monitor progress | A progress dialog displays extraction progress and the current image. |
| 5 | Select a thumbnail | The receipt image and extracted fields appear for review. |
| 6 | Compare and correct | The operator verifies the data against the image and edits fields where necessary. |
| 7 | Select Save and Send | The batch is validated against required fields and approved lists. |
| 8 | Correct any errors | The application selects the receipt with the issue and displays the validation message. |
| 9 | Save a valid batch | Records are committed to SQLite and daily reports are generated. |
| 10 | Review the email draft | Outlook opens a draft with the Excel file and image ZIP attached. |
| 11 | Send according to company policy | The user reviews and sends the Outlook message. |

---

## 5. Business Benefits for a Food-Industrial Company

For a large food-industrial company, the application can support departments that receive or review payment evidence related to suppliers, drivers, contractors, operational purchases, petty cash, employee reimbursements, or other controlled transactions.

The main operational benefits are the reduction of repetitive manual typing, earlier detection of duplicate receipts, controlled use of approved account lists, a consistent review process, and a consolidated daily reporting package. The image ZIP archive also helps preserve supporting evidence for reconciliation and internal review.

The application can improve process discipline because every receipt follows the same sequence: image selection, AI extraction, human comparison, validation, database storage, report generation, and email distribution.

| Business area | Potential benefit |
|---|---|
| Finance and accounting | More consistent receipt registration and easier daily reconciliation. |
| Procurement and purchasing | Controlled validation of approved recipient accounts and Note numbers. |
| Operations | Faster handling of batches of receipt images. |
| Internal control | Duplicate detection, mandatory fields, and review before acceptance. |
| Management reporting | Date-based Excel reports that can be distributed to selected recipients. |
| Audit support | Structured data linked to receipt-image evidence. |
| IT support | Local configuration, packaged Windows deployment, and accessible data folder. |

---

## 6. Security, Privacy, and Operational Considerations

Receipt images and transaction data may contain sensitive financial or business information. The company should protect the Windows user account, limit access to the application data folder, and establish a backup and retention policy appropriate to its internal controls.

Receipt images are sent to the configured Azure Computer Vision OCR service for extraction, so the company should review its AI vendor agreement, information-security policy, data-retention requirements, and any restrictions on transmitting financial documents to external services before production deployment.

The Azure Vision endpoint and API key should be treated as confidential and should be entered only through the application’s Settings workflow. It should not be embedded in source code, shared in email, or committed to a public repository.

Classic Outlook must be installed and signed in on the workstation used for report distribution. Company security settings may display an automation warning or restrict Outlook automation. These policies should be tested by the company’s IT department before rollout.

For a large-company deployment, the following controls are recommended as future enterprise enhancements if required:

- Centralized database or approved cloud storage.
- User authentication and role-based permissions.
- Encrypted local data and encrypted backups.
- Central audit log of edits, approvals, and report transmissions.
- Centralized configuration management.
- Monitoring of Azure Computer Vision OCR API failures and usage.
- Formal retention and deletion policies.
- Digitally signed installer and executable.
- Automated backup and disaster-recovery procedures.

---

## 7. Current Scope and Future Expansion Options

The current application is optimized for a controlled Windows workflow in which one operator processes receipt images, reviews the extracted data, and distributes the resulting reports through Outlook.

A large food-industrial company may later choose to expand the application into a multi-user departmental system. Possible future capabilities include a centralized server database, department-level access, approval stages, searchable historical transactions, dashboards, supplier or cost-center fields, ERP integration, automated scheduled reporting, and analytics on payment activity.

These expansions are not required for the current desktop workflow, but the existing separation between the interface, database, extraction service, reporting logic, and Outlook service provides a useful foundation for future development.

---

## 8. Summary of Delivered Functionality

The InstaPay Receipt Register provides a complete receipt-processing workflow for a Windows environment. Its principal capabilities are:

1. Selection and batch processing of multiple receipt images.
2. Azure Computer Vision OCR agent extraction of the required receipt fields.
3. Recipient-only account number or label extraction from the To section.
4. Internal extraction and validation of the Note number without displaying a separate Note-number field.
5. Human review and manual correction before acceptance.
6. Duplicate receipt-number detection.
7. Approved account and Note-number validation.
8. SQLite storage of accepted transactions and configuration data.
9. Date-based Excel report generation.
10. Separate ZIP archive generation for receipt images.
11. Outlook draft creation with both reports attached.
12. Multiple configurable email recipients.
13. Windows executable and installer preparation.
14. Configurable Settings window and accessible data folder.
15. Contact Developer window with clickable social-contact links.

> In summary, the application provides a controlled bridge between **receipt photographs** and **validated, reportable transaction records**, reducing manual effort while retaining a human verification point for business accuracy.

---

## 9. Conclusion

The InstaPay Receipt Register is suitable as a focused departmental tool for a large food-industrial company that needs to process receipt evidence consistently and distribute daily transaction reports. Its strongest value is the combination of AI-assisted extraction with human review and rule-based validation.

Before company-wide deployment, the organization should conduct a pilot using representative receipt images, confirm Azure Computer Vision OCR API and Outlook policies with IT and information security, define user access and data-retention rules, and agree on the required support and backup model. Once those operational controls are confirmed, the application can provide a practical foundation for faster receipt registration and more consistent daily reporting.
