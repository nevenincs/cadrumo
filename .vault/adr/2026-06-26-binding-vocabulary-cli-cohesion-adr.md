---
tags:
  - '#adr'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - "[[2026-06-26-bindings-architecture-unification-audit]]"
  - "[[2026-06-26-bindings-architecture-unification-research]]"
  - "[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]"
  - "[[2026-06-10-cli-pull-file-standard-adr]]"
---



# `binding-vocabulary-cli-cohesion` adr: `vocabulary and CLI cohesion: retire the binding homonyms and reconcile the source-pull verb surface` | (**status:** `proposed`)

> PROPOSED — design-ahead for coordinator review, authored while the code phases are
> gated. NOT self-accepted, NOT a code-execution request; EXECUTION sequences last,
> after phases 2.1-2.3 (it renames symbols those phases introduce/settle). Phase 2.4
> of the bindings-architecture-unification sweep; canonical direction = the phase +
> foundational ADRs (no apex).

## Problem Statement

Phase 2.4 — the final phase — of the bindings-architecture-unification sweep, grounded
in the breadth audit (findings F6, F7, F8). Phases 2.1-2.3 make the source-kind set,
the resolver contract, and the fold-in/carry value layer cohesive in TYPE and
STRUCTURE; phase 2.4 makes them cohesive in NAME, so a reader and a semantic search
land on one vocabulary.

The defect (audit F6/F7/F8):

- **F6 — pervasive homonyms make the surface grep-hostile.** `resolve`/`resolve_*`
  spans six unrelated meanings; `SourceKind` names four unrelated closed sets;
  `Observation` names 30+ types across unrelated domains with no discriminating prefix;
  `BindingRow` names four unrelated row types (`BindingRowPayload`, `BindingPreviewRowPayload`,
  `ModeloBindingRow`, `_BindingRow`); `prefill` spans three concepts; "provider" and
  "resolver" are used interchangeably for one role. Two false-friend filenames sit
  inside the registry binding package without being part of it (`_m232_row_bindings.py`
  — a CLI-row materialiser, not a binding family; `_sources.py` — a BOE corpus
  verifier, unrelated to binding source kinds).
- **F7 — the CLI forked the one aggregation path into three verbs.** "Produce the bound
  casilla values from sources" is spelled `bindings preview`, `calc pull --compute`, and
  `work calculate`, under two unrelated command groups; `bindings list` vs `preview`
  names the value-bearing verb after a UI gesture; the `pull` verb multiplexes four
  source-family channels with no naming parity to the resolver families.
- **F8 — residual type-erasure in the registry binding model.** `DataBindingDefinition.selector`
  is a free-form `Mapping` (typed only at validate-time, never at the schema), and
  `typed_enum` is a stringly-typed pointer to an enum class.

## Considerations

This phase is sequenced LAST because it renames and re-homes symbols that phases 2.1-2.3
introduce or settle: the one source-kind enum (2.1), the one resolver contract/envelope
(2.2), the one fold-in implementation (2.3). Doing the naming pass before those land
would rename moving targets. It is fenced to NAMING, CLI vocabulary, and the residual
`selector`/`typed_enum` typing; it makes no semantic or mechanism change.

The genuine `*SourceKind` HOMONYMS are reconciled here, not absorbed: `ModeloReconciliationSourceKind`
(reconcile transport), `BusinessOperationInvoiceSourceKind` (invoice direction), and
`IvaCompensationAuthoritySourceKind` (wallet authority) name different concepts that
merely share the suffix; each is either renamed to what it actually is or formally
documented as a distinct axis — never folded into `BindingSourceKind`. The oracle/wallet
"binding" name collisions are reconciled against `binding-names-reserved-for-registry-input`
(the term "binding" is reserved for the registry-data-input concept).

Project rules binding this: `binding-names-reserved-for-registry-input` (the naming
discipline this phase enforces), `aeat-cli-pull-and-file-standard` and the CLI-naming
ADRs (the verb surface this phase reconciles), `aeat-architecture-boundaries` (closed
sets are typed; the CLI gate is instructive), `core-struct-docstring-links` (renames keep
the docstring graph navigable), and `aeat-docs-scaffolding-cli` (every relocation
regenerates the API-reference stubs in the same atomic commit).

