<vaultspec type="config">
## Vaultspec Rules

You MUST respect these rules at all times:

---
name: aeat-agent-orchestration
trigger: always_on
---

# AEAT agent orchestration, audit cadence, and campaign close

Governs dispatch, the standing audit, and campaign close. Companion to
`aeat-worktree-safety` (the commands).

## Dispatch

- Drive campaigns through a persistent, role-based team resumed by name; do not
  spawn one-shot agents for work a standing role owns. One issue per
  delegation; handovers agent-agnostic (never hard-code a model vendor or
  launcher command into project instructions).
- **Discover with a swarm, not solo.** For any non-trivial code-location,
  duplication or cross-domain question: parallel discovery agents, output
  treated as inventory to confirm, paired with a targeted `rg` for known
  symbols.
- **Drive autonomously.** Resolve reversible, in-scope choices from code and
  rules. Do not expand authorization. Suite runs are rolling checkpoints.
- **Before dispatching a Step:** `git log --grep` and plan status — Steps land
  in parallel and may already be done. Before editing, inspect the target diff
  and coordinate overlapping work without treating it as an automatic blocker.
- **Re-read HEAD before recommending or acting on any finding** — a peer fix
  can land between investigation and report, so recompute the "still-a-gap"
  conclusion at report time. A backgrounded agent's empty output file is not a
  death signal; transcripts flush at completion.
- **Absorb in-scope regressions.** No "pre-existing, not my problem".
- **Work tracking:** no GitHub project board — issues, live worktrees and the
  vault pipeline only. An issue is actively worked only when a worktree AND a
  delegation exist. Balance the AEAT remote-synchronisation and financial-input
  tracks; bind financial-input work to the Transaction Data Pipeline step it
  serves; preserve provenance from ingest through handoff; Google Sheets is a
  one-way export mirror, never an authority.

## Audit cadence

Run the multi-agent audit swarm on **event triggers**: before a release cut
that crossed a domain boundary or persisted a new record type; after a
structural refactor touching more than two domain subpackages; every six to
eight commits on a long branch otherwise.

**Eight axes, one agent each:** calculation-engine grounding,
persistence-boundary identity, cross-domain handoffs, export/import fidelity,
workflow and CLI surface, selector/binding drift, semantic
functionality-cluster overlap, runtime import-graph coupling. Reasoning tier
for the four structural axes (calculation engine, cross-domain handoffs,
selector/binding drift, semantic overlap); cheap tier for the breadth four.

- **Axis 7, semantic overlap:** find by MEANING every site implementing a
  concept; classify true-duplication vs constraint-shape-divergent; confirm
  consumers import the canonical implementation; nominate a canonical home
  where two or more substitutable sites exist without one. Pair with a
  targeted `rg` for known canonical symbols.
- **Axis 8, runtime coupling:** grimp over the *executed* import graph (denser
  than import-time — deferred function-local imports hide cycles rather than
  remove them); diff cross-layer and cycle edges against the static picture.
  There is NO sanctioned inventory of function-local first-party edges to diff
  against: report such an edge on the graph difference alone, marked
  **unclassified** — never imply an allowlist cleared the rest.
- **Substitutability pre-filter** before any "X where Y exists" flag: Y's
  constraint shape must be a superset of X's. If Y carries constraints
  (min_length, pattern, max_length, value-format) that X does not, the site is
  NOT promotable — exclude it or document the mismatch.
- **Persist every finding** as `.vault/audit/yyyy-mm-dd-<axis>-swarm-audit.md`:
  third-level headings with pathway label, `file:line`, what is lost, concrete
  remediation. Reports must not modify production code. **Action every
  finding:** structural fix + roundtrip test, a wontfix vault note, or a linked
  follow-up task.
- **Swarm output is inventory, not gospel** — sub-agents miss things and
  hallucinate `file:line`. Verify every finding against current code first.

## Campaign close

- Every close triggers a **fresh-context honesty review** against the closure
  summary BEFORE declaring structural completeness (an independent reviewer
  dispatch; a "review as if you just inherited it" persona switch; or a
  declarative-vs-action curate pass). Persist as a vault audit; track every
  item as a Step with a verification gate. **Not complete until honest-pass
  items are closed with verification or formally deferred with a reference.**
- **A campaign cannot narrow its own completion criterion.** Beside every
  scope-narrowing note, write what the standing goal still asks for that it
  excludes.
- **No plan step marked complete without a matching exec record**, or a close
  audit recording the deferred carry-forward — otherwise delivered-as-specified,
  delivered-narrower and recorded-but-not-implemented wear the same checkbox.
- **An ADR amendment ruling on CODE is not self-executing.** Open the
  implementing rows in the SAME action as the amendment and grep the source for
  prose describing the old state as pending. "The ADR says X" is not evidence
  that X is true of the tree.

---
name: aeat-architecture-boundaries
trigger: always_on
---

# AEAT architecture boundaries

## Placement

Place Python application code under `src/cadrumo/`. Do not add top-level Python
packages, ad-hoc module roots, or hidden parallel implementations. Keep the
accepted hexagonal direction: domain logic independent from adapters, and
inbound, outbound, persistence, application, entrypoint and core responsibilities
separated. Keep the CLI root surface to `config` and `app` — never a third root
command family.

**Every Python test file lives under a `tests/` directory** at the narrowest
owning package or architectural boundary. A naked `test_*.py` beside
implementation modules pollutes the code namespace and is forbidden.

**A registry binding or resolver family** — counterpart, ledger, invoice,
detail-record, withholding, previous-filing, and any new one — lives in its own
semantically named public defining module under
`domain/calculations/registry/`. New families follow the established shape:
selector model, typed validator registered in the dispatch table, and
`resolve_*` functions. A dispatch module may define the cross-family dispatch
table, but it never re-exports per-family symbols.

## Typed boundaries

Expose validated boundary data through pydantic v2 models, with strict config
where practical. Do not expose bare `dict[str, Any]` for persisted records, wire
payloads, configuration, CLI input, MCP messages, LLM responses, or fixtures.

**Type every constant-like axis.** Closed value sets — period codes, output
languages, lifecycle states, source kinds, auth providers — MUST be a StrEnum (or
`Literal` where appropriate) in `core/`. Production code and CLI handlers accept
and emit enum members, not raw strings; registry TOML stays free-form and the
loader hydrates the typed enum at the boundary; tests assert against enum
members.

**Hint accepted values at the CLI boundary.** Every Typer argument whose value is
a closed enum declares that enum as its type, so click renders the accepted set
on parse failure. A late registry-driven refusal is acceptable for axes depending
on dynamic registry data, but it MUST list the accepted set — never a bare "value
invalid".

## Imports resolve to canonical defining modules

Every cross-package symbol has exactly one definition in a semantically named
public module. Consumers import directly from that module. Package `__init__.py`
namespaces are inert and may not import, bind, alias, lazily resolve, or
re-export project symbols. An empty `__all__` may document the inert boundary.

A contract required outside its package must hard-move from an underscore-
private module to a public defining module with every production, test,
fixture, tooling, annotation, registration, and dynamic consumer updated and
the old path deleted atomically. Truly private modules remain package-internal.
Never mechanically strip an underscore without adjudicating whether the
contract is shared, narrower API is required, or the reach must be deleted.

Re-export modules, package facades, hierarchical roll-ups, aliases, forwarding
wrappers, compatibility imports, fallback imports, star imports, and PEP 562
export maps are prohibited. Dynamic imports name the canonical defining module
exactly. Static imports, local imports, annotations, `TYPE_CHECKING`,
registrations, and string-based discovery all count as import edges.

## No shims, no parallel write paths

Do not introduce shims, compatibility layers, deprecation paths, or duplicate
legacy APIs. Move callers to the canonical path instead.

**A new service must delegate to an existing single-writer primitive rather than
re-implementing its write path**, preserving its atomicity and lifecycle-event
emission. The service emits its own surface-level event **in addition to** the
primitive's: the lifecycle event records the data change, the surface event
records the operator's verb invocation, and a later query distinguishing "record
relabelled" from "operator invoked the verb" depends on both. Re-implementing
re-introduces the torn-write risk the primitive eliminates and creates shadow
event emission.

## Relocations are atomic

Land every symbol relocation in ONE explicit-path commit: the canonical-site
move, every consumer update, every fixture update, and every canonical-
definition inventory and inert-namespace gate update share one git index and
one commit. Run
`uv run --no-sync pytest --collect-only -q` immediately before and observe clean
collection. Never split the move from the consumer sweep, and never reintroduce a
re-export as a temporary bridge. One Step = one symbol = one atomic commit; tag
the subject `relocation:<symbol>`.

## Source hygiene

Keep source free of project-management metadata: no waves, phases, agent names,
issue workflow, handover state, temporary migration labels, or process history in
production identifiers, comments, fixtures, schemas, or public APIs. Use domain
names that stay true after the current plan changes. Do not land design-only
implementation shells — ship working behavior, executable validation and tests
together. Add comments sparingly and only for *why*; never describe changes
through comments.

**The term "binding" is RESERVED** for the registry-data-input concept
(`DataBindingDefinition`, its value carrier, its source resolvers). Account
scoping, parsing helpers, verification gates and other concepts MUST NOT be named
"binding"; when two concepts would share the name, the non-registry-input one is
renamed to what it actually does. Two unrelated `_profile_binding.py` modules
once shipped side by side, one an OAuth scoping resolver and one the registry
profile-fact resolver.

## How

- **Good:** a new service imports `rename_profile` directly from its public
  defining module, and the owning package `__init__.py` remains inert.
- **Good:** the OAuth resolver is `_active_profile.py`; the string-to-Decimal
  parser is `_decimal_parsing.py`. The registry profile-fact resolver keeps the
  binding name — it is correct there.
- **Good:** `src/cadrumo/application/modelo/tests/test_work_addressing.py`.
- **Bad:** `src/cadrumo/application/modelo/test_work_addressing.py` beside the
  implementation modules.
- **Bad:** importing a symbol from a package namespace, private cross-package
  module, bridge, or alias; or blanket underscore stripping without judging
  shared primitive versus single caller versus design defect.
- **Bad:** naming a new module `_*_binding.py` for a session, identity, parsing
  or verification concern.
- **Bad:** a `rename` that opens its own bucket session, decrypts, mutates,
  re-encrypts, then separately rewrites the manifest label — re-implementing the
  cross-store atomicity the repository holds.

Enforced by `dev/quality/import_hygiene_scan.py` and
`dev/tests/test_import_hygiene_gate.py` -- both outside the `src/` test lanes, so
run them explicitly. Source: ADRs
`2026-07-01-import-centralization-adr`, `2026-08-11-tui-architecture-adr`,
`2026-08-11-tui-interface-adr`, `2026-08-24-tui-registry-api-gate-adr`,
`2026-06-05-test-topology-refactor-adr`,
`2026-06-03-cli-workflow-redesign-adr`,
`2026-06-14-bindings-interface-hardening-adr` (decisions E, F).

---
name: aeat-calculation-aggregation
trigger: always_on
---

# AEAT calculation aggregation: one mechanism, no dormancy, one path

## One canonical mechanism per calculation type

Each calculation value channel has exactly one canonical mechanism:

| kind | mechanism |
|---|---|
| cross-MODELO fold-in | a relation (`cross_model_output` / `annual_summary` / `previous_period`) |
| same-modelo static carry | a direct `previous_filing` binding |
| ledger projection | a ledger aggregation resolver |
| cross-member fan-in | a `per_grupo_member` binding |
| M303 compensación | the IVA wallet decision |

A new aggregation surface MUST enroll under an existing row or amend the ADR
before shipping. **Never model one fold-in two ways at once.**

The engine's channels once had overlapping mechanisms with implicit canonicality:
one cross-modelo fold-in was declared BOTH as a relation and as a
`previous_filing` binding — two entities, two resolvers, different live-fire
status. One canonical mechanism per type makes ownership declared data: a binding
`source` kind maps to a resolver's `owned_sources`, greppable and gate-auditable.

## No dormant resolvers; every source is routed or advised

Every `ModeloSourceResolver` merged to main MUST be enrolled in the live
calculate mesh (`merge_source_resolutions` in
`src/cadrumo/application/modelo/_calculation_actions.py`) or deleted. Every
registry binding `source` kind MUST be a member of the enrolled-or-explicitly-
deferred set (`_BUCKET_AGGREGATION_OWNED_SOURCES` union `DEFERRED_SOURCE_KINDS`,
enforced by `assert_no_novel_source_kinds`). And
`collect_unhandled_source_diagnostics` MUST run on the live calculate path, so an
unrouted source surfaces a non-blocking advisory — never a silent blank.

The safety net was once built and switched off: the diagnostic collector had no
live caller and the owned-sources set described the enrolled set while enforcing
nothing, so a new TOML binding with a novel `source` compiled and silently
resolved to blank.

## Pull and calculate share one aggregation path

A casilla's value MUST be produced by the same aggregation logic whether reached
via the live `calculate` path or the Sheets-pull path. Both surfaces share one
resolver set, and a regression proves they agree for a shared revision — they
both persist to the SAME revision, so a calculate-then-export cycle could
otherwise yield divergent, conflicting values with no detection at save time.

## How

- **Good:** a cross-modelo fold-in is modelled as a relation feeding the engine's
  relation channel; a same-modelo single-filer carry uses a direct
  `previous_filing` binding; cross-member fan-in stays a `per_grupo_member`
  binding, because the relation schema has no grouping axis.
- **Good:** a not-yet-built source kind is added to `DEFERRED_SOURCE_KINDS`
  (canonical in `application/aggregation/_source_mesh.py`) — explicitly deferred
  and advisory-visible.
- **Good:** the relation prefill resolver delegates to
  `resolve_relations_from_local_store` in
  `src/cadrumo/application/calculations/_relation_prefill.py` — the exact
  function the pull path calls — with parity enforced by
  `application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`.
- **Bad:** declaring the same fold-in as both a relation and a `previous_filing`
  binding; or inventing a new resolver or source kind for a value an existing row
  already covers.
- **Bad:** merging a fully-implemented resolver that is exported but never
  enrolled — dead capacity whose registry kind blanks silently.
- **Bad:** landing a new `source` kind without enrolling a resolver or
  registering it deferred, then silencing the refusal via the manual-input
  allowlist.
- **Bad:** a pull-path assembler that computes a casilla one way while the live
  calculate path computes it another.

Source: ADR `2026-06-10-calculation-aggregation-taxonomy-adr`; audit
`2026-06-10-calculation-engine-foundations-audit` (F4, F5).

