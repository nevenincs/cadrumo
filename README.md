# aeat

Spanish tax authority (AEAT) automation -- tax information retrieval and filing tools.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`)

## Setup

```bash
# Install dependencies
uv sync

# Install Playwright browsers
uv run playwright install chromium

# Install pre-commit hooks
uv run pre-commit install

# Copy and configure environment variables
cp .env.example .env
```

## Google Cloud Configuration

### 1. Create a Google Cloud Project

```bash
# Create project (or use an existing one)
gcloud projects create YOUR_PROJECT_ID --name="AEAT Automation"
gcloud config set project YOUR_PROJECT_ID
```

### 2. Enable Required APIs

```bash
gcloud services enable \
    sheets.googleapis.com \
    drive.googleapis.com \
    storage.googleapis.com \
    cloudfunctions.googleapis.com
```

| API | Purpose |
|-----|---------|
| Google Sheets API | Read/write spreadsheet data |
| Google Drive API | List, find, create, and manage files and folders |
| Cloud Storage API | Store documents and exports |
| Cloud Functions API | Future: serverless automation triggers |

### 3. Authentication Methods

The project supports three authentication methods, resolved in priority order
by `aeat.auth.get_credentials()`:

#### Option A: Service Account (recommended for automation)

Best for server-side, headless, and CI/CD environments.

```bash
# Create a service account
gcloud iam service-accounts create aeat-automation \
    --display-name="AEAT Automation"

# Grant roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:aeat-automation@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/drive.file"

# Download key file
gcloud iam service-accounts keys create credentials/service-account.json \
    --iam-account=aeat-automation@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

Then set in `.env`:
```
GOOGLE_APPLICATION_CREDENTIALS=credentials/service-account.json
```

> **Domain-wide delegation:** To access Workspace files owned by other users,
> enable domain-wide delegation in the Admin console and set
> `GOOGLE_IMPERSONATE_EMAIL` to the target user's email.

#### Option B: OAuth 2.0 Desktop App (recommended for development)

Best for local development with user-delegated access.

1. Go to [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Download the client ID and secret

Then set in `.env`:
```
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

On first run, a browser window opens for consent. The resulting token is cached
in `.tokens/google_oauth_token.json` and refreshed automatically.

#### Option C: Application Default Credentials (quick start)

For local development without explicit credentials:

```bash
gcloud auth application-default login \
    --scopes="https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/cloud-platform"
```

### 4. Required API Scopes

| Scope | Grants |
|-------|--------|
| `drive` | Full read/write access to Google Drive |
| `spreadsheets` | Full read/write access to Google Sheets |
| `cloud-platform` | Access to Cloud Functions, Cloud Storage, and other GCP services |

Narrower read-only scopes (`drive.readonly`, `spreadsheets.readonly`,
`drive.file`) are available in `aeat.auth` for least-privilege scenarios.

### 5. Token Management

| Method | Token storage | Refresh |
|--------|---------------|---------|
| Service Account | No token file — credentials are self-contained | Automatic |
| OAuth 2.0 | `.tokens/google_oauth_token.json` | Automatic via refresh token |
| ADC | `~/.config/gcloud/application_default_credentials.json` | Via `gcloud` |

The `.tokens/` directory is git-ignored. Never commit token files or
service account keys.

## Usage

```python
from aeat.config import load_settings
from aeat.auth import get_credentials, build_drive_service, build_sheets_service

settings = load_settings()
creds = get_credentials(settings)

drive = build_drive_service(creds)
sheets = build_sheets_service(creds)
```

## Development

```bash
# Run tests
uv run pytest

# Lint & format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy src/
```

## License

Apache 2.0 -- see [LICENSE](LICENSE).
