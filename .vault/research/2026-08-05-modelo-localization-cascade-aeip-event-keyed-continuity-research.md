---
tags:
  - '#research'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:574d022adc85a5e278f12b81b4fef64e7c1d4c4e20747c9db40b6927dea0e504'
related:
  - "[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]"
  - "[[2026-08-04-modelo-localization-cascade-adr]]"
  - "[[2026-08-05-modelo-localization-cascade-gapped-continuity-chain-notation-research]]"
---

# `modelo-localization-cascade` research: `aeip event-keyed continuity`

Modelo 100 anexo A ("acontecimientos de excepcional interés público", section
`resultados/anexo_a_res/deducciones_inversion_empresarial_res`) is the one casilla family
where the ordinary continuity keys do not work. Its ids are repacked every filing year and
all its event rows share a single `semantic_role`, so a chain named after either would be
wrong. Only the official Spanish programme title identifies the underlying acontecimiento —
and since the localization cascade landed, that title is not in the schema at all: a casilla
declares only its `localization_keys` and the text resolves from the shared catalogues.

Measured across the six shipped revisions (2020-2025): 315 event-row occurrences carrying
136 distinct programmes, 93 of which span more than one revision. 31 of the 97 casilla ids
in use carry more than one programme, one of them three. Keying on the resolved title
produces zero collisions across all 136.

Four identity questions could not be settled from the titles alone. All four are now
settled, and the instrument that settled them was not the label but the **XML field name**
in AEAT's own Diseño de Registros dictionary — a stable per-designation identifier that
distinguishes a relabelled programme from a re-designated one where the printed title
cannot.

The scheme itself changed shape under the cascade. A chain id is embedded whole into its
continuity locale key, and the key encoder base32-encodes any segment outside
`[A-Za-z0-9_-]`, so the dotted convention would turn every chain's own key into an opaque
blob. The family is therefore keyed `irpf-aeip-<event-slug>-aplicado`, which supersedes the
dotted shape H1 landed.

## Findings

### The family, measured

Counts are reproducible with `python -m dev.registry.aeip inventory`, which reads the family
through `load_modelo_directory` and resolves each title with `casilla.get_label`.

The anexo-A table carries two roles. `irpf_anexo_a_aeip_aplicado` is the per-programme event
row (315 occurrences). `irpf_anexo_a_aeip_aplicado_flag` is the *category* row of the same
table (133 in-section) — régimen general LIS, I+D+i, producciones cinematográficas. Category
rows name no programme and are not part of this family.

| revision | event rows | category rows | programmes | new | retired into |
|---|---|---|---|---|---|
| 2020 | 37 | 14 | 36 | 36 | 0 |
| 2021 | 56 | 20 | 56 | 32 | 12 |
| 2022 | 67 | 24 | 67 | 27 | 16 |
| 2023 | 71 | 25 | 71 | 16 | 12 |
| 2024 | 41 | 25 | 41 | 0 | 29 |
| 2025 | 43 | 25 | 43 | 25 | 24 |

Programmes span 1 revision (43), 2 (26), 3 (52), 4 (13), 5 (1), and 6 (1) — the three-year
mode matching the usual AEIP designation window.

### Neither the id nor the role can key this family

The `semantic_role` is shared by every event row in every revision, so a role-derived name
would collide 315 ways.

The id is actively reused: 31 of 97 event-row ids carry more than one programme. Id `0757`
carries three — Gran Teatre del Liceu, Gran Premio de España de Fórmula 1, and Primavera
Sound — and `0760`, `0791`, `0793`, `0796`, `0797` carry three each. A chain keyed on the id
would assert that a Formula 1 race and an opera-house anniversary are one legal concept.

The structural core cannot discriminate either: every event row declares the same field set
with no `data_type`, `input_kind`, `formula`, or `binding`. `legal_refs` vary by revision,
not by programme — 2020-2024 rows carry `ley-35-2006:art-68.2` and 2025 rows carry that plus
`orden-hac-277-2026:art-3`. No row cites the disposición that designated its own
acontecimiento.

### The scheme, and why the separator is a hyphen

```
irpf-aeip-<event-slug>-aplicado
```

`<event-slug>` is the official Spanish title, NFKD accent-stripped, `ñ` folded to `n` and
the ordinal indicators `º`/`ª` to `o`/`a` so "4ª Edición" and "150.º aniversario" stay
readable, then lowercased with non-alphanumeric runs collapsed to single hyphens
(`dev/registry/aeip/manager.py`, `derive_slug`).

The separator is the load-bearing detail. `casilla_continuity_locale_key` embeds the chain
id whole into `modelo.schema.100.casilla.continuidad.<chain-id>.label`, and
`encode_modelo_locale_segment` passes `[A-Za-z0-9_-]+` through verbatim but base32-encodes
anything else. Measured on the landed hockey chain, the dotted form
`irpf.aeip.centenario-del-hockey-1923-2023.aplicado` produces a 126-character key whose
segment is the unreadable `x-d5p70phec5imis1ecdimst35dpgn4qbf5li6ar1dd1nm6qr5f4mj2e9i6cmj4c1i6cn62s3cd5hm2p3f`,
while the kebab form `irpf-aeip-centenario-del-hockey-1923-2023-aplicado` produces a
94-character key carrying the chain id verbatim.

