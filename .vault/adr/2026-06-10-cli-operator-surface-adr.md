---
tags:
  - '#adr'
  - '#cli-operator-surface'
date: '2026-06-10'
related:
  - '[[2026-06-10-cli-operator-surface-research]]'
  - '[[2026-06-10-cli-operator-surface-audit]]'
  - '[[2026-06-10-cli-operator-crud-matrix-audit]]'
  - '[[2026-06-10-aeat-cli-userdocs-hardening-audit]]'
  - '[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]'
  - '[[2026-05-14-ledger-transaction-lifecycle-adr]]'
  - '[[2026-06-02-ledger-operator-hardening-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-01-registry-period-code-union-cli-boundary-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-profile-output-language-adr]]'
  - '[[2026-06-03-modelo-036-census-sync-adr]]'
---

# `cli-operator-surface` adr: `operator surface verb, lifecycle, and honesty decisions` | (**status:** `proposed` -- operator approval pending)

## Problem Statement

The `aeat-cli-userdocs-hardening` campaign wrote operator how-to guides against
the live CLI and, in doing so, surfaced a class of defect documentation could
only describe, never repair: the operator surface itself is misshapen. The
sibling audits `2026-06-10-cli-operator-surface-audit` (findings F1-F8) and
`2026-06-10-cli-operator-crud-matrix-audit` (CRUD matrix, five journey verdicts,
one new gestor-bulk gap) catalogue eight surface-design weaknesses plus one
capability-coverage gap, each re-verified against `HEAD` and reconciled against
the prior decision that created it.

This ADR makes one coordinated set of decisions over those findings. It is a
reconciliation ADR: where a prior accepted decision named a behaviour that was
never built (the ledger-lifecycle "reversible" promise) or scoped a principle
narrowly (the modelo-addressing "operators never handle content IDs" rule), this
ADR amends or extends that prior decision rather than re-litigating it; where no
ADR ever governed the surface (the ledger period grammar, the self-referential
hint strings, the eager language flag timing contract, the preflight signature),
the decision here is net-new. Every claim of current behaviour below traces to
the audits or to code verified during authoring; no CLI behaviour is invented.
The never-live-submission gate is untouched by every decision here.

## Considerations

- The audits are written decision-shaped and pre-reconciled, so each decision can
  amend a named prior decision rather than re-deriving the problem.
- The Spanish-stem naming discipline governs AEAT domain concepts. The lifecycle
  verbs decided here (`restore`, `switch`) are generic computing vocabulary with
  no AEAT counterpart and fall under that rule's explicit English-stays-English
  exception; they are not AEAT surfaces.
- The ledger lifecycle already carries a generic state-transition primitive
  (`_transition_manual_transaction_lifecycle` in
  `src/aeat/application/ledger/_actions_lifecycle.py`) that can target any state.
  No `ACTIVE`-targeting public action or CLI verb calls it; the inverse the prior
  ADR promised is one caller away, not a new subsystem.
- The modelo-addressing-ux ADR already solved the content-addressed-id-churn shape
  for modelo work units. F3 and F8 are the same shape on two surfaces (ledger
  rows, the preflight readiness question) the principle never reached.
- The project already ships a `test_documented_command_conformance.py` gate that
  pins documentation commands against the live tree. That gate is the template for
  the F5 self-referential-string conformance gate; the mechanism exists.
- The CRUD audit rates the ledger set-aside reversal (F2 / F-01) the single
  highest-leverage gap: an accidental bulk stash currently recovers only through
  `ledger reset` -- clearing and re-importing the whole ledger.

## Constraints

- This ADR decides surface shape and reconciles prior decisions; it is not an
  implementation plan. Sequencing, locale-key population, and per-verb test wiring
  belong to the follow-on plan.
- `restore` must honour the same finalized-modelo guard, `--yes`, `--reason`, and
  audit-event guarantees the forward `archive` / `stash` verbs carry per
  `2026-06-02-ledger-operator-hardening-adr`; an inverse weaker than its forward
  is not acceptable.
