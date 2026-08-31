---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:3944fb9f4f08c3c95685e5e2d07f7b61ff7e9108cbd8f6b31595e2c1396e8bff'
step_id: 'S78'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Prove C3 lexical-error focus, scalar distinctions, row editing, review and abandon, exact tuple refusal, stale conflict, locale switch, operation handoff, terminal refresh, all accessibility axes, and unique-sentinel non-retention before editor availability

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c3_editor_accessibility.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c3_editor_accessibility.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/edit/screen.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c3_editor_screen.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/edit/review.py`
- `M` `src/cadrumo/entrypoints/tui/modelo/edit/tests/test_rows_and_review.py`
- `M` `src/cadrumo/locales/{en,es,ca,hu}/flows.yml`
- `verify:` `pytest test_c3_editor_screen.py edit/` -> `36 passed`
- `verify:` `pytest dev/locales/tests/test_parity.py test_locale_translation_honesty.py` -> `42 passed`
- `verify:` `python -m dev.locales scaffold --check` -> `ca/en/es/hu ok`

## Notes

ALL ELEVEN AXES NOW COVERED, at 36 passed / 0 failed. This record previously said
PARTIAL and blocked on W06.P12b.S77; that submission path has since landed, and
the three remaining axes needed a mounted surface that did not exist.

EIGHT AXES WERE PROVABLE HEADLESSLY and are proven in the modules' own suites --
scalar distinctions, row editing, review and abandon, exact tuple refusal, stale
conflict, locale switch, unique-sentinel non-retention, and operation handoff.
Deliberately not duplicated here: a second copy would be two tests of one
property, free to disagree.

THREE NEEDED A SCREEN, because every C3 module built so far was headless logic.
`edit/screen.py` builds its controls from the admitted permitted surface, so a
casilla the contract will not accept has no widget to type into -- the
controller's structural guarantee carried onto the screen rather than restated.
It takes a catalogue SUPPLIER rather than catalogues, because review must be
judged against what the tree holds when the operator asks; caching would hide a
concurrent change from exactly the check that exists to catch it. It never
admits on mount, so the no-control-before-admission guarantee cannot be broken
by rendering early.

FOCUS IS THE ERROR CHANNEL. A refused lexeme returns focus to the input that
carried it and leaves the operator's text in place. The alternative -- accept
the keystroke, clear the box, report the problem elsewhere -- makes the operator
hunt for which field was rejected, and is how a mistyped amount becomes a
silently abandoned one. The proof moves focus AWAY before the refusal, so
passing requires the screen to actively return it; a counterpart test asserts an
ACCEPTED value does NOT steal focus, without which the first would pass equally
well against a screen that grabs focus on every keystroke and fights the
operator moving through the form.

DEFECT FOUND BY BUILDING THE SCREEN, and it is the substance of the locale axis
rather than an aside. The screen renders through ambient `tr()` while the
controller parses lexemes in the locale it was ADMITTED for, and nothing kept
the two in step: an operator could be shown Hungarian while their number was
parsed as Spanish. The failure is invisible by construction, because `1.234,56`
is a valid spelling in more than one language -- the form accepts the typing and
records a DIFFERENT AMOUNT than the operator believes they entered, with no
error for anyone to notice. The headless tests could not see it because they had
no display language to disagree with. The controller now exposes its parse
locale and the screen REFUSES to mount on a divergence, raised rather than shown
as a notice: a mismatch means the route was built with the wrong locale, which
is a programming error the operator cannot act on.

LOCALES. 32 entries written through `python -m dev.locales set` across es/en/ca/hu,
none hand-edited. `casilla` is kept verbatim in all four languages because it
names an official AEAT surface; a Catalan cognate or a generic Hungarian word
would stop matching what the operator sees on the AEAT site. The language proof
does not stop at 'mounted without raising': a catalogue silently serving the
Spanish string for every language would mount cleanly four times and still be
wrong, so it also requires the rendered titles to differ.

TEST HOME. The mounted proofs live in the sibling `test_c3_editor_screen.py`
rather than the module this row names, because they carry integration and
hex_entrypoint markers while the accessibility module is headless unit tests. A
file-level `pytestmark` cannot say both, and a test tagged with two
contradictory lane markers ends up selected by neither lane in the way its
author expected.

CARRIED FORWARD FROM THE EARLIER DRAFT, because it is the same hollow-proof
shape this campaign keeps finding: the accepted-path retention test originally
read `f"12.34{'' if True else _SENTINEL}"` and then asserted the sentinel was
absent -- a test that never introduced what it searched for, and would have
passed forever while proving nothing.
