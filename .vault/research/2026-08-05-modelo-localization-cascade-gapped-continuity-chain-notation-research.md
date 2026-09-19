---
tags:
  - '#research'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:54db6facc4f102b63df73c585699a2a4b335bac220fdcf810770d2bec778dbd6'
related:
  - "[[2026-08-04-modelo-localization-cascade-adr]]"
---
# `modelo-localization-cascade` research: `gapped continuity chain notation`

Modelo 100 casilla `1082` ("Otras deducciones", role `irpf_deduccion_la_rioja_otras`) is
present in the 2020 and 2024 revisions with an identical surface and genuinely absent from
2021-2023. The continuity contract says `retired` ends a chain permanently and a later
concept needs a new grounded `continuidad_id`, while the evolution taxonomy has no
suspended/resumed kind - so an intermittent concept must be modelled as two disconnected
chains, which duplicates the localization cascade's per-concept translation for exactly the
boxes that share wording across the gap. This research censused the class to size the cost
and weighed the three candidate notations against it.

The census found the class is a single casilla registry-wide, and that one of the two
structural dimensions the question was framed around is already solved by the existing
schema. It also found the contract itself unenforced: the validator accepted a retired chain
that reappeared later, so "retired ends a chain permanently" was prose only. That defect is
closed. What remains for the ADR is whether a chain may ever legally resume.

## Findings

### The intermittent-concept class is one casilla registry-wide

A census over the compiled registry - all 73 modelos loaded through `load_registry_tree`,
never a TOML directory listing - found exactly **one** gap run whose boundary surface is
stable.

A gap run is a pair of consecutive occurrences of one casilla id in a modelo's
validity-ordered revisions with at least one revision skipped between them. "Stable
boundary" means the last occurrence before the gap and the first after it agree on
normalized label, section path, `semantic_role`, and `data_type` - the `1082` shape.

| measure | count |
| --- | --- |
| modelos in the registry | 73 |
| modelos with 3+ revisions (the minimum a gap needs) | 4 |
| casilla ids present in more than one revision | 2193 |
| gap runs with a **stable** boundary surface | **1** |
| gap runs with a drifted boundary surface | 55 |
| same-concept reappearance under a different id after a gap | 5 |
| currently-stamped `continuidad_id` chains that are gapped | **0** |

The single stable case is `100/1082`, present 2020 and 2024, absent 2021-2023, role
`irpf_deduccion_la_rioja_otras`, section `resultados/deduccion_autonomica_res/la_rioja_res`.
It carries no `continuidad_id` today.

Only M100 can exhibit the class at all. It is the only modelo with per-year revisions and
more than two of them; M131 (4 revisions) and M202 (3) produced no gap runs, and M369's
three revisions are variant schemas sharing one validity window rather than a temporal
sequence. Every other multi-revision modelo uses `<year>-y-siguientes` windows, which cannot
gap.

### The 55 drifted gap runs are id reuse, not intermittent concepts

All 55 are M100 numeric ids carrying unrelated concepts in different years. `0700` is
"resultado a ingresar o devolver" in some revisions and an Anexo A AEIP flag in others;
`0356` moves between a premios section and an elemento-patrimonial section. The AEIP event
slots (`0757`, `0760`-`0787`, `0795`, `0798`) are a positional block whose occupant event
changes as programmes enter and leave the acontecimiento list.

These are renumbering and slot reuse. They need `repurposed` or separate chains under the
existing taxonomy and are untouched by the notation question.

### The different-id dimension is already solved by the schema

The looser variant - the same concept reappearing under a **different** id after a gap -
returned five cases, the clearest being `irpf_deduccion_la_rioja_vehiculos_electricos`
("Por adquisición de vehículos eléctricos nuevos"), carried by id `1077` in 2020-2023,
absent in 2024, and carried by id `0255` in 2025.

This needs no new notation. `continuidad_id` lives on the casilla and is read independently
of `casilla.id`, so a single chain already spans an id change - that is what the continuity
surface is for. What the five cases share with `1082` is only the gap. The id-change
dimension is therefore not part of the option space, and a `successor_of` link would be
solving a problem the schema does not have.

The remaining four are RIC dotación year-slot reindexing (`0733`/`0742`/`0746`) and AEIP
slot movement - the same positional-block reuse as above.

### The "retired ends a chain permanently" contract was unenforced

Measured, not reasoned. A probe built a three-revision M100 with a chain present in 2022,
retired 2022-to-2023, and present again in 2024 under the same `continuidad_id`, every
revision strict. The strict validator returned **zero** failures. A positive control - the
same chain disappearing with no retired declaration - returned one failure, proving the
validator ran and the fixture shape reached it.

The cause is scope. `_validate_strict_retired_continuity_surfaces` walks only adjacent
revision pairs, and `_validate_strict_continuity_evolution_references` checks a `retired`
evolution against its own `from_revision`/`to_revision` pair alone: together they confirm
the chain left, never that it stayed gone. Nothing read chain presence across the full
revision ordering.

A second, quieter shape sat alongside it. Both retirement checks require at least one
revision of the pair to be strict, and M100's 2020 and 2021 revisions are both advisory - so
a chain stamped on `1082` in 2020 and 2024 would have raised nothing at all: no retirement
requirement at the disappearance boundary, and no objection at the resumption.

