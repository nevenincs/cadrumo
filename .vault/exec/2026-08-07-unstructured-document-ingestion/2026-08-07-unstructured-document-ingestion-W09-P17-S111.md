---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:3808678896a7688222cf3d032812daa7c0168e94e7d626520b224c037ef32d3f'
step_id: 'S111'
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
     The S111 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Offer a model pre-suggestion for supply nature through the existing operator suggest, review and apply channel rather than building a second one, since that loop already exists in the ledger's LLM-assisted classification module and the assembly already names its settler as a printed statutory citation or an explicit operator assertion. Depends on the lazy-demand fix landing first: while the demand is unconditional, wiring the suggestion would fire a prompt on every document and manufacture a decision on the domestic path where the treatment does not depend on it. The suggestion must reach the deterministic classifier only after operator confirmation, entering as an operator-provenance assertion so the classifier's inputs stay facts and never model output. Gated by a test proving an unconfirmed suggestion never reaches the classifier and by a positive control proving a confirmed one does and ## Scope

- `src/cadrumo/application/ledger` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Offer a model pre-suggestion for supply nature through the existing operator suggest, review and apply channel rather than building a second one, since that loop already exists in the ledger's LLM-assisted classification module and the assembly already names its settler as a printed statutory citation or an explicit operator assertion. Depends on the lazy-demand fix landing first: while the demand is unconditional, wiring the suggestion would fire a prompt on every document and manufacture a decision on the domestic path where the treatment does not depend on it. The suggestion must reach the deterministic classifier only after operator confirmation, entering as an operator-provenance assertion so the classifier's inputs stay facts and never model output. Gated by a test proving an unconfirmed suggestion never reaches the classifier and by a positive control proving a confirmed one does

## Scope

- `src/cadrumo/application/ledger`

## Description

- Check the governing ADR for a ruling on the pre-suggestion before designing
  one, and find it SANCTIONED.
- Check the channel the row says to reuse, and find it is about a different
  subject.
- Check the precondition the suggestion sits on, and find it absent.

## Outcome

BLOCKED ON A MISSING PRECONDITION that is more important than this row, and
which measuring for this row is what surfaced.

The ADR check came back POSITIVE, which is worth stating because the last two
rows I touched came back negative: the second amendment explicitly permits a
model to pre-suggest supply nature from the line descriptions through the
accepted suggest-review-apply channel, calls it a cheap selection task within
the low-context budget, and requires that the suggestion reach the
deterministic classifier only after operator confirmation. So the row is
sanctioned rather than a widening to argue for.

The channel the row says to reuse is not the right one. The shipped
suggest-review-apply loop is about a TRANSACTION -- its suggestion carries a
business classification and a spending category -- while supply nature is an
input to the INVOICE classification assembly at the confirm boundary. Reusing
it would mean extending it to a second subject or building the second loop the
row forbids, and that is a design decision rather than a wiring task.

THE PRECONDITION IS ABSENT, and this is the finding. ``supply_nature`` appears
nowhere outside the classification assembly: no CLI option, no confirm
parameter, no review-item resolution path. The production caller constructs
the declared facts from the filer scope, the counterparty scope, the
counterparty identification and the stated category -- never a supply nature.

So on a cross-border or reverse-charge branch, where the law forks on it and
the lazy demand correctly fires, the category is absent and THE OPERATOR HAS NO
WAY TO ANSWER. The ADR states the intended behaviour plainly -- the review gate
surfaces one resolvable item, the operator states goods or services, and the
classifier consumes it as an operator-provenance assertion -- so this is an
unbuilt half of an accepted decision rather than an omission nobody decided.

Rowed as its own step. This row stays open behind it, because the pre-suggestion
is the optional convenience layered on the deterministic channel and must not be
built before the path it feeds.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The row's own stated dependency was satisfied and its real one was not. It
waits on the lazy-demand fix, correctly, because wiring a suggestion under an
unconditional demand would fire a prompt on every document and manufacture a
decision on the domestic path where the treatment does not depend on it. That
fix has landed and is separately gated. What the row did not know is that the
answer channel the suggestion feeds was never built, so satisfying the stated
dependency does not unblock it.

The ordering discipline this leaves behind: do not build the model convenience
before the deterministic channel it feeds. A pre-suggestion wired to nothing
would present an operator with an answer they cannot accept.
