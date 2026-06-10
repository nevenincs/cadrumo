---
tags:
  - '#audit'
  - '#cli-operator-surface'
date: '2026-06-10'
related:
  - '[[2026-06-10-aeat-cli-userdocs-hardening-audit]]'
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]'
  - '[[2026-05-14-ledger-transaction-lifecycle-adr]]'
  - '[[2026-06-02-ledger-operator-hardening-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-01-registry-period-code-union-cli-boundary-adr]]'
  - '[[2026-06-04-aeat-cli-userdocs-hardening-adr]]'
  - '[[2026-06-03-modelo-036-census-sync-adr]]'
---

# `cli-operator-surface` audit: `operator surface design weaknesses from the userdocs campaign`

## Scope

The `aeat-cli-userdocs-hardening` campaign (audit
`2026-06-10-aeat-cli-userdocs-hardening-audit`, plan
`2026-06-04-aeat-cli-userdocs-hardening-plan`) wrote operator-facing how-to
guides against the live CLI. The act of teaching the CLI to a newcomer surfaced
a class of defect the campaign could not fix in documentation: the operator
surface itself is misshapen. Where a guide had to gloss a verb, teach a
registry-internal handle, or warn that a documented option does nothing, the
documentation was papering over a CLI design weakness, not a wording gap.

This audit collects the eight such weaknesses surfaced by that campaign,
re-verified against `HEAD`. Each is an operator-surface design decision — a verb
name, a lifecycle shape, an identity handle, a help string, an option contract —
that the documentation phase could only describe, never repair. The audit exists
to feed the verb-and-lifecycle ADR (and its amendments to the prior decisions
named below) plus a rollout plan: the findings are written decision-shaped, each
reconciled against the prior decision that created it, so the ADR phase can
amend rather than re-litigate.

Severity reflects operator-facing harm: HIGH = an operator is misled into a
wrong action or a dead end with no recovery; MEDIUM = an operator is forced to
learn an internal concept or hits an avoidable friction wall; LOW = a simple
question demands a harder answer than it should.

## Findings

### F1 — Operator vocabulary leaks the storage layer (`switch` retired for `unlock`)

**Severity:** HIGH.

**Operator-visible symptom.** The human action "change to another taxpayer
profile" has no human verb. The live CLI returns `No such command 'switch'`; the
surviving path is `aeat config unlock`, which names the storage-layer concept
(unsealing an encrypted bucket session) rather than the operator's intent. The
userdocs campaign was forced to write "switch by unlocking" (commit
`df71ba94a`) — a gloss that exists only because the verb and the intent diverged.
The same family leaks elsewhere: `config repair reset-state`, the noun "bucket"
for what an operator calls a profile, and "work unit" for a filing workspace.

**Code evidence.** `switch`, `use`, `view`, and the `get`/`set`/`unset` triple
are enumerated as retired in `_RETIRED_VERBS` at
`src/aeat/entrypoints/cli/tests/test_config_profile_surface_inventory.py:41-49`;
the live surface confirms `switch` resolves to no command. Session-unlock
semantics live underneath the verb that replaced it.

**Prior-decision reconciliation.**
`2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr` decided the
*switching* verb is `aeat config profile set active NAME`, explicitly rejected a
root-level `aeat switch`/`aeat use` shortcut (its HARD RULE), and chose `use` as
the developer-idiomatic switch verb — but it never anticipated the
session-unlock model collapsing the switch verb into `config unlock`. The ADR
reasoned about `use` versus `set active`; it did not decide that storage-unlock
vocabulary would become the operator's only door. This is the prior decision the
amendment must revise: the switch intent needs a human verb whose name survives
the encrypted-session model underneath it.

**Decision the ADR must make.** Decide whether `switch` (or another
intent-named verb) is restored as the operator-facing door — with
session-unlock semantics living underneath the human verb — or whether `unlock`
is renamed to an intent term. Either way the rule is: the operator's verb names
the operator's intent, not the storage mechanism that implements it.

### F2 — Ledger lifecycle is a one-way trapdoor (no un-stash, no un-archive)

**Severity:** HIGH.

