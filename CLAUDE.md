Spanish tax authority (AEAT) automation — Python 3.13, uv, hatchling, src layout.
MCP tooling: Playwright (headless browser), Context7 (docs), Google Workspace (Drive, Sheets, Docs) — see `.mcp.json`.
All environment variables must be defined in `src/aeat/config.py` via the pydantic-settings `Settings` model and documented in `.env.example` — `tests/test_config.py` enforces alignment.
Testing uses pytest. Unit tests may use mocks; live integration tests must never contain mocks, patches, shadows, fakes, or stubs. All tests must carry `@pytest.mark.unit` or `@pytest.mark.live` markers. Unit tests live inside each module's directory (Rust-style colocated tests).
Use Google-style docstrings and type hints on all public signatures.

## Module Structure & API Rules
- All Python code lives under `src/aeat/`.
- **Public API Discipline**: Code outside a subpackage must import only from the subpackage root (e.g., `from aeat.models import ModelCatalogue`).
- **Types**: Use Enums for closed catalogues, Pydantic models for wire/config, and dataclasses for internal values. No bare dicts.
- **Errors**: All domain errors inherit from `aeat.errors.AeatError`.
- **Logging**: Always use `aeat.logging.get_logger(__name__)`.

<vaultspec type="config">
## Vaultspec Rules

You MUST respect these rules at all times:

@.claude/rules/vaultspec-cli.builtin.md
@.claude/rules/vaultspec-system.builtin.md
@.claude/rules/vaultspec.builtin.md
</vaultspec>
