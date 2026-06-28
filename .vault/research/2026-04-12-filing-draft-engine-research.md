---
tags:
  - "#research"
  - "#filing-draft-engine"
date: 2026-04-12
modified: '2026-04-12'
related: []
---
# Filing draft generation engine — research (#39)

Date: 2026-04-12
Branch: `feature/39-filing-draft-engine`
Issue: wgergely/aeat#39

## Question

What public API shape should the filing draft engine expose so that
every upstream subpackage (modelos, casillas, schemas, deadlines,
manuals, sync, storage) can converge on a single typed answer to
"give me a draft for `(modelo, period, profile, inputs)` and tell me
whether it is valid"?

## Constraints

- **Pydantic v2 mandate.** Every record/finding/value crossing a
  module boundary or persisted to disk MUST be a strict pydantic v2
  `BaseModel` (`ConfigDict(strict=True, frozen=True, extra="forbid")`).
  Closed enumerations are `enum.StrEnum`. No dataclasses for
  boundary-crossing types. No bare `dict[str, Any]` in public
  signatures or persisted files.
- **Public API discipline.** Callers outside `aeat.application.filing` may import
  only from `aeat.application.filing`; private builder implementations live in
  `aeat.application.filing._builders`.
- **Sibling-branch isolation.** Hard imports from `aeat.domain.modelos`,
  `aeat.domain.schema`, `aeat.domain.casillas`, `aeat.domain.deadlines`, `aeat.adapters.persistence.storage`,
  `aeat.adapters.outbound.llm`, `aeat.application.sync` are forbidden — every cross-module
  collaborator is consumed via a Protocol stub. `aeat.domain.manuals.Rule`
  and `aeat.core.i18n.Translatable` are exceptions because they are
  already on `main`.
- **Trilingual contract.** All user-facing strings are
  `aeat.core.i18n.Translatable` nested dicts (`es`/`en`/`hu`).
- **Errors.** Every domain error inherits from `aeat.core.errors.AeatError`.
- **Tests.** Pytest only, `@pytest.mark.unit`, colocated with the
  module under `src/aeat/application/filing/`. No mocks/patches/fakes/stubs;
  Protocol-conforming concrete test doubles are written by hand.

## Trade-off 1 — single function vs. session class

Option A — single `build_draft(modelo, period, profile, inputs)`
function that selects the right builder, runs it, runs the validator,
and returns a frozen `FilingDraft`.

Option B — `FilingDraftSession` class that holds intermediate state
across multiple `add_value()` / `recompute()` / `validate()` calls,
mutates a working draft, and freezes on `commit()`.

**Decision.** Option A. The first cut explicitly produces drafts up
to `READY_TO_SUBMIT`; there is no interactive editing surface yet.
A pure function with frozen pydantic outputs gives us deterministic
hashes, JSON round-trip for free, and an obvious unit-testing model.
We can layer a `FilingDraftSession` on top later without breaking
this surface.

## Trade-off 2 — formula trace shape

Option A — free-form `formula_trace: str | None` that the builder
fills with a human-readable expression like
`"casilla_03 = casilla_01 - casilla_02"`.

Option B — structured `formula_trace: tuple[str, ...] | None`
listing the casilla IDs that fed the computation, in evaluation
order.

**Decision.** Option B (matches the issue spec). A structured
sequence of casilla IDs lets the validator detect divergence
mechanically (rebuild the dependency graph; check that every
declared input was actually used) without parsing free text. The
human-readable expression is a separate concern that lives on the
casilla schema (`#9`), not on the draft.

## Trade-off 3 — proof-of-concept modelo

Modelo 130 (pago fraccionado IRPF, autónomos régimen de estimación
directa) is the chosen PoC because:

- It is the project's north-star use case (CLAUDE.md / memory:
  "automated end-to-end tax filing for a Spanish autónomo").
- It has a small, well-understood casilla shape (~16 casillas) so
  the synthetic test schema fits in a single file.
- Its formulas (ingresos − gastos → rendimiento → pago fraccionado
  20%) exercise both literal inputs and computed casillas.
- It is filed quarterly, which lets the deadline-engine Protocol
  stub return a meaningful value during smoke tests.

Other modelos (303 IVA, 100 IRPF) are explicit follow-ups, one PR
per modelo.

## Trade-off 4 — drafts on disk

Drafts are written as individual JSON files under
`AEAT_DRAFTS_DIR` (default `<repo>/var/drafts`). The filename is
`{modelo}_{period}_{draft_id}.json`. This avoids any premature
coupling to `aeat.adapters.persistence.storage` (#10) while preserving the round-trip
guarantee — `FilingDraft.model_validate_json(path.read_text())`
must equal the original draft.

## Stable `draft_id` hashing

The `draft_id` is a SHA-256 hex digest, truncated to 16 hex chars,
of the canonical JSON serialisation of the tuple
`(modelo, period, profile_tax_id, schema_version, sorted_values)`.
`sorted_values` is the list of `FilingValue` records sorted by
`casilla_id` and serialised via `model_dump(mode="json")` so the
hash is content-addressed and deterministic regardless of insertion
order. `created_at`, `updated_at`, `findings`, `notes`, and `status`
are deliberately excluded so re-validating a draft does not change
its identity.

## Cross-module Protocols

Every upstream collaborator is represented by a `Protocol` defined
in `aeat.application.filing._protocols`. The PoC ships in-test concrete
implementations of each Protocol; production wiring lives behind
follow-up rebases.

- `CasillaSchema` — describes a single casilla (id, kind,
  required, value type, formula inputs, validation range).
- `CasillaSchemaProvider` — `get_schema(modelo) -> CasillaCollection`.
- `DeadlineChecker` — `check(modelo, period) -> DeadlineStatus`.
- `ModeloIdentity` — `id`, `display_name`, `cadence`.

## Out of scope

- Submission to AEAT (`#16` browser + `#8` cert auth).
- Builders for any modelo other than 130.
- Storage layer integration (`#10`).
- A web UI.
- LLM-driven assistance (`#21`).