---
name: aeat-calculation-grounding
trigger: always_on
---

# AEAT calculation grounding and legal provenance

## Tax semantics come from official sources

Ground tax semantics in BOE, AEAT publications, AEAT workbooks, registry sources
or live oracle replay. **Do not invent legal behavior, and do not treat user
preference as authority for regulated calculations.** Where an identity or
classification judgment is required, it is a TAX REVIEW against official sources
— never text similarity — and it records honest reviewer provenance.

## Grounding travels to the operator

**Carry regulatory grounding through every domain boundary.** Every casilla
observation, calculation revision, filing draft, export record and CLI emit MUST
preserve its `legal_refs`, `source_refs` and `formula_id` provenance from the
registry source to the operator-facing surface.

**Persist typed envelopes, not flat scalar mappings.** `RegistryFilingObservation`,
`CasillaObservation`, `CalculationRevision.observations` and equivalent typed
records are canonical; do not collapse them to `dict[str, Decimal]` for
downstream consumers. Expose a derived mapping as a property if a flat view is
needed.

**Emit every casilla in `engine_result.values`, not only computed entries.** Input
and bound casillas MUST produce `CasillaObservation` rows pulled from the registry
casilla definition; computed casillas pull the same fields from the matching
engine entry. Never drop a casilla on the way to the persisted revision.

**Surface `legal_refs` and `source_refs` on every operator-facing CLI JSON
payload.** Wrap typed observations in a parallel JSON list alongside any flat
`casilla_values` mapping — the flat view is for readability, the typed list is
the contract.

**Validate referential integrity at snapshot build.** Every typed-ID reference
must point at an existing entity; every per-source binding selector must satisfy
its typed selector model; every cross-domain routing table must reference real
casillas in the modelo revision.

**Treat type-system escapes as boundary leaks.** `cast(...)`, `dict[str, Any]`
returns and bare `str(...)` coercion of typed aliases are documentation debt or
design escapes. Document third-party API boundaries inline; remove them
everywhere else.

## Every value cites the provision that establishes it

Every regulatory value compiled into the registry — a rate, bracket tranche,
threshold, deadline window, reduction coefficient — MUST declare in its
`legal_refs` the specific binding provision that *establishes that value*, and
that provision MUST be defined in the legal catalogue with a `corpus_ref`
resolving to real BOE or AEAT text.

**Citing the general framework article alone is insufficient** when a more
specific provision — a transitional disposition, a phased schedule, a modifying
law — actually fixes the number. A value whose binding provision is not in the
schema is ungrounded and MUST NOT ship. Confirm the provision is cited, defined,
backed by corpus text the evidence gate validates, and **consistent with the
value** — the corpus clause states the number encoded.

**Correcting a generic-default grounding:** where a casilla's `legal_refs` carry a
chapter as a generic default and the box is not actually of that kind, re-ground
it to its own concept's binding article, keyed by the **renumbering-immune
section tag** (the leaf of `section = [...]`), **never by casilla id across
filing years** — ids renumber, so an id-keyed map injects the wrong article. A
framework article that *applies* a regime is a valid foundation home even when
the regime is *established* elsewhere. For a casilla that is a member of a
construct or binding, sweep the casilla, its construct AND its bindings in ONE
change: the validator requires a construct's refs to cover both its member
casillas' and its bindings' refs, so a partial sweep breaks registry load.

## Verify against the bundled corpus, and distrust it on numbers

Verify legal text against the BUNDLED authoritative consolidated corpus under
`src/cadrumo/_data/corpus/normatives/html/` FIRST. Never author a corpus excerpt
from a secondary source without that cross-check, and prefer pointing
`corpus_ref` at the bundled file over hand-authoring a duplicate.

**The bundled corpus is preferred but NOT infallible.** For any numeric AMOUNT or
RATE, cross-check against the live BOE or AEAT consolidated text even when the
bundled corpus states it. An excerpt authored from a secondary source once
carried a fabricated year list while the repo already bundled the authoritative
text — and the `required_text` cross-check was tautological, because the same
author wrote both the excerpt and the phrase validating it.

**A fetched file can still be unfit.** A consolidated-legislation payload carries
every historical version, oldest first, so taking the first block bundles
repealed law under a current filename; and a truncating shell heredoc silently
loses text. Take the **last** version, assert the amending norm's identifier,
never pass legal text through a shell, and read the file back before trusting it.

## Total aggregations enumerate every contributing tier

An IVA "total cuota devengada" aggregation — M303's total casilla, M390's annual
total, any IVA modelo's equivalent — MUST sum the **recargo de equivalencia**
cuota tiers (LIVA art. 161) alongside the standard, reducido and super-reducido
repercutido tiers and the autorepercutido cuota. Omitting them silently
under-declares for any recargo filer and desynchronises the annual return from
the summed quarters. Generalise it: when a tier or category is added to any
total, confirm every downstream total and every return that reconciles against it
enumerates it too.

## How

- **Good:** `rg` the bundled consolidated file for the provision's anchor, read
  the verbatim text, and point `corpus_ref` at that file with a `required_text`
  phrase distinctive enough to match only the target provision.
- **Good:** if the bundled corpus is wrong, correct the corpus, the grounded
  parameter, the legal-entry notes and any tautological test that baked the wrong
  value, in ONE atomic commit.
- **Good:** the total formula enumerates every tier, the construct's `legal_refs`
  cite art. 161, and a grounded parity test against a manual worked example
  charging recargo reproduces the printed total exactly.
- **Bad:** authoring an excerpt from a blog or summary site — the
  self-referential `required_text` gate passes anyway.
- **Bad:** stamping an agent-authored legal entry as reviewed under the
  operator's name without the cross-check; the legal catalogue is a
  human-reviewed, filing-grade surface.
- **Bad:** mapping one year's casilla id to another's to copy grounding; or
  grounding a construct-member casilla without its construct and bindings.
- **Bad:** "fixing" a failing recargo-inclusive parity test by adopting a
  recargo-excluded expected value — fix the formula, not the test.

Source: ADR `2026-06-14-bindings-interface-hardening-adr`; audits
`2026-06-14-legal-grounding-centralization-audit`,
`2026-06-14-aeat-grounding-completion-audit`.

---
name: aeat-cli-contract
trigger: always_on
---

# AEAT CLI contract: verbs, notices, single-subject mutations

## Transport verbs are keyed on the counterparty

Two axes, four tokens. A **remote counterparty** — the AEAT sede, a Drive or
Sheets store, a model distribution host — is read with `pull` and written with
`push`. A **local filesystem** counterparty is read with `import` and written
with `export`. The AEAT axis has no outbound half, permanently, because live
submission is prohibited.

`capture`, `refresh`, `fetch`, `download`, `upload`, `sync`, `send`, `get`,
`mirror`, `probe` and `file` MUST NOT name a verb whose primary purpose is
moving data. `file` retains only its domain meaning, the act of filing a
declaration, and that meaning is exclusive. A verb whose primary purpose is
COMPUTATION names the computation; transport it performs as a means is
incidental and is declared on its parameters.

A command reconciling from either transport MUST be a subgroup of `pull` and
`import --file`, never one verb multiplexed by `--from-*` flags.

Compounds are legal as `<token>-<subject>` and `<token>-all`; `<token>-<locus>`
is not, because locus belongs in an option.

The reconcile surface had grown four divergent `--from-*` flags plus a sugar
verb while sibling surfaces used `capture`, `refresh` and `--source`, so no
operator could transfer knowledge across verbs. Fixing that with one token per
AEAT fetch left every OTHER remote read unnamed, so the axis was widened from
"AEAT" to "remote" and given a `push` partner.

## Local paths are spelled by declared locus, shape and role

The parameter spec declares a `TransportLocus`, `TransportShape` and
`TransportRole`; a gate reads the declaration rather than guessing, because
type cannot tell a Drive folder id from a filesystem directory and a spelling
gate that reads spellings proves nothing.

Exactly ONE local input per verb is primary, spelled `--file` or the positional
subject; one local output is primary, spelled `--output`. A bulk local directory
is `--directory`, a local output directory `--output-root`, a resolution base
`--<name>-root`. Every FURTHER local input is auxiliary and is named for the
role it plays — `--verify-source`, `--receipt`, `--scenario` — because an
auxiliary's name is the only place that job is written down.

A single-file input MUST NOT be `--source`, `--path`, `--from-file`, or a
bespoke `--from-*` family. A parameter declaring locus `none` is outside this
table entirely, which is what protects a closed-enum discriminator that happens
to be named `--source`, and `--from-year`.

**A verb rename MUST be swept by hand through the surfaces the gates do NOT
scan:** the runtime write-policy allowlist (`storage_write_policy.py`), the
error-registry `default_suggestion` fields, the cross-period `next_action`
builders, the curated operator help surface (`operator_surface/_help.py`), and
the envelope `command=` identifiers. Updating only the verb registrations leaves
dead operator instructions and drops the verb out of the profile-bound write
guard, which then fails open.

The censal reader is pinned to the read-only consulta view and fails closed on a
filing-tool or procedure-launcher landing; that guard binds regardless of the
verb's name.

## Notices are the only diagnostic channel

Operator-facing non-blocking diagnostics — warnings, advisories, next-step hints
— MUST be emitted through the typed `Notice` channel on the shared CLI envelope
spine (`cadrumo.core.json_contract.Notice`, via `_emit_envelope(...,
notices=[...])` / `emit_json_success(..., notices=[...])`).

A command MUST NOT re-introduce a bespoke advisory, `next` or `suggestion` field
inside its `result` payload. The shared spine (`schema_version`, `command`,
`status`, `notices`) is uniform across the success envelope and the stderr error
document; `status` derives from notice severity and stays in lock-step with the
`ExitCode` table.

The success and error envelopes were once disjoint with no shared `status`, the
success `warnings` channel was structurally dead, and advisories were smuggled as
bespoke `result` fields — so the contract was un-introspectable and bypassed the
envelope redaction funnel.

**Allowed, not a violation:** primary structured result data a command exists to
produce — verify `findings`, calendar `warnings`, a `next_due` date, a
per-finding `next_action`. These are output, not incidental diagnostics.

## Single-subject verbs: positional id, uniform result, idempotent

**The subject id is positional.** A verb addressing one ledger transaction
accepts the id as a positional `Argument` resolved through the single shared
transaction-id resolver — never a `--id` option, never a duplicated resolver
helper. The subject is an argument; flags configure the operation.

**Single-transaction mutations return the uniform quintet**
`{bucket_id, transaction_id, bucket_event_ids, review_status, transaction}`
through the shared ledger mutation result shape. Structural verbs that act on a
set or destroy the subject (`split`, `merge`, `remove`, `reset`) are different
operations and declare their own typed schemas.

**Creating mutations are idempotent-guarded.** Every verb that CREATES one
addressable record: a retry carrying the same caller-supplied idempotency key, or
the same deterministic clock-free derived id, returns the EXISTING record as a
no-op (no second lifecycle event, no `created_at`/`modified_at` re-stamp, no
re-run of side effects), surfaced through the uniform result shape plus an info
`Notice`. A same-key call whose content DIFFERS refuses with an instructive
localised conflict naming the divergent fields. A deliberately additive verb is
`non_idempotent_append` and MUST document that choice.

**Identity MUST be clock-free.** The timestamp is a non-identity last-seen body
field, never folded into the derived id.

This CLI's operator is an autonomous agent that retries calls, so a
non-retry-safe creating mutation silently double-writes — a duplicate ledger
transaction inflates every downstream modelo aggregation. The subtler failure is
a **no-op match that omits a persisted field**, silently dropping the new value.
**The match compares EVERY persisted field.**

## The operator harness cites only the live surface

Every agent-harness document under `src/cadrumo-harness/` that names a CLI
verb or a JSON-envelope field MUST cite only verbs resolving against the live
operator-surface manifest and fields existing on the live envelope models, and
MUST be co-committed with the CLI surface it couples to. A citation to a renamed
verb hands the agent a dead instruction it cannot recover from.

## How

- **Good:** `aeat app live justificante pull`, `pull-all`, `pull-sources`;
  `aeat app ledger import --file STATEMENT.csv`; a dual-transport reconcile as
  `reconcile pull` + `reconcile import --file PATH`. `aeat config profile censo`
  is the worked example: `censo import --file` and `censo pull`, both reconciling
  through the one `apply_cotejo` authority behind the same `--apply` door.
- **Good:** an advisory projected with `advisory_notice(code, message,
  context={...})` and passed via `notices=`, its text line rebuilt from the same
  notice so JSON and text cannot drift.
- **Good:** derived verification and filing record ids fold the OUTCOME
  (revision, status or findings, actor) and drop the timestamp.
- **Bad:** a new `capture`/`refresh`/`fetch` verb for an AEAT read, a `--source`
  file input, or multiplexing one verb with a `--from-*` family.
- **Bad:** adding `authorization_advisory`, `source_advisories`, or any
  `*_advisory` / bare `next` / `suggestion` as a top-level field on a registered
  `OutputSchema`.
- **Bad:** `ledger view --id tx_123` for a one-subject verb; a mutation returning
  only `transaction_id`; an id that folds the clock; or a guarded no-op whose
  match omits a field.
- **Bad:** citing a harness verb that does not exist, or renaming a CLI verb
  without sweeping the harness documents.

Gates in this repository: `test_documented_command_conformance.py` and
`test_json_schema_conformance.py`. The latter was rebuilt against the command-spec
`ResultSchemaSpec` kernel after the `SCHEMA_REGISTRY` it originally walked was
retired; it walks every spec declaring a result-schema target and refuses a
bespoke `next` / `suggestion` / `*_advisory` field beside the envelope's one
diagnostic channel. `test_rule_surface_conformance.py` is deliberately NOT named
here any more: it shipped inside the cadrumo-harness client and left with it when
that client was rehomed out of this repository, so naming it here pointed every
reader at a file this tree does not contain. Source:
ADRs `2026-06-10-cli-pull-file-standard-adr`,
`2026-06-10-cli-envelope-notice-standardisation-adr`,
`2026-06-10-ledger-interface-contract-adr`,
`2026-06-30-ledger-add-idempotency-adr`, `2026-06-30-agent-harness-adr`.

---
name: aeat-documentation
trigger: always_on
---

# AEAT documentation, terminology and shipped search

## User-facing language

Write user-facing documentation in simplistic, singular, imperative instruction
steps — "Create taxpayer profile." / "Import bank statement." — never
conversational plural narration ("We will now set up…"). Walk concrete
scenarios step by step instead of presenting every option; use general
terminology (NIF, CIF, DNI, NIE, NII); guide from profile setup and transaction
import through calculation and reconciliation, cross-linking so complex topics
arrive gradually; keep descriptions objective.