This is not a stylistic preference. The registry already agrees: **802 of the 814
`continuidad_id` values are kebab-only**; the 12 dotted ones are all recent, and every one of
them owns an opaque key. Base32 also expands roughly 1.6x, so a chain id near the
128-character ceiling would produce a ~205-character encoded segment.

`aplicado` is the column leaf, and the dictionary explains why it is the only one. AEAT gives
each programme three XML fields — `...S` (deducción generated), `...A` (aplicado), `...P`
(pendiente de aplicación) — and **only the `A` field carries a numbered casilla** (the other
two print `###`). The registry models numbered boxes, so `aplicado` is the only column that
exists here. The leaf stays explicit so a future numbered `pendiente` column extends the
scheme without renaming existing chains.

Measured properties, all gated in `dev/registry/aeip/tests/test_manager.py`: zero slug
collisions across 136 programmes; every planned id validates against the real `ContinuidadId`
annotation (`src/cadrumo/domain/calculations/registry/_schema_base.py:185`, imported rather
than restated); no planned id base32-encodes; the longest id among programmes that actually
get a chain is exactly 128 characters (Magallanes/Elcano V Centenario), fitting with no
margin.

### What grounding buys on the locale surface

Each occurrence spends one per-revision key
(`modelo.schema.100.revision.2024.casilla.1945.label`). A stamped chain adds one continuity
key that the resolver prefers, so the whole chain collapses onto a single translated concept.
Across the 93 chains, 271 per-occurrence keys collapse to 93 — **178 fewer translatable
keys**, and no programme's translation can drift between the years it spans. That is the
cascade's own payoff, which is why this family is worth grounding rather than merely
inventorying.

### The four identity questions, and the instrument that settled them

Each dictionary row is `FIELD=[xml-path][page][casilla][label]`. The FIELD name is AEAT's own
identifier for a designation and is stable across years, which makes it decisive where the
printed label is not. Every judgment below is recorded with its evidence in
`dev/registry/aeip/adjudications.toml`, whose loader rejects an entry with no stated reason.

**The Liceu duplicate — AEAT's own error, occurrence withheld.** In 2020, "175 Aniversario de
la construcción del Gran Teatre del Liceu" appears at both id `0757` and id `0765` with
byte-identical records. The field names separate them: `M21CTLA` carries the Liceu label at
casilla 0765 consistently across 2020-2023, while `M21GPFA` at casilla 0757 carries "Gran
Premio de España de Fórmula 1" in 2021, 2022 and 2023 — and only in 2020 does the AEAT
dictionary print the Liceu label on it. The registry faithfully transcribed an AEAT
mislabelling. The 2020/`0757` occurrence is therefore withheld. It is deliberately *not*
folded into the Formula 1 chain: the published 2020 form said Liceu, and inferring an F1
designation from the field name alone would assert a continuity the published form
contradicts.

**Barcelona Mobile World Capital — a fresh designation, split.** Present 2020-2023, absent
from 2024, back in 2025. The field changes across the gap: `M21MWCA` at casilla 1702 in
2021-2023, then `M21MOBA` at casilla 1629 in 2025. A chain spanning 2024 would assert one
legal concept across a year the form says it did not exist in, which the contiguity policy
refuses (`_validate_cross_revision_contiguity.py`). The earlier window keeps the clean id;
the later takes `irpf-aeip-barcelona-mobile-world-capital-2025-aplicado`. (2020's field
`M21BWCA` also differs from 2021's `M21MWCA`, but those years are contiguous, so that rename
is a renumbering within one designation, not a new one.)

**Fráncfort — one programme relabelled, aliased.** "España País Invitado de Honor en la Feria
del Libro de Fráncfort en 2021" (2020, 2021) and "... en 2022" (2022) are the same XML field
`M21EPIA` at the same casilla `0764` with no gap; only the year inside the title moved,
tracking the fair's postponement. One chain, with the 2021→2022 pair correctly classified
`label_evolved`.

**Año Santo Jacobeo — two jubilees, kept apart.** "Año Santo Jacobeo 2021" is field `M21ASJA`
at casilla `0798` across 2020-2022; "Año Santo Jacobeo 2027" is field `M21JACA` at casilla
`0765` in 2025, with a two-year gap between. Different field, different casilla, different
jubilee. Together with the Fráncfort case this is the proof that no mechanical year-masking
rule can work: two structurally identical year-variant pairs resolve in opposite directions.

**The oversize titles were not a question at all.** The two titles exceeding the
128-character budget — the 2020 "20 Aniversario de la Reapertura del Gran Teatro del
Liceo..." (151) and "XXV Aniversario de la Declaración por la UNESCO... Guadalupe" (146) —
are both single-revision programmes (fields `M21GTLA` and `M21UMGA`, 2020 only). A
single-revision programme is never stamped and needs no chain id, so demanding a shortened
slug would have been an adjudication that changes nothing. The planner over-blocked here and
was corrected to check chain-id shape only for programmes that actually get a chain; if such
a programme later gains a revision, the check fires then.

