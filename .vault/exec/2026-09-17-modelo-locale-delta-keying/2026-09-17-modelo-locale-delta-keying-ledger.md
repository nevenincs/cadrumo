---
tags:
  - '#exec'
  - '#modelo-locale-delta-keying'
date: '2026-09-17'
modified: '2026-09-18'
body_schema: 'body-v2'
body_hash: 'sha256:c62d59f24a9aa5c7b93d099722b36430d7fab96860836bb246d3ef2645d93b6c'
related:
  - "[[2026-09-17-modelo-locale-delta-keying-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `modelo-locale-delta-keying` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
- `S01` `M` `src/cadrumo/domain/calculations/registry/modelo_localization.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_localization_continuity_tier_is_reached.py`
- `S01` `M` `dev/registry/tests/test_isolated_edition_staging.py`
- `S01` `verify:` `pytest test_localization_continuity_tier_is_reached test_isolated_edition_staging` -> `pass`
- `S02` `M` `src/cadrumo/domain/calculations/registry/static_inspection.py`
- `S02` `M` `src/cadrumo/application/modelo/workspace.py`
- `S02` `verify:` `pytest test_workspace test_workspace_models` -> `pass`
- `S12` `M` `dev/registry/compiler/loader_materialisation.py`
- `S12` `verify:` `pytest test_delta_minimality test_edition_delta_migration test_revision_label_inheritance test_isolated_edition_staging` -> `pass`
- `S03` `M` `dev/registry/compiler/loader.py`
- `S03` `M` `dev/locales/_registry_scanner.py`
- `S03` `A` `dev/locales/_casilla_keys.py`
- `S03` `M` `dev/locales/manager.py`
- `S03` `M` `dev/locales/_revision_drift.py`
- `S03` `verify:` `pytest dev/locales/tests/test_modelo_revision_locale_key_parity.py test_revision_drift_report.py test_modelo_schema_runtime_localization.py` -> `pass`
- `S04` `A` `dev/locales/modelo_casilla_catalogue.py`
- `S04` `M` `dev/locales/cli.py`
- `S04` `M` `dev/locales/_paths.py`
- `S04` `A` `dev/locales/tests/test_modelo_casilla_catalogue.py`
- `S04` `M` `src/cadrumo/domain/calculations/registry/modelo_localization.py`
- `S04` `verify:` `pytest dev/locales/tests/test_modelo_casilla_catalogue.py` -> `pass`
- `S05` `M` `dev/locales/tests/test_locale_translation_honesty.py`
- `S05` `D` `dev/locales/revision_label_restatement.py`
- `S05` `D` `dev/locales/casilla_label_derivation.py`
- `S05` `D` `dev/locales/translation_drift.py`
- `S05` `D` `dev/locales/tests/test_revision_label_restatement.py`
- `S05` `D` `dev/locales/tests/test_casilla_label_derivation.py`
- `S05` `D` `dev/locales/tests/test_translation_drift.py`
- `S05` `M` `dev/quality/metadata/import_load_targets.json`
- `S09` `M` `src/cadrumo/locales`
- `S09` `verify:` `dev.locales casilla-collapse --apply (post-write resolution diffs 0)` -> `pass`
- `S10` `M` `src/cadrumo/locales`
- `S10` `verify:` `dev.locales casilla-audit: derived_help 0, null_leaves 0` -> `pass`
- `S11` `M` `src/cadrumo/locales`
- `S11` `verify:` `dev.locales casilla-author placeholders.json (all changes attributed)` -> `pass`
- `S08` `A` `var/test-iter/wording_review/worklist.json`
- `S08` `by:` `sonnet-worklist`
- `S06` `M` `src/cadrumo/locales/es/modelo/schema`
- `S06` `verify:` `casilla-author spanish_review.json (443 ok, 73 fixed against official designs)` -> `pass`
- `S06` `by:` `sonnet-spanish-review`
- `S07` `M` `src/cadrumo/locales`
- `S07` `M` `dev/locales/tests/test_locale_translation_honesty.py`
- `S07` `A` `dev/locales/tests/test_shipped_casilla_catalogue.py`
- `S07` `verify:` `casilla-audit: stale 0, stranded 0, drift 0, placeholders 0` -> `pass`
- `S12` `M` `dev/locales/modelo_casilla_catalogue.py`
- `S12` `M` `dev/locales/fstring_registry.py`
- `S12` `M` `dev/locales/_signal.py`
- `S12` `M` `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`
- `S12` `M` `dev/locales/tests/test_audit.py`
- `S12` `M` `src/cadrumo/application/modelo/verification_cross_period.py`
- `S12` `M` `src/cadrumo/locales`
- `S12` `verify:` `pytest dev/locales` -> `pass`
- `S12` `A` `dev/locales/casilla_orthography.py`
- `S12` `A` `dev/locales/tests/test_casilla_orthography.py`
- `S12` `M` `dev/locales/cli.py`
- `S12` `M` `src/cadrumo/entrypoints/tui/profile/local_reader.py`
- `S12` `verify:` `pytest dev/locales/tests/test_casilla_orthography.py` -> `pass`
- `S12` `M` `src/cadrumo/domain/calculations/registry/modelo_localization.py`
- `S12` `M` `src/cadrumo/domain/calculations/registry/tests/test_localization_continuity_tier_is_reached.py`
- `S12` `M` `dev/locales/casilla_orthography.py`
- `S12` `verify:` `pytest test_localization_continuity_tier_is_reached` -> `pass`
- `S12` `M` `dev/locales/tests/test_casilla_orthography.py`
- `S12` `M` `dev/locales/tests/test_modelo_casilla_catalogue.py`
- `S12` `M` `src/cadrumo/_data/registry/authority`
- `S12` `verify:` `python -m dev.registry.pipeline publish-authority` -> `pass`
- `S12` `M` `dev/locales/tests/test_shipped_casilla_catalogue.py`
- `S12` `verify:` `pytest dev/locales/tests/test_locale_translation_honesty.py` -> `pass`
- `S16` `M` `src/cadrumo/locales`
- `S16` `M` `dev/locales/tests/test_locale_translation_honesty.py`
- `S16` `M` `dev/locales/modelo_casilla_catalogue.py`
- `S16` `verify:` `pytest dev/locales/tests/test_shipped_casilla_catalogue.py` -> `pass`
- `S13` `M` `dev/locales/modelo_casilla_catalogue.py`
- `S13` `M` `dev/locales/tests/test_shipped_casilla_catalogue.py`
- `S13` `M` `dev/locales/tests/test_modelo_casilla_catalogue.py`
- `S13` `M` `src/cadrumo/locales`
- `S13` `M` `src/cadrumo/_data/registry/authority`
- `S13` `verify:` `python -m dev.registry.pipeline publish-authority` -> `pass`
- `S14` `M` `dev/locales/casilla_orthography.py`
- `S14` `M` `dev/locales/cli.py`
- `S14` `M` `dev/locales/tests/test_casilla_orthography.py`
- `S14` `M` `src/cadrumo/locales`
- `S14` `verify:` `pytest dev/locales/tests/test_casilla_orthography.py` -> `pass`
- `S16` `M` `dev/locales/tests/test_modelo_casilla_catalogue.py`
- `S16` `M` `dev/locales/tests/test_shipped_casilla_catalogue.py`
- `S16` `verify:` `pytest dev/locales/tests/test_locale_translation_honesty.py` -> `pass`
- `S14` `verify:` `pytest dev/locales/tests` -> `pass`
- `S15` `M` `dev/locales/modelo_casilla_catalogue.py`
- `S15` `M` `dev/locales/tests/test_modelo_casilla_catalogue.py`
- `S15` `M` `src/cadrumo/locales`
- `S15` `verify:` `ruff check dev/locales` -> `pass`
- `S15` `M` `dev/locales/tests/test_shipped_casilla_catalogue.py`
- `S15` `verify:` `pytest dev/locales/tests/test_shipped_casilla_catalogue.py` -> `pass`
- `S16` `verify:` `pytest dev/locales/tests` -> `pass`
- `S17` `M` `dev/locales/modelo_casilla_catalogue.py`
- `S17` `M` `src/cadrumo/locales`
- `S17` `verify:` `python -m dev.locales casilla-author` -> `pass`
- `S17` `M` `dev/locales/tests/test_locale_translation_honesty.py`
- `S17` `verify:` `pytest dev/locales/tests/test_locale_translation_honesty.py` -> `pass`
- `S17` `verify:` `pytest dev/locales/tests` -> `pass`
- `S18` `M` `dev/locales/tests/test_shipped_casilla_catalogue.py`
- `S18` `verify:` `pytest dev/locales/tests/test_shipped_casilla_catalogue.py` -> `pass`
- `S17` `M` `dev/locales/casilla_orthography.py`
- `S17` `M` `dev/locales/tests/test_casilla_orthography.py`
- `S17` `verify:` `python -m dev.locales casilla-audit` -> `pass`
- `S17` `verify:` `pytest dev/locales/tests/test_shipped_casilla_catalogue.py` -> `pass`
- `S17` `M` `dev/locales/tests/test_modelo_casilla_catalogue.py`
- `S17` `M` `src/cadrumo/locales/hu.yml`
- `S17` `verify:` `python -m dev.locales status` -> `pass`

