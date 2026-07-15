---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S102'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# re-run Laia e-commerce OSS UK Marc autonomo intracom and Joan SL intracom confirming OSS 349 UK IVA-wallet handled

## Scope

- `.vault/audit/`

## Description

- Ran all commands with `AEAT_LOCAL_STORAGE_ROOT` set to the isolated `.runtime-s102-personas` directory and `AEAT_OUTPUT_LANGUAGE=en`; no command contacted AEAT.
- Created valid local profiles `laia-oss` (natural person, OSS-enrolled), `marc-intracom` (natural-person intra-community operator), and `joan-sl-intracom` (S.L. intra-community operator). Joan's first create refused missing `--legal-name`; retrying with `--legal-name 'Comercial Joan SL'` succeeded. This was clear operator remediation, not a product defect.
- Laia: `aeat --profile laia-oss app overview calendar --from 2025-01-01 --to 2026-12-31 --allow-incomplete --show-suppressed` listed Modelo 369 windows. `aeat --format json --profile laia-oss app modelo work create --modelo 369 --year 2025 --period 1T --revision esquema-union` created work unit `608540ab5ff81e4e4b5ba81c7328201873ebdb2102ee29902779f70cd9a26fec`. Calculate saved draft `325f15bdbb801372810a479152e3429d93c5c63dee644610ca2d48f76e18447d` with explicit unresolved `ledger_oss_aggregation` advisories.
- Laia: `aeat --format json --profile laia-oss app ledger invoice add --kind issued --counterparty-nif GB123456789 --counterparty-name 'London Retail Ltd' --invoice-number LAIA-UK-001 --invoice-date 2025-03-18 --country-code GB --taxable-base 1000 --iva-rate 0 --iva-amount 0 --total-amount 1000` created UK invoice `c239f130f4a48372`. `aeat --format json --profile laia-oss app ledger add --date 2025-03-18 --amount 1000 --direction INCOMING --description 'UK third-country export' --counterparty 'London Retail Ltd' --classification BUSINESS --taxable-base 1000 --iva-rate 0 --iva-amount 0 --iva-category export_third_country_zero_rated --source-jurisdiction GB --actor s102-persona --idempotency-key s102-laia-uk-export` created reviewed transaction `083baf602fec6e5262039af9646ab521e023570c0bdefa2a321aa557de0da633`; it retained the zero-rated export classification and source jurisdiction GB. `aeat --format json --profile laia-oss app modelo iva-wallet balance --as-of-year 2028` exited 0 with every balance zero and `lot_count=0`.
- Marc: `aeat --format json --profile marc-intracom app ledger invoice add --kind issued --counterparty-nif DE123456789 --counterparty-name 'Berlin Beratung GmbH' --invoice-number MARC-DE-001 --invoice-date 2025-03-19 --country-code DE --eu-iva-id DE123456789 --operation-type S --taxable-base 2500 --iva-rate 0 --iva-amount 0 --total-amount 2500` created invoice `8ecd76e91daa9da6`. M349 2025/1T work unit `71720a39afee6031385321d38df114f06ba03196cf2a835d5bb123200cfa9460` calculated draft `f97cbc49e62a5e4b8f85e6a49bd5e61cee329266f846719ca4729f726dbf2b16`, with one `operador` row DE / DE123456789 / Berlin Beratung GmbH / S / 2500.
- Marc: `aeat --format json --profile marc-intracom app ledger add --date 2025-06-20 --amount 600 --direction INCOMING --description 'EU intracom raw ledger supply Q2' --counterparty 'Munich raw client' --classification BUSINESS --taxable-base 600 --iva-rate 0 --iva-amount 0 --iva-category intra_community_supply --counterparty-eu-member-state de --actor s102-persona --idempotency-key s102-marc-de-raw-q2` created raw transaction `e4a45822245d3479cff77a91a36609eeee1f56aa5d9569f96692555c3eecba7a`. M349 2025/2T calculation exited 1 with `ERROR_MODELO_AGGREGATION_BINDING`, named this exact transaction and count, and suggested `aeat app ledger invoice add --help`; the raw-transaction guard is fail-closed and actionable. Marc's IVA wallet query also exited 0 with zero balance.
- Joan: the invalid EU IVA-ID `FR987654321` was rejected at the CLI boundary with `REFUSED_CLI_BOUNDARY` and an exact expected-format message. Retrying with `FR40303265045` created invoice `f90e0695fa4ccae3`. M349 2025/2T work unit `0c60df8f8684429146fa74ad7a045ae28acd2300574b144ef16885da74c506c8` calculated draft `0044afe7b2a6422396699a5ee69525e172d84722e1025fa08f4dce7d39ff5429`, with one FR / FR40303265045 / Lyon Commerce SARL / E / 4200 operator row; verify exited 0 and granted `verificado_completo` report `2de05af207f812ba9fe3279575d01c499d4151002bfd76c228bdaa4afd25e42c`.

## Outcome

Pending S103 consolidation; do not credit this plan row yet.

The 349 rich-invoice path, raw-ledger refusal, UK export classification, and empty IVA-wallet inspection are reachable, understandable, and local-only. The rerun found one MAJOR user-visible failure: after Modelo 369 saved the zero-valued draft with six explicit unresolved OSS-source advisories, `aeat --format json --profile laia-oss app modelo work verify --modelo 369 --year 2025 --period 1T --revision esquema-union --by s102-persona` exited 0 and granted `verificado_completo` report `d4063e7cce15cfc07c433457ce9e3dc29f1bbf90b6c2f5b7718d97bea0e391f0`. This permits export of an OSS return despite unavailable source data and is a silent-under-declaration route. S103 must consolidate it and add a corrective plan step before S102 can close.

## Notes

- Re-running Marc's existing 2025/1T calculation after adding a same-period raw intra-community transaction returned the existing draft unchanged. The fresh 2025/2T control was therefore used to prove the raw-ledger guard itself. Assess source-change revision invalidation while consolidating the M369 failure; it may be a separate evidence-revision concern.
- Exit-code summary: profile create retries and all valid persona operations exited 0; invalid French IVA-ID exited 2 with a specific remediation message; raw-only M349 2025/2T calculation exited 1 with an explicit, safe refusal.
