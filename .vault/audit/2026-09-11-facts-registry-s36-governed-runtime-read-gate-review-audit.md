---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:564febe7f0db20c709dcf49e787412e3a074f551c14b23e63b1b0aefb23778d5'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S36 governed runtime read gate review`

## Scope

Read-only re-review of the S36 remediation against W04.P18.S36, the governed-fact authority decision, the S80 IVA retirement ledger, and the live product-runtime reader census. Development compiler tooling and tests stay outside the gate. The country-name vocabulary remains technical, and the IVA catalogue settings value remains path wiring rather than a raw file read.

## Findings

### computed-path-and-builtin-loader-bypasses | medium | Resolved: immediate computed reads and builtin imports now refuse

Literal and simple literal-starred path sequences are resolved before classification. A non-resolvable starred path now fails closed when its result is immediately read. The dynamic loader detector now rejects literal `__import__` and builtins-qualified forms in addition to `importlib.import_module`; focused mutations prove direct, resolved-starred, unresolved-starred, and both builtin loader routes are detected.

### source-wide-s80-exceptions | medium | Resolved: ledger exceptions now bind to the named reader entrypoint

The gate retains each S80 reader symbol and matches a raw-table access only when it occurs within that named function or class method, or within a narrow wrapper that invokes that reader. The sole source-only repository entry is narrowed to `IvaCatalogueRepository._load`. A mutation proves that a new direct `place_of_supply.toml` read in `classification.py` outside `place_of_supply_rule` fails, while the named repository adapter and the legitimate territorial reader remain admitted.

## Recommendations

Final verdict: CLEAR. Retain the runtime-only scope and the ledger-derived S80 exceptions until S81 through S84 remove the raw legal tables. Keep the discriminating computed-path, builtin-loader, and source-scope mutations with this gate.