## Constraints

- **Sequenced last; depends on phases 2.1-2.3.** It renames symbols those phases settle,
  so execution follows them. Design-ahead only; lands no code.
- **Pure rename / re-home — behaviour-preserving by construction.** No semantic, type-value,
  or mechanism change; every relocation is an atomic explicit-path commit with the
  docs-scaffold + locale + API-stub regen in the same commit (per `aeat-docs-scaffolding-cli`,
  `aeat-architecture-boundaries` relocation atomicity), and the conformance gates
  (documented-command, json-schema, docstring-core-struct) stay green.
- **CLI verb changes are operator-visible and locale-bound.** Any verb rename sweeps the
  runtime write-policy allowlist, error-registry suggestions, next_action builders, and
  the curated operator help, and is authored through the locale CLI (per
  `aeat-cli-pull-and-file-standard`, `aeat-locales-cli`); a rename that updates only the
  registration leaves dead operator instructions.
- **The `selector` typing (F8) may be deferred.** Typing `DataBindingDefinition.selector`
  as a discriminated union is the largest residual and may split into its own follow-up
  if the rename pass is large; the ADR records it but does not force it into one landing.

## Implementation

A naming-discipline pass plus a CLI-verb reconciliation. Layering:

1. **Retire the `BindingRow` and `Observation` homonyms.** Give the four `*BindingRow`
   row types role-distinct names (CLI payload vs registry-query row vs calc-sheets row),
   and apply a discriminating prefix discipline to the `Observation` family so calc /
   ledger-aggregation / live-capture / oracle observations are distinguishable by name.
   Disambiguate the `resolve`/`provider`/`resolution` tangle so a symbol's name says
   whether it is the port, the output, or an aggregate.

2. **Re-home the false-friend filenames.** `_m232_row_bindings.py` (a CLI-row materialiser,
   not a `DataBindingDefinition` family) and `_sources.py` (a BOE corpus verifier) move
   out of / are renamed within the registry binding package so the "binding"/"source"
   names are load-bearing, per `binding-names-reserved-for-registry-input`.

3. **Reconcile the genuine `*SourceKind` homonyms and the "binding" collisions.** Rename
   `ModeloReconciliationSourceKind` / `BusinessOperationInvoiceSourceKind` /
   `IvaCompensationAuthoritySourceKind` to what they are (a reconcile transport, an
   invoice direction, a wallet authority) or document each as a distinct axis; reconcile
   the oracle/wallet "binding" name collisions against the reserved-term rule.

4. **Reconcile the CLI source-pull verb surface (F7).** Make "produce the bound casilla
   values from sources" one learnable verb story rather than three (`bindings preview` /
   `calc pull --compute` / `work calculate`), under the `aeat-cli-pull-and-file-standard`
   discipline; align the value-bearing verb name to what it sources and the `pull`
   channels to the resolver families.

5. **Type the residual registry fields (F8).** Replace the free-form
   `DataBindingDefinition.selector` `Mapping` with a typed discriminated union keyed by
   `BindingSourceKind` (the per-family selector models become the schema, not a
   validate-time overlay), and narrow `typed_enum` — or split this into a tracked
   follow-up if the rename pass is already large.

A `{reference}` document will pin the homonym sites, the false-friend files, and the CLI
verb anchors the plan edits.

## Rationale

Phases 2.1-2.3 make the engine cohesive in type and structure; if the NAMES still
overload (`BindingRow`×4, `Observation`×30+, `resolve` ×6, three CLI verbs for one path),
a reader and a semantic search still land on a scatter — the very RAG-incoherence the
goal targets, one altitude up. Naming is therefore not cosmetic here; it is the last
mile of "cohesive." Doing it last avoids renaming moving targets, and the project's
relocation-atomicity + docs/locale/API-stub regen discipline makes each rename safe and
gate-green.

## Consequences

