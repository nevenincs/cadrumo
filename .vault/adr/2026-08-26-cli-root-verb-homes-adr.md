---
tags:
  - '#adr'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:7591cf4daafd4c35e9aa05e4a459e8f9a3d82dce8a5d8680a67b4bcdd30b6280'
related:
  - "[[2026-08-25-cli-root-verb-homes-audit]]"
---

# `cli-root-verb-homes` adr: `root verb homes and bidirectional transport verb symmetry` | (**status:** `proposed`)

## Problem Statement

The executable mounts 294 leaves under two roots whose entire written charter is
two help strings. `2026-08-25-cli-root-verb-homes-audit` establishes nine drifts
against that charter, the sharpest being that the whole modelo workbook surface
lives under `config google` and carries the only `filing` capability outside `app`.

Re-homing those leaves cannot be done in isolation, because the drift has a second
dimension the audit surfaced only in passing: the verbs themselves do not form
predictable pairs. Data enters the application through `import`, `file`, `pull`,
`pull-folder`, `doclink`, `add --source-path`, `batch --directory` and `restore`,
and leaves through `export` and `push`. Two of those tokens are spelled with
options the CLI contract already forbids. Three tokens (`file`, `archive`,
`restore`) carry two unrelated meanings each depending on which family they appear
in. Moving a verb to the right root while leaving it in a nine-token intake
vocabulary would relocate the confusion rather than remove it.

A decision is needed now because both dimensions touch the same specs, the same
locale keys and the same envelope `command=` identifiers. Landing them separately
means paying the breaking-envelope cost twice.

## Considerations

- The two root help strings are the only charter; no prior ADR states a placement
  rule (audit, `no-gate-enforces-root-ownership`).
- Every leaf already declares an `ExecutionPolicySpec` carrying capabilities, side
  effects and a write route, so an objective placement signal exists in authored
  data and needs no new annotation (audit, Scope).
- `filing` is declared on eleven leaves, ten under `app`; `registry` on
  twenty-three, twenty-two under `app`. The policy axes already dissent from the
  mount points (audit, findings one and five).
- Both workbook transports already share one plan builder in the application layer,
  so the defect is confined to the entrypoint (audit, finding one).
- The `aeat-cli-contract` rule fixes `pull` as the AEAT fetch verb and `--file` as
  the single-local-file input, and gives `censo file --file` plus `censo pull` as
  its worked dual-transport example. Any grammar that renames `file` must amend
  that rule rather than contradict it.
- The `sensitive-financial-data-secure-storage-only` rule prohibits live AEAT
  submission, so the AEAT counterparty has no outbound half by policy and its
  asymmetry is principled rather than accidental.
- `aeat-naming` reserves Spanish stems for AEAT domain concepts and leaves generic
  computing vocabulary in English, so a transport-neutral subject noun is
  admissible where no AEAT surface names the thing.
- `no-legacy-compatibility` forbids alias or bridge spellings, so every rename is a
  hard cutover with the old spelling deleted.
- The runtime write guard derives from the spec's declared `write_route` rather
  than a path allowlist, so re-homing carries the guard with it (audit, finding
  nine).
- `aeat-vaultspec-centralisation` retires new rule authorship, so the grammar lands
  as an amendment to the existing `aeat-cli-contract` rule source, never as a new
  rule file.

## Considered options

**Option A — re-home only, leave the verb vocabulary alone.** Cheapest and matches
the audit's literal scope. Rejected: it pays the breaking envelope-identifier cost
without buying predictability, and it leaves `config google sync calc pull` sitting
next to `app ledger pull-folder` as two spellings of one idea.

**Option B — normalise the verb vocabulary, leave the mounts alone.** Rejected for
the mirror reason: an operator who learns the grammar still cannot guess which root
a family lives under, and the `filing`-under-`config` defect survives untouched.

**Option C — key the transport grammar on the transport mechanism** (HTTP, Drive
API, Sheets API, filesystem). Rejected: mechanism is an implementation fact that
changes without the operator's knowledge, and it produces four token pairs where
the operator can only meaningfully distinguish two.

**Option D — key the transport grammar on the counterparty, and key root placement
on the declared execution policy.** Chosen. Two independent criteria, each derived
from something already authored and greppable, each mechanically gateable.

