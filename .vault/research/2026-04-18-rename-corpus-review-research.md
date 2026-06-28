---
tags:
  - "#research"
  - "#rename-corpus-review"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-12-casilla-db-adr]]"
  - "[[2026-04-12-manual-practico-adr]]"
---

# Rename corpus review research

## Context

Issue `#225` clears the `reviewed_by` namespace before the Kent-centric review
workflow lands. The current corpus fields on casilla and manual records describe
developer review of AEAT definitions, but the bare `reviewed_*` names read like
future user-filing approval metadata.

## Findings

### Casillas surface facts

- `src/aeat/domain/casillas/models.py:111-112` defines `CasillaRecord.reviewed_by`
  and `CasillaRecord.reviewed_at` as persisted boundary fields.
- `src/aeat/domain/casillas/catalogue.py:77-92` enforces those fields when
  `AEAT_CASILLAS_REVIEW_REQUIRED` is enabled and emits user-facing verification
  messages that currently name `reviewed_by` and `reviewed_at`.
- `src/aeat/domain/casillas/catalogue.py:126` persists canonical JSON through
  `catalogue.model_dump(mode="json")`, so the field names on the Pydantic model
  directly control the on-disk key names.
- `src/aeat/domain/casillas/_test_catalogue.py:30-54` and
  `src/aeat/domain/casillas/_test_cli.py:18-61` build test fixtures with the old keys
  and assert the current review gate behavior.

### Manuals surface facts

- `src/aeat/domain/manuals/_schema.py:191-192`, `:238-239`, and `:274-275` define
  `reviewed_by` / `reviewed_at` on `Rule`, `Section`, and `Manual`.
- `src/aeat/domain/manuals/_loader.py:120-124` reconstructs `Manual` objects from raw
  JSON payloads, so schema field names also control the accepted and emitted
  manual JSON contract.
- `src/aeat/domain/manuals/errors.py:26-31` bakes the old field names into the review
  error description.
- `src/aeat/domain/manuals/test_schema.py`, `test_loader.py`, and `test_verify.py`
  all encode the old keys in model constructors and committed JSON fixtures.

### Persisted JSON and contributor docs still use the old keys

- Committed canonical casilla files under `corpus/casillas/` still serialize
  `reviewed_by` / `reviewed_at`, including:
  `corpus/casillas/modelo_130/2025Q4.json`,
  `corpus/casillas/modelo_303/2025Q4.json`, and
  `corpus/casillas/modelo_390/2025.json`.
- `docs/casillas.md:109-127`, `:157-158`, and `:220` still documents
  `reviewed_by` / `reviewed_at` as the canonical contributor contract.
- `src/aeat/entrypoints/cli/manual.py:237-238` prints the old names in the `aeat manual`
  CLI output, so the public presentation layer also needs the rename.

### Compatibility and migration implications

- A strict field rename without aliases will break every existing committed
  casilla corpus file and every manual JSON fixture because both subpackages
  parse raw JSON directly through `model_validate_json`.
- `save_casillas()` writes the canonical JSON from `model_dump(mode="json")`,
  so once the model fields are renamed the persisted key names will switch
  automatically. The same applies to manual JSON produced through
  `model_dump_json()` in tests and future tooling.
- There are two viable migration stances:
  1. compatibility-first: add parse aliases for the old keys so stale local JSON
     still loads while writers emit only the new keys,
  2. strict cutover: rewrite the checked-in corpus and tests in this branch and
     treat stale local JSON on the old keys as unsupported after the rename.
- A dedicated migration script is optional rather than required for this issue.
  The repository only has three checked-in casilla corpus files with the old
  keys, and the manual corpus structure is not committed yet.

### Terminology constraints and drift

- The Kent audit already names this as shadowing: `.vault/audit/2026-04-17-kent-revise-review-audit.md`
  records that `CasillaRecord.reviewed_by` and `Manual.reviewed_by` describe
  corpus-author review, not Kent reviewing his filing.
- The new names must stay definition-scoped everywhere they appear in code,
  tests, verification output, and contributor docs. Mixing `definition_reviewed_*`
  in models with old `reviewed_*` wording in CLI or docs would preserve the
  semantic drift the issue is trying to remove.
- This rename is intentionally scoped to corpus-definition review only. Other
  review metadata in the repo, such as `corpus/normatives/*` using
  `reviewed_by` plus `last_reviewed_at`, is a separate domain and should not be
  swept into this issue.

## Recommendation

- Rename the casillas and manuals schema fields to
  `definition_reviewed_by` / `definition_reviewed_at`.
- Rewrite committed `corpus/casillas/*.json`, the affected tests, CLI text, and
  contributor documentation so the repository no longer advertises the old
  namespace.
- If the team does not want an indefinite compatibility layer for local stale
  JSON, a strict cutover is operationally safe because the checked-in manual
  corpus is still only manifests and the checked-in casilla corpus is small.
