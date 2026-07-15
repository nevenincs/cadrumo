---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-26'
modified: '2026-07-11'
step_id: 'S343'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-ANDREA-HIGH Article 27 LGT late-filing recargo + intereses de demora computation entirely absent from CLI

## Scope

- `closed by existing deadline/plazo implementation and reverified on 2026-07-01: domain deadlines _recargo resolves Art. 27 LGT completed-month bands using the current post-Ley 11/2021 scale (1 percent plus 1 percent per completed month`
- `15 percent plus intereses after 12 months) rather than the obsolete 5/10/15/20 percent bracket named in the original row`
- `modelo work plazo summaries attach the recargo band and CLI calculate emits a warning notice plus structured deadline.recargo payload for overdue work units`
- `verified by 35 focused recargo/deadline/CLI tests after registry-source blockers were cleared`
- `src/aeat/domain/deadlines/ src/aeat/application/modelo/_work_plazo.py src/aeat/entrypoints/cli/_modelo_rendering.py`

## Description

Resolved the two open HIGH findings from the 2026-07-10 cross-domain-continuity
audit against the Art. 27.2 LGT recargo surface. Grounded every boundary decision
in the bundled authoritative consolidated corpus for Ley 58/2003 art. 27
(`src/aeat/_data/corpus/normatives/html/ley-58-2003-art-27.html`), legal ref
`ley-58-2003:art-27.2`.

- Finding 1 (exact twelve-month boundary): the recargo table resolved the exact
  twelve-month anniversary of the plazo to the 15%-plus-intereses tail, one day
  too early. Art. 27.2 pins the tail to a filing presented "una vez transcurridos
  12 meses", with intereses de demora running "desde el día siguiente al término
  de los 12 meses posteriores a la finalización del plazo" — so the anniversary
  itself is the término and still belongs to the graduated 1%-per-completed-month
  band, and the 15% tail begins the following day.
- Reworked the band table `src/aeat/_data/registry/aeat/legal/ley-58-2003-recargo-bands.toml`:
  added a graduated `completed_months_12` band (13% = 1% + 12 completed months, no
  interest) and moved `after_12_months` (15% + interest) to `min_completed_months = 13`.
- Date-gated the tail in `src/aeat/domain/deadlines/_recargo.py`: added
  `twelve_month_anniversary`, `more_than_twelve_months_elapsed`, and
  `_interest_bearing_tail_band`; `build_recovery_for_overdue` now selects the tail
  only when the presentation date is strictly after the anniversary (a
  completed-months count alone cannot distinguish the anniversary from the day
  after — both report twelve completed months).