- Read-back surfaces (F7) must not re-implement an existing single-writer
  primitive; a list / view verb reads through the owning repository, it does not
  open a parallel read path.
- The period-grammar decision (D4) must not break the registry-period union
  authority's `EVENT-N` regex member; whatever the ledger surface adopts must pass
  the registry period validator for the codes it accepts.
- Parent features are stable: the ledger transaction lifecycle, the modelo
  addressing resolver, the registry-period union type, the profile-owned output
  language, and the M036 declaration service are all accepted and shipped; this
  ADR extends their operator surface, it does not rebuild their backends.

## Implementation

Each decision below names its finding, states the decision imperatively, quotes
the prior text it amends or upholds, then gives consequences and rejected
alternatives.

### D1 -- Restore an intent-named profile-switch verb (F1)

**Context.** The human action "change to another taxpayer profile" has no human
verb. `aeat config profile switch` and `aeat config profile use` are retired
(`_RETIRED_VERBS` at
`src/aeat/entrypoints/cli/tests/test_config_profile_surface_inventory.py`); the
surviving door is `aeat config unlock NAME`, registered in
`src/aeat/entrypoints/cli/_config/_custody.py`, which names the storage-layer act
of unsealing an encrypted bucket session, not the operator's intent. The userdocs
campaign was forced to write "switch by unlocking" -- a gloss that exists only
because the verb and the intent diverged.