## Notes

- `S01` barrier changes 19 shipped M303 strings whose Spanish occurrence holds placeholder text; repaired by S11
- `S12` patched rows keep a separate text origin; minimality still judges them (131/2025 carries 8 no-op overrides)
- `S04` first real apply was interrupted by a Windows file lock and re-planned from a partial state, losing 24,861 resolved translations; restored from the verified rehearsal copy, and apply now stages, verifies and installs from a persistent pending directory
- `S07` identical cognates are classified in the honesty allowlist rather than stored as copies
- `S12` Serving no translation where Spanish resolves nowhere removed ~2300 genuine en help texts (ca/hu likewise) that lacked a Spanish source; Spanish help is being authored and the translations restored from 1b7a46e4cb^
- `S12` Edition-specific Spanish restored from official designs for Modelo 100 casillas 0002/0758/0854/1016 broke registry strict continuity; reverted to shared text, casilla-author now refuses such splits until the registry declares a continuity evolution
- `S12` Modelo 100 casilla 1908 stays shared and cut short: its official label names annex B.8/B.9/B.11 per edition, which needs a registry casilla continuity evolution before the locale text can diverge
- `S16` Casilla help was untranslated for 177 Spanish texts because the untranslated finding and the honesty gate read labels only; both now read help as well
- `S13` Revision labels are edition text: 19 per locale repeated one modelo's text across editions and were re-authored per period; the scaffold emits no per-edition key family beyond them
- `S14` The interface domains lost diacritics like the casilla surface did: 125 texts repaired across es/ca/hu, the check now reads every shipped surface with reviewed-word exemptions, and a gate covers it; placeholder and glossary patterns stay casilla-only because progress ellipses and the Hungarian -kent suffix are correct there
- `S16` A 300-label sample measured meaning-defect rates of en 5.0/ca 2.7/hu 4.0 per cent; the dominant class, translations dropping a box reference, amount or comparison the Spanish states, is now a check with cross-language equivalences, 268 repairs installed, one wrong year caught in Modelo 131, and a gate at zero
- `S16` One translation may render only one Spanish wording of a modelo: 72 keys carried another casilla's text, including a reused box number in Modelo 200 and the minorado/reducido pair, with 100 reviewer-recorded equivalences for abbreviations, typos, punctuation and synonyms
- `S14` Half-translated text is now a gated invariant at one untranslated Spanish word: 747 texts repaired (en 266, ca 190, hu 108) and the reviewers' kept terms recorded with reasons, covering Latin, official programme names, field identifiers and terms the product states in Spanish
- `S14` Third blind 300-label sample measured the meaning-defect rate at en 2.33, ca 1.67 and hu 1.67 per cent, against en 5.0/ca 2.7/hu 4.0 in the first sample and en 2.3/ca 2.3/hu 2.7 in the second; its 17 findings were installed (Abono read as a credit rather than a payment, retencion as withholding rather than deduction, El Hierro kept as a place name, I.A.E. restored, and six half-translated fragments)
- `S15` Segment drift is now measured: AEAT composes a label from segments joined by a dash, so a repeated Spanish segment must keep one rendering the way one meaning keeps one key. Box subtraction uses the same characters and is kept whole. 357 segments render more than one way (en 142, ca 70, hu 145); the case-only and apostrophe variants were normalised first, the rest are under review
- `S15` Segment drift is closed and gated: reviewers chose one canonical rendering for each of the 357 drifting segments, installing 5,028 stored values (ca 1,046, en 2,279, hu 1,703). The corrections reach meaning, not only style - Abono as a credit, retencion as withholding, a disposicion transitoria no longer cited as an article, El Hierro and Gipuzkoa kept as place names, and jovobeli restored to future periods. Cuota is the one recorded exception: it names the IVA amount, the recargo amount or a fee by the label it sits in
- `S16` shared_segments mirrors segment drift: one rendering standing for two Spanish segments hides a distinction the source draws. It found the Basque Concierto economico and the Navarrese Convenio economico sharing one English name, box 00418 wearing another box's label in three locales, Abono read as a payment again, and a levelling-reserve variant dropping its Aumentos. AEAT restates a segment by abbreviating it or dropping prepositions, so those wordings compare equal; 44 further pairs are recorded with the difference a reviewer saw
- `S17` The sentence break is now a composition separator too, read only between a word and a capital so that art. 12.2 LIS and pag. 3D stay whole; about five thousand more labels became checkable. It exposed Catalan accent losses the spell check had passed because the unaccented forms are English words (electronic, referencia, traves), Spanish left untranslated in Catalan and English, and shared renderings merging distinct concepts: Portal with Escalera, Otros acreedores with Otros pasivos, Otros deudores with Otros creditos, and the first, second and third legal representative under one Hungarian label. 754 stored values were repaired; accented renderings now win over more frequent unaccented ones
- `S17` Round two of segment canonicalisation is installed (en 388, hu 654, ca 67 values). Two regressions the reviewers introduced were caught by the existing gates and corrected: a generic Hungarian heading erased which of the three legal representatives a row names, and two rows lost the page reference of their official design while restoring Kifizetes for Abono. The representative rows now carry the ordinal in parentheses so the rendering holds no sentence break of its own. Drift is down to the one reviewed Catalan NIF case; NIF is classified as an acronym for English and Hungarian too
- `S17` Both segment families now read zero. The 76 legitimate shared renderings are recorded with the difference a reviewer saw: an official misspelling, an abbreviation AEAT writes out in another edition, the slash and word forms of one heading, two spellings of one province, and pairs like razon social with denominacion social or base liquidable with base imponible reducida that name one thing
- `S18` Two readers stand behind every stored text: the registry surfaces load the shipped shards through the product's own catalogue, and the dev module reads the authoring tree. The gate requires the same label and help from both for every casilla the product exposes in every locale, and treats a casilla the catalogue does not know as a finding rather than a skipped row, so the comparison cannot go quiet
- `S17` The fourth blind sample measured en 2.33, ca 2.33 and hu 3.67 per cent on labels the earlier rounds never touched, and named a class worth more than the sample: the Spanish word for a form box sat on the kept-Spanish list although the catalogue renders it as box, casella and rovat elsewhere, so 672 leaks were excused. All forms including the Hungarian suffixed ones were swept, 898 values installed, and a unit test proves the leftover is now reported. Auditing the kept list the same way showed ejercicio and tipo-declaracion are field identifiers of modelo 184 and correctly kept, while Innovacion tecnologica, Investigacion y desarrollo and the Catalan modelos were genuine leaks
- `S17` The half-translation check no longer blanks parentheses: one holding prose is read like the rest of the label, and only citations, form numbers and acronyms are skipped. That exposed 111 texts rewritten whole and six English rows that half-translated a spelled-out citation. Three further classes were swept catalogue-wide: the Spanish word for a form box (898 values), the revision phrase y siguientes (332), and the Hungarian form name, which the user settled as the legal term nyomtatvany (1,546). A collapse then folded 18 values back onto lineage keys, and the Catalan typo pair por ejemplo against por ejermplo is recorded in both families that see it
- `S17` A generic detector - a Spanish word the catalogue translates in the large majority of rows but keeps in a few - found 1,224 rows, of which 765 values were genuine leaks and the rest were proper names, citations and registry identifiers correctly kept. Widening the dropped-content check from labels to help then exposed a broken generator: 728 help rows across three locales stated no transaction number, read tax information about tax information, or had lost their LIVA citations. Repair peels, because collapsing a repaired value uncovers the edition keys beneath it, so the audit was re-run after every collapse until it read zero. Five checks were corrected rather than the data: parentheses are read by the half-translation check, help by the dropped-content check, Hungarian numerals inside compounds and as teen words, and one Hungarian label now composes the segments its Spanish composes
- `S17` Help is now judged by every check that judges a label. Widening translation drift to help exposed 600 lineages storing one meaning twice - 61 were the old template surviving beside correct text, 183 were one Catalan case split, and 356 were reviewer judgements - after which the collapse folded 1,019 values onto lineage keys. Widening copied, stale, stranded and shared translations then reported only eight further cases: seven equivalent Spanish wordings now recorded with the difference seen, and one genuine defect no earlier check could see, a Modelo 303 label carrying its own help text in all three locales and so losing the result line, the winding up of the non-customs warehousing regime and the State Administration share
- `S17` The Hungarian interface now uses the same legal terms as the casilla catalogue: 258 of 269 strings say rovat and nyomtatvany where they said casilla and modelo. Machine tokens were left exactly as they were - every brace placeholder, percent key and option name survives byte for byte across all 269 rows, and the Spanish words remain only where a user types them, in the aeat app modelo command examples, the modelo command group name in help, and a relation id. Placeholder parity and cross-surface coverage were re-verified after the install