**Option E — retire the two-root split entirely and mount every family at the
executable root.** Rejected: `aeat-architecture-boundaries` fixes the CLI root
surface at `config` and `app` and forbids a third family, and flattening would
break that constraint in the opposite direction while making the 294-leaf surface
unnavigable.

## Constraints

No frontier technology and no immature dependency; the whole change is entrypoint
declaration plus locale keys. The blocking constraints are contractual rather than
technical.

The envelope `command=` identifiers are part of the operator-facing JSON contract,
and every re-homed or renamed leaf changes its identifier. There is no released
data and no deployed caller, so `no-legacy-compatibility` governs: the old
identifier is deleted, not aliased.

The `aeat-cli-contract` rule must be amended in the same campaign, because this
record's grammar retires the `file` transport token that the rule currently
presents as its canonical example. The amendment lands on the
`.vaultspec/rules/aeat-cli-contract.md` source and propagates through
`vaultspec-core sync`; the generated provider copies are never hand-edited.

The rule's own warning about unscanned surfaces binds every rename here: the
error-registry `default_suggestion` fields, the cross-period `next_action`
builders, the curated `operator_surface/_help.py` surface and the envelope
identifiers are not covered by the conformance gates and must be swept by hand.

One dependency is genuinely absent rather than deferred: there is no restore path
that reads the encrypted-object mirror back from the remote store. This record
does not build one, and it does not ship a stub, because
`aeat-architecture-boundaries` forbids design-only implementation shells.

## Implementation

### D1 — Root placement is keyed on the declared execution policy

A leaf declaring `calculation`, `filing` or `registry` is tax-application work and
mounts under `app`. A leaf whose write route is `bootstrap-root`, or whose
capability set is `profile-custody` without `encrypted-facts`, is custody or
environment configuration and mounts under `config`. A leaf declaring neither
signal is placed by its owning family, and its family is placed by this rule.

The criterion is deliberately keyed on data the author already writes, so the gate
that enforces it reads the same field the runtime write guard reads.

### D2 — Transport verbs are keyed on the counterparty, in matched pairs

There are two counterparty axes and exactly four transport tokens.

A **remote counterparty** — the AEAT sede, a Google Drive or Sheets store, a model
distribution host — is read with `pull` and written with `push`. A **local
filesystem** counterparty is read with `import` and written with `export`.

`upload`, `download`, `fetch`, `sync`, `send`, `get`, `capture`, `refresh`,
`mirror`, `probe` and `file` are not transport tokens and may not name a verb that
moves data. `file` retains its domain meaning as the act of filing a declaration,
and that meaning becomes exclusive.

Every family that moves data in both directions declares the matched pair of its
axis. Where one half is absent, the absence is recorded here as either a policy
fact or a declared gap; an unexplained missing half is a defect.

The AEAT axis has no outbound half, permanently, because live submission is
prohibited. That is the one asymmetry the grammar blesses.

### D3 — Option grammar is symmetric across the local axis

The single local input file is `--file`; the single local output path is
`--output`. `--source`, `--source-path`, `--path` and `--from-*` are forbidden as
local-file spellings. A bulk local directory is `--directory`.

`--output` is today a de-facto convention on four leaves and is promoted here to a
declared half of the pair, so that the local axis reads `import --file` against
`export --output`.

### D4 — Colliding tokens are resolved in favour of the domain meaning

`file` keeps only the filing meaning (`app modelo work file`); its transport uses
become `import`. `archive` and `restore` keep only the ledger row-lifecycle
meaning; the custody-backup uses become the `archive` subject's `export` and
`import` verbs, which reads as a noun-scoped subject rather than a colliding verb.

### D5 — The concrete surface changes

The modelo workbook family moves to `app` under a transport-neutral subject that
also accommodates the offline transport the export rule anticipates:
`config google sync calc export` becomes `app modelo workbook push`;
`sync calc pull` becomes `app modelo workbook pull`; `sync calc compute` and
`sync calc verify` become `app modelo workbook compute` and `workbook verify`,
neither being a transport verb.

The custody-backup family consolidates under one subject:
`config profile archive export` keeps its name and gains `--output` conformance;
`config profile restore` becomes `config profile archive import --file`;
`config google sync push` becomes `config profile archive push`;
`config google sync probe` becomes `config profile archive status`;
`config profile archive inspect` is unchanged. `config google` is left holding
only `login`, `logout`, `register`, `status`, `folder` and `credential-source` —
configuration and nothing else.

