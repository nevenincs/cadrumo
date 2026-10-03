# Terminology concept corpus

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-205` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope and method

This reference-data chunk contains 166 TOML concept fragments in one directory, totaling 266,021 bytes. I read 18 complete, stratified samples (39,758 bytes): core concepts (`aeat`, `barrido-rag`, `binding`, `casilla`, `fichero-boe`, `irpf`); three VAT regimes; four filing forms (036, 100, 200, 303); two period codes; two topic stubs; and `work-unit`. The original sampling pass estimated roughly 10,000 tokens from bytes. A subsequent coordinator measurement establishes a conservative upper bound of **10,436 o200k_base tokens**, below the 24,000-token ceiling: it measures the 14 specifically identified samples and the largest possible two period and two topic files. The original notes did not identify those four stubs exactly, so this is an upper bound rather than an exact sample count; see the [sample-bound audit](../evidence/terminology-sample-bound.json). All 166 files were parsed as TOML with Python’s standard library for inventory metadata, but only the named samples received semantic reading. Syntax parsing does not validate translations, tax meaning, consumer behavior, or current law.

## What the corpus provides

Each fragment is structured terminology data: a concept identifier, domain and lifecycle, optional relationships and legal/domain references, followed by localized summaries, definitions, source citations, and preferred/admitted/forbidden terms. The corpus covers models, periods, VAT regimes, filing concepts, internal workflow terms, and other tax vocabulary. Inventory metadata counts 75 `modelo-*` files, 25 `iva-*`, 21 `periodo-*`, 14 `tema-*`, and 31 other names. Parsed `concept.domain` values are 74 `modelo`, 24 `regimen`, 21 `periodo`, 46 `concepto`, and one `casilla-namespace`. Lifecycle labels are 49 approved, 87 draft, 11 deprecated, and 19 retired; these are editorial states, not proof that a runtime loader filters or prioritizes entries.

The localized fields can support glossary or terminology retrieval and explain product concepts in Spanish, English, Catalan, and Hungarian. A sample approved entry defines the AEAT, cites the agency and a legal source, and distinguishes the authority from the application; its prose says taxpayers file with AEAT and that the application never files on their behalf (aeat.toml (`src/cadrumo/_data/terminology/concepts/aeat.toml`)). A separate entry describes generating a fixed-width BOE record file for a person to upload themselves (fichero-boe.toml (`src/cadrumo/_data/terminology/concepts/fichero-boe.toml`)). These are claims and intended product boundaries recorded in handbook text, not verification of the filing/export implementation.

Concepts are related rather than just isolated translations. `irpf` links to Renta and specific model concepts and distinguishes personal income tax from corporate and non-resident taxes; Modelo 100 and 303 entries describe annual IRPF and periodic general-regime VAT returns, while Modelo 036 covers census registration, changes, and deregistration (irpf.toml (`src/cadrumo/_data/terminology/concepts/irpf.toml`), modelo-100.toml (`src/cadrumo/_data/terminology/concepts/modelo-100.toml`), modelo-303.toml (`src/cadrumo/_data/terminology/concepts/modelo-303.toml`), modelo-036.toml (`src/cadrumo/_data/terminology/concepts/modelo-036.toml`)). VAT regime entries distinguish domestic reverse charge and intra-community acquisition from a standard-rate domestic concept. That standard-rate entry is retired and points to `iva-domestic-general` as its replacement, while its Spanish text is an explicit uncured-draft placeholder (iva-domestic-reverse-charge.toml (`src/cadrumo/_data/terminology/concepts/iva-domestic-reverse-charge.toml`), iva-intra-community-acquisition-reverse-charge.toml (`src/cadrumo/_data/terminology/concepts/iva-intra-community-acquisition-reverse-charge.toml`), iva-domestic-general-21.toml (`src/cadrumo/_data/terminology/concepts/iva-domestic-general-21.toml`)). Lifecycle and replacement metadata therefore matter to any display or retrieval consumer.

Some concepts document internal implementation vocabulary rather than taxpayer-facing terms. `binding` describes a registry rule that maps a ledger or profile datum to a form box and explicitly marks itself deprecated and outside the public glossary; `work-unit` describes a model/year/period/revision calculation handle and similarly characterizes itself as an internal development-RAG concept (binding.toml (`src/cadrumo/_data/terminology/concepts/binding.toml`), work-unit.toml (`src/cadrumo/_data/terminology/concepts/work-unit.toml`)). `barrido-rag` describes a build-time process that queries a resident RAG service and stores reviewable targets so CI need not run live retrieval; it too is deprecated (barrido-rag.toml (`src/cadrumo/_data/terminology/concepts/barrido-rag.toml`)). These entries expose the vocabulary and intended separation of editorial/build-time concepts from live product behavior, but this corpus cannot establish that pipeline.

## Provenance, coverage, and quality

Metadata often records authority classes and citations such as AEAT, BOE, or `other`, plus `legal_refs`, `domain_refs`, creation/update dates, related concepts, and replacement targets. Parsing found legal references on 46 entries, domain references on 135, related links on 49, and replacement pointers on 19. These are author-provided provenance pointers, not independently checked authority or evidence that cited law is applicable today. This report performs no external legal validation.

Locale table presence is broad but completeness is not: all 166 files contain Spanish language data, and 165 contain each of English, Catalan, and Hungarian. Only 60 entries in each locale have a `definition`; many others have just a short description. In the Spanish data, 106 entries lack a definition, and the sampled period, topic, and retired-rate entries include `(sin curar) draft pendiente de definicion` placeholders. The language tables also include 108 Spanish term rows, 27 English, 3 Catalan, and 3 Hungarian term rows. These counts show that locale presence does not mean equivalent depth or synonym coverage. Whether that is a defect depends on which locales and fields the consumers promise; any user-facing glossary or multilingual RAG should honor lifecycle status, avoid placeholder text, and have a clear fallback policy.

The shared header says the strict `dev.docs.terminology_handbook` loader compiles fragments into frozen `ConceptRecord` objects, that prose is hand-edited, and that `narrower` is derived from `broader` rather than authored here. Those are corpus comments about intended tooling, not inspected loader guarantees. The sampled metadata’s mixed draft/deprecated/retired states and unequal translations make lifecycle-aware filtering, reference integrity checks, and locale completeness checks important verification points. No tests or consumer code are part of this chunk; successful TOML parsing alone cannot show those checks run.

## Dependencies and follow-up

Synthesis should connect this data to the terminology handbook loader and CLI, any compiled glossary or search index, the build-time RAG sweep, and UI locale fallbacks. It should confirm how non-approved concepts and placeholder strings are filtered, how `broader`/`narrower`, `related`, and `replaced_by` references are validated, and whether source/date metadata is surfaced with appropriate freshness limits.

## Complete assigned-file inventory

- `src/cadrumo/_data/terminology/concepts/aeat.toml` — 2,690 bytes
- `src/cadrumo/_data/terminology/concepts/autoliquidacion.toml` — 2,300 bytes
- `src/cadrumo/_data/terminology/concepts/barrido-rag.toml` — 2,938 bytes
- `src/cadrumo/_data/terminology/concepts/binding.toml` — 2,904 bytes
- `src/cadrumo/_data/terminology/concepts/borrador-vs-presentado.toml` — 2,398 bytes
- `src/cadrumo/_data/terminology/concepts/borrador.toml` — 2,363 bytes
- `src/cadrumo/_data/terminology/concepts/casilla.toml` — 4,032 bytes
- `src/cadrumo/_data/terminology/concepts/censo.toml` — 2,500 bytes
- `src/cadrumo/_data/terminology/concepts/clases-registro-busqueda.toml` — 2,845 bytes
- `src/cadrumo/_data/terminology/concepts/declaracion.toml` — 2,659 bytes
- `src/cadrumo/_data/terminology/concepts/depuracion-licencia.toml` — 3,716 bytes
- `src/cadrumo/_data/terminology/concepts/expediente.toml` — 2,389 bytes
- `src/cadrumo/_data/terminology/concepts/fichero-boe.toml` — 3,159 bytes
- `src/cadrumo/_data/terminology/concepts/gancho-preprocesado.toml` — 3,516 bytes
- `src/cadrumo/_data/terminology/concepts/irpf.toml` — 4,103 bytes
- `src/cadrumo/_data/terminology/concepts/iva-domestic-exempt.toml` — 852 bytes
- `src/cadrumo/_data/terminology/concepts/iva-domestic-general-21.toml` — 950 bytes
- `src/cadrumo/_data/terminology/concepts/iva-domestic-general.toml` — 1,110 bytes
- `src/cadrumo/_data/terminology/concepts/iva-domestic-not-subject.toml` — 890 bytes
- `src/cadrumo/_data/terminology/concepts/iva-domestic-reduced-10.toml` — 951 bytes
- `src/cadrumo/_data/terminology/concepts/iva-domestic-reduced.toml` — 1,093 bytes
- `src/cadrumo/_data/terminology/concepts/iva-domestic-reverse-charge.toml` — 2,372 bytes
- `src/cadrumo/_data/terminology/concepts/iva-domestic-super-reduced-4.toml` — 986 bytes
- `src/cadrumo/_data/terminology/concepts/iva-domestic-super-reduced.toml` — 1,197 bytes
- `src/cadrumo/_data/terminology/concepts/iva-domestic-zero.toml` — 885 bytes
- `src/cadrumo/_data/terminology/concepts/iva-erroneous-invoice.toml` — 887 bytes
- `src/cadrumo/_data/terminology/concepts/iva-export-assimilated-zero-rated.toml` — 932 bytes
- `src/cadrumo/_data/terminology/concepts/iva-export-third-country-zero-rated.toml` — 935 bytes
- `src/cadrumo/_data/terminology/concepts/iva-import-third-country.toml` — 936 bytes
- `src/cadrumo/_data/terminology/concepts/iva-intra-community-acquisition-reverse-charge.toml` — 998 bytes
- `src/cadrumo/_data/terminology/concepts/iva-intra-community-service-acquisition-reverse-charge.toml` — 1,044 bytes
- `src/cadrumo/_data/terminology/concepts/iva-intra-community-service-supply.toml` — 903 bytes
- `src/cadrumo/_data/terminology/concepts/iva-intra-community-supply.toml` — 879 bytes
- `src/cadrumo/_data/terminology/concepts/iva-intra-community-triangulation.toml` — 899 bytes
- `src/cadrumo/_data/terminology/concepts/iva-operacion-no-sujeta.toml` — 863 bytes
- `src/cadrumo/_data/terminology/concepts/iva-reagp-compensation.toml` — 646 bytes
- `src/cadrumo/_data/terminology/concepts/iva-recargo-equivalencia.toml` — 2,496 bytes
- `src/cadrumo/_data/terminology/concepts/iva-regimen-simplificado.toml` — 2,289 bytes
- `src/cadrumo/_data/terminology/concepts/iva-unknown.toml` — 882 bytes
- `src/cadrumo/_data/terminology/concepts/iva.toml` — 3,907 bytes
- `src/cadrumo/_data/terminology/concepts/justificante.toml` — 2,493 bytes
- `src/cadrumo/_data/terminology/concepts/ledger.toml` — 2,713 bytes
- `src/cadrumo/_data/terminology/concepts/manual-terminologia.toml` — 2,939 bytes
- `src/cadrumo/_data/terminology/concepts/mapa-relevancia.toml` — 3,164 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-036.toml` — 2,258 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-037.toml` — 1,128 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-038.toml` — 1,041 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-100.toml` — 2,024 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-111.toml` — 2,261 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-115.toml` — 2,278 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-117.toml` — 1,092 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-121.toml` — 1,051 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-122.toml` — 1,014 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-123.toml` — 2,204 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-126.toml` — 977 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-128.toml` — 1,050 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-130.toml` — 2,303 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-131.toml` — 2,117 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-136.toml` — 977 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-140.toml` — 959 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-143.toml` — 1,063 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-145.toml` — 1,003 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-151.toml` — 1,080 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-156.toml` — 1,059 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-165.toml` — 1,005 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-179.toml` — 1,043 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-180.toml` — 2,406 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-181.toml` — 1,042 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-182.toml` — 956 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-184.toml` — 2,248 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-185.toml` — 1,014 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-186.toml` — 933 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-187.toml` — 1,044 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-188.toml` — 1,010 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-189.toml` — 971 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-190.toml` — 2,458 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-193.toml` — 2,347 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-194.toml` — 1,040 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-200.toml` — 2,202 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-202.toml` — 2,189 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-210.toml` — 2,213 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-216.toml` — 1,042 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-220.toml` — 981 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-222.toml` — 995 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-231.toml` — 880 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-232.toml` — 2,228 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-233.toml` — 1,066 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-234.toml` — 950 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-238.toml` — 929 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-270.toml` — 1,033 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-280.toml` — 952 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-289.toml` — 1,065 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-296.toml` — 1,045 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-303.toml` — 2,275 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-308.toml` — 1,032 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-309.toml` — 2,120 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-322.toml` — 1,924 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-341.toml` — 1,086 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-345.toml` — 1,049 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-347.toml` — 2,097 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-349.toml` — 2,261 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-353.toml` — 2,059 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-360.toml` — 1,104 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-361.toml` — 1,090 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-369.toml` — 2,134 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-379.toml` — 944 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-380.toml` — 969 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-390.toml` — 2,123 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-490.toml` — 927 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-576.toml` — 965 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-592.toml` — 1,017 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-604.toml` — 923 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-714.toml` — 964 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-720.toml` — 2,315 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-721.toml` — 948 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-763.toml` — 1,017 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-840.toml` — 1,038 bytes
- `src/cadrumo/_data/terminology/concepts/modelo-848.toml` — 1,019 bytes
- `src/cadrumo/_data/terminology/concepts/modelo.toml` — 4,205 bytes
- `src/cadrumo/_data/terminology/concepts/nif.toml` — 4,272 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-01.toml` — 832 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-02.toml` — 835 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-03.toml` — 831 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-04.toml` — 831 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-05.toml` — 826 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-06.toml` — 828 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-07.toml` — 830 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-08.toml` — 833 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-09.toml` — 840 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-0a.toml` — 819 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-10.toml` — 835 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-11.toml` — 837 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-12.toml` — 837 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-1p.toml` — 861 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-1t.toml` — 824 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-2p.toml` — 864 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-2t.toml` — 827 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-3p.toml` — 864 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-3t.toml` — 827 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-4p.toml` — 864 bytes
- `src/cadrumo/_data/terminology/concepts/periodo-4t.toml` — 827 bytes
- `src/cadrumo/_data/terminology/concepts/preflight.toml` — 3,238 bytes
- `src/cadrumo/_data/terminology/concepts/prorrata-especial.toml` — 3,177 bytes
- `src/cadrumo/_data/terminology/concepts/prorrata.toml` — 4,652 bytes
- `src/cadrumo/_data/terminology/concepts/proyeccion-busqueda.toml` — 3,138 bytes
- `src/cadrumo/_data/terminology/concepts/recargo-equivalencia.toml` — 2,579 bytes
- `src/cadrumo/_data/terminology/concepts/renta.toml` — 3,658 bytes
- `src/cadrumo/_data/terminology/concepts/revision.toml` — 3,309 bytes
- `src/cadrumo/_data/terminology/concepts/sede-electronica.toml` — 2,469 bytes
- `src/cadrumo/_data/terminology/concepts/tema-authentication.toml` — 985 bytes
- `src/cadrumo/_data/terminology/concepts/tema-calendar.toml` — 947 bytes
- `src/cadrumo/_data/terminology/concepts/tema-casilla.toml` — 922 bytes
- `src/cadrumo/_data/terminology/concepts/tema-formats.toml` — 926 bytes
- `src/cadrumo/_data/terminology/concepts/tema-irpf-regime.toml` — 918 bytes
- `src/cadrumo/_data/terminology/concepts/tema-iva-regime.toml` — 875 bytes
- `src/cadrumo/_data/terminology/concepts/tema-modelos.toml` — 898 bytes
- `src/cadrumo/_data/terminology/concepts/tema-pago-fraccionado.toml` — 948 bytes
- `src/cadrumo/_data/terminology/concepts/tema-profile.toml` — 940 bytes
- `src/cadrumo/_data/terminology/concepts/tema-providers.toml` — 953 bytes
- `src/cadrumo/_data/terminology/concepts/tema-recargo-extemporaneo.toml` — 976 bytes
- `src/cadrumo/_data/terminology/concepts/tema-regimens.toml` — 928 bytes
- `src/cadrumo/_data/terminology/concepts/tema-sii.toml` — 937 bytes
- `src/cadrumo/_data/terminology/concepts/tema-verifactu.toml` — 958 bytes
- `src/cadrumo/_data/terminology/concepts/verificado-completo.toml` — 3,540 bytes
- `src/cadrumo/_data/terminology/concepts/vies.toml` — 3,663 bytes
- `src/cadrumo/_data/terminology/concepts/work-unit.toml` — 3,209 bytes
<!-- /preserved:article -->
