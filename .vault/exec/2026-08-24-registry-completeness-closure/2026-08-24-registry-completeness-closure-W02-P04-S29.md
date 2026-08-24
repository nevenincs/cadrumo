---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:8d8f35146bff23eb8de99575633a8a629c92e9d6924dfb254c0fb164ed81141b'
step_id: 'S29'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Prove every live filing gap has exactly one terminal refusal or one existing-plan owner and reconsideration condition

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`

## Description

- Keep the loaded capability worklist as the only filing-gap denominator.
- Guard authorable rows with the closed generic feature-domain vocabulary `registry-temporal-coverage`, `source-casilla-integration`, and `aeat-export-fragment-generator-authority`.
- Keep distinct terminal dispositions outside that vocabulary and reject an authorable row whose owner domain is not one of its three members.
- Preserve the exact predecessor mapping in this execution record, not in production or test source. Source contains no Vault locations, plan coordinates, plan-parser logic, or duplicated plan state.

## Outcome

The loaded worklist reports 14 non-emitting live revisions. Each has exactly one disposition class: twelve are authorable gaps with the accepted owner set below; Modelo 136 is `terminal_no_authority`; and Modelo 036 is the revision-specific `terminal_product_scope` disposition. Modelo 185 has only the export feature domain; it no longer carries a stale temporal diagnostic.

| Live revision | Disposition or generic owner domains | Exact accepted predecessor, verified open |
| --- | --- | --- |
| M036 / 2025-02-03-y-siguientes | `terminal_product_scope` | None; accepted product-boundary decision `c7126d6393` |
| M038 / 2002-y-siguientes | temporal; export | `W02.P05.S43`; `W04.P07.S96` |
| M136 / 2026 | `terminal_no_authority` | None; reconsider when revision-scoped machine authority exists |
| M182 / 2007-y-siguientes | temporal; source/casilla; export | `W02.P05.S44`; `W05.P17.S100`; `W05.P17.S101`; `W05.P17.S102`; `W05.P17.S103`; `W04.P07.S100` |
| M185 / 2003-2025 | export | `W04.P07.S101` |
| M187 / 2019-y-siguientes | temporal; source/casilla; export | `W02.P05.S45`; `W06.P20.S226`; `W04.P07.S102` |
| M188 / 2019-y-siguientes | temporal; source/casilla; export | `W02.P05.S46`; `W06.P20.S232`; `W04.P07.S103` |
| M194 / 2019-y-siguientes | temporal; source/casilla; export | `W02.P05.S47`; `W06.P20.S233`; `W04.P07.S104` |
| M220 / 2024 | source/casilla; export | `W06.P20.S227`; `W04.P07.S105` |
| M220 / 2025-y-siguientes | temporal; source/casilla; export | `W02.P05.S48`; `W06.P20.S227`; `W04.P07.S105` |
| M390 / 2021 | source/casilla; export | `W06.P20.S228`; `W04.P07.S106` |
| M721 / 2023-y-siguientes | temporal; source/casilla; export | `W02.P05.S49`; `W06.P20.S229`; `W04.P07.S97`; `W04.P07.S98`; `W04.P07.S99` |
| M763 / 2011-y-siguientes | temporal; source/casilla; export | `W02.P05.S50`; `W06.P20.S230`; `W04.P07.S107` |
| M840 / 2003-y-siguientes | source/casilla; export | `W06.P20.S231`; `W04.P07.S108` |

Vaultspec-RAG narrowed the classifier, composer, closure decision, and three owner plans; whole-file reads then established context. Exact `rg` checks confirmed every tabled predecessor row remains unchecked, and the fully-qualified feature namespace distinguishes repeated local step numbers such as `S100`. This is the durable ownership evidence; Python deliberately retains only the three generic domains.

The prior source-level route implementation was withdrawn because it embedded Vault paths and plan identifiers in the Python test. The generic-owner cleanup and the Modelo 036 disposition alignment landed in mixed remediation commit `32977aebf8`; the approved Modelo 036 product-boundary decision landed in `c7126d6393`. Commit `58e605ed6e` adds the closed-owner mutation: an authorable row using an unowned domain raises `ValueError`.

Focused validation passed: ruff and five focused worklist tests, including the exact Modelo 036 identity mutation and the unowned-domain mutation. The standing aggregate test enumerated the same 14 rows and remains intentionally red until accepted owners deliver their artifacts. No filing schema, source taxonomy, producer, export writer, layout, or filing authority was added or redeclared.

S29 remains unchecked pending independent review.

## Notes

The terminal rows remain in the visible denominator and are not silently converted into authorable support. The M136 mutation turns a copied revision source from `manual_pdf` into `xsd` and proves the terminal label retires into the export owner domain; the M036 mutation proves that a neighbouring revision or modelo cannot inherit the terminal product scope.