This is closed. Commit `ea7026b1fb` adds a contiguity policy that reads chain presence over
the validity-ordered revisions and refuses a non-contiguous chain, extracted to
`_validate_cross_revision_contiguity.py` in commit `98ba148ca2`. It fires when any revision
in the chain's span is strict, so it catches the advisory-boundary shape the retirement gate
misses, and it excludes revisions sharing a validity window so M369's variant schemas do not
false-fire. The committed corpus carries no gapped chain and is unaffected.

The gate enforces what the contract already said; it does not pre-empt the notation choice.
If the ADR admits a resuming chain, this is the one site that gains the exemption.

### A resuming chain would assert legal continuity across years the deduction did not exist

This is the substantive argument against the taxonomy extension, and it is about grounding
rather than validator mechanics.

A continuity chain carries `legal_refs`. Regional catch-all buckets like La Rioja's "Otras
deducciones" appear only in the years the comunidad legislates one - the 2024 box exists
because La Rioja's 2024 measures granted it, and no norm granted it for 2021-2023. A
`suspended` kind would encode the claim that one legal concept persisted, dormant, across
years in which no law established it. That is invented legal behaviour, which
`aeat-safety-legal-gates` and `registry-calculation-legal-grounding` both forbid. Two
chains, each grounded in the norm that actually granted it, is the legally honest model -
not merely the cheaper one.

The distinction matters because the boxes look identical. Surface stability is what makes
`1082` a candidate for one chain, and surface stability is exactly what legal identity does
not follow from: two grants of a catch-all bucket four years apart can share a two-word
label and share no norm.

### Option evaluation against the census

**(a) `suspended` evolution kind.** Costs a seventh member on the closed evolution-kind
`Literal`, and touches more than the enum. `_evolution_covers_field` must decide which drift
a suspension covers (none, on the reading that a suspension is not a drift event); the
retirement gate must accept `suspended` as an alternative to `retired` at the disappearance
boundary; the contiguity gate needs an exemption; a resumption-proof check is needed, since
a suspended chain that never resumes is a retirement wearing another name and nothing else
would catch it; `ModeloRenameRecord` projects the kind to operators. Benefit: `1082` keeps
one chain and one translation. The census puts that benefit at one casilla, and the grounding
finding argues the claim it encodes is one the registry cannot make.

**(b) `successor_of` / `predecessor` link.** Adds a field and a graph relation to the schema.
If the localization resolver traverses the link it is option (a) under another name, with
more machinery and the same grounding objection; if it does not traverse, it is option (c)
with a breadcrumb. The dimension it would most obviously serve is already covered. It also
splits "how do two concepts relate" across two mechanisms - the evolution record and the
link field.

**(c) Two chains, translation duplicated.** Zero schema delta. Cost is one duplicated
translation of "Otras deducciones" today, and the loss of a machine-readable trail from the
2024 box back to the 2020 one. Both chains stay individually grounded. Now enforced rather
than assumed.

### What the ADR must settle

Whether a continuity chain may ever legally resume. The evidence favors no: the class is one
casilla, the id-change dimension it was thought to also cover is already handled, and a
resuming chain encodes a legal claim the corpus cannot ground. If the ADR agrees, the
amendment records the rationale so the next author meeting a gapped box does not re-derive
it, and the shipped contiguity gate is the enforcement. If the ADR disagrees, the taxonomy
extension carries the validator obligations enumerated under option (a); resumption proof is
the one with no existing analogue.

### Not investigated

Whether the localization cascade's translation surface could deduplicate two chains sharing
a normalized Spanish value without asserting continuity - a presentation-layer answer to the
duplication cost that would leave the legal model alone. The census did not measure how
often two distinct chains in one modelo share a normalized label, which is what would size
that option.

Whether the 55 drifted gap runs each carry a correct `repurposed` decision. They are outside
this question, but they are the population a corpus-wide continuity completeness gate would
have to adjudicate.

## Sources

- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:66` - `CasillaContinuidadEvolutionDefinition` and the closed evolution-kind `Literal`
- `src/cadrumo/domain/calculations/registry/_validate_cross_revision.py` - retirement and evolution-reference policies, adjacent-pair scope
- `src/cadrumo/domain/calculations/registry/_validate_cross_revision_contiguity.py` - the contiguity policy added by this work
- `src/cadrumo/domain/calculations/registry/_cross_revision_divergence.py` - divergence fields, `revisions_overlap`, `ordered_revisions`
- `src/cadrumo/domain/calculations/registry/_validate_registry_scope.py:63` - build-time wiring of the strict continuity gate
- `src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py` - regression coverage for the contiguity policy
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/continuidad/1038-2024-2025-retired.toml` - worked retirement example
- commit `ea7026b1fb` - contiguity gate and tests; commit `98ba148ca2` - extraction to its own policy module
- Census and probe were run against the compiled registry at commit `9355c545dc`. Every count above is reproducible by loading `load_registry_tree` over `src/cadrumo/_data/registry/aeat` and comparing casilla presence across validity-ordered revisions; the scripts were scratch and are not committed.
