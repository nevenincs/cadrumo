# aeat

Spanish tax authority (AEAT) automation -- tax information retrieval and filing tools.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)

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

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Enable required APIs
gcloud services enable sheets.googleapis.com
gcloud services enable drive.googleapis.com
gcloud services enable storage.googleapis.com
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
