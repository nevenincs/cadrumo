---
tags:
  - '#audit'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:100802097363a7ad98db718d011038a6f33961fe31c0f5625c80038c9ec0cb3b'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# `binding-schema` audit: `binding order gate, family identities, lift, 714 rename, predecessor cause, period overrides`

## Scope

Two read-only code reviews of the binding-schema lane, consolidated here as one record. The first covers the binding order-invariance gate and the family-identity authoring tool: `dev/registry/compiler/validate_bindings.py`, `dev/registry/compiler/validate_projection_endpoints.py`, `dev/registry/author_family_identities.py`, `src/cadrumo/domain/calculations/registry/export.py`, `src/cadrumo/domain/calculations/registry/m303_regimen_simplificado_annual_summary_bindings.py`, and `dev/registry/tests/test_binding_order_invariance.py`. The second covers four batches: the family source-default lift in `dev/registry/lift_family_source_defaults.py`, the modelo 714 identifier rename and record-design reads in `dev/registry/rename_formula_binding_identifiers.py` and `dev/registry/record_design_labels.py`, the predecessor-none root-cause ruling in `dev/registry/analysis/none_root_cause_ruling.py`, and the period-override selector together with its production consumers.

## Method

Read-only review: no source mutations and no version-control operations. Correctness was established by reading each production path whole and confirming symbols by targeted search, then by running the owning gates.

Gates run. `ruff check` over every reviewed module, clean throughout. `pytest` over the three order-gate and identity test files: 119 passed, 61 skipped, the skips being honest "this modelo declares no such binding" guards. `pytest -m '' -n 0` over the lift and 714 residual-naming suites: 26 passed, 1 failed, that failure being the live reproduction of HIGH-1. `pytest` over the period-override and predecessor-cause suites: pass. A live `load_modelo_directory` over modelo 714 loads with five revisions. A live corpus sweep reports 2460 projection endpoints, zero casilla-only projection refs, zero cross-edition casilla drift under one id, and zero duplicate full refs. The modelo 303 and 720 refusal teeth were exercised against real copied modelo trees through the real loader rather than a substitute.

Two pre-existing breakages were observed and are not attributable to the reviewed work: a bundled published-authority artifact one schema version behind its reader, erroring every test that reads published authority, and a `NameError` from an in-flight edit at `dev/registry/tests/test_export_projection_refs.py:372`.

## Findings

| id | severity | location | status |
|---|---|---|---|
| F1 | high | `dev/registry/author_family_identities.py:194` | fixed |
| F2 | high | `src/cadrumo/domain/calculations/registry/export.py:115` | fixed |
| F3 | medium | `dev/registry/tests/test_binding_order_invariance.py:218` | fixed |
| F4 | medium | `dev/registry/tests/test_binding_order_invariance.py:54` | fixed: public `prorrata_source_casilla_ids` in `src/cadrumo/domain/calculations/registry/prorrata_regularizacion_bindings.py` |
| F5 | medium | `dev/registry/compiler/validate_bindings.py:189` | fixed |
| F6 | medium | `dev/registry/compiler/validate_projection_endpoints.py:76` | resolved, branch retained |
| F7 | medium | `dev/registry/author_family_identities.py:80` | open observation |
| F8 | medium | `src/cadrumo/domain/calculations/registry/m303_regimen_simplificado_annual_summary_bindings.py:43` | open observation |
| F9 | low | `dev/registry/compiler/validate_bindings.py:31` | fixed |
| F10 | low | `dev/registry/author_family_identities.py:83` | fixed |
| HIGH-1 | high | `dev/registry/lift_family_source_defaults.py:727` | fixed |
| HIGH-2 | high | `dev/registry/analysis/none_root_cause_ruling.py:30` | in progress |
| HIGH-3 | high | `src/cadrumo/application/filing/runtime.py:718` | in progress |
| MEDIUM-1 | medium | `dev/registry/rename_formula_binding_identifiers.py:2932` | fixed |
| MEDIUM-2 | medium | `dev/registry/tests/test_modelo_714_residual_naming.py:143` | fixed |
| MEDIUM-3 | medium | `dev/registry/lift_family_source_defaults.py:118` | fixed |
| MEDIUM-4 | medium | `dev/registry/rename_formula_binding_identifiers.py:2508` | fixed |
| LOW-1 | low | `dev/registry/record_design_labels.py:236` | fixed |
| LOW-2 | low | `dev/registry/rename_formula_binding_identifiers.py:3220` | fixed |

