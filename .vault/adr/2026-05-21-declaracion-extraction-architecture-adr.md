---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/adr/ location)
# Feature tag (replace declaracion-extraction-architecture with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#adr'
  - '#declaracion-extraction-architecture'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-21'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - '[[2026-05-21-declaracion-extraction-architecture-research]]'
  - '[[2026-04-21-declaracion-extractor-adr]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `declaracion-extraction-architecture` adr: `registry-driven declaración extraction supersedes per-modelo extractor classes` | (**status:** `accepted`)

## Problem Statement

A filed-declaración PDF is parsed in HEAD by a registry-profile-driven
generic parser: `src/aeat/adapters/inbound/declaracion/_parser.py`
selects one `declaracion_pdf` `ExtractionProfileDefinition` from the
loaded `RegistrySnapshot` and matches each `target_casillas` entry
against the PDF text. There are no extractor classes and no
`DeclaracionExtractor` ABC.

The only accepted ADR on the subject — `2026-04-21-declaracion-extractor-adr`
— mandates the opposite: a `DeclaracionExtractor` ABC with one Python
subclass per modelo-revision, registered in a code registry keyed
`(modelo, año, revision)`. The hexagonal restructure **deleted every
per-modelo extractor class** (commits `1f301c9e1`, `624e7d7cf`,
`39d5bbc99`) and replaced them with the registry-driven parser. No ADR
sanctioned that re-architecture; it stands in undocumented contradiction
to the accepted ADR.

The contradiction must be resolved, and the resolution must also close a
correctness hole the re-architecture left: of the six modelos the
accepted ADR scoped (130, 303, 111, 115, 180, 190), only 130/111/115
have working registry extraction profiles. Modelo 303 — the MVP-v1
headline modelo — has no extraction profile at all; Modelo 180 has none;
Modelo 190 carries a `declaracion_pdf` profile whose `target_casillas`
are abstract `decl.*` slugs the parser's `re.escape(casilla_id)` regex
can never match — it loads green and silently extracts nothing.

## Considerations

- **The code/data line is already settled.** `2026-05-03-calculation-truth-
  registry-pending-adr` (accepted) moved per-modelo calculation authority
  out of Python (`_rulesets/`) into reviewed registry TOML. The
  registry-driven declaración parser is the *same move* applied to
  extraction: per-modelo parsing knowledge expressed as reviewed
  registry data, not code. Restoring per-modelo extractor classes would
  rebuild the exact pattern the codebase deliberately retired.
- **The generic parser's matching contract.** `_find_casilla_hits`
  compiles, per casilla, a line-anchored regex on the casilla id printed
  literally at line start with a trailing Spanish-formatted amount. This
  works only when the casilla id equals the printed number and the value
  is numeric.
- **The named-field gap.** Modelos 036, 037, 369, 720, 840 carry text
  fields keyed by printed label, not numeric casilla id. The generic
  parser structurally cannot read them — it would anchor on a slug that
  is never printed. `_label_regex.py` already exposes a `TEXT_VALUE_GROUP`
  the numeric path does not use; the missing piece is a typed
  match-strategy in the profile schema.
- **Conformance.** The registry-driven design conforms to the hexagonal
  layout, the registry-data direction of `2026-05-03`, the
  strict-pydantic discipline of `2026-05-18-schema-hardening-adr`, the
  Spanish-stem rule of `2026-05-19-spanish-stem-terminology-authority-adr`,
  and the fragment layout of `2026-05-19-modelo-registry-fragment-
  architecture-adr`. The per-modelo-class design conforms only to the
  now-contradicted `2026-04-21` ADR.
- **Scope drift.** The accepted ADR scoped six modelos; branch
  `feature/271-pdf-import` reached twenty-one; HEAD has already drifted
  (Modelo 123 ships working numeric extraction; 720/840 carry dead
  stubs) with no ADR.

## Constraints

- The named-field extension must hold the strict / frozen /
  `extra="forbid"` discipline of `ExtractionProfileDefinition`: typed
  `Literal` enums for the match strategy and value kind, no
  `dict[str, Any]`.
- Single-segment numeric modelos already working (130/111/115/123) must
  keep validating and parsing unchanged — the named-field primitive is
  purely additive.
- A `declaracion_pdf` profile whose `target_casillas` reference
  `data_type = "text"` casillas must fail the snapshot-build gate unless
  it uses the `named_label` strategy — so dead `decl.*`-slug stubs
  cannot load green.
- No live AEAT write surface is touched; this is an inbound-parsing and
  registry-data concern only.
- Bounded MVP scope: this ADR commits the numeric-casilla tier; it does
  not commit twenty-one modelos in one bite.

## Implementation