**Operator-visible symptom.** A row stashed or archived by mistake cannot be
brought back. There is no un-stash, no un-archive, and no lifecycle transition
whose target is `ACTIVE`; `update` additionally refuses any non-active row. The
verb "stash" carries a universal promise of reversibility (every developer's
`git stash` restores), and the import guide claimed exactly that until the claim
was disproven and removed (commit `68c1c1cfe`). The operator is left with a
silent dead end: the trapdoor only opens downward.

**Code evidence.** The lifecycle transition in
`src/aeat/application/ledger/_actions_lifecycle.py:402-421` only moves a row
*into* `ARCHIVED`/`STASHED` (it explicitly refuses `archived -> stashed` and
routes `SPLIT` elsewhere); no branch targets `ACTIVE`. Edit is barred for
non-active rows at `src/aeat/application/ledger/_actions_manual.py:449-451`
("only active ledger transactions can be edited; archived, stashed, and
split-parent rows are immutable"). The full `aeat app ledger --help` inventory
carries no restore verb.

**Prior-decision reconciliation.**
`2026-05-14-ledger-transaction-lifecycle-adr` classifies `archive` and `stash`
as "Tier 1 — reversible state transitions" and states "The inverse op is
documented in the verb help text" (Decision 4). The inverse op was never built:
the ADR named the transitions reversible and promised a documented inverse, but
shipped only the forward direction. `2026-06-02-ledger-operator-hardening-adr`
then hardened the *forward* verbs (`--yes`, `--reason`) without supplying the
inverse the lifecycle ADR had promised. The amendment must close the gap between
the lifecycle ADR's "reversible" claim and the shipped one-way reality.

**Decision the ADR must make.** Decide either a restore-to-`ACTIVE` transition
(emitting its own audit event, honouring the finalized-modelo guard) that makes
the Tier 1 "reversible" claim true, or a rename of `stash`/`archive` to verbs
that do not promise restoration. The current state — a verb that promises
reversal and a help text that was supposed to document a non-existent inverse —
is the one outcome the amendment must not leave standing.

### F3 — `update` breaks row identity (content-addressed transaction IDs)

**Severity:** MEDIUM.

**Operator-visible symptom.** Correcting a field on a transaction changes its
ID. An operator who recorded `history <old-id>`, then fixed a typo, finds
`history <old-id>` now fails — the very correction the CLI invited destroyed the
handle the CLI taught. The identity churn is invisible until the operator
reuses the old handle.

**Code evidence.** The transaction-ID derivation in
`src/aeat/domain/transactions/_models.py:96-100` keys on the provider identifier
and verbatim narrative and "therefore changes when a transaction is edited or
re-exported in a different file format." (A separate movement fingerprint exists
for import dedup, but it is not the operator-facing handle.)

**Prior-decision reconciliation.** `2026-06-04-modelo-addressing-ux-adr` already
solved exactly this shape for *modelo work units*: it decided internal
content-addressed IDs "must remain authoritative for storage" but operators must
never have to handle them, exposing stable operator-facing addressing instead.
That principle was never extended to the *ledger transaction* surface — the
addressing-ux ADR scoped itself to modelo work and left ledger row identity
content-addressed and operator-facing. There is therefore a decided principle
the ledger surface violates by omission; the ADR must extend it, not invent it.

**Decision the ADR must make.** Decide the stable operator-facing lineage handle
for a ledger row across an edit — a stable alias carried through correction, an
automatic old-id-to-new-id redirect, or `history` resolving by any lineage id —
applying the modelo-addressing-ux principle (internal content address stays
authoritative; the operator handle is stable) to ledger transactions.

### F4 — Two period grammars (modelo vs ledger surfaces)

**Severity:** MEDIUM.

**Operator-visible symptom.** The same operator must learn two period
vocabularies depending on which sub-app they are in. Modelo surfaces accept
`0A / 1T-4T / 01-12`; ledger surfaces accept `2026Q1 / 2026-03 / 2026`. A
quarter is `1T` in one place and `2026Q1` in another, with no conversion offered
and no cross-acceptance. The userdocs guides had to teach both.

