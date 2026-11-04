---
tags:
  - '#research'
  - '#fixture-canonicalization'
date: '2026-11-04'
modified: '2026-11-04'
body_schema: 'body-v2'
body_hash: 'sha256:6ad4c4b11f44528d524e887d0aa19fb1c490cc8f2791567d122666ada73a421c'
related: []
---

# `fixture-canonicalization` research: `Fixture populations, divergence and controls`

Question: is taxpayer and filing-flow fixture data defined once and reused by the Python tests, the docs sequences, the desktop window and the native Rust tests, and are its generated forms controlled? Conclusion: no population shares scenario data with another. Generators reuse backend code but each invents its own taxpayer; most generators are run by hand only; one generated output is nondeterministic and one Rust copy is stale. Inventory taken 2026-11-04 on `feature/tui` at commit `2b42fefde9`.

## Findings

### Populations

- Desktop window: 457 Modelo envelopes under `native/desktop/frontend/src/dev/fixtures/modelo/` (about 49 MB), 13 flat JSON files and 14 TypeScript modules under `native/desktop/frontend/src/dev/fixtures/`. 49 of 94 stories import them; Rust reads envelopes with `include_str!` in `native/desktop/src-tauri/src/modelo/tests.rs:402`.
- Python tests: 307 files under `src/cadrumo/tests/fixtures/` (AEAT pages, justificantes, borrador, bank files) and 40 under `src/cadrumo/application/ledger/tests/_evidence_corpus/`, each specimen carrying a provenance sidecar.
- In-code taxpayers: about 177 test functions build a profile, 137 of them private helpers. Shared builders disagree: `REQUIRED_PROFILE_PLACEHOLDERS` stores the string `"false"` where `GENERAL_REGIME_NATURAL_PERSON_FACTS` (`src/cadrumo/domain/user_profile/tests/general_regime_facts.py`) stores `False`; `seed_ready_profile` exists twice (`ready_profile_support.py:27`, `src/cadrumo/entrypoints/tests/profile_persistence/import_flow_support.py:112`).
- Docs: 281 `.seq` step scripts, 213 recorded goldens and 9 seed recipes under `docs/_sequences/`, executed against the real CLI in `dev/docs/sequences/sandbox.py`, whose profile facts are restated inline at `dev/docs/sequences/sandbox.py:70`.
- Native: shared protocol vectors read in place by Rust, Python and TypeScript; `relay_contracts.json` and `cli_contract_fixtures.json` are generated and gated by CMake `--check` (`CMakeLists.txt:343`); `native/application/tests/data/modelo-303-admitted-baseline.json` is a hand copy of an envelope's `admitted_baseline`.

### Divergence

- No file is byte-identical across populations; divergence is semantic. Placeholder `12345678Z` is a taxpayer in the ledger corpus, the Borrador declarant, the Modelo 100 acceptance declarant, a child in `household.json` and an invoice buyer; `X1234567L` is a taxpayer in AEAT pages and a grandparent in `household.json`.
- No persona agrees across populations: window profile "Ana Soler Vidal" with null tax facts, Modelo envelopes "Garcia Lopez Ana", docs "Ana Garcia Lopez" under another profile id, docs Renta seed a 1985-born employee.
- 303 and 130 scenarios share no figures between window fixtures and docs goldens.
- The Rust 303 baseline carries digests absent from `src/cadrumo/_data/operations/contract_manifest.json` and expired on 2026-10-24.
- 38 commits touched two or more populations together, evidence of hand synchronisation. 444 commits touch the populations; the window fixtures saw 153 commits and 8.15M changed lines in 60 days.
- Fixed "today" instants and year literals appear in about six fixture producers; `calendar.ts` holds hand-written deadlines.

### Generators and determinism

- Window envelopes come from `native/desktop/frontend/scripts/modelo_fixtures.py` through real application services; `issued_at` and `observed_at` come from `clock_now()` when `admit_modelo_edit_baseline` receives no instant (`src/cadrumo/application/modelo/edit_admission.py:353`), so two consecutive runs differ in timestamps only.
- `dev/desktop_*_fixture.py` and `native/desktop/frontend/scripts/ledger_served_words.py` have `--check`, run in 2 to 5 seconds and are deterministic; nothing runs them automatically.
- Five ledger fixtures have no writer: `ledgerInvoicePreview`, `ledgerInvoiceMatch`, `ledgerRuleTrial`, `ledgerSplitCheck`, `ledgerInvoiceDuplicate`.
- The four `src/cadrumo/tests/fixtures` generators render with ReportLab `invariant=True` and are deterministic.

### Controls and precedents

- No just recipe or CI job generates or checks window fixtures; per-PR CI (`.github/workflows/merge-gate.yml`) has no frontend or Rust job.
- On-demand precedent: the registry authority is gitignored, published by `publish-authority --if-stale`, and staleness is a content digest of sources (`authority_database_currency`); setup recipes run it first. `content-build.mjs` writes frontend generated inputs to `build/<preset>` with an input fingerprint record. `dev/docs/sequences/verdict_cache.py` keys verdicts on a content hash.
- Hard constraints on committed outputs: Rust `include_str!` and TypeScript static JSON imports need files at compile time; docs goldens are committed by design so drift fails the build (`2026-07-13-docs-cli-sequences-adr`, D2).

### Placement

- `.importlinter:84` forbids shipped code from importing `dev`; `.importlinter:209` limits `cadrumo.tests` to core. A data-only directory needs no contract; `src` tests reach the repository root through `src/cadrumo/tests/inventory.py:20`.
- The wheel excludes tests and the sdist includes only listed roots (`pyproject.toml:238`), so `dev/` data ships nowhere.
- No operation takes a whole plaintext profile; fact entry is `ProfilePatchValue(question_id, value)` through the profile patch operation (`src/cadrumo/entrypoints/cli/config/operation_profile_patch.py`), ledger entry is `app ledger import --file`. A persona expressed as question ids and ledger rows can be replayed through production operations.

### Not investigated

Legal correctness of any fixture amount; whether CIF-shaped values such as `A58818501` or `src/cadrumo/tests/fixtures/aeat-sede/submitted-files/modelo-130-2026-1T-redacted.txt` hold real data; full runtime of the envelope generator (it failed on drift from uncommitted edits in the shared checkout).

## Sources

- `native/desktop/frontend/scripts/modelo_fixtures.py`
- `native/desktop/frontend/scripts/ledger_served_words.py`
- `native/desktop/src-tauri/src/modelo/tests.rs:402`
- `native/application/tests/data/modelo-303-admitted-baseline.json`
- `src/cadrumo/_data/operations/contract_manifest.json`
- `src/cadrumo/application/modelo/edit_admission.py:353`
- `src/cadrumo/domain/user_profile/tests/general_regime_facts.py`
- `src/cadrumo/entrypoints/tests/profile_persistence/import_flow_support.py:112`
- `src/cadrumo/entrypoints/cli/config/operation_profile_patch.py`
- `src/cadrumo/tests/inventory.py:20`
- `dev/docs/sequences/sandbox.py:70`
- `dev/docs/sequences/verdict_cache.py`
- `CMakeLists.txt:343`
- `.importlinter:84`, `.importlinter:209`
- `pyproject.toml:238`
- `.github/workflows/merge-gate.yml`
- commit `2b42fefde9`
