# Retained Hermes Runtime Secret

This Stack creates a retained Secrets Manager container for Telegram runtime
configuration. The Secret starts with `{}`; populate its value out of band.

Required JSON fields:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USERS`
- `TELEGRAM_HOME_CHANNEL`
- optional `TELEGRAM_HOME_CHANNEL_THREAD_ID`

```sh
./deploy/hermes-runtime-secrets/validate-template.sh
```

The Secret value must never enter CloudFormation parameters, Git, shell
history, chat, logs, or model context. Use the templates under `policies/` for
temporary deployment and narrow write-only credential operation, rendered
outside this repository.