**Code evidence.** The ledger period normaliser
`src/aeat/entrypoints/cli/_common.py:190-207` (`_PERIOD_RE` /
`_canonical_period`) accepts only the `YYYY[Qn|-MM]` shapes and emits `2026Q1` /
`2026-03` / `2026`. The modelo-side token grammar and its validation messages
live separately in `src/aeat/locales/en.yml:~1628` and accept the AEAT
`0A / 1T-4T / 01-12` set.

**Prior-decision reconciliation.**
`2026-06-01-registry-period-code-union-cli-boundary-adr` decided the *modelo*
period grammar deliberately and at length: `StandardPeriodCode`
(`1T-4T`, `0A`, `01-12`, plus extended OSS/IOSS and ad-hoc members), the
explicit choice not to type it as a closed CLI enum, per-modelo help scoping.
That ADR is the authority for the AEAT-shaped grammar — but it scoped itself to
registry/modelo period codes and never reconciled the *ledger* `2026Q1` grammar,
which predates it and was decided implicitly in the ledger CLI common module
with no governing ADR. The second grammar is therefore an *implicitly decided*
divergence — an absence the ADR phase must repair, per this audit's own
no-ADR-found rule.

**Decision the ADR must make.** Decide one operator-facing period grammar (with
internal conversion to whichever representation each store needs) or
bidirectional acceptance at both surfaces. The registry-period-code ADR is the
incumbent authority for the AEAT shape; the decision is whether the ledger
surface adopts it, keeps its own with a conversion layer, or both surfaces
accept both.

### F5 — Help-text drift is systemic (hint strings describe instead of derive)

**Severity:** HIGH.

**Operator-visible symptom.** Hand-maintained CLI strings repeatedly disagree
with the CLI they describe — five distinct instances in a single campaign,
indicating a structural pattern rather than five typos. An operator who trusts
the help text is sent to non-existent commands, told a prefix is accepted when
only an exact id works, and offered enum choices and `--select` targets the
handler rejects.

**Code evidence (five instances).**
(a) A failure hint pointed at a non-existent
`aeat app modelo work verification-report list` command, corrected in commit
`7c3a19c89`.
(b) Evidence-id help promises "(or unambiguous prefix)"
(`src/aeat/locales/en.yml:1058`) while the lookup matches by exact equality at
`src/aeat/application/ledger/_evidence.py:352` (`record.evidence_id ==
evidence_id`).
(c) The `doclink` `--source` Typer option is typed as the full five-member
`AttachmentSource` enum (`LOCAL_FILE / GMAIL / GOOGLE_DRIVE / URL / INLINE`,
`src/aeat/domain/attachments/_enums.py:54-58`), so click advertises all five,
but the handler accepts only `gmail / google_drive / url` and refuses the rest
(`src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py:213-226`).
(d) `work verify --select` offers `latest-verified` and `filed`
(`ModeloCalculationRevisionSelector`,
`src/aeat/application/modelo/_selectors.py:50-54`) though `verify_modelo_revision`
refuses any state but `BORRADOR`
(`src/aeat/application/modelo/_verification_actions.py:728`), making
`--select latest-verified` an advertised-but-impossible combination.
(e) `integrity registry` help said "profile registry", corrected in commit
`0fd9a9119`.
The pattern: these strings *describe* the CLI by hand instead of being *derived*
from it, so they drift the moment the surface moves.

**Prior-decision reconciliation.** No ADR governs next-action hint strings or
the enum-choice-vs-handler contract — the surface was decided implicitly, hint
string by hint string, with no conformance gate. The project already has the
template for the fix: a documented-command conformance gate
(`test_documented_command_conformance.py`) pins doc commands against the live
tree. That precedent exists for *documentation* but was never extended to the
CLI's own internal hint strings and advertised enum choices. The absence of a
governing decision is itself the finding.

**Decision the ADR must make.** Decide a conformance-style gate for the two
classes of self-referential string — next-action / failure hints that name a
command path, and Typer enum choices whose handler accepts a narrower set —
mirroring the documented-command gate: a hint that names a command must resolve;
an advertised enum member must be acceptable to its handler, or the choice set
must be narrowed to what the handler accepts.

### F6 — Localization half-wired (root `--language` does not localize help)

**Severity:** MEDIUM.

