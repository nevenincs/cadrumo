---
tags:
  - '#exec'
  - '#corporate-tax-runtime'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S01'
related:
  - "[[2026-05-26-corporate-tax-runtime-plan]]"
  - "[[2026-05-21-corporate-entity-calculation-adr]]"
---

# `corporate-tax-runtime` `P01.S01`

Registered the scoped legal entry `ley-27-2014:art-40-3` in the IS legal catalogue, grounded against the local BOE corpus excerpt of Article 40 of Ley 27/2014. The entry carries the verbatim 6.000.000 EUR INCN-threshold rule that fixes the Modelo 202 Art. 40.3 modality as mandatory above the threshold and optional below it. This is the legal ground the upcoming Modelo 202 modality applicability gate (`P02.S07`) cites and resolves against the registry.

- Modified: `src/aeat/_data/registry/aeat/legal/is.toml`
- Modified: `.vault/plan/2026-05-26-corporate-tax-runtime-plan.md` (Step closed via `vault plan step check`)

## Description

The new legal table `[legal."ley-27-2014:art-40-3"]` mirrors the surrounding LIS article entries on the same catalogue: `evidence_tier = "legal_authority"`, `authority = "boe"`, `kind = "ley"`, `document_id = "BOE-A-2014-12328"`, `corpus_ref = "corpus/normatives/html/ley-27-2014-art-40.html#a40"`, `permalink` to the BOE consolidated act anchor `#a40`, `published_at = 2014-11-28`, `effective_from = 2015-01-01`, and `review_status = "reviewed"`. The `article` field is set to `40.3` to disambiguate the apartado-scoped entry from the existing article-level `ley-27-2014:art-40` entry; both entries share the same corpus file and BOE anchor because the consolidated BOE text does not assign a sub-anchor to individual apartados within an article.

The `required_text` list carries five verbatim substrings drawn from the apartado-3 paragraphs of the BOE corpus: the opt-in clause for the base-imponible modality, the obligatory-modality clause, the 6.000.000 EUR INCN-threshold phrasing, the 12-month look-back-window phrasing, and the five-sevenths-of-the-tipo-de-gravamen rate phrasing. Each substring was confirmed to resolve through the registry's text-normalisation surface against the on-disk corpus excerpt, so the registry's evidence validator will accept the entry under live validation.

The plan Step row `P01.S01` was closed via `vault plan step check ... S01`, the canonical CLI surface; the checkbox glyph was not edited by hand.

The TOML edit was authored against `HEAD = 18d9d2994`. By the time the working-tree commit was attempted, a parallel agent had already landed an identical `[legal."ley-27-2014:art-40-3"]` block in commit `a67e07b10` (whose commit subject describes a synthetic-data guard but whose `is.toml` diff is the same Art. 40.3 entry verbatim). My authored edit was therefore deduplicated to a no-op against the working tree, no new application-code commit is produced by this Step, and the persisted state of the registry is already in the intended shape. The Step Record and the plan checkbox flip are the only artefacts this Step contributes.

## Tests

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_text.py` → 126 passed, real-behaviour, no mocks / skips / xfail.

`uv run --no-sync pytest src/aeat/application/overview/test_applicability.py::test_seed_legal_refs_resolve_against_the_registry` → 1 passed; the new key resolves cleanly through `ValidatedRegistryAuthority` and is admissible as a `legal_refs` target for downstream applicability conditions.

A direct `ValidatedRegistryAuthority.load(...).catalogues.legal['ley-27-2014:art-40-3']` probe returned the populated entry (`corpus_ref` resolved, `article = 40.3`, `document_id = BOE-A-2014-12328`, five `required_text` entries).

The wider `pytest src/aeat/domain/calculations/registry/` run reported 1841 passed, 19 failed, 1 deselected; the 19 failures are owned by the active parallel campaigns on Modelo 190 semantic-role cardinality, Modelo 180 / cross-revision relation closure, audit-cluster public-API boundaries, and loader-directory-mode coverage. None of the failures touch the legal catalogue, the IS TOML surface, or the Art. 40 corpus parser, and none are causally connected to this Step. The single deselected test is the M190 cardinality regression already in foreign-flight rebase.

The legal catalogue verification gate (the `test_seed_legal_refs_resolve_against_the_registry` style guard) extends correctly to the new key without code changes, because the resolver consumes the TOML data directly and the new key sits inside the bundled registry tree.
