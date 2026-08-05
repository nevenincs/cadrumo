---
tags:
  - '#research'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:a762530e80bd6751b44142519365fc282697570887e7d562e23132fd8ac50761'
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
wrong. Only the programme title AEAT prints in the label identifies the underlying
acontecimiento.

Measured across the six shipped revisions (2020-2025), the family is 315 event-row
occurrences carrying 136 distinct programmes, of which 93 span more than one revision and
are therefore genuine continuity chains. 31 of the 97 casilla ids in use carry more than
one programme across the years, one of them three. Keying on the title instead produces
zero collisions across all 136 programmes, and reproduces byte-for-byte the one chain the
corpus already carries, so the shape H1 landed
(`irpf.aeip.centenario-del-hockey-1923-2023.aplicado`) is ratified by the evidence rather
than superseded.

Four shapes remain that the title alone cannot settle, each a legal-identity judgment
rather than a text comparison. A planner for the family has been built and committed
(`dev/registry/aeip/`, commits `e1e8db2beb` and `a922e64ad6`); it plans 89 chains today and
refuses the rest rather than guessing. Nothing has been stamped.

## Findings

### The family, measured

Counts below are taken from the committed registry at `f54138c2c8`, which the registry
tree still matches at `a922e64ad6`. They are reproducible with
`python -m dev.registry.aeip inventory`.

The anexo-A table carries two roles. `irpf_anexo_a_aeip_aplicado` is the per-programme
event row (315 occurrences). `irpf_anexo_a_aeip_aplicado_flag` is the *category* row of
the same table (133 occurrences in-section) — régimen general LIS, I+D+i, producciones
cinematográficas, and so on. Category rows name no programme and are not part of this
family; no category row carries a quoted programme title.

| revision | event rows | category rows | programmes present | new | retired into |
|---|---|---|---|---|---|
| 2020 | 37 | 14 | 36 | 36 | 0 |
| 2021 | 56 | 20 | 56 | 32 | 12 |
| 2022 | 67 | 24 | 67 | 27 | 16 |
| 2023 | 71 | 25 | 71 | 16 | 12 |
| 2024 | 41 | 25 | 41 | 0 | 29 |
| 2025 | 43 | 25 | 43 | 25 | 24 |

2020 shows 37 rows but 36 programmes because one programme occupies two ids that year (see
the intra-revision duplicate below). Programmes span 1 revision (43), 2 (26), 3 (52), 4
(13), 5 (1), and 6 (1) — the three-year mode matching the usual AEIP designation window.

### Neither the id nor the role can key this family

The `semantic_role` is shared by every event row in every revision, so it carries no
per-programme information at all: a role-derived chain name would collide 315 ways.

The casilla id is worse than uninformative, because it is actively reused. Of 97 distinct
event-row ids, 31 carry more than one programme across the six revisions. Id `0757` alone
carries three: "175 Aniversario de la construcción del Gran Teatre del Liceu" in 2020,
"Gran Premio de España de Fórmula 1" in 2021-2023, and "Primavera Sound, created in
Barcelona" in 2025. Ids `0760`, `0791`, `0793`, `0796`, and `0797` likewise carry three
programmes each. A chain keyed on the id would assert that a Formula 1 race and an opera
house anniversary are one legal concept.

The structural core cannot discriminate either: every event row declares exactly the same
field set (`id`, `number`, `label`, `section`, `semantic_role`, `legal_refs`,
`source_refs`), with no `data_type`, `input_kind`, `formula`, or `binding`. The two
exceptions are the two rows H1 already stamped, which add `continuidad_id`.

### The published label is the only identity signal, and it is currently at risk

Because the id, the role, and the structural core are all uninformative, the label is the
sole remaining discriminator. `legal_refs` do not help: they vary by revision, not by
programme — every 2020-2024 row carries exactly `ley-35-2006:art-68.2`, and every 2025 row
carries that plus `orden-hac-277-2026:art-3`. No row cites the specific disposición that
designated its own acontecimiento.

This makes the scheme's input load-bearing, and it is presently in motion. At the time of
writing, the shared worktree holds an uncommitted peer sweep that has removed the `label`
field from 11,344 Modelo 100 fragments, including all 315 anexo-A event rows, with no
replacement home yet visible in the 2020 revision tree. That work is live and untouched
here. If it lands as-is, the event-keyed scheme loses its identity source entirely and this
family becomes unkeyable until the titles are reachable again — from the locale catalogues
or from wherever the cascade rehomes them.

Two consequences were built in rather than left to prose. The planner's tests read the
committed tree via `git archive HEAD` rather than the working tree, so they measure the
registry rather than a peer's half-applied sweep. And an event row whose title cannot be
parsed is reported as a `missing_title` ambiguity rather than silently dropped, so the loss
surfaces as a loud refusal instead of an empty plan.

### The event-keyed scheme

The shape the evidence favours is the one H1 already used:

