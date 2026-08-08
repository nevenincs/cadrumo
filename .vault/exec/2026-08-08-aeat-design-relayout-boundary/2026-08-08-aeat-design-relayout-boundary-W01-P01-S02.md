---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b0f686dc80a4b40f722dd7677cc8eed55bcd208b87f6045d911d5a6a46af6dee'
step_id: 'S02'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Compute the prescripcion-reachable filing window per modelo at the execution date

## Scope

- `src/cadrumo/_data/corpus/normatives/html/`

## Description

- Search the bundled consolidated corpus for the prescripcion provision and inventory which Ley 58-2003 articles ship.
- Locate the tree's existing canonical four-year prescription constant and its declared binding provision rather than restating the figure.
- Ground the voluntary filing deadline for each modelo against the bundled orden that fixes it.
- Compute, per modelo and per filing year, the deadline plus four whole years and compare against the execution date.

## Outcome

The window is **filing year 2022 onward for Modelo 303, Modelo 390 and Modelo 200**, measured at 2026-08-08. (This record first stated 2024 for Modelo 200; corrected by `W01.P01.S01`, which grounded that modelo's deadline on the bundled Ley 27/2014 art. 124.1 - 25 natural days after the 6 months following the period close - giving prescription on 2026-07-25 for ejercicio 2021 and 2027-07-25 for 2022. The 2024 figure came from reading this modelo's registry deadline windows, which exist only from 2024, which is the absence-is-not-an-answer error this record flags for the other two modelos.) That confirms the working assumption the plan carried for Modelo 303 and **contradicts it for Modelo 390**, where the plan assumed 2021.

Grounding is split and the split matters. The four-year period itself is **not verifiable against the bundled corpus**: the bundled Ley 58-2003 set is articles 5, 26, 27, 93, 98, 99, 119, 120, 122 and 213 plus disposicion adicional 18, and **articles 66 and 67 are absent**. No corpus excerpt was authored and no legal-catalogue entry was created. The figure instead has an existing canonical home in the tree, `TAX_RECORD_RETENTION_FLOOR_YEARS` in `src/cadrumo/domain/retention/_floor.py`, which declares its binding provision as Ley 58-2003 article 66 for the four years and article 67 for the day-after-the-deadline start, with BOE-A-2003-23186 as the locator. This Step reuses that constant and its date helper `add_prescription_years` rather than minting a second figure. The grounding gap is inherited, not introduced, and is recorded here as an open item.

The deadline anchor, by contrast, **is** grounded in the bundled corpus. Orden EHA-3786-2008 article 7 fixes the Modelo 303 deadline as the first twenty natural days of the month following each liquidation period, except the year's last period which is due in the first thirty natural days of the following January, for the monthly case in apartado 1 and the quarterly case in apartado 2. Orden EHA-3111-2009 article 8 fixes the Modelo 390 annual summary at the first thirty natural days of the January following the ejercicio.

The registry's own deadline windows were probed first and **cannot answer this question for the years that decide it**. Modelo 303 declares no deadline window before 2024 and Modelo 200 none before 2024, so absence there means the registry cannot say, never that the year prescribed. Modelo 390 does declare windows from 2020 and those confirm the computation directly: ejercicio 2021 closes 2021-01-30 plus four years, prescribing 2026-01-30, already elapsed; ejercicio 2022 closes 2023-01-30, prescribing 2027-01-30, still open.

Per modelo, as of 2026-08-08:

- **Modelo 303.** Filing year 2021 is fully prescribed, its last period 4T closing 2022-01-30 and prescribing 2026-01-30. Filing year 2022 is **partially** open: quarterly 1T prescribed 2026-04-20 and 2T prescribed 2026-07-20, while 3T prescribes 2026-10-20 and 4T prescribes 2027-01-30. Filing years 2023 onward are fully open. The partial openness of 2022 needs **no period-token partition**, because AEAT bundles a single design for the whole of 2022 and the gate's own mid-course assertion names only 2018, 2021 and 2024 as split ejercicios, so one revision at valid_from 2022 serves every open period of that year at its correct offsets.
- **Modelo 390.** Ejercicio 2021 prescribed 2026-01-30 and 2022 prescribes 2027-01-30, so the earliest in-window filing year is 2022, not the 2021 the plan assumed.
- **Modelo 200.** The floor is 2022: ejercicio 2021 prescribed 2026-07-25 and 2022 prescribes 2027-07-25, per the bundled Ley 27/2014 art. 124.1. Filing years 2024 and 2025 are open well beyond that. Filing years 2022 and 2023 are inside the window but claimed by no revision, so they refuse today as a coverage gap rather than a mis-write, recorded as `W05.P11.S70`.

Weekend and holiday displacement of a deadline moves a prescription date by at most a few days and changes no year-level verdict here: the nearest call is Modelo 303 monthly period 06 of 2022, which prescribed 2026-07-30, nine days before the execution date, and period 07 of 2022, which prescribes 2026-08-30.

Applied to the live boundary set, the window **excludes six named boundaries and includes six**. Excluded because they sit entirely below the edge: Modelo 303 2014/2015, 2016/2017 and 2020/2021, and Modelo 390 2017/2018 and 2020/2021. Included: Modelo 303 2023/2024, 2024/2025 and 2025/2026 plus the mid-2024 boundary the gate is structurally blind to, and Modelo 390 2022/2023, 2023/2024 and 2024/2025, and Modelo 200 2024/2025. Two further boundaries, Modelo 303 2021/2022 and Modelo 390 2021/2022, are **the window edge itself** rather than splits between authored revisions: each becomes a valid_from with no earlier sibling, so every year below refuses. The mid-course Modelo 303 ejercicios 2018 and 2021 are likewise outside.

## Verification

    uv run --no-sync python <scratch>/probe_prescripcion.py
    modelo 390: 2021 FULLY PRESCRIBED (0A closes 2021-01-30 prescribes 2026-01-30 closed)
    modelo 390: 2022 FULLY OPEN (0A closes 2023-01-30 prescribes 2027-01-30 OPEN)
    modelo 303: NO registry deadline window for 2009 through 2023
    modelo 200: 2024 FULLY OPEN, 2025 FULLY OPEN

The probe resolves every window through the production `ValidatedRegistryAuthority` deadline-window surface and applies the shipped `add_prescription_years` helper, so the arithmetic is the tree's own rather than the author's. The Modelo 303 and Modelo 200 pre-2024 rows read as `NO registry deadline window`, which is the honest negative that forced the corpus-grounded derivation above.

## Notes

**Open honesty item, inherited rather than introduced.** The four-year period is cited from a Python constant whose grounding is a BOE URL, not a bundled corpus file, because Ley 58-2003 articles 66 and 67 are not bundled. Fetching them requires taking the **last** consolidated version rather than the first, asserting the amending norm's identifier, and never passing the legal text through a shell. That work was deliberately not attempted here: this Step is a decision row, an agent must not author a legal-catalogue entry because its review status forges a human attestation, and a corpus excerpt written from a secondary source would pass a self-referential required-text check while proving nothing.

**The window decays in the dangerous direction.** Modelo 303 filing year 2022 loses periods as the year advances, 3T of 2022 prescribing on 2026-10-20, so a later executor must recompute rather than read this record's edge.