## Workflow

Every documentation change follows the `vaultspec-documentation` lifecycle:
wireframe → refinement → approval; context gathering and isolated
section-by-section drafting; technical review (against the codebase and
conformance gates) and editorial review; final approval. A *researcher* gathers
context without writing drafts; an *author* writes from that research only; an
*editor* reviews for a newcomer's clarity, tone and link integrity. **Final
wording and approval stay with the main session** — never delegate final prose
to a subagent.

Verify with
`pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`
and the nitpicky Sphinx gate `pytest dev/docs/tests/test_docs_build.py`. Chat
responses use absolute `file://` links with forward slashes; user-facing docs
use relative markdown links.

## The generated API reference is CLI-owned

Maintain with `python -m dev.docs.apidocs scaffold`; never hand-author or
hand-edit `docs/api/*.rst`. Run `scaffold` after any `src/cadrumo/` module-tree
change (relocation, rename, deletion) and land the regenerated stubs in the
same commit; `scaffold --check` is the drift gate, `audit` the health report. A
stub left for a deleted module hard-crashes the nitpicky `-n -W` autodoc build;
a module without a stub silently drops out.

**`scaffold` is tree-wide, not change-scoped:** one run also emits stubs for
peers' unscaffolded modules. Diff each modified stub and stage only those whose
added lines name YOUR module; leave the rest for their owners and do not revert
them. A red docs build after `scaffold` is often not yours — grep the log for
your own module names first.

## Docstrings cross-link the core spine