**Decision.** Ratify the registry-profile-driven generic parser as the
canonical declaración-extraction architecture. This ADR **formally
supersedes `2026-04-21-declaracion-extractor-adr`**; the
`DeclaracionExtractor` ABC and per-modelo Python extractor classes are
not restored. Extend the registry profile with a typed named-field
primitive (the research's Option C).

**Named-field primitive.** Extend `ExtractionProfileDefinition` (and its
per-target descriptor) with `match_strategy: Literal["numeric_casilla",
"named_label"]` and `value_kind: Literal["amount", "text", "enum"]`,
plus an optional label pattern for the `named_label` strategy.
`_find_casilla_hits` branches on `match_strategy`: the `numeric_casilla`
path is unchanged; the `named_label` path anchors on the printed label
and captures with the existing `TEXT_VALUE_GROUP`. The snapshot-build
validator gains a rule: a `declaracion_pdf` profile target that names a
`data_type = "text"` casilla must use `named_label`.

**Scope — two tiers.**

- *Numeric-casilla tier (committed by this ADR):* modelos 130, 303, 111,
  115, 180, 190, and 123. 130/111/115/123 already work; the execution
  work is to author `declaracion_pdf` extraction profiles for 303 and
  180, and to replace Modelo 190's abstract `decl.*` stub targets with
  the real numeric/labelled casilla targets the form prints. The Modelo
  130 `03 = 01 − 02` intra-filing cross-check is restored as a
  `verification_expectations` stanza.
- *Named-field tier (committed as mechanism, deferred as content):*
  modelos 036, 037, 369, 720, 840. This ADR commits the named-field
  primitive as the mechanism and requires that the dead 720/840 stub
  profiles be corrected or removed so they no longer load green;
  authoring functional named-field profiles for these modelos (and
  registering 037, which has no registry presence) is scheduled as
  follow-up, gated on the primitive.

Per-modelo bbox and AcroForm extraction primitives (the superseded
ADR's P2/P3) are deferred as a named future extension if a modelo's
layout proves unreadable by label/numeric matching.

## Rationale

The registry-driven design is the only option in step with the settled
post-April direction: `2026-05-03` already decided per-modelo authority
belongs in registry data. The undocumented restructure moved declaración
extraction onto the correct side of the code/data line; the defect was
procedural — a missing ADR — not architectural. Restoring the per-modelo
extractor classes (research Option B) would reverse three deletion
commits, delete a working tested parser, and rebuild a retired pattern
at the highest migration cost.

Ratifying the parser as-is (Option A) would be cheapest but leaves five
named-field modelos unreadable and three `declaracion_pdf` stub profiles
that load green while extracting nothing — a silent-failure class this
codebase has repeatedly resolved to make loud. The hybrid (Option C)
closes that hole inside the registry contract at moderate, additive
cost, and makes the dead-stub failure mode a hard snapshot-build error.

## Consequences

- `2026-04-21-declaracion-extractor-adr` is superseded; its
  `DeclaracionExtractor` ABC and per-modelo class registry are not
  built. That ADR is marked `superseded` on acceptance of this one.
- `ExtractionProfileDefinition` gains the typed named-field fields; the
  change is additive — numeric-casilla profiles are unaffected.
- The snapshot-build validator gains a rule that turns a dead
  text-casilla `decl.*`-slug stub into a hard error; Modelo 190/720/840
  profiles must be corrected as part of the rollout or they fail the
  gate.
- The numeric-casilla tier is a bounded, executable plan: author 303 and
  180 profiles, fix Modelo 190, restore the M130 cross-check. The
  named-field tier is scheduled follow-up gated on the primitive.
- This ADR does not itself author the extraction profiles or the
  parser-code extension; those are Plan/execution work depending on this
  decision.
- No live AEAT write surface is affected.

## 2026-05-26 amendment

### Silent-failure class and the provisional_pending_specimen field

The task-32 audit (swarm axis: extraction-profile grounding) identified a
systematic silent-failure class not addressed by this ADR's original
`named_label` rule: nine `declaracion_pdf` profiles had loaded green for
months with `label_pattern` values derived circularly from the registry's
own casilla `label_es` fields, never verified against a real printed PDF.
Three profiles (M036, M347, M840) carried inline `# PROVISIONAL` comments;
six (M184, M193, M232 ×2, M720, M349) were silently provisional. Task-33
added warning comments and downgraded confidence on M184, M193, and M720.

This amendment formalises the acknowledgement mechanism as a typed schema
field. `ExtractionProfileDefinition` now carries `provisional_pending_specimen:
bool = False`. When True, it declares that the profile's `label_pattern`
values were authored without a corpus PDF specimen for round-trip
verification — the silent-failure class described above.

### Validator gate

The snapshot-build validator gains a complementary rule: for any
`declaracion_pdf` profile that is NOT marked `provisional_pending_specimen =
true`, the validator checks for a corpus fixture PDF at
`tests/fixtures/justificantes/<modelo_id>/`. If no fixture exists and the
flag is false, validation raises `RegistryValidationError`, requiring the
author to either supply a specimen or explicitly acknowledge the open risk
by setting the field. The gate is activated when the `RegistryValidator`
has a `justificante_corpus_root` available (derived automatically from
`source_root` or supplied directly for tests). M190 — the only GROUNDED
profile in the audit's classification — retains the default `false` because
its corpus fixture at `tests/fixtures/justificantes/190/` satisfies the
gate.

### Discipline going forward

Any new `declaracion_pdf` extraction profile without a corpus fixture PDF
must set `provisional_pending_specimen = true` explicitly. The silent
path — authoring a profile, watching it load green, and shipping it — is
now closed. Removing the provisional flag requires depositing a real
specimen PDF and confirming the `label_pattern` values match its printed
labels. The nine profiles tagged in task-34 (M036, M184, M193, M232
2016-2017, M232 2018-y-siguientes, M347, M349, M720, M840) carry the flag
until their respective specimen PDFs are acquired and the patterns are
verified.

## 2026-05-26 amendment (round-trip gate)

### Silent-failure class exposed by M111 and M130

Task-37 real-corpus round-trip work revealed a second silent-failure class
not addressed by the existing provisional_pending_specimen gate: M111 and
M130 both had real corpus fixture PDFs at
tests/fixtures/justificantes/{111,130}/ -- satisfying the specimen gate's
fixture-existence check -- yet production-profile extraction structurally
fails on both. M111's numeric_casilla strategy cannot match AEAT's printed
form because casilla numbers appear at line-end merged with value tokens
rather than at line-start. M130's numeric casillas appear in a detached value
block that the parser's line-anchored patterns cannot reach. The specimen gate
passed them as grounded; round-trip tests exposed them as extraction failures.

Fixture existence alone is therefore an insufficient signal of extraction
correctness. A profile may have corpus AND fail silently on every PDF in it.

### Strengthened gate: corpus_round_trip_verified

ExtractionProfileDefinition gains a second boolean field:
corpus_round_trip_verified: bool = False.

Semantic: true declares that the author has confirmed extraction works
end-to-end against the modelo's corpus PDFs via a parametrized real-corpus
round-trip test in test_parser_boundary.py (or an equivalent module).

The snapshot-build validator gains a complementary rule
(validate_declaracion_pdf_round_trip_gate): for any declaracion_pdf
profile where corpus fixture exists AND both corpus_round_trip_verified and
provisional_pending_specimen are false, validation raises
RegistryValidationError. The gate logic is:

- surface != declaracion_pdf: dormant
- provisional_pending_specimen = true: dormant (explicit opt-out)
- corpus_round_trip_verified = true: dormant (author asserts verified)
- no corpus fixture: dormant (specimen gate handles the missing-fixture case)
- fixture exists, neither flag set: FAIL

The two gates are complementary and non-overlapping: the specimen gate fires
when no fixture exists and the provisional flag is absent; the round-trip gate
fires when a fixture exists but neither verification flag is set.

### Ground-truth tagging applied

VERIFIED (corpus_round_trip_verified = true):
- M100 revisions 2021, 2022, 2023: 19 named_label casillas, round-trip
  confirmed against 3-PDF corpus.
- M190 revision 2024-y-siguientes: 3 named_label casillas, 1-PDF corpus.
- M303 revisions 2009-y-siguientes and 2023-y-siguientes: 4 and 12 casillas,
  15-PDF corpus across two templates.
- M390 revision 2010-y-siguientes: 6 named_label casillas, 2-PDF corpus.

CORPUS-GAP (provisional_pending_specimen = true added):
- M111 revision 2019-y-siguientes: corpus exists; numeric_casilla layout
  defeats extraction due to line-end box-number merging.
- M130 revision 2019-y-siguientes: corpus exists; numeric_casilla layout
  defeats extraction due to detached value blocks. Coverage = 0 on all
  corpus PDFs. Layout-defeated counts as unverified.

NO-FIXTURE-ALREADY-PROVISIONAL (no change):
- M036, M115, M123 (x2), M131, M184, M193, M232 (x2), M347, M349, M720, M840.

### Discipline going forward

Any declaracion_pdf profile with a corpus fixture must satisfy one of two
conditions or fail the snapshot-build gate:
1. A real parametrized round-trip test exists and corpus_round_trip_verified =
   true is set.
2. Extraction is known to fail or is unverified, and provisional_pending_specimen
   = true is set explicitly.

Fixture presence with neither flag is the newly-closed silent-failure path.
