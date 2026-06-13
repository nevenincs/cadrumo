---
tags:
  - '#research'
  - '#linkage-design-audit'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
  - "[[2026-05-17-linkage-design-audit-plan]]"
  - "[[2026-05-18-linkage-design-audit-audit]]"
---

# `linkage-design-audit` research: `casilla-values-collapse-hash-stability`

Pre-flight research for `linkage-design-audit` plan step `P02.S09`
(collapse `CalculationRevision.casilla_values` into a derived
projection over the typed `observations` envelope). The collapse is
constrained by content-addressed identity: `derive_calculation_revision_id`
emits a SHA-256 hash whose payload includes a `casilla_values`
projection. Every already-persisted revision id was derived against
the current payload shape; any change must preserve byte-identical
hashes or every catalogue row mismatches its derived id and the
content-addressing invariant breaks.

## Findings

### Current hash payload shape

The hash payload at `src/aeat/domain/modelos/_calculation_revision.py:135`
is a deterministic JSON object built from seven inputs:

- `work_unit_id`: trimmed string
- `inputs`: sorted dict of trimmed-key trimmed-value strings
- `overrides`: sorted dict of trimmed-key trimmed-value strings
- `outputs`: sorted dict of trimmed-key canonical-Decimal strings —
  this is the projection of `casilla_values`
- `source_transaction_ids`: sorted tuple of trimmed strings
- `borrador_snapshot_id`: trimmed string, conditionally present
- `bindings_sourced_from_borrador`: sorted tuple of trimmed strings,
  conditionally present

The `outputs` projection is built inline in the function:
`dict(sorted((k.strip(), _canonical_decimal(v)) for k, v in casilla_values.items()))`.
The `_canonical_decimal` helper at `_calculation_revision.py:155` is
a pure function over `Decimal`.

### Hash-stability pin (anti-tautology proof)

Landed at `_calculation_revision.py:test_revision_id_pinned_against_fully_populated_fixture`
(P08.S35). Pins SHA-256
`5b78dd04e614a50fe448439b7fdb843f1e31afe76f9d424d0276866679dee7ca`
for a fully-populated derivation. Any future change to the hash
domain — whether intentional migration or accidental drift — fails
this pin.

### Storage shape today

`CalculationRevision` at `_calculation_revision.py:204` carries two
fields after the dual-write campaign:

- `casilla_values: Mapping[str, Decimal]` — flat persisted mapping,
  drives the hash via the `outputs` projection above.
- `observations: tuple[CasillaObservation, ...]` — typed envelope
  with full formula provenance; default-factory empty for
  backward-compat with revisions persisted before the typed envelope
  landed.

`RegistryModeloObservation` at `_bindings.py:117-127` already
demonstrates the canonical collapse pattern: typed `observations`
tuple is canonical storage; `casilla_values` is a derived `@property`
materialising `{obs.casilla_id: obs.value for obs in observations}`.
The same pattern landed on `RegistryCalculationResult` in P02.S08
(commit `6963600c0`).

### Constraint surface (consumers reading from casilla_values)

The cross-module discovery (W09.P20.S139 gate, paired with the
2026-05-26 linkage-P02 inventory in commit `f424db370`) confirmed
~100 read sites of `.casilla_values` plus 27 construction sites
passing `casilla_values=` as a keyword argument. Notable
hash-domain-coupled paths:

- `_actions.py:1005, 2854, 3083` — 3 call sites threading the same
  mapping into `derive_calculation_revision_id` AND into the
  `CalculationRevision` constructor. Both must see the same
  projection for the constructor-validator id check to pass.
- `_calculation_revision.py:228` — the model_validator at construction
  re-derives the id from `self.casilla_values` and compares against
  `self.calculation_revision_id`. If `casilla_values` becomes a
  property, this re-derivation chain still reads via the property
  and the comparison stays consistent.

### Two projection strategies

**Strategy A — derive-at-hash-time, preserve flat shape.** Keep
`casilla_values` as a field today; introduce a derivation helper
`_outputs_for_hash(observations)` that materialises the same
`{casilla_id: Decimal}` projection from the typed envelope; route
both the constructor and `derive_calculation_revision_id` through it.
Hash domain is byte-identical to today because the projection is the
same `{casilla_id: Decimal}` mapping; pinned SHA stable. Field shape
unchanged on the wire (no schema migration). Adds one helper, zero
breaking changes downstream. Closes the P02.S09 intent (the typed
envelope becomes the source of truth even though both fields persist).

