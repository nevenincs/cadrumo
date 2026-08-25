---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:769fba49ddb208afda27529e6854892ecc299bd7976ec5c6922deaedb8233afc'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `s172 workspace producers review`

## Scope

Independent review of `W03.P20.S172` against the accepted Workspace producer-contract boundary. Reviewed the public defining module, epoch-v2 comparison semantics, direct consumer migration, API stub migration, inert namespace, digest reproduction, and exact-remnant tests in the shared tree.

## Findings

No findings. The current-only v2 epoch requires an opaque comparison domain and refuses domain mismatches before generation comparison. The public module is the sole producer-contract authority; live consumers import it directly and the package namespace remains inert.

### s172-workspace-producers-review | low | none: no S172 implementation defect confirmed

RAG discovery followed by whole-file and exact-symbol confirmation found one public defining module containing the complete S126 producer-contract, stamp, epoch, structural port, and inventory families. The retired private source and private API stub are absent; exact production and focused-test consumers import the public module directly; and `application.modelo` remains inert with an empty `__all__`. The epoch requires a `ContentDigest` `comparison_domain` and `Literal[2]` schema version. Its shared comparison guard runs before both successor and currentness integer comparisons, while the focused tests cover current, old, future, and missing-domain schema refusal plus same-domain success and cross-domain equal/lower/higher-looking coordinates. Contract and inventory digest inputs carry the v2 declaration. The module contains only the structural protocol, with no S167 port realization or registration, no S173 domain derivation, no S166 manifest move, and no S128 assembly.

### s172-workspace-producers-review | low | EXTERNAL: persisted-format gate has an unrelated unbound secure replay proof constant

The full persisted-format control reports `SECURE_REPLAY_PROOF_SCHEMA_VERSION (cadrumo.application.filing._export_proof)` as unbound in `test_every_version_constant_is_bound_or_deliberately_excluded`. The constant is declared in `src/cadrumo/application/filing/_export_proof.py` and is outside the S172 producer-contract move and epoch-v2 classification. This review neither fixes nor assigns a persisted-format classification to that external filing concern.

## Recommendations

No remediation is required. Preserve the separation of concerns: native domain derivation remains with the native-owner steps, while concrete port registrations and field-manifest relocation remain with S167.
