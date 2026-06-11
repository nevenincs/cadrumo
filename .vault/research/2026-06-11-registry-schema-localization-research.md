---
tags:
  - '#research'
  - '#registry-schema-localization'
date: '2026-06-11'
related:
  - '[[2026-06-08-registry-localization-backend-adr]]'
---

# `registry-schema-localization` research: `modelo schema localization continuation`

This note records the current-state handoff for the schema-localization campaign. It focuses on the registry-backed modelo schema path, where official Spanish casilla labels remain legal invariants and operator-facing localized labels/help are carried by lazy-loaded registry locale TOML files.

## Findings

- The accepted decision is `2026-06-08-registry-localization-backend-adr`: keep `CasillaDefinition.label` as the official Spanish invariant, load per-modelo or per-revision locale TOML lazily, validate locale keys against real `casilla_id` or `continuidad_id`, and expose localized values through `get_label(locale)` and `get_help(locale)`.
- The backend implementation already exists in `src/aeat/domain/calculations/registry/_loader.py` and `src/aeat/domain/calculations/registry/_schema_surfaces.py`. Locale files under `locales/` are excluded from revision-fragment parsing but included in registry fingerprints, so edits invalidate the compiled registry cache.
- Existing concrete locale coverage before this continuation was seeded but sparse: M100 revision `2024` had 3 of 2068 casilla labels/help entries per locale, M130 revision `2019-y-siguientes` had 7 of 20 labels and 2 of 20 help entries per locale, M200 revision `2024-y-siguientes` had 2 of 3232, and M303 revision `2023-y-siguientes` had 2 of 120.
- The M130 revision is now the first complete small-model exemplar: every one of its 20 casillas has localized labels and help in `en`, `ca`, and `hu`, including the internal carry-forward casilla `saldo-negativo-fin-periodo`.
- Core application locale YAML files were not edited. The `aeat.locales` CLI remains the authority for core `tr(...)` catalogue work, while registry-local casilla translations currently live in the model-local TOML mechanism defined by the ADR.

## 2026-06-11 CLI authority update

The follow-up ADR `2026-06-11-modelo-locales-cli-adr` is accepted and implemented. Modelo schema-local locale TOML is now controlled by `python -m aeat.locales modelo ...`; direct hand edits to registry-local `locales/*.toml` are no longer the routine campaign path.

Available commands:

- `python -m aeat.locales modelo coverage <locale> <modelo> <revision>` reports translated and required labels/help.
- `python -m aeat.locales modelo scaffold <locale> <modelo> <revision>` aligns schema-local TOML and preserves translated leaves.
- `python -m aeat.locales modelo set <locale> <modelo> <revision> labels|help <key> <value>` writes one translated leaf after registry-key validation.
- `python -m aeat.locales modelo remove <locale> <modelo> <revision> labels|help <key>` removes one existing translated leaf.
- `python -m aeat.locales modelo audit <locale> <modelo> <revision>` reports coverage and drift, exiting nonzero while coverage is incomplete.

Project rule `modelo-locales-cli-authority` codifies this constraint. The existing `aeat-locales-cli` rule still governs eager YAML catalogues; the new rule governs registry-local modelo schema TOML.

Spanish schema-local TOML is not part of the current rollout. Official Spanish schema labels remain in `CasillaDefinition.label` and serve as the fallback for Spanish output unless a future ADR changes that model.

## Seeded scaffold baseline

P04.S18 scaffolded the existing seeded non-Spanish schema-local files through the CLI for M100, M130, M200, and M303. Scaffold placeholders are values equal to their schema keys and do not count as completed translations.

Current seeded coverage after scaffold:

- M100 `2024`: `ca`, `en`, and `hu` each report `labels=3/2068 help=3/2068`.
- M130 `2019-y-siguientes`: `ca`, `en`, and `hu` each report `labels=20/20 help=20/20`.
- M200 `2024-y-siguientes`: `ca`, `en`, and `hu` each report `labels=2/3232 help=2/3232`.
- M303 `2023-y-siguientes`: `ca`, `en`, and `hu` each report `labels=2/120 help=2/120`.

M100 scaffold exposed and fixed a manager bug where all-revision inventory deduped revision-local keys without `revision_id`. The fix preserves revision-local translations when the same casilla id appears in multiple revisions, and the existing M100 translated leaves were restored through `modelo set`.

## 2026-06-11 translation progress

M303 `2023-y-siguientes` English, Catalan, and Hungarian are now complete. All label/help leaves were written through `python -m aeat.locales modelo set`; the schema-local TOML was not hand-edited.

Verified commands:

