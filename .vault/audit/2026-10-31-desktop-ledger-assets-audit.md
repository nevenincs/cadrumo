---
tags:
  - '#audit'
  - '#desktop-ledger-assets'
date: '2026-10-31'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:32580b56e9fd122cec585d32e4f34faf6def72e1b764b7505cb96379d6cdd89d'
related:
  - "[[2026-10-30-desktop-ledger-assets-plan]]"
---

# `desktop-ledger-assets` audit: `desktop ledger assets review`

## Scope

Independent review of the Assets tab at `07ace7bbad`: display of the amortization schedule and timeline, flows in Storybook across en, es, ca and hu (705 renders), and the vehicle-class seed claim. The running desktop app is still to be reviewed.

## Findings

### claim-year | high | Claiming opens on the plan's last future year

`ClaimFlow.tsx:101` picks the latest row with `claimable_intervals`, and `register_reads.py:125` serves them for future years, so the van opens on 2031.

### missing-opening | high | Status says nothing is left to record for a year that cannot be worked out

`AmortizationPlan.tsx:311` clears the refusal, and `:358` falls through to `claimable_none`.

### vehicle-reason | high | A reason sentence draws the opaque asset id

`ledger.actividad_asset.errors.vehicle_affectation_required_for_class` uses `{asset_id}`; `assetFields.ts:637` leaves the declaration optional.

### minimum-column | high | The cumulative minimum sits among annual figures unlabelled

`AmortizationPlan.tsx:562,720` draw `minimum_through`, defined at `activity_asset_read_models.py:274`.

### not-known | high | Known states carry the Not known mark

`AmortizationPlan.tsx:68,373,692,709`.

### maximum-period | high | Maximum period ends on shows the exclusive boundary

`schedule.py:568` serves the first day after the useful life; `AmortizationPlan.tsx:508` draws it unchanged.

### zero-minimum | high | An unknown minimum is drawn as 0.00 incomplete

`register_reads.py:268`, `AmortizationPlan.tsx:720`; the disposal view serves null (`test_disposal_edition_gap.py:75`).

### stale-claim | high | A claim that no longer matches shows a green check

`AmortizationPlan.tsx:329,237`.

### timeline-corrections | medium | Correction and baja removal both read as tax facts recorded

`register_timeline.py:138,174`.

### timeline-claims | medium | Claim events have no span

`register_timeline.py:147,180`.

### out-of-service | medium | An element with a baja still shows an amount to amortize and its plan omits the baja

`register_reads.py:402`, `AssetList.tsx:220`.

### dropped-facts | medium | Served reason facts are not passed to the reason text

`AmortizationPlan.tsx:315,470`.

### raw-facts | medium | Non-date facts reach the screen unformatted

`assetsWords.ts:225`.

### count-pills | medium | Pills count states twice or not at all

`register_reads.py:450`.

### logic-in-react | medium | Forms and writes hold decisions the backend should own

`assetRevision.ts:105,127,230`, `assetFields.ts:586,680`, `assetWrites.ts:37`, `FixedAssetsPane.tsx:128`, `StockPane.tsx:1474`, `FilingHandoffPanel.tsx:22,157`.

### estimated-mark | medium | Estimated years share the Not known glyph

`AmortizationPlan.tsx:678`, `ClaimFlow.tsx:244`.

### broken-stories | medium | 15 Assets stories throw in their play function

`Stock.stories.tsx:342`, `AssetForms.stories.tsx:385`.

### fixture-drift | medium | The fixture states what the backend does not

`assetsFixture.ts:1737`.

### stock-wording | medium | Stock refusal and retired-book text say nothing or contradict

`StockPane.tsx:208`.

### citation-key | low | Citations use the address as React key

`AmortizationPlan.tsx:433`.

### terminology | low | One concept has several English names

Catalogue values for dotación, including covered interval and Modelo 100 edition.

### small-glyphs | low | Stale and incomplete pills are nearly the same mark

`assetsWords.ts:344`.

### panel-width | low | Minimum and Days sit off-screen with no cue

Plan table 697 px in a 512 px frame.

### handoff-end-date | high | The filing handoff prints the exclusive day as the last day

`handoffWords.ts:58`, `operation_dtos.py:584-590`.

### not-known-remains | high | Three known states still carry the Not known mark

`AmortizationPlan.tsx:418`, `AssetTimeline.tsx:214-215`, `AssetList.tsx:200-203`.

### free-method-recorded | high | An open free-method year says recording does not apply

`AmortizationPlan.tsx:774`, `planWords.ts:43-48`.

### vehicle-question | medium | The vehicle question offers answers that leave the plan unworkable

`assetFields.ts:641-645`, `actividad_asset_bindings.py:873-877`.

### free-minimum-reason | medium | The minimum's reason is false for a free method

`register_reads.py:283`, `actividad_asset_bindings.py:235-236`.

