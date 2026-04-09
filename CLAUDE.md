# CLAUDE.md

## Project

AEAT - Spanish tax authority (Agencia Estatal de Administración Tributaria) automation tools for tax information retrieval and filing. Python 3.13 monorepo using uv, hatchling, src layout.

## MCP Servers (`.mcp.json`)

| Server | Command | Purpose |
|---|---|---|
| `playwright` | `npx -y @playwright/mcp --headless` | Headless browser automation for AEAT website browsing and data extraction |
| `context7` | `npx -y @upstash/context7-mcp` | Documentation and library lookup |
| `google-workspace` | `uvx workspace-mcp --tool-tier core` | Google Drive, Sheets, Docs, Gmail, Calendar (OAuth 2.1 via env vars) |

Google OAuth credentials are read from environment variables (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`), never stored in repo files.

## Tech Stack

- **Language:** Python 3.13
- **Package manager:** uv (no pip)
- **Build backend:** hatchling
- **Linter/formatter:** ruff
- **Type checker:** mypy (strict mode)
- **Tests:** pytest + pytest-playwright
- **Pre-commit:** ruff, mypy, trailing whitespace, YAML/TOML checks, private key detection
- **Key deps:** google-api-python-client, gspread, google-cloud-storage, playwright, pydantic, httpx, python-dotenv

## Project Layout

```
src/aeat/          # Main package
tests/             # Test suite
.mcp.json          # MCP server config (committed, no secrets)
.env.example       # Environment variable template
pyproject.toml     # Project and tool configuration
```

## Commands

```bash
uv sync                          # Install all dependencies
uv run pytest                    # Run tests
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run mypy src/                 # Type check
uv run pre-commit run --all-files  # Run all pre-commit hooks
uv run playwright install chromium # Install browser
```

## Rules

- Never commit secrets, credentials, or `.env` files
- Use src layout (`src/aeat/`) for all package code
- Run `uv sync` not `pip install`
- All Python code must pass ruff and mypy strict