- Added failing-first real-behaviour regressions in
  `src/aeat/domain/deadlines/tests/test_recargo.py` for the exact anniversary
  (13%, no interest — the audit's demonstrated 2026-04-20 / 2027-04-20 case) and
  the day after (15% + interest), plus anniversary/leap-day and strict-boundary
  predicate tests. Expected percentages derived from the statutory scale, not the
  code under test.
- Finding 2 (statute-fact gate): the calculate path emitted an imperative Art. 27
  rate payload for every overdue work unit given only a work unit and a date,
  over-claiming eligibility for informational/zero/refund work. Extended
  `src/aeat/application/modelo/_work_plazo.py` `modelo_work_plazo_summary` with
  optional `amount_payable`, `presentation_date`, and `prior_requirement` facts
  and a `conditional` flag on `ModeloWorkRecargoSummary`. It now fails closed:
  absent the facts it surfaces a rate-only CONDITIONAL advisory (no eligibility
  claim); a prior requerimiento (Art. 27.1 "sin requerimiento previo") or a
  non-positive importe a ingresar (Art. 27.2 recargo "sobre el importe a
  ingresar") attracts no recargo; only all three facts present mark a statutory
  computation (`conditional = False`).
- Threaded the distinction through the typed operator surface:
  `WorkRecargoPayload.conditional` (`src/aeat/entrypoints/cli/_modelo_payloads.py`)
  and the `Notice` context / text lines in
  `src/aeat/entrypoints/cli/_modelo_rendering.py`.
- Added `src/aeat/application/modelo/tests/test_modelo_calculate_recargo_notice.py`
  proving the facts-absent conditional advisory, the facts-present statutory
  computation, and both fail-closed branches (prior requerimiento, zero amount).

## Outcome

Both findings closed. Focused gate green: 37 passed across
`test_recargo.py`, `test_extemporaneidad.py`, the application and CLI
`test_modelo_calculate_recargo_notice.py`, and `test_work_plazo_m303_recargo.py`.
Collection over `src/aeat` is clean (no collection errors). Ruff check and format
clean on all authored files. Landed in commit `97bac6403b` with an explicit,
verified index carrying zero foreign markers.

## Notes

`src/aeat/entrypoints/cli/_modelo_rendering.py` carried live peer WIP (an unrelated
cross-period suppression regex, a `calculation_revision_state_label` rename, and a
`_formula_operation_label` refactor) in regions disjoint from my three additions.
To avoid sweeping that peer work into my commit, I landed only my hunks via the
apply-cached gated drive: a HEAD-anchored own-edits-only patch staged with
`git apply --cached`, verified the staged index carried zero foreign markers, then
committed the verified index (no pathspec, since a pathspec commit would re-take
the peer-bearing working tree). The peer WIP remains intact and unstaged in the
working tree.

A broader run of `src/aeat/domain/deadlines/tests`,
`src/aeat/application/modelo/tests`, and the registry suite showed 8 failures — all
outside this feature surface (`_collect_revision_verification_findings()` missing a
new `invoice_repository` kwarg, a `renta-2025-profile-has-economic-activity`
binding, taxation-comparison, and a 38-binding count). Those stem from uncommitted
peer WIP in shared application modules (`_verification_actions.py`,
`_profile_binding.py`, `_registry_helpers.py`, etc.) and are not caused by these
additive recargo/plazo changes.

Plan step W09.P41.S343 left unchecked for the coordinator to verify independently.

## Corrective execution (2026-07-11)

### Description

- Ground the reopened boundary with `vaultspec-rag` against the accepted Article
  27 ADR, the related research, the deadline engine, the calculate projection,
  and the real CLI surface.
- Replace `ModeloWorkPlazoSummary` and its mixed-purpose recargo summary with
  `ModeloWorkDeadlinePosture` and `ModeloWorkConditionalRecargoPreview`.
  Remove the optional payable-amount, presentation-date, and
  prior-requirement primitives that could previously mark a rate as a statutory
  computation.
- Make the preview contract one-way and explicit: it carries the governed rate
  reference date and literal `assessment_status="unassessed"`; the reference
  date is not a presentation date.
- Project the renamed contract onto the CLI payload and notice context. Replace
  `deadline.recargo`, `recargo_conditional`, and the recargo-liability notice
  with `conditional_recargo_preview`, an unassessed status, and language that
  states no Article 27 surcharge or interest liability is determined.
- Update all shipped CLI locales and the M130/M303 application and real CLI
  regressions. Preserve the exact twelve-month rate boundary by deriving test
  expectations from the governed deadline recovery engine.

### Outcome

The calculate path now exposes only voluntary-deadline posture and an
explicitly unassessed conditional rate preview. It cannot accept or represent
an unproven actual presentation date, amount payable, or no-prior-requirement
fact as a statutory Article 27 assessment.

### Verification

- `uv run pytest -q src/aeat/domain/deadlines/tests/test_recargo.py src/aeat/domain/deadlines/tests/test_extemporaneidad.py src/aeat/application/modelo/tests/test_modelo_calculate_recargo_notice.py src/aeat/application/modelo/tests/test_work_plazo_m303_recargo.py src/aeat/application/modelo/tests/test_work_plazo_m100_campaign.py src/aeat/entrypoints/cli/tests/test_modelo_calculate_recargo_notice.py src/aeat/core/i18n/tests/test_placeholder_parity.py` — 42 passed.
- `uv run ruff check` and `uv run ruff format --check` against all S343 Python
  modules and tests — passed.

### Notes

The annual-campaign plazo regression was live untracked peer work. Its owner
updated the renamed public deadline-posture import and confirmed its focused
tests; it was not included in this Step's authored diff.

### Review correction (2026-07-11)

Independent review found that the no-preview fallback still selected the
general warning translation, whose text says a rate is displayed. Route only
the `conditional_recargo_preview is None` branch through a dedicated
no-preview translation key in every shipped locale. The preview-bearing branch
retains its rate-preview wording.

Extend the direct typed CLI-renderer regression to assert the JSON projection
contains `conditional_recargo_preview: null`, retains the explicit unassessed
status, and does not describe a displayed rate.

Verification: `uv run pytest -q
src/aeat/entrypoints/cli/tests/test_modelo_calculate_recargo_notice.py
src/aeat/core/i18n/tests/test_placeholder_parity.py` — 3 passed. Targeted
`ruff check` and `ruff format --check` — passed.
