---
tags:
  - '#audit'
  - '#registry-deadline-window-span'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:3a4cf6d675bf07c8ba4e54a5eeaf2074e8f818550a447f14f711befef94c168a'
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

## Open, needs an authority ruling: modelo 184 orphaned window years

`src/cadrumo/_data/registry/aeat/modelos/184/revisions/2015-2024/revision.toml`
declares `period_selector = { year_from = 2023, year_to = 2024, periods = ["0A"] }`,
but the revision directory is named `2015-2024` and its fragment declares windows
for 2018, 2019, 2020, 2021 and 2022. No revision claims those five years, so each
window fails canonical-owner resolution:

```
modelo 184 revision 2015-2024: deadline window 'modelo-184-2018-0a' has no unique
canonical owner for filing coordinate (2018, '0A'): no revision for year=2018
```

The directory name, the selector, and a third name (`2015-y-siguientes`) appearing
in the revision's own prose disagree about the span. Resolving it means ruling on
which filing years this application supports modelo 184 for -- widen the selector
to 2015, or delete five years of windows. That is a claim about what AEAT
authorises, so it is recorded here rather than guessed.

## Open, needs an authority ruling: modelo 322 `2008-2022` authority grade

Removing the borrowed 2023 windows revealed that this revision has no deadline
windows of its own, and it claims `filing` authority grade:

```
modelo 322 revision 2008-2022 claims 'filing' authority grade while
['deadline_windows'] remain blocked pending evidence.
```

The grade was previously satisfied only by duplicating another revision's
windows, so this is a pre-existing overstatement the fix exposed rather than
introduced. Closing it means either authoring the revision's real 2008-2022
windows, downgrading the grade, or declaring the family not applicable with a
reason and citations -- each an authority claim.

## Durable lesson

A revision's span lives in three places that can disagree: the directory name,
the `period_selector`, and the prose. The `period_selector` is the one the
loader honours; the directory name is decoration and misled this investigation
until the selector was read. Check the selector, never the directory name, when
deciding which years a revision owns.
