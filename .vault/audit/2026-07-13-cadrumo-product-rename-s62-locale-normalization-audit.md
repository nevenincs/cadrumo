---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s62-locale-normalization'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:1730292e5bbd6d6799f21640041571b7d9b5eb062041ad2a0927151a9a4c3c92'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-12-cadrumo-cli-executable-adr]]"
---

# `cadrumo-product-rename-s62-locale-normalization` audit: `S62 locale normalization review`

## Scope

Commit `5730933328` was reviewed independently against the binding executable
ADR and its ratified Status Note, the active rename plan, the appended S62
execution record, both production normalization boundaries, the locale
maintenance command, focused renderer and parity tests, and all four committed
catalogues. The review checked sentence prose, identity contexts, human-command
conversion, test and record honesty, and commit isolation without changing
implementation.

## Findings

### live-catalogue-casing | high | Removing the render rewrite exposes all-caps sentence prose from checked catalogues

The production changes correctly stop rewriting `Cadrumo` to `CADRUMO`, but
the reviewed commit's four catalogues contain zero exact `Cadrumo` occurrences
and 36 standalone `CADRUMO` occurrences. Many are sentence prose rather than
identity headings, including phrases equivalent to `this CADRUMO profile`,
`No active CADRUMO profile`, and `the CADRUMO vault`. Because the renderer now
preserves catalogue casing, these values reach users unchanged and violate the
ratified `Cadrumo` sentence-prose rule. Intentional headings such as
`CADRUMO, ...` remain valid identity contexts; the defect is the unclassified
sentence copy left beside them.

### descendant-plan-honesty | high | S62 claims catalogue ownership remains downstream while S63 through S67 stay checked

The appended S62 record explicitly says S63 through S66 retain ownership of
catalogue corrections and S67 retains generated parity, but the active plan
marks S63 through S67 complete. The S62 row itself also still says product copy
must become `CADRUMO`, contradicting the Status Note that this commit follows.
No plan path was changed in the commit. The operator-facing plan therefore
reports the affected locale phase complete while the record says its corrective
work remains downstream and the committed catalogues prove that work has not
landed under the ratified convention.

### semantic-casing-gate | medium | Passing renderer and parity tests do not exercise real catalogue casing semantics

The focused renderer and parity slice passes, but its casing assertions use
synthetic `Cadrumo` inputs. Catalogue audit and scaffold checks validate keys,
types, and placeholder parity; they do not classify product casing by sentence
versus identity context. Consequently the S62 record's healthy-catalogue
evidence cannot detect the 36 all-caps occurrences above. A real-catalogue
semantic gate is required before the record can use structural health as
evidence of ADR casing compliance.

## Recommendations

Verdict: **FAIL**. The two HIGH findings block S62 and the locale phase from
being treated as complete.

Keep the corrected normalization behavior: command-leading stale `cadrumo`
must become `aeat`, while `Cadrumo`, intentional `CADRUMO` identity headings,
lowercase machine identifiers, `CADRUMO_*`, and authority `AEAT` remain
untouched. Reopen and execute S63 through S67 against the ratified convention,
rewrite the stale S62 plan wording, and add a real-catalogue classification gate
that distinguishes sentence prose from identity contexts before reclosing the
phase.

The implementation slice itself is clean: 37 renderer/parity tests passed;
Ruff lint and format, Ty, and commit-scoped whitespace checks passed; the stale
command scan found zero catalogue matches. The commit modified no catalogue or
foreign path, and all reviewed paths remained byte-identical at re-read HEAD.