**Strategy B — drop the flat field, new canonical projection.**
Remove `casilla_values` from `CalculationRevision` entirely; expose
it as a derived `@property` over `observations` (mirroring
`RegistryModeloObservation`). The hash payload's `outputs` key now
sources from `observations` directly. To preserve the pinned SHA,
the projection must produce the same byte string as today — which it
does, because `{obs.casilla_id: obs.value for obs in observations}`
canonicalised by the same sort+canonical-Decimal logic equals the
current projection. Requires a JSON-schema migration on every
persisted catalogue row (drop the `casilla_values` key, persist
`observations` as the canonical envelope), plus a one-shot data
migration to upcast historical rows that lack `observations`. Touches
27 construction sites + 4 roundtrip suites + the secure-object
storage envelope.

### Hash-stability test result (key observation)

The SHA-256 pin is invariant under projection-source change as long
as the materialised dict is `{casilla_id: Decimal}` keyed by trimmed
casilla_id strings with values canonicalised by `_canonical_decimal`.
Both strategies preserve this — the difference is wire shape, not
hash shape. Confirmed by the existing P02.S08 RegistryCalculationResult
collapse where the same logic landed without hash-domain disturbance.

### Strategy A vs B tradeoffs (architectural)

| axis | Strategy A (keep field, derive at hash time) | Strategy B (drop field, new projection) |
|---|---|---|
| Hash-domain risk | none — projection unchanged | none — projection unchanged but requires migration discipline |
| Wire-shape risk | none | high — every persisted row needs migration |
| Roundtrip suite impact | none (field still present) | 4 suites need fixture/expected-shape updates |
| Construction-site impact | 27 sites unchanged | 27 sites need `casilla_values=` → derivation kwarg shift, libcst codemod (P02.S10) |
| AEAT calculation-grounding-rule alignment | partial — flat field persists alongside typed envelope, which the rule deprecates | full — typed envelope is the only persisted shape |
| Single source of truth | weak — both fields persist; drift possible | strong — observations is canonical, projection is derived view |
| Reversibility | trivial (drop helper, revert) | high cost (data migration to restore the flat field) |

### Cross-campaign collision check

Grounded against in-flight vault docs at `.vault/exec/` and
`.vault/plan/`: no parallel campaign currently touches
`CalculationRevision.casilla_values` or `derive_calculation_revision_id`.
The linkage-design-audit plan is the sole owner of this surface.

The schema-hardening campaign owns `semantic_role` on
`CasillaDefinition` and the registry-fragment architecture; it does
not touch the persisted modelo-revision storage shape.

The live-iva-compensation-wallet campaign owns
`RepairRemediationDecision` and secure-object hardening; it touches
`SecureObjectRepository` but not the calculation-revision payload.

### Recommendation surface

Both strategies preserve the pinned SHA. Strategy A is mechanically
cheap, preserves wire shape, and satisfies the P02.S09 intent (the
typed envelope drives the hash). Strategy B aligns more strictly
with the AEAT calculation-grounding rule's "persist typed envelopes,
not flat scalar mappings" mandate but requires a one-shot data
migration and roundtrip-suite churn.

A staged path is also available: land Strategy A first (single helper
+ constructor wiring; cheap, reversible), then schedule Strategy B
behind a separate migration ADR once Strategy A has run for one
release cycle and proven hash stability in practice.

ADR follows in `2026-05-26-linkage-design-audit-adr` (the
casilla-values-collapse-projection-strategy decision).

## Second topic: typed context keys on RegistryValidationError and RegistrySnapshotError

Pre-flight research for `linkage-design-audit` plan steps `P05.S25`
and `P05.S26` (add typed context keys to `RegistryValidationError`
and `RegistrySnapshotError`). The intent is to formalise what
context-dict keys these errors carry so downstream consumers (CLI
emit, error registry, JSON output, `--explain` flag per the
accepted cli-workflow-redesign `--explain` ADR) can rely on the
shape without parsing free-form strings.

