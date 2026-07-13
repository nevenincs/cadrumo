---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s89-catalogue-parity'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s89-catalogue-parity` audit: `S89 catalogue parity code review`

## Scope

- Independently review commit `2d976745ee5e95c29b1bd9945ecc6d0649d4a8f5` against the binding identity ADR, S89 plan step, S89 execution record, prior parity findings, and the complete four-catalogue diff.
- Verify exact change classification, localized meaning, call-site placeholder authority, scalar and key parity, retired-key removal, CADRUMO display restoration, preservation of machine and AEAT authority names, S90 ancestry, plan state, CLI provenance evidence, live help, scaffold and audit gates, and focused tests.
- Keep the shared dirty tree intact and create only this independent audit record.

## Findings

### s89-independent-cli-replay | low | Full byte-for-byte CLI replay exceeded the bounded review window

Two isolated replays from the exact parent tree invoked the real locale CLI for all recorded sets, removals, and canonicalization operations, but the catalogue-wide serializer did not complete within the 120-second and 300-second bounds. The temporary trees were removed and the shared checkout was never mutated. This limits independent proof of the no-hand-edit provenance claim, but it does not identify a catalogue defect: the recorded command inventory exhaustively matches the semantic diff, the refused Catalan shorthand is absent, every checkout hash matches the record, and the resulting YAML has the production serializer's normalized shape.

No critical, high, or medium findings were found. Verdict: **PASS**. S91 is not blocked by this review.

The exact parent-to-target semantic classification is 32 grounded sets, eight removals, 36 overlap reversals from `Cadrumo` to `CADRUMO`, and zero unexpected additions or changes. Set counts are English eight, Spanish one, Catalan six, and Hungarian seventeen; reversal counts are English ten, Spanish seven, Catalan thirteen, and Hungarian six. The eight removals are only `cli.config.bucket` and `cli.config.unlock` in all four catalogues. Independent inspection of every set against its error construction or direct `tr()` call confirms localized meaning and context. Static call-site placeholder sets match exactly for the IVA wallet, operator contract, source-kind, and MCP timeout messages; dynamic error-context producers supply the required names for authentication, modelo import, registry-manual, calculation, and review messages.

All four target catalogues contain the same 3,702 keys. Every leaf is an actual string, with zero nulls, zero booleans, and zero cross-locale placeholder mismatches. The retired bucket and unlock keys are absent. There is no title-case `Cadrumo` and no command-leading lowercase `cadrumo`; the only lowercase residues are the intended `cadrumo-vault/` storage prefix and, in Spanish and Hungarian, the intended `cadrumo_secret_store_backend` setting. Valid lowercase package, MCP, URI, environment, namespace, and historical identities remain intact, as do uppercase AEAT authority references and `AEAT_` machine names.

The recorded checkout SHA-256 values reproduce exactly: English `06C2550F40D46982ADBBBA713D3031B1BB54CEBBE1141C80340F749C6F70325B`, Spanish `2D97F3174AA18D65ECFBE5856A6D4FCF015606AFB54447610DE85BAFCD8E3A72`, Catalan `9A4BBE39A1DCA9B4B42175D5DAF1DAECC0E0BCEBD354F52E759BFEFDE30BC5CC`, and Hungarian `9F659FD5A312A7B1B1B5219A43B00285E3F3BD8CEEF81F90F6C03D2CEFE30F9B`. The S90 implementation and its independent audit are ancestors of S89. The plan closes S89 and S90 while retaining S05, S86, and downstream S62-S67 as open; S89 changes only its execution record, its plan row, and the four locale catalogues.

The locale scaffold check and locale audit both pass for all four catalogues. The focused i18n and locale suite passes 25 tests, including all three call-site placeholder checks; the complete parity module passes 27 tests. Live `aeat --language <locale> --help` passes in English, Spanish, Catalan, and Hungarian with `CADRUMO` product display, `AEAT` authority language, and `aeat` command spelling, and without `Cadrumo` or a legacy `cadrumo` command. The commit changes no tests and introduces no fake, mock, stub, patch, monkeypatch, skip, xfail, shadowed logic, or tautological assertion.

## Recommendations

- Allow validator S91 to proceed; this review found no blocking catalogue, authority, placeholder, or plan-state defect.
- Treat the bounded replay timeout as a performance and evidence limitation, not as grounds for hand-edit remediation absent contradictory provenance evidence.
- Keep S62-S67 open until their dedicated command-help, scaffold, and downstream validation work is independently completed.
