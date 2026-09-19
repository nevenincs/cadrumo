---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:060f084675219882c4f005f7f9c0c53a7dc61abb91e52b220c7a375a26724191'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S55 DP30301 scalar authority closure review`

## Scope

Independent formal review of `W04.P07.S55` at immutable candidate `e7cb1c55c6739d4a21e0dffe670f5fe7d750e8ab`, directly parented by `7e8f59f032a91f91fb069c0a451a5775f9f80c93`, with tree `285226e9e27d38c3f9ecd344520e7fdf3b0d233a`. The review covered all 304 changed paths, the DP30301 A16-A30 producer authorities, encrypted profile and register cutovers, calculation and export consumers, bucket identity, source-mesh bindings, and removal of implicit/default/legacy authority.

The final reviewer verdict was `APPROVE` with zero unresolved critical, high, or medium findings. Immutable evidence included 126 scalar and authority tests, 150 secure-storage, prorrata, Renta, and repository tests, 159 profile and readiness tests, targeted A21 and settlement tests, changed-file Ruff and formatter checks, compileability, clean diff and scope censuses, exact CLI help, and registry verification for 73 modelos and 94 revisions.

## Findings

### received-invoice-deduction-authority | high | Partial reverse-charge observations bypassed the exact ledger authority contract

The first reviewed candidate attempted to build received domestic reverse-charge observations without the required deduction family and immutable provenance. The final candidate withholds every received invoice from IVA observation projection until a classified ledger transaction supplies both authorities and emits the actionable `missing_deduction_authority` diagnostic. Rated and unrated reverse-charge cases, diagnostic content, constructor refusal, and the 17-call AST census all pass.

### simplified-scope-profile-bypass | high | Operator evidence could select a calculation branch that contradicted the secure profile

Calculation ingress initially trusted the evidence payload's simplified-regime scope and did not compare it with the canonical profile mapper until export. The final candidate calls `m303_regimen_simplificado_scope_for_profile` in the filing-evidence validator before calculation persistence and refuses GENERAL-versus-SIMPLIFIED/MIXED mismatches. The legacy static gate was corrected to prohibit only retired override surfaces while positively proving that calculation and export share the canonical mapper.

### bienes-register-result-underdeclaration | medium | A supplied regularisation result could omit canonical register rows

The initial snapshot checked the regularisation year but allowed empty, foreign, or omitted rows relative to the supplied Bienes register. The final candidate replays the existing canonical `compute_registro_regularizacion` function from row-carried definitive-prorrata values and requires full immutable result equality at both snapshot and export applicability boundaries. Canonical positive and empty, foreign, and omitted-row refusal tests pass.

### strict-cutover-test-drift | medium | Stale tests obscured mandatory profile, revision, and explicit-repository behavior

Several tests retained omitted M303 composition, a retired `2023-y-siguientes` revision token, missing mandatory filing evidence, or AST visitors unable to see intentional refusal calls wrapped in `cast`. The final candidate migrates them to explicit real profile/evidence facts and exact year-bound revisions. AST gates unwrap direct and typed-cast callees while retaining the exact omission tuples and runtime `TypeError` assertions; no exclusion or empty expectation was introduced.

## Recommendations

- Preserve the canonical profile mapper as the only authority for M303 simplified-regime calculation and export scope.
- Keep received invoice projection fail-closed until the classified transaction ledger supplies exact deduction authority and provenance.
- Retain full Bienes regularisation result equality; do not weaken it to row-subset or count checks.
- Keep the positive owner and AST censuses paired with direct runtime refusal tests so removed defaults, aliases, and implicit repositories cannot return silently.