### Current state

`AeatError` (`src/aeat/core/errors/__init__.py:67`) already accepts
a `context: Mapping[str, object] | None` kwarg and stores it as
`self.context: dict[str, object] | None`. Plenty of raise sites
already pass typed context dicts ad-hoc; the keys are not pinned
by any contract.

### Frequency-ranked context-key inventory

Production raise sites of `RegistryValidationError` and
`RegistrySnapshotError` under
`src/aeat/domain/calculations/registry/` (excluding tests) pass the
following keys with the indicated occurrence counts:

- `op` (12) — formula operator name (`add`, `multiply`,
  `lookup_bracket_by_ccaa`, etc.)
- `parameter_id` (7) — registry parameter identity
- `binding_id` (5) — registry binding identity
- `position` (4) — formula expression argument slot
- `expected_kind` (4) — what the formula op expected at that slot
  (`binding`, `dispatch_table`, etc.)
- `expected` (2) — opaque expected-value string
- `dispatch_key` (2) — value resolved against a `dispatch_table`
- `casilla_ids` (2) — comma-joined casilla ids
- `bracket_table` (2) — parameter data-type discriminator
- `base` (2) — input value to a bracket lookup
- `available_keys` (2) — comma-joined valid dispatch keys
- `relation_id` (1) — registry relation identity
- `filing_date` (1) — ISO date the bracket lookup used
- `computed` (1) — flag indicating a computed casilla
- `casilla_id` (1) — single casilla identity

Plus the `casilla` key (variant of `casilla_id`) used at several
constraint-violation sites — partly redundant with `casilla_id`,
partly distinct (the constraint sites pass the casilla's `number`
attribute, not the id).

### Constraint surface (downstream consumers)

- `aeat.core.errors._registry.resolve_error_message(error)` looks
  up the error's registered message template and interpolates from
  `error.context`. Today the template assumes specific keys exist;
  a missing key in context renders as the templated placeholder.
- CLI JSON emit (`SchemaEnvelope` consumers per the
  cli-workflow-redesign ADR) needs a typed view of the error
  payload so the `aeat ... --json` shape is stable.
- Translation locales reference context keys by name (`tr("errors.calc.casilla_constraint_violation",
  casilla_id=...)` and similar); a key rename today silently breaks
  one locale per cycle.

### Design space

**Strategy P — pin keys with constants.** Define a closed enum or
constants set per error type listing the allowed context keys.
Raise sites use the constants; tests assert no raise site uses an
unregistered key. Zero runtime overhead; minimal refactor.

**Strategy Q — typed context model per error.** Add a pydantic
context model (e.g. `RegistryValidationContext`) with typed fields
matching the key inventory above. Raise sites build the model and
pass `context=model.model_dump(exclude_none=True)`. The model
provides field-level validation; consumers get a typed view via
`error.typed_context` property. Higher refactor cost; gains
schema-validated context payloads.

**Strategy R — factory method per error subclass.** Add
classmethod factories on `RegistryValidationError` /
`RegistrySnapshotError` for each canonical raise scenario
(`for_unknown_parameter`, `for_dispatch_key_unknown`,
`for_unsupported_op`, etc.). Each factory takes typed kwargs and
builds both the message and the context dict. Encapsulates the
template-key-name mapping so locales and CLI rendering both go
through one named contract. Refactor cost proportional to the raise
site count (29 sites across registry production code).

### Cross-campaign collision check

Grounded against in-flight vault docs: no parallel campaign
currently touches `RegistryValidationError` or
`RegistrySnapshotError`. The cli-workflow-redesign `--explain` ADR
authorises the consumer-side legal-grounding surface; the
error-class context shape is implementation under that umbrella.
The schema-hardening campaign owns `semantic_role` on
`CasillaDefinition` and the registry-fragment architecture; it
does not touch error classes.

### Recommendation surface

Strategy R (factory methods) gives the strongest typing-at-raise-
time benefit with the smallest blast radius — every raise site
migrates row-by-row, the existing `raise ...(message, context=...)`
shape keeps working during migration, and the locale layer + CLI
emit gain a single named contract per error scenario. Strategy P
(key constants) is a smaller starting point; Strategy Q (pydantic
model) is the heaviest with the most cross-cutting impact.

