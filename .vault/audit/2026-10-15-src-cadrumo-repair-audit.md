---
tags:
  - '#audit'
  - '#src-cadrumo-repair'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:c42edea58811108f3721e09d96150092c69c4a0d23f220af565938f2e04ba78c'
related:
  - "[[2026-10-14-src-cadrumo-repair-plan]]"
  - "[[2026-07-01-import-centralization-adr]]"
  - "[[2026-08-14-test-harness-sanity-successor-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace src-cadrumo-repair with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `src-cadrumo-repair` audit: `Canonical source and authority repair audit`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Canonical source and authority repair audit | {level} | {summary}

     followed by a paragraph carrying the detail. Canonical source and authority repair audit is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

## Context

## Scope and findings

The operator's October 15 correction governs ownership: the TUI and tax CLI live inside cadrumo; generic runtime authority lives in cadrumo_runtime. Assertion ownership is determined by the behavior under test, not the runtime fixture supplying it. Storage producer provenance is package-owned; packaging inclusion controls belong to tooling. Existing accepted architecture and synchronized always-on rules record this boundary.

The canonical source audit removed the refused-boundary class facade and every direct and dynamic consumer across 135 files, then removed the remaining 29 reported alias imports across 23 files. Consumers bind to cadrumo_client.commands.errors, cadrumo_client.contracts.automation_lifecycle, cadrumo_client.contracts.worker_identity, or the actual local defining module. Private implementation bindings retain the exact canonical objects; none is used as an external compatibility facade. Independent read-only review found no reportable defect. Former public facade attributes are absent, and namespace initializers remain passive.

Python corpus audit controls no longer participate in legal evidence identity. Eight provenance audit cases moved to dev/quality/tests; source and legal enrollment explicitly refuse Python controls, while actual evidence bytes remain authoritative. No legal payload was rewritten. Publication and integrity checks agree on generation 66af11543946175d3d2b85399d6132b5d1f4a0f4a60a0c3d3732db1538d02dba: 58 modelos, 161 revisions and 1502 legal references.

## Verification evidence

The final configured static component scanned all 11321 governed Python files across seven configured roots. REEXPORT_OR_ALIAS, FORWARDING_MODULE, PACKAGE_FACADE and ACTIVE_INITIALIZER each have zero findings; the scan has no fatal or incomplete findings. The overall component exits 1 for 1128 private cross-package blockers and one unresolved dynamic target. Its 9275 spelling advisories are not alias failures. This is a completed category census, not a passing aggregate import gate.

Fresh tax CLI unit scope passed 2805 tests. The recovered unreported source-unit selection passed 739 of 740; its sole stale IVA exclusion failure passed a focused post-fix run. Source IVA naming and payload guards passed 11 tests; no predicate or field bound was relaxed. The guard now names offenders directly. Other final bounded evidence includes 41 corpus controls, 106 ownership/refusal controls, four runtime ownership controls, 72 canonical exception controls, nine command compiler controls, 50 core error tests, seven real-browser direct-entry tests, and three TUI cleanup cases both serially and with xdist8.

The final 15-module alias batch recorded 231 passes and four fence/KDF failures, with 18 deselected tests. One unchanged serial rerun of those exact four failures passed all four. No baseline, regression attribution or resource-causality claim follows from that rerun. Ruff and formatting passed for the canonical source slices; regenerated import-load metadata completed and the final doc-reference gate reports zero dangling targets.

Evidence directory: .logs/test-runs/src-cadrumo-repair. Key records: canonical-import-classifier-final.json, reexport-canonical-owner-manifest.txt, reexport-canonical-owner-focused.log, reexport-failed-node-rerun.log, cli-unit-canonical-baseline.log, authority-publication-final.log, registry-gate-final.log, doc-reference-canonical-final.log and import-load-targets-canonical-final.log.

## Remaining verification

The earlier full source-unit run aborted at 97 percent with an xdist reporter failure caused by an incomplete sys.flags test replacement; the test now restores real flags before reporting and its strict refusal cases pass. Earlier CLI setup failures arose from worker/source interface skew; fresh CLI verification has no such errors. These results are preserved and are not presented as one clean complete suite run.

The broader code aggregate recorded nine failed gates on a concurrently changing tree. Full import-gate authority also detected mismatched source snapshots. Remaining private cross-package and unresolved dynamic-target blockers keep integrated plan step S06 open; canonical reexport step S10 is closed. Other sessions continue to edit and checkpoint this shared tree, so root made no mixed-source Git commit. Current RAM measurements do not establish memory pressure as the cause of earlier slowdowns.
