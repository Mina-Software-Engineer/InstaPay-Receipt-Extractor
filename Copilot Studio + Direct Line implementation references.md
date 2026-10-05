# Copilot Studio + Direct Line implementation references

## Official Microsoft sources

- Copilot Studio custom/native app integration: https://learn.microsoft.com/en-us/microsoft-copilot-studio/publication-connect-bot-to-custom-application
  - Copilot Studio exposes a Token Endpoint from the agent's Channels > Mobile app/custom app configuration.
  - The custom application calls the token endpoint, receives a Direct Line token and may receive a conversationId, then communicates through Direct Line.

- Direct Line API 3.0 reference: https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-direct-line-3-0-api-reference?view=azure-bot-service-4.0
  - Global base URL: https://directline.botframework.com
  - Requests use Authorization: Bearer SECRET_OR_TOKEN.
  - Start conversation: POST /v3/directline/conversations.
  - Get activities: GET /v3/directline/conversations/{conversationId}/activities.
  - Upload and send files: POST /v3/directline/conversations/{conversationId}/upload?userId={userId}.
  - Uploaded files can be sent as a single binary body or multipart form data with an optional application/vnd.microsoft.activity part.

- Direct Line send activity and attachment upload: https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-direct-line-3-0-send-activity?view=azure-bot-service-4.0
  - Local images can be sent through the upload endpoint with image/jpeg or image/png content type and Content-Disposition filename.
  - Multipart upload can include an Activity object containing the prompt text.

- Copilot Studio file input: https://learn.microsoft.com/en-us/microsoft-copilot-studio/image-input-analysis
  - File uploads must be enabled in Generative AI > File processing capabilities.
  - JPG and PNG are supported; the documented individual file size limit is 15 MB.

## Adapter decisions

- The existing public adapter call remains OcrService.process_receipt(image_path, credential).
- The Admin field stores the Copilot Studio Token Endpoint, not a model API key.
- The adapter obtains a Direct Line token with GET token_endpoint.
- If the token response includes conversationId, it is reused. Otherwise, the adapter starts a conversation with POST /v3/directline/conversations.
- The receipt image and extraction prompt are sent using the Direct Line multipart upload endpoint.
- The adapter polls activities until it receives a bot message and parses JSON into the existing seven fields.
- Outlook integration remains unchanged.