Gains: the bindings vocabulary becomes load-bearing — one name per concept, one learnable
CLI verb story, the false-friend files re-homed, and the registry `selector` typed at the
schema. Combined with phases 2.1-2.3, the codebase delivers a cohesive bindings engine in
type, structure, AND name, so a semantic search for any binding/source/carry/CLI concept
returns one canonical answer.

Difficulties, framed honestly: rename blast radius is wide (import sites across layers,
the docstring graph, the API-reference stubs, the locale catalogues, the operator help)
and each must land atomically with its regen or it reds a peer's gate; CLI verb renames
are operator-visible and must sweep every instructive surface, not just the registration.
The `selector` typing is the largest residual and may defer. Execution depends on phases
2.1-2.3 and is sequenced last; this ADR is design-ahead and proposed — no completed
change, no acceptance ahead of coordinator review.

## Codification candidates

None new beyond the existing `binding-names-reserved-for-registry-input` (which this
phase ENFORCES across the remaining homonyms) and the CLI-standard rules. If the
`selector` discriminated-union typing proves a durable pattern worth binding, a
`binding-selector-is-a-typed-union` candidate is authored at phase-2.4 review/codify —
not now.

## Amendment — G2 transport/compute separation

This amendment sanctions, in scope, the one behaviour change G2 (W04.P07.S22) carries
beyond pure rename: splitting `config google sync calc pull --compute` into two sibling
verbs.

The verb shape is RULE-DETERMINED, not a free UX choice. `aeat-cli-pull-and-file-standard`
requires `pull` to mean "go read this from AEAT" — a TRANSPORT verb and nothing else.
`calc pull --compute` violated that: the `--compute` flag multiplexed the Sheets transport
(read operator-edited cells back from the workbook) with a compute step (run the shared
registry engine over those cells and display the result). A `pull` verb that also computes
is two intents under one word, the exact multiplexing the standard collapsed elsewhere.
Under the standard the only conforming design is a two-verb split, so the separation is
mandated by the rule, not chosen.

The split:

- **`calc pull`** keeps the Sheets TRANSPORT only — read operator-edited cells back from
  the workbook into typed records (operator/binding/relation edits, optional row-set
  assemblies). The `compute: bool` flag and its `_compute_pull_casillas` call are removed;
  the `computed` block leaves the pull payload.
- **`calc compute --spreadsheet-id <id>`** is a NEW sibling verb carrying the
  Sheets-roundtrip compute: pull the operator-edited cells, run the shared engine
  (`compute_from_pull` → `calculate_registry_snapshot`), and DISPLAY the computed casillas.
  It persists NOTHING — read-only by construction, refusing a stale workbook stamp exactly
  as `--compute` did.

The compute path is SHARED, not divergent. Both the former `--compute` and `work calculate`
terminate in `calculate_registry_snapshot`; this split does not fork the engine. What
`calc compute` preserves is the Sheets-INPUT compute that `work calculate` structurally
cannot do: `work calculate` computes from the bucket / local observation store and persists
a revision, whereas `calc compute` computes from the operator's edited Sheet cells and
persists nothing. The two are different INPUT sources into one engine, so retiring
`--compute` without `calc compute` would drop a capability — hence the new verb rather than
a bare flag removal.

Operator-surface sweep (per `aeat-cli-pull-and-file-standard`, the fail-open trap): the new
`config google sync calc compute` verb is added to the runtime write-policy allowlist
alongside the retained `config google sync calc pull`; the locale subtree
`cli.config.google.sync.calc.pull.compute_*` moves to `cli.config.google.sync.calc.compute.*`
and gains the verb help, authored only through the locale CLI; the `computed` payload moves
to a new `GoogleSyncCalcComputeResult` registered under `command="config.google.sync.calc.compute"`;
the how-to docs and the generated CLI reference are swept. The two conformance gates
(`test_documented_command_conformance.py`, `test_json_schema_conformance.py`) discover the
new verb from the live Typer tree once it is registered, schema-bound, and documented.

This is behaviour-affecting (a flag retires, a verb is born) and so is operator-visible and
carries a code-review obligation at phase close; it is recorded here so the in-scope
behaviour change is sanctioned rather than smuggled under "pure rename".