### Churn and record volume

136 programmes opened and 93 closed across six revisions. Averaged over 2021-2025, each
filing year opens 20 chains, retires 19, and needs roughly 54 evolution records.

Fully adjudicated, the six shipped revisions plan **93 chains, 271 stamps and 254 evolution
records** — 160 `unchanged`, 76 `retired`, 17 `legal_refs_evolved`, 1 `label_evolved`. The 76
retirements are the volume the brief asked to size: this family will generate on the order of
19 retirement records per year indefinitely, because AEIP windows are designed to close.

That volume is why the scaffolding was built rather than only proposed, and it has already
paid for itself once. Every chain crossing 2024 to 2025 is `legal_refs_evolved`, not
`unchanged`, because the 2025 revision adds `orden-hac-277-2026:art-3` to every row — 17
records that hand-authoring would have got wrong and that the strict cross-revision validator
would then have refused. The generator compares both drifting axes; a human reading labels
would not have seen it.

What cannot be generated is the identity judgment, which is why the planner fails closed and
the adjudications file demands a reason.

### The 2024 cliff is a cohort expiry, not a missing transcription

The drop from 71 programmes to 41 with zero new designations looks like an under-transcribed
revision. The dropped set argues otherwise: 27 of the 30 departures end exactly at 2023, most
of them three-year 2021-2023 windows (Solheim Cup 2023, Torneo Davis Cup Madrid, MADRID HORSE
WEEK 21/23, FITUR especial, Centenario de la Batalla de Covadonga-Cuadonga). That is a cohort
reaching the end of its window together, and 2025 then opens 25 fresh programmes. The zero new
designations in 2024 is consistent with no new Presupuestos Generales del Estado having been
approved for that year, though that was not verified against the BOE here.

### Adjacent defects found while measuring

Three casillas wear `irpf_anexo_a_aeip_aplicado_flag` while sitting outside anexo A: id `0842`
in 2021 and 2022 (`resultados/deduccion_autonomica_res/canarias_res`, La Palma mínimo personal
y familiar) and id `0769` in 2022 (`.../i_baleares_res`, donaciones Ucrania). These are
autonomic deductions, not AEIP category rows. Out of scope here and harmless to the event
family, which filters on the anexo-A section, but a real `semantic_role` fidelity defect.

Separately, no anexo-A event row cites the disposición that designated its own acontecimiento
— only the framework article and, from 2025, the ordinal reference. Each AEIP programme is
established by a specific disposición adicional, so under the calculation-grounding rule this
is a per-programme legal grounding gap across the whole family. Closing it is much larger than
the chain scheme and is not attempted here.

### What was not investigated

Whether the kebab-only separator should be ratified for *all* future chain ids rather than
just this family. The measurement (802 of 814 already kebab, every dotted id owning an opaque
locale key) argues it should, and the continuity-contract ADR's stated convention is the
dotted minority, so an ADR amendment looks warranted — but that governs every modelo, not just
anexo A, and is left for the decision record.

Whether the 12 existing dotted chain ids should be renamed. Only the one in this family was
re-stamped; the other 11 belong to other campaigns.

Whether any other modelo carries an event-keyed family of the same shape. Scope was Modelo 100
anexo A; the planner takes a `--modelo` option but no other modelo was scanned.

## Sources

- `dev/registry/aeip/manager.py` — extraction through the loader, slug derivation, ambiguity
  detection, chain planning.
- `dev/registry/aeip/adjudications.toml` — the four recorded judgments and their evidence.
- `dev/registry/aeip/tests/test_manager.py` — real-corpus gates, including the locale-key
  readability gate and the landed-chain ratification.
- `src/cadrumo/domain/calculations/registry/_modelo_localization.py` —
  `casilla_occurrence_locale_key`, `casilla_continuity_locale_key`,
  `encode_modelo_locale_segment`.
- `src/cadrumo/domain/calculations/registry/_schema_base.py:185` — the `ContinuidadId`
  constraint (max 128, `^[a-z0-9][a-z0-9._:-]*[a-z0-9]$`).
- `src/cadrumo/domain/calculations/registry/_validate_cross_revision_contiguity.py` — the
  contiguity policy that refuses a gapped chain.
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/` — the AEAT
  Diseño de Registros dictionaries, 2020-2025; the XML field names `M21CTLA`, `M21GPFA`,
  `M21MWCA`, `M21MOBA`, `M21BWCA`, `M21EPIA`, `M21ASJA`, `M21JACA`, `M21GTLA`, `M21UMGA` are
  the adjudication evidence.
- Unverified: attributing 2024's zero new AEIP designations to the absence of an approved
  Presupuestos Generales del Estado for that year is general knowledge, not checked against
  the BOE here.