A module importing a canonical core struct MUST cross-link it in at least one
docstring via a Sphinx role (`` :class:`ModeloRevision` ``). The spine is the
`CORE_STRUCTS` mapping in
`src/cadrumo/tests/test_docstring_core_struct_links.py`; anchors are bare (no
dotted path — the build's missing-reference resolver handles them). Choose
anchors for navigability, not import in-degree: a central data aggregate, a
domain authority, or a domain's primary closed-value enum — never ubiquitous
infrastructure, error subclasses, or low-reach types. The link MUST be
semantically truthful.

## Terminology: one declaration, preserved by scaffold

Every user-facing domain term is enrolled once in the Terminology Handbook
(fragments under `src/cadrumo/_data/terminology/concepts/`) and referenced via
`:term:`; never redeclare an enrolled definition in prose or maintain a
parallel glossary. Scaffold runs preserve curated fields verbatim, add new
entries as **empty drafts**, and retire vanished entries as **tombstones** with
`replaced_by` — never clobber, invent, or delete.

**Only a taxpayer- or operator-facing AEAT concept may be `approved`** (and so
render in the glossary and shipped search): a tax, modelo, casilla, régimen,
period, legal concept, or operator workflow noun. A concept naming search,
calculation or registry **machinery** is `deprecated` with a `scope_note`
(excluded from the glossary) — never
`retired` (asserts a successor a mis-enrolment lacks), never deleted.

## Shipped search artefacts are licence-clean

*(Home of the retired rule slug `shipped-search-licence-clean` — deliberately
merged here, not shipped as its own file, so a search for the slug lands here.)*

Ship only licence-clean sources, laundered identifiers and rankings. **Never
ship** NC/ND/gated derivatives, raw oracle output (scores, snippets, sparse
maps, term weights), or raw or unbounded vectors. **Sole narrow exception:** a
bounded term-embedding matrix in the BUILT DOCS only (never the wheel) —
reviewable plain data, computed on the dev box by a pinned, named MIT or
Apache-2.0 model over project vocabulary, provenance-stamped (model, revision,
licence, vocabulary fingerprint, size), no larger than 3 MB. **That exception
currently has NO consumer** — the matrix, its compiler and its client tier were
removed. It is a deliberately unlocked, presently unused door: shipping through
it is a first use that needs a ruling, not sanctioned practice.

**Commit only the LIGHT precompiled data** (laundered relevance mapping,
synonym candidates, held-out queries, Handbook fragments, a qualifying matrix).
**Never commit the HEAVY generated search index** — gitignored, regenerated per
docs build; committing it bloats every clone and drifts from the corpus.

## How

- **Good:** a relocation commit runs `scaffold` and stages only its own
  modules' regenerated deltas in the same explicit-path commit.
- **Good:** stdlib cross-references module-qualified
  (`` :exc:`~decimal.InvalidOperation` ``); bare *project* anchors stay bare.
- **Good:** add or update a concept fragment, then `:term:` references; commit
  a ratified relevance mapping and regenerate the index at build time.
- **Bad:** hand-editing an API stub; landing a delete or rename without
  re-running `scaffold` (orphan stub crashes the next build); a scaffold run
  rewriting curated prose; promoting internal tooling to `approved`; committing
  an embedding outside the exception, sparse maps, raw scores, or the generated
  index.

Source: ADRs `2026-06-10-docs-terminology-search-adr`,
`2026-06-15-docs-terminology-search-adr`,
`2026-08-01-user-docs-search-consolidation-adr` (R5),
`2026-05-30-docs-architecture-adr`.

---
name: aeat-ledger-contract
trigger: always_on
---

# AEAT ledger contract: amounts, evidence, advisories, derived indexes

## Amount is an absolute magnitude; direction is the sole flow authority

A ledger transaction stores a **non-negative** `amount`; flow direction is
carried solely by the `direction` enum (INCOMING / OUTGOING /
INTERNAL_TRANSFER). No model, adapter, evidence row or CLI surface may encode
flow in the sign of an amount. The constraint is enforced at the `RawTransaction`
boundary so import and manual paths are both gated, and evidence rows mirror the
absolute convention. There is no signed-amount shape to read, migrate or bridge.

Flow was once encoded twice and the two could disagree; consistency was enforced
only on the manual command, so the import path derived direction from the sign
and a zero-amount import silently classified as INCOMING.

## Evidence is encrypted bytes, and rides with the revision that used it

Every ledger evidence record must carry the document's **encrypted bytes** in a
bucket-scoped secure-object namespace. A Gmail, Drive or URL reference must be
fetched and encrypted, or the attachment refused — never stored as a link-only
manifest. A stored pointer is not evidence: links rot, permissions change, and a
later audit cannot answer why a casilla had a value from a dead manifest.

Every modelo calculation revision that derives any casilla from the ledger MUST
bundle the typed ledger evidence — contributing-transaction projections plus
manual fact-basis entries — pegged to the revision's snapshot fingerprint, and
every export MUST carry that evidence or a resolvable in-system reference. An
export carrying neither is refused. Revision state once stored only fingerprints,
so the fact basis explaining *why a casilla holds its value* was absent from the
persisted revision and every export.

## The IVA advisory fires only on cuota-bearing categories

The unconsumed-declarable-IVA advisory MUST fire only on `IvaCategory` values
legally expected to produce a cuota a binding should route. Categories that are
**cuota-less by law** (exempt, zero-rated, not-subject, exempt intra-community
supply, triangulation, other-regime) MUST be excluded via the named
`CUOTA_LESS_M303_IVA_CATEGORIES` frozenset — never an inline literal.

The advisory once false-fired on categories bearing no cuota by law, which
legitimately match no cuota binding — noise that trains operators to ignore the
alert. It only earns trust if every fire is a genuine unrouted cuota.

## The participation index is derived and rebuildable

The transaction-to-revision participation index is a **derived encrypted cache**,
co-written atomically with revision persistence and rebuildable from the revision
catalogue. Lifecycle correctness MUST rely on the live catalogue scan, never on
index freshness — if deletion guards depended on the cache, a stale write could
silently permit destructive ledger changes.

## How

- **Good:** `RawTransaction.amount` carries a non-negative validator firing for
  both import adapters and the manual command, locked by a save-load-equality
  roundtrip plus an anti-tautology proof (corrupt the on-disk amount negative,
  assert load refusal). Import adapters map the export sign or debit/credit
  signal to a direction at the parse boundary, store the absolute amount, and
  refuse a zero-amount source row.
- **Good:** the doc-link path resolves a permitted file to bytes, stores them
  through the attachment secure-object namespaces, and records source metadata;
  out-of-scope references fail with an actionable refusal naming the scope
  upgrade or manual-download path.
- **Good:** the evidence projection resolves source transaction ids into typed
  rows bound to the fingerprint, persisted inside the encrypted revision and
  surviving a strict roundtrip with every defaultable field populated
  non-default; a coverage assertion makes a bundle that drops a resolved
  contributor raise.
- **Good:** verification or filing persistence co-emits participation entries in
  the same secure-object write batch as the revision state change, and a rebuild
  action regenerates them from finalized catalogues.
- **Bad:** writing a negative amount to encode an expense, or a
  `direction_from_amount` helper reading `amount < 0` downstream of the parse
  boundary.
- **Bad:** persisting only a URL as evidence, or falling back to link storage
  after a fetch permission error.
- **Bad:** flagging an exempt entrega intracomunitaria or an export as "unrouted
  declarable IVA"; or silencing a genuine unrouted reverse-charge cuota by adding
  it to the cuota-less set.
- **Bad:** allowing a ledger transaction delete because the participation index
  has no entry for it; or writing a plaintext index outside the encrypted
  repository.

Source: ADRs `2026-06-10-ledger-amount-direction-adr`,
`2026-06-10-ledger-evidence-enforcement-adr`,
`2026-06-03-modelo-export-evidence-parity-adr`,
`2026-06-09-modelo-iva-routing-carry-adr`,
`2026-06-10-ledger-modelo-crossref-adr`.

---
name: aeat-local-execution
trigger: always_on
---

# AEAT local execution

Use `fd` and `rg` for discovery and search. Prefer native PowerShell in this
environment; do not wrap normal commands in `pwsh`, `powershell`, `cmd /c`, or
`bash -lc` unless a tool requires a separate shell process.

Use the uv-managed workflow, and prefer platform-agnostic project configuration
over shell-specific variants.

**Run real gates.** Do not use mocks, fakes, stubs, patches, monkeypatches,
skip, xfail, or tautological assertions as shortcuts.

**Re-run before blaming the code.** Registry-suite failures under parallel
pytest are more often a loader-cache race than a real regression, and this
worktree's backing share fails under concurrent I/O, so a dead parallel run is
more likely the drive than the code. Re-run sequentially before triaging.

## Capturing a background run

Write the **full** output to a log file and read it back from disk. Do not pipe
through `Select-Object -Last N` or `tail -n N` **before** `Tee-Object` — the
truncation happens upstream of the file write, so only the last N lines reach
the log and the `FAILED` summary is lost. The cost of a bad capture is an extra
full suite run.

## How

- **Good:** `... 2>&1 | Out-File -FilePath suite.log -Encoding utf8`, then slice
  the file for `^FAILED`.
- **Bad:** `... | Tee-Object -FilePath suite.log | Select-Object -Last 5`.
- **Bad:** citing a pipeline's exit status as the run's result — a pipeline exits
  with its **last** command's status. Redirect to a file, capture the status on
  the very next command, then slice.

---
name: aeat-locales-cli
trigger: always_on
---

# AEAT locale catalogue CLI

Perform all locale work through the `dev.locales` CLI; never hand-edit the
`src/cadrumo/locales/{en,es,ca,hu}/` shard trees or the `_intentional_identical.json`
allowlist directly. Verbs: `set LOCALE KEY VALUE` / `remove LOCALE KEY` for
individual leaves, `scaffold` to align catalogues to codebase keys,
`scaffold --check` as the drift gate, and `audit` for a health report.

The catalogue DATA ships under `src/cadrumo/locales/` because the renderer loads
it at runtime, but the maintenance TOOLING is not in the package: it lives at
`dev/locales/`, so the module path is `dev.locales` and the tool runs from a
repository checkout only. There is no `cadrumo.locales` CLI.

The four catalogues are not free-form YAML: a parity gate requires every codebase
key to exist in every locale and every locale to carry the same key set, and an
honesty ratchet allows an untranslated string only when
`_intentional_identical.json` records it with an explicit reason. Hand-editing
lands a key in one locale only, lets a stale key outlive its removed reference,
or slips an untranslated string past the ratchet.

**A new `tr()` key needs a REAL value in all four catalogues.** There is no
sanctioned untranslated state: the scaffold's documented self-referencing
placeholder (value equals key) is refused by a shipped gate, and omitting `ca` or
`hu` trips the parity check. Both escapes are red. When a task says "en/es only,
someone else will translate", obtain the `ca` and `hu` strings before running
`set`, or the tree goes red the moment anything sweeps your working copy.

## Modelo localization lives in these same catalogues

Modelo and revision titles and official names, construct titles, and every
casilla `label` and `help` string live ONLY in these four catalogues, under
derived dotted keys
(`modelo.schema.<modelo-id>.revision.<revision>.casilla.<casilla-id>.label` and
siblings), resolved through `resolve_modelo_localization` /
`lookup_translation_entry`, and managed with these same standard verbs. Spanish
is the mandatory, required source for titles and official names.

**There is no `python -m dev.locales modelo ...` verb family and no
per-modelo registry-local `locales/*.toml` file.** Both were retired; neither may
be reintroduced or recreated. Casilla-schema keys dominate the Spanish catalogue
by volume, and that content is load-bearing, not misplaced.

## How

- **Good:** `python -m dev.locales set es "cli.config.google.help" "..."`;
  after adding or removing a `tr(...)` call, run `scaffold` then
  `scaffold --check`.
- **Good:** `ModeloDefinition.get_title(locale)`,
  `ModeloRevision.get_label(locale)` and a compiled `CasillaDefinition`'s
  `localization_keys` all resolve through `resolve_modelo_localization` against
  these catalogues.
- **Bad:** opening a `.yml` to add a key; or hand-appending to
  `_intentional_identical.json` to silence the honesty gate for a string you
  simply did not translate — the allowlist is for deliberately-identical strings
  with a stated reason, not a mute button.
- **Bad:** expecting `python -m dev.locales modelo scaffold|set|coverage` —
  the verb does not exist.
- **Bad:** creating `registry/aeat/modelos/<id>/revisions/<rev>/locales/*.toml`.

Gates: `test_parity.py`, `test_locale_translation_honesty.py`. Source: ADR
`2026-08-04-modelo-localization-cascade-adr`, superseding
`2026-06-11-modelo-locales-cli-adr`; tooling location per
`2026-08-07-dev-harness-bleed-adr`.

---
name: aeat-naming
trigger: always_on
---

# AEAT domain naming and product identity

## Domain concepts use Spanish stems

Domain concepts that map 1:1 to AEAT surfaces MUST be named with their Spanish
stem in source code, locale keys, CLI verbs, audit-trail field names and event
type values: `iva`, `renta`, `modelo`, `casilla`, `censo`, `borrador`,
`declaracion`, `justificante`, `apoderamiento`, `retencion`, `recargo de
equivalencia`, `expediente`, `sede`. Do not introduce English aliases or English
shim modules (`Vat*`, `Census*`, `Form*`, `Receipt*`) over a Spanish-named
implementation.

AEAT publishes its surfaces and regulatory text in Spanish. An English alias
layer invites drift, duplicates vocabulary in tests and locales, and silently
rots when AEAT updates the Spanish surface.

**Acceptable exceptions:** generic computing vocabulary with no AEAT counterpart
(`repository`, `service`, `validator`, `boundary`, `snapshot`) and cross-cutting
framework concepts (`Settings`, `Registry`, `Snapshot`) stay English.
**By operator directive**, the operator-facing ledger invoice CLI noun is the
English `invoice` (`aeat app ledger invoice --kind issued|received`), while the
internal source-kind taxonomy stays canonical as `payable_invoice` /
`collectible_invoice` — do not collapse those into a bare `invoice` source kind.

Already-public pre-rule identifiers keep their names.

## Product identity versus the tax authority

Use `Cadrumo` in sentence prose and `CADRUMO` in identity contexts for
application-owned surfaces, and retain AEAT names when the referent is the
Spanish tax authority, its official evidence, or its external protocol. The sole
human CLI executable is the exact lowercase token `aeat` — it names the Cadrumo
command contract, not a legacy product alias.

Classifying by spelling alone creates contradictions even for apparently obvious
settings; classify by **ownership and referent** instead, which prevents both
stale branding and corrupted tax-authority semantics.

## How

- **Good:** `CensoSnapshot`, `CensoSnapshotService`, `CensoFactSet`,
  `CensoSyncError`; the CLI verbs `aeat config profile censo file` and
  `censo pull` (a fetch is `pull` and a local artefact is `--file`, per
  `aeat-cli-contract` — never `refresh`); locale keys
  `cli.config.profile.censo.*`; event types `CENSO_APPLIED` and
  `CENSO_DEPENDENT_STAMPED_STALE`.
- **Good:** rename an application-controlled `AEAT_WALLET_DIAGNOSTIC_DUMP_DIR`
  setting to `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR`, while retaining AEAT names
  inside the authority payload stored there.
- **Good:** keep `adapters.outbound.aeat`, official AEAT URLs, legal provenance
  and the `registry/aeat` taxonomy under the CADRUMO package root; invoke the
  human CLI as `aeat` and import the package as `cadrumo`.
- **Bad:** a new `_census.py` re-exporting `CensoSnapshot` as `CensusSnapshot`
  for "compatibility", or authoring a new ADR or plan in English when the AEAT
  surface uses a Spanish noun.
- **Bad:** globally replacing every `AEAT` token with `CADRUMO`, changing the
  name of the authority or of byte-exact official evidence.
- **Bad:** retaining `aeat` for a product import, environment prefix, or storage
  owner, or exposing `cadrumo` as a second human executable.

Source: ADR `2026-07-12-cadrumo-cli-executable-adr`; audit
`2026-07-12-cadrumo-product-rename-audit`; ADR
`2026-06-02-modelo-036-census-sync-adr`.

---
name: aeat-quality-gates
trigger: always_on
---

# AEAT quality gates, roundtrips and fixtures

## Real behaviour, external authority

Write real-behavior tests. Do not use fakes, mocks, stubs, monkeypatches, skipped
tests, xfail markers, or tautological assertions to make gates pass.

**No tautological calculation tests.** Do not assert registry runtime output
against numbers hand-computed from the same registry formula under test. Use
external authority: AEAT workbooks, BOE or AEAT worked examples,
registry-authoritative fixtures, or live oracle replay. When no external numeric
authority exists, test graph wiring, validation errors, provenance, schema shape
or primitive evaluator contracts — do not manufacture `Decimal` expectations from
synthetic inputs.

**Before accepting a calculation test, ask whether it would fail if the registry
formula were wrong against AEAT.** If not, remove or rewrite it. Deriving the
expected value dynamically from the code under test is still tautological,
whether the literal is typed in or fetched at runtime. And a test that encodes a
current defect as the contract is worse than no test — correct it rather than
working around it.

Reject duplicated symbols, shadowed responsibilities, misplaced code, import
cycles, dead code and cross-package private imports. Run structural audits at
milestone and cluster gates.

## Roundtrip every persistence boundary

Write strict roundtrip tests for every **persistence boundary**, not just every
pydantic model: encrypted SQL via `SecureObjectRepository`, TOML manifests, JSON
envelopes, fichero-BOE bytes, worksheet export and pull, and any CLI emit path
that flows over the wire.

**Use real adapters, not mocks** — real key provider, real SQLite engine, real
serializer. A mock returning what the test expects is the canonical
false-positive signal.

**Assert strict pydantic equality across the boundary.** Build a populated model,
push it through the real cycle, load on the other side, assert `model_a ==
model_b`. Partial-field comparison and string-shape checks are insufficient.

**Populate every defaultable field with a non-default value** — a
save-drops-field / load-re-defaults-field regression is invisible when the fixture
uses the default.

**Provide an anti-tautology proof for each boundary class.** Save a record, mutate
the on-disk payload to delete a field, reload, and assert either a
`ValidationError` is raised or strict inequality is surfaced. If this ever passes
with the boundary broken, every roundtrip in the suite is tautological.

**Never use xfail, skip or stub**, and never wrap a roundtrip in try/except to
hide failures. **Carry every roundtrip in the production test path** — tests in
scratch are ephemeral.

## A gate is unproven until it bites

Break the production code on purpose, confirm the gate reds, restore. Prefer a
runtime monkeypatch from **outside** the repo over an edit to a tracked file:
nothing under `src` changes, so a peer's sweep cannot commit the mutation and a
crashed run leaves no residue. The edit form is only unavoidable when the fix is
not yet in the code; announce before opening that window.

An anti-tautology proof over synthetic input is necessary but not sufficient — it
cannot catch a detector correct on synthetic input that never reaches the real
site.

**Allowlists are where the judgement moves**, so require every entry to state its
reason and make stale entries fail. Key exemptions by `(path, enclosing
function)`, never by line number. For any gate pinning registry ids, add a
fixture-anchor test asserting those ids still carry the property they are named
for, or a rename makes the module pass vacuously.

**Never hardcode an exact count as a pass condition.** Gate on the property, not
the tally: a module count or import-site ceiling encodes a moment, trains
everyone to update the constant, and then detects nothing.

**This repo's gates overlap**, so satisfying one can violate another. Verify a fix
against both before committing. The tell is oscillation — if fix A reds gate B
and fix B reds gate A, neither is right and a third shape is needed. Never
resolve it by hiding the construct from one gate's matcher.

## Fixture provenance is declared, never allowlisted

Every test-fixture PDF under a modelo subdirectory MUST declare its provenance
(`real_corpus` or `synthetic_generated`) in its `.json` sidecar. Provenance gates
MUST read that declaration and cross-check it against physical evidence — the PDF
`/Producer` DocInfo — and MUST NOT hardcode per-fixture exception allowlists in
test source.

A gate inferring provenance from a single proxy assumes every fixture in a modelo
directory shares one provenance. That is false: a real sanitised AEAT anchor can
live alongside synthetic specimens for the same modelo. Patching the resulting red
gate with an allowlist re-introduces the honor-system list the gate exists to
remove. A mis-stamped sidecar still reds the gate via the cross-check, so honesty
survives without an allowlist.

## How

- **Good:** a real corpus anchor in an otherwise-synthetic pool stamps
  `provenance = real_corpus`; the gate reads it and confirms the PDF carries no
  generator signature. No test source changes.
- **Bad:** exempting a fixture by adding `(modelo_id, filename)` to an allowlist
  constant; or shipping a gated fixture with no `provenance` field.

Source: ADR `2026-06-01-verification-fixture-roles-adr`. Companions:
`no-silent-under-declaration`, `aeat-worktree-safety` (triaging a red tree-wide
gate).

---
name: aeat-registry-authority-flow
trigger: always_on
---

# AEAT registry authority, schema, identifiers and revision resolution

## The authority pipeline

Treat the modelo registry as a deterministic authoring-compiler pipeline:
TOML authoring tree → loader/compiler → strict schema objects → registry
validation → validated authority → immutable snapshots → runtime projections.

**`ValidatedRegistryAuthority` is the production orchestration boundary.**
Request validated modelos, deadline windows and snapshots through the authority
or a repository facade that owns one. Do not add production paths that call raw
loaders and then independently validate or select revisions.

**`_loader.py` is a compiler implementation detail.** Loader changes MUST
preserve deterministic merge order, reject ambiguous scalar conflicts, include
every read TOML file in cache invalidation, and compile fragments into the
existing strict runtime schema.

**Snapshot construction is authority-owned.** Filing schema providers, query
services, formula execution, export parsing and adapter projections consume
`RegistrySnapshot` or typed projections derived from snapshots — never fragment
paths or partially merged raw dictionaries.

**Invalidate any cache above the loader by the complete registry tree
fingerprint**, including directory-mode manifests and recursive revision
fragments. Never introduce a path-only registry cache that can serve stale TOML.

## Revision content is fragmented

A revision declares its sections — bindings, formulas, casillas, verification
expectations and predicates, constructs, completeness manifest — ONLY in
fragmented subdirectories. The fragment directory's `revision.toml` carries
scalar metadata only, and an inline section table is a hard `RegistryLoadError`.

**Assess coverage from the LOADED snapshot, never a directory listing.** To
decide whether a revision is calc-grade or a casilla is ledger-bound, load
through the authority and inspect the compiled schema; grep fragments only to pin
exact ids. A file-shape glob undercounts the same way — a pattern matching one
shape silently excludes directory-mode fragments, which can hold most of the
corpus. Assume fragmentation until you have checked; both shapes ship. Read a
binding's `source` field before classifying a blank: a `profile` binding absent
from a ledger sweep is not a ledger silent-zero.

## Regulatory values live in the config or the registry

All AEAT schema, constants, thresholds, regulatory codes and registry-shaped data
MUST be defined in the central config or the registry authoring tree — never
inlined as Python literals in feature modules. These values are versioned by
filing year plus revision, so a literal bakes the value into the call site,
scatters the authority, and silently drifts on a new revision.

Read regulatory values through the authority (`authority.snapshot(...)`) and
deployment settings through `load_settings()`, honouring `override_settings()`.
New thresholds, windows and constants land first in registry TOML. A one-line
import from the curated `core.external_constants` re-export layer is acceptable
for a true regulatory leaf constant.

**Acceptable exceptions:** pure mathematical or framework constants, the AEAT
control-letter table, sentinel zeros; and translation KEY literals — but literal
user-facing prose belongs in the locale files.

## Modelo identifiers are the core enum

Production code MUST reference modelo identifiers through the
`cadrumo.core.Modelo` StrEnum, never as bare three-digit string literals. An AST
gate enforces this; a genuine non-identifier occurrence (an article number, a
digit-set membership test, a CLI command-name token) is recorded in the gate's
allowlist with a stated reason.

Use the **bare member** in comparison, membership and dict-key positions; reserve
**`.value`** for plain-`str` contracts (pydantic field values, call arguments,
parameter and CLI-option defaults, returns). A `StrEnum` member compares, hashes,
`str()`s and JSON-serialises identically to its value, so the substitution is
behaviour-preserving.

A modelo that is code-referenced but has no registry definition (a retired form)
is added to the enum and listed in `NON_REGISTRY_MODELOS`, which the
registry-parity gate excludes.

## Revision resolution is law-determined, never injected

Every production calculation, verification, filing, export or projection path
MUST resolve its registry revision from `(modelo, filing_year, period)` through
`ValidatedRegistryAuthority.snapshot` / `select_revision`, or through
`law_selected_revision_for_work_target`, which takes exactly one
`RegistryAuthorityCapture` and delegates to the pure
`assert_work_target_revision`. A stored, literal or operator-supplied
`revision_id` may only be **asserted equal** to that resolution, never injected
as the selector; the requested and stored axes are judged independently against
the same capture, so neither can select the revision the other is judged by.

AEAT binds every triple to exactly one revision by publishing orden, so "which
revision applies" is a derived fact. Feeding a stored id back into resolution
makes the stored value *causal* — the defect class that lets one year's numbers
be computed under another year's norms. The non-overlap window gate guarantees
resolution is unique, so a narrowing can only equal the law-determined pick or
refuse.

**Carried observations stamp their revision and re-confirm it.** Every persisted
calculation observation MUST carry a required, non-empty law-determined
`stamped_revision_id`, and a missing or invalid stamp MUST refuse at strict load.
Every cross-period or cross-year carry MUST re-confirm a populated stamp against
`select_revision` for the source context before trusting the value; a divergent
or unreconfirmable stamp MUST block the carry. The carry path is the one place a
revision error *compounds across years*.

## Period boundaries have one authority

Every period-scoped selection resolves its date span through `Period.contains()`,
built from the canonical year plus the AEAT-token grammar. No call site may
implement a parallel boundary, an inclusion override, or a legacy period alias.
Re-derived start/end math creates off-by-one gaps, overlaps and inconsistent
handling of adjacent quarters; a continuity invariant keeps the boundary gap-free
and overlap-free.

## How

- **Good:** load the work unit, resolve the snapshot from its `filing_year` and
  `period`, then assert equality and raise an instructive refusal naming both
  revisions on mismatch. A creation-time `--revision` is accepted only when it
  names exactly the resolved id.
- **Good:** the producer persists the stamp from the law-selected snapshot it
  already holds; anti-tautology coverage deletes the persisted field and proves
  loading fails.
- **Good:** `if unit.modelo != Modelo.M303:` and `{Modelo.M100: ...}` use bare
  members; `modelo=Modelo.M720.value` for a `str`-typed field.
- **Good:** parse `--year 2026 --period 1T` to a `Period`, then filter with
  `period.contains(row.date)`.
- **Bad:** passing a stored `revision_id` into `authority.snapshot(...)` on a
  calculation path, so resolution is *selected* by the stored value.
- **Bad:** reconstructing, defaulting or bypassing a missing stamp; or treating a
  divergent stamp as a warning instead of a blocker.
- **Bad:** `if unit.modelo != "303":`; an inline
  `THRESHOLD = Decimal("3005.06")`; redeclaring period codes as bare-string sets.
- **Bad:** re-introducing a section table inline in a `revision.toml`, or
  `ls bindings/ | wc -l` as the sole signal of whether a revision is calc-grade.
- **Bad:** accepting an alternate boundary grammar (`2026Q1`, `ANUAL`, `Q1`), or
  open-coding `start <= row.date <= end` with locally derived dates.

Gates: `src/cadrumo/core/tests/test_modelo_string_usage.py`, `test_modelo.py`.
Source: ADRs `2026-07-02-arch-remediation-registry-format-adr`,
`2026-06-10-modelo-enum-hardening-adr`,
`2026-06-10-period-revision-resolution-adr`,
`2026-06-10-ledger-filter-period-adr`.

---
name: aeat-registry-bindings
trigger: always_on
---

# AEAT registry binding contract

## One validator, run at registry build

Every binding `source` family MUST expose a single
`validate(binding) -> list[str]` validator — accumulating, never raising —
registered in the one dispatch table keyed by `BindingSourceKind`, and run by the
registry-build section validator for ALL families. Op and fact invariants MUST be
enforced at **build** time, never resolve-time-only; resolve-time helpers may
remain as backstops. Preserve the underlying pydantic field error in the
diagnostic — never flatten it to a generic "malformed selector".

Validation was once scattered across three incompatible conventions, with
invariants run at build for some sources and only at resolve time for others, so
a malformed binding shipped clean through snapshot build and failed only when a
taxpayer's calculation ran.

## Aggregation is a typed model with a closed op enum

A binding's aggregation MUST be the typed `BindingAggregation` model carrying a
closed `BindingAggregationOp` enum declared in `core`, never a free-form
`Mapping`. No call site may re-parse `aggregation.get("op")` or pick its own
default: `binding_aggregation_op(binding)` returns the typed op and applies the
one declared per-family default in one place. A new op is added to the enum, so
the typed field validates it at build.

The op was once re-derived at roughly ten sites with divergent silent defaults,
so the effective default was source-dependent and unauditable. The relation and
formula-expression `op` axes are separate concepts, out of scope.

## Source kinds are one canonical core taxonomy

The `source` closed set MUST be the single canonical `BindingSourceKind` StrEnum
in `core`; `DataBindingDefinition.source` is typed as it, and every per-family
collection MUST be **derived** from it, never hand-listed. A new kind is added
with its value byte-identical to its stored token, and a registry-versus-enum
parity gate keeps them in lock-step. A hand-listed ledger collection once carried
only half the ledger kinds, so the ledger preflight misclassified the rest.

**Before deleting a retired member**, reconcile every validation, schema, fixture
and test consumer into one coherent accept-or-reject state and prove the owning
collection gate is green — a member can look retired at the CLI layer while still
powering a contradictory registry-validation surface.

## Values carry provenance at casilla parity

Every persisted and operator-facing binding value MUST carry its `legal_refs`,
`source_refs` and a typed `BindingSourceKind` source, at parity with casilla
provenance. The filing builder populates them from the binding definition it
already holds; a hardcoded free-text source string is forbidden. The CLI bindings
list and preview payloads MUST expose the same grounding as typed models, never
an untyped dict bag.

There was a provenance asymmetry at exactly the operator boundary: casilla values
carried full grounding to draft and export while binding values were flattened to
a hardcoded source string, so an operator inspecting a bound value could not see
its legal basis.

## Relation-targeted slots declare relation_prefill

A binding that exists only as a relation's `target_binding` materialisation slot
MUST declare `source = "relation_prefill"`, never `source = "previous_filing"`. A
`previous_filing` binding MUST satisfy the direct-selector predicate, and registry
validation refuses a binding that is both relation-targeted AND
previous-filing-resolvable — the M303 IVA-wallet compensación slot being the sole
documented carve-out.

Slots were once mislabelled `previous_filing` for a value only relation
resolution could produce, so one fold-in looked like two mechanisms and the
enrolled resolver skipped the non-direct slot by design, leaving it dormant.

## How

- **Good:** a new family is added to the dispatch table with a
  `validate(binding) -> list[str]` entry, routing the selector through
  `selector_as_dict` and surfacing the field message verbatim.
- **Good:** `frozenset(k for k in BindingSourceKind if ...)` — complete by
  construction.
- **Good:** `ModeloBindingValue` carries `legal_refs`, `source_refs` and
  `source: BindingSourceKind`, read from the binding definition.
- **Good:** a same-modelo direct carry keeps `source = "previous_filing"` and
  passes the direct-selector predicate.
- **Bad:** a per-family validator that raises, or a private validated selector
  invoked only inside the resolver.
- **Bad:** `str((binding.aggregation or {}).get("op", "sum"))` inline, or
  widening `aggregation` back to a bare mapping.
- **Bad:** a hand-listed string set for a family, a mixed enum/string Literal on
  `source`, or renaming a stored token to "align" it.
- **Bad:** constructing a `ModeloBindingValue` with a literal free-text source,
  or a bindings payload that omits grounding while the casilla payload carries it.
- **Bad:** a relation `target_binding` slot declaring `previous_filing` with a
  non-direct selector.

Gates: `test_binding_build_validation.py`, `test_binding_aggregation.py`,
`test_binding_source_kind_taxonomy.py`,
`test_binding_value_provenance_roundtrip.py`,
`domain/calculations/registry/_validate_relation_sources.py`. Source: ADRs
`2026-06-14-bindings-interface-hardening-adr` (A, B, D),
`2026-06-10-calculation-aggregation-taxonomy-adr`.

---
name: aeat-vaultspec-centralisation
trigger: always_on
---

# AEAT vaultspec centralisation

Keep all repo-specific agent rules in `.vaultspec/rules/`. Do not place project
rules, policies, handover mandates, or provider-specific instructions in any
provider's own config; treat provider files as generated outputs, not authorship
surfaces.

**Do not author new rules.** Codification is retired: the always-on corpus is
loaded into every agent context, so each new rule taxes every session forever.
Record durable lessons in the campaign's `.vault/audit/` document instead.

**Rules must not reference private agent memory** — a rule is repo-committed and
shared, so a citation to a private memory file is a dangling reference for every
other reader. State the mandate inline.

Correct or remove an existing rule on its `.vaultspec/rules/*.md` source (or via
`vaultspec-core spec rules edit|remove`) and propagate with
`vaultspec-core sync`. Never hand-edit the generated `.claude/`, `.agents/`,
`.codex/`, `AGENTS.md`, `GEMINI.md`, or `CLAUDE.md` copies — the next sync
reverts the change, so the fix is lost.

Prefer merging a new mandate into the nearest existing rule over adding a file.
When a rule's name is cited from `src/` docstrings, keep the name even while
compressing the body.

---
name: aeat-worktree-safety
trigger: always_on
---

# Cooperative Git handling in a shared worktree

## Rule

Preserve peer work by default. Follow explicit operator Git instructions for the named operation, targets, and current worktree state.

## How

- Serialize repository Git writers and wait for hooks and Git LFS.
- `commit everything` authorizes current non-ignored worktree content. Split it by domain. Push only when requested.
- A bare commit consumes the shared index. A pathspec commit consumes named working-tree files. Use an isolated index only for mixed same-file ownership, then verify the committed diff.
- Before pushing, inspect the outgoing commits, ref, and remote target.
- Treat an advancing lock as active. For a stable lock, attribute the exact repository process; stop it only when authorized. Remove the unchanged lock only after that process is gone. Never kill unrelated Git processes.
- Stash, reset, restore, clean, history rewrites, force-pushes, ref deletion, and worktree removal require explicit authorization and exact-target verification.
- Report scoped validation separately. Required release gates still govern releases.

## Why

`2026-08-08-shared-tree-coordination-audit` and `2026-07-24-worktree-commit-attribution-audit` show both hazards: broad commits capture peer work, while absolute prohibitions block authorized delivery.

---
name: firmware-reference-parity.builtin
trigger: always_on
---

# Firmware reference parity: named artifacts must resolve

A worked example of codification applied to an audit finding. Promoted from the firmware
wording review audit following the discipline described in the `vaultspec-codify` rule.

## Rule

Every skill, persona, template, or CLI verb named in firmware prose - the bundled rules,
system fragments, skills, personas, and templates under `src/vaultspec_core/builtins/` -
must resolve to a shipped artifact of exactly that name, and a rename must update every
referencing surface in the same change.

## Why

The firmware is consumed by agents at session load, so a dangling name in an always-on
mandate degrades every downstream session. The
`2026-06-10-firmware-wording-review-audit` documented two such breakages: a phantom
`vaultspec-write-plan` skill name routing the Plan phase across the pipeline table,
intent table, and catalog (the shipped directory is `vaultspec-write`), and an orphaned
`ref-audit.md` template left behind by a rename. Both were renames that updated one
surface and left the old name standing in the others, contradicting the firmware's own
consistency mandate.

## How

- Before naming a skill, persona, template, or verb in firmware prose, confirm it ships:
  `vaultspec-core spec <resource> list` (one of `rules`, `skills`, `agents`) enumerates
  the shipped artifacts to check names against, and the template files live under
  `src/vaultspec_core/builtins/templates/`.

- **Good:** renaming a skill updates the pipeline table, the intent table, the catalog,
  and every cross-reference atomically in one change, so no surface names the old slug.

- **Bad:** renaming the skill directory (or template file) and leaving the old name in
  the system prompt, a discipline rule, or another skill's prose; the next agent loads a
  reference to an artifact that no longer exists.

## Status

Active. Until a structured firmware-name linter lands, the cross-surface sweep is the
author's discipline; `vaultspec-core spec <resource> list` is the check.

## Source

Audit `2026-06-10-firmware-wording-review-audit`, findings REVIEW-001 and REVIEW-002 and
the campaign's renamed-artifact root cause. Sibling decision ADR
`2026-06-09-firmware-wording-review-adr` (decisions D1 and D7).

---
name: generated-reference-is-cli-owned.builtin
trigger: always_on
---

# Generated reference is CLI-owned: regenerate, never hand-edit the managed zones

A worked example of codification applied to an audit finding. Promoted from the CLI
reference automation audit following the discipline described in the `vaultspec-codify`
rule.

## Rule

The bundled CLI references' generator-managed regions - delimited by the
`vaultspec:generated:begin` and `vaultspec:generated:end` markers in
`src/vaultspec_core/builtins/reference/cli.md` and `docs/CLI.md` - are updated only by
running `vaultspec-core spec reference generate`, never by hand-editing inside the
markers; the `--check` mode gates pre-commit and CI and fails until both references
match fresh output.

## Why

The bundled reference is hand-authored prose wrapped around generator-owned zones, and
the hand-authored content drifted from the live Typer surface every time a flag or
enumeration changed. The `2026-06-10-cli-reference-automation-audit` documented that
drift (the prior reference omitted live signatures, D6) and that the two surfaces
drifted in ordering against each other (`GENREVIEW-003`, first divergence at index 7).
The generator plus `--check` is the durable guarantee: drift is mechanically corrected
and CI fails deterministically until the managed regions equal fresh output.

## How

- **Good:** a new flag lands on a verb; run `vaultspec-core spec reference generate`,
  review the regenerated managed region, and commit it. Both `cli.md` and `docs/CLI.md`
  inventories regenerate from one Typer walk and cannot diverge.

- **Bad:** hand-edit a signature or option table inside the
  `vaultspec:generated:begin/end` markers; the edit is overwritten on the next generate
  and `--check` fails CI in the meantime.

- Hand-written prose **outside** the markers (the entry-point table, global-options
  narrative, sync-vocabulary section, environment-variable table) is still
  hand-maintained normally; the generator reads but never rewrites those zones.

## Status

Active. The generator and its `--check` gate have shipped across both managed files. The
rule's intent (the managed zones are CLI-owned) is now structurally enforced; the
author's remaining duty is to regenerate rather than hand-edit inside the markers.

## Source

Audit `2026-06-10-cli-reference-automation-audit`, the generator design plus findings
`GENREVIEW-002` and `GENREVIEW-003`. Sibling decision ADR
`2026-06-10-cli-reference-automation-adr`.

---
name: modelo-export-mirrors-official-structure
trigger: always_on
---

# Modelo exports mirror the official structure

Every modelo workbook export — offline xls and online Sheets alike — MUST be
generated from the single shared plan builder, render live spreadsheet formulas
with an explicit labelled start (input) and final (resultado) anchor, and pass
the registry-grounded parity gate on casilla set and numbering. A structural
divergence from the official AEAT layout is a hard failure, never a warning.

The plan is typed presentation facets defined once in the builder and
materialised identically by both transports; parity is checked against the same
registry authority the engine uses, not a hand-maintained spec.

**Casilla section order is deliberately not gated.** Section is presentation; what
must mirror the official modelo is the casilla SET and its numbering, both of
which are gated. Do not assert section order and do not rely on it.

## The fixed-width export carries the same completeness gate

`export_draft` MUST, before writing any bytes, assert that every casilla that is
a calculation RESULT (declares a formula) or is schema-required, **and** that the
completeness manifest lists **and** the official record files can represent,
carries a real value on disk. A blank such casilla means the calculation did not
populate it — a structurally thin file behind a valid digest — and MUST raise a
hard `FilingExportError` enumerating every missing casilla with its official
number and segmento.

Optional operator-input casillas (retenciones, prior payments, deductions the
taxpayer may legitimately not have) are NOT required: a blank slot is a valid
zero, excluded from the required set.

**The rendered set keys on value presence (`v.value is not None`), never on
casilla-id membership**, because `build_draft` emits an EMPTY row for every
declared casilla. The gate is scoped to `format == "fixed_width"`; an
`xml_dictionary` export omits an absent casilla as a legitimately absent optional
element.

## A generated export tree is produced and checked by the generator's own authority

`dev/registry` owns the whole export-tree lifecycle, and every job in it has ONE
entry point. `validate_generated_export_tree` is the pre-cutover proof;
`publish_validated_generated_export_tree` validates, journals, swaps, verifies and
finalises under an exclusive lock with rollback; `check_generated_export_tree`
regenerates into an isolated candidate registry, validates that candidate through
the real loader and registry authority, then requires the published target to
attest to the same authorities with identical normalised loader semantics and
identical bytes.

Calling `render_complete_export_tree` straight into `src/`, or comparing committed
fragments with a directory diff, RE-IMPLEMENTS those and loses what they prove. A
byte comparison cannot ask whether a tree is a valid registry authority; it can
only say two directories differ. Modelo 210 and 232 were first generated that way,
so both were written without the pre-cutover proof, and a coverage refusal that
should have blocked publication surfaced later, at registry-load time.

Before building generator or export tooling, find the existing authority by MEANING
rather than reading one module and extending outward: record designs, semantic maps,
render profiles, provenance manifests, check mode and publication mode are one
pipeline, and its reach is not visible from any single file. The same applies to a
shape rule -- the parser and the development intermediate once held two copies of the
auxiliary-header contract and drifted into disagreeing about which modelos have one.

## How

- **Good:** a gate that drives `check_generated_export_tree` against the committed
  tree, so drift and invalid-authority both red through the one contract.
- **Bad:** rendering into the registry tree by hand, then asserting with `filecmp`;
  or a second copy of a shape rule kept "for independent validation".
- **Bad:** computing the rendered set from casilla-id membership — every EMPTY
  casilla then counts as rendered and the gate never fires on a real thin draft.
- **Bad:** writing a thin file because the digest is valid. The digest is a
  byte-integrity lock, not a completeness claim.
- **Bad:** writing formatting, anchors or evidence in one transport but not the
  other, or downgrading a structural divergence to a warning.

Source: ADRs `2026-06-03-modelo-export-workbook-parity-adr`,
`2026-07-01-fichero-boe-parity-gate-adr`. Gates:
`test_export_completeness_gate.py`, `test_export_completeness_sets.py`,
`test_fichero_boe_completeness_parity.py`.

---
name: no-legacy-compatibility
trigger: always_on
---

# No legacy or backwards-compatibility support

This project has no released data and no deployed callers. Carry ZERO legacy
code: no migration of old on-disk formats, no read-tolerance of pre-current data
shapes, no deprecated aliases, no retired-field handling, no version-upgrade
ALTER passes, no coercion branches for old serialised records. When a format,
schema, key derivation, or API shape changes, **DELETE the old surface and its
tests outright** — never add a bridge, fallback, or shim to read what an earlier
version of THIS app wrote.

Every migration pass and read-tolerance branch obscures the canonical flow and
defends behaviour no caller needs. This is the deletion-side companion to
`aeat-architecture-boundaries`, which forbids *introducing* shims.

## Distinctions, each normative

- **Delete, do not bridge.** Delete a from-birth migration module, its bootstrap
  call site, and its harness — do not refactor it.
- **Refuse, do not tolerate.** A read path for a written-from-birth envelope,
  prefix or typed shape RAISES on a missing prefix (that is corruption now) and
  never silently returns the raw legacy form.
- **CREATE is not migration; keep it.** Fresh-schema bootstrap that materialises
  the current shape on first access is forward-functional; an ALTER pass
  upgrading an OLDER table is legacy.
- **External-world variability is not our legacy; keep it.** Resilience for AEAT
  portal variations, BOE corpus formats, PDF producer quirks, and AEAT regulatory
  revisions — each modelo revision year is CURRENT law for its filing year.
- **AEAT regulatory status is never CODE legacy.** A real modelo AEAT still
  supports is a current product feature. Only delete a surface that exists to
  read or migrate data an OLDER VERSION OF THIS APP wrote.
- **A forward version FIELD is not legacy; keep it.** A `schema_version` marker or
  a `max_supported_version` ceiling refusing a FUTURE shape is
  forward-compatibility. Only code that BRANCHES on an OLD version is legacy.
- **Key-management caution:** deleting a key-schedule or DEK-derivation branch can
  strand encrypted data. Confirm the creation path mints only the current schedule
  first — owner-gated, not autonomous.

## The regime is a one-way core constant

The persisted-data compatibility posture is governed by
`cadrumo.core.COMPATIBILITY_REGIME`, flipped `PRE_RELEASE -> RELEASED` **only** by
an accepted checkpoint ADR whose same commit freezes
`cadrumo.core.RELEASED_FORMAT_FLOORS` at the then-current per-format durability
floors. The regime MUST NOT be read from `Settings` or the environment, and the
enforcing gates MUST NOT be skipped, weakened, or monkeypatched. A runtime flag
can differ per machine and be patched in its own gate; a repo-committed constant
has a conscious owner, a version-milestone tripwire, and gate teeth.

**Pre-checkpoint (today):** everything above governs unchanged — delete not
migrate, floors may chase the current version, no read-tolerance of pre-current
shapes.

**Post-checkpoint:** for every persisted format the durability floor is FROZEN at
its released value; every version bump MUST land, in the same commit, its one-hop
upgrader (for the archive tier, a version-aware reader), a committed pre-bump
serialized fixture, and a restorability test loading the old bytes through the
real production read path. Strict persisted-read models stay `extra="forbid"`
with the pre-validation upgrade hop as the ONLY sanctioned tolerance point, and a
persisted-model shape change rides a version bump plus upgrader, never a loosened
model. This rule then narrows to "no legacy beyond the released floor" —
read-tolerance of shapes nothing released wrote, and shims and aliases, stay
forbidden in both regimes.

Installing the dormant regime constant, the empty upgrader registries, and the
regime-aware gates does not violate this rule: they read no old shapes and
migrate nothing.

## How

- **Bad, post-flip:** raising any durability floor above its released value to
  dodge writing an upgrader; flipping the regime back; reading it from settings;
  or loosening a persisted read model instead of versioning the shape.
- **Bad, either regime:** fabricating an old-version fixture or upgrader before a
  genuine post-checkpoint bump needs one — that invents shapes nothing wrote.

Source: ADRs `2026-07-09-compatibility-lifecycle-adr`,
`2026-07-08-released-data-durability-adr`; inventory
`2026-06-10-zero-legacy-purge-research`. Enforced by the regime-aware lineage
gates and `test_compatibility_lifecycle_gate`.

---
name: no-silent-under-declaration
trigger: always_on
---

# No silent under-declaration; evidence and oracles must be real

## The gate must not grant completeness over an under-declaration

A modelo verify gate MUST NOT grant `verified_complete` with zero findings on a
draft that under-declares. Whenever a positive economic input is declared
(resultado contable, rendimiento de módulos, ingresos) but the dependent base or
cuota resolves to zero and no offsetting reduction is declared, the gate MUST
surface at least an ADVISORY finding.

A human files outside the application, so an explicit operator-facing alert —
never a silent grant — is the minimum safeguard against filing a zero-tax return
on positive activity. A verify gate once granted completeness for a sociedad with
substantial resultado contable but zero base and zero cuota, because base
imponible was a bare manual input with no derivation.

**Watch the unwatched direction too.** This apparatus is built against
under-declaration; nothing in it watches a taxpayer over-paying, and that
direction produces valid output, no refusal and no signal to the taxpayer. When
auditing a chain, deliberately probe the opposite direction — the structural tell
is a **restrictive provision used as a default**, which silently captures the
population the limiting article does not govern.

## Grounding claims need a bundled oracle AND engine reproduction

A casilla listed in a verification expectation's
`externally_grounded_casilla_ids` MUST be backed by a bundled AEAT-authoritative
oracle payload carrying the expected figure (a Renta WEB Open replay under
`corpus/parity_replays/renta_web_open/`, or a manual worked-example oracle under
`corpus/manual_oracles/`, keyed by `expected_by_casilla_id`), AND the registry
engine MUST independently reproduce that figure in a parity test.

Never fabricate a grounding figure, never hand-compute it from the registry
formula under test, and never declare the ids without both.

**Enrollment in a verification expectation is NOT grounding.** Enrollment only
reconciles filed-versus-engine; grounding is the stronger claim that the engine
value is checked against an independent AEAT authority. A value reconciled only
against the app's own engine cannot catch a systematic engine error the filing
matches.

**The oracle must follow the fix, never precede it.** Building an oracle that
asserts a currently-wrong figure converts a live defect into verified behaviour
behind an AEAT-branded test name, which is harder to find later than the open
gap. Never force a figure with an override reaching beneath a guard every real
filing passes through — a fixture proving a chain works in a configuration no
filing can reach reads as coverage.

## Suppression is grounded in registry classification, never the schedule

A cross-period dependency may be scoped out of the clean-state gate as
not-applicable ONLY on a registry signal on that dependency's own
`DependencyClassificationDefinition`: `taxpayer_files_source = false` (suffered
retenciones), or `conditional_on_economic_activity = true` combined with a
**fail-closed** `taxpayer_files_economic_activity is False` (pagos fraccionados).

The suppression set MUST derive from `snapshot.revision.dependency_classifications`,
never from the deadline-engine obligation schedule — the schedule is an
INCOMPLETE signal that over-suppresses other targets' enforced sources. A taxpayer
who DOES file the source, and the undeclared case, stay enforced.

## Local-filed observations are non-official evidence

Observations persisted by the local `file` flow MUST carry a non-official
`source_kind` (`app_filing`) and MUST NEVER be classified official: the one
official-evidence authority is `ObservationSourceKind.is_official_aeat`
(`application/calculations/_observations_repository.py`), which satisfies the
cross-period clean-state gate for `aeat_sede_justificante`,
`aeat_sede_live_capture` and `aeat_csv_register` only, and MUST stay `False`
for `app_filing`.

Automatic cross-period carry may feed calculate and draft from these
observations, but they must never substitute for external AEAT filing evidence. A
same-filing-year local chain may reach local verify and export ONLY when the
chain is present, value-consistent, revision-confirmed, and its only blockers are
the official-evidence delta — and that path MUST surface a non-blocking
non-official-local-chain advisory and MUST NOT assert AEAT acceptance. Cross-year
priors, operator-manual sources, missing data and value or revision divergence
remain blocking.

## How

- **Good:** the revision declares an ADVISORY `verification_predicate` such as
  `implies_nonzero([...])`. It holds trivially when the antecedent is at or below
  zero (no false positive on losses) and fires only when the antecedent is
  strictly positive and the consequent zero, surfacing a non-blocking WARNING
  grounded with `legal_refs`.
- **Good:** an id is declared grounded only after the bundled oracle carries the
  AEAT literal figure with a raw-evidence locator AND a test proves the engine
  independently computes it. Where a manual states contradictory figures, ground
  on the one it states repeatedly and the engine re-derives bottom-up, and
  document the discrepancy.
- **Good:** a suffered-retencion source marked `taxpayer_files_source = false`
  scopes out as a **visible** not-applicable advisory, never silently.
- **Good:** the local filing path stamps `source_kind="app_filing"`, and a
  regression asserts `is_official_aeat` is `False` for the `app_filing` member.
- **Bad:** shipping a manual base or result casilla with no derivation and no
  guard, so the gate grants completeness on positive input.
- **Bad:** a blocking rule refusing legitimate positive-result/zero-base filings
  (negative result, full loss compensation, exemptions) — the guard must
  distinguish the suspicious case and stay advisory while legitimate zero-base
  cases exist.
- **Bad:** adding a grounded id because the engine emits a plausible value, with
  no bundled oracle; or authoring an expected figure by copying the registry
  formula's own output.
- **Bad:** scoping out because the source modelo is missing from the
  deadline-engine schedule; or suppressing on an undeclared profile signal, which
  fails open.
- **Bad:** making `is_official_aeat` return `True` for `app_filing`, or adding
  any locally-produced source kind to the official set.

Gate: `test_external_oracle_grounding_enrolled.py`. Source: ADRs
`2026-06-02-modelo-200-base-determination-adr`,
`2026-07-01-verification-power-adr`,
`2026-06-19-m100-dependent-modelo-applicability-adr`,
`2026-06-09-modelo-iva-routing-carry-adr`.

---
name: sensitive-financial-data-secure-storage-only
trigger: always_on
---

# Sensitive financial data, and the AEAT safety gates

## Secure storage is the only home

All sensitive financial data — every purchase invoice, every incoming or outgoing
business invoice, every bank statement and supporting document, and any decrypted
evidence bytes derived from them — persists ONLY inside the encrypted
secure-storage backend, accessed through the active-profile-bucket runtime
wrapper (`secure_object_repository_for_active_bucket` /
`secure_object_repository_for_bucket`, the `SecureObjectRepository` substrate,
and the content-addressed `AttachmentStore` that wraps it).

No code path may write or persist sensitive financial data anywhere else: no temp
files, no scratch directories, no plaintext side stores, no on-disk caches, no
logs. **Decrypted bytes may exist only transiently in process memory and must
never be written out.** A path pointer to a cleartext file on operator disk is NOT
a valid persistent home; the bytes themselves belong in secure storage.

This is the load-bearing confidentiality guarantee of the whole application. An
early design proposed a decrypted-temp-file route for subprocess agents and
framed off-host upload as a tunable boundary; the operator rejected it outright —
removing sensitive financial data from secure storage, by temp file or off-host,
is never acceptable, and categorically unacceptable for gestors or serious
professional use.

## Never file, never mutate remotely

**Never perform live AEAT submission.** Build, validate, verify, export, and
require human filing outside the app. Live-write paths are prohibited unless a
future accepted ADR explicitly replaces this rule.

Guard every external AEAT write surface behind explicit live-test controls; use
`CADRUMO_LIVE_TESTS_ENABLED` for opt-in and keep dry-run behavior as the default.
Any read-only AEAT probe is pinned to the consulta view and **fails closed** on a
filing-tool or procedure-launcher landing.

Reject tests or code paths that can file, mutate, notify or submit remotely
without an explicit safety gate and auditable provenance.

## How

- **Good:** invoice and attachment bytes are written and read through the
  content-addressed `AttachmentStore`, wrapping encrypted `Envelope` records at
  `FINANCIAL` sensitivity via the active-bucket wrapper; a consumer reads them
  into memory and writes nothing to disk. A model that must read a document runs
  **on-host** (in-tree extraction or a local vision model fed in-memory base64);
  any off-host transmission is gated behind an explicit, per-invocation,
  default-off, gestor-barred consent acknowledgement, and never uses a
  file-writing transport.
- **Bad:** materialising decrypted evidence to a temp file — even
  bounded-lifetime, mode 600, promptly removed — for a subprocess to read by
  path; storing only a `source_path` to a cleartext file as the durable home; or
  writing sensitive values to logs, a plaintext side store, an on-disk cache or a
  scratch dir.

Source: operator directive; ADR `2026-06-10-llm-evidence-classification-adr`.
Companions: `aeat-ledger-contract` (evidence bytes, not links),
`aeat-calculation-grounding` (grounding tax semantics in official sources).

---
name: vaultspec-archive-discipline.builtin
trigger: always_on
---

# Archive discipline: audit incoming references before retiring a feature

A working example of codification applied to a real audit finding. This rule was
promoted from the rolling CLI UX audit (finding B9) following the discipline described
in the `vaultspec-codify` rule.

## Rule

Before invoking `vaultspec-core vault feature archive <feature-tag>`, run the same verb
with `--dry-run` as the canonical discovery pass and audit the preview for incoming
references: documents outside the feature whose `related:` frontmatter points at
documents inside it. Decide whether each incoming reference should be rewritten,
acknowledged as dangling, or block the archive entirely before applying the real run.

## Why

The rolling CLI UX audit's B9 finding documented compounding gaps in the archive verb:
no preview, no reversal verb, silent breakage of cross-feature `related:` links, and a
destructive auto-fix path. The CLI has since closed the verb-level gaps: the archive
verb carries `--dry-run`, a paired `vaultspec-core vault feature unarchive` verb
restores a mistaken archive, and archiving a nonexistent tag exits 1 with an error
(re-verified against the live CLI on 2026-06-10, `vaultspec-core --version` 0.1.26).
What the CLI cannot decide is whether an incoming cross-feature reference is provenance
to preserve, a stale link to drop, or a dependency that should block retirement. That
judgment is this rule.

## How

- Run `vaultspec-core vault feature archive <feature-tag> --dry-run` and read the
  previewed changes; classify every incoming reference before the real run.
- After the real run, verify `vaultspec-core vault check all` stays green. If the
  archive was a mistake, `vaultspec-core vault feature unarchive <feature-tag>` reverses
  it.

## Status

Active. The CLI improvements this rule anticipated (`cli-memory-lifecycle`
`W02.P04.S14`) have landed: `--dry-run` is the canonical discovery pass, `unarchive` is
the reversal verb, and typo'd tags fail loudly. The rule's intent (audit incoming
references before retirement) survives the verb improvement; the discovery procedure now
lives in the CLI preview.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), finding B9 critical. Sibling
decision ADR `2026-05-17-cli-memory-lifecycle-adr`. Umbrella plan step `W02.P04.S14` in
`2026-05-17-cli-simplification-ux-plan`.

