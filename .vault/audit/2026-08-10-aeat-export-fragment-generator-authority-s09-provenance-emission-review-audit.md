---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ed904ace524d63d98ef85587475c6ac6f3a75e6380c5cb8add8e2024f643027d'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `s09 provenance emission review`

## Scope

Audit W02.P03.S09's manifest emission and verification boundary: current-authority rebinding, canonical sibling output, complete TOML/file coverage, per-field normalization evidence, direct real-loader verification, and no-legacy refusal behavior.

## Findings

### authority-rebinding | high | Verification initially trusted persisted identity fields

The first review found that verification recomputed files, loader semantics, and derivations without proving that the manifest still matched the current joined design, reviewed semantic map, and generation target. The corrected verifier now requires those current authorities and rejects source, schema, map-digest, modelo, revision, or epoch drift before accepting the materialized layout.

### direct-emission-proof | high | Initial tests did not directly exercise the public emitter

The first review found that render-path coverage alone did not prove the public emission and verification functions. The corrected real filesystem proof removes the rendered sibling, invokes the emitter directly, loads the generated revision through the production directory loader, and verifies the reconstructed manifest against that materialized layout.

### materialized-layout-proof | medium | Initial unit coverage used a constructed layout

The corrected coverage passes the actual `load_modelo_directory` result to direct verification. It also proves refusal for TOML-byte tampering, canonical authority tampering, derivation-code drift, omitted field evidence, non-TOML output, timestamps, generic defaults, old builder inputs, and semantic-map mismatch without a sibling manifest.

### final-rereview | pass | No unresolved critical, high, or medium finding

The independent re-review accepted the repaired current-authority binding, direct emission path, real loader roundtrip, and fail-closed guards.

## Recommendations

- Keep `verify_export_fragment_provenance_manifest` supplied with freshly reconstructed authorities; a future check-mode step must not replace them with persisted manifest values.
- Preserve the closed normalization-code axis and exact field-to-layout coverage when a reviewed normalization form is added.
