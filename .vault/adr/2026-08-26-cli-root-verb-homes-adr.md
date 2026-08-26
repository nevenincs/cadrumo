---
tags:
  - '#adr'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:59690fd568b81b5d37ed11b60d3441131b5b43302abc1160743f7c1d5771fe0f'
related:
  - "[[2026-08-25-cli-root-verb-homes-audit]]"
---

# `cli-root-verb-homes` adr: `root verb homes and bidirectional transport verb symmetry` | (**status:** `accepted`)

## Problem Statement

The executable mounts 294 leaves under two roots whose entire written charter is
two help strings. `2026-08-25-cli-root-verb-homes-audit` establishes twelve drifts
against that charter, the sharpest being that the modelo workbook surface lives
under `config google` and holds the only `filing` capability outside `app`.

Re-homing cannot be done in isolation, because the drift has a second dimension:
the verbs do not form predictable pairs. Data enters through `import`, `file`,
`pull`, `pull-folder`, `doclink`, `add`, `batch` and `restore`, and leaves through
`export` and `push`. Three tokens (`file`, `archive`, `restore`) carry two
unrelated meanings each depending on family. Twenty-three leaves spell a local
path with one of nineteen different option or metavar names. Moving a verb to the
right root while leaving it in that vocabulary relocates the confusion.

A decision is needed now because both dimensions touch the same specs, the same
locale keys and the same envelope `command=` identifiers, and the envelope
identifier is the expensive part of any move. Landing them separately pays that
cost twice.

This record is a full re-derivation of a first draft that two independent reviews
rejected. The first draft's transport half rested on a premise both reviews
falsified: that a gate could tell a local path from a remote handle by inspecting
what is already declared. It cannot, and the re-derivation below turns that from
an assumption into a precondition.

## Considerations

- The two root help strings are the only charter; `2026-07-28-cli-authority-verb-conformance-adr`
  separately states the two-root split is an accepted architectural boundary and
  gives a second criterion — app commands operate on the active profile bucket —
  that reaches the same verdict on the workbook family by a different route.
- Capability counts, re-derived directly from `COMMAND_GRAPH`: 294 leaves, 212
  `app` / 82 `config`; `filing` 7 (6 app, 1 config); `registry` 22 (all app);
  `calculation` 40 (32 app, 8 config); `profile-custody` 52 (1 app, 51 config).
  The audit's first published counts were inflated by a census that matched
  capability names against whole rendered rows, and are corrected in place there.
- `calculation` is NOT a reliable `app` signal on its own: `config profile
  status`, `validate` and `preflight` declare it while computing facts about the
  profile, and `config repair integrity registry` declares it while reading
  bundled data. All four are read-only with write route `none`.
- Nothing on a leaf declares that a verb moves data, or that an option carries a
  local path. Path-typing is a proxy that misfires in both directions: `app ledger
  pull-folder --folder` is a remote Drive id typed `str`; `app ledger evidence add`
  takes a local path as a positional typed `str`; `app ledger import
  --verify-source` is `Path`-typed but is not the primary input.
- `app ledger doclink --source` is a required `DocumentLinkSource` closed enum
  sitting beside a separately required `--reference`. `aeat-architecture-boundaries`
  mandates that enum declaration. It is not a local-file spelling.
- `app modelo readiness` already asserts its `--revision-id` equal to the
  law-determined resolution and refuses on divergence
  (`src/cadrumo/application/state_projection.py:852`), and the guard is written
  `if request.revision_id and ...`, so the projection already tolerates an omitted
  id. Only the CLI spec makes it required.
- `config google sync probe` verifies OAuth credentials and root-folder resolution
  (`src/cadrumo/entrypoints/cli/_config/_google.py:356`). It never reads the
  secure-object mirror; it is Google configuration.
- `docs/_sequences/contracts/**/*.seq` is gate-covered by
  `test_documented_command_conformance.py`, so a rename reds there rather than
  rotting. `docs/locales/{es,ca,hu}/LC_MESSAGES/**` is NOT gate-covered and rots
  silently.
- `src/cadrumo/_data/agent/` does not exist; the harness is `src/cadrumo-harness`.
  The `aeat-cli-contract` rule cites the dead path, so the rule is itself stale.