---
name: vaultspec-cli.builtin
trigger: always_on
---

# Vaultspec Core CLI

This project is vaultspec-managed. See `vaultspec.builtin.md` for framework rules and
workflow concepts.

## Mandate

All `.vault/` reads, mutations, audits, and repairs route through `vaultspec-core`
owning-verb logic; never hand-write frontmatter, filenames, plan structure, or new
`.vault/` documents (editing scaffolded body prose is permitted, see "Allowed manual
edits"). The vaultspec MCP tools are the primary transport where the server is
connected, the `vaultspec-core` CLI verbs otherwise; both terminate in the same
owning-verb logic that enforces templates, taxonomy, wiki-links, and schema, so
bypassing it produces drift the `check` tool and `vaultspec-core spec doctor` will flag.

## Orientation

Orient before working in a project you have no session context for: the `status` tool
reports the in-flight plans and their next open Step, and the `find` tool locates the
documents and features behind them (CLI: `vaultspec-core status [TARGET]`). Orientation
is descriptive, read-only, and the zeroth move, not a pipeline phase.

## Tools and operations

The nine MCP tools cover the hot path by capability: `status` (orientation), `find`
(document and feature discovery), `create` (scaffold documents, batchable), `edit`
(body-prose edits, batchable), `plan_progress` (mark Steps checked or unchecked),
`plan_edit` (author and restructure Step rows), `check` (validate and repair), and the
`discover`/`invoke` gateway that reaches every remaining verb.

Operations without a first-class hot tool fall into two honest bands:

- **Gateway-only, CLI-first:** `vaultspec-core sync`,
  `vaultspec-core spec <resource> sync`, and the above-Step plan verbs
  (`tier promote/demote`, `wave`, `phase`, `epic intent`). The `discover`/`invoke`
  gateway also reaches these, but `invoke`'s destructive annotation forces host
  confirmation on every call, so the CLI is the better default even when connected.
- **CLI-only:** `vaultspec-core vault feature index`,
  `vaultspec-core spec mcps add/remove/sync`, and `vaultspec-core uninstall` have no MCP
  path at all; run them through the CLI.

For anything else, the `discover` tool and the bundled CLI reference
(`.vaultspec/reference/cli.md`, locally resident) are the catalogs of every command,
option, argument, and exit code.

Where the vaultspec MCP server is not connected, the `vaultspec-core` CLI verbs carry
every operation; the bundled CLI reference is the catalog.

## CLI fallback

- Run `vaultspec-core <cmd>`, or `uv run --no-sync vaultspec-core <cmd>` in uv
  environments; `--target DIR`, `--dry-run`, `--json`, `--force`, and `<cmd> --help`
  cover targeting, previewing, and the full flag and exit-code reference.
- Sync-shaped results (`vaultspec-core install`, `vaultspec-core sync`,
  `vaultspec-core spec <resource> sync`, `vaultspec-core migrations run`) read with one
  vocabulary - `created`, `updated`, `unchanged`, `removed`, `restored`, `skipped`,
  `failed`; `unchanged` is a successful no-op, `skipped` carries a reason, only `failed`
  stops the pipeline.

## Allowed manual edits

Permitted: editing body prose of a document scaffolded through the `create` tool or
`vaultspec-core vault add`, and editing sources under `.vaultspec/rules/`, `skills/`,
`agents/`, `hooks/`, or `mcps/` followed by `vaultspec-core sync`. Forbidden:
hand-writing frontmatter, filenames, or new `.vault/` documents, and editing files
inside generated provider directories (`vaultspec-core sync` regenerates them).

---
name: vaultspec-discovery.builtin
trigger: always_on
---

# Codebase and intent discovery

Begin every pipeline phase - Research, ADR, Plan, Execute - by grounding in what the
project already decided and built. The project's own benchmarking is unambiguous: a
semantic-search-led hybrid sweep finds a feature fastest and at the lowest context cost
\- roughly 1.3-2x cheaper than broad keyword search on a large tree - and recalls
governing decisions with near-zero noise. Lead with it. The validated sequence is locate
by meaning, read the epicenter whole, confirm with grep:

1. **Locate by meaning.** For code, lead with
   `vaultspec-rag search "<concept and domain nouns>" --type code` (narrow with
   `--language`/`--path`); it reaches the right file in about one call where broad
   globbing floods context. For decisions and intent,
   `vaultspec-rag search "<intent>" --type vault --doc-type adr` - the directed ADR
   filter, sharper than catch-all `--type vault`. `vaultspec-core status [target]`,
   `vaultspec-core vault list`, and `vaultspec-core vault graph` are first-class for
   orientation, in-flight plan state, and project health - reach for them to get your
   bearings on intent. For a small, well-named module, list the directory.
1. **Read** the epicenter file - or, when extending a feature, the nearest existing
   analogue - in full. This whole-file read is the breakthrough in nearly every run.
1. **Confirm** exact symbols and insertion points with a targeted grep, which is sharper
   than semantic search at exact-symbol lookup.
1. For decision discovery, round out recall by listing `.vault/adr/` and filtering by
   feature - semantic search alone can miss lower-ranked or opaquely-named records.

Do not lead with broad `Glob`/grep sweeps; their context cost scales badly on large
codebases, and grep earns its place at the confirmation step. Where `vaultspec-rag` is
not installed, the `vaultspec-core` discovery verbs and grep carry the same sequence.

---
name: vaultspec-dry-run-discipline.builtin
trigger: always_on
---

# Dry-run discipline: preview destructive verbs before applying

A worked example of codification. Promoted from the rolling CLI UX audit's findings S4,
S14, and the gating dimension of B9.

## Rule

Before invoking any vaultspec CLI verb that writes or removes state, run the same verb
with `--dry-run` first, read the previewed change list carefully, and apply the real run
only after the preview matches your intent. `--dry-run` is the canonical preview path on
every destructive verb.

## Why

The rolling CLI UX audit's findings S4, S14, and B9 documented asymmetric gating of
destructive verbs: some lacked a preview entirely, and others previewed nothing. Those
gaps have closed: `install`, `uninstall`, `sync`,
`vaultspec-core vault feature archive`, and every plan mutator accept `--dry-run`, and
`vaultspec-core install --upgrade --dry-run` prints a populated per-file preview
(re-verified against the live CLI on 2026-06-10, `vaultspec-core --version` 0.1.26). The
discipline survives the fix: a preview only protects the operator who reads it.

## How

- **Good:** `vaultspec-core install --dry-run` against an empty directory, read the file
  list, confirm provider selection, then run `vaultspec-core install`.

- **Good:**
  `vaultspec-core vault add plan --feature my-feature --title "..." --tier L1 --related <stem> --dry-run`
  to preview the scaffolded path, frontmatter, and tier value before the file is
  created.

- **Bad:** `vaultspec-core install` in a busy repository without a preview. About
  seventy files appear, `.gitignore` is rewritten, `CLAUDE.md` is created; the cleanup
  is manual.

- If a preview is empty on a verb that should produce side effects, escalate: an empty
  preview is a finding worth logging, not a green light.

## Status

Active. The universal preview discipline this rule anticipated
(`cli-blast-radius-gating` `W04.P11`) has landed: `--dry-run` is the canonical preview
path on every destructive verb. The rule's intent (preview before apply) is now
structurally supported; the operator's remaining duty is to read the preview before
applying.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), findings S4 (round 1), S14
(round 3a), and the gating dimension of B9 (round 3b). Sibling decision ADR
`2026-05-17-cli-blast-radius-gating-adr`. Umbrella plan steps `W04.P11.S39`, `S40`,
`S41`, `S42` in `2026-05-17-cli-simplification-ux-plan`.

