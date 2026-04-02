# Baso Enterprise API Reference

## Authentication
- Use Bearer tokens in the Authorization header.
- Example: Authorization: Bearer YOUR_API_KEY
- Keep API keys secure and do not expose them in browser code.

## Core Concepts
- The API supports messaging and communication workflows.
- Group chats can support up to 1,024 participants per channel.
- Role-based permissions include Admin, Moderator, and Member.

## Typical Request Pattern
- Generate an API key from Developer Settings.
- Add the key to the Authorization header.
- Send requests over HTTPS.
- Log and validate responses during integration testing.

## Webhooks
- Use webhooks for event delivery into your application.
- Ensure your endpoint returns HTTP 200 within 3 seconds.
- Check the dashboard webhook logs if deliveries fail.

## Rate Limits
- Baso Enterprise API rate limits may vary by plan.
- For exact limits, refer to the active contract or billing plan.

## Troubleshooting
- If requests fail with 401, verify the Bearer token.
- If requests fail with 429, review rate limits or upgrade the plan.
- If webhook delivery fails, confirm the endpoint is publicly reachable.