- `aeat-locales-cli` requires a real value in all four catalogues and forbids the
  placeholder; the rename touches roughly 78 keys in each of en/es/ca/hu.
- `no-legacy-compatibility` forbids alias spellings, so every rename is a hard
  cutover. `aeat-vaultspec-centralisation` retires new rule authorship, so the
  grammar lands as an amendment to `aeat-cli-contract`.
- `aeat-architecture-boundaries` was rewritten by another actor while this record
  was being drafted, and its import model reversed: package facades, re-export
  modules, hierarchical roll-ups and PEP 562 export maps are now prohibited, and
  every cross-package consumer imports directly from the symbol's canonical
  defining module with `__init__.py` namespaces inert. This binds the campaign's
  implementation, because the workbook handlers being moved currently reach the
  export service through a package facade. Every moved handler adopts canonical
  defining-module imports as part of its move; none may carry a facade import to
  its new home. This is a constraint discovered mid-campaign, not a decision of
  this record.

## Considered options

**Option A — re-home only.** Rejected: pays the envelope break without buying
predictability.

**Option B — normalise verbs only.** Rejected: the `filing`-under-`config` defect
survives and root membership stays unguessable.

**Option C — key the grammar on transport mechanism** (HTTP, Drive API, Sheets
API, filesystem). Rejected: mechanism changes without the operator's knowledge and
yields four pairs where an operator can distinguish two.

**Option D — key the grammar on the counterparty, key placement on declared
policy, and treat the gate as derivable from what is already declared.** This was
the first draft. **Rejected on review**: the placement half is derivable, the
transport half is not, and a gate written against the transport half degrades to a
name list — a tally, which `aeat-quality-gates` forbids.

**Option E — as D, but declare the missing fact.** Chosen. Placement stays keyed
on declared policy at narrowest-subject granularity; the transport grammar becomes
enforceable by adding a transport-locus annotation to the parameter spec, which is
a precondition of the gate rather than an assumption behind it.

**Option F — flatten to one root.** Rejected: `aeat-architecture-boundaries` fixes
the root surface at `config` and `app`.

## Constraints

The transport half **cannot ship before its precondition**: `ParameterSpec` gains
a declared locus, and every path-bearing parameter declares it. Until that lands,
any spelling gate is a name list. This ordering is a hard dependency, not a
preference, and the plan sequences it first.

The envelope `command=` identifiers change for every re-homed or renamed leaf.
With no released data and no deployed caller, `no-legacy-compatibility` governs:
delete the old identifier, never alias it.

The change is larger than the first draft claimed. Beyond entrypoint specs it
touches roughly 78 locale keys in each of four catalogues (312 leaves) under a
hard parity gate and an honesty ratchet that forbids the placeholder; gate-covered
`.seq` contracts and their JSON goldens; three non-gate-covered `docs/locales`
catalogues; `src/cadrumo/application/operator_actions/_catalogue.py:512`;
`dev/quality/cli_action_census_dispositions.toml`; and `dev/benchmarks/cli`
goldens.

`aeat-cli-contract` must be amended, and D7 enumerates the specific sentences.
The amendment lands on `.vaultspec/rules/aeat-cli-contract.md` and propagates by
`vaultspec-core sync`; generated provider copies are never hand-edited.

One capability is genuinely absent: nothing reads the encrypted-object mirror back
from the remote store. This record does not build it and does not ship a stub.

## Implementation

### D1 — Placement is refused per subject, from declared policy

**Leaf signals.** A leaf carries an `app` signal if it declares `filing`, or
`registry`, or `calculation` together with a write route other than `none`. A leaf
carries a `config` signal if its write route is `bootstrap-root`, or if it
declares `profile-custody` without `encrypted-facts`.

`calculation` alone is deliberately insufficient, because four read-only `config`
leaves declare it while computing facts about the profile or about bundled data.
Requiring a write route separates computing a filing from reporting on a profile.