### claim-blank-reason | medium | A claim form with nothing open is blank with no reason

`ClaimFlow.tsx:102,109-111`, `register_reads.py:490`.

### future-baja-pending | medium | A future-dated baja hides the amount still to amortize

`register_reads.py:437`, `AssetList.tsx:253-262`.

### handoff-unavailable-unnamed | medium | Unworkable elements are not named among those left out

`handoffWords.ts:24-33`, `FilingHandoffPanel.tsx:126,155`.

### react-decisions | medium | React still holds decisions outside the known open items

`planWords.ts:43`, `AmortizationPlan.tsx:140`, `assetWrites.ts:129-139`, `assetFields.ts:634`.

### estimated-claim | medium | The claim flow never says a year is estimated

`ClaimFlow.tsx:242-245,375`.

### singular-count | low | Count sentences have no singular

`common.yml:1506-1523`.

### empty-further-line | low | A later payment without an invoice adds an empty timeline line

`assetRevision.ts:152`, `AssetTimeline.tsx:44`.

### partial-count-word | low | A partly recorded year counts as a year without a dotación

`register_reads.py` `_finding_counts`.

## Recommendations

Backend-owned items go to the amortization and inventory backend owners; frontend items are fixed under S07. The form-options contract serving per-stage facts and the default year, and the timeline's added event kinds, are additive and need no follow-on ADR. The vehicle-class seed matches the registry: `0001-declarations.toml:1483` flags `transporte` only in the simplified table.

Re-review at `251c76b2d1`: of the first pass, 18 findings are fixed; `not-known`, `logic-in-react`, `estimated-mark`, `terminology` and the form half of `vehicle-reason` remain, and the entries above carry them forward.

### live-list-years | high | The list read dropped years and default_year

The window's year selector stayed blank, Record a depreciation charge did nothing and the filing handoff had no year, because the registered list read projected `rows` only. The scenario fixtures hid it. Fixed in `e0efc09342`; confirmed in the running app on a synthetic profile: the selector offers years and the handoff shows 248.92 in casilla 0208.

### live-form-crash | high | The add form crashed the window once options loaded

`AssetForm.tsx` passed the served `wholly_business_facts[].value`, a public decimal, to a formatter that takes text, so a profile with a regime lost the whole window. The hand-written seed repeated the wrong shape. Fixed in `f7ce953940`, with a seed test that fails on the old shape; confirmed in the running app.

### live-opening-refusal | high | A zero opening amount with a covered year gave no reason

Fixed by the backend owner in `5263975b48`. The window now says the covered year applies only above zero and that nothing was saved.

### live-after-save | medium | Record stayed active after a save

A second press on a saved claim was refused without recording twice, but the button invited it. `b8be028a5e` clears the forecast and retires the disposal submit. The contract spec passes; the running app was not re-driven after this commit.

### live-disposal-words | low | English mixed baja and disposal

`b8be028a5e` says disposal on the English screens. Backend refusal messages under `ledger.actividad_asset.errors` still say baja. Not confirmed in the running app.

### live-stale-row | low | One stale row after a disposal was not reproduced

Once, the row still read In service well after the disposal saved, while the CLI read `out_of_service`. Two sampled repeats updated within 2 and 5 seconds. No cause was established.

### live-log-levels | medium | Expected sign-in states and a read are logged as errors

Each sign-in logs `session_unavailable [sign_in_mutation_in_progress]` as ERROR, although `native/desktop/src-tauri/src/agent/supervisor.rs:114` treats it as pending. `form-options` logs a WARNING for the ordinary missing-regime refusal. Left to the owners of sign-in and settlement logging.

### live-uncoded-rejection | medium | Rejections without a code are unexplained

`user_profile_read` and `ledger_submit` were each rejected once with no code, and `native/desktop/frontend/src/shell/hostCall.ts:108` raises the internal-error notice for that. Repeated navigation with capture did not reproduce it, and the diagnostic does not carry the raw error. Cause unknown.

### live-slow-read | low | One candidates read took 18 seconds

`ledger.actividad-asset.acquisition-candidates` took 18.3 s once during concurrent builds, against a 2 s budget. Not separated from machine load.

### live-disposal-layout | low | Disposal confirm sits below the fold and figures split across lines

In the narrow pane the final confirm button needs scrolling, and each figure's value sits on the line below its label. The change confirmation also reuses the record wording.

### live-verified | info | Flows confirmed in the running app

Sign-in, create, inline missing-field marks, wholly business hint, plan arithmetic (248.92 = 312 x 292/366), forecast, claim, duplicate claim refusal, replacement refusal for a different period, handoff, timeline kinds and order, disposal figures (170.49; loss 229.51), record, change (92.07; loss 307.93), remove, the shortened charge staying short, CLI parity of state, and es, ca and hu with no raw keys or the English words scanned. Not driven in this pass: Correct, a stock purchase with files, and replacing a charge after a basis correction.
