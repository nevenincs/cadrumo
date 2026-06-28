---
tags:
  - '#research'
  - '#verification-fixture-roles'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - '[[2026-06-01-semantic-cluster-hardening-plan]]'
---

# `verification-fixture-roles` research: `role-aware verification fixtures`

The verification-source honesty gate enforces that an extraction profile's
declared `verification_source` tag matches the physical provenance of the
fixture PDFs under `justificantes/<modelo_id>/`. It infers provenance from a
single proxy — the `/Producer` DocInfo field — and treats every PDF in a
modelo's fixture directory as having one uniform provenance. Modelo 390 broke
that assumption: its directory holds one real sanitised AEAT specimen
(`2021-0A.pdf`) kept as a parser-fidelity anchor alongside two synthetic
formula-verification specimens (`2022-0A.pdf`, `2023-0A.pdf`). Campaign step
`W06.P16.S37` unblocked the gate by adding a hardcoded per-fixture allowlist,
`_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS`, exempting the real anchor. This
research evaluates a durable design that removes the allowlist by making fixture
role and provenance explicit data rather than inferred-and-patched facts.

## Findings

### The conflated concepts: provenance vs role

Two orthogonal axes are currently collapsed onto one per-modelo tag:

- **Provenance** — was the PDF produced by a real AEAT toolchain (sanitised real
  corpus) or by `_generate.py` (`/Producer = "aeat-test-fixture-generator"`).
- **Role** — is the specimen a *parser-fidelity anchor* (proves the extractor
  survives a real-world layout) or a *formula-verification specimen* (synthetic,
  formula-consistent values used to verify the calculation closure).

A modelo can legitimately host both roles. M390 does: a real anchor for
layout fidelity plus synthetic specimens for formula verification. The gate's
per-modelo `verification_source` tag can only describe one provenance, so a
mixed-role pool has no truthful single tag.

### Current enforcement surfaces

- `ExtractionProfileDefinition` carries `surface`, `corpus_round_trip_verified:
  bool`, and `verification_source: Literal[...]` (values
  `real_aeat_corpus_pdf`, `synthetic_from_aeat_published_text`,
  `historical_suppression`, `not_applicable`). The tag is per-profile /
  per-modelo, never per-fixture.
- The verification-source gate globs every `*.pdf` under the modelo directory
  and asserts each one's `/Producer` matches the tag, with the new
  `_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS` allowlist as the only escape hatch.
- A *second*, independent per-fixture allowlist already exists in the
  corpus-sidecar roundtrip test: `_PERIOD_EQUALS_EJERCICIO` enumerates fixtures
  whose real or positional layout omits a labelled period token
  (M190 2024, M390 2021, M100 2023, M036 events). It encodes the same class of
  per-fixture provenance/layout fact, hardcoded in test source.

### The sidecar already encodes provenance

Every fixture PDF ships a `.json` sidecar. Real sanitised specimens carry
redaction provenance (`source_sha256`, `real_sha256`, `source_size_bytes`);
the M390 `2021-0A.json` is ~8 KB of redaction metadata. Synthetic specimens
carry formula-derived ground truth only; `2022-0A.json` / `2023-0A.json` are
~1.4 KB. The provenance the gate infers from `/Producer` and patches with an
allowlist is therefore *already determinable from the committed sidecar*. The
`/Producer` check is a proxy for a fact the sidecar holds first-hand.

### Scope today is small but the model is fragile

A producer-signature sweep of the whole fixture tree shows exactly one mixed
pool: M390. M100, M111, M190 are all-real; every other modelo is all-synthetic.
So the immediate blast radius is one modelo and two allowlist-style escape
hatches. The fragility is structural: any future real anchor added to a
synthetic pool (or synthetic specimen added to a real pool) silently reds the
gate until someone edits the allowlist, and the gate's honesty guarantee
quietly degrades into an honor-system list — the exact smell the gate was built
to remove.

### Design options

- **A — Declare role + provenance in the sidecar.** Add explicit
  `provenance` (`real_corpus` | `synthetic_generated`) and optionally `role`
  (`parser_anchor` | `formula_verification`) fields to the sidecar schema (or
  derive provenance from the already-present redaction-metadata shape). The gate
  reads each fixture's declared provenance from its sidecar instead of inferring
  from `/Producer`, and cross-checks the sidecar claim against the physical
  `/Producer` rather than against a per-modelo tag. Removes
  `_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS` entirely and can subsume
  `_PERIOD_EQUALS_EJERCICIO`. Single source of truth; honesty preserved (the
  physical `/Producer` still validates the sidecar's claim). Cost: sidecar
  schema addition + a one-time sidecar backfill + gate rewrite. Moderate.

- **B — Separate fixtures by role into subdirectories.**
  `justificantes/390/real-corpus/` vs `justificantes/390/synthetic/`. The gate
  keys provenance off the directory. Physically obvious. Cost: relocates the
  fixture tree and rewrites every consumer path reference across parsers,
  sanitiser, and tests — high churn for one mixed modelo.

- **C — Declare verification specimens on the profile.** The
  `ExtractionProfileDefinition` lists which fixtures are its formula-verification
  specimens; the gate checks only those. Cost: couples the registry authority to
  test-fixture filenames — an architecture-boundary smell (the registry should
  not know about the test fixture tree).

- **D — Keep the S37 allowlist (status quo).** Minimal, documented, but
  re-introduces the honor-system per-fixture list the gate exists to eliminate,
  and leaves the parallel `_PERIOD_EQUALS_EJERCICIO` list unaddressed.

### Recommendation

Option **A** (sidecar-declared provenance, gate reads the sidecar and validates
it against the physical `/Producer`) is the durable fit: it puts the
provenance fact where the data already lives, keeps the physical-evidence
honesty check, removes the new allowlist, and offers a path to retire the
second `_PERIOD_EQUALS_EJERCICIO` list. The `role` field is a worthwhile
companion if the parser-anchor vs formula-verification distinction earns its own
assertions; if not, provenance alone closes the gate cleanly. Option B is
rejected for churn, C for the boundary violation, D for re-introducing the smell.

### Open questions for the ADR

1. Add an explicit `provenance` field to the sidecar, or derive it from the
   existing redaction-metadata shape (presence of `source_sha256`)?
2. Include a `role` field now, or defer until a role-specific assertion needs it?
3. Should the gate cross-check the sidecar claim against `/Producer` (defence in
   depth) or trust the sidecar as sole source?
4. Migrate `_PERIOD_EQUALS_EJERCICIO` onto the same sidecar mechanism in this
   feature, or leave it as a tracked follow-up?
