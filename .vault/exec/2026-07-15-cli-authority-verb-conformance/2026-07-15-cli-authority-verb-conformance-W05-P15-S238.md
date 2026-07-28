---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S238'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S238 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Remove certificate backend selectors and replay-specific fields from every payload and schema projection while preserving independent master-key keyring custody contracts and ## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`
- `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove certificate backend selectors and replay-specific fields from every payload and schema projection while preserving independent master-key keyring custody contracts

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`
- `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`

## Description

- Sweep the two named payload modules for certificate backend selectors and replay-specific fields.
- Confirm the master-key custody contract this Step preserves is still projected.
- Disambiguate the surviving backend field against the certificate selectors the Step removes.

## Outcome

All three clauses hold, and the third is the one a careless sweep would have broken.

The certificate payloads project no backend descriptor, and the secret-mutation payload records why: named certificate secrets have exactly one storage authority, so no selector is meaningful. That payload also never carries the secret value, exposing only whether one is registered and whether the call rotated an existing secret. The replay-specific fields are absent from the modelo auxiliary payload module.

The surviving `backend_kind` field belongs to the login result and names the master-key custody backend that performed the unwrap. That is the independent keyring custody contract this Step explicitly preserves, not a certificate backend selector; removing it on a name match would have destroyed the contract the Step was written to protect.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
