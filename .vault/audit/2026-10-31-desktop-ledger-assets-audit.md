---
tags:
  - '#audit'
  - '#desktop-ledger-assets'
date: '2026-10-31'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:7a92fef192bb8ac244c889fcf4da02ae9e8db0160eb97dbcce463880b103cd84'
related:
  - "[[2026-10-30-desktop-ledger-assets-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace desktop-ledger-assets with a kebab-case feature tag, e.g. #foo-bar.
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

## Recommendations

Backend-owned items go to the amortization and inventory backend owners; frontend items are fixed under S07. The form-options contract serving per-stage facts and the default year, and the timeline's added event kinds, are additive and need no follow-on ADR. The vehicle-class seed matches the registry: `0001-declarations.toml:1483` flags `transporte` only in the simplified table.
