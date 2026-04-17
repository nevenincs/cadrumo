Spanish tax authority (AEAT) automation — Python 3.13, uv, hatchling, src layout.
MCP tooling: Playwright (headless browser), Context7 (docs), Google Workspace (Drive, Sheets, Docs) — see `.mcp.json`.
All environment variables must be defined in `src/aeat/config.py` via the pydantic-settings `Settings` model and documented in `.env.example` — `tests/test_config.py` enforces alignment.
Testing uses pytest with a two-axis marker taxonomy applied at module level via `pytestmark = [pytest.mark.<access>, pytest.mark.<domain>]`; per-function access or domain markers are forbidden. **Axis A (access, mutually exclusive):** every test carries exactly one of `unit`, `live_read`, or `live_write`. **Axis B (domain):** every test carries at least one of `domain_aeat_remote`, `domain_submission`, `domain_financial_input`, `domain_local_state`, `domain_mediation`, `domain_infra`. Unit tests may use mocks; live tests (`live_read` AND `live_write`) must never contain mocks, patches, shadows, fakes, or stubs. Unit tests live inside each module's directory (Rust-style colocated tests). `live_read` opts in via `AEAT_LIVE_TESTS_ENABLED=1`; Google Workspace `live_read` additionally requires `AEAT_LIVE_TESTS_GOOGLE=1` and project-owned fixtures provisioned via `just google-fixtures-provision` — see `scripts/README.md`. `live_write` tests are collection-banned by default (drop-not-skip) and require a three-factor interactive bypass; zero `live_write` tests exist today. See `tests/README.md` and charter `#116`.
Use Google-style docstrings and type hints on all public signatures.

## Module Structure & API Rules
- All Python code lives under `src/aeat/`.
- **Public API Discipline**: Code outside a subpackage must import only from the subpackage root (e.g., `from aeat.models import ModelCatalogue`).
- **Types**: Use Enums for closed catalogues, Pydantic models for wire/config, and dataclasses for internal values. No bare dicts.
- **Errors**: All domain errors inherit from `aeat.errors.AeatError`.
- **Logging**: Always use `aeat.logging.get_logger(__name__)`.
- **Trilingual Contract**: The system handles Spanish (es), English (en), and Hungarian (hu). Spanish is the authoritative language for AEAT domain terminology. English is the authoritative language for internal code and documentation. Hungarian is the target output language for user-facing content. We use a Nested-dict shape (`Translatable` TypedDict) for storage and avoid gettext or `.po` files.

## Commits & Releases
- **Conventional commits are mandatory** on every commit on every branch. Format: `<type>(<scope>): <subject>`. Valid types: `feat`, `fix`, `perf`, `revert`, `docs`, `refactor`, `chore`, `test`, `build`, `ci`, `style`. The type drives the CHANGELOG section when `just release` runs — see `RELEASING.md` and `.vault/adr/2026-04-12-release-please-adr.md`.
- **Releases run LOCALLY, never in CI.** GitHub Actions is permanently disabled on this repo. `just release` previews the next release via release-please in dry-run mode; `just release-apply` guides the human operator through the bump + tag locally. Nothing is ever pushed automatically. **Do not add a `.github/workflows/release-please.yml` file** — `tests/test_release_config.py` fails if one appears.
- **Version source of truth:** `pyproject.toml [project].version` is canonical. `src/aeat/__init__.py __version__` and `.release-please-manifest.json` mirror it. All three must agree — enforced by `tests/test_release_config.py`.

<vaultspec type="config">
## Vaultspec Rules

You MUST respect these rules at all times:

@.claude/rules/vaultspec-cli.builtin.md
@.claude/rules/vaultspec-system.builtin.md
@.claude/rules/vaultspec.builtin.md
</vaultspec>
