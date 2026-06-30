---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S26'
related:
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# W04.P09.S26 Calculation Registry Legal-Source Bundle Verification

Scope: legal/source bundle verifier behavior for calculation registry tests.

## Description

RAG grounding:

- `uvx vaultspec-rag search "legal source bundles authoritative calculation tests registry source_refs legal_refs corpus" --type code`
- `uvx vaultspec-rag search "registry calculation legal grounding authoritative source bundle" --type vault --doc-type adr`

The registry already required committed TOML `legal_refs` and `source_refs` to
resolve through catalogues and bundled corpus. The defect was in
`verify_legal_reference()`: bundled `required_text` validation was skipped when
`article is None`, including non-article and treaty refs. Required corpus text is
now validated before the article-specific branch returns.

## Outcome

Changed:

- `src/aeat/domain/calculations/registry/_legal.py`
- `src/aeat/domain/calculations/registry/tests/test_catalogue_verification_verifiers.py`

The worker audited catalogue shape: loaded legal catalogue was BOE-backed with
required text, and source catalogue refs were AEAT/BOE rather than `other`.
Focused tests and ruff passed in the worker run.

## Verification

Passed:

- `.venv\Scripts\python.exe -m pytest src/aeat/domain/calculations/registry/tests/test_catalogue_verification_verifiers.py src/aeat/domain/calculations/registry/tests/test_registry_legal_grounding.py` -> 38 passed in the worker run.
- `.venv\Scripts\ruff.exe check src/aeat/domain/calculations/registry/_legal.py src/aeat/domain/calculations/registry/tests/test_catalogue_verification_verifiers.py` -> passed.
- Isolated latest-HEAD focused P09 command, excluding source-catalogue baseline failures, contributed to 69 passed.
- W04 touched-file ruff gate in isolated latest-HEAD worktree passed.

Latest isolated retest note: clean `HEAD` currently fails source-catalogue
verification for `aeat-calendario-contribuyente-2026-domiciliacion` and
`boe-modelo-210-base-order` byte-count mismatches. A no-W04 baseline worktree
reproduced those failures, so they are recorded as baseline blockers outside S26.

