---
name: aeat-project-mandates
trigger: always_on
---

# aeat project mandates

Project mandates for every contributor (human or agent). Read before any change. These are imperatives, not prose.

## North star
- Kent is the user — a Spanish autónomo filing his taxes. Every change answers: "What can Kent do now that he couldn't before?"
- Product direction: **produce → verify → export**. Kent self-files by uploading an exported fichero BOE to the AEAT portal.
- Must READ `ROADMAP.md` and `CONTRIBUTING.md` before your first change.
- CONSULT charters: product #197, safety #116, env gate #117, PM #240.

## Live AEAT writes (non-negotiable)
- DO NOT introduce a default-enabled AEAT write path.
- DO NOT register `aeat submission submit` in any CLI surface (default OR hidden) until 1.0.0 reintroduces live submission. The CLI module was excised on 2026-04-18 per `.vault/adr/2026-04-18-live-submit-cli-excision-adr.md`. Programmatic callers that genuinely need the live path MUST construct `SubmissionEngine(..., live_transport_supported=True)` explicitly.
- DO NOT add `live_transport_supported=True` as a default to any new `SubmissionEngine` factory or constructor wrapper; the engine default is False (opt-in only). Verify with `rg -n 'live_transport_supported=True' src/aeat/` — only test sites should match.
- FOLLOW the 4-factor gate (kept as defense in depth for any future reintroduction): `AEAT_ALLOW_LIVE_SUBMIT_OPT_IN=1` + `AEAT_LIVE_SUBMIT_ENABLED=1` + `--i-understand-this-is-real` + per-submission prompt.
- When live submission is reintroduced in 1.0.0, it MUST route through a pluggable `AuthProvider` (see `.vault/adr/2026-04-18-auth-provider-abstraction-adr.md`, EPIC #279): certificate, Cl@ve Permanente, Cl@ve Móvil, or Cl@ve PIN.
- Live submission is deferred to milestone 1.0.0.
- DO keep `aeat submission preflight` and `aeat submission dry-run` — they are primary pre-export gates.
- Must READ `.vault/adr/2026-04-17-export-first-adr.md` AND `.vault/adr/2026-04-18-live-submit-cli-excision-adr.md` before touching submission code.
- CONSULT live-write safety charter #116 for the six non-negotiable rules.

## Kent's journey
- Must READ `.vault/audit/2026-04-17-kent-ux-journey-audit.md` and `.vault/audit/2026-04-17-kent-revise-review-audit.md`.
- Every PR closing a Kent wall MUST ship a regression-prevention test.
- Utilize `docs/coverage/modelos.md`, `docs/coverage/kent-capabilities.md`, `docs/coverage/pipeline.md` as the single source of truth.
- DO update coverage matrices in every PR that changes per-modelo / per-capability / per-pipeline-stage state.

## Issue and PR discipline
- Issue titles MUST lead with a Kent capability.
- Acceptance criteria MUST be Kent-observable (non-developer-verifiable).
- Labels MUST include type, domain, priority (`P0-blocker..P3-low`), effort (`XS..XL`), `parallel-safe|risky`.
- DO only pick up issues labelled `ready` + `parallel-safe` without explicit assignment.
- DO NOT pick up `parallel-risky` issues without coordinating.
- DO NOT pick up `needs-design` issues without first producing an ADR.
- DO use issue templates under `.github/ISSUE_TEMPLATE/`.
- FOLLOW `CONTRIBUTING.md` DoR and DoD checklists.

## Delegation (up to 6 parallel agent slots)
- Handover prompts MUST be agent-agnostic — no hardcoded CLI names.
- FOLLOW the canonical handover template (project memory: `handover_prompt_template`).
- Any slot (Claude, Codex, Gemini) may pick any `ready` + `parallel-safe` issue.

## Subagent scope
- Subagents are for CONTEXT ENRICHMENT only — raw discovery, inventory, command maps, file counts, issue lists.
- The primary contributor (human or agent) does the UX reasoning, user-journey narration, verdict judgment, and recommendations.
- DO NOT ask subagents for strengths / gaps / scores / verdicts; they produce shallow generic output.
- DO imagine the user (Kent) and narrate his actual steps — that is work only the primary can do.

## Vaultspec rule management
- Project mandates live at `.vaultspec/rules/rules/aeat-project-mandates.md` — the single source of truth.
- Edit the custom rule, then run `uv run vaultspec-core install --force` to resync all providers.
- DO NOT hand-author root `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`; they are generated config stubs.
- If you find hand-authored prose in root config files, migrate it to a custom vaultspec rule via `spec rules add` (or direct write to `.vaultspec/rules/rules/*.md`).
- The custom rule source is force-tracked (`git add -f`) despite `.vaultspec/` being gitignored.
- DO NOT edit the `>>> vaultspec-managed <<<` block in `.gitignore`. Additions and negations go AFTER the closing marker.
- Add new custom rules via `uv run vaultspec-core spec rules add --name <name> --content "..."` OR direct write to `.vaultspec/rules/rules/<name>.md`.

## EPIC shape
- EPICs MUST have ≤5 children. If a cluster needs more, split into focused sub-EPICs and retain the original as a tracking umbrella.
- Every EPIC title leads with a Kent capability ("Kent can {do X}").
- When splitting an umbrella, add a comment listing the split sub-EPICs and mark the umbrella as tracker-only.

## Milestone shape
- Every milestone title is a Kent-capability statement: "X.Y.Z — Kent can {do something}".
- Every milestone description MUST open with ONE observable success moment — a single event that proves the milestone shipped.
- Milestones have NO calendar due dates until capacity is committed.
- DO NOT pack infrastructure into milestones without citing the Kent capability it unblocks.

## Verification is first-class
- Produce → **verify** → export. Verification is a product surface, not an implementation detail.
- Kent MUST be able to prove his exported numbers match AEAT's record (#239).
- Every exported artifact MUST have a round-trip verification path (serialise → reparse → diff).

## Audit cadence
- Monthly: coverage #241, duplication #242, code health #243, Kent regression #244.
- Quarterly: charter compliance #245, architectural review #246.
- Per-milestone gate: methodology #109, per-milestone instances #110–#113.

## Code structure
- All Python lives under `src/aeat/<subpackage>/`.
- DO use relative imports inside `src/aeat/` (`.module`, `..sibling`). DO NOT use absolute `aeat.*` imports inside `src/aeat/`.
- Cross-subpackage imports from the subpackage root only.
- DO use Pydantic v2 frozen models for every boundary-crossing structure.
- DO use Enums for closed catalogues, dataclasses for internal values.
- DO NOT use bare dicts at boundaries.
- DO inherit all domain errors from `aeat.errors.AeatError`.
- DO use `aeat.logging.get_logger(__name__)`.
- DO declare every env var in `src/aeat/config.py` Settings and document it in `.env.example`.

## Testing
- Testing is pytest-only.
- DO NOT use `unittest`, `unittest.mock`, `mock`, `pytest_mock`, `pytest_httpx`, `time_machine`, `freezegun`, or `vcr`.
- DO apply markers at module level via `pytestmark = [pytest.mark.<access>, pytest.mark.<domain>]`. DO NOT apply per-function access/domain markers.
- Axis A (exactly one): `unit`, `live_read`, or `live_write`.
- Axis B (at least one): `domain_aeat_remote`, `domain_submission`, `domain_financial_input`, `domain_local_state`, `domain_mediation`, or `domain_infra`.
- Live tests MUST NOT contain mocks, patches, shadows, fakes, or stubs.
- Unit tests colocate with the module (Rust-style).
- `live_read` requires `AEAT_LIVE_TESTS_ENABLED=1`; Google Workspace `live_read` additionally requires `AEAT_LIVE_TESTS_GOOGLE=1`.
- `live_write` tests are collection-banned; three-factor interactive bypass only.
- Coverage floor is 60% on `src/aeat` via `just test-cov`.
- CONSULT `tests/README.md` and `.vault/adr/2026-04-17-pytest-markers-adr.md`.

## Trilingual contract
- Handle `es` / `en` / `hu`: Spanish is the default output language and the authoritative AEAT terminology baseline, English is for code and docs, and Hungarian is used for user-facing output when `AEAT_OUTPUT_LANGUAGE=hu`.
- DO use the nested-dict `Translatable` TypedDict for stored user-facing strings.
- DO NOT use gettext or `.po` files.
- `AEAT_OUTPUT_LANGUAGE` default is `es`.

## Commits and releases
- Conventional commits are mandatory: `<type>(<scope>): <subject>`. Valid types: feat, fix, perf, revert, docs, refactor, chore, test, build, ci, style.
- Releases run LOCALLY via `just release` and `just release-apply`.
- DO NOT add `.github/workflows/release-please.yml`.
- Version source of truth: `pyproject.toml [project].version`; mirrored in `src/aeat/__init__.py __version__` and `.release-please-manifest.json`.
- CONSULT `RELEASING.md` and `.vault/adr/2026-04-12-release-please-adr.md`.

## Documentation
- DO use Google-style docstrings and type hints on all public signatures.
- DO NOT create documentation files unless explicitly requested.

## Forbidden patterns
- DO NOT introduce a default-enabled AEAT write path.
- DO NOT add `.github/workflows/release-please.yml`.
- DO NOT use mocks / fakes / stubs in `live_read` or `live_write` tests.
- DO NOT use absolute `aeat.*` imports inside `src/aeat/`.
- DO NOT commit secrets (`credentials/`, `service-account*.json`, `token.json`, OAuth JSONs, `providers.json`).

## Key references
- Product charter: #197
- Safety charter: #116
- Env-gate hardening: #117
- PM charter: #240
- Roadmap: `ROADMAP.md`
- Contributing: `CONTRIBUTING.md`
- Kent audits: `.vault/audit/2026-04-17-kent-ux-journey-audit.md`, `.vault/audit/2026-04-17-kent-revise-review-audit.md`
- Export-first ADR: `.vault/adr/2026-04-17-export-first-adr.md`
- Coverage matrices: `docs/coverage/modelos.md`, `docs/coverage/kent-capabilities.md`, `docs/coverage/pipeline.md`
- Testing: `tests/README.md`
- Releasing: `RELEASING.md`