---
name: vaultspec-plan-editing-discipline.builtin
trigger: always_on
---

# Plan editing discipline: structure first, prose last

A worked example of codification applied to an audit finding. Promoted from the rolling
CLI UX audit (finding B6) following the discipline described in the `vaultspec-codify`
rule.

## Rule

Treat the plan as one cohesive document: route every Wave, Phase, and Step structural
mutation through the `vaultspec-core vault plan {wave,phase,step}` CLI verbs, and author
the Description, Parallelization, and Verification prose sections by direct file edit.
Prose and structure may interleave freely: the serializer preserves authored prose
blocks verbatim across structural mutations.

## Why

The rolling CLI UX audit's B6 finding documented that plan structural verbs once
silently discarded author-written prose sections, forcing a structure-first, prose-last
ordering. The fix proposed in the sibling ADR `cli-plan-body-preservation` has landed:
every structural mutation now reports "Preserved N unknown blocks", and a live
confirmation against a prose-bearing scratch plan (sentinel sentences carried through
`phase add`, `step add`, and `step check`) showed every authored sentence surviving
byte-for-byte (verified against the live CLI on 2026-06-10, `vaultspec-core --version`
0.1.26).

## How

- Prose content is preserved verbatim; prose position may reflow, because the serializer
  re-anchors blocks around the canonical structure on write. Review the diff after a
  structural verb when section ordering matters.