**Subject rule.** Placement is decided for the NARROWEST MOUNTABLE SUBJECT — the
deepest group that can move as a unit — not for a leaf and not for a top-level
family. That subject mounts under `app` if any of its leaves carries an `app`
signal, under `config` if any carries a `config` signal. A subject carrying both
is a design defect and is split before it is placed. Operators navigate subjects,
and a subject split across roots is unlearnable regardless of which half is right.

The granularity is load-bearing and was found by simulation, not by argument. At
top-level-family granularity the rule moves the whole `config google` family to
`app`, because three of its fourteen leaves carry `app` signals — contradicting
D5, which keeps Google auth, folder and credential-source under `config`. At
narrowest-subject granularity the rule produces exactly two moves over the whole
graph, `config google sync calc` to `app` and `app maintenance` to `config`, and
demands no splits. Those are precisely D5's moves.

**D1 is a refusal criterion, not a placement criterion, and the record does not
claim otherwise.** Simulated over all 67 mountable subjects, 46 of them — 68% —
carry no signal in either direction. D1 says nothing about where `app live`,
`app overview`, `config auth` or `config provision` belong; it only refuses a
subject that has landed demonstrably wrong. Every no-signal subject stays where it
is, and its placement rests on the charter prose in D7, not on this criterion.
Claiming more than that is what made the first draft's gate untestable.

### D2 — Transport verbs are keyed on the counterparty

Two axes, four tokens. A **remote counterparty** — the AEAT sede, a Drive or
Sheets store, a model distribution host — is read with `pull`, written with
`push`. A **local filesystem** counterparty is read with `import`, written with
`export`.

**The verb names the primary counterparty; a secondary locus is an option, never a
second verb.** `app live filed pull --output-root` reads AEAT and writes local: it
is a `pull`, and its local output is spelled by D3.

**A verb whose primary purpose is computation names the computation.** Transport
it performs as a means is incidental and is declared on its options. This is why
`spreadsheet calculate` is not a `pull` even though it reads a remote workbook —
and the ADR records that collision rather than defining it away.

**Compounds are permitted and their suffix axis is ruled.** `<token>-<subject>`
and `<token>-all` are legal inflections; `<token>-<locus>` is not, because locus
belongs in an option. So `pull-sources`, `pull-evidence`, `pull-history` and
`pull-all` are legal, and `pull-folder` is not.

`upload`, `download`, `fetch`, `sync`, `send`, `get`, `capture`, `refresh`,
`mirror`, `probe`, `doclink` and `file` may not name a verb whose primary purpose
is moving data. `file` retains only its domain meaning.

**Every family that moves data carries a disposition for each half.** A missing
half is either a policy fact or a declared gap; unexplained is a defect. The
dispositions:

- AEAT (`app live`): inbound `pull`; outbound absent **by policy** — live
  submission is prohibited.
- `app modelo spreadsheet`: `pull` / `push` complete.
- `app modelo` filing artefacts: `export` outbound, `reconcile import` and
  `filing-record import` inbound; complete.
- `app modelo audit`: `export` outbound; inbound absent — **declared gap**, an
  audit bundle is re-derivable and has no import case.
- `app modelo review-package`: `export` and `import` both present; see D5.
- `app ledger`: `import` / `export` complete for rows; `evidence pull` /
  `pull-all` inbound from remote, outbound absent — **declared gap**.
- `config profile archive`: `export` / `import` complete for local.
- `config profile archive`: `push` outbound to the remote replica; `pull` absent
  — **declared gap**, the restore path does not exist and is owed a follow-on
  record. (Listed as `config profile mirror` before the D5 amendment.)
- `config provision`: `pull` inbound; outbound absent **by policy** — the app
  never publishes a model.
**A verb that CREATES a record names what it creates.** Amended 2026-08-26 after
sweeping the whole graph against this grammar. The record first carved out
credential enrolment (`config auth certificate register`, `config auth
configure`, `config google register`) as a special case. It is not special: it is
one instance of a third category the grammar was missing.

`app ledger evidence add` registers purchase-invoice evidence from a PDF; `app
ledger evidence batch` ingests a directory of documents into evidence and a
reviewable draft; `app ledger inventory closing-authority-record` records
evidenced closing authority. Each reads a local file, and for none of them is
moving the file the point — the file is where the content comes from, and the
verb names the record that results. Renaming any of them to `import` would
describe the mechanism and hide the outcome.

