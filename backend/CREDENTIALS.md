# Backend Credentials Setup

## 1) Copy environment template

```bash
cp .env.example .env
```

## 2) Required credentials

Set these in `.env`:

- `DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>`
- `GEE_PROJECT=<gcp-project-id>`
- `GEE_SERVICE_ACCOUNT=<service-account>@<project>.iam.gserviceaccount.com`
- `GEE_PRIVATE_KEY_FILE=/absolute/path/to/service-account-key.json`

## 3) Authentication modes

### Recommended (server/deploy)

Use service-account credentials (`GEE_SERVICE_ACCOUNT`, `GEE_PRIVATE_KEY_FILE`) with `INGESTION_INTERACTIVE_AUTH=false`.

### Local fallback

Set `INGESTION_INTERACTIVE_AUTH=true` to allow interactive OAuth (`ee.Authenticate()`).

## 4) Date window behavior

For polygon submission requests:

- If `INGESTION_START_DATE` / `INGESTION_END_DATE` are not set:
  - start date = submit date minus `INGESTION_LOOKBACK_MONTHS` (default 6)
  - end date = submit date (server current date)
- If `INGESTION_START_DATE` / `INGESTION_END_DATE` are set, those values are used.

## 5) Suggested defaults

```env
INGESTION_START_DATE=
INGESTION_END_DATE=
INGESTION_LOOKBACK_MONTHS=6
INGESTION_INTERACTIVE_AUTH=false
```

## 6) Security notes

- Keep service-account JSON outside the repository when possible.
- Never commit `GEE_PRIVATE_KEY_FILE` contents.
- Rotate key immediately if exposed.