**Operator-visible symptom.** The CLI advertises a `--language` flag that
silently fails for help text. `aeat --language en config profile create --help`
renders Spanish; only setting `AEAT_OUTPUT_LANGUAGE` *before* the process starts
changes help-text language. An operator who discovers the flag and trusts it is
quietly betrayed.

**Code evidence.** The root `--language` option is declared `is_eager=True` at
`src/aeat/entrypoints/cli/__init__.py:78-88`, so it is applied after the
import-time `tr(...)` calls have already rendered every help string. The
environment variable wins because it is read before import; the flag arrives too
late to affect the strings it claims to control.

**Prior-decision reconciliation.**
`2026-05-13-cli-workflow-redesign-profile-output-language-adr` (and the related
locale/output-language decisions) established the output-language model; none of
them decided the *help-text rendering timing* contract for the eager
`--language` flag. The half-wired behaviour is an unaddressed consequence of the
import-time `tr()` rendering model, decided implicitly. The ADR must decide the
honesty contract for the flag.

**Decision the ADR must make.** Decide whether the flag is made to work for help
text (deferring help rendering until after eager-option resolution), made to
warn when it cannot take effect, or removed from the surfaces it cannot affect.
The rule: a flag must not silently fail to do what it advertises.

### F7 — Write-only records (M036 declarations, no read-back)

**Severity:** MEDIUM.

**Operator-visible symptom.** Several record-creating verbs have no read-back.
The `aeat app modelo m036` group exposes exactly `alta / modificacion / baja` —
record verbs only. After recording an M036 declaration there is no list, no
edit, and no delete; the only confirmation is the command output the operator
has already scrolled past. The same shape recurs: no tax-year filing-history
surface, no guided manual-value entry.

**Code evidence.** The M036 group registers exactly three commands —
`alta`, `modificacion`, `baja` —
(`src/aeat/entrypoints/cli/_modelo_m036_cli.py:90,136,164`), and the lifecycle
module exposes only `record_m036_declaration` plus its id-derivation helper with
no read-back / list / mutate public surface
(`src/aeat/application/modelo/_m036_lifecycle.py`, sole writer
`record_m036_declaration`). The plan already carries the sibling gaps as backlog
steps `W05.P09.S52` (filing history) and `W05.P10.S32` (guided manual entry).

**Prior-decision reconciliation.** `2026-06-03-modelo-036-census-sync-adr`
decided the M036 declaration-recording surface (alta / modificacion / baja) but
never decided a read-back guarantee — the write path was specified without its
read counterpart. No ADR establishes "every record-creating verb has a
read-back"; the omission is systemic and implicitly decided.

**Decision the ADR must make.** Decide read-back as a baseline guarantee for
every record-creating verb: each verb that persists a record exposes a
corresponding list/show surface so the operator can confirm, review, and find
what they recorded after the confirmation scrolls away.

### F8 — Internals leak into a simple question (`preflight --revision-id` required)

**Severity:** LOW.

**Operator-visible symptom.** "Am I ready to file this?" demands a
registry-internal handle. `aeat config profile preflight` requires
`--revision-id` (marked `[required]` in live help), so answering a readiness
question forces the operator to first run `modelo describe`, read out an internal
revision id, and paste it back — friction the choose-modelo guide had to teach
explicitly (commit `948621a9c`).

**Code evidence.** The preflight command in
`src/aeat/entrypoints/cli/_config/__init__.py` declares `revision_id`,
`modelo`, `filing_year`, and `period` as required `typer.Option(...)` values
(no default), so `--revision-id` is mandatory to answer the readiness question.

**Prior-decision reconciliation.** This shares F3's root principle — the
modelo-addressing-ux ADR's "operators must never have to handle internal
content-addressed IDs" — applied here to the readiness surface, where it was
likewise never extended. No ADR decided that readiness must accept a
registry-internal revision id; it is an implicit consequence of the preflight
command signature.

**Decision the ADR must make.** Decide that `preflight` defaults to the active
revision for the given modelo/year/period, so the simple readiness question is
answerable from the natural key alone, with `--revision-id` available only as an
explicit override. This is the readiness-surface instance of the
F3 internal-handle principle.

## Recommendations

