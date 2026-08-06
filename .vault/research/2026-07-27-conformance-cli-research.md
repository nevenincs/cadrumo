---
tags:
  - '#research'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:b01922f3ab2c68c238c2528f576815b07e09ccda2822bab0aa7267f689ddef98'
related:
  - '[[2026-07-01-verification-power-adr]]'
  - '[[2026-07-01-verification-contract-coverage-audit]]'
  - '[[2026-07-02-arch-remediation-registry-format-adr]]'
  - '[[2026-06-14-legal-grounding-centralization-audit]]'
  - '[[2026-05-14-legal-grounding-audit-reference]]'
  - '[[2026-04-25-aeat-verify-audit]]'
  - '[[2026-04-21-casilla-schema-completeness-adr]]'
  - '[[2026-06-30-obligation-coverage-completeness-adr]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-07-12-calculation-truth-registry-classification-review-audit]]'
  - '[[2026-06-30-modelo-verify-nonzero-guards-research]]'
  - '[[2026-07-03-registry-grounding-spotcheck-audit]]'
---

# `conformance-cli` research: `modelo schema conformance governance mini-CLI`

The question: how should a mini-CLI that reviews and governs conformance of the
modelo schemas — deducing per-modelo/per-revision status, drift, coding rigour,
review provenance, and enforcement posture across 73 modelo directories, 90
revisions, ~15,774 casillas, 567 legal entries, and 67 fixture sidecars — be
shaped, placed, and grounded? The stakes: today no per-modelo status scalar
exists anywhere; status is deduced by scattered folds and pytest gates, review
provenance is unstructured prose on one catalogue only, and prior per-modelo
coverage tables were one-shot audit artefacts that rotted on landing. The
evidence picture: (a) a large majority of the conformance facts the tool needs
are ALREADY importable library functions — the strongest being
`audit_registry_model_law_coverage` — so a first useful `report` verb needs
zero new fact computation; (b) four high-value fact sets are trapped inside
pytest modules and need lifting; (c) house precedent is unambiguous on shape (a
`python -m` Typer trio outside the two `aeat` roots, screen-vs-gate declared
explicitly, anti-vacuity refusals); (d) the genuinely new ground is a declared
status/provenance layer — `engineered_by` exists nowhere, `review_status` is a
degenerate `Literal["reviewed"]`, and several governance axes are
declared-but-dead. The ADR must settle placement, the declared-vs-derived
status boundary, the provenance stamp schema, and the gate posture.

## Findings

### No declared per-modelo status exists; every status today is a derived fold

`manifest.toml` and `revision.toml` carry zero review-provenance or lifecycle
fields (`src/cadrumo/domain/calculations/registry/_schema.py:1278`, `:1226`).
The only per-modelo state machine is the access-gate `AuthorizationState`
(`unauthorized`/`authorized`, `src/cadrumo/core/access_gate/_authorization.py:81`),
derived default-deny from `authorization.d/*.toml` (30 of 73 modelos
authorized, with a declared `EnrollmentEvidenceClass` of
`calculation`/`reconciliation`/`data_fidelity`/`threshold_continuity`,
`_authorization.py:94`). Everything else a governance frontend needs is
derivable only: calc-grade closure
(`registry/_record_design_coverage.py:148`), evidence-tier coverage gates
(`registry/_coverage.py:90`), Diseño coverage gap
(`_record_design_coverage.py:478`), cross-revision drift
(`registry/_cross_revision_divergence.py`), `is_deprecated`
(`registry/_support_matrix.py:203`, always False — see dead axes below), and
`independently_grounded_fraction`
(`src/cadrumo/application/verification/_verify.py:192`, per-verdict only).
This declared-vs-derived split is the central design axis: the CLI can either
keep status purely derived (always honest, never stale, but recomputed each
run) or add a declared status layer to registry TOML (reviewable, but a new
drift surface the tool itself must then police).

### Review provenance exists only on the legal catalogue, as unstructured prose

`review_status`/`reviewed_at`/`reviewed_by`/`notes` exist solely on
`LegalReference` (567 entries), `SourceReference` (306, status only), and
`LegalParameter` (11) in `legal/*.toml`
(`src/cadrumo/domain/calculations/registry/_schema_references.py:115-118`,
`:162`, `:207-210`). `ReviewStatus` is the degenerate `Literal["reviewed"]`
(`_schema_base.py:59`) — an unreviewed branch is structurally unreachable
(`registry/_legal.py:35-39`). `reviewed_by` is free text: ~204 `"operator"`,
~117 `"agent-review"`, ~130+ carrying `pending operator re-stamp` /
`operator to re-stamp` substrings — a de-facto un-restamped backlog minable
only by prose-parsing. The field contract (reviewed means operator signoff,
never falsely stamped) is recorded in `2026-05-14-legal-grounding-audit-reference`;
the agent-vs-operator stamping practice and the honest agent-authored
precedent in `2026-06-14-legal-grounding-centralization-audit`. No
`engineered_by` field exists anywhere in registry data; the only other
provenance key in-tree is `definition_reviewed_by: "operator"` in
`src/cadrumo/_data/corpus/manuals/iva/*/structure/*.json`. Casillas,
revisions, and manifests carry no review fields at all — so the
reviewed-by/engineered-by axis the governance surface wants is, for the
schema tree itself, entirely new schema work.

