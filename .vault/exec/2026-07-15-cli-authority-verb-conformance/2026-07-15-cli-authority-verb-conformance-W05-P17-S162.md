---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S162'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S162 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Rewrite data-access protection procedures for passphrase, recovery, logout, quarantine, and reset and ## Scope

- `docs/how-to/protect-data-access.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rewrite data-access protection procedures for passphrase, recovery, logout, quarantine, and reset

## Scope

- `docs/how-to/protect-data-access.md`

## Description

- Materialise the live command tree and read the accepted custody grammar from
  the CLI itself rather than from any document.
- Check the page's five named topics against that surface one at a time.
- Add the missing quarantine route, sited so a reader meets it before the
  irreversible option.

## Outcome

SATISFIED, and mostly by verification rather than rewrite. Four of the five
named topics were already correct; one was a genuine operator-safety gap.

Passphrase, recovery, logout and reset are accurate at HEAD. Every command the
page teaches resolves against the live tree and matches the signatures I read
from the CLI: the login verb takes an optional profile positional, passphrase
change and recover both accept the bounded secrets-stdin JSON object, recovery
status reports enrolment without exposing the words, and reset carries yes,
override-retention and reason exactly as the page describes. The page reaches
those commands through sequence directives whose contracts carry the accepted
spellings verbatim.

QUARANTINE was the real gap, and it mattered more than its size. The page told
a reader whose data would not open that "the only way forward is a reset",
immediately above an irreversible all-profile delete. That is true only when
BOTH the passphrase and the recovery words are gone. When merely SOME records
fail to open, quarantine is the correct first move: it moves each unreadable
record, still encrypted, into an archive in the same storage, leaves readable
records untouched, previews before running, and deletes nothing - so a
passphrase recovered later still finds the archived records. A reader who
missed that distinction would destroy recoverable data.

The procedure itself is correctly owned by the repair guide, which documents it
with a preview-and-confirm sequence and links back here for the recovery key.
So the fix is a route, not a duplicate: the page now names quarantine at the
decision point and its next-steps link says what the repair guide is for
instead of describing it as problems "that do not need a reset".

Gates at HEAD `286db29da0ea427ff81306bf68353cf9b3b308f3`:

- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
  dev/quality/tests/test_doc_privacy.py -m "" -n0` collected 17 cases and
  exited `1 failed, 16 passed in 17.95s`. The sequence contract passed in
  full. The single failure is attributed below and is not this page's.

## Notes

The failing case is peer-owned and is recorded rather than fixed. The
cross-project identifier gate flags a placeholder AWS role ARN in a deploy
test. Attribution by dates rather than by subject: the gate banning those
identifiers landed on 2026-07-27, and the file carrying the placeholder landed
on 2026-07-28 - a peer's new file meeting a gate that arrived the day before.
The value is an all-zeros placeholder, not a real account, so whether the ban
should match it at all is a judgement for the owning campaign; both remedies
available (a non-numeric placeholder, or an allowlist entry) are theirs to
choose. Editing another campaign's deploy authority test to green my own run
would be the wrong move.

Worth recording how nearly this page was rewritten unnecessarily. An initial
sweep searched the documentation tree for literal command strings and returned
nothing for passphrase, recovery, certificate and reset, which read as four
whole surfaces missing from the docs. They were all present - the pages cite
commands through sequence directives by NAME, so the literal-string search was
looking for a shape the data does not use. The search ran, the paths existed,
and the result was still meaningless. Reading one page settled in a minute what
the sweep had got backwards.