- `uv run --no-sync python -m aeat.locales modelo coverage en 303 2023-y-siguientes` -> `locale=en modelo=303 revision=2023-y-siguientes etiquetas=120/120 ayuda=120/120`.
- `uv run --no-sync python -m aeat.locales modelo audit en 303 2023-y-siguientes` -> `locale=en modelo=303 revision=2023-y-siguientes etiquetas=120/120 ayuda=120/120`.
- `uv run --no-sync python -m aeat.locales modelo coverage ca 303 2023-y-siguientes` -> `locale=ca modelo=303 revision=2023-y-siguientes etiquetas=120/120 ayuda=120/120`.
- `uv run --no-sync python -m aeat.locales modelo audit ca 303 2023-y-siguientes` -> `locale=ca modelo=303 revision=2023-y-siguientes etiquetas=120/120 ayuda=120/120`.
- `uv run --no-sync python -m aeat.locales modelo coverage hu 303 2023-y-siguientes` -> `locale=hu modelo=303 revision=2023-y-siguientes etiquetas=120/120 ayuda=120/120`.
- `uv run --no-sync python -m aeat.locales modelo audit hu 303 2023-y-siguientes` -> `locale=hu modelo=303 revision=2023-y-siguientes etiquetas=120/120 ayuda=120/120`.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_registry_locales_parity.py -q -m unit` -> `2 passed`.

The M303 English pass covered both casilla part files:

- `0001-casillas.part-001.toml`: semantic IVA, compensation, pro rata, declaration period, and numbered accrued-VAT boxes.
- `0001-casillas.part-002.toml`: remaining official numeric boxes, including deductible VAT, simplified regime, additional information, result, and corrective-return fields.

M100 `2024` has begun. The work-income slice immediately after seeded casilla `0001` is complete for `en`, `ca`, and `hu`: casillas `0002` through `0026` now have translated labels and help in all three locales. The movable-capital income slices `0027` through `0036`, `0037` through `0046`, and `0047` through `0057` are also complete in all three locales. The sparse transition slice `0058`, `0060`, and `0062` through `0068` is complete in all three locales. The first real-estate use/location slice, `0069` through `0080`, the first real-estate activity, availability, and imputed-income slice, `0081` through `0090`, the first lease-party detail slice, `0091` through `0100`, the rental income and deductible expense slice, `0101` through `0110`, the legal-defense, service-cost, acquisition-type, and acquisition-date slice, `0111` through `0120`, the transfer-date, cadastral-value, improvement, and depreciation-base slice, `0121` through `0130`, the depreciation/acquisition metadata slice, `0131` through `0140`, the accessory-property acquisition, depreciation, net-income, and housing-rental reduction slice, `0141` through `0150`, the real-estate income totals plus first economic-activity reduction slice, `0151` through `0160`, the DANA reduction plus economic-activity identification slice, present keys in `0161` through `0170`, the economic-activity computable-income slice, `0171` through `0180`, the inventory and personnel-expense slice, `0181` through `0190`, the subsistence, lease, repair, utility, mutual-society, professional-service, and insurance expense slice, present keys in `0191` through `0200`, the mixed activity-expense plus rural-residence, relocation, single-parent, and nursery identifier slice, `0201` through `0210`, the childcare, rental, patronage, deductible-item, provision, and deductible-total slice, `0211` through `0220`, the net-income, hard-to-justify expense, intangible-depreciation, and dwelling-deduction slice, `0221` through `0230`, the economic-activity reduced-net-income and activity-reduction slice, `0231` through `0236`, the spouse disability deduction metadata slice, `0240` through `0249`, the Rioja cultural donation plus entity-imputation slice, present keys in `0250` through `0260`, the imputed deduction, public-aid, and international fiscal-transparency slice, `0261` through `0270`, the image-rights and collective-investment imputation slice, `0271` through `0280`, the prize and gambling capital-gain/loss slice, `0281` through `0290`, the prize plus protected-housing subsidy slice, `0291` through `0300`, the public-aid capital-gain/loss plus DT 9 transfer/ownership slice, `0301` through `0310`, the company, investment-fund, annuity-reinvestment, and DT 9 capital-gain reduction slice, `0311` through `0320`, the IIC/SOCIMI loss/sum plus transmitted-securities opening slice, `0321` through `0330`, the traded-share acquisition, gain, DT 9 reduction, loss, and computed subtotal slice, `0331` through `0340`, the subscription-rights ownership, transfer-value, acquisition-value, gain, and DT 9 reduction slice, `0341` through `0350`, the subscription-rights reduced-gain/loss subtotal plus 200-euro aid and other-capital-gain collection metadata slice, `0351` through `0359`, the deferred other-capital-gain allocation/collection rows, `0363` through `0375`, the remaining deferred-collection, social-security-reduction marker, and other-capital-gain subtotal slice, present keys in `0376` through `0390`, the previous-year gain/loss imputation plus reinvestment deferral allocation slice, `0391` through `0400`, the residence-change securities value, gain, and DT 9 reduction slice, `0401` through `0410`, the residence-change reduced-gain subtotal plus special-regime and base-general integration slice, present keys in `0411` through `0420`, the capital-gain integration, social-welfare contribution, and movable-capital balance slice, `0421` through `0430`, the general taxable-base negative-balance and base calculation slice, `0431` through `0435`, and the savings-base movable-capital and capital-gain carry-forward slice, `0436` through `0445`, are complete in all three locales.

The savings-base gain/loss and movable-capital carry-forward continuation slice, `0446` through `0455`, is also complete in all three locales.

The child identifier, savings taxable-base total, joint-taxation reduction, and first social-welfare reduction slice, `0456` through `0468`, is also complete in all three locales.

The spouse social-welfare reduction, disability-related social-welfare reduction, and protected-estate reduction slice, `0469` through `0481`, is also complete in all three locales.

The compensatory pension, maintenance annuity, and professional-athlete mutual-society reduction slice, `0482` through `0490`, is also complete in all three locales.

The applied-reduction and general-liquidable-base sparse slice, `0491` through `0497`, `0499` through `0501`, and `0505`, is also complete in all three locales. Casillas `0502` through `0504` remain untranslated and should be handled next before moving on to `0506` and later keys.

The Balearic investment reserve, autonomous-community birth-deduction recapture, remaining reduction, Balearic tangible-goods income, and savings-liquidable-base bridge slice, `0502` through `0504` and `0506` through `0510`, is also complete in all three locales.

The personal and family minimum allocation slice, `0511` through `0524`, is also complete in all three locales.

The exempt-income, maintenance-annuity total, and general-liquidable-base tax-scale slice, `0525` through `0535`, is also complete in all three locales.

The savings-liquidable-base tax-scale, savings quota, average-rate, La Palma, and gross-tax slice, `0536` through `0546`, is also complete in all three locales.

The first deduction block, `0547` through `0559`, covering habitual-residence investment, new-company investment, cultural-interest expenses, donations, business-investment incentives, and Canary Islands reserve/tangible-goods deductions, is also complete in all three locales.

The deductions and regularization bridge slice, `0560` through `0585`, covering Ceuta/Melilla, transitional habitual-residence rental, autonomous deductions, EU/EEA family-unit deduction, energy-efficiency works, loss-of-deduction regularization, La Palma residence, and the increased net state tax liability, is also complete in all three locales.

The increased quota, international double-taxation, attributed withholding, and self-assessment quota slice, `0586` through `0595`, is also complete in all three locales.

The retentions, payments on account, instalment payments, and non-resident income tax quota slice, `0596` through `0605`, is also complete in all three locales.

The legacy Directive 2003/48/EC withholding, electric-vehicle deduction, charging-point deduction, payments-on-account total, differential quota, maternity deduction, nursery expense increase, and descendant identification slice, `0606` through `0615`, is also complete in all three locales.

The descendant disability deduction metadata and start of the ascendant disability deduction slice, `0616` through `0625`, is also complete in all three locales.

The ascendant disability deduction metadata and transferred-rights slice, `0626` through `0635`, is also complete in all three locales.

The ascendant disability deduction amount and Annex B rental-contract detail slice, `0636` through `0645`, is also complete in all three locales.

The autonomous rental deduction and large-family certificate metadata slice, `0646` through `0655`, is also complete in all three locales.

The large-family transferred-rights, single-parent deduction, and descendant regularization slice, `0656` through `0665`, is also complete in all three locales.

The ascendant regularization, administrative-criteria discrepancy, return result, and autonomous-community IRPF allocation slice, present casillas `0666`, `0667`, `0669`, `0670`, `0671`, `0672`, and `0675`, is also complete in all three locales.

The previous-assessment regularization, Annex A habitual-dwelling works, Asturias relocation deduction, spouse-compensation, and habitual-dwelling deduction amount slice, present casillas `0676`, `0677`, `0683`, `0684`, `0685`, `0689`, `0690`, `0691`, `0692`, `0693`, `0694`, `0695`, `0698`, and `0699`, is also complete in all three locales.

The payment/refund result, correction refund, Annex A habitual-dwelling deduction amount, named investment-event application, dwelling acquisition date, and mortgage-loan identifier slice, casillas `0700` through `0709`, is also complete in all three locales.

The Annex A mortgage loan percentage, new-company investment, and rental lessor identifier/payment slice, casillas `0710` through `0719`, is also complete in all three locales.

The Annex A second-lessor payment, general deduction amount, patronage/donation/political contribution deduction, cultural-interest investment deduction, Ceuta/Melilla deduction, and EU-resident family-unit tax quota slice, casillas `0720` through `0729`, is also complete in all three locales.

The EU-resident family-unit joint-liability/deduction calculation and Canary Islands investment reserve 2020-2022 allocation/investment slice, casillas `0730` through `0739`, is also complete in all three locales.

The Canary Islands investment reserve 2022-2024 investment and pending-materialization continuation slice, casillas `0740` through `0749`, is also complete in all three locales.

Verified commands:

- `uv run --no-sync python -m aeat.locales modelo coverage en 100 2024` -> `locale=en modelo=100 revision=2024 etiquetas=718/2068 ayuda=718/2068`.
- `uv run --no-sync python -m aeat.locales modelo coverage ca 100 2024` -> `locale=ca modelo=100 revision=2024 etiquetas=718/2068 ayuda=718/2068`.
- `uv run --no-sync python -m aeat.locales modelo coverage hu 100 2024` -> `locale=hu modelo=100 revision=2024 etiquetas=718/2068 ayuda=718/2068`.
- Structured placeholder scans over casillas `0002` through `0026`, `0027` through `0036`, `0037` through `0046`, `0047` through `0057`, sparse keys `0058`, `0060`, `0062` through `0068`, `0069` through `0080`, `0081` through `0090`, present keys in `0091` through `0100`, `0101` through `0110`, `0111` through `0120`, `0121` through `0130`, `0131` through `0150`, `0151` through `0160`, present keys in `0161` through `0170`, `0171` through `0180`, `0181` through `0190`, present keys in `0191` through `0200`, `0201` through `0210`, `0211` through `0220`, `0221` through `0230`, `0231` through `0236`, `0240` through `0249`, present keys in `0250` through `0260`, `0261` through `0270`, `0271` through `0280`, `0281` through `0290`, `0291` through `0300`, `0301` through `0310`, `0311` through `0320`, `0321` through `0330`, `0331` through `0340`, `0341` through `0350`, `0351` through `0359`, `0363` through `0375`, present keys in `0376` through `0390`, `0391` through `0400`, `0401` through `0410`, present keys in `0411` through `0420`, `0421` through `0430`, `0431` through `0435`, and `0436` through `0445` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0446` through `0455` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0456` through `0468` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0469` through `0481` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0482` through `0490` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0491` through `0497`, `0499` through `0501`, and `0505` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0502` through `0504` and `0506` through `0510` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0511` through `0524` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0525` through `0535` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0536` through `0546` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0547` through `0559` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0560` through `0585` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0586` through `0595` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0596` through `0605` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0606` through `0615` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0616` through `0625` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0626` through `0635` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0636` through `0645` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0646` through `0655` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0656` through `0665` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over present casillas `0666`, `0667`, `0669`, `0670`, `0671`, `0672`, and `0675` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over present casillas `0676`, `0677`, `0683`, `0684`, `0685`, `0689`, `0690`, `0691`, `0692`, `0693`, `0694`, `0695`, `0698`, and `0699` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0700` through `0709` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0710` through `0719` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0720` through `0729` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0730` through `0739` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- A subsequent structured placeholder scan over casillas `0740` through `0749` found no remaining placeholder labels or help in `en`, `ca`, or `hu`.
- `uv run --no-sync pytest src/aeat/locales/tests/test_modelo_manager.py src/aeat/locales/tests/test_modelo_cli.py src/aeat/domain/calculations/registry/tests/test_registry_locales_loader.py src/aeat/domain/calculations/registry/tests/test_registry_locales_parity.py -q -m "unit or integration"` -> `21 passed`.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/_validate_record_sections.py` -> `All checks passed`.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_temporal.py -q -m unit` -> `9 passed`.

During the M100 CLI batch, the registry package public import contract was found inconsistent: `registry.__init__` still expected `parse_modelo_period`, while `_queries.py` no longer exposed it. The helper and public re-export were restored so `from aeat.domain.calculations.registry import parse_modelo_period` works and the locale CLI remains importable.

## Remaining campaigns

Prioritize work in this order:

1. M100 `2024`: continue after completed casilla `0749`, from `labels=718/2068 help=718/2068` per locale. The scaffold still exposes 1350 untranslated label/help leaves per locale, so work should continue by registry section or source grouping.
2. M200 `2024-y-siguientes`: continue from the two translated seeded leaves per locale. The scaffold exposes 3232 label/help leaves per locale, so this should be planned as a separate large-model translation campaign.
3. New modelo/revision enrollment: run `coverage`, then `scaffold`, then translate with `set`, and finish with `coverage` evidence. Do not create Spanish schema-local TOML as part of routine enrollment.

Every campaign should record the exact coverage output before and after translation work. A locale/revision is complete only when coverage reports all required labels and help translated; placeholder equality with the schema key is unfinished work, not success.
