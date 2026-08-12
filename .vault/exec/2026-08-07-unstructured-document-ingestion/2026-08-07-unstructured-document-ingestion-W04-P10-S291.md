---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d47a93f3d86eb4d79871624ffff6ef87e36f139d5cfa3ebf4a259e67012b9317'
step_id: 'S291'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S291 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The RULED AND BUILT. The ADR's ninth amendment refuses the repeating form and adopts a third shape. The repeating group would have required the anchor mirror to become repeating alongside the values, changing the anti-fabrication guarantee at its root, plus a large context addition on a lowest-bound vision target. Neither is needed: the collapse is detectable from three figures the draft ALREADY carries. Measured 2026-08-12 - a 1000-at-21%-plus-1000-at-10% invoice read as the flat triple (base 2000.00, rate 21, cuota 310.00, total 2310.00) raised ZERO findings, because the total identity holds and the per-tier check iterates an iva_breakdown only the structured reader populates. The flat triple was never checked against itself on any lane, and flat iva_rate is set ONLY by the model-read lane, so the unchecked representation was exactly the model-read one. Landed as _flat_rate_consistency_finding in the canonical closure home, enrolled in closure_findings so it reaches every reader, and skipped when the breakdown carries more than one tier, which is where the breakdown is the authority. DETECTION ONLY - recovering the lost tier from a text or vision read stays open and undecided and ## Scope

- `src/cadrumo/application/ledger` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# RULED AND BUILT. The ADR's ninth amendment refuses the repeating form and adopts a third shape. The repeating group would have required the anchor mirror to become repeating alongside the values, changing the anti-fabrication guarantee at its root, plus a large context addition on a lowest-bound vision target. Neither is needed: the collapse is detectable from three figures the draft ALREADY carries. Measured 2026-08-12 - a 1000-at-21%-plus-1000-at-10% invoice read as the flat triple (base 2000.00, rate 21, cuota 310.00, total 2310.00) raised ZERO findings, because the total identity holds and the per-tier check iterates an iva_breakdown only the structured reader populates. The flat triple was never checked against itself on any lane, and flat iva_rate is set ONLY by the model-read lane, so the unchecked representation was exactly the model-read one. Landed as _flat_rate_consistency_finding in the canonical closure home, enrolled in closure_findings so it reaches every reader, and skipped when the breakdown carries more than one tier, which is where the breakdown is the authority. DETECTION ONLY - recovering the lost tier from a text or vision read stays open and undecided

## Scope

- `src/cadrumo/application/ledger`

## Description

- Measure what the flat triple is actually checked against, before designing
  either proposed route.
- Rule the fork in the ADR as its ninth amendment.
- Land the identity in the canonical closure home and gate it.

## Outcome

Delivered, and NOT as the row asked. The amendment refuses the repeating form
and adopts a third shape neither proposal considered.

THE MEASUREMENT IS THE RULING. A draft carrying base 2000.00, rate 21, cuota
310.00 and total 2310.00 -- a 1000-at-21% plus 1000-at-10% invoice exactly as
the text or vision lane reads it -- returned ZERO deterministic findings. The
total identity holds perfectly, 2000 plus 310 is 2310, so the one check that
ran confirmed it clean while the draft carried a single rate that is wrong
about half its own base, and that rate decides which Modelo 303 tier the base
lands in.

The cause is a hole with a precise shape. The per-tier check applies
`base * rate == cuota` only to `iva_breakdown` ENTRIES, and the breakdown-sum
check returns early on an empty breakdown. Only the STRUCTURED reader populates
that breakdown; only the model-read lane populates a flat `iva_rate`. The two
representations are disjoint, so the representation nothing checked was exactly
the one a model produced.

BOTH PROPOSALS MIS-LOCATED THIS AS A MISSING DERIVATION. Neither needs to find
the second rate. Three figures the draft already carries are mutually
inconsistent, and saying so is the whole detection.

So the repeating form is refused. It would have made the anchor mirror repeat
alongside the values -- the mirror is a per-field exact parity and an array of
per-rate rows cannot carry one anchor string -- which changes the
anti-fabrication guarantee at its root. It would also have added a repeating
group to a prompt whose design target is a lowest-bound vision model, a far
larger ask than the two role-evidence keys a shipped gate already refuses on
those grounds. A guarantee change and a context cost, to buy a detection the
arithmetic gives away.

The identity landed in the canonical closure home and enrolled in the shared
check list, so it reaches every reader rather than the lane it was written for.
It is skipped when the breakdown carries more than one tier: there the flat
rate is legitimately not a single rate and the existing checks cover the
figures. No producer populates both today, so that guard is not load-bearing --
it states which representation wins before one can violate it.

DETECTION, NOT RECOVERY, and the amendment says so out loud. The lost tier is
not recovered from a text or vision read. The operator holding the document
supplies the split, which is the division of labour the ambiguity candidates
already use, and recovering a breakdown from those lanes stays open and
undecided.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The asymmetry that makes this a defect rather than a gap was already sitting in
the tree, and finding it is what settled the ruling's confidence: the identical
identity is a HARD refusal on manually entered asset and inventory invoices --
"iva_amount must equal taxable_base * iva_rate". The figure a human types is
refused when it does not close. The figure a model reads was not checked at all.

The fork itself is the lesson. Both rows were written from an accurate
measurement and both proposed a remedy at the wrong layer, because both asked
"how do we obtain the missing rate" rather than "what do the figures we have
already say". One was expensive and changed a guarantee, the other was cheap
and imprecise, and the argument between them ran for two sessions without
either side checking whether the existing figures were self-consistent. THE
CHEAPEST CHECK IS THE ONE OVER DATA YOU ALREADY HAVE, and it is worth asking
for before pricing either acquisition.

Seven ledger-suite failures were present alongside this work and are NOT this
surface: every one is an error-message rendering failure -- an empty rendered
message, and a `KeyError: 'actionability'` -- against the error-code rehoming
that was already modified in the working tree when this session opened.
`errors.storage.runtime.not_ready` resolves to no catalogue entry. Left with
its owner rather than patched.
