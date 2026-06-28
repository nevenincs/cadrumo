---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-00-adr-lock-in-exec]]"
  - "[[2026-04-30-aeat-restructure-step-01-pre-move-scan-exec]]"
---

# 2026-04-30-aeat-restructure step-02 phase-1 auth/_secret_adapters deletion

## status

Step 2 PR 1 of N. Carrier PR for Step 0 + Step 1 ADR amendments + plan amendment + migration-helper TODO annotations + the first Phase-1 dead-code deletion.

## scope

- Delete `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_secret_adapters.py` (whole module, 278 LOC).
- Delete `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_test_secret_adapters.py` (colocated test, ~190 LOC, 12 tests).
- Add `# TODO(#477):` annotations on all 5 `migrate_legacy_*_to_repository` helpers per Step 0 Decision 10 outcome.
- ADR amendments (Step 0/1 outcomes; test-marker rule extension to all 6 destination layers; Phase 2 dead-code list addition for `SchemaSource` enum slots).
- Plan amendment (migration-helper count correction 3 → 5; SchemaSource enum slots added to Step 10 list).

## pre-merge safety check

Per ADR Dead-code workstream / Pre-merge safety check requirement:

```
grep -rn "_secret_adapters|migrate_legacy_to_secret_store|EnvKeyringSecretStore|FileSecretAdapter" \
    --include="*.py" --include="*.toml" --include="*.cfg" --include="*.md" \
    --include="*.json" --include="*.yaml" --include="*.yml" .

grep -rn "KEY_GOOGLE_OAUTH_CLIENT|KEY_GOOGLE_SERVICE_ACCOUNT|KEY_GOOGLE_OAUTH_TOKEN_PREFIX|KEY_MCP_WORKSPACE_CREDENTIALS|google_oauth_token_key|load_secret_or_legacy" \
    --include="*.py" --include="*.toml" --include="*.cfg" --include="*.json" \
    --include="*.yaml" --include="*.yml" .
```

Result: zero non-test, non-self, non-vault references to any symbol in `_secret_adapters.py`. The module is genuinely dead in production. `aeat/adapters/outbound/aeat/auth/__init__.py` does NOT re-export from `_secret_adapters`.

## verification

- `python -c "import aeat"`: succeeds.
- `pytest --collect-only`: 6783/6807 tests collected (24 deselected); zero collection errors. Test count drop matches the 12 deleted tests in `_test_secret_adapters.py`.

## additional content riding in this PR

### ADR amendments (`.vault/adr/2026-04-30-aeat-restructure-adr.md`)

1. Approval gate section: appended `### Step 0/1 outcomes (recorded 2026-04-30)` recording Decision 6 (`DELETE`), Decision 10 (`RETAIN with TODO(#477)`), and Step 1 sub-pass 3 manual-override-list outcome (zero-length, audit-grounded).
2. Test-marker realignment / Migration mechanic — per-test-file: extended from 2 destination layers (`domain/`, `adapters/persistence/`) to ALL 6 layers (`domain/`, `adapters/persistence/`, `adapters/inbound/`, `adapters/outbound/`, `application/`, `core/`) per Step 1 finding. The ~37 destination-aware reclassifications (`submission/_formats/*` → `domain_outbound + domain_export`; `review/*` → `domain_application`; `identity/*` → `domain_inbound`) are listed.
3. Dead-code workstream / Phase 2 list: added the 3 `SchemaSource` reserved enum members + their `_models.py` docstring + `test_models.py` references (per Step 0 Decision 6 outcome). Clarified the migration helpers are NOT in Phase 2 per Decision 10 (`RETAIN with TODO(#477)`).

### Plan amendment (`.vault/plan/2026-04-30-aeat-restructure-plan.md`)

Step 10 description: corrected the migration-helper count from 3 to 5 (the actual count surfaced by Step 0 audit); listed the 5 helper names; added the 3 `SchemaSource` reserved enum members to the Step 10 deletion list.

### Migration-helper TODO annotations (5 source files)

Added `# TODO(#477): remove after 2026-10-27 retention window per restructure ADR Decision 10.` immediately above each helper's `def` line in:

- `src/aeat/adapters/outbound/aeat/export/_repository.py:194`
- `src/aeat/application/filing/_complementaria_repository.py:181`
- `src/aeat/application/filing/_history_repository.py:179`
- `src/aeat/application/filing/_repository.py:205`
- `src/aeat/domain/justificante/_repository.py:178`

### Exec records committed

- `.vault/exec/2026-04-30-aeat-restructure/2026-04-30-aeat-restructure-step-00-adr-lock-in-exec.md` (Step 0 record)
- `.vault/exec/2026-04-30-aeat-restructure/2026-04-30-aeat-restructure-step-01-pre-move-scan-exec.md` (Step 1 record)
- this record (Step 2 sub-PR)

## findings (FIX / FILE / STRIKE matrix)

The deletion of `_secret_adapters.py` + its test surfaced no in-code findings beyond the deletion itself. Vault references in `.vault/audit/2026-04-30-secure-persistence-foundation-upstream-reconciliation-audit.md`, `.vault/exec/2026-04-28-secure-persistence-foundation-exec.md`, and several research-doc rows mention `_secret_adapters` in past-tense audit context — those are forensic vault records (Tier 4 archive) and are not edited per ADR Vault-corpus supersession Tier 4 treatment.

## next step

Step 2 PR 2 — next Phase-1 deletion item. Candidates by ordering:

1. `auth._providers.describe_certificate_provider` — `__all__` removal.
2. `filing.utc_now` — `__all__` removal.
3. `llm._FakeAdapter` — `__all__` removal.
4. `llm.ProviderRequest` — `__all__` removal.
5. `schema._extractor.py` — whole 27-LOC file deletion.

Each subsequent PR ships its own exec record at
`.vault/exec/2026-04-30-aeat-restructure/2026-04-30-aeat-restructure-step-02-phase1-<slug>-exec.md`.