```
irpf.aeip.<event-slug>.<column>
```

`<event-slug>` is the official programme title, NFKD accent-stripped, with `ñ` folded to
`n` and the ordinal indicators `º`/`ª` folded to `o`/`a` so "4ª Edición" and "150.º
aniversario" stay readable, then lowercased with every non-alphanumeric run collapsed to a
single hyphen (`dev/registry/aeip/manager.py`, `derive_slug`).

`<column>` is `aplicado`. That is the only column the family declares: all 315 event-row
labels end in the single suffix "Aplicado en esta declaración", so there is no
"pendiente de aplicación" sibling to distinguish today. The leaf is kept explicit anyway so
a future column extends the scheme without renaming chains that already exist. Note this
corrects the H5 brief's premise of "sibling roles for the other columns of each event row":
no such siblings exist in the registry.

Measured properties of the derived ids, all enforced by
`dev/registry/aeip/tests/test_manager.py`:

- **No collisions.** 136 programmes produce 136 distinct slugs.
- **Valid.** Every planned id validates against the real `ContinuidadId` annotation
  (`src/cadrumo/domain/calculations/registry/_schema_base.py:185`), which the test imports
  rather than restating, so a change to the constraint fails the gate.
- **Length.** 134 of 136 fit the 128-character budget; two do not (151 and 146 characters)
  and are refused pending a shortened form.
- **Ratifies the landed chain.** The scheme reproduces
  `irpf.aeip.centenario-del-hockey-1923-2023.aplicado` exactly, including the 2024 -> 2025
  retirement H1 authored.

Also worth pinning: the evolution kind for a continuing pair must cover both drifting axes,
not just the label. Because the 2025 revision adds `orden-hac-277-2026:art-3` to every row,
all 17 chains crossing 2024 -> 2025 are `legal_refs_evolved`, not `unchanged`. Recording
them as unchanged would be a drift the strict cross-revision validator refuses — a defect
the planner carried until `a922e64ad6`.

### Four shapes the title alone cannot settle

These are the open adjudications. Each is a legal judgment against the official AEAT form
dictionaries and the designating norms; the planner refuses to guess and blocks the
affected programmes. `python -m dev.registry.aeip check` exits non-zero while any remain.

**A re-designated programme (`gapped_span`, 1 case).** "Barcelona Mobile World Capital"
appears in 2020 (id `0786`), 2021-2023 (id `1702`), is absent from 2024, and appears again
in 2025 (id `1629`). Under the contiguity policy settled by the sibling gapped-chain
research and enforced by
`src/cadrumo/domain/calculations/registry/_validate_cross_revision_contiguity.py`, one
chain cannot span that gap. If the 2025 appearance is a fresh designation under a new
window, it is a second chain; if the 2024 absence is instead a transcription gap, the fix
belongs in the 2024 revision, not in the chain scheme.

**A duplicate with no discriminator (`intra_revision_duplicate`, 1 case).** In 2020, "175
Aniversario de la construcción del Gran Teatre del Liceu" occupies both id `0757`
(`.../2020/casillas/0676-c0757.toml`) and id `0765` (`.../2020/casillas/0684-c0765.toml`),
and the two records are byte-identical apart from the id and number. From 2021 onward
`0765` carries the Liceu programme while `0757` carries the Formula 1 race, which makes the
2020 `0757` record the suspected transcription error — but the registry holds nothing that
distinguishes a spurious duplicate from a genuine second box, so this needs the official
2020 dictionary.

**Titles too long for the budget (`oversize_chain_id`, 2 cases).** "20 Aniversario de la
Reapertura del Gran Teatro del Liceo de Barcelona y el bicentenario de la creación de la
Societat d'Accionistes" yields a 151-character id, and the XXV Aniversario UNESCO/Guadalupe
title yields 146. Both need a shortened but still recognisable form.

**Year-variant titles (`title_variant`, 2 groups).** Two pairs differ only in an embedded
year, and they resolve in opposite directions — which is precisely why this cannot be a
text rule. "España País Invitado de Honor en la Feria del Libro de Fráncfort en 2021"
(2020, 2021) versus "... en 2022" (2022) looks like one programme whose label AEAT
restated. "Año Santo Jacobeo 2021" (2020-2022) versus "Año Santo Jacobeo 2027" (2025) are
distinct holy years under distinct designations. A masking rule that merged the first would
also wrongly merge the second.

Ten further title pairs are near-duplicates above 0.90 similarity — "Universo Mujer (II)" /
"III" / "IV", "Programa Deporte lnclusivo" / "II", "Barcelona Equestrian Challenge (3ª
Edición)" / "(4ª Edición)", the successive "Programa de preparación de los deportistas
españoles" editions. All are genuinely successive designations carrying their own windows,
and the edition marker in the title keeps them apart automatically. They are reported as
advisory only, not blocked.

### Churn and record volume

