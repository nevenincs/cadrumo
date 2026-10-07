---
tags:
  - '#audit'
  - '#user-docs-weight'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:975398036b01f2a4b7cbf637646757b113ecf397f5c4da78e8e55a5647fba144'
related:
  - "[[2026-10-06-user-docs-weight-plan]]"
---

# `user-docs-weight` audit: `final review of the one-compile documentation`

## Scope

Independent, read-only review at plan close of every Step of `2026-10-06-user-docs-weight-plan` as one integrated change, at commit `403b191341` on `feature/tui`, restricted to the documentation tooling, the package documentation build, the desktop host's documentation handler, the website publisher and the test-lane recipes. The reviewer ran 223 unit tests (all passed) and reproduced the first finding with a script; it ran no documentation build, so no finding here rests on compiled bytes.

## Findings

### proof-verdict | high | the comparison exits 0 when a composed root is missing files or has extra ones

`dev/docs/compile_once.py:210` sums the per-context counts only, and the exit status is taken from that sum; files present in a language's own build and absent from the composed root are printed and do not reach the verdict. Reproduced: a built root with three files against a composed root with one reported no difference and exit 0. Reopens the proof of `S08`.

### switcher-published-layout | high | the language switcher's links to other languages are wrong on the published site

`dev/docs/language_switcher.py:67` takes the path to the shared base from a default language that `docs/conf.py:698` fixes as English at the apex. That is the package's layout. The website serves every language under its own code, so the Spanish link on an English page resolves beneath the English root, where nothing is, and the English link on a translated page resolves to the apex. The computation is the one the template had before this plan; `S07` rewrote the surface and kept it.

### proof-not-scheduled | medium | no recipe or lane runs the comparison against each language's own build

Every caller of the one compile uses the mode that writes roots and measures nothing. The one automated round trip, in `dev/packaging/native/docs_stage.py:548`, factors built roots and composes them back, so it proves the storage format and cannot see a root composed with the wrong language's text. The plan's first verification line and the decision's proof rule describe a gate; what exists is an instrument an operator runs.

### declaration-width | medium | two declared differences excuse any value containing their text

`dev/docs/compile_once.py:718` matches a declaration by substring. The declarations for `how-to/filing-calendar.html` therefore excuse any link on that page containing `profile-setup.html` and any class list containing `std std-doc`.

### stored-form-unread | medium | every compile writes the stored form and nothing reads it

`dev/docs/compile_once.py:651` writes the structure and each language's text beneath the build root on every call. The package build passes it to no one, staging factors the composed roots again by alignment, and the unread copy enters the package build's inventory and the shared site cache.

### oracle-moved | medium | two mechanisms changed what every build writes and are not listed where the comparison is made

`dev/docs/untranslated_typesetting.py:139` and `dev/docs/section_anchors.py` are registered for every build, so both sides of the comparison moved together: byte equality on those regions shows agreement, not faithfulness. The decision requires a difference kept on purpose to be listed where the comparison is made.

### local-roots-search | low | the local language roots carry no search index

`justfile:1547` runs the compile in a mode that pins the index off and no index pass follows, where the retired single-language builds each indexed themselves.

### lone-closing-delimiter | low | a non-page file holding only a closing mark delimiter is stored once and shipped to every language

`dev/docs/language_roots.py:314` treats a file without an opening delimiter as shared, and the composed-root refusal runs for pages only.

### lenient-decode | low | both sides of a page comparison are decoded with replacement

`dev/docs/compile_once.py:714` decodes built and composed pages with `errors="replace"`, so two different invalid byte sequences compare equal.

### catalogue-drift | medium | nine translated pages are behind their sources, so the composed pages carry English there

`dev/docs/tests/test_docs_catalogue_drift.py` fails for the three translated languages: 9 of 60 pages hold source messages their catalogues lack, the largest `how-to/review-with-google-sheets.md` with 15. The pages were last changed by a cross-session checkpoint commit, not by this plan. It bears on this plan because `dev/docs/message_marks.py:634` records the source text for a message a language leaves untranslated, so those messages reach a translated reader in English until the catalogues are regenerated and translated.

### worker-first-word | low | a Sphinx interface word first asked for inside a forked reader stops the compile

`dev/docs/sphinx_messages.py:247` answers Sphinx's own words with marks, and a mark made outside the recording process is refused at `dev/docs/compile_slots.py:348`. Reading is parallel on Linux, so a word a transform reaches first inside a reader fails the whole compile. The failure is loud and the current pages do not trigger it.

### not-reviewed | low | areas the review did not cover

The generated-reference generators behind `S06`, the command-tree projection of `S11`, the search-record content, the Rust handler's media and policy modules, and `native/CONTRACT.md` prose were not reviewed. The Rust tests were read and not run.

## Recommendations

- `proof-verdict`, `declaration-width`, `lenient-decode`, `lone-closing-delimiter`, `stored-form-unread` and `oracle-moved` are corrections within the plan's scope and are fixed under the reopened proof of `S08`.
- `switcher-published-layout` is a defect in what a reader of the website is served; derive the links from the layout authority `dev/docs/build_paths.py` already holds, and prove both layouts.
- `proof-not-scheduled` needs a decision the plan does not make: whether the comparison against each language's own build runs on a schedule, which costs one build per language each time, or stays an instrument run by an operator when a creation site changes. A follow-on amendment to `2026-10-06-user-docs-weight-adr` should say which, and name what protects a reader between runs.
- `local-roots-search` is answered in the recipe's own description: a faithful multi-root site with search is the site preview recipe.