- Every plan mutator accepts `--dry-run` to preview the rewritten document without
  writing it.
- `--canonicalise` is the explicit opt-in that strips unknown prose blocks; never pass
  it on a plan whose prose you mean to keep.

## Status

Active. The serializer fix this rule anticipated (`cli-plan-body-preservation`
`W03.P07`) has landed and was live-confirmed on 2026-06-10: the ordering constraint is
retired, and preservation is the default with stripping behind the `--canonicalise`
opt-in. The rule's intent (treat the plan as one cohesive document; mutate structure
only through the CLI verbs) survives the fix; only the procedure changed.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), finding B6 sharp (three
reproductions). Sibling decision ADR `2026-05-17-cli-plan-body-preservation-adr`.
Umbrella plan steps `W03.P07.S23`, `S24`, `S25`, `S26` in
`2026-05-17-cli-simplification-ux-plan`.

---
name: vaultspec-rag.builtin
trigger: always_on
---

# vaultspec-rag — semantic search for code and decisions

Discover by MEANING when you do not know the exact name, instead of grepping keywords or
guessing identifiers. vaultspec-rag does two jobs: find the CODE, and find the DECISIONS -
the ADRs (architecture decision records) that govern it.

Server mode is the default backend. If a search reports the service is down, start it with
`uvx vaultspec-rag server start` (small or offline projects opt into the on-disk local
backend with `--local-only`). The running service auto-reindexes on file changes.
DO NOT manually reindex during normal work.

## Discover code by meaning

`--type code` searches source by meaning. Phrase the query as a short behaviour plus the
concrete domain nouns the target code would use: the behaviour drives semantic matching, the
nouns drive exact matching, so a bare keyword or pure prose finds less than both together.

```
uvx vaultspec-rag search "retry backoff around failed webhook delivery" --type code
```

## Discover architecture decisions

When you need the WHY - the rationale, constraints, or decision behind code - search the
vault's ADRs, not the source. `--type vault --doc-type adr` returns the governing records.

```
uvx vaultspec-rag search "decision on gpu lock scope around the forward pass" --type vault --doc-type adr
```

`--doc-type` also accepts `audit`, `plan`, `reference`, `research`, and `exec` (comma-separate
to union several).

## Cut noise with filters

Semantic search competes production code against its own noise - overlapping tests, parallel
locale files, generated and vendored trees, worktree clones. Code search is production-biased
by default: it hides duplicate/derivative domains (`generated`, `worktree`) and demotes
`tests`, `docs`, `locale`, and `vendored` beneath production. When noise still crowds a page,
narrow by DOMAIN rather than raising `--max-results`. The domains are `prod`, `tests`, `docs`,
`locale`, `generated`, `vendored`, `worktree`.

Steer with inline query tokens (comma-separated, repeatable):

```
uvx vaultspec-rag search "fixture setup helpers exclude:tests" --type code
uvx vaultspec-rag search "auth token validation only:prod" --type code
uvx vaultspec-rag search "translation table lookup include:locale" --type code
```

`exclude:` hides a domain, `only:` keeps just the named domains, and `include:` re-admits a
domain the default profile hides or demotes. Compose with path and category filters:

```
uvx vaultspec-rag search "request handler" --type code --include-path "src/**" --exclude-path "**/legacy/**"
uvx vaultspec-rag search "encode batch" --type code --prefer production
```

The full option set is `uvx vaultspec-rag search --help`. The same search is available through
MCP as the `search_codebase` and `search_vault` tools.

---
name: vaultspec.builtin
trigger: always_on
---

# Spec Skills

This project follows a spec driven development framework and mandates a vaultspec
pipeline of: research -> decision (ADR) -> plan -> verify (+ audit either as closeout or
pipeline start).

