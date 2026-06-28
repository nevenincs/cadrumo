---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S11'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the scaffold verb walking every enrolment source (registry snapshots via the validated authority, core enums, legal catalogue, topics, CLI tree introspection, locale catalogues) under the msgmerge three-outcome contract: preserve curated fields verbatim, scaffold new enrolables as empty drafts with no fuzzy auto-fill, retire vanished entries as tombstones with replaced_by (ADR D3)

## Scope

- `aeat.terminology CLI scaffold verb`

## Description

- Ground the `aeat.locales` scaffold CLI, the `dev.docs.apidocs` dev-CLI output style, and the `dev/docs/cli_reference.py` Typer tree-walk via RAG and `rg`.
- Implement the enrolment-source walkers in `_enrolment.py` - one per machine axis (modelos, IVA categories, period codes, registry topics, CLI leaf verbs) - each consuming its existing authority, producing typed `EnrolmentCandidate` records with deterministic Spanish-stem concept ids and source-derived `domain_refs` only (never prose).
- Implement the canonical TOML serialiser `_serialize.py` so a `ConceptRecord` round-trips load -> serialise unchanged and emits byte-stable output (idempotence).
- Implement the three-outcome scaffold engine `_scaffold.py`: `build_scaffold_plan` computes the structured `ScaffoldPlan` diff (the S12 `--check` seam) and `apply_scaffold_plan` writes it; `scaffold_handbook` orchestrates load -> walk -> plan -> apply.
- Add the scaffold-managed-prefix discriminator so the RETIRE outcome only touches concepts the scaffold itself created from a source axis; hand-authored concepts (e.g. `prorrata`) are never retired.
- Add the `python -m aeat.terminology` dev CLI (`__main__.py` + `cli.py`, plain English output mirroring `apidocs`) with the `scaffold` verb.
- Write real-behaviour tests proving SCAFFOLD-EMPTY (no invented prose), PRESERVE (byte-for-byte anti-clobber), RETIRE (tombstone, never delete), idempotence, `--check` dry-run, serialiser round-trip, and the concept-grade-bounded real source set.
- Run the real scaffold dry-run against a temp copy of the bundled tree to report the concept count and outcome breakdown.

## Outcome

The msgmerge three-outcome scaffold verb (ADR D3) is implemented, green, and demonstrably non-clobbering. Deliverables:

- **Enrolment walkers (`_enrolment.py`).** `collect_enrolment_candidates()` walks five axes through their authorities: modelos via the `aeat.core.Modelo` enum (`modelo-<code>`, domain `modelo`); IVA categories via `aeat.domain.iva.IvaCategory` (`iva-<value>`, domain `regimen`); period codes via `aeat.core._period.StandardPeriodCode` (`periodo-<value>`, domain `periodo`); registry topics via `aeat.core.topics.load_topic_catalogue` (`tema-<slug>`, domain `concepto`); CLI leaf verbs via `typer.main.get_command(app)` + the house Click tree-walk mirrored from `dev/docs/cli_reference.py` (`cli-<path>`, domain `cli-verb`). Each yields an `EnrolmentCandidate` carrying only machine-known identity (concept_id, domain, `domain_refs`) - never prose, so fuzzy carry-forward is structurally impossible.
- **Serialiser (`_serialize.py`).** `serialise_concept` renders a `ConceptRecord` to canonical, byte-stable TOML in record order (language sections preserve authoring order so load -> serialise -> load is order-stable); `narrower` is never emitted; empty optionals are omitted so a draft is visibly bare.
- **Three-outcome engine (`_scaffold.py`).** `build_scaffold_plan(candidates, existing, *, today)` returns a `ScaffoldPlan` of `ScaffoldEntry` rows, one per concept, each tagged PRESERVE / SCAFFOLD_EMPTY / RETIRE / UNCHANGED. `apply_scaffold_plan` writes only the changed entries (UNCHANGED touches no file). `scaffold_handbook(...)` orchestrates and accepts `apply=False` for the dry-run mode.
- **CLI (`cli.py` + `__main__.py`).** `python -m aeat.terminology scaffold` applies the plan and prints the outcome breakdown. A dev/maintenance module CLI like `aeat.locales` / `dev.docs.apidocs`, NOT the operator `aeat config`/`app` tree, so the two-CLI-roots rule does not apply (locales precedent); plain English output like `apidocs`.
- **Tests (`tests/test_scaffold.py`, 13 tests).** All green; package suite 44 passed. Key proofs: `test_preserve_keeps_curated_prose_verbatim` (full-record equality across a re-scaffold - the anti-clobber proof), `test_scaffold_empty_invents_no_prose` (no definition/scope_note/source/terms invented), `test_retire_tombstones_vanished_source_with_successor` + `test_retire_without_successor_flags_operator_and_never_deletes` (never deleted), `test_hand_authored_concept_is_never_retired_by_scaffold`, `test_second_scaffold_run_is_a_noop` (idempotence), `test_check_mode_does_not_write`, `test_serialise_round_trips_a_curated_concept`, `test_real_enrolment_candidates_are_concept_grade_and_bounded`.