The family turns over faster than any other in the registry: 136 programmes opened and 93
closed across six revisions. Averaged over 2021-2025, each new filing year opens 20 chains,
retires 19, and needs roughly 54 evolution records (continuing pairs plus retirements).

For the six revisions already shipped, the currently-plannable 89 chains need 257 stamps
and 240 evolution records — 151 `unchanged`, 72 `retired`, 17 `legal_refs_evolved`. The
four blocked multi-revision programmes add roughly 15 more once adjudicated. Retirements
alone are 72 records, which is the volume the H5 brief asked to size: this family will
generate on the order of 19 retirement records per year indefinitely, because AEIP windows
are designed to close.

That volume is why the scaffolding was built rather than only proposed. Hand-authoring 240
records with correct evolution kinds is not reliable, and the `legal_refs_evolved` defect
found above is the exact failure mode — it was invisible to inspection and obvious to a
generator that compares both axes. What cannot be generated is the identity judgment, which
is why the adjudications file (`dev/registry/aeip/adjudications.toml`) requires a stated
`reason` on every entry and the loader rejects one without it.

### The 2024 cliff is a cohort expiry, not a missing transcription

The drop from 71 programmes in 2023 to 41 in 2024, with zero new programmes, looks like an
under-transcribed revision. The dropped set argues otherwise: 27 of the 30 departures are
programmes whose declared span ends exactly at 2023, most of them three-year 2021-2023
windows (Solheim Cup 2023, Torneo Davis Cup Madrid, MADRID HORSE WEEK 21/23, FITUR especial,
Centenario de la Batalla de Covadonga-Cuadonga, and so on). That is a cohort reaching the
end of its window together, and the 2025 revision then opens 25 fresh programmes. The zero
new designations in 2024 is consistent with no new Presupuestos Generales del Estado having
been approved for that year, though that explanation was not verified against the BOE here
and should be before it is relied on.

### Adjacent defects found while measuring

Three casillas wear `irpf_anexo_a_aeip_aplicado_flag` while sitting outside anexo A
entirely, in autonomic-deduction sections: id `0842` in 2021 and 2022
(`resultados/deduccion_autonomica_res/canarias_res`, "Por mínimo personal, familiar y por
discapacidad para residentes en la isla de La Palma") and id `0769` in 2022
(`.../i_baleares_res`, "Por donaciones para paliar los efectos del conflicto de Ucrania").
These are Canarias and Baleares deductions, not AEIP category rows. The mis-roling is out
of scope here and does not affect the event family, which is filtered on the anexo-A
section, but it is a real `semantic_role` fidelity defect.

Separately, no anexo-A event row cites the disposición that designated its own
acontecimiento — only the framework article `ley-35-2006:art-68.2` and, from 2025, the
ordinal reference. Each AEIP programme is established by a specific disposición adicional
of a specific law, so under the calculation-grounding rule this is a per-programme legal
grounding gap across the whole family. Closing it is a much larger piece of work than the
chain scheme and is not attempted here.

### What was not investigated

The identity judgments themselves. All six open ambiguities are stated with their evidence
and left open; none was resolved against the official AEAT form dictionaries, the Manual
Práctico, or the BOE, and the planner is deliberately blocked until they are.

Whether the peer label-removal sweep will rehome the titles somewhere the planner can read
them. That work is uncommitted and its destination is not yet visible, so the scheme's
input dependency is flagged rather than resolved.

Whether any other modelo carries an event-keyed family with the same shape. The measurement
was scoped to Modelo 100 anexo A because that is where the brief pointed; the planner takes
a `--modelo` option but no other modelo was scanned.

## Sources

- `dev/registry/aeip/manager.py` — extraction, slug derivation, ambiguity detection, chain
  planning.
- `dev/registry/aeip/adjudications.py`, `dev/registry/aeip/adjudications.toml` — the
  operator judgment surface and the six open cases.
- `dev/registry/aeip/tests/test_manager.py` — the real-corpus gates, including the
  `HEAD`-pinned corpus fixture and the landed-chain ratification.
- `src/cadrumo/domain/calculations/registry/_schema_base.py:185` — the `ContinuidadId`
  constraint (max 128, `^[a-z0-9][a-z0-9._:-]*[a-z0-9]$`).
- `src/cadrumo/domain/calculations/registry/_validate_cross_revision_contiguity.py` — the
  contiguity policy that refuses a gapped chain.
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/{2020..2025}/casillas/` — the
  measured corpus; `.../2020/casillas/0676-c0757.toml` and `.../2020/casillas/0684-c0765.toml`
  are the intra-revision duplicate.
- Commits `e1e8db2beb` (planner) and `a922e64ad6` (legal-refs classification fix); registry
  state measured at `f54138c2c8`.
- Unverified: the attribution of 2024's zero new AEIP designations to the absence of an
  approved Presupuestos Generales del Estado for that year is general knowledge, not
  checked against the BOE here.
