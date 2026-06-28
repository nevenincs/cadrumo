---
tags:
  - '#research'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-20-branch-reconciliation-audit]]'
  - '[[2026-04-21-declaracion-extractor-adr]]'
---



# `declaracion-extraction-architecture` research: `registry-driven vs per-modelo Python extractors`

HEAD parses a filed declaración PDF via a registry-profile-driven generic
parser, but the only accepted ADR on the subject mandates per-modelo
Python extractor classes. The hexagonal restructure deleted every
extractor class and replaced them with the generic parser — an
undocumented re-architecture. This research grounds the decision the
follow-up ADR must settle: ratify the registry-driven design or restore
the Python extractor classes.

## Findings

### 1. Current state — registry-profile-driven generic parser

`src/aeat/adapters/inbound/declaracion/` has no extractor classes and no
ABC. `__init__.py` exports only `parse_declaracion`,
`parse_declaracion_bytes` and the strict records — no
`DeclaracionExtractor`, no `_extractor.py`, no `_extractors/` package.
(Contrast the sibling `borrador` adapter, which *retained*
`_extractors/modelo_100_summary_v2025.py` and a `get_extractor(año)`
class registry.)

`parse_declaracion` → `_parse_declaracion_pages` in `_parser.py` runs one
fixed sequence with no modelo branch: resolve `TemplateRevision`,
resolve period, load `RegistrySnapshot`, select one `declaracion_pdf`
profile, extract tax id, `_extract_profile_values`.

`_select_extraction_profile` filters snapshot `extraction_profiles` to
`surface == "declaracion_pdf"` and `"declaration_pdf" in
accepted_artefact_kinds`, requiring exactly one. The profile is the only
per-modelo input — registry data, not code.

`_extract_profile_values` iterates `profile.target_casillas`, rejects
zero hits (`missing`), multiple hits (`ambiguous`), unparseable values
(`malformed`), then enforces `min_coverage`; any miss raises
`DeclaracionParseError` (`failure_semantics = "fail_hard"`).

The matching core `_find_casilla_hits` in `_parser.py` compiles a
per-casilla regex `(?m)^\s*{re.escape(casilla_id)}\b[^\n]*?\s+
{SPANISH_AMOUNT_GROUP}\s*$` — it anchors on the casilla id printed
literally at line start and captures a trailing Spanish-formatted
amount. The referential validator checks `target_casillas` against the
revision's casilla **id** set, so the parser regexes casilla *ids*
verbatim. This works only when the casilla id equals the printed number
and the value is numeric.

`ExtractionProfileDefinition` in `registry/_schema.py`: `surface`
selects the pipeline; `accepted_artefact_kinds` is the validated
allow-list; `target_casillas` a non-empty `CasillaId` tuple;
`min_coverage` the required-resolution fraction; `failure_semantics`
fixed `"fail_hard"`. Strict/frozen records throughout;
`DeclaracionObservation` additionally carries a `registry_snapshot_ref`
four-axis coordinate the ADR's `DeclaracionFiling` lacked.

Deletion commits confirmed: `1f301c9e1` "disable declaracion extractor
registry", `39d5bbc99` "delete generic declaracion extractor",
`624e7d7cf` "delete legacy declaracion extractors" — no accepted ADR
sanctions any.

### 2. What the accepted ADR mandated

`2026-04-21-declaracion-extractor-adr` (accepted): a `DeclaracionExtractor`
ABC with abstract `extract(pdf_path) -> DeclaracionFiling`; a Python-class
registry in `_extractors/__init__.py` keyed `(modelo, año, revision)`,
one subclass file per modelo-revision; an ordered P3-AcroForm /
P1-label-regex / P2-bbox primitive stack inside each class; six-modelo
scope 130/303/111/115/180/190 with MVP v1 = 130 + 303; 500+ synthetic +
3 anchor exit criteria per class. The ADR's registry is a **code**
registry; HEAD's is a **data** registry — opposite sides of the
code/data line.

### 3. Current registry coverage of the six ADR-scoped modelos

- **130** — `modelo-130-declaracion-pdf`, numeric `target_casillas`
  `"01".."19"`; casilla `id == number`. **Functional.**
- **111** — extraction-profile fragment, numeric `"01".."30"`.
  **Functional.**
- **115** — numeric `"01".."05"`. **Functional.** (130/111/123
  round-trip in `test_parser_boundary.py`.)
- **180** — only an `export_record` profile (`decl.*`/`perc.*` slugs);
  **no `declaracion_pdf` profile** — `_select_extraction_profile` raises
  "available: none".
- **190** — `surface = "declaracion_pdf"` but `target_casillas` are
  slugs (`decl.total-percepciones`, ...); ids are slugs, not numbers.
  **Non-functional stub** — `_find_casilla_hits` regexes the slug, which
  cannot match the printed form. Loads green, extracts nothing.
- **303** — `303.toml` has **no `extraction_profiles` array at all**.
  Zero coverage — and 303 is the MVP-v1 headline modelo.

Verdict: 3 work (130/111/115), 3 do not (180 absent, 190 stub, 303
absent).

### 4. The named-field problem