### order-gate-annotation | high | an added annotation turned the type gate red

A `dict[str, object]` annotation over a TOML parse result introduced an unsound-assignment error the prior state did not carry. The scenario is misattribution: the type gate goes red on an unrelated later change and the cause is hunted in the wrong place. Fixed.

### export-surface | high | a public accessor documented a coupling that does not exist

`claimed_export_binding_records` was promoted to the public surface on the stated grounds that the order gate consumes the same eligibility set. The gate deliberately keys on the declared selector instead and says so at `dev/registry/compiler/validate_bindings.py:170`, leaving a public symbol with a single caller and an untrue docstring. A reader trusting that docstring could narrow the gate to export-claimed records and silently remove the refusal for the unclaimed records it was written to cover. Reverted to the private name and the export entry dropped in the same change that stopped needing it.

### gate-copy | medium | the invariance suite asserted a verbatim copy of the gate

Two row-slot tests reimplemented the duplicate-row-field predicate rather than calling it, using the same filter, the same selector extraction and the same key. A production narrowing of the key would have left the suite green and only the separate refusal file would have caught it. Fixed by exercising the production predicate.

### private-import | medium | a dev test reaches a private application helper

The ordered prorrata source helper is imported across a package boundary from `src/cadrumo/application/calculations/prorrata_regularizacion.py:176`, which the import-boundary rule admits only for canonical public definitions. The preferred fix is not a new accessor invented for the test: the ordered source tuple is already public on the provenance record at `prorrata_regularizacion.py:617` and on the result at `:812` and `:832`, and asserting through one of those proves the invariant where a consumer actually reads it. Carrying that through requires live repositories this test does not construct today, so the private import is retained with a comment naming the intended public carrier. A knowing, bounded exception that should close when the fixture cost is paid.

### selector-shape | medium | a malformed selector left the uniqueness check silently

A row binding whose selector carried a non-string record or row field was continued past the uniqueness check with no advisory, collapsing "unknown shape" into "proven unique". A selector schema change making the row field an enum would have emptied the refusal corpus-wide while the copied invariance test stayed green for the same reason. The unparseable selector is now refused.

### projection-branch | medium | the duplicate-endpoint branch is still reachable

The admitted-by-several-declarations branch was proposed for deletion as dead. It is not. The endpoint index keys on the whole projection ref, identity-keyed family validation refuses only duplicate authored ids, and nothing at load validates an authored id against the derivation, which is used only by the authoring tool and two tests. Two declarations sharing a projection ref under distinct hand-written ids therefore compile, and this branch is the only thing that catches them. Retained.

### continuity-axis | medium | excluding casilla identity from continuity is unguarded

No false continuity is possible on the present corpus: every projection ref carrying a casilla also carries slot and field, 366 of 2460 with no casilla-only refs, so identity stays discriminating, and no id moves its casilla across editions today. The residual scenario is a later edition reusing the same kind, slot and field label for a legally different concept while renumbering the box; the successor then inherits predecessor grounding silently, because the only axis that changed is the excluded one. No gate covers it. A coverage note at the identity construction, or a continuity check flagging an id whose casilla moves across editions without a stated evolution, would close it. Open.

### regulatory-constant | medium | a closed casilla set is hardcoded in domain code

The annual-summary casilla set is a regulatory constant held in production domain code where registry authority directs it to typed registry fields. It is pre-existing in weaker form and the new form is strictly safer, since it also detects a short map, but the closed set must now be hand-edited if a future record design moves the annual-summary block. Open.

### lift-rollback | high | the cap gate parsed outside the rollback guard

The cap refusal parsed the manifest before the baseline load and before the rollback guard, so a manifest that does not parse raised a raw decode error instead of the documented lift failure. Reproduced live: a duplicate revision table aborts with an unhandled parser traceback, and the contract that a failed lift never leaves a half-written tree was no longer proven by its own gate. Fixed by bringing the cap loop inside the guard.

### ruling-table | high | the root-cause ruling table is stale and guarded by a frozen count

The ruling names twenty-nine roots where the live corpus declares twenty-eight; one entry gained a declared predecessor at `src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/revision.toml:3`. Entry selection tests only that the manifest text contains the word predecessor, which a declared predecessor also satisfies, so the ruling can emit a cause for a named predecessor edge. That is refused at the typed boundary and so fails closed, but noisily and late. The expected-root count is a frozen corpus count, which the quality-gate rule excludes as a gate. The remedy is to derive the root set from the loader, as the census survey already does, refuse any row that is not a live no-predecessor root, and drop the count. Twenty-six of the twenty-eight roots still carry no cause; the census reports them as unclassified rather than coercing them, which is correct. In progress.

