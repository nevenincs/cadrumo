---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:5a5dd3484ddb7359bf699d05c6c30cb55d9f56b8b457e362a4da4a9fc15d006c'
step_id: 'S77'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Correct Modelo 182 statutory filer-population wording and reconsideration scope

## Scope

- `.vault/reference/2026-08-24-registry-completeness-closure-modelo-182-design-era-and-donor-row-reference.md`
- `.vault/exec/2026-08-24-registry-completeness-closure/2026-08-24-registry-completeness-closure-W02-P03-S15.md`
- `src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py`

## Description

- Apply the S15 independent-review correction without promoting Modelo 182 or creating a second legal-filer authority.
- State the Article-3 statutory classes and the 2025 type-1 nature-3/type-2 administrator evidence at the existing filing-subject reference epicentre.
- Preserve the donor-row source owner and prove that type-1 declarant nature cannot be smuggled into donor-row observations.

## Outcome

The existing S15 reference now names all three Article-3 filer classes: recipient entities, the named political-party cases, and protected-estate holders or administrators. It distinguishes those classes from donor detail rows and requires a future filing decision to provide complete type-1/type-2 ownership, including protected-estate holder identity when an administrator files. No filing grade, exporter, source resolver, binding, or parallel legal declaration was added.

The focused mutation regression supplies `declarant_nature = "3"` to `DonativoDonorObservation` and receives strict-schema refusal. This prevents a future implementation from disguising a protected-estate filer header as donor detail data.

## Verification

- `uvx vaultspec-rag search "Modelo 182 legal filing subject declarant protected estate administrator donor row" --type code` located the sole donor-row family at `src/cadrumo/domain/calculations/registry/_donativo_bindings.py`; whole-file reading and targeted `rg` confirmed its canonical deferred source boundary and no production filer-population redeclaration.
- `uvx vaultspec-rag search "Modelo 182 statutory filer population protected estate administrator donor detail row source ownership" --type vault --doc-type adr,plan,audit,research,reference,exec` located the S15 review, S15 reference, and the existing W05.P17 owner.
- `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py -q` â€” 53 passed.
- `git diff --check -- <Step-scope files>` â€” passed.
- `vaultspec-core vault check modified-stamp --feature registry-completeness-closure` â€” clean.

## Notes

- This Step corrects the earlier S15 prose and binds the legal population to its established authority reference; it does not alter the non-fileable disposition.
- The next implementation remains in the existing temporal, source/casilla, and export owner routes. It must establish the full type-1/type-2 lifecycle before Modelo 182 can be reconsidered for filing grade.

## Handoff

Independent review must confirm that no Article-3 filer class is omitted, that the only live donor source remains `donativo_donor`, and that the refusal remains applicability-grade until each existing temporal, source/casilla, and export owner closes its route with exact evidence.
