---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ff0cdd6efcfed9b5bac80bb92b6c570104023ee468e342ebbf56010a2ad846b6'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-25-tui-architecture-s170-selector-convergence-audit]]"
  - "[[2026-08-11-tui-architecture-W03-P20-S170]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `S170 selector convergence remediation review`

## Scope

Corrective record for the final integrated review of `W03.P20.S170`, after the
coordinating review reopened the Step in `114d8ed2de`. The review re-examined
the live shared-tree fixed-point proof, its import boundary, semantic scanner,
resident-service discovery gate, documentation surface, deletion inventory,
and execution provenance.

This audit supersedes the false PASS recorded by review commit `4b802cc588` at
frozen source `a3dbaeee421`. That review assessed an explicit consumer census
and an incomplete fixed-point test rather than a reusable complete live-tree
authority scanner. Its PASS must not be used as completion evidence. This
record documents the final-review findings and their remediation, but does not
perform the required independent clean-HEAD re-review and does not authorize
closing the plan row.

## Findings

### false-pass-provenance | high | The prior review and execution record overstated fixed-point completion

The PASS at `4b802cc588` did not prove complete tracked-live discovery, reusable
import and dataflow resolution, dynamic re-export detection, or exclusive RAG
ownership. The S170 execution record repeated that PASS and said the Step was
eligible for lifecycle transition. The plan was subsequently closed on false
provenance and had to be reopened. The execution record is corrected in the
same atomic remediation to retract those claims and name this audit as the
superseding disposition.

### shipped-test-dev-import | high | A shipped core test imported unshipped development tooling

The cutover gate lived under `src/cadrumo/core/tests` while importing
`dev.quality.import_hygiene_scan`. The gate now lives under `dev/tests`, imports
the development scanner relatively, and the shipped test path is deleted with
no bridge or runtime scanner promotion.

### incomplete-live-corpus | high | The S170 census omitted tracked development tooling and embedded its own retired literals

The feature gate previously selected only `src`, `docs`, and `packaging`, so a
retired import or dynamic access under `dev` could survive. It now scans the
canonical `tracked_live_files()` inventory without path exclusions. Retired
module spellings are assembled from semantic components in the test fixture,
so the live census includes the gate itself without self-exemption; synthetic
mutants are scanned separately with exact violation-kind assertions and text
fallback disabled.

### wrapper-dataflow-gap | high | Repository-owning wrappers escaped when the repository type was not named

The original wrapper rule recognized a concrete repository constructor or an
exact receiver name, but not a protocol or untyped `repo.load()` whose result
fed the canonical selector. `DelegatingWrapperRule` now declares keyword-source
method dataflow. The scanner follows `load()` and `load_revisioned()` into the
selector's `catalogue=` argument inside nested definitions, with an exact
realistic mutant proving the finding bites.

### dynamic-export-gap | high | Dynamic re-exports through setattr and globals assignment were invisible

The reusable scanner now rejects target-symbol writes through
`setattr(module, name, value)` and `globals()[name] = value`. Exact mutants prove
both shapes report `dynamic authority export`; ordinary subscript value writes
remain non-alias consumption.

### weak-rag-ownership | medium | The discovery gate passed when any canonical hit coexisted with a parallel owner

The resident-service gate now classifies every returned production declaration
as canonical, parallel, or supporting evidence. It requires exactly the public
`work_addressing.py` owner and no parallel owner. A pure mixed-response mutant
proves canonical-plus-parallel results fail, while tests and ordinary consumers
do not become false owners. The live query is enrolled in the canonical
resident-service lane at explicit port `8766` with the installed `0.4.2` client
and an explicit managed-session status directory.

### retired-documentation-and-compatibility | medium | Retired names survived in documentation and scanner compatibility surface

The obsolete `_work_addressing` API stub is deleted and the Modelo API index
points to the public `work_addressing` document. The unused
`AddressingBoundaryViolation` alias and `find_addressing_boundary_violations`
wrapper are deleted; both feature gates consume the canonical scanner API
directly. The obsolete fixed-point test deletion is included in the same
atomic remediation path set.

## Recommendations

Keep `W03.P20.S170` unchecked. Commit the scanner, both declarative gates,
retired test and documentation deletions, resident-service classification gate,
this audit, and the corrected execution record atomically. Then run an
independent clean-HEAD review that treats this audit as the finding inventory,
re-runs both fixed-point gates, focused import hygiene, Ruff, and the canonical
resident-service lane, and verifies no relevant RAG result is a parallel owner.
Only that later review may recommend closing S170.