A staged path is available: land Strategy R for the highest-traffic
canonical scenarios first (the unknown-parameter / dispatch-key /
unsupported-op / bracket-no-coverage families covering 25+ of 29
sites), leave the tail as ad-hoc context until a downstream consumer
needs it pinned.

ADR follows in the same `2026-05-26-linkage-design-audit-adr`
extension — the architectural decision is recorded alongside the
casilla-values-collapse decision because they share the same
"contract typed at the boundary" theme.

## Third topic: JSON envelope migration for modelo work-lifecycle commands

Pre-flight research for `linkage-design-audit` plan step `P09.S40`
(extend the linkage research with a json-envelope-migration
section). The intent is to formalise the migration sequencing for
`emit_json_success`/`SchemaEnvelope` adoption across the modelo
work-lifecycle command surface — a contract-breaking change to
the JSON output shape that the cross-campaign CLI work has so far
deferred.

### Current state — bare-payload emit

Today's CLI work-lifecycle commands (`work create`, `work list`,
`work status`, `work rename`, `work discard`, `work calculate`,
`work verify`, `work file`, `work amend`, `work revisions`,
`work revision`) call `_emit(ctx, payload, lines)` from
`src/aeat/entrypoints/cli/_common.py`. `_emit` routes the
`payload` argument straight to `render_command_output` which
either echoes the text lines or `json.dumps`-es the raw payload.
No envelope wrapping; no `schema_version`, `command`, or
`warnings` keys on the way out.

The April 2026 `json-output-contract` audit documented this
explicitly: "newly registered emitters do not use it: they write
raw objects or arrays directly from command code… `aeat --json
modelos show 303` returns a bare metadata object with no
`schema_version` or `result`, and `test_json_schema_conformance.py`
then locks that raw shape into the registry tests."

### Target shape — `emit_json_success` + `SchemaEnvelope`

`aeat.core.json_contract.emit_json_success(command, result, *,
warnings=None, indent=2, sort_keys=False, stream=None)` wraps the
payload in:

```
{
  "schema_version": "1",
  "command": "<stable command path>",
  "result": <payload>,
  "warnings": [...],
}
```

The typed `OutputSchema` subclasses + `@register_schema("...")`
decorators are already landed at
`src/aeat/entrypoints/cli/_modelo_payloads.py` for the
work-lifecycle commands — `WorkCreateResult`, `WorkListResult`,
`WorkStatusResult`, `WorkRenameResult`, `WorkDiscardResult`, plus
`@register_schema("modelo.work.calculate")` and others. The
infrastructure is ready; what's missing is the routing.

### Constraint surface — downstream consumers

Three classes of consumer depend on today's bare-payload shape:

- **`test_json_schema_conformance.py`** at
  `src/aeat/entrypoints/cli/test_json_schema_conformance.py`
  asserts bare-payload shape for every registered command
  (lines 167-169 cited in the audit). Acts as the regression
  cap: changing the wire shape requires re-baselining this test.
- **Per-command CLI surface tests** (~30+ files under
  `src/aeat/entrypoints/cli/test_*.py`) that probe JSON output
  via `runner.invoke(app, [..., "--json"])` and assert on the
  bare payload keys.
- **Downstream tooling** — none in-tree today; the JSON-output
  contract audit notes the envelope-vs-bare question is the
  compatibility boundary for future external consumers.

### Sequencing strategies

**Strategy A — whole-surface flip in one commit.** Migrate every
work-lifecycle command to `emit_json_success` in a single commit;
re-baseline the conformance test + every probing test to expect
the envelope. Largest single commit; smallest window of
inconsistency; downstream consumers all hit the new shape
simultaneously.

**Strategy B — per-command incremental.** Migrate one command at
a time, re-baselining its tests in the same commit. Smaller
commits; the suite is briefly inconsistent (some commands return
envelope, others return bare) but each command is internally
consistent at every commit boundary. Requires the conformance
test to accept BOTH shapes during migration, then tightens back
to envelope-only when every command is migrated.

