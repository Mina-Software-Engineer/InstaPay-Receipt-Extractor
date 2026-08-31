# Implementation Plan: Manual OCR Review Before Receipt Verification

## Goal

Update **InstaPay Receipt Register** so every OCR run visibly presents its extracted results to the operator before any validation or persistence takes place. The operator must be able to compare the OCR output against the selected receipt image, manually edit any incorrect field, and then explicitly choose **Verify & save**. Only the values currently shown in the editable inputs—not hidden OCR-only values—will be validated and saved.

## Scope and intended workflow

| Stage | User-visible behavior | Required application behavior |
|---|---|---|
| 1. Select receipt | The user chooses a receipt image. | Clear any prior receipt-review state and display the selected image/path. |
| 2. Run OCR | The app displays an in-progress state, then shows the recognized raw text and the four extracted fields. | Execute existing bilingual OCR and field-extraction logic; do not save, reject, or email at this stage. |
| 3. Review and correct | The user visually compares the image with the OCR results and can overwrite any field. | Render editable, pre-populated controls for account number, receipt number, receipt date/time, and money value; preserve user edits in UI state. |
| 4. Verify & save | The user clicks a clearly labeled action after reviewing values. | Validate the values currently in the inputs; check approved account and duplicate receipt number; show field-specific feedback without losing corrections. |
| 5. Accepted receipt | After a successful save, the app confirms success and updates its report/email flow according to existing settings. | Persist the accepted, normalized values and OCR audit data, regenerate Excel, and invoke the existing optional Outlook-send behavior. |

## Implementation steps

### 1. Inspect and map the current implementation

After approval, locate the Electron entry process, renderer/UI components, OCR extraction module, inter-process communication handlers, SQLite persistence layer, and automated tests. Trace the current transition from image selection through OCR, validation, save, Excel regeneration, and Outlook sending.

The implementation will identify whether the current behavior validates or saves immediately after OCR. Any such side effect will be split so OCR is strictly an extraction step and validation/save remains a separate, user-initiated operation.

### 2. Define an explicit receipt-review state model

Introduce or standardize a renderer state object representing one pending receipt review. It should distinguish:

| State element | Purpose |
|---|---|
| Selected image metadata | Supports image preview, accessible alt text, and saved source path. |
| OCR status and error | Controls loading, retry, and error UI without treating a failed OCR result as a verified receipt. |
| Raw OCR text | Lets the operator compare extraction context when needed; it remains non-authoritative. |
| Extracted field defaults | Pre-populates the editable controls after OCR succeeds. |
| Editable field values | The exact operator-visible values submitted for verification. |
| Per-field validation messages | Displays formatting/required-value issues next to the relevant input. |
| Verification/save status | Prevents duplicate submissions and presents a clear success/failure result. |

The UI will initialize editable values from the OCR result once per selected image, then will never overwrite active user edits unless the operator selects a new image or intentionally reruns OCR and confirms reset behavior.

### 3. Build the review interface

Modify the receipt-processing screen to show the receipt image alongside a structured **Review OCR results** form after extraction completes. The form will include labeled inputs for **Account number**, **Receipt number**, **Receipt date and time**, and **Money value**, each prefilled from OCR and directly editable.

The layout will make the current stage unambiguous: OCR completion means “ready for review,” not “accepted.” The **Verify & save** action will remain disabled while no image is selected, OCR is running, or a verification request is in progress. It will be enabled even if OCR extracted an empty or malformed field, so the operator can enter the correct value manually; validation feedback will then guide correction.

For usability, date/time input formatting will match the existing supported locale/normalization logic, and currency input will accept a user-friendly numeric representation before canonical conversion. If the app already has design-system components, styles, or accessibility conventions, the new form will reuse them.

### 4. Separate OCR extraction from verification and persistence

Refactor the OCR handler/API contract, if necessary, to return a structured extraction payload such as image metadata, raw text, and candidate fields. It must not call database insertion, Excel regeneration, duplicate checks that produce a final rejection, or Outlook automation.

Create or adjust the **Verify & save** handler so it receives the currently edited values from the renderer. On the trusted process side, it will:

1. Trim and normalize input (for example, Arabic/English numeral conversion if supported today, whitespace cleanup, canonical money/date formatting).
2. Run all required validation: non-empty values, valid date/time, positive monetary amount, approved-account membership, and receipt-number uniqueness.
3. Return structured, field-level validation errors to the UI when a check fails, retaining all user-entered values.
4. On success, save the normalized, accepted fields plus existing audit metadata (source image path and raw OCR text where currently retained).
5. Trigger the existing Excel regeneration and configured automatic Outlook email only after the database save succeeds.

Server/main-process validation will remain authoritative even if the renderer includes convenience validation, ensuring direct UI manipulation cannot bypass approved-account or duplicate checks.

### 5. Preserve data handling and audit semantics

Maintain the stated privacy model: receipt image files are referenced but not copied, and only the existing permitted metadata is stored. The plan will confirm that manually corrected values are what appear in SQLite and `Instapay_Receipts.xlsx`, while the raw OCR text can remain as an audit/reference field if that is the current product behavior.

If the schema already separates extracted and accepted values, retain that distinction. If it has only accepted columns, avoid a migration unless retaining original OCR candidates is an explicit product requirement. Any required migration will be versioned and backward-compatible with existing local data.

### 6. Test the workflow end to end

Add or update automated tests at the levels supported by the repository. Test fixtures will use representative English and Arabic OCR outputs without relying on a live first-run language-data download.

| Test category | Coverage |
|---|---|
| OCR-to-form mapping | All four candidates populate their matching editable inputs; missing candidates leave editable blank values. |
| Manual corrections | A changed account/receipt number/date-time/money value is sent to verification and saved as the edited value rather than the original OCR candidate. |
| Review-state safety | Selecting a different image resets the prior form; ordinary UI re-renders do not erase manual edits. |
| Validation | Invalid/empty date-time, non-positive money, unauthorized account, and duplicate receipt number show clear errors and do not persist a record. |
| Successful save | A valid corrected receipt produces one SQLite record, regenerates the Excel report, and follows existing email-on-save settings. |
| Regression | OCR completion alone has no save, Excel, email, or final acceptance side effect. |
| Error handling | OCR and database/Excel/email failures remain understandable, do not falsely report success, and leave the user able to retry when safe. |

Manual acceptance testing on Windows will cover receipt-image preview, Arabic and English sample receipts, keyboard navigation, screen-size/layout behavior, and the Outlook behavior in both manual-send and automatic-send configurations.

### 7. Validate packaging and document the change

Run the project’s existing lint, unit/integration test, and build commands, then build the Windows installer through the documented distribution command. Verify the packaged application on Windows with a pre-existing local database where feasible.

Update the README or in-app guidance to clarify that OCR results are **suggestions requiring operator review**, and that the values displayed in the editable form are the ones validated and saved after **Verify & save**.

## Acceptance criteria

The work will be complete when a user can select a receipt, see the image plus all OCR-extracted values, edit any value, and press **Verify & save**; the application validates and persists the edited values only after that explicit action. Incorrect OCR output must be correctable without reprocessing the image, rejected data must not trigger Excel/email side effects, and existing accepted-receipt reporting behavior must still work after success.

## Assumptions and risks

This plan assumes the app is an Electron/Node.js Windows desktop project, as indicated by the documented `npm` workflow and Outlook COM automation, and that the existing OCR flow already yields candidate values plus raw text. The source files are not currently available in the workspace, so exact file paths, component architecture, validation-library APIs, database schema, and test commands will be confirmed immediately after approval.

The main product decision assumed here is that users manually compare OCR candidates with a visible receipt preview and must explicitly submit them. If automatic rejection on preliminary OCR extraction is currently intentional, it will be changed so only **Verify & save** performs final validation. The plan does not alter the approved-account database, Excel report layout, or Outlook recipient/settings behavior except to ensure they operate only after a successful verified save.

A residual operational risk is that classic Outlook may display security prompts or be blocked by organization policy; that behavior is external to the manual-review change and will be regression-tested rather than bypassed.

## Deliverables after approval

The implementation phase will provide the updated source code, automated tests or test updates, documentation changes, and a concise change summary including the exact validation/build results and any environment-specific constraints found during code inspection.