### Classification axes exist but disagree, and several schema axes are dead

The filed/informative/non-filing partition is spread over four
non-agreeing homes: `calculation_class` (`Literal["filing","informative","summary"]`,
`_schema.py:1285`; 11 informative, `summary` used zero times — Modelo 390
defaults to `filing` despite being the canonical summary); `tax_domain`
(17 modelos carry the `informative` domain — overlapping but NOT equal to the
11 `calculation_class` informatives, a live drift signal); the Python-side
`NON_REGISTRY_MODELOS` / `UNMODELED_OBLIGATIONS` (80 reasons) /
`OUT_OF_SCOPE_OBLIGATIONS` constants (`src/cadrumo/core/_modelo.py:340-358`);
and per-dependency `taxpayer_files_source` / `conditional_on_economic_activity`
(`_schema.py:622`, `:634`). Declared-but-dead axes a conformance report must
surface as unused rather than passing: `calculation_class="summary"` (0),
`SupportRemovalDecisionDefinition` (0 declarations, hence `is_deprecated`
always False), extraction `confidence="review_required"` (0 — all 43 profiles
`"strict"`), `verification_source="real_aeat_corpus_pdf"` (0),
`completeness_manifest.manual_extraction=true` (0), fixture
`provenance="real_corpus"` (0, asserted by
`adapters/inbound/sanitizer/tests/test_residual_identity_absence.py:118-121`).
The stale fleet-size comment at `core/access_gate/_authorization.py:69` is
itself a small drift specimen.

### Rigour signals are rich but unevenly declared

Grounding presence is universal (`legal_refs`/`source_refs` are
`min_length=1` on every registry model, `_schema_base.py:67-68`), so rigour
must be measured by breadth/specificity, never presence. The sharpest
declared discriminators: `externally_grounded_casilla_ids` (11 files across
7 modelos only: 100, 200, 202, 303, 322, 353, 390; `_schema.py:433`);
verification expectations (34 of 73 modelos); completeness manifests (16 of
73); extraction profiles (20 of 73, with per-profile
`corpus_round_trip_verified` and `provisional_pending_specimen`,
`_schema_extraction.py:93-106`); oracle corpora (16 manual-oracle JSONs + 5
renta-web-open replays under `src/cadrumo/_data/corpus/`); and fixture
sidecars (60 `synthetic_generated`, 7 `aeat_published_facsimile`, roles
`formula_verification`/`parser_anchor`/`casilla_value_oracle`, no pydantic
model — gate-validated only). Per-modelo calc-grade census evidence already
exists in `2026-06-30-modelo-verify-nonzero-guards-research` (predicates on
6 of ~12 calc-grade modelos). The four-tier evidence model any rigour score
must key off is decided in `2026-05-04-calculation-authority-evidence-tiering-adr`;
the required-tier fold is `_coverage.py:26-32`.

### Most conformance facts are already importable; four are test-trapped

