# Secrets Policy

- Never print secrets in logs.
- Never commit .env.
- Never send API keys to Telegram.
- Never expose /opt/automation over static file server.
- Webhooks must use a shared secret header.
