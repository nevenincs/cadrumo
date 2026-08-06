---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:157b88f1355b5c0611b06f583f23c5f46273063518ad59d26206691daebdbeba'
step_id: 'S24'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S24 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Confirm with the localization cascade owner that the result-summary application row is meant to follow the active output language, the repair is stronger than what it replaced but it crosses another campaign's surface and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_modelo_result_summary_labels.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm with the localization cascade owner that the result-summary application row is meant to follow the active output language, the repair is stronger than what it replaced but it crosses another campaign's surface

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_modelo_result_summary_labels.py`

## Description

- Search the tree for evidence that the confirmation this row requires took place.

## Outcome

**The row is NOT closed, and this record exists to make that visible rather than to close it.**

The row asks for a confirmation from another campaign's owner — that the result-summary
application row is meant to follow the active output language. Its deliverable is therefore an
agreement, not a change, and an agreement leaves no artefact unless someone writes one.

Three commits touch result-summary localization in the relevant window:

    29b8702987  test(modelo): pin the summary label to a requested locale, not the ambient one
                15/6   test_modelo_result_summary_labels.py
    23eb9321ad  test(cli): keep the localized result-summary payload inside the display layer
                194/0  test_result_summary_consumer_boundary.py
    a2b19c6ccc  test(modelo): keep the localized result summary inside its owning layers
                206/0  test_result_summary_consumer_boundary.py

All three are consistent with the confirmation having been given — they pin behaviour that
follows a requested locale and hold the localized payload inside the display layer. **None of
them records the confirmation itself**, and consistency with an agreement is not evidence that
the agreement happened. Three commits that would look identical either way cannot distinguish
"the owner agreed" from "we proceeded on the reading that seemed right".

## Verification

    git log --since="2026-08-05 19:00" --grep="result-summary\|result summary" --format='%h %s'

Three commits returned, listed above, each inspected by `git show <sha> --numstat`. No vault
document, commit message, or code comment in the searched set states the cascade owner's
verdict.

I did not go looking for a conversation to cite. If the confirmation happened only in chat it
is not evidence, and a record asserting it on that basis would be the failure this campaign
spent the day correcting elsewhere.

## Notes

**What would close this row**, so the next reader does not have to re-derive it: a statement
from the cascade owner, recorded anywhere durable — a line in the localization cascade ADR, a
commit message on the owning campaign's surface, or a vault document of theirs — that the
application row is intended to follow the active output language. Any of the three suffices;
the requirement is that the verdict exists outside a conversation.

**Why leaving it open is the right outcome rather than a shortfall.** The row exists precisely
because the change crosses another campaign's surface, and the risk it guards is that this
campaign's reading of another campaign's intent is wrong. Checking it on the strength of three
commits that are merely *compatible* with the reading would retire the guard while leaving the
risk, which is worse than the row staying visibly open — an open row invites the confirmation,
a checked one closes the question.

The landed work is not in doubt and is not what this row tracks. The tests are stronger than
what they replaced. What is undetermined is whether the behaviour they pin is the behaviour
the owning campaign intends, and only that campaign can settle it.
