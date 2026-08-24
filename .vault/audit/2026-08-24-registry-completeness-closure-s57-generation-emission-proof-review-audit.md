---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:02451e28f371a4812535ecfe7f983da1c316fe0b0a073d54236aa01705974426'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - "[[2026-08-24-registry-completeness-closure-adr]]"
  - "[[2026-08-24-registry-completeness-closure-W01-P02-S57]]"
---

# `registry-completeness-closure` audit: `S57 generation and emission proof review`

## Scope

Independent post-implementation review of commit `17f56b69ef3` against
`W01.P02.S57`, the registry authority-flow and quality-gate rules, and the
campaign requirement that filing capability be demonstrated rather than
declared. The review covered the public proof models and port, catalogue lookup,
filing-export closure composition, Modelo 111 refusal regression, API exposure,
and the S57 execution record. Production code was not changed.

## Findings

### passive-proof-catalogue | high | Structurally valid claims can fabricate filing-export closure evidence

`FilingExportProofCatalogue` is a passive tuple of caller-authored models. Its
lookup checks only modelo, revision, and the ordered layout-id tuple. The proof
models constrain hashes to 64 lowercase hexadecimal characters and counters to
positive integers, but no production authority reopens or re-hashes the named
manifest, semantic map, render profile, loader semantic material, generated
fragments, or emitted payload. No authority invokes `export_draft` and checks
the claimed payload length, payload digest, or claimed official offsets.
Consequently, a caller can provide arbitrary all-zero digests, one invented TOML
path, and counters of one; `_filing_export_proof` accepts the catalogue result
and `_proof_evidence` promotes those claims into a satisfied closure limb.

The missing-authority default does fail closed, but catalogue staleness cannot
be detected: the catalogue performs no I/O and cannot raise the errors mapped to
`stale_evidence`. A layout mismatch is collapsed to absence by `proof_for`, so
the catalogue also cannot report that conflict as conflicting evidence. The
Modelo 111 regression exercises only the omitted-authority path and therefore
does not bite if fabricated or stale catalogue evidence is supplied. This
contradicts the S57 outcome statement that proof comes from two independent
authorities and the rule that a gate is unproven until it rejects a broken real
boundary.

## Recommendations

- Enrol `W01.P02.S60` to replace or front the passive catalogue with a live,
  fail-closed authority that resolves canonical sources, re-hashes every claimed
  generation input and output, executes or verifies the production
  `export_draft` result, and checks exact official offsets before returning a
  proof.
- Add fabricated, missing-file, changed-file, changed-payload, wrong-length,
  wrong-offset, and identity-conflict regressions, including a Modelo 111 case
  demonstrating that well-shaped invented proof cannot satisfy closure.
