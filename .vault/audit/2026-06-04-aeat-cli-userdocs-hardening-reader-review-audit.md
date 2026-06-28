---
tags:
  - '#audit'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
---


# `aeat-cli-userdocs-hardening` Reader Review Evidence

## WIREFRAME-001 | STRUCTURE | Handbook corpus, not a mega-document

The zero-context wireframe reviewer found the intended quick-reference handbook understandable only if the corpus is treated as linked task pages rather than one mixed document. The mitigation pathway therefore keeps Diataxis boundaries explicit: landing route, focused how-to pages, generated reference links, explanation pages, and symptom-first troubleshooting.

## WIREFRAME-002 | STRUCTURE | Support route is required

The wireframe review found that new readers need a clear support path before they can safely use a complex filing tool. The plan therefore includes a privacy-safe support checklist and a "where to ask for help" route.

## READER-001 | HIGH | First-time path skips ledger readiness

The non-technical reader review found that the current documentation does not clearly explain the full loop required to make ledger data tax-ready: import, inspect, classify, allocate, attach evidence, correct rows, preflight, and only then calculate. The plan therefore adds ledger operation, evidence, correction, and mixed-use allocation pages.

## READER-002 | HIGH | Profile, censo, and Modelo 036 concepts are not plain enough

The reader review found that users are asked to handle profile fields, censo state, and enrolment changes without enough plain-language explanation. The plan therefore separates profile setup, censo comparison/application, and Modelo 036 lifecycle documentation.

## READER-003 | HIGH | Manual casilla and binding values need their own operational surface

The reader review found that users cannot reasonably infer how to supply manual values from raw `--casilla` and `--binding` snippets. The plan therefore requires focused manual-value guides and a backlog item for a guided product surface if the CLI still exposes raw ids without a natural explanation.

## READER-004 | MEDIUM | Filing handoff language is confusing

The reader review found that "file", "export", "fichero", and portal upload language can read as remote filing when the CLI only prepares or records filing state. The plan therefore requires a verify-export-file-manually checklist and a rewrite of `work file` language as internal state only.

## TECH-001 | HIGH | Generated CLI reference drifted from live help

The technical CLI review found 193 live leaf commands while the previously observed generated index listed 188 and omitted `ledger.doclink`, `ledger.providers`, and the three `modelo m036` lifecycle commands. The local generated reference can be refreshed to 193 leaves, but `docs/cli/` is ignored, so the plan records a durable mitigation decision point instead of pretending the local generated output is a tracked corpus change.

## TECH-002 | MEDIUM | Help-language behavior can undermine examples

The technical CLI review found that `--language en` did not consistently render English help in this environment, while setting `AEAT_OUTPUT_LANGUAGE=en` before import affected some surfaces. The plan therefore separates runtime flag behavior from import-time locale pinning and records this as a documentation trust issue.

## TECH-003 | MEDIUM | Verification-report next action may point at an invalid command path

The technical CLI review found a likely invalid next-action path for verification reports. The plan records a backlog step to confirm and fix or document the live command surface: `aeat app modelo verification-report list/view`.