Gates: `pytest src/aeat/terminology -q` 44 passed; `pytest --collect-only -q src/aeat/terminology` 44 clean; ruff / format / ty / pyright clean; apidocs `scaffold --check` conformant.

## Enrolment-source walkers and authorities used

| Axis | Authority accessor | concept_id | domain |
| --- | --- | --- | --- |
| Modelos | `aeat.core.Modelo` enum (import) | `modelo-<code>` | modelo |
| IVA categories | `aeat.domain.iva.IvaCategory` enum (import) | `iva-<value>` | regimen |
| Period codes | `aeat.core._period.StandardPeriodCode` enum (import) | `periodo-<value>` | periodo |
| Registry topics | `aeat.core.topics.load_topic_catalogue()` | `tema-<slug>` | concepto |
| CLI leaf verbs | `typer.main.get_command(app)` + Click tree-walk (house pattern) | `cli-<path>` | cli-verb |

The registry/legal authority used in S10 (`bundled_authority`) is NOT needed by the scaffold itself - the scaffold enrols concept-grade vocabulary, and legal/casilla grounding is compile-time projection (W03), not scaffold enrolment. The locale catalogue is listed in D3's source list but contributes translations to already-enrolled concepts (a curation/projection concern), not new concept ids; the scaffold therefore does not mint concepts from locale leaves (that would re-explode the 2,855-key surface). Flagged below.

## Three-outcome engine design + PRESERVE no-clobber guarantee

The engine is a pure function over `(candidates, existing, today)` producing a `ScaffoldPlan`, applied separately. PRESERVE is the load-bearing contract: `_reconcile_present` takes the EXISTING curated `ConceptRecord` and, if the source `domain_refs` are already a subset, returns it UNCHANGED (no rewrite); if the source carries a new `domain_ref`, it `model_copy`s ONLY `domain_refs` (machine-owned metadata) additively - every prose field, term, relation, lifecycle, legal_ref is carried from the existing record untouched. The anti-clobber guarantee is proven by `test_preserve_keeps_curated_prose_verbatim` asserting full `ConceptRecord` equality after a re-scaffold, and by the serialiser round-trip test asserting a curated fragment survives load -> serialise -> load. No source walker ever produces a definition / short_description / scope_note, so fuzzy carry-forward (the gettext failure mode) cannot occur by construction. SCAFFOLD-EMPTY writes a `draft` with one es section carrying a literal `(sin curar)` placeholder short_description and no prose; a source-provided `SeedLabel` may seed exactly one `preferred` term (deterministic identity, not prose).

The RETIRE refinement (surfaced by the real dry-run): retirement applies ONLY to scaffold-MANAGED ids (prefixes `modelo-`/`iva-`/`periodo-`/`tema-`/`cli-`). A hand-authored concept like `prorrata` has no managed prefix, so a vanished candidate set leaves it UNCHANGED, never retired - the scaffold only retires what it created. A managed concept whose source vanished tombstones as `retired` + `replaced_by` when a successor is curated; with no inferable successor it downgrades to `deprecated` and flags `needs_replaced_by` (it cannot mint a fake successor, and the schema forbids a retired concept without `replaced_by`).

## Concept-grade granularity + the legal-provisions question (FLAGGED for ratification)

CONFIRMED concept-grade, bounded: the real scaffold yields 291 candidates (31 modelo, 17 IVA, 21 period, 13 topic, 209 CLI verb) - hundreds, not the 18,885 casillas or 262 legal provisions. Casillas and legal provisions are PROJECTED at compile time (W03.P07), never scaffolded as concepts.

