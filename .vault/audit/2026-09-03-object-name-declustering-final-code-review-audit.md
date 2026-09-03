---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:9b8ffd96d9315e52a881f5d71d04c1bdd50ebbdf22aa8911130efa9642c1ef93'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---
# `object-name-declustering` audit: `final code review`

## Scope

Reviewed the complete W01-W03 implementation and focused tests against the accepted ADR, research, reference, implementation plan, and Step Records. The review covered inventory identity, reviewed-manifest validation, hard-edge component construction, controlled LibCST transformations, disposable rehearsal, receipt integrity, live replay and rollback, concurrency behavior, CLI defaults, Justfile forwarding, the reviewed pilot manifest, and the pilot rehearsal evidence. The live tree was not mutated by an apply operation during review.

## Findings

### rollback-evidence | high | stage cleanup failure can be hidden while transaction evidence is deleted

After `_restore` succeeds, `replay_object_name_component` marks the transaction removable before cleaning same-directory stage files. If `_cleanup` then raises while the primary replay failure is active, that cleanup error is suppressed, but the transaction directory is still removed. A stage artifact can therefore remain in the live repository while the caller receives only the earlier rolled-back error and the durable transaction evidence disappears. The existing cleanup-failure test accepts the primary exception without proving stage absence or marker retention.

### generator-authority | high | live generated artifacts bypass their owning generator

Replay classifies generated paths but writes their rehearsed bytes directly into the live tree, then reuses the rehearsal's recorded generator outcomes without executing the owner during live replay. This contradicts the accepted decision that generated outputs change only through their owning generators and that apply replays the identical operation sequence. The current test proves byte transplantation and outcome reuse, thereby encoding the bypass rather than the decided authority boundary.

### mandatory-gates | high | architecture, semantic-overlap, and clone checks are optional and absent from the pilot

The accepted design requires applicable parsing/import, architecture, semantic-duplication, and clone non-regression evidence. Production orchestration wires import-edge discovery and object-name finding deltas, but `semantic_advisory` and `clone_advisory` have no production caller, and the manifest schema requires only an arbitrary non-empty `focused_gates` list without enforcing gate classes. The pilot manifest runs the renamed generator in read-only mode and Ruff only. A receipt can therefore be successful without the architecture, semantic-overlap, clone, or broader import-hygiene gates required by the ADR and plan.

### focused-suite | medium | the current complete focused suite has two failing replay tests

The combined object-name implementation suite completed with 252 passing tests and two failures. Both `test_component_structural_forgery_reaches_canonical_preflight_and_refuses` variants still expect the earlier supplied-component diagnostic, while current copied-tree reconstruction refuses with `copied repository graph differs from the reviewed component`. The behavior remains fail-closed, but the required focused gate is red and the Step evidence does not describe the current integrated result.

## Recommendations

- For `rollback-evidence`, treat stage cleanup as part of transaction completion. Aggregate cleanup failure without masking the primary error, retain the transaction marker whenever any stage cannot be removed, and add a test proving both artifact and marker behavior.
- For `generator-authority`, execute the declared owning generator during bounded live replay with transactional capture and exact output verification, or obtain an explicit superseding ADR before adopting verified-byte transplantation.
- For `mandatory-gates`, make required gate families typed and non-omissible in production orchestration, wire semantic and clone evidence into planning/rehearsal, and ensure the pilot receipt records every applicable required gate.
- For `focused-suite`, update the structural-forgery assertions to the current fail-closed boundary and rerun the complete focused suite before declaring the feature complete.
