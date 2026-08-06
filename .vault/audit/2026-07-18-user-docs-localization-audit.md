---
tags:
  - '#audit'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
body_hash: 'sha256:c633026a904db93844b1f4179a63bfc1443e7e185315dd9ac5147cc5b7cf5fd1'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
  - "[[2026-07-18-user-docs-localization-adr]]"
---

# `user-docs-localization` audit: `campaign close honesty review`

## Scope

Close-out audit for the four-language user-documentation localization campaign
(en source; es, ca, hu targets; ~57 authored user-scope pages; 2994 gettext
entries per language). Persists three review layers required before the
campaign may be declared structurally complete: the independent S21 code
review, the fresh-context S22 honesty review (independent agent, no execution
stake), and the coordinator's adjudication of every surfaced item as
actioned, accepted-deferral, or note. Final state at review: `just docs-check`
154 passed / 0 failed including the per-language nitpicky builds, the
completeness / parity / orphan gates, and the catalogue-vs-source drift gate;
plan 21/22 with only the S22 step itself open.

## Findings

### s21-code-review-pass | low | independent code review returned PASS with one minor, actioned

The S21 reviewer re-ran every gate family green and verified: honest
non-tautological gates (babel-parsed catalogue counts, real gettext
extraction in the drift gate, real Furo builds in the switcher tests), the
single language authority (`OutputLanguage` derived at every production
surface, parity-gated), single page-set definition shared by the gates, and
deploy safety (publish confirm-gated; per-language roots validated
pre-upload). One minor was actioned in-campaign: an orphan-catalogue
assertion now fails loudly if a committed catalogue outlives its source page
(`test_docs_localization.py`). Two accepted notes: endonym labels are
deliberately dual-authored (conf.py + test) so the switcher test is an
independent oracle; the drift gate is integration-marked and therefore
lane-dependent — acceptable while the docs lane stays a required gate, and
the docs-check run demonstrably executes it.

### honesty-audit-persistence | high | audit trail existed only as exec-record prose — resolved by this document

The S22 honesty review's one blocking finding: no `.vault/audit/` document
existed for the campaign, while the governing close rule makes persisted
honesty-review output the gate itself. This document resolves it, and
records the S21 outcome above so both independent reviews are auditable.

### generated-surface-english | medium | generated pages render in English inside localized sites — accepted deferral

The translation surface is the 57 authored pages. Generated build products
(CLI reference `cli/`, generated glossary and casilla trees, executed CLI
sequences) render in English inside the `/es/`, `/ca/`, `/hu/` roots with no
on-page signpost. Accepted deferral, now explicit: the carve-out matches the
ADR's authored-surface sizing and keeps volatile generated msgids out of the
committed catalogues, but a follow-up campaign
(localized-generated-surface-signposting) should either localize the
generated prose pipeline or add a visible per-page notice on English pages
inside localized roots. Until then, the completeness contract is scoped to
the authored surface — documented here rather than silently assumed.

### generated-page-in-gettext | medium | environment-overrides is a generated committed page inside the translation set — accepted maintenance tax

`docs/reference/environment-overrides.md` is generated from `Settings` yet
committed and translated. Every settings change regenerates it, drifts three
catalogues, and reds docs-check until re-translated — this recurred live
mid-campaign (MCP-concurrency + verdict-cache settings; caught only by the
new drift gate, closed by a 5-entry top-up ×3). Accepted as a recurring,
gate-visible maintenance tax: the drift gate makes it loud, and the top-up
loop is small. Owners of settings changes should expect the docs lane to
demand a three-language top-up.

### drift-gate-blind-spot-closed | high | completeness gate could not see source drift — drift gate added in-campaign

The original completeness gate read committed catalogues against themselves,
so an English-source edit or regeneration passed green with stale
translations (proven by a peer regeneration commit that drifted the env
reference unnoticed). This falsified the ADR promise that an English edit
reds the lane until every language catches up. Closed in-campaign: the
catalogue-vs-source drift gate runs a fresh gettext extraction and requires
msgid-set equality per page per language; validated red on the real drift,
green after reconciliation; enrolled in the docs lane.

### register-consistency-three-rounds | medium | mixed-register translations required editorial passes in es and ca — lesson for briefs

Spanish shipped with mixed tú/usted across both translators (~1100 corrected
lines over three editorial rounds: bulk normalization, tail sweep, irregular
forms found by a rendered-site read). Catalan batch 1 shipped entirely in
vós register (653 corrected strings in one pass). Hungarian scanned clean
(uniform formal önöző). Lesson recorded: translator briefs must pin the
register EXPLICITLY (person, formality, with examples from the runtime
catalogue) rather than "match the runtime catalogue"; and a per-language
register scan belongs in the editorial checklist before any close.

### terminology-and-markup-fixes | low | cross-language marker and term-role defects caught and fixed by coordination review

Two defect classes surfaced by cross-batch comparison rather than any gate:
the `(secret)`/`(derived)` table markers were translated in hu and es while
their footer legends kept the literals (fixed to literal in both, matching
ca); and hu accented Spanish stems inside `:term:` role targets
(`modeló`, `justificanté`), breaking glossary resolution in the hu build
(fixed to bare stems; suffixes ride outside the role). The per-language
nitpicky build matrix catches the second class; the first has no gate and
relies on editorial review.

### remaining-notes | low | non-blocking notes routed to owners

Post-publish delivery verification checks the canonical root but not each
localized root after invalidation (deploy owner note; pre-upload validation
covers the roots). Pagefind search-UI strings and theme chrome are not part
of the gettext surface and render in English on localized roots (content is
localized; chrome is not — candidate for the signposting follow-up). The
release-notes template and contributor authoring guide were swept into the
translated surface by the rglob; kept deliberately (cost already sunk, no
harm), but a future scope pass may exclude contributor-facing pages. A
pre-existing un-backticked inline term in the ca ledger-corrections
catalogue mirrors the English source faithfully (source-side item). The
frontend web application's separate i18n module still lacks Hungarian —
out of this campaign's scope, flagged for a follow-up. The language
switcher renders inside the always-on site-broadcast header block, so the
earlier announcement-coupling caveat is moot in this configuration.

## Recommendations

- Run the follow-up campaign for generated-surface localization or
  signposting (banner on English generated pages inside localized roots;
  Pagefind/theme chrome strings in the same pass).
- Add Hungarian to the frontend web-app i18n as its own campaign.
- When authoring future translator briefs, pin register explicitly with
  worked examples, include the `(secret)`-style literal-marker rule, and the
  bare-stem-inside-role rule — all three defect classes recurred across
  independent translators.
- Keep the docs lane (with its integration-marked drift gate) a required CI
  gate; any lane refactor must preserve the `docs`+`integration`
  intersection or the drift protection silently disappears.
- Settings authors: a Settings change now carries a three-language
  env-reference top-up in its definition of done (the drift gate will
  insist).
