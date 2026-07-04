---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S01'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m303-refund-fichero-block with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-06-24-m303-refund-fichero-block-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add the refund-account financial fields (swift_bic, bank_name, bank_address, bank_city, bank_country_code, sepa_marca) to the profile schema as sensitivity financial and ## Scope

- `src/aeat/_data/registry/aeat/user_profile/schema.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the refund-account financial fields (swift_bic, bank_name, bank_address, bank_city, bank_country_code, sepa_marca) to the profile schema as sensitivity financial

## Scope

- `src/aeat/_data/registry/aeat/user_profile/schema.toml`

## Description

- Declare the refund-account financial fields on the filing-export profile section of the central schema: `swift_bic`, `bank_name`, `bank_address`, `bank_city`, `bank_country_code`, and `sepa_marca`.
- Stamp every field `sensitivity = "financial"` and `required = false`, keeping the refund-account data inside the encrypted secure-storage sensitivity class, per the schema-central-config authority.
- Bind each field to its DR303 cuenta-devolucion (DID) page position in the description (SWIFT-BIC 12, bank name 57, address 127, city 162, country 192, Marca SEPA 194), and record that the value is read transiently at export from encrypted storage and never logged.
- Give each field an `export_headers` alias matching its field key so the fichero header composer can resolve it.

## Outcome

- The six refund-account fields are present in `src/aeat/_data/registry/aeat/user_profile/schema.toml` at HEAD, all `sensitivity = "financial"`, verified by grep and by reading the block.
- The registry loads cleanly and the downstream M303 fichero export tests that read these fields pass, confirming the schema declarations are consumed correctly.

## Notes

- This record documents the verified landed state at HEAD; the schema fields were implemented and committed by the feature campaign and confirmed present, correctly typed, and consumed by the export layer.
- The `sepa_marca` field is a derived-at-export indicator, not a persisted operator fact; it carries the same financial sensitivity for schema completeness.