So the grammar has three verb categories, not two. A TRANSPORT verb moves data
and takes one of the four tokens. A COMPUTATION verb names the computation. A
CREATING verb names the record it creates. In the second and third, the local
file or remote handle is declared on the parameters under D3 and is not allowed
to claim the verb.

### D3 — Option spelling is keyed on a DECLARED locus

**Precondition.** `ParameterSpec` gains a `TransportLocus` declaring `local-in`,
`local-out`, `remote-handle` or `none`, plus a shape of `file`, `directory` or
`root`. Every path-bearing or handle-bearing parameter declares it. Without this,
the rest of D3 is unenforceable.

Given the declaration, spellings are fixed:

Spelling is keyed on locus, shape and ROLE. Role is the axis the first draft
missed, and it is the one that matters most: a verb may take more than one local
input, and the tree does so on at least eight leaves.

| locus | shape | role | spelling |
|---|---|---|---|
| local-in | file | primary | `--file`, or the positional subject |
| local-in | file | auxiliary | `--<role>` naming what it is |
| local-in | file | auxiliary, repeatable | plural `--<role>` |
| local-out | file | primary | `--output` |
| local-in | directory | primary | `--directory` |
| local-out | directory | primary | `--output-root` |
| local-in | root | auxiliary | `--<name>-root` |
| remote-handle | — | — | free (`--folder`, `--reference`, `--spreadsheet-id`) |
| none | — | — | free |

**Exactly one local input per verb is primary.** Every additional local input is an
auxiliary and is spelled for the role it plays, not for the fact that it is a file.
`app ledger import --file --verify-source`, `app modelo work calculate
--m303-filing-evidence`, `app registry verify-filed-state --observation
--source-observation`, and `review-package encrypt-feedback --output --receipt` are
all CONFORMANT under this rule, and were all violations under the first draft's
single-`--file` table. Naming an auxiliary for its role is better operator
guidance than numbering it, so the rule ratifies the existing practice rather than
churning it.

A positional subject satisfies the primary role. Where a leaf carries two path
positionals — `review-package counter-sign <PACKAGE> <SIGNATURE>`,
`verify-receipt <PACKAGE> <RECEIPT_PATH>`, `verify-signature <PACKAGE>
<SIGNATURE>` — the first is the subject and the second is an auxiliary that may
stay positional, because a cryptographic verification reads as a pair. What is
refused is a subject spelled as an option while its siblings use a positional,
which is why `review-package import-feedback --package` changes and nothing else
in that family does.

A parameter declaring locus `none` is outside the table entirely. That protects
`--source` on `doclink` (a closed enum), `--from-year` and `--from-filing-record`.

The consequence of the role axis is that the campaign is far smaller than the
first draft implied. Of 55 `Path`-typed parameters across 37 leaves and 15
distinct spellings, this table leaves all but two conformant: `import-feedback
--package` becomes a positional, and `config profile restore --file --artifact`
must declare which of its two local inputs is primary. `config google register
--client-json` is an auxiliary-free enrolment verb already carved out of D2, and
D3's carve-out extends to it: it keeps `--client-json`.

### D4 — Colliding tokens resolve to the domain meaning

`file` keeps only the filing meaning; its transport uses become `import`.
`archive` and `restore` keep only the ledger row-lifecycle meaning; the
custody-backup uses become verbs under the `archive` and `mirror` subjects.
`work` and any new subject must not shadow each other, which is why the workbook
subject is `spreadsheet` and not `workbook`.

### D5 — The concrete surface changes

**Workbook family moves and is renamed.** `config google sync calc {export, pull,
compute, verify}` becomes `app modelo spreadsheet {push, pull, calculate,
verify}`. The subject is `spreadsheet`, not `workbook`, because `app modelo work`
already exists and `work` / `workbook` differ by four characters under one parent.
`compute` becomes `calculate` to match `app modelo work calculate`, which is the
same idea. `calculate` and `verify` are computation verbs under D2 and keep their
names despite reading a remote workbook; the collision with `pull` is recorded
here, not defined away.