**Decision.** Restore `switch` as the operator-facing verb for changing the
active taxpayer, layered over the existing session-unlock implementation:
`aeat config switch NAME` (at the `config` surface the current `unlock` occupies)
becomes the operator door, and the existing unlock code path runs underneath it
unchanged. Keep `unlock` as a documented lower-level synonym for operators who
think in session terms; do not remove it. Adopt the standing policy: an operator
verb names the operator's intent, not the storage or session mechanism that
implements it. Enumerate the rename / alias set this policy implies today without
boiling the ocean -- restore `switch` (D1's subject), and queue intent-named
spellings for the two other leaked terms the audit named: `config repair
reset-state` (storage mechanic) and the operator-facing noun "bucket" where the
operator means "profile". Treat those two as follow-on rename work tracked by the
plan, not decided in detail here.

**Amends.** `2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr`
decided the switch verb was `use` as an alias of `set active` and forbade a
root-level shortcut: "The HARD RULE forbids a root-level `aeat switch` or `aeat
use` shortcut. The convenience must live under `config profile`." That ADR is
superseded by the profile-lifecycle authority and its `use` verb was itself
retired; this ADR does not reinstate a root-level `aeat switch` (the
two-root-command constraint stands) but reinstates `switch` as the intent-named
verb under the config / profile surface, over session-unlock semantics the prior
ADR never anticipated. Per F1 the prior ADR "reasoned about `use` versus `set
active`; it did not decide that storage-unlock vocabulary would become the
operator's only door."

**Consequences.** The "switch by unlocking" gloss disappears. Operators get a
verb whose name survives the encrypted-session model underneath it. `unlock`
survives for continuity and for the genuine session-only case (unsealing without
intending a context switch). The policy seeds a codification candidate.

**Rejected.** Renaming `unlock` outright to `switch` (drops the legitimate
session-only meaning and breaks every guide that already teaches `unlock`).
Leaving `unlock` as the only door (keeps the gloss the documentation could not
remove). A root-level `aeat switch` shortcut (violates the standing two-root
constraint `config` plus `app`).

### D2 -- Build a ledger `restore` verb to ACTIVE (F2 / CRUD F-01)

**Context.** A ledger row stashed or archived by mistake cannot be brought back.
`_transition_manual_transaction_lifecycle` exists and is state-generic, but the
only public actions are `archive_manual_transaction`, `stash_manual_transaction`,
and `remove_manual_transaction` (no `ACTIVE`-targeting public action), and the
ledger CLI exposes no inverse verb. `update` additionally refuses any non-active
row. The CRUD audit's journey (e) rates this the product's weakest recovery: an
accidental bulk stash recovers only through `ledger reset` -- nuke and re-import
the whole ledger.

**Decision.** Honour the lifecycle ADR's reversibility promise. Add a public
restore-to-`ACTIVE` lifecycle transition and an `aeat app ledger restore --id ID`
verb (accepting the `_resolve_id` prefix form like every other id-consuming verb)
that moves `STASHED -> ACTIVE` and `ARCHIVED -> ACTIVE`, emits its own audit
event, and honours the finalized-modelo guard. The verb carries the same Tier-1
UX as its forward counterparts: `--yes` and `--reason` recorded into the event
payload. `restore` is generic computing vocabulary (English correct per the
Spanish-stem exception). Split rows stay out of scope: `SPLIT` / `MERGED` lineage
transitions remain exclusive to `split` / `merge` as today.

**Amends and upholds.** `2026-05-14-ledger-transaction-lifecycle-adr` Decision 4
classifies `archive` and `stash` as "Tier 1 -- reversible state transitions" and
Decision 2 names the inverse explicitly: archive's "Reversibility: inverse is
`activate` via `_transition_manual_transaction_lifecycle`" and stash "As archive,
but ACTIVE to STASHED". This decision upholds that classification and honours the
named-but-unbuilt inverse rather than superseding the reversibility promise -- the
audit's two options were "make the claim true, or rename the verbs", and this
chooses the former. It amends the prior ADR only by spelling the operator verb
`restore` (the audit's and CRUD audit's spelling) rather than `activate` (the
prior ADR's internal-primitive name), so the operator surface reads as a clean
inverse of `archive` / `stash`. It coordinates with
`2026-06-02-ledger-operator-hardening-adr` by carrying the same `--yes` /
`--reason` / audit guarantees that ADR added to the forward verbs.

**Consequences.** The single highest-leverage usability gap closes: a routine
operator slip stops being a whole-ledger reset. The `correct-ledger-entries.md`
honest-permanence sentence ("Both are permanent") becomes the line to update when
the verb lands. `update`'s non-active refusal is unchanged -- the operator
restores first, then edits.

**Rejected.** Formally superseding the reversibility promise and renaming `stash`
/ `archive` to non-reversible verbs (the CRUD audit rates reversal the
highest-leverage fix; renaming away from it abandons the highest-value option and
contradicts the universal `git stash` expectation the verb name sets). A restore
that skips the finalized-modelo guard (would let a row re-enter the active set
behind a sealed calculation).

### D3 -- Stable operator lineage handle for ledger rows across edits (F3)

**Context.** Correcting a field on a transaction changes its id: the
transaction-id derivation in `src/aeat/domain/transactions/_models.py` keys on the
provider identifier and verbatim narrative and "therefore changes when a
transaction is edited". An operator who recorded `history <old-id>`, then fixed a
typo, finds the old handle dead -- the correction the CLI invited destroyed the
handle the CLI taught.

**Decision.** Extend the modelo-addressing-ux principle to ledger rows: the
content-addressed `transaction_id` stays authoritative for storage and audit, but
the operator-facing handle must survive an edit. Adopt the redirect-and-resolve
shape: `aeat app ledger history` (and `view` / `track`) MUST resolve any id in a
row's edit-lineage chain -- the `TransactionEditLineageEntry` chain the lifecycle
ADR's `edit` semantics already records -- to the current row, so an old id keeps
answering after a correction. Where a stable display alias is cheaper than chain
resolution, an alias carried through correction is an acceptable equivalent; the
binding requirement is that the operator handle does not die on edit, not the
specific mechanism. Do not require operators to learn the content-address churn.

**Extends.** `2026-06-04-modelo-addressing-ux-adr` decided for modelo work that
"Internal content-addressed IDs must remain authoritative for storage, audit,
replay, and machine consumers. This ADR demotes raw IDs from the ordinary CLI
path; it does not remove them." Per F3 that ADR "scoped itself to modelo work and
left ledger row identity content-addressed and operator-facing." This decision
extends the decided principle to the ledger transaction surface by
omission-repair; it does not invent a new principle.

**Consequences.** The quarter-end journey's sharp edge (journey (a): a late
`ledger update` invalidates a written-down id) is smoothed: the old id keeps
resolving. The edit-lineage chain the lifecycle ADR already persists becomes the
resolution substrate, so no new storage is required.

**Rejected.** Freezing the `transaction_id` across edits (breaks the
content-addressing invariant the lifecycle ADR's Decision 8 protects and that
import dedup relies on). Doing nothing and documenting the churn (the userdocs
campaign already did, and the CRUD audit records the friction as a live product
stumble, not an acceptable limitation).

### D4 -- One operator period grammar, AEAT tokens canonical (F4)

**Context.** The same operator learns two period vocabularies. Modelo surfaces
accept `0A / 1T-4T / 01-12`; ledger surfaces accept `2026Q1 / 2026-03 / 2026` via
`_PERIOD_RE` / `_canonical_period` in `src/aeat/entrypoints/cli/_common.py`. A
quarter is `1T` in one place and `2026Q1` in another, with no conversion and no
cross-acceptance. The ledger grammar predates and has no governing ADR.

**Decision.** Make the AEAT modelo token grammar the canonical operator-facing
period vocabulary across both surfaces, and give the ledger calendar grammar its
missing governing decision by ruling it a non-canonical input the ledger surface
also accepts and converts internally. Concretely: the AEAT tokens (`1T-4T / 0A /
01-12`, plus the registry union's extended members where a modelo needs them) are
the documented, taught, canonical form everywhere; ledger `--period` sites
continue to accept their `2026Q1 / 2026-03 / 2026` calendar shapes as an alternate
input but normalise to the canonical representation each store needs, and ledger
`--help` leads with the AEAT tokens. Operators are taught one grammar; the ledger
surface converts the second for backward compatibility rather than forcing a
flag-day break. The canonical grammar's authority remains
`2026-06-01-registry-period-code-union-cli-boundary-adr`.

**Upholds and reconciles.**
`2026-06-01-registry-period-code-union-cli-boundary-adr` decided the AEAT-shaped
grammar deliberately: per F4 it is "the incumbent authority for the AEAT shape",
and its accepted Candidate 3 routes `--period` through the registry validator with
the accepted set in `--help` and on parse failure. This decision upholds that ADR
as the canonical authority and reconciles the unreconciled ledger `2026Q1`
grammar -- which per F4 "predates it and was decided implicitly in the ledger CLI
common module with no governing ADR" -- by demoting it to an accepted-but-converted
alternate input, supplying the governing decision the second grammar never had.

**Consequences.** The guides teach one period grammar. The ledger calendar shapes
keep working (no flag-day break for existing scripts and muscle memory), but they
stop being a second thing the operator must learn. The conversion layer becomes a
maintained surface: ledger `--period` parsing must map AEAT tokens to its internal
calendar representation and vice versa, validated against the registry union for
the codes it advertises.

**Rejected.** Adopting the ledger calendar grammar as canonical everywhere (would
re-decide the registry-period ADR's deliberate AEAT-shaped choice and lose the
per-modelo registry-union members). Pure bidirectional acceptance with no canonical
preference (leaves the docs teaching both and gives the operator no single mental
model). A hard flag-day rename of ledger sites (breaks existing scripts for no
safety gain).

### D5 -- Conformance gate for self-referential CLI strings (F5)

**Context.** Hand-maintained CLI strings repeatedly disagree with the CLI they
describe -- five distinct instances in one campaign (a hint to a non-existent
`verification-report list` command; an evidence-id help promising "unambiguous
prefix" while the lookup matches by exact equality; a `doclink --source` option
typed as the full five-member `AttachmentSource` enum while the handler accepts
only three; a `work verify --select latest-verified` advertised though verify
refuses any state but `BORRADOR`; a "profile registry" string for a
calculation-registry probe). The pattern is structural: the strings describe the
CLI by hand instead of being derived from it.

**Decision.** Add a test-time conformance gate, owned by the CLI entrypoints test
suite and mirroring the existing `test_documented_command_conformance.py`, that
pins two classes of self-referential string against the live tree. First,
next-action and failure-hint strings that name a command path MUST resolve to a
live command (the documented-command gate's mechanism, applied to internal hint
strings). Second, every Typer option typed as an enum whose handler accepts a
narrower set MUST either narrow the advertised choice set to exactly what the
handler accepts, or the handler MUST accept every advertised member -- an
advertised enum choice the handler refuses is a gate failure. Scope is exactly
those two classes (command-naming hint strings; enum-choice-vs-handler-accepted
sets); suggested-command strings inside error messages are in scope as a subset of
the first class. The gate is the fix, not a per-string patch -- the five instances
are symptoms of its absence.

**Net-new (no prior ADR).** Per F5, "No ADR governs next-action hint strings or
the enum-choice-vs-handler contract -- the surface was decided implicitly, hint
string by hint string, with no conformance gate." This decision is net-new; the
documented-command gate is the precedent it generalises.

**Consequences.** Hand-edited drift reds a fast test instead of misleading an
operator. The gate seeds a codification candidate. The `doclink --source` and
`work verify --select` enums must be narrowed (or their handlers widened) to pass
the gate -- a small, bounded surface change the gate will enumerate.

**Rejected.** Patching the five known strings without a gate (the audit's explicit
finding is that this is a structural pattern, not five typos; the next edit
re-introduces drift). A lint-only convention with no executable gate (not
enforceable across sessions).

### D6 -- Make `--language` honest for help text (F6)

**Context.** The root `--language` flag silently fails for help text. `aeat
--language en config profile create --help` renders Spanish; only setting
`AEAT_OUTPUT_LANGUAGE` before the process starts changes help-text language. The
flag is declared `is_eager=True` in `src/aeat/entrypoints/cli/__init__.py`, so it
resolves after the import-time `tr(...)` calls have already rendered every help
string. The environment variable wins because it is read before import.

**Decision.** Make the flag honest. The acceptable outcomes, in preference order:
(1) defer help-text rendering until after eager-option resolution so `--language`
works for help -- preferred if feasible without destabilising the import-time i18n
model; otherwise (2) emit a one-line warning when `--language` is supplied on a
surface it cannot affect, naming `AEAT_OUTPUT_LANGUAGE` as the working
alternative; and as a floor (3) the flag MUST NOT silently fail to do what it
advertises. The plan picks (1) or (2) after a feasibility spike on deferred help
rendering; this ADR forbids the current silent-failure state and binds the
honesty contract, not the implementation mechanism.

**Reconciles (no prior timing decision).**
`2026-05-13-cli-workflow-redesign-profile-output-language-adr` established the
profile-owned output-language precedence -- "1. `AEAT_OUTPUT_LANGUAGE` when
present... 2. Active profile `output.language`... 3. Settings default" -- and
notes "The i18n resolver runs before many command handlers, especially while
rendering help text." Per F6 it established the output-language model but never
decided the help-text rendering timing contract for the eager `--language` flag.
This decision adds the missing honesty contract for the flag without disturbing
that ADR's precedence model: the precedence chain is unchanged; only the eager
flag's silent-failure-on-help behaviour is corrected.

**Consequences.** An operator who discovers `--language` is no longer quietly
betrayed. If outcome (2) ships, the warning teaches the working path
(`AEAT_OUTPUT_LANGUAGE`). The profile-owned precedence and the env override stay
exactly as the output-language ADR decided.

**Rejected.** Removing `--language` from every surface (heavier than necessary;
the flag is honest for non-help output paths). Leaving it silent (violates the
flag-must-not-lie rule the audit names).

### D7 -- Read-back baseline for every record-creating verb (F7 / CRUD)

**Context.** Several record-creating verbs have no read-back. `aeat app modelo
m036` exposes exactly `alta / modificacion / baja`
(`src/aeat/entrypoints/cli/_modelo_m036_cli.py`), and the application layer
exposes only `record_m036_declaration` with no list / view public surface -- the
`list_declarations` verb the census-sync ADR's landing plan named was never built.
After recording an M036 declaration there is no list, view, edit, or delete; the
only confirmation is the command output already scrolled past. The CRUD matrix
names the same shape on reconciliation results (no history list), the IVA wallet
(seed-once, no correction path), and the local filing record (no un-file).

**Decision.** Establish read-back as a baseline guarantee: every operator verb
that persists a record ships with a corresponding list / view surface so the
operator can confirm, review, and find what they recorded. Apply it in priority
order from the audits: first M036 (`m036 list` / `m036 view`, reading through the
already-shipped declaration repository -- no parallel read path); then the plain
tax-year filing-history surface (CRUD F-02, plan step `W05.P09.S52`); then the
reconciliation-history list and the IVA-wallet correction / read path. The
filing-record `unfile` / `reopen` decision is deferred with rationale: un-filing a
locally-recorded filing marker touches the never-live-submission boundary's
honest-record discipline (a filing record asserts a human filed outside the app),
so reopening it needs its own decision about what the reopened state means for
downstream calendar and amendment flows; it is not a simple read-back gap and is
out of scope here.

**Extends (no prior read-back ADR).** `2026-06-03-modelo-036-census-sync-adr`
decided the M036 declaration-recording surface and its landing plan named a
Commit-2 service with "`list_declarations` verbs", but the read-back was never
decided as a guarantee and the list verb never shipped: per F7 "the write path was
specified without its read counterpart. No ADR establishes 'every record-creating
verb has a read-back'." This decision establishes that guarantee and closes the
M036 instance under it.

**Consequences.** The M036 documented dead end closes. The taxpayer's most natural
question ("what did I file, what is still due") gains a single plain surface. The
append-only-and-immutable model for calculation revisions and verification reports
is not a read-back gap (they have `revisions` / `view` / `list` and are correctly
superseded, never deleted) and is explicitly excluded.

**Rejected.** Treating M036 read-back as a one-off backlog item (the audit shows
the write-only shape recurs across four record types; a baseline guarantee
prevents the next recurrence). Bundling `unfile` into this decision (it is a
lifecycle-semantics decision near the safety boundary, not a read-back surface).

### D8 -- `preflight` defaults `--revision-id` to the active revision (F8)

**Context.** "Am I ready to file this?" demands a registry-internal handle. `aeat
config profile preflight` declares `revision_id: str = typer.Option(...)` in
`src/aeat/entrypoints/cli/_config/__init__.py` with no default, so `--revision-id`
is mandatory; answering a readiness question forces the operator to first run
`modelo describe`, read out an internal revision id, and paste it back.

**Decision.** Default `preflight` to the active revision for the given
modelo / year / period, so the readiness question is answerable from the natural
key alone. `--revision-id` remains available as an explicit override for exact
replay. This is the readiness-surface instance of the D3 internal-handle
principle: resolve the operator-facing target (active profile, modelo, filing
year, period) to the current revision through the modelo-addressing resolver, and
only consult the internal revision id when the operator explicitly supplies it.

**Extends.** Shares D3's and `2026-06-04-modelo-addressing-ux-adr`'s root
principle -- internal content-addressed IDs stay authoritative but operators
address by natural key. Per F8 "No ADR decided that readiness must accept a
registry-internal revision id; it is an implicit consequence of the preflight
command signature." This decision applies the addressing-ux resolver to the
readiness surface it never reached.

**Consequences.** The choose-modelo guide's explicit "run `modelo describe` first,
read out the revision id, paste it back" detour disappears. Where the natural key
is ambiguous (multiple active revisions), preflight refuses and lists candidates
per the addressing-ux ambiguity contract rather than guessing.

**Rejected.** Keeping `--revision-id` required (forces an internal handle on a
simple question, the exact friction the addressing-ux ADR removed elsewhere).
Defaulting to "latest" without the resolver's lifecycle-aware selection (the
addressing-ux ADR already rejected a generic latest rule as unsafe).

### Triage of the new gestor cross-profile bulk gap (CRUD F-04)

The CRUD audit's new finding F-04 (no bulk or cross-profile operation for the
gestor persona; every mutating verb is single-active-profile and the only
cross-profile surface is `overview calendar --all-profiles`) is explicitly
deferred to a future feature ADR. Rationale: a gestor-mode decision is a
product-scope question (is batch mutation across client profiles in scope at all,
and how does it interact with per-profile encrypted-bucket isolation) large enough
to warrant its own research and ADR, and folding it into this reconciliation ADR
would bloat it past its verb-and-lifecycle remit.

## Rationale

The eight decisions share one spine: an operator verb, handle, grammar, hint, or
flag must name and serve what the operator intends, and must not silently fail or
silently churn. Five of the eight (D2, D3, D6, D7, D8) honour or extend a
principle a prior accepted ADR already decided but never carried to this surface
-- the cheapest, least-frail kind of decision, because the design was already
adjudicated and only the reach was missing. Two (D1, D4) reconcile a verb or a
grammar that drifted from or never received a governing decision. One (D5)
generalises an existing gate template to a surface that lacked enforcement. The
audits ground every current-behaviour claim in verified code and live `--help`
output, and each decision quotes the prior text it touches so the ADR phase amends
rather than re-litigates.

## Consequences

- The userdocs campaign's three glosses-of-necessity ("switch by unlocking", the
  removed false un-stash claim, the two taught period grammars) become removable:
  D1, D2, and D4 each repair the surface the documentation could only describe.
- The single highest-leverage recovery gap (D2) closes; an accidental bulk stash
  stops being a whole-ledger reset.
- Two new test gates land: D5's self-referential-string conformance gate and the
  roundtrip / anti-tautology coverage D2's restore verb and D7's read-back surfaces
  require per the roundtrip-discipline rule.
- The ledger period surface gains a maintained conversion layer (D4) -- a small
  ongoing cost in exchange for one operator grammar.
- The gestor bulk gap stays open by explicit decision; the product remains "usable
  by a single hands-on taxpayer or a gestor working one client at a time", with
  multi-client batch operation tracked as a separate future ADR.
- Nothing here touches the never-live-submission gate, the Spanish-stem naming of
  AEAT domain concepts (the generic `restore` / `switch` verbs are the rule's
  English exception), or the registry-as-authority flow.

## Codification candidates

- **Rule slug:** `operator-verbs-name-operator-intent`.
  **Rule:** An operator-facing CLI verb must name the operator's intent, not the
  storage or session mechanism that implements it; if a user-facing doc must gloss
  a verb to explain what it does (for example "switch by unlocking"), the verb is
  misnamed and the gloss is the smell. Author after this ADR is accepted so the
  rule body cites the accepted D1 decision.

- **Rule slug:** `cli-hint-and-enum-choices-conformance-gated`.
  **Rule:** Every CLI next-action / failure hint that names a command path, and
  every Typer enum-choice surface whose handler accepts a narrower set, must be
  conformance-gated against the live tree (the hint resolves; the advertised enum
  member is acceptable to its handler) rather than hand-maintained as a describing
  string. Author after the D5 gate lands so the rule cites the shipped gate.

- **Rule slug:** `set-aside-verbs-need-a-reversal-or-documented-permanence`
  (offered by the CRUD audit, not asserted).
  **Rule:** Every CLI verb that sets a record aside or marks a one-way lifecycle
  transition must either ship a paired reversal verb or carry an explicit, tested
  honest-permanence statement in its help text and the owning docs page. Borders
  the existing dry-run-discipline rule; promote only if the team judges it distinct
  after D2 and D7 land.
