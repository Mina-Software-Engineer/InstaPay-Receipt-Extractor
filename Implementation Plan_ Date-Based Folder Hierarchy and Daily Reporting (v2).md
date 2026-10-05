# Implementation Plan: Date-Based Folder Hierarchy and Daily Reporting (v2)

## Goal

Reorganize the reporting system to use a date-based folder structure. For every day that receipts are recorded, the application will create a dedicated folder (e.g., `11-Aug-2026`). Inside this folder, it will generate a daily Excel report and a ZIP archive of images. When sending via Outlook, the **Excel file will be attached as a standalone document**, and the **images will be attached as a single ZIP archive**.

## Proposed Hierarchy

```text
.instapay_receipts/
└── 11-Aug-2026/
    ├── Instapay_Receipts_11_Aug_2026.xlsx  <-- Attached as File
    └── Instapay_Receipt_Images_11_Aug_2026.zip <-- Attached as Zip
```

## Key Changes

### 1. Database Logic (`database.py`)
- The `get_all_receipts` method will be used to fetch records, but we will filter them in the reporting layer based on the `created_at` timestamp to ensure we only process receipts "recorded" on the target day.

### 2. Reporting Logic (`reporting.py`)
- **`generate_excel_report`**: Modified to accept a `target_folder` and `date_str`. It will filter for receipts created on that date and save as `Instapay_Receipts_{date_str}.xlsx`.
- **`generate_images_zip`**: Modified to accept a `target_folder` and `date_str`. It will bundle images for receipts created on that date into `Instapay_Receipt_Images_{date_str}.zip`.

### 3. Application Logic (`app.py`)
- **Dynamic Path Management**: The app will generate a `today_str` (e.g., `11-Aug-2026`) and create a subfolder in the data directory.
- **Verification Workflow**: After a successful save:
    1. Resolve the daily folder path.
    2. Generate the Excel file and ZIP file inside that specific folder.
    3. Pass both distinct paths to the Outlook service.

### 4. Outlook Service (`services.py`)
- **Attachment Handling**: Ensure `send_excel_report` (or a renamed `send_daily_report`) accepts multiple specific paths. It will attach the `.xlsx` file and the `.zip` file as two separate attachments in the same email.

## Implementation Steps

### Phase 1: Update Reporting & Database
- Update `reporting.py` to handle the new naming convention and folder structure.
- Ensure the filtering logic correctly identifies receipts based on the current system date (recording date).

### Phase 2: Update UI & Workflow
- Update `MainWindow.verify_and_save` in `app.py` to:
    - Create the daily directory.
    - Call the updated reporting functions with the new paths.
    - Pass both the Excel and ZIP paths to the email service.

### Phase 3: Final Verification
- Verify that the Outlook email contains two distinct attachments: the Excel spreadsheet and the zipped image folder.
- Ensure that older daily folders remain untouched and organized.

## Assumptions & Risks
- **Assumption**: Even if a receipt has an old date (e.g., from 10-Aug), if it is recorded on 11-Aug, it belongs in the 11-Aug folder.
- **Risk**: Large images might make the ZIP file exceed Outlook's attachment limit (usually 20-25MB). We will use `ZIP_DEFLATED` to maximize compression.