### period-overrides | high | filing-grade consumers still read the flat period tuple

The year-aware period accessors landed correctly across the query, temporal, fact-resolution, snapshot and support modules, but several production sites did not move. `src/cadrumo/application/filing/runtime.py:718` takes the first flat token with the filing year in hand, and `:796` passes the steady-state tuple off a snapshot that knows its year. The same year-known pattern persists at `src/cadrumo/application/modelo/binding_readiness.py:202`, `src/cadrumo/application/modelo/m145_communication.py:101` and `src/cadrumo/application/calculations/cross_period_clean_state.py:201`. Year-less inventories at `src/cadrumo/application/modelo/registry_discovery.py:61` and `src/cadrumo/domain/calculations/registry/censo_modelos.py:163` under-declare an override-only token, as do validators at `dev/registry/compiler/_validate_dependency_sections.py:121`, `dev/registry/compiler/_validate_previous_filing_sources.py:93` and `dev/registry/conformance/external_grounding.py:188`. In an override year whose surface drops the first flat token, the runtime picks a period the edition does not file in that year and stamps it onto the filing handoff. Latent today because no corpus revision declares overrides, which is exactly why it must close before the first one is authored: nothing fails loudly, the wrong period simply flows into a filing. In progress.

### evolution-provenance | medium | evolution source refs were spelled, not read

Emitted identifier evolutions built their design source refs from a naming pattern while the sibling legal refs were read from the manifest. The pattern holds for modelo 714, whose design sources exist, but the corpus also spells design sources with a version suffix; applied to such a modelo the tool would emit a fragment citing a source that does not exist. Registry validation catches it, so the outcome is fail-closed, but the tool wrote a file it could not stand behind. Fixed by resolving the design source id off each edition's own declared refs, the chain the tool already walks. Provenance is read, not spelled.

### parity-fixture | medium | the evolutions parity test compared a fixture to itself

The test claimed a byte-for-byte comparison against the artefact the corpus carries but compared against the test fixture. The two are byte identical today, so the committed corpus fragment was ungated and a hand-edit to it would have passed the suite. Fixed by asserting against the corpus path as well.

### import-root | medium | an import-time path mutation

The lift module inserted the source root onto the import path as a module-import side effect in order to reach the domain package. Its own test imports the same symbol at top level with no such hack, so the source root is already importable in the project environment. This is the ad-hoc import root the architecture rule forbids and it silently shadows an installed distribution. Fixed.

### contested-names | medium | the fallback did not re-check its own result

A contested identifier strip was re-pointed at an ordinal name without checking that the ordinal name was unclaimed and without updating the holder set. Downstream collision withdrawal catches it, projected over the full inventory and refusing the modelo whole, so the outcome is safe; the cost is a refused modelo where a second resolution round would have succeeded. Fixed.

### docstring-drift | low | two stale prose claims

The validation module header undercounted its own refusals after two were added, still describing the unreferenced-binding advisory as the fifth check when it is the seventh. Separately, the record-design docstring claimed an edition citing no readable design is simply absent from the result, when the sidecar read raises on a digest mismatch or missing file and that propagates out of the loop. Failing closed is right and both texts were corrected. A secondary observation stands: the caller catches that error and degrades the whole modelo to mechanical rules, so one unreadable edition suppresses designs for every edition.

### cleanup-abort | low | directory cleanup aborted on the first unowned empty directory

The emptied-fragment cleanup raised inside its loop, so an unrelated pre-existing empty directory anywhere under the modelo prevented removal of the directories the pass legitimately emptied, while leaving earlier removals applied. Fixed by collecting and reporting at the end. The ownership proof itself is sound and strictly better than an index check.

### redundant-casts | low | casts where narrowing already applies

Eight casts were added where an instance check already narrows. They buy nothing and are the likely reason the offending annotation appeared. Removed.

## Verdicts

Binding order-invariance gate: fix-first at review, ship after remediation. Both new refusals are correct and carry real teeth. The prorrata refusal addresses a genuine order dependency, since the source ids concatenate across every prorrata binding with first occurrence winning, so the positional role reads depend on fragment merge order; the refusal fires on two or more and names both ids. Its planted-duplicate test compiles a copy of the live modelo 303 tree with a real appended declaration through the real loader, the bundled corpus untouched, and asserts the clean path in the same file, while the invariance suite additionally proves the duplicate is visible. The row-field key matches what the resolver dedups on, and checking the declared selector rather than the export projection is a deliberate and correct widening. Its teeth include the negative half, six legitimate row bindings on one record that must pass, which is exactly what would catch a check keyed per record instead of per slot.