Importable today, composable into a first `report` verb with zero new fact
computation: `audit_registry_model_law_coverage` /
`build_model_law_coverage_ledger` (walks every modelo × revision, builds
validated snapshots, emits per-tier gap ledger with `.ok`;
`registry/_coverage.py:90`, `:143`); `build_support_matrix`
(`registry/_support_matrix.py:265` — but note it probes the LATEST revision
only, `:60`); `build_capability_matrix` (`dev/registry/matrix/manager.py:127`);
`inspect_registry_tree` / `verify_registry_tree` / `audit_registry_oracles`
(`src/cadrumo/application/registry/__init__.py:368`, `:374`, `:421` — already
CLI-surfaced at `aeat app registry inspect/verify/audit-oracles`,
`src/cadrumo/entrypoints/cli/registry.py:162-244`);
`validate_registry_scope` (`registry/_validate_registry_scope.py:31`,
accumulating diagnostics); `validate_binding_selector_shape`
(`registry/_bindings.py:986`); `ModeloLocaleManager.coverage_records`
(`src/cadrumo/locales/_modelo_manager.py:364`); `build_obligation_coverage`
(`src/cadrumo/application/overview/_coverage.py:126`). Test-trapped fact sets
worth lifting, in value order: (1) the external-oracle grounding inventory
and both-direction honesty check — there is NO registry-wide
`independently_grounded_fraction` anywhere, only the per-verdict one
(`registry/tests/test_external_oracle_grounding_enrolled.py:57-227`); (2) the
fichero-BOE covered-modelo table and required-applicable derivation
(`application/filing/tests/test_fichero_boe_completeness_parity.py:59`,
duplicated at `test_export_completeness_gate.py:69` which admits "Mirror the
gate's required set"); (3) locale honesty detectors + ceiling ratchets
(`src/cadrumo/tests/test_locale_translation_honesty.py:41-129`); (4) the
anti-vacuity floor + shrink-only JSON baseline idiom of
`entrypoints/cli/tests/test_documented_command_conformance.py:517`, `:783`.
Enumeration API: `ValidatedRegistryAuthority` (`registry/_authority.py:45`,
zero-arg `bundled_authority()` `:244`); the non-validating
`load_registry_tree` survives concurrent peer registry churn
(used by `test_external_oracle_grounding_enrolled.py:50`).

### Placement precedent: a `python -m` Typer trio outside the two `aeat` roots

The `aeat` root surface is contractually two families
(`ACCEPTED_ROOTS`, `src/cadrumo/application/operator_surface/_contract.py:39`;
rule `aeat-architecture-boundaries`), and every dev/governance CLI in-tree is
a `python -m` module CLI: `dev.docs.apidocs`, `cadrumo.locales`,
`dev.docs.terminology_handbook`, `dev.registry.matrix`,
`dev.registry.newmodelo`, `dev.docs.sequences`. The house shape is the trio
`__main__.py` → thin Typer `cli.py` → pure `manager.py`, verbs
`report [--json]` / `audit` / `scaffold --check` / `coverage`, greppable
`key=value` output rows, `typer.Exit(1)` only on declared gate verbs. The
terminology CLI's docstring (`dev/docs/terminology_handbook/cli.py:1-22`)
explicitly frames itself as the precedent paragraph for exactly this case,
including the two-roots non-impact statement. The screen-vs-gate doctrine is
stated at `dev/audit/legal_attribution_screen.py:26-31` (report exits 0 while
a known-wrong worklist exists; promote to a gate once empty), and the
vacuity refusal at `:184` (`SystemExit` when the input set is empty).
Import hygiene enforces the dev/product boundary — shipped modules must not
import `dev.*` (`dev/import_hygiene_scan.py:372`, `:460`) — so any fact
computation the product also needs must live under `src/cadrumo/`, with
`dev/` holding only the rendering shell. Counter-consideration for the ADR:
the user intent includes agents driving information gathering, and an
`aeat app registry ...` extension would give them the typed JSON envelope +
notices contract and operator-harness citability
(`operator-harness-cites-live-cli-surface`), at the cost of making governance
tooling an operator-facing product surface. `aeat app registry` already
carries eight read-only verbs (`entrypoints/cli/registry.py:162-530`), so a
hybrid is viable without a third root.

### Prior art is one-shot; the cautionary precedents are decided law

Closest prior art: the 21×4 modelo coverage matrix in
`2026-04-25-aeat-verify-audit` and the per-modelo `semantic_role` coverage
table in the schema-hardening enrollment queue audit — both one-shot vault
tables that no tool keeps current. The schema-complete bar per modelo is
already published (`2026-04-21-casilla-schema-completeness-adr`); the
obligation-coverage invariant and the informativas catalogue framing in
`2026-06-30-obligation-coverage-completeness-adr`. Three decided constraints
bind the design: (1) `independently_grounded_fraction` must be surfaced as
coverage-of-independent-checking, never a correctness score
(`2026-07-01-verification-power-adr`); (2) enrollment is calibrated design,
not a mechanical sweep — mechanically enrolling all computed casillas would
flip M100 VERIFIED→NEEDS_REVIEW
(`2026-07-01-verification-contract-coverage-audit`); (3) a derived status
index is discovery evidence, never authority to act
(`2026-07-12-calculation-truth-registry-classification-review-audit`). The
fragmented-only registry convergence
(`2026-07-02-arch-remediation-registry-format-adr`) exists precisely because
subdirectory-blind tooling produced wrong "parse-only" verdicts twice; the
conformance CLI must read the LOADED snapshot, never `ls` fragment dirs. The
grounding spot-check audit frames itself as sampling and invites "a fuller
per-modelo grounding review" (`2026-07-03-registry-grounding-spotcheck-audit`)
— the standing demand this tool answers.

### Option space for the ADR

Option A — `dev/registry/conformance/` Typer trio (report/audit/coverage
verbs) composing the importable facts, per the matrix/terminology precedent.
Cheapest to land, honest screen-first posture, no product-surface impact;
but not envelope-typed and not citable by the operator harness.
Option B — extend `aeat app registry` with governance verbs. Typed envelope,
notices, agent-operable through the product contract; but grows an
operator-facing surface with contributor-governance concerns and binds every
verb to docs/locale/schema conformance gates.
Option C (the shape the evidence favors) — hybrid: lift the test-trapped
facts into importable fact-builders under `src/cadrumo/` (the coverage-audit
pattern), add a `dev/registry/conformance` rendering CLI for
contributor/agent governance including any declared-status authoring, and
optionally surface the read-only roll-up through the existing
`aeat app registry` family later. Orthogonal decisions the ADR must settle
regardless of placement: whether to introduce declared review/engineering
provenance fields on modelo/revision/casilla records (and their stamp
vocabulary — the degenerate `Literal["reviewed"]` cannot carry a pending
state); whether the un-restamped legal backlog gets a structured field or
stays prose-mined; drift-ratchet mechanics (shrink-only JSON baselines per
the documented-command idiom vs live recomputation); which facts get gate
teeth vs screen status; and the JSON output contract agents consume.

### Not investigated

Live behaviour of the eight existing `aeat app registry` verbs (shapes read
from source only); the `docs/_sequences` runner interaction; performance of
a full 90-revision validated-snapshot fold on this machine (the coverage
audit already does it in CI, cost unmeasured here); Google-Sheets/export
mirroring of any governance report.

## Sources

- `src/cadrumo/domain/calculations/registry/_schema.py:219,403,429-443,512-542,618-634,1226,1265-1287,1314-1341`
- `src/cadrumo/domain/calculations/registry/_schema_base.py:45-68,127-137`
- `src/cadrumo/domain/calculations/registry/_schema_references.py:88-210`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:202,357,398-433`
- `src/cadrumo/domain/calculations/registry/_schema_extraction.py:81-106`
- `src/cadrumo/domain/calculations/registry/_coverage.py:25-143`
- `src/cadrumo/domain/calculations/registry/_support_matrix.py:60,142-265`
- `src/cadrumo/domain/calculations/registry/_record_design_coverage.py:148,303,478-504`
- `src/cadrumo/domain/calculations/registry/_authority.py:45-260`
- `src/cadrumo/domain/calculations/registry/_validate_registry_scope.py:31`
- `src/cadrumo/domain/calculations/registry/_bindings.py:944-986`
- `src/cadrumo/domain/calculations/registry/_legal.py:26-80`
- `src/cadrumo/domain/calculations/registry/tests/test_external_oracle_grounding_enrolled.py:50-227`
- `src/cadrumo/core/_modelo.py:340-358`
- `src/cadrumo/core/access_gate/_authorization.py:69-206`
- `src/cadrumo/application/registry/__init__.py:224-421`
- `src/cadrumo/application/verification/_verify.py:191-192`
- `src/cadrumo/application/verification/_schema.py:121-142`
- `src/cadrumo/application/overview/_coverage.py:83-126`
- `src/cadrumo/application/operator_surface/_contract.py:39-534`
- `src/cadrumo/application/filing/tests/test_fichero_boe_completeness_parity.py:59`
- `src/cadrumo/application/filing/tests/test_export_completeness_gate.py:69`
- `src/cadrumo/entrypoints/cli/registry.py:162-530`
- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py:49-1074`
- `src/cadrumo/tests/test_locale_translation_honesty.py:41-241`
- `src/cadrumo/locales/_modelo_manager.py:178-364`
- `src/cadrumo/locales/cli.py:193-373`
- `dev/docs/terminology_handbook/cli.py:1-186`
- `dev/registry/matrix/manager.py:46-147`
- `dev/registry/newmodelo/checklist.py:32`
- `dev/audit/legal_attribution_screen.py:26-196`
- `dev/import_hygiene_scan.py:372,460`
- `adapters/inbound/sanitizer/tests/test_residual_identity_absence.py:83-121` (under `src/cadrumo/`)
- `src/cadrumo/_data/corpus/manual_oracles/` (16 files), `src/cadrumo/_data/corpus/parity_replays/renta_web_open/` (5 files)
- Counts (73 modelos / 90 revisions / ~15,774 casillas / 567+306+11 legal-catalogue entries / 30 authorizations / 67 sidecars) — swept 2026-07-27 from the working tree; re-derive before relying on exact figures.
