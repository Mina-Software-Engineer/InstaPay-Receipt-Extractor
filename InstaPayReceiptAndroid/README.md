# InstaPay Receipt Register — Android Kotlin/XML Clone

This project is the native Android direction for the existing InstaPay Receipt Register desktop application. It uses **Kotlin, XML layouts, Material 3, Room, ViewModel, Retrofit, Apache POI, FileProvider, and repository-based clean architecture**.

## Verified report and email attachments

The Home workflow is review-first. The user selects receipt images, extracts the first active receipt, corrects the editable values, and taps **Verify & save**. The **Send Excel + images** button remains disabled until verification succeeds without errors.

After successful verification, the app creates two app-private report artifacts:

1. An `.xlsx` workbook with the same desktop report columns: `Date`, `Value`, `Client Code`, and `Receipt No`.
2. A `.zip` archive containing every selected/scanned receipt image, with safe numbered filenames and the correct image extension.

The Android `FileProvider` exposes both files through temporary read-only content URIs. Tapping **Send Excel + images** opens the Android email/share chooser with both files attached. The user can select Microsoft Outlook (or another installed mail client), and Outlook receives the Excel workbook and receipt-image ZIP as attachments. This is the Android-safe equivalent of the desktop app's Outlook COM automation; the app does not automate Outlook internals.

Reports are only generated after all validation checks pass. Validation failure does not create or share report artifacts.

## Approved Note-number Excel import

Authorized users can maintain the approved Note-number list from **Settings → Approved Note numbers**. The manager is protected by the administrator password currently initialized to `123456`.

Choose **Import Excel file** and select an `.xlsx` or `.xls` workbook. The importer reads the first worksheet locally. The first non-empty column is treated as the Note number and the second column is optional descriptive text/name. Common headers are skipped. Arabic-Indic and Persian digits are normalized, duplicates are ignored, and invalid rows are reported before additive merge into Room.

During **Verify & save**, the Note number must exist in the approved Room list. An unapproved Note number prevents the receipt from being saved and prevents report/email side effects.

## Azure OCR parity

The Android OCR implementation ports the desktop `services.py` `OcrService` behavior, including Azure Vision `read`, block/page/content line fallback, Arabic/English labels, RTL-aware parsing, recipient account extraction, EGP money parsing, date normalization, Note extraction, and detailed Azure error reporting. Account extraction returns numeric recipient accounts or `@instapay` handles, not display names.

## Build

Open the `InstaPayReceiptAndroid` folder in Android Studio with a recent Android Gradle Plugin. Sync Gradle, enter the Azure endpoint and key from the drawer's **Settings** screen, then run on an Android 8+ device or emulator. The current session does not include a Gradle wrapper, so final compilation should be performed by Android Studio after Gradle sync.
