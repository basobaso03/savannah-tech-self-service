# Troubleshooting Guide

## SSH Connection Refused
1. Confirm the server is powered on.
2. Check firewall rules and port 22 access.
3. Verify the correct private key or password.
4. Use the web console if firewall rules locked you out.

## Webhook Deliveries Failing
1. Check webhook logs in the dashboard.
2. Confirm the receiving endpoint returns HTTP 200 quickly.
3. Verify the endpoint is publicly accessible.
4. Remove firewall or challenge rules that block delivery.

## Rate Limit Errors
- A 429 error means the plan limit was reached.
- Review the current plan or request a higher tier.

## Payment Failed
- The system retries failed payments after 3 days and then after 7 days.
- If payment is still not received after 14 days, service may be suspended.
- Services may be terminated after 30 days of non-payment.

## First Diagnostic Questions
- What product are you using?
- What exact error message do you see?
- When did the issue start?
- What changed right before the issue began?
