---
tags:
  - "#adr"
  - "#quality-gate-zero-closure"
date: '2026-09-08'
related:
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-measurement-research]]"
  - "[[2026-09-08-quality-gate-zero-closure-dev-tooling-product-boundary-audit]]"
supersedes:
  - '2026-09-07-quality-gate-zero-closure-blind-green-gates-adr'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:cd8f6527b32c8559a892e959b1a3f28aca36d7a9b3c12353e6144713f399d3ba'
---
# `quality-gate-zero-closure` adr: `Development tooling serves product authority and behavior` | (**status:** `accepted`)

## Problem Statement

The standing blind-green decision requires mutation-tested development analyzers whose principal subjects are other development gates. That authority direction is wrong: `src/cadrumo` is the tax-filing product, while `dev` exists only to build and verify it. The measurement and product-boundary review are recorded in `2026-09-07-quality-gate-zero-closure-blind-green-measurement-research` and `2026-09-08-quality-gate-zero-closure-dev-tooling-product-boundary-audit`.

This decision supersedes the standing mutation/meta-detector mandate. Historical measurements and direct product repairs remain evidence, but no longer authorize retaining or recreating their investigative machinery.

## Considerations

- Static decidability is class-specific; source shape does not generally establish product relevance.
- A durable gate must exercise a supported product authority or behavior and fail under a representative product defect.
- A detector proved mainly against fixtures crafted around its own branches forms a closed validation loop.
- Registry diagnostics consume `ValidatedRegistryAuthority`, not an independently parsed registry model.
- Filing and registry handoffs carry greater product risk than auxiliary-analyzer conformance.
- Superseded implementations, tests, fixtures, recipes, configuration, and facades are removed together.

## Considered options

- Restore the mutation-tested detector stack: rejected because it reinstates the closed loop.
- Replace it with another mutation tool or home-grown analyzer family: rejected because changing implementation does not correct authority direction.
- Keep disabled machinery as optional history: rejected because version history already preserves it and dormant code creates maintenance ambiguity.
- Retain only tooling that verifies product authorities and behavior, with mutation permitted only as a bounded product-code diagnostic: accepted.

## Constraints

Permanent gates name a product invariant, invoke its real public or typed boundary, carry a real-tree positive control, and demonstrate a representative failure. Registry checks use the validated authority. Synthetic product-source modules and analyzer-branch fixture corpora are not acceptance evidence. Built-in linters and authoritative external tools own generic language and output contracts.

No standing mutation score, threshold, baseline, mutation lane, meta-gate, or cadence is established. Mutation may be used temporarily against bounded high-risk product code; survivors are individually triaged and the temporary infrastructure is removed when the investigation ends.

This decision creates no allowance, suppression, exclusion, skip, xfail, or unchecked declaration mechanism.

## Implementation

Remove the mutation/meta-detector analyzers, paired tests, fixtures, dependency configuration, recipes, suite registrations, declarations, compatibility surfaces, and prose presenting them as current obligations. Preserve independently valuable product repairs.

Evaluate surviving `dev` mechanisms by their authority path. Keep tools that exercise registry compilation, validated authority loading, revision resolution, filing admission, calculation, secure persistence, or serialization. Narrow or remove tools that duplicate these through raw storage parsing, source inspection, hard-coded inventories, or invented semantic models.

Registry conformance is the priority. Repair real registry/filing failures before adding analysis machinery. The full suite is blocking in its existing scheduled/full lane once green; any smaller per-push set uses the same validated authority and does not create a second model.

## Rationale

Product authority direction is decisive. Development code may exercise product authorities but may not manufacture a parallel subject and present its self-conformance as tax-product evidence. The cited measurement remains useful because it informed direct repairs; the cited audit shows the durable value lies in those repairs and real authority tests, not the scaffolding used to discover them.

## Consequences

The prior mutation/meta-detector mandate must not be recreated. Its machinery remains deleted, while historical research and product repairs remain. Registry conformance and filing-boundary tests take priority. Mutation has no standing repository role. Removing weak gates may reduce check count while increasing assurance; green remains revision-scoped product evidence, never an inference from tooling volume.
