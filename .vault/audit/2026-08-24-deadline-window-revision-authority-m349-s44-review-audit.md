---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:790308baa94c494709cb33d0044e9356e14290be277f642d73e579a6f2b32956'
related: []
---
# `deadline-window-revision-authority` audit: `m349 s44 review`

## Scope

Reviewed Modelo 349 Step S44 as landed in commit `32977aebf8` plus its focused working-tree regression. The review covered the exact 2022-2026 monthly and quarterly census, bundled AEAT calendar and statutory plazo provenance, canonical revision ownership and authority projection, construct closure, and absence of a redeclared selector, resolver, period parser, cadence authority, supported-year horizon, or deadline catalogue. Vaultspec RAG semantic discovery was followed by exact-symbol inspection of the changed surface and the shared authorities.

## Findings

### unsupported-2027-physical-close | high | Two 2026 filing coordinates hard-code an ungrounded Saturday close

The `12` and `4T` windows for filing year 2026 both declare `closes_on = 2027-01-30`. That physical date is outside every bundled contributor calendar cited by this change, falls on a Saturday, and is deliberately left without a 2027 calendar source. The statutory thirty-natural-day rule grounds the nominal interval but does not prove that Saturday as the operator-visible terminal filing date; the implementation plan expressly forbids inferring a date. The focused regression repeats the same unsupported value, so it cannot independently prove source fidelity. S44 therefore cannot attest all 80 cells as officially grounded.

### non-atomic-commit-scope | high | The M349 commit includes an unrelated filing-capability worklist rewrite

Commit `32977aebf8`, whose subject declares Modelo 349 deadline windows, also changes `test_filing_capability_worklist.py` by roughly 270 lines across owner routing and terminal product-scope behavior. Those edits are outside S44's declared Modelo 349 ownership, are unrelated to the 80-cell calendar repair, and were not covered by this focused review. This defeats atomic provenance and makes the commit unsuitable as the isolated evidence claimed by the execution record.

## Recommendations

- For `unsupported-2027-physical-close`, refuse or defer the two physical 2027 close facts until an official 2027 AEAT calendar is bundled and adjudicated, unless a separately accepted architecture explicitly represents a statutory nominal bound distinct from the actual operator deadline. Do not preserve `2027-01-30` as an exact filing close merely to satisfy the census.
- For `non-atomic-commit-scope`, separate the unrelated filing-capability changes from the Modelo 349 deadline change and subject them to their own owning Step and review before S44 is closed.
- Retain the current canonical reuse: semantic discovery and exact confirmation found only the shared `select_revision`, `Period`, `registry_period_kind`, deadline semantic-coordinate validation, `ValidatedRegistryAuthority.deadline_windows`, and existing filing-window resolver. No M349-specific redeclaration was found.

## Remediation status

- `unsupported-2027-physical-close` is remediated in the working corpus: the 2026 `12` and `4T` rows, their construct memberships, and their self-confirming regression values were removed. The exact census now reports 78 grounded cells and preserves `{2026 12, 2026 4T}` as an explicit residual. No replacement date is declared pending official 2027 calendar evidence.
- `non-atomic-commit-scope` remains a historical lifecycle finding. Commit `32977aebf8` cannot be made atomic without rewriting shared history or reverting unrelated peer work, neither of which this remediation is authorised to do. The execution record no longer presents that commit as isolated evidence.
- A repeated Vaultspec RAG search plus exact-symbol confirmation found no M349-specific selector, resolver, parser, cadence authority, supported-year horizon, or deadline catalogue. The remediation adds no code authority.
- S44 remains open because its complete 80-cell source-grounded outcome is not yet achievable from bundled evidence.