**Strategy C — dual-emit compatibility window.** Update `_emit`
itself to accept an optional `command_path` argument; when
present, wrap in envelope; when absent, fall back to bare
payload. Each command opts in by passing `command_path`. The
conformance test asserts envelope shape for opted-in commands
and bare for the rest. Migration shape per-command; opt-out
shape preserved permanently for commands that don't need it.

### Cross-campaign collision check

The cli-workflow-redesign campaign owns the JSON contract space
per the `2026-04-25-json-output-contract-audit` document. Its
epic plan does not currently carry a JSON-envelope-migration step
explicitly; that work logically lives under the linkage-design-audit
P05.S24 row, now pulled into P09.S42-S44. No direct overlap; the
cli-workflow-redesign campaign's authority documents are the
input to this decision, not a competing path.

### Recommendation surface

Strategy B (per-command incremental) gives the smallest commit
risk + the clearest migration progress signal. The work-lifecycle
surface is 11 commands; one commit per command makes review and
revert mechanically simple. The conformance test gains a
short-lived "accepts both shapes" mode for the migration window;
each per-command commit tightens the per-command expectation.
Once every work-lifecycle command is migrated, the conformance
test tightens to envelope-only for the work-lifecycle surface
(other CLI surfaces remain bare until their own migration ADRs).

Strategy A creates a single bisect-friendly cutover but
concentrates risk and review burden. Strategy C bakes a
permanent dual-shape into the emit helper, eroding the "envelope
is the contract" intent the json-output-contract audit
established.

ADR follows in the same `2026-05-26-linkage-design-audit-adr`
extension — third decision under the boundary-typed-contracts
theme.

## Fourth topic: repair_integrity backend cross-campaign coordination

Pre-flight research for `linkage-design-audit` plan step `P10.S45`
(extend research with `repair-integrity-backend-shape`). The
intent is to formalise the coordination path for the four
`RepairRemediationDecision`-family symbols that the linkage
W09.P20 cross-module-import gate currently carries as known
baseline (`#534` in the task list).

### Current state — symbols missing in this branch

The `chore/eliminate-shims` working tree carries
`src/aeat/application/repair_integrity.py` at 215 lines today
without `RepairRemediationDecision`, `RepairRemediationDecisionRepository`,
`repair_remediation_decision_id`, or `build_repair_policy_command_surface_catalog`.
Two test files in this branch import these names:

- `src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
  uses `RepairRemediationDecision`, `RepairRemediationDecisionRepository`,
  `repair_remediation_decision_id` heavily (lines 52-54, 651-1102) for
  encrypted secure-object roundtrip coverage of the decision payload.
- `src/aeat/entrypoints/cli/test_repair_policy_coverage.py` imports
  `build_repair_policy_command_surface_catalog` (line 10) to assert
  the catalogued repair-policy command-surfaces match the CLI
  registry.

Both test files were committed in commit
`82c87a2f9 Cluster E: reroute 3 private registry imports to public API`
explicitly marked "stage two previously untracked test files" —
i.e., the linkage / persistence campaigns landed the tests
expecting the backend to follow.

### In-flight design from the other campaign

The live-iva-compensation-wallet exec record at
`.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-22-live-iva-compensation-wallet-w05-p02-s01.md`
documents the design that campaign landed (in its own working
tree) on 2026-05-22:

> `RepairRemediationDecision` now records preserve, quarantine,
> rebuild, and export-required planning outcomes without
> authorizing mutation. The model records the target namespace,
> optional row digest, decided time, reason, likely origin,
> replacement-evidence requirements, and verified evidence
> references. The `mutation_authorized` field is hard-typed to
> `False`. Decision ids are content-bound to the decision fields
> so callers cannot persist an arbitrary sha-shaped key for a
> different remediation target or evidence requirement set.
>
> `RepairRemediationDecisionRepository` persists those decisions
> as encrypted AUDIT-class secure-object rows in a profile-local
> namespace. Object keys are opaque SHA-256 decision ids and the
> repository supports save, load, and decision-time ordered
> listing. The repair namespace classifier also treats the
> decision namespace as preserve-first remediation context.

That campaign's exec record references its own test surface
(`src/aeat/application/test_repair_integrity.py`) — not the
linkage / persistence campaign's tests that depend on the same
symbols. So the in-flight backend exists in their working tree
but hasn't propagated to `chore/eliminate-shims`.

### Symbol-shape inventory recovered from the test surface

The two test files in this branch effectively pin the public
contract of the missing symbols:

- `RepairRemediationDecision(BaseModel)` — pydantic model with
  fields: `decision_id` (str, SHA-256), `namespace` (str),
  `row_digest_hex` (str | None), `decided_at` (datetime),
  `reason` (str), `likely_origin` (str/enum), `replacement_evidence`
  (tuple/list), `verified_evidence_refs` (tuple/list),
  `mutation_authorized` (literal False).
- `RepairRemediationDecisionRepository` — class with `save_decision`,
  `load_decision`, `list_decisions` methods. List ordering is
  decision-time descending per the exec record.
- `repair_remediation_decision_id(...)` — pure function returning
  the content-addressed SHA-256 id. Inputs are exactly the
  fields excluded from the id (decided_at), so the id is stable
  across re-runs of the same logical decision.
- `build_repair_policy_command_surface_catalog()` — returns a
  tuple of repair-policy command surfaces, each carrying a
  `command_path` string and (per the test) catalogue coverage
  matching the CLI registry.

### Strategy options

**Strategy P — wait for upstream merge.** Leave the W09.P20
baseline entries in place; close them automatically once the
live-iva-compensation-wallet campaign lands its production code
into the shared branch. Zero coordination work today; the
in-flight backend is the canonical implementation; this branch
inherits it cleanly. Risk: timing is opaque — the campaign may
or may not land before this branch needs the symbols for other
work.

**Strategy Q — scaffold compatible stubs here.** Land minimal
implementations of the four symbols that match the test
contract (and the exec record's documented semantics) inside
`chore/eliminate-shims`. The in-flight campaign's full
implementation eventually supersedes these stubs via the shared
working tree's normal cross-commit-absorption flow; stubs and
real implementation are merge-compatible if their public shape
matches. Closes the W09.P20 baseline entries in this branch
immediately. Risk: scaffold drift if the campaign's design
moves between today and merge.

**Strategy R — pull the in-flight production code wholesale.**
Copy the campaign's working-tree production code (the
`repair_integrity.py` body the exec record describes) directly
into this branch. Identical to Strategy Q from this branch's
perspective, but the source of truth is the other campaign's
working tree rather than the exec-record-derived stub. Requires
access to the other campaign's worktree; the shared parallel-
worktree setup means it's available, but treating another
campaign's WIP as canon before they've landed it is a
discipline violation against the "do not stomp WIP" memory.

### Cross-campaign collision check

The live-iva-compensation-wallet campaign explicitly owns
`repair_integrity.py` per its W05.P02 exec records. Strategy R
would cross-contaminate this branch with that campaign's
in-flight design. Strategy Q is the lightest-touch path: the
linkage campaign owns the test surface that needs the symbols,
so scaffolding compatible stubs here satisfies the linkage
test surface without claiming authority over the other
campaign's design.

The shared `repair_integrity.py` module is a single file with
no overlapping edit conflict if the linkage scaffold sits next
to (rather than replacing) the live-iva-compensation-wallet
campaign's production code. Strategy Q lands additive symbols;
the campaign's full implementation supersedes once its own
landing is committed.

### Recommendation surface

Strategy Q (scaffold compatible stubs) is the right path given:

- The user mandate explicitly designates this branch as in-scope
  for the previously-deferred items (mono-worktree, everything
  in scope).
- The in-flight campaign's documented public contract is
  recoverable from the exec record + the linkage test surface.
- The W09.P20 gate's silent-fix detector will naturally demand
  the baseline trim once the symbols land, regardless of which
  campaign provides them.
- A scaffold landing inside `linkage-design-audit P10.S47` is
  reviewable as a standalone artifact; the live-iva-compensation-
  wallet campaign's eventual landing supersedes via standard
  merge resolution.

Strategy P preserves cross-campaign hygiene but risks indefinite
deferral. Strategy R violates the WIP-non-stomp discipline.

ADR follows in the same `2026-05-26-linkage-design-audit-adr`
extension — fourth decision under the boundary-typed-contracts
theme.