The pipeline ask is one ADR (or a small ADR set) that reconciles the
verb-and-lifecycle findings against the prior decisions named above, amending
each prior decision where it is being revised rather than re-deciding from
scratch:

- **Verb-and-lifecycle ADR (F1, F2, F3, F4).** Amend
  `2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr` to give
  the profile-switch intent a human verb over session-unlock semantics (F1).
  Amend `2026-05-14-ledger-transaction-lifecycle-adr` to make its Tier 1
  "reversible" claim true with a restore-to-`ACTIVE` transition (or rename the
  verbs), coordinating with `2026-06-02-ledger-operator-hardening-adr` so the
  inverse op carries the same `--yes`/`--reason`/audit guarantees as the forward
  op (F2). Extend `2026-06-04-modelo-addressing-ux-adr`'s stable-handle
  principle to ledger transaction identity across edits (F3). Reconcile the two
  period grammars against `2026-06-01-registry-period-code-union-cli-boundary-adr`,
  the incumbent authority for the AEAT shape, deciding whether the ledger
  surface adopts it or keeps a conversion layer (F4). Where F3, F4, F6, and F8
  found no governing ADR, the decision is net-new, not an amendment — that
  absence is itself a repair the ADR phase owns.

- **Conformance-gate fix (F5).** Decide a conformance-style gate for
  next-action / failure hint strings and Typer enum-choice surfaces, mirroring
  the existing documented-command conformance gate: a hint that names a command
  must resolve to a live command; an advertised enum member must be acceptable
  to its handler (or the advertised set narrowed to the accepted set). This is a
  gate-shaped fix, not a per-string patch — the five instances are symptoms of
  the missing gate.

- **Honesty fixes (F6, F8).** Make the `--language` flag honest — work, warn, or
  be removed from surfaces it cannot affect (F6). Default `preflight` to the
  active revision so the readiness question stops demanding an internal handle
  (F8).

- **Read-back baseline (F7).** Establish that every record-creating verb exposes
  a corresponding read-back (list/show) surface; close the M036 instance and the
  sibling backlog steps `W05.P09.S52` and `W05.P10.S32` under that guarantee.

## Codification candidates

Two candidates clear the three durability criteria (cross-session,
constraint-shaped, project-bound). Both should be authored only *after* the
verb-and-lifecycle ADR lands, so the rule body can cite the accepted decision
rather than this audit alone.

- **Source:** finding F1 (operator vocabulary leaks the storage layer).
  **Rule slug:** `operator-verbs-name-operator-intent`.
  **Rule:** An operator-facing CLI verb must name the operator's intent, not the
  storage or session mechanism that implements it; if a user-facing doc must
  gloss a verb to explain what it does (for example "switch by unlocking"), the
  verb is misnamed and the gloss is the smell.
  **Durability assessment:** Cross-session (any future agent adding a verb
  inherits it), constraint-shaped (a positive obligation with a clear smell
  test), project-bound (ties to this CLI's session-unlock model and the
  Spanish-stem naming discipline). Meets the bar.

- **Source:** finding F5 (help-text drift is systemic).
  **Rule slug:** `cli-hint-and-enum-choices-conformance-gated`.
  **Rule:** Every CLI next-action / failure hint that names a command path, and
  every Typer enum-choice surface whose handler accepts a narrower set, must be
  conformance-gated against the live tree (the hint resolves; the advertised
  enum member is acceptable to its handler) rather than hand-maintained as a
  describing string.
  **Durability assessment:** Cross-session (the drift recurred five times in one
  campaign and will recur whenever a string is hand-edited), constraint-shaped
  (a derive-don't-describe obligation with an existing gate template), and
  project-bound (mirrors the project's documented-command conformance gate).
  Meets the bar.

The remaining findings do **not** meet the codification bar in isolation: F2,
F3, F4, F6, F7, and F8 are concrete surface-design decisions for the ADR to
make, not yet cross-session constraints. Several of them share an underlying
principle already decided (internal content-addressed IDs stay authoritative;
operators handle a stable surface handle — F3, F8) or already promised (Tier 1
lifecycle transitions are reversible — F2). If the verb-and-lifecycle ADR
generalises one of those into a project-wide obligation, that generalisation —
not the individual finding — becomes the codification candidate at review time.
