---
tags:
  - '#audit'
  - '#registry-support-bounds'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:513eb7799931cc1c9323c655bf70fe8b833fc235aa535e0442d69cd6c536c388'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-support-bounds with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `registry-support-bounds` audit: `Registry editions outside the supported filing years`

## Scope

Which authored modelo editions the product can ever select, measured against the registry's
own support declaration (`src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml`:
floor 2022, horizon 2026, no hard ceiling). The operator directed on 2026-10-02 that periods
below the floor will never be supported and that the registry must not grow outside the
supported bounds.

Method: the canonical selectors `select_revision` and `select_revision_for_year`
(`src/cadrumo/domain/calculations/registry/temporal.py:583`, `:693`) were asked, for every
modelo, every filing year from the floor to one past the horizon, every period the modelo's
editions declare, and the first day of every month of the filing year and the year before, which
edition serves the request. An edition no request selects is outside the bounds. Each such
edition was then checked against the `predecessor`, `casilla_storage_baseline`,
`family_storage_baseline` and `reviewed_against` keys of every reached edition. The run used a
clean extraction of HEAD `494357b819` so that in-flight registry edits could not perturb it.

## Findings

### unreachable-editions | high | 21 of 159 authored editions serve no supported filing year

138 editions are selected by at least one supported filing coordinate; 21 are selected by none.
They are authored, compiled, published and maintained, yet no supported request can reach them,
so every edit, layout regeneration, export-gap fill and target render spent on them is work on
data the product refuses to serve.

### unreachable-baselines | high | 12 unreachable editions are still storage baselines of reachable ones

These cannot simply be deleted: a reachable edition inherits payload from each through delta
storage. 100/2021 (for 2022), 165/2013-2015 (for 2016-2022), 184/2019-2021 (for 2022),
232/2016-2017 (for 2018-y-siguientes), 308/2016-2018 (for 2019-y-siguientes), 309/2016-2017
(for 2018-2022), 341/2005-2015 (for 2016-y-siguientes), 390/2021 (for 2022), 490/2021 (for
2022-1t), 576/2007 (for 2008-y-siguientes), 714/2021 (for 2022), 763/2018-4t (for
2019-y-siguientes). The 232 case carries 140 page bindings in the 2016-2017 baseline that the
in-force edition inherits unchanged.

### unreachable-dead-chains | medium | 9 unreachable editions are inherited by nothing reachable

100/2020, 184/2015, 184/2016-2018, 308/2009-2011-junio, 308/2011-julio-2015, 309/2004-2015,
763/2012-2014, 763/2015-2017, 763/2018-1t-3t. Each is named only by other unreachable editions,
so a whole chain can be removed together once its reachable successor no longer depends on it.

### no-envelope-refusal | high | nothing refuses an edition authored outside the supported years

The compiler validates editions in isolation and the registry health report censuses export
targets, but no gate asks whether an edition is selectable at all. Out-of-bounds editions
therefore accumulate silently, and in-flight work was found filling export gaps and moving
bindings inside them (309/2016-2017, 490/2021, 714/2021, 232/2016-2017).

### straddling-editions | low | 33 in-force editions start before the floor

Editions such as 232/2018-y-siguientes, 360/2010-y-siguientes and 349/2020-y-siguientes begin
before 2022 but are the editions every supported request in their modelo resolves to. Their
identifiers and selectors reach below the floor although no request there is admitted. The
registry already keys new storage at the floor (Modelos 222 and 296 were re-rooted at 2022; 303
and 390 serve from a `2022` edition), so these are the remaining exceptions rather than the
convention.

## Recommendations

- An ADR must decide whether the registry may carry any edition no supported filing coordinate
  selects, how a reachable edition that inherits from one is re-rooted without changing its
  hydrated meaning, and what refuses such an edition at authoring time. The project rule
  `aeat-registry-authority-flow` currently permits historical storage baselines outside the
  request envelope, so the decision also names the rule wording it supersedes.
- The same ADR must state whether straddling in-force editions are re-keyed to the floor, since
  that changes persisted revision identity and needs a forward stored-data migration.
