---
step_id: S668
tags:
  - "#exec"
  - "#codebase-solidification"
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-31-codebase-solidification-audit]]"
---

# codebase-solidification W26.P59 — S668–S671 execution record

Executor: coder-alpha31. Prior coder alpha30 hit session limit with all
working-tree changes in place but no commits landed.

## S668 — `_app_live.py` wire-payload splat cluster (9 sites)

**Commit**: `83188512c`

Lines 1062, 1088, 1176, 1362, 1392, 1456, 1509, 1561, 1637 each received
`CAST-RATIONALE-WIRE-PAYLOAD-<scope>` inline markers on the existing
`# type: ignore[arg-type]` lines. Line 1681 remains DEFERRED (hard bucket).

Allowlist paydown: 9 entries removed from `_KNOWN_VIOLATING_LINES`.

## S669 — `_modelo.py` three sub-clusters (13 sites)

**Commit**: `20645d51b`

- Sub-A (4 sites, lines 892–915): `kv_pairs` splats — `CAST-RATIONALE-WIRE-PAYLOAD-MODELO*` markers.
- Sub-B (6 sites, lines 3111–3152): `Decimal(Optional[str])` — `assert x is not None` guards replacing `[arg-type]` ignores.
- Sub-C (3 sites, lines 5780–5782): `_enum()` → Literal fields — `CAST-RATIONALE-MARITIME-LITERAL-FIELD` markers.

Allowlist paydown: 13 entries removed.

## S670 — 6 misc moderate sites across 6 files

**Commit**: `68a40f38c`

| File | Fix |
|------|-----|
| `_parser.py:519` | `col_x_max is None or` guard removes `[operator]` |
| `_envelope.py:158` | `CAST-RATIONALE-GENERIC-CLASSGETITEM` marker on existing ignore |
| `_iva_wallet_reconciliation.py:196` | Typed `CalculationObservationRepository | None` annotation |
| `_doc_reference.py:526` | `isinstance(schema_cls, type)` narrowing removes `[union-attr]` |
| `_identity_placement.py:1028` | `isinstance(node.operand.value, (int, float))` narrowing |
| `_descendant_facts.py:207` | `cast(Literal[0, 33, 65] | None, ...)` with `CAST-RATIONALE-DISCAPACIDAD-LITERAL` |

Also fixed 2 `_doc_reference.py` rationale comments that alpha30 displaced
>3 lines from their `# type: ignore` targets (lines 174, 304) — placed
bridging rationale comments within the 3-line window.

Allowlist paydown: 6 entries removed.

## S671 — Closure test + ratchet update

**Commit**: `30439bb62`

- `test_w26_p59_closure.py`: 24-case suite (all pass) verifying all 28 S668–S670 fixes.
- `test_type_ignore_rationale_inventory.py`: `_KNOWN_VIOLATING_LINES` ratcheted to 11 (39 – 28).
- Main ratchet + prior-wave ratchets all green.

## Final state

| Metric | Value |
|--------|-------|
| Sites paid down | 28 |
| Allowlist before P59 | 39 |
| Allowlist after P59 | 11 |
| Steps closed | S668, S669, S670, S671 |
| Test suite | 24/24 pass |