Modelos 036/037/369/720/840 use named text fields, not numeric
casillas. 036 has `decl.event-kind`, `decl.vigencia-2025`
(`data_type="text"`); 720 and 840 carry `declaracion_pdf` profiles
whose `target_casillas` are `["decl.ejercicio","decl.tipo-declaracion"]`
— text. Those are dead on arrival: `_find_casilla_hits` always raises
`missing`. 369 is a fragment-directory modelo with no `declaracion_pdf`
profile; 037 has no registry presence at all.

`_label_regex.py` already exposes `TEXT_VALUE_GROUP` alongside
`SPANISH_AMOUNT_GROUP`, but `_find_casilla_hits` hard-codes the numeric
group and the `re.escape(casilla_id)` line-start anchor. The generic
parser structurally cannot read a named-field modelo: it would need to
anchor on the printed *label* (not the id slug) and capture a *text*
value. Registry-driven handling needs a typed match-strategy in the
profile schema; Python-class handling writes the label regex per class.

### 5. Conformance against the accepted ADR corpus

- **Hexagonal** (`2026-04-30-aeat-restructure-adr`) — both options sit
  under `adapters/inbound/declaracion/`; no violation.
- **Registry-data direction** (`2026-05-03-calculation-truth-registry-
  pending-adr`, accepted) — this ADR moved per-modelo authority into
  reviewed registry TOML and retired the Python `_rulesets/`. The
  registry-driven parser is the same move; restoring per-modelo
  extractor classes rebuilds exactly the retired pattern — a
  counter-current.
- **Schema hardening** (`2026-05-18-schema-hardening-adr`, accepted) —
  `ExtractionProfileDefinition` is already strict/frozen; a named-field
  extension must use typed `Literal` enums, no `dict[str, Any]`.
- **Spanish-stem** (`2026-05-19`) — current module conformant; neutral
  between options.
- **Fragment registry** (`2026-05-19-modelo-registry-fragment-
  architecture-adr`) — already hosts `extraction_profiles/` fragments;
  composes with the registry-driven design.

Conformance: registry-driven is strongly aligned with all accepted
post-April ADRs; the per-modelo-class design aligns only with the
now-contradicted `2026-04-21` ADR.

### 6. Modelo scope

The ADR commits six (130/303/111/115/180/190); `feature/271-pdf-import`
reached 21. HEAD has already drifted — 123 ships working numeric
extraction; 720/840 carry dead named-field stubs — without an ADR.

## Option evaluation

- **A — Ratify registry-driven as-is.** Lowest cost (code exists,
  tested). Covers numeric modelos with zero new code. Does not cover
  named-field modelos. Strongly conformant. Weakness: no bbox/AcroForm;
  cannot express hard layouts.
- **B — Restore per-modelo Python extractor classes.** Maximum
  flexibility, full P1/P2/P3 reachable. Highest cost (reverse three
  deletion commits, re-implement to current convention, delete the
  working parser). Conformant only with the superseded-in-spirit
  `2026-04-21` ADR; counter to `2026-05-03`.
- **C — Hybrid: ratify registry-driven + typed named-field primitive.**
  Full coverage; closes the 190/720/840 dead-stub defect; moderate cost
  (schema migration + parser branch + named-field tests, no class
  restoration). Best conformance. Leaves a clean bbox/AcroForm
  extension point.

## Recommendation

**Adopt Option C.** The follow-up ADR should **formally supersede
`2026-04-21-declaracion-extractor-adr`** and ratify the
registry-profile-driven generic parser, extended with a typed
named-field primitive.

Rationale: the registry-driven design is the only option in step with
the settled post-April direction — `2026-05-03` already decided
per-modelo authority belongs in registry data, not Python classes;
Option B would rebuild the retired pattern. The undocumented restructure
moved declaración extraction onto the *correct* side of the code/data
line — the defect is procedural (no ADR), not architectural. Option A
alone leaves five named-field modelos unreadable and three dead
`declaracion_pdf` stub profiles; the hybrid closes that hole inside the
registry contract.

**Scope to commit — two explicit tiers:**

- *Numeric-casilla tier (ratify now):* the ADR six (130/303/111/115/180/
  190) **plus 123** (already shipping — fold in rather than leave as
  drift). Work: 130/111/115/123 done; author `declaracion_pdf` profiles
  for 303 and 180; replace modelo 190's `decl.*` stub ids with the
  numbered/labelled targets the form prints; restore the modelo 130
  `03 = 01 − 02` cross-check as a `verification_expectations` stanza.
- *Named-field tier (separately scoped, gated on the primitive):*
  036/037/369/720/840 — not immediate deliverables; the ADR commits the
  primitive as the mechanism, registers 037, corrects/removes the dead
  720/840 stubs, and schedules these as follow-up. This deliberately
  rejects the 21-modelo single-bite scope.

**Named-field handling:** extend `ExtractionProfileDefinition` with a
typed per-target descriptor — `match_strategy:
Literal["numeric_casilla","named_label"]`, an optional label pattern,
`value_kind: Literal["amount","text","enum"]`. Branch
`_find_casilla_hits` on strategy (numeric path unchanged; `named_label`
anchors on the printed label, captures with the existing
`TEXT_VALUE_GROUP`). Add registry validation that a `declaracion_pdf`
profile referencing `data_type = "text"` casillas must use `named_label`
targets — so 720/840-style dead stubs fail the snapshot-build gate
instead of loading green. Defer bbox/AcroForm (the ADR's P2/P3) as a
named future extension.
