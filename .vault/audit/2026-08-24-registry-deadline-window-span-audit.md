---
tags:
  - '#audit'
  - '#registry-deadline-window-span'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:add58c361da6b9291e9a8dbc4efa8ff2e19f4eb933e936c45c7144d8a06f1f5b'
related: []
---

# `registry-deadline-window-span` audit: deadline-window span ownership

A registry revision may declare deadline windows only for filing years inside
its own span. Four modelos violated that, and the violations made the entire
registry fail to load, which reddened twelve core tests that never mention
deadlines.

## Fixed: revisions declaring another revision's windows

Modelos 210, 353 and 322 each had a revision carrying byte-identical copies of a
sibling revision's windows. Modelo 210's two revisions (`2025` and
`2026-y-siguientes`) were complete duplicates of one another: all eight window
ids present in both, every body identical.

- `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/deadline_windows/0001-deadline-windows.toml` -- carried four `filing_year = 2026` windows
- `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2026-y-siguientes/deadline_windows/0001-deadline-windows.toml` -- carried four `filing_year = 2025` windows
- `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2026-y-siguientes/deadline_windows/0001-deadline-windows.toml` -- carried three `filing_year = 2025` windows
- `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2008-2022/deadline_windows/0001-deadline-windows.toml` -- carried two `filing_year = 2023` windows

Each out-of-span block was removed, along with its id in the revision's
construct completeness manifest. Registry validation errors fell from 3183 to
2760, and every remaining error belongs to modelo 303 or 184.

Landed as `c5f7ff7f94` and `f6dd525b73`.

## Fixed: an emptied fragment is a hard load failure

Modelo 322's `2008-2022` window fragment held nothing but the two out-of-span
2023 windows, so removing them left a zero-byte TOML file. The loader refuses a
fragment without a `[revisions.<id>]` table, and then refuses a fragment
directory with no TOML in it -- each a `RegistryLoadError` that made the whole
registry unloadable, a strictly worse failure than the duplication being fixed.
The fragment and its directory were removed.

When a span sweep empties a fragment, delete the fragment and its directory in
the same change; do not leave an empty file behind.

## Fixed: modelo 184 windows no revision owned

`src/cadrumo/_data/registry/aeat/modelos/184/revisions/2015-2024/revision.toml`
declares `valid_from = 2023-01-01`, `valid_to = 2024-12-31`,
`period_selector = { year_from = 2023, year_to = 2024, periods = ["0A"] }`, and
cites `aeat-dr-184-2023-2024`. Every declaration in the file says the revision
governs 2023-2024. Only the directory name `2015-2024`, stale from the earlier
`2015-y-siguientes` revision this one was split out of, says otherwise.

Its fragment still carried windows for 2018 through 2022 -- years no revision in
the modelo declares -- so each failed canonical-owner resolution:

```
modelo 184 revision 2015-2024: deadline window 'modelo-184-2018-0a' has no unique
canonical owner for filing coordinate (2018, '0A'): no revision for year=2018
```

This was first recorded here as needing an authority ruling, on the reading that
choosing between widening the selector to 2015 and deleting five years of windows
was a claim about what AEAT authorises. Reading the revision file settled it
without a ruling: the selector, both validity dates and the source reference
already agree on 2023-2024, and no revision covers 2018-2022, so those windows
were unreachable data contradicting the span that governs them. Removing them
makes the fragment agree with its own selector. Landed as `6a69b9715b`.

## Open, needs authored windows: modelos 303 and 322 filing-grade gaps

Two revisions claim `filing` authority grade while declaring no deadline windows
of their own. Both were previously masked: each was satisfying the grade with
windows an adjacent revision canonically owns, and removing those duplicates --
in modelo 322 here, in modelo 303 by the separately-briefed deadline-owner fix
`b6312a471c4` -- exposed the real state.

```
modelo 303 revision 2023 claims 'filing' authority grade while ['deadline_windows']
remain blocked pending evidence.
modelo 322 revision 2008-2022 claims 'filing' authority grade while
['deadline_windows'] remain blocked pending evidence.
```

Each governs a real filing year and needs its windows authored:

- **modelo 303 revision `2023`** -- `valid_from 2023-01-01`, `valid_to
  2023-12-31`; zero windows authored.
- **modelo 322 revision `2008-2022`** -- the directory name is again misleading:
  the revision declares `valid_from 2022-01-01`, `valid_to 2022-12-31` and
  `period_selector = { years = [2022], periods = ["01" .. "12"] }`, so it governs
  2022 alone and needs twelve monthly windows.

"Declare the family not applicable" is not available to either: both are
self-assessment modelos with real statutory filing deadlines for the years they
govern, so a not-applicable declaration would be false. The remaining honest
options are authoring the windows against AEAT sources, or downgrading the
authority grade. Authoring requires `legal_refs` and `source_refs` grounded in
official sources, which is why this is recorded rather than guessed.

These two errors are the whole remaining registry-validation surface -- the
count fell from 3183 to 2 -- and they gate the entire tree above core, because
registry validation raises during collection.

## Durable lesson

A revision's span lives in three places that can disagree: the directory name,
the `period_selector`, and the prose. The `period_selector` is the one the
loader honours; the directory name is decoration and misled this investigation
until the selector was read. Check the selector, never the directory name, when
deciding which years a revision owns.