PROPOSAL on the open legal-provisions question (per the brief): the 262 legal provisions are NOT scaffolded as `legal`-domain concepts. ADR D4 surfaces legal grounding through concept/casilla `legal_refs` links, and the scale-control rule's logic ("18,885 casillas must NOT become 18,885 entries") applies identically to 262 provisions - 262 curated concepts recreates the bulk-enrolment disease. The walker therefore emits zero `legal`-domain candidates (asserted by `test_real_enrolment_candidates_are_concept_grade_and_bounded`). RATIFICATION REQUESTED: confirm legal provisions stay projected, not curated. Default per the brief: do not mass-enrol them.

Second granularity flag: 209 CLI-verb candidates dominate the 291. ADR D3 lists "CLI tree introspection" as a scaffold source and the brief says "one concept per CLI verb", so they are enrolable; but ADR D4 also calls CLI verbs a "searchable namespace" (like casillas), which could argue for projecting them instead of curating 209 drafts. The engine enrols them per D3/the brief; if the coordinator prefers CLI verbs projected (not scaffolded), flip the `cli_verbs=False` walker toggle - the engine already supports per-axis selection. FLAGGED.

## S12 --check seam left explicit

`build_scaffold_plan` returns a fully structured `ScaffoldPlan` (entries tagged by `ScaffoldAction`, `by_action()`, `counts`, `is_empty`) and `scaffold_handbook(..., apply=False)` computes it WITHOUT writing - exactly the dry-run mode S12's `scaffold --check` drift gate needs. `--check` is then a trivial: compute the plan, report `counts`, exit non-zero if not `is_empty`. The `set`/`relate`/`retire` curation verbs and `audit` report are S12's, not built here.

## Real scaffold count + outcome breakdown

Run against a temp COPY of the bundled tree (the committed tree was not mutated): 291 concept-grade candidates; against the 3 committed exemplars the plan was 291 SCAFFOLD_EMPTY, 0 PRESERVE, 0 RETIRE, 3 UNCHANGED (the hand-authored `prorrata`/`prorrata-especial`/`casilla` are correctly left UNCHANGED, not retired).

## Commit-now vs defer-to-S13 RECOMMENDATION (FLAGGED)

RECOMMEND: DEFER the full 291-fragment bootstrap run to S13. S11 ships the verb + engine + tests + the 3 hand-curated exemplars (UNCHANGED). Committing 291 generated empty-draft fragments now is precisely the bootstrap step's job (W02.P06.S13: "Run the first scaffold and editorially migrate ... into the initial curated concept set"). The S11 commit therefore contains ZERO generated draft fragments - only the verb, engine, tests, and apidocs stubs - so the engine is reviewable in isolation before the bulk tree lands under S13's editorial pass. The bundled exemplars remain the loader/validator/scaffold fixtures and prove the engine end to end.

## Notes

- One determinism fix surfaced by the round-trip test: the serialiser originally sorted language sections alphabetically while the loader preserved authoring order, breaking `load -> serialise -> load` equality. Fixed by emitting language sections in record order (loader-preserved). No schema change.
- One real bug surfaced by the dry-run: CLI `domain_refs` used a space-joined command path (`cli:app ledger add`) that violated the typed `_DomainRef` no-space pattern. Fixed to colon-joined (`cli:app:ledger:add`).
- One design correction surfaced by the dry-run: without the scaffold-managed-prefix discriminator, the real scaffold would have RETIRED the 3 hand-authored exemplars (no source axis). The managed-prefix predicate scopes retirement to scaffold-created concepts only - the correct msgmerge semantics (scaffold retires only what it created).
- Pre-existing peer drift, out of scope, none under terminology: `test_codebase_size_budgets` (peer modules) and `test_docstring_core_struct_links` (`aeat.application.live._justificante`, `aeat.application.modelo._calculation_actions`). apidocs `scaffold` again generated the peer `aeat.application.ledger._evidence_input` stub, left UNCOMMITTED; committed only my 5 terminology stubs + the toctree.
- No mocks, skips, xfail, or tautological assertions. The controlled candidate sets are real `EnrolmentCandidate` data passed to the real engine; the real-source test walks the live authorities.
