---
tags:
  - "#adr"
  - "#quality-gate-zero-closure"
date: '2026-09-08'
related:
  - '[[2026-09-07-quality-gate-zero-closure-blind-green-measurement-research]]'
  - '[[2026-09-08-quality-gate-zero-closure-dev-tooling-product-boundary-audit]]'
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-09-11-import-centralization-import-authority-drift-audit]]'
supersedes:
  - '2026-09-07-quality-gate-zero-closure-blind-green-gates-adr'
  - '2026-09-02-object-name-declustering-adr'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:8b50251f1684c0261d107cc2656a2611f4af66744c47e44f70ac340df6fe05da'
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

## 2026-09-11 amendment: import tooling serves one product-source verdict

The product/tooling boundary permits one narrow subordinate import analyzer because its subject is the shipped source boundary and its output is owned by the authoritative product import command. This is not a restoration of the superseded meta-detector stack.

`just check-imports` is the sole contributor-facing import-quality verdict. Import Linter owns the dependency graph, source-root classification, and lane directions. A subordinate parser may enforce only properties the graph cannot express: relative intra-`cadrumo` spelling, canonical defining-module imports, private ownership, inert initializers, forwarding and re-export shapes, and supported dynamic targets. It runs only behind `just check-imports`, imports or derives the graph classification rather than restating it, and has no separate live-tree verdict.

The command fails closed when any component reports a violation, cannot parse or read governed source, cannot classify a first-party package, cannot resolve a supported first-party dynamic target, or is unavailable. Architectural warnings are errors. The development health report may invoke or consume the command's exit status and bounded native diagnostics, but it does not parse Import Linter's contract grammar, count declarations, or turn unavailable execution into an alternate advisory import result.

Representative planted defects are acceptance evidence for the command and each contract family. Existing pytest gates and scanners are removed only when their exact import predicate is proven by that driver; distinct product behavior and packaging tests remain.