Family identities: ship. The annual-summary re-key is the strongest part of the work. The prior code assigned boxes by dictionary insertion order and would have accepted a short map as complete; the new code holds each endpoint to its own declared number and adds exact coverage of the closed set. It is proven meaning-preserving on every live revision of the corpus that declares the requirement, ten boxes each, with the earliest declaring none.

Family source-default lift: fix-first at review, ship after remediation. The byte-identical materialisation test is real, driving the real loader over a real copied modelo and comparing every member's materialised source refs before and after, with a companion comparing raw bytes per file; neither restates the tool's own rule. A carried declaration cannot land on a no-predecessor edition, because carries come only from the successor map, which is keyed on a declared predecessor string that a none table never produces. The carried provenance comment survives this tool's later manifest writes, since the lift touches only source-ref lines inside member tables and a later default insert lands above the existing comment and key pair. It is a comment rather than a schema field, so nothing outside the tool enforces the pairing.

714 rename and record designs: ship with follow-ups, all now closed. Sidecar encoding is correct and deliberate, pinned to strict decoding against a named legacy defect and additionally gated on the declared digest of the binary beside it. The ordinal fallback is deterministic, read from the design's own field table and edition-scoped in step with the edition-scoped rewrite. The identifier length cap is read from the type rather than restated, and raises when the type declares none. The emitted rows validate through the real discriminated union with distinct identifiers, and the live tree loads with five revisions.

Predecessor cause: fix-first, remediation in progress. The unknown-code refusal is a real tooth: it drives the real loader over an on-disk tree, asserts the load reds on a bad token, repairs the same tree and asserts it greens. Wrong case, stray spaces, a retired spelling and empty are all refused rather than normalised, and a cause on a named predecessor edge is refused too. The per-root classification table lives in a development module rather than in the registry, acceptable only as the migration scaffolding it declares itself to be, with the stated deletion condition.

Period overrides: fix-first, remediation in progress. The inheritance-time selector reimplementation at `dev/registry/compiler/_loader_internals.py:392` is clean and deliberate, honouring an override entry against the raw table because inheritance runs before typed construction; the duplication is documented and the two copies currently agree. It remains a second copy of a rule and needs a parity test against the typed method.

## Source-window citations on modelo 303

The refusal "cites sources outside their applicability window" is raised by `src/cadrumo/domain/calculations/registry/snapshot.py:781` through `SourceReference.applies_across`, which delegates to `source_window_applies_across` in `src/cadrumo/domain/calculations/registry/schema_references.py:595`: one overlap rule in one home, with the deadline-window escape as the only addition. The 303 refusals are six sites on two sources (`boe-orden-hfp-1172-2022-iva-authority`, `boe-orden-hfp-1359-2023-iva-authority`) carried by `m303-regimen-simplificado-fact` projection endpoints authored under the 2023 revision and inherited into 2024-hasta-08-y-2t, 2024-desde-09-y-3t, 2025 and 2026-y-siguientes. Decision: an inherited member carries the refs it states; explicit refs outside the inheriting revision's window are a re-grounding decision for that revision (restate under its own default, or declare an evolution), never a silent carry-forward exemption. The refusals are correct data debt on modelo 303, listed for its owner; no code change.

## Residual risk

The two in-progress high findings are the live exposure. Until the ruling derives its root set from the loader, a stale row can drive a cause onto a named predecessor edge, caught only late at the typed boundary, and a frozen count stands in for a semantic gate. Until the year-aware accessors reach the filing runtime and the remaining consumers, the first authored period override will stamp a period the edition does not file onto a filing handoff with nothing failing loudly; the fix must land before that first override is authored.

Three accepted items remain. The private import across the application boundary is a knowing exception that should close when the test can construct live repositories. The unguarded continuity axis admits a successor inheriting predecessor grounding when a later edition reuses a label for a legally different concept while renumbering the box, and no gate covers it. The hardcoded annual-summary casilla set must be hand-edited if a future record design moves the block, where a typed registry field would carry it.

Two smaller follow-ups stand outside the finding table: the loader-time selector reimplementation needs a parity test against the typed method, and one unreadable record-design edition still degrades designs for an entire modelo.
