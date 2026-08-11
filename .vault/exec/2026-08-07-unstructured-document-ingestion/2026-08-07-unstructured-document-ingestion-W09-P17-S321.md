---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:40070c05f0c3c934bd3f76f5094e205997d8707c636a6f9abc442af9fbd1ef15'
step_id: 'S321'
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
     The S321 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The Restore the missing-required-field refusal that left the CLI layer when the confirm suite switched to a structured document, as an application-layer case over a constructed draft needing neither a model nor a document. The property is that a required field with no extraction heuristic and no operator override refuses rather than being fabricated, and it is currently proven nowhere: the CLI case that carried it could only construct the state from a text PDF, whose reading lane needs a live model, and a structured document names its parties so the state is unreachable from the bundled corpus. Do NOT rebuild it around a document - the point is the confirm service's own behaviour when the draft it is handed lacks the field, which a constructed draft states directly and ## Scope

- `src/cadrumo/application/ledger/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Restore the missing-required-field refusal that left the CLI layer when the confirm suite switched to a structured document, as an application-layer case over a constructed draft needing neither a model nor a document. The property is that a required field with no extraction heuristic and no operator override refuses rather than being fabricated, and it is currently proven nowhere: the CLI case that carried it could only construct the state from a text PDF, whose reading lane needs a live model, and a structured document names its parties so the state is unreachable from the bundled corpus. Do NOT rebuild it around a document - the point is the confirm service's own behaviour when the draft it is handed lacks the field, which a constructed draft states directly

## Scope

- `src/cadrumo/application/ledger/tests`

## Description

- Locate the guard and confirm it had no coverage at all.
- Land nine cases over constructed arguments, needing neither model nor
  document, with the typed verdict asserted beside the message.
- Mutation-prove the refusals from outside the checkout.

## Outcome

Delivered. The coverage the confirm-CLI refit displaced now exists where it
belonged all along, and it covers more than the case that was lost.

The guard had NO coverage before this: neither the function nor its
precondition condition appeared in any test in either package. So the property
was gated only through a CLI case built on a text PDF, and when that suite
moved to a structured document to become runnable, the property went with it.

Nine cases. The shape worth recording is the pairing rather than the count:

The typed precondition verdict is asserted BESIDE the message, on the failed
condition id and the recorded fact, because those two degrade in opposite
directions. A refusal that keeps its wording while losing its verdict still
reads correctly to a human and cannot be projected by any surface -- silent,
and exactly the shape a message-only assertion would miss.

Blank is parametrised over BOTH sides. A guard that stripped the operator's
value and trusted the reader's would mint a record whose party is a tab
character, and the reader is the side more likely to produce one, since a stray
cell in a structured document arrives as whitespace rather than as None.

Three positive controls, without which the module is satisfiable by a function
that refuses always -- the failure mode a refusal test cannot detect about
itself.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Mutation-proven by replacing the guard with an unguarded version at runtime,
from outside the checkout so nothing under source changed: all three refusal
cases red, all three positive controls stay green, and the restored tree is
green again. The controls staying green under the mutation is the half that
makes the proof mean something -- a mutation that reddened everything would
only show the module runs.

One probe defect found and fixed rather than worked around: the first harness
caught ``Exception`` and pytest's own failure outcome derives from
``BaseException``, so the mutation's first run reported an unhandled traceback
instead of a verdict. The mutation was biting correctly the whole time; the
instrument was not reading it.

Why the counterparty name and not another field: it is the one with no
fallback. The tax id has a checksum and a role resolver, the currency has a
documented default. An invoice reaches Modelo 347 per counterparty, so an empty
party name is a filing-grade gap rather than a cosmetic one.
