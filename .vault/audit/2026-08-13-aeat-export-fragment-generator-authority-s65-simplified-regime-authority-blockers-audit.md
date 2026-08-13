---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:9105881c3f4aed5714e53b0f0d6399cdec3194e2403148ee0c22e4dddac5f6c9'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-12-aeat-export-fragment-generator-authority-dp30302-projection-declaration-deficit-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace aeat-export-fragment-generator-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `aeat-export-fragment-generator-authority` audit: `S65 Simplified-Regime Authority Blockers`

## Scope

Audited whether the M303 simplified-regime calculation and value-arrival authority step can
be executed as one row. Triggered by attempting the step, not by a scheduled sweep. Anchors
were measured through `load_record_design_intermediate` against the five hash-pinned official
binaries; admissible homes were read from the live snapshot through `ValidatedRegistryAuthority`,
never from a directory listing.

## Findings

### dp30302-semantic-field-matrix | low | The five-epoch matrix reproduces the deficit census and corrects two of its constants

Measured DP30302 field populations per epoch, as total / agrícola / no agrícola / simplified /
numbered / constant / reserve / producer: 2023 is 153/20/114/134/12/5/1/1; 2024-early is
153/20/110/130/12/5/5/1; 2024-late is 163/24/116/140/12/5/5/1; 2025 is 166/20/122/142/12/5/6/1;
2026 is 166/20/122/142/12/5/6/1. The simplified column reproduces the earlier deficit audit's
134, 130, 140, 142 and 142 exactly.

Two constants in that earlier audit are corrected. Its "122 non-agricultural anchors across two
slots" holds only for 2025 and 2026; 2023 carries 114, 2024-early 110 and 2024-late 116. Its
"ten agricultural fields per slot" holds for four epochs, but 2024-late carries twelve. There
are 87 distinct field semantics across the five epochs, and three descriptions repeat eight
times per epoch (the Módulo Mesas capacidad, mesas and días trio, across four tariff tiers and
two slots), so a declaration schema needs a sub-index axis rather than four ad-hoc endpoints.

### iae-epigrafe-cannot-key-the-orden | critical | A declared identity endpoint is insufficient, not merely incomplete, and it silently selects the wrong regulatory values

The DP30302 design declares, beside the four-character IAE epígrafe, a one-character field
described as an auxiliary activity indicator for epígrafes 691.9 and 722. It is load-bearing.
Verified directly against the bundled official Orden text: IAE 722 resolves to two distinct
Orden activities, "Transporte de mercancías por carretera, excepto residuos" carrying cuota
devengada anual per unit of 4.149,99 and 388,55 with a 5 per cent ingreso a cuenta, and
"Transporte de residuos por carretera" carrying 1.948,64 and 181,58 with 1 per cent. The cuota
mínima differs by a factor of ten. IAE 691.9 likewise resolves to two activities.

The typed activity projection reference declares only the IAE epígrafe for the non-agricultural
cohort, so the discriminator has no endpoint at all. Any declaration fan-out keyed on the
epígrafe alone therefore resolves four activities to the wrong regulatory values without
refusing. This is the restrictive-provision-as-default shape the project rules name: it produces
valid output, no refusal and no signal, in both the under- and over-declaring directions.

This finding is new. The earlier deficit audit did not record it, and it changes the contract of
the step that authors the declarations: the discriminator must reach the identity endpoint
before any fan-out is authored, or the fan-out bakes in a mis-keying.

### annual-orden-authority-carries-one-cohort | critical | Three of the eight regulatory axes the official calculation needs are absent from the compiled authority

Read from the loaded snapshot, every one of the five Orden projections carries 49 activities,
all of kind non-agricultural, and exactly one fact identity across the whole authority. Zero
agricultural activities exist. The compiler hardcodes the non-agricultural kind and the single
fact identity, and the annual-Orden HTML reader hard-refuses any annex that is not ANEXO II.

The bundled corpus does carry what is missing, verified present in the bundled Orden: the
agricultural índices in ANEXO I, twenty rows; the porcentaje de ingreso a cuenta in the normas
comunes, a per-IAE table of forty-seven rows; the índices correctores de temporada, at 1,50 for
sixty days or fewer, 1,35 for sixty-one to one hundred twenty, and 1,25 for one hundred
twenty-one to one hundred eighty; and the one per cent cuotas soportadas de difícil
justificación. None is extracted. The agricultural porcentaje and the two-digit agricultural
código taxonomy have no located source at all.

The compiled authority can therefore supply module coefficient, cuota mínima percentage and IAE
identity, and nothing else the calculation needs. The step assumed this extraction already done.

### two-mechanisms-not-one | high | The step presupposes an architectural ruling nobody has made

The step orders the extension of "the one existing registry calculation mechanism". There are
two. The formula runtime carries simplified-regime ops computing over casilla leaves; the
projection module projects filing rows to record slots. The casilla channel is structurally
single-activity: the loaded revision's simplified casilla set is exactly ten entries, the seven
módulos unidades plus the orden id, the cuota devengada and the cuota derivada, with no cohort
or slot axis. Extending that over filing rows spanning up to twelve activities, two cohorts and
three records replaces the input channel rather than extending it, and breaks the registry TOML
formula-op contract consuming those casillas. Which channel is canonical is a ruling the step
presupposes rather than makes.

### deletions-are-downstream-of-the-replacement | high | Landing the ordered deletions first would blank fourteen endpoints per epoch

The generic off-form result is the only value source for the non-agricultural módulo importe
anchor. It is referenced by the projection-ref member, the filing-row model, three test modules,
and all five revisions' projection-endpoint declarations, where it backs fourteen of the
twenty-eight declared module endpoints each. Deleting it before the computed units-times-
coefficient path exists blanks those fourteen endpoints per epoch. The deletion is correct and
strictly downstream: it must be co-committed with the replacement value path, never ahead of it.

### tooling-defect-observed | low | Semantic code search crashes on binary corpus results

Semantic code search over IVA concepts crashes client-side with a Unicode decode error whenever
a bundled binary PDF ranks into the result set, which it reliably does for IVA queries. The JSON
output mode is unaffected and is the workaround. Recorded because a crashing discovery tool
reads as a down service, and a down service refuses the coding work under the standing mandate.

## Recommendations

Retire the row and re-carry it without loss as six rows, sequenced so that each is independently
verifiable: persist the five-epoch matrix as a gated artefact; extend the annual Orden authority
to the agricultural annex and the three missing normas comunes axes; rule on and collapse the two
mechanisms to one; add the auxiliary discriminator to the activity identity endpoint; build the
typed per-activity result and thread it through the filing facts and producer snapshot; and land
the ordered deletions co-committed with the replacement value path.

The scope-narrowing guard applies and is satisfied: the six rows account for all five of the
retired row's deliverables plus the matrix it was to review, and exclude nothing the standing
goal asks for. The denominator moves because the work was re-carried, never because it was
reduced.

The discriminator finding must land before the declaration fan-out is authored. That ordering is
the finding's whole point, and the sequence above places it accordingly.

## Context

S65 was dispatched as written and returned a measured refusal rather than a narrowed delivery. Every claim below was independently re-verified by the plan lead against HEAD before the row was re-carried; none is reviewer inventory taken at face value.

The step bundles five independently-large bodies of work, two of which are blocked on regulatory extraction that does not exist in the tree. The row is retired and re-carried without loss, following the precedent this plan already set when S19 became S67 through S71: the carrier changed, the scope did not.