The workflow persists the following documents, bound by a single feature tag:

- `.vault/research/yyyy-mm-dd-<feature>-research.md`: The `<Research>` findings.

- `.vault/reference/yyyy-mm-dd-<feature>-reference.md`: A project, code, or research
  grounding `<Reference>`, useful for grounding implementation details prior to ADR
  authoring.

- `.vault/adr/yyyy-mm-dd-<feature>-adr.md`: Research-derived `<ADR>`.

- `.vault/plan/yyyy-mm-dd-<feature>-plan.md`: The `<Plan>` to execute, authored and
  managed through the plan verbs - the `plan_progress` and `plan_edit` MCP tools where
  connected, the `vaultspec-core vault plan` CLI otherwise.

- `.vault/exec/yyyy-mm-dd-<feature>/.../<step>.md`: The individual `<Step Record>`.

- `.vault/exec/yyyy-mm-dd-<feature>/...-summary.md`: The `<Phase Summary>`.

- `.vault/audit/yyyy-mm-dd-<feature>-audit.md`: The `<Audit>` report. A feature with
  multiple ADRs, audits, references, or research documents disambiguates each with an
  optional topic infix - `yyyy-mm-dd-<feature>-<topic>-<type>.md` - scaffolded through
  the owning verb's `--topic` flag (`vaultspec-core vault add` for adr, audit,
  reference, and research only), never by hand-picking a filename.

- `.vault/index/<feature>.index.md`: The auto-generated `<Feature Index>` linking every
  document for a feature. The index regenerates as a side effect of the `create` and
  `edit` tools; regenerate it manually with `vaultspec-core vault feature index` when
  working through the CLI, and never author it by hand.

Use the following pipeline skills:

- `vaultspec-research`
- `vaultspec-code-research`
- `vaultspec-adr`
- `vaultspec-write`
- `vaultspec-execute`
- `vaultspec-code-review`

The following helper skills are available:

- `vaultspec-curate`
- `vaultspec-documentation`
- `vaultspec-team`
- `vaultspec-projectmanager`

## Documentation Hierarchy

The documentation trail follows a strict dependency graph. Artifacts lower in the
hierarchy should reference those above them. Source code sits outside this hierarchy
entirely: vault documents cite code by `path:line` locator, and tracked source-file
content never references `.vault/` documents, identifiers, or harness contents (opt-in
git commit trailers are the sanctioned linkage channel).

- **Brainstorm** / **Research** / **Reference** (`.vault/research/`,
  `.vault/reference/`)

- **Audits** (`.vault/audit/yyyy-mm-dd-{feature}-audit.md`, optionally
  `.vault/audit/yyyy-mm-dd-{feature}-{topic}-audit.md`)

  - *Depends on:* the artifacts under review (plans, execution records, code)
  - *References:* the artifacts under review

- **Architecture Decision Records (ADR)** (`.vault/adr/`)

  - *Depends on:* brainstorm, research, audits

- **Implementation Plans** (`.vault/plan/`)

  - *Depends on:* ADRs, research, audits, (previous or related feature plans)
  - *Cardinality:* one plan executes one ADR or a cluster of ADRs (the epic roll-up);
    every governing ADR is listed in `related:`. One ADR is never spread across several
    concurrent plans.

- **Execution Records**
  (`.vault/exec/{yyyy-mm-dd-feature}/{yyyy-mm-dd-feature-{phase}-{step}}.md`)

  - *Depends on:* Plans.
  - *References:* The Plan being executed.
  - *Content:* A mechanical log, not a narrative. One `A`/`M`/`D`/`R` line per path
    touched under `## Changes`, plus the machine-filled `## Scope`. No prose: the Step
    row states the intent and the commit carries the diff. A `## Notes` section is added
    only on exception (data loss, skipped work, a scaffold left in code, a persistent
    failure) and is otherwise omitted.
  - *Location:* Inside feature-specific folder.
  - *Filename:* `{yyyy-mm-dd-feature-{phase}-{step}}.md` where `{phase}` and `{step}`
    are the canonical container identifiers (`P##`, `S##`) from the plan, zero-padded to
    a minimum of two digits. At `L1` the `{phase}` segment is omitted; at `L3`/`L4` a
    `{wave}` segment (`W##`) is prepended.
  - *Examples:*
    - L1: `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-S01.md`
    - L2: `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-P01-S01.md`
    - L3 / L4:
      `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-W01-P01-S01.md`

- **Summaries**
  (`.vault/exec/{yyyy-mm-dd-feature}/{yyyy-mm-dd-feature-{phase}-summary}.md`)

  - *Depends on:* Execution Records.
  - *References:* The Plan and key Artifacts produced.
  - *Content:* The deduplicated union of the Phase's Step Record `## Changes` lines, in
    the same mechanical grammar. Not a retelling of the Step Records.
  - *Location:* Inside feature-specific folder.
  - *Filename:* `{yyyy-mm-dd-feature-{phase}-summary}.md` where `{phase}` is the
    canonical Phase identifier (`P##`).
  - *Examples:*
    - L2: `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-P01-summary.md`
    - L3 / L4:
      `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-W01-P01-summary.md`

- **Feature Indexes** (`.vault/index/{feature}.index.md`)

  - *Auto-generated* as a side effect of the `create` and `edit` tools; regenerate
    manually with `vaultspec-core vault feature index` when working through the CLI,
    never authored by hand.
  - *Filename:* `{feature}.index.md` (no date prefix).
  - *Example:* `.vault/index/editor-demo.index.md`

## Must follow

- We **ALWAYS** use **Obsidian-style Wiki Links** for internal documentation.

- **Always** populate the `related:` field in the YAML frontmatter with
  `'[[wiki-links]]'` (quoted as strings).

- **Never** use relative paths (`../`) in wiki links; assume a flat namespace or
  vault-root resolution.

- **Always** check if a referenced file exists before linking (if possible).

- **Always** include the relevant `#{feature}` tag in the YAML frontmatter using the
  `tags:` field.

- **Always** use the `tags:` field (not `feature:`) as a YAML list.

- **Always** quote wiki-links in YAML: `- '[[file-name]]'`.

## Tag Taxonomy

**ALLOWED TAGS - DO NOT REMOVE - REFERENCE:** `#adr` `#audit` `#exec` `#index` `#plan`
`#reference` `#research` `#{feature}`

Every document in `.vault/` MUST include the required tag pair in the frontmatter
`tags:` field:

- **Directory Tag**: Based on the `.vault/` subfolder location (`#adr`, `#audit`,
  `#exec`, `#index`, `#plan`, `#reference`, `#research`)

- **Feature Tag**: Groups related documents across the feature lifecycle (kebab-case,
  e.g., `#editor-demo`)

**CRITICAL:** No structural tags like `#step`, `#summary`, `#phase*`, or `#design` are
allowed. Every document carries exactly one directory tag plus exactly one `#{feature}`
tag - no more, no less. Any additional tag is read as a second feature tag and fails
validation.

### Directory Tags (Required for ALL documents)

The directory tag is determined by the file's location in `.vault/`:

| Directory           | Tag          | Description                              |
| :------------------ | :----------- | :--------------------------------------- |
| `.vault/adr/`       | `#adr`       | Architecture Decision Records            |
| `.vault/audit/`     | `#audit`     | Audit reports and assessments            |
| `.vault/exec/`      | `#exec`      | Execution records (steps & summaries)    |
| `.vault/index/`     | `#index`     | Auto-generated feature indexes           |
| `.vault/plan/`      | `#plan`      | Implementation plans                     |
| `.vault/reference/` | `#reference` | Implementation references and blueprints |
| `.vault/research/`  | `#research`  | Research and brainstorming               |

### Tag Format

All documents use YAML list syntax with exactly 2 tags (one directory tag, one feature
tag):

```yaml
---
tags:
  - '#plan'
  - '#feature-name'
date: '2026-02-06'
modified: '2026-02-06'
body_hash: 'sha256:...'
related:
  - '[[related-file]]'
---
```

`modified:` is a CLI-maintained last-modified stamp: set equal to `date:` at scaffold,
refreshed by every mutating verb and by `vaultspec-core vault check all --fix`, parsed
leniently but rewritten to the canonical quoted `yyyy-mm-dd` form, never hand-edited.

`body_hash:` is the machine-filled fingerprint of the document body that `modified:`
attests, written beside the stamp by the same verbs. It is what makes an unstamped body
edit detectable: the reconciliation check compares the live body against this value, and
file timestamps are never consulted. Never hand-write or hand-edit it - a value the
author did not compute is the only way the field can lie. A document that carries no
`body_hash:` simply makes no claim about its body and is reported clean until a verb or
migration seeds it.

**Examples:**

- Plan file: `tags: ['#plan', '#editor-demo']`
- ADR file: `tags: ['#adr', '#editor-demo']`
- Exec step: `tags: ['#exec', '#editor-demo']`
- Exec summary: `tags: ['#exec', '#editor-demo']`
- Research: `tags: ['#research', '#text-layout']`
- Reference: `tags: ['#reference', '#text-layout']`
- Feature index (auto-generated): `tags: ['#index', '#editor-demo']`

### Feature Tags

Feature tags use kebab-case and group all documents related to a specific feature or
work stream:

- Format: `#{feature}` (e.g., `#live-preview-blocks`, `#grid-layout`,
  `#syntax-highlighting`)

- Must be consistent across all documents in the feature's lifecycle

- Always quoted in YAML

## Placeholder Naming Conventions

Templates use curly-brace placeholders `{...}` to indicate values that must be replaced.
Follow these conventions:

### Frontmatter Placeholders

| Placeholder      | Format                | Example                   |
| :--------------- | :-------------------- | :------------------------ |
| `{feature}`      | lowercase, kebab-case | `editor-demo`             |
| `{yyyy-mm-dd}`   | lowercase, ISO 8601   | `2026-02-06`              |
| `{yyyy-mm-dd-*}` | lowercase pattern     | `2026-02-04-feature-plan` |
| `{tier}`         | uppercase enum        | `L1`, `L2`, `L3`, `L4`    |
| `modified`       | CLI-maintained stamp  | `2026-02-06`              |

### Document Body Placeholders

Container identifiers (`{wave}`, `{phase}`, `{step}`) use the canonical uppercase
zero-padded form from the plan template hint blocks. `{feature}` uses lowercase
kebab-case. Narrative placeholders (`{topic}`, `{title}`) use concise prose.

| Placeholder | Format              | Example                   |
| :---------- | :------------------ | :------------------------ |
| `{feature}` | kebab-case          | `editor-demo`             |
| `{wave}`    | uppercase canonical | `W01`, `W02`              |
| `{phase}`   | uppercase canonical | `P01`, `P02`              |
| `{step}`    | uppercase canonical | `S01`, `S02`              |
| `{topic}`   | concise prose       | `event handling`          |
| `{title}`   | concise prose       | `display map integration` |

### Machine-Filled Placeholders

A separate placeholder class is filled by the CLI, never by the author. Machine-filled
placeholders use snake_case to distinguish them from author-replaced placeholders; do
not fill or rename them by hand - scaffold the document through the owning CLI verb
instead.

| Placeholder       | Filled by                            | Value                                           |
| :---------------- | :----------------------------------- | :---------------------------------------------- |
| `{heading}`       | `vaultspec-core vault add exec`      | The originating Step row's action text          |
| `{step_id}`       | `vaultspec-core vault add exec`      | The Step's canonical identifier (`S##`)         |
| `{plan_stem}`     | `vaultspec-core vault add exec`      | The parent plan's filename stem                 |
| `{scope_block}`   | `vaultspec-core vault add exec`      | A Scope section listing the Step's scoped files |
| `{document_list}` | `vaultspec-core vault feature index` | The feature's full document list                |

The frontmatter fields `modified:` and `body_hash:` belong to the same machine-filled
class but carry no template placeholder: their values are derived at write time - from
the clock and from the rendered body - so they are injected by the owning verb rather
than substituted into a template token.

### General Rules

- **YAML frontmatter**: Always lowercase, kebab-case

- **Document titles/headings**: The shipped templates are canonical for level-one
  headings. Top-level vault documents use backticks around both the `{feature}` segment
  and the narrative `{title}`, `{topic}`, or `{phase}` segment. Examples:
  `# {feature} research: {topic}` represents the literal template heading '# `{feature}`
  research: `{topic}`', and `# {feature} plan` represents '# `{feature}` plan'.
  Narrative segments should be concise prose; canonical uppercase identifiers remain
  required for `{wave}`, `{phase}`, and `{step}` identifier segments.

- **File names**: lowercase kebab-case for narrative segments (`{feature}`, `{type}`);
  canonical uppercase identifiers for `{wave}`, `{phase}`, `{step}` segments. Patterns:

  - Top-level docs: `yyyy-mm-dd-{feature}-{type}.md` (e.g.,
    `2026-02-04-editor-demo-plan.md`)

  - Optional topic infix (adr, audit, reference, research only):
    `yyyy-mm-dd-{feature}-{topic}-{type}.md` (e.g.,
    `2026-02-04-editor-demo-engine-wire-reference.md`), scaffolded with the owning
    verb's `--topic` flag

  - Exec Steps (L1): `yyyy-mm-dd-{feature}-{step}.md` (e.g.,
    `2026-02-04-editor-demo-S01.md`)

  - Exec Steps (L2): `yyyy-mm-dd-{feature}-{phase}-{step}.md` (e.g.,
    `2026-02-04-editor-demo-P01-S01.md`)

  - Exec Steps (L3 / L4): `yyyy-mm-dd-{feature}-{wave}-{phase}-{step}.md` (e.g.,
    `2026-02-04-editor-demo-W01-P01-S01.md`) inside `.vault/exec/yyyy-mm-dd-{feature}/`
    folder.

  - Exec Summaries (L2): `yyyy-mm-dd-{feature}-{phase}-summary.md` (e.g.,
    `2026-02-04-editor-demo-P01-summary.md`)

  - Exec Summaries (L3 / L4): `yyyy-mm-dd-{feature}-{wave}-{phase}-summary.md` (e.g.,
    `2026-02-04-editor-demo-W01-P01-summary.md`) inside the feature folder.

- **Replace ALL placeholders**: No template should be committed with `{...}`
  placeholders remaining. Run `vaultspec-core vault check all --fix` to validate and
  format documents before committing - it reconciles frontmatter, strips leftover
  template annotations, and applies markdown hygiene fixes. The dedicated
  `vaultspec-core vault check placeholders` check surfaces any `{...}` residue left in
  body prose, which must be filled in by hand or by the owning CLI verb.
</vaultspec>