**Custody backup splits into two subjects by blast radius.** `config profile
archive export` keeps its name; `config profile restore` becomes `config profile
archive import --file`; `config profile archive inspect` is unchanged. The
whole-corpus Drive mirror does NOT join that subject: `config google sync push`
becomes `config profile mirror push`. `archive` implies a thing you can restore,
and the mirror cannot be read back — putting it under `archive` would promise
recoverability that does not exist.

**Superseded 2026-08-26 by operator ruling: the verb is `config profile archive
push`.** The operator rejected `mirror` as a subject noun on the ground that it
names nothing an operator recognises — asked what a `mirror` is, no reading
distinguishes a backup from a malformed one. The objection this record raises
above is answered rather than overruled: the danger was that `archive` promises
a round trip, and the answer is that the VERB carries the promise, not the
subject. `push` sitting beside a working `export` / `import` pair makes the
absent `pull` loud on every help listing, where `mirror push` was quiet because
the subject told the reader nothing to expect. The declared gap is unchanged and
still owes a follow-on record; it is now visible in the place an operator looks. `config google sync probe` **stays where it
is**: it is a credential and connectivity check, which is Google configuration.

**Ledger evidence intake moves into its own subgroup.** `app ledger doclink`
becomes `app ledger evidence pull <TRANSACTION_ID> --reference`, **retaining
`--source` unchanged** as the required link-source enum. `app ledger pull-folder`
becomes `app ledger evidence pull-all --folder`, using the real `pull-all`
cardinality precedent from `app live filed` rather than the `-folder` locus
suffix D2 refuses. `app ledger evidence add`'s positional local path and `evidence
batch`'s positional directory declare their locus and take the D3 spellings.

**`file` transport uses are renamed.** `app modelo reconcile file` becomes
`reconcile import`; `config profile censo file` becomes `censo import`. Both keep
`--file` and their `pull` siblings.

**`review-package` is brought under the grammar.** Its ten leaves are local
transport: `build` and the `sign`/`encrypt-*` leaves write with `--output`;
`import-feedback` and `decrypt` read. `import-feedback`'s `--package` becomes a
positional to match its six siblings; `<ENVELOPE_PATH>`, `<RECEIPT_PATH>` and
`<SIGNATURE>` declare their locus and keep positional subject form.

**Duplicates retire, where they are duplicates.** `app maintenance reconcile`
folds into the custody-backup subject and the one-verb family retires.

**`config repair integrity registry` is NOT retired. Amended 2026-08-26 on the
execution proof.** This record first ruled it a duplicate of `app registry
verify`. The proof step that was required before deleting it showed the two do
different work, and neither subsumes the other: `verify_registry_tree` validates
the authority and runs `required_text` corpus checks over every legal reference,
while `build_registry_integrity_report` additionally builds a representative
`M100` snapshot and so exercises the snapshot-build gate — typed-ID existence,
renta first-slice routing, per-binding selector shape. Retiring the config verb
would have silently dropped that coverage.

The audit finding that prompted the retirement was already once corrected for
false evidence, and this is its second correction: the verbs are not duplicates
at all. What remains true is that an operator has two places to ask about
registry health, which is a discoverability defect rather than a duplication
one, and it is left open rather than fixed by deletion. `config profile preflight` retires in favour of `app modelo readiness`,
**conditional on readiness first making `--revision-id` optional** with
law-determined resolution — cheap, because the projection already resolves
law-determined and asserts equality — and on adopting preflight's exit-2 contract.
Ten `.seq` contracts call preflight and are re-pointed in the same change.

`config provision pull` is already conformant and is not touched.

### D6 — Two gates, each testing a stated property

**Gate one, placement.** Encodes D1 literally, at narrowest-subject granularity:
no subject carrying an `app` signal mounts under `config`, none carrying a
`config` signal mounts under `app`, and no subject carries both. Because D1
refuses rather than decides, this gate is silent on the 68% of subjects that carry
no signal — it must not be read, or extended, as an assertion that those are
correctly placed.

**Gate two, spelling.** Encodes the D3 table over declared locus. It ships only
after the D3 precondition, and it refuses on the declared locus, never on a name
list or a `Path` type guess.

Exemptions are keyed by `(leaf path, enclosing function)` with a stated reason, and
a stale exemption fails — the discipline `aeat-quality-gates` requires. An
exemption cannot express an ABSENCE, so the declared gaps in D2 live in this
record and in the family disposition table, not in a gate exemption list.

Each gate is proven by breaking production on purpose from outside the repository:
mount a `filing` leaf under `config` for gate one, mis-spell a declared `local-in`
file parameter for gate two.

### D7 — The charter and the rule are corrected

The `config` root help stops claiming diagnostics it does not own. The
`aeat-cli-contract` rule source is amended in these specific places: the opening
paragraph fixing `pull` as the AEAT fetch verb (widened to the remote
counterparty, with the AEAT signal migrating to the `app live` subtree); the
normative sentence requiring a dual-transport command to be a subgroup of `pull`
and `file --file` (becomes `pull` and `import --file`); the `censo file --file`
worked example; and the dead `src/cadrumo/_data/agent/` path, which is now
`src/cadrumo-harness`.

## Rationale

Option E wins because it is the only option that makes the enforcing gate honest.
The first draft's knockout claim — that both criteria are computable from data
already authored — was true for placement and false for transport, and both
reviews independently falsified it. Rather than weaken the gate to a name list,
this record declares the missing fact. That converts an assumption into a
precondition with a cost, which is a worse-looking decision and a better one.

Keying transport on counterparty rather than mechanism produces usability: an
operator never knows whether evidence arrives over the Drive API or an HTTP
redirect, but always knows whether the other end is a machine elsewhere or a file
on their own disk. Two pairs are learnable; four are a lookup table.

Deciding placement per subject rather than per leaf is what makes D1 survive
contact with the tree. A leaf-level rule evicted `config profile status` — the most
canonical `config` verb there is — because it declares `calculation`. The subject
rule keeps it, without weakening the signal that moves the workbook family. Both
the granularity and the 68% blind spot were established by simulating the rule
over the graph before adopting it, which is the check the first draft skipped.

Doing both dimensions in one campaign is justified by cost: the envelope
identifier is the expensive part, and it is paid once per leaf whether the leaf
changes root, verb, or both.

## Consequences

Every re-homed or renamed leaf changes its envelope `command=` identifier — a
clean cutover with no released data, but a real break for anything scripted, and
the `.seq` goldens and `operator_actions` catalogue must move with it.

The D3 precondition means this campaign adds a field to the parameter spec before
it renames anything. That is real work with no operator-visible benefit on its
own, and it is the price of a gate that is a property rather than a tally.

Widening `pull` to every remote counterparty gives up something the first draft
did not price: today `pull` under `app live` plus the one sanctioned `censo pull`
is a greppable enumeration of AEAT reach. After D2 it names Drive reads, Sheets
reads and model downloads indistinguishably. The write guard is unaffected — it is
spec-derived from `write_route` with no verb allowlist — so the loss is
auditability, not enforcement. D6's placement gate compensates by refusing an AEAT
`network` leaf mounted outside `app live`, which moves the signal from the verb to
the mount.

Naming the mirror `config profile mirror push` rather than folding it into
`archive` keeps a true promise instead of an attractive one. The operator still
meets `push` in a place that does not round-trip, and that asymmetry is recorded
rather than hidden — but `mirror` does not imply the recovery that `archive`
would. **Superseded — see the D5 amendment.** The shipped verb is `config
profile archive push`; the asymmetry is carried by `push` beside `export` and
`import`, which states it more loudly than an unfamiliar subject noun did.

Retiring three leaves is the campaign's only net simplification and should not be
traded away under scope pressure.

Amending `aeat-cli-contract` retires a worked example other documents may cite by
its `file --file` spelling, so the amendment sweep covers the vault and the rule
corpus, not only the source tree.

The grammar opens the pathway the export rule anticipates: once `app modelo
spreadsheet` exists with a counterparty-keyed verb set, the offline xls transport
lands as `spreadsheet export --output` and `spreadsheet import --file` with no new
vocabulary and no new decision.
