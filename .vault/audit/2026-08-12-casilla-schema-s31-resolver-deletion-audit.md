---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:c33549669d85ed00987b3a37e4f274203ec62fb6b0254e436f8ee6ce6dbd322b'
related:
  - "[[2026-08-10-casilla-schema-dead-surface-adr]]"
---
# `casilla-schema` audit: `S31 strict bound-input resolver deletion`

## Scope

Reviewed the accepted dead-surface decision, the full uncommitted S31 delta, all fifty-nine migrated test/support files and seventy-four migrated calls, the structural regression, and the repaired execution record. Unrelated preflight and entrypoint peer work was excluded.

## Findings

### structural-regression-boundary | medium | Resolved

The repaired test imports only public registry and application facades. Its filesystem AST scan proves the application projector is the sole matching production resolver definition, the retired symbol has no production import or registry facade exposure, and the exact retired identifier is carried honestly in the test. The private-module reach and obscured census are gone.

### focused-ruff-gate | medium | Resolved

The repaired import block is sorted. Focused Ruff, BasedPyright, and structural pytest are reported green; bounded reinspection found no remaining owned lint or typing defect.

### stale-test-prose | low | Resolved

Exact search across the three previously identified Modelo 200 and Modelo 303 scenarios finds neither the stale strict-resolver wording nor the deleted missing-binding-fact narrative. No strict semantics were restored.

### exec-scaffold-hygiene | low | Resolved

The execution record now contains only final scope, description, outcome, and notes. Template annotations, malformed guidance, and blank residue are gone, and the body is re-attested.

## Recommendations

No follow-up change is required for S31. Preserve the public-facade filesystem-AST regression and keep missing or unrouted input enforcement in the existing CLI, engine, advisory, and verification owners.

## Final Verdict

PASS. The strict resolver and exactly its two facade entries are deleted; no alias or compatibility shim remains; and the permissive application projector is the sole living production owner. All fifty-nine migrations are valid complete-map calculation scenario setup, with no erased missing or unknown behavior expectation, forbidden test double, tautological calculation oracle, or invalid production dependency.
