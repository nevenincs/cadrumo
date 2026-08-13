---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:5b15d940be189ecf56fd7fe8b2d9e47ddfd559651accf4ab43ee781bba434891'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-W02-P04-S20]]"
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

# `tui-architecture` audit: `S20 persistence adapter facade review`

## Scope

Independent review of `W02.P04.S20` against the complete live plan, accepted
ADR and research, S18-S20 execution records, S18/S19 implementation and review
evidence, fresh code and vault RAG discovery, exact-symbol source confirmation,
and the current scoped diff. The review covered public export completeness and
minimality, implementation-internal containment, canonical declaration-module
identity, package-relative facade topology, direct tests, and focused static
and behavioral gates. Production code, tests, plan state, and peer-owned work
were not modified.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### S20 persistence adapter facade review | {level} | {summary}

     followed by a paragraph carrying the detail. S20 persistence adapter facade review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### exact-public-surface | low | The facade exports exactly the two concrete persistence adapters

`cadrumo.adapters.persistence.operations.__all__` is exactly
`OperationJournalRepository` and `OperationLeaseFilesystemRepository`. Both
names are bound to the concrete classes implemented by the S18 journal and S19
lease modules, so the facade neither mirrors nor relocates their declarations.
No third adapter is implemented in the package or required by the binding plan.

### internal-containment | low | Lease storage and private record machinery do not leak through the facade

`OperationLeaseStorage` remains an intra-package implementation seam used by
the journal adapter to share the canonical lock and is absent from the package
namespace and facade `__all__`. The private journal repository, persisted
record models, and replay request model are likewise not imported or exported
by the facade. The public package therefore exposes composition-ready concrete
ports without advertising lock, codec, record, or storage-substrate authority.

### facade-topology | low | Relative imports preserve the canonical declaration modules and package boundary

The package facade imports each concrete adapter directly from its owning
private sibling module using package-relative imports. The direct facade test
imports only through the package root and asserts exact exported identity plus
the absence of `OperationLeaseStorage`. This matches the repository's
relative-self-import rule and the architecture rule that cross-package callers
consume the owning package facade.

### focused-verification | low | S20 behavior and scoped structural gates are green

The S18-S20 adapter/application regression run passed 32 tests. Ruff check and
format check passed for the facade, its direct test, and both implementation
modules. Basedpyright reported zero errors, warnings, or notes, and the
path-scoped relative-import scan passed. The narrowed facade-export,
relative-import, cross-module-resolution, and layout-smoke run passed 97 of 98
checks; its sole failure names unrelated live peer facades in filing, profile
custody, prorrata, corpus manifest, bienes de inversion, notifications, and CLI,
not this package. The broader import-hygiene run similarly failed only on
unrelated notification, custody, annual-order, and legacy-TUI census changes.
Those current-tree failures are not evidence against S20 and were preserved.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

- Keep the two-name package facade as the sole cross-package construction
  surface for the journal and lease adapters.
- Keep `OperationLeaseStorage` and all typed persisted-record machinery below
  the facade; future composition must not deep-import them.
- Track the unrelated current-tree import-hygiene failures with their owning
  campaigns; they require no S20 change.

Final verdict: PASS. No CRITICAL, HIGH, MEDIUM, or LOW defect remains open in
the authorized S20 review scope.

