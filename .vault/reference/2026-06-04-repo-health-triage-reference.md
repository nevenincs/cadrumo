---
tags:
  - '#reference'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:832336ffffb8c400b08c3e972911b13cfd0ef01687e97642a91dda6bf734cce7'
related:
  - '[[2026-06-04-repo-health-triage-research]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# `repo-health-triage` reference

## Discovery method

The codebase was searched through the resident VaultSpec RAG service on port `8766` using `vaultspec-rag search --port 8766`. This avoided opening the local Qdrant store from a second process.

## Semantic query ledger

- Code duplication query: `code duplication repeated implementation clone group workbook parity registry fragments duplicated parser mapping`.
- Shim query: `shim compatibility wrapper re-export __getattr__ __all__ deprecated adapter facade legacy alias`.
- Test shortcut query: `fake stub monkeypatch mock patch skip xfail tautological test shortcut`.
- Boundary query: `relative import violation top level reexports architecture boundary import linter layer contract adapters tests domain application`.
- Complexity query: `complexity cognitive load monolithic CLI modelo work_calculate ledger actions formula runtime split function extraction`.
- Site discovery query: `AEAT site discovery sede portal URL crawler scraping official corpus source mirror HTTP plaintext endpoint`.
- Vault duplication query: `repo health diagnostics type import boundary complexity dependency dead code duplication semgrep ruff`.
- Registry adjacency query: `registry hardening next work complexity bindings schema workbook parity fragmentation`.
- Secure-storage test hygiene query: `secure storage production hardening monkeypatch fake stub test isolation mock inventory`.

## High-signal anchors

Structural anchors:

  violations.
- `lint-imports` analyzes 1925 files and 7863 dependencies, with 3 kept contracts
  and 1 broken layered-architecture contract.

Type anchors:

- `ty check src --output-format concise` reports 1014 diagnostics.
- Pyright reports 2370 errors and 495 warnings.
- Root-cause families are aggregation source-kind taxonomy, secure repository
  payload typing, optional narrowing, constructor coercion, private API test
  access, and strict generic annotations.

Complexity anchors:

- Radon reports 284 C-or-worse blocks.
- Complexipy reports total cognitive complexity of 21856 over 1926 files.
- High-priority files include `src/cadrumo/entrypoints/cli/_modelo.py`,
  `src/cadrumo/entrypoints/cli/_ledger.py`, and

Hygiene anchors:

- `deptry` reports 6 dependency issues: `formulas`, `rich`, `torch`,
  `playwright_stealth`, and `prompt_toolkit`.
- `vulture` reports 15 candidates, including Google API unused variables, one SQL
  import, one submission protocol variable, and CLI doc-reference imports.
- `jscpd` reports 22 clone groups with 0.24 percent duplicated lines.
- `rg` found 68 lines matching high-risk test shortcut tokens, but many are
  protective guardrails or legitimate environment-isolation fixtures.

Security and site anchors:

- Semgrep reports 159 blocking findings over 17782 tracked files, but mixes
  production code, tests, mirrored official data, and fixtures.
  `src/cadrumo/adapters/outbound/aeat/sede/__init__.py`, and

## Agent synthesis

The type/boundary explorer prioritized structural import policy, relative imports,
aggregation source-kind typing, secure repository payload typing, local narrowing,
and strict generic cleanup.

The complexity explorer prioritized modelo CLI, modelo application orchestration,
registry binding families, formula runtime initialization, ledger CLI/actions, and
live/auth as the later high-risk cluster.

The duplication/test-hygiene explorer added the following high-signal items:

  shim gate fails before checking the repository.
  undocumented `monkeypatch.setattr` sites around `_drive_service`.
  shim duplicating the filing-status token.
- `src/cadrumo/core/parsing/__init__.py` carries private underscore compatibility
  aliases.
  should be reviewed as a placeholder-named backend.
- URL authority is spread across `src/cadrumo/core/external_constants.toml`, portal
  entries, registry cross-reference TOMLs, and Sede adapters. The
  strong control, but depends on complete planned-operation declarations.