Ledger evidence intake collapses to the grammar: `app ledger doclink` becomes
`app ledger pull` with its forbidden `--source` retired in favour of
`--reference`; `app ledger pull-folder` keeps its name, matching the established
`pull` / `pull-all` sibling pattern in the live family; `app ledger evidence add`
renames `--source-path` to `--file`.

`app modelo reconcile file` becomes `app modelo reconcile import`, and
`config profile censo file` becomes `config profile censo import`, both retaining
`--file` and their `pull` siblings.

`app maintenance reconcile` folds into `config repair` and the one-verb `app
maintenance` family retires. `config repair integrity registry` retires in favour
of the existing `app registry verify`. One of `config profile preflight` and
`app modelo readiness` retires once their reports are shown to answer the same
question; the survivor is the `app` one, because the question is modelo-scoped.

`config provision pull` is already conformant under D2 and is not touched.

### D6 — A property gate enforces both criteria

One gate walks the declared graph and refuses on the property: a leaf declaring
`filing` or `registry` mounted outside `app`; a leaf with a `bootstrap-root` write
route mounted outside `config`; a transport verb whose token is outside the four;
a local-file option spelled anything but `--file` or `--output`. Exemptions are
keyed by leaf path with a stated reason, never by count, and the absent
remote-store restore path is the one exemption this record authorises.

The gate is proven by mounting a `filing` leaf under `config` from outside the
repository and confirming it reds.

### D7 — The charter is written down

The `config` help string is corrected to stop claiming diagnostics it does not own,
and the `aeat-cli-contract` rule source gains D2, D3 and D4 as an amendment,
replacing its `file --file` worked example with the counterparty grammar.

## Rationale

Option D wins on a knockout criterion the alternatives cannot meet: both of its
criteria are computable from data already authored on every leaf, in one pass over
the declared graph. That is what makes the gate in D6 a property rather than a
tally, and it is why the audit could enumerate all nine drifts mechanically before
this record existed. A criterion that required new annotation would decay the first
time an author skipped it.

Keying the transport grammar on the counterparty rather than the mechanism
(Option C) is what produces usability. An operator does not know or care whether
evidence arrives over the Drive API or an HTTP redirect, but always knows whether
the other end is a machine elsewhere or a file on their own disk. Two pairs are
learnable; four are a lookup table.

The grammar also converts the audit's `pull`-dilution finding from a defect into a
rule. `pull` was diluted precisely because it was defined against one counterparty
(AEAT) while being the natural word for every remote read. Widening it to the
remote axis and giving it a `push` partner restores the signal the CLI contract
wanted, because the operator now learns "remote" instead of "AEAT", and AEAT's
missing `push` teaches the filing prohibition every time it is noticed.

Doing both dimensions in one campaign is justified by cost rather than elegance:
the envelope `command=` identifier is the expensive part of any move, and it is
paid once per leaf whether the leaf moves root, changes verb, or both.

## Consequences

Every re-homed or renamed leaf changes its envelope `command=` identifier. With no
released data and no deployed caller this is a clean cutover, but it is a real
break for anything scripted against the current strings, and the agent harness
documents must be swept in the same commits per the CLI contract.

The four unscanned surfaces the contract rule names — error-registry suggestions,
`next_action` builders, the curated help surface, envelope identifiers — carry the
real regression risk, because no gate catches a stale reference in them. The
mitigation is that the write guard is spec-derived and therefore moves with the
leaf, so the failure mode is a dead instruction rather than a dropped write
guard.

Retiring `config repair integrity registry` and one of the two readiness verbs
removes surface rather than adding it, which is the campaign's only net
simplification and should not be traded away if scope pressure appears.

The declared gap is honest and uncomfortable: after this record, `config profile
archive push` writes an encrypted mirror to a remote store that nothing can read
back. Naming it `push` makes the missing `pull` visible on every help listing,
which is the intended effect — the current name `sync push` hides it. A follow-on
record owes the restore path, and it will have to rule on key availability at
restore time, which is why it is not folded in here.

Amending `aeat-cli-contract` retires a worked example that other documents may
cite by its `file --file` spelling, so the amendment sweep must grep the vault and
the rule corpus, not only the source tree.

The grammar opens a pathway the export rule already anticipated: once
`app modelo workbook` exists as a subject with a counterparty-keyed verb set, the
offline xls transport lands as `workbook export --output` and `workbook import
--file` with no new vocabulary and no new decision.
