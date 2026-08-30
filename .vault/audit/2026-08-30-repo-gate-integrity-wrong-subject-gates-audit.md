---
tags:
  - '#audit'
  - '#repo-gate-integrity'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:36b67de554083aa38c3b49c0572646838b8e6aa695deb2134ca8874a077fb736'
related: []
---

# `repo-gate-integrity` audit: `gates that report clean about the wrong subject`

## Scope

A gate that is WRONG fails loudly and gets fixed. A gate that is CORRECT about
something other than what everyone believes it covers reports green forever, and
its green is read as coverage of the larger thing. This audit records that second
shape as a distinct species, with one fully-measured exemplar.

The distinction matters because the two have different tells. A gate that drifted
into blindness was once right, so a staleness or drift check can catch it. A gate
authored blind to the population it describes was never right about that
population, and nothing about it will ever go stale — there is no earlier state
to diff against. It cannot be found by any mechanical freshness check. It is
found only by asking, of a green gate, *what exactly did this assert*.

The title says gates because that is where the shape was first measured, but it
is not confined to them. Two of the instances below are verification ACTIONS
rather than committed gates — a test selector and a grep — and they fail
identically: correct about their own subject, irrelevant to the question being
asked, and returning exactly what they would return if everything were fine.
Read "gate" throughout as any artifact whose green is taken as evidence.

Scoped to what was measured directly during the receipt-retirement work on
2026-08-30. Instances relayed from other lanes are recorded as relayed and are
marked unverified here; they need their own evidence before anyone acts on them.

## Findings

### shared-config-gate-asserts-the-constant-not-its-use | high | the strict-frozen gate proves the canonical config is correct and nothing proves any module uses it

`src/cadrumo/core/tests/test_strict_frozen_config_validates_defaults.py` is
green and has been. It asserts that `STRICT_FROZEN_CONFIG` and
`STRICT_FROZEN_HIDDEN_INPUT_CONFIG` each declare `validate_default`, `strict`,
`frozen` and `extra="forbid"`, and that a default violating its own field
constraint is refused. Every one of those assertions is true and worth having.

Its own module docstring states the failure mode it does not check: "These
assertions are written against the shared constant rather than against any model
that embeds it, because the guarantee belongs to the constant. A per-module
declaration would leave every module that forgot it unprotected, which is the
state this replaced."

That is the current state, at scale. An AST census of every inline
`ConfigDict(...)` call under `src/cadrumo` finds 302 calls, 269 of them in
production modules. Two populations, defined precisely because a single figure
without its filter gets quoted back wrongly:

- **62** production calls declare `strict` AND `frozen` AND `extra="forbid"`,
  omit `validate_default`, and add no key — a strict subset of the canonical
  constant, which is to say the canonical config with a guarantee silently
  removed.
- **182** production calls declare `strict` OR `frozen`, omit
  `validate_default`, and add no key. This is the superset; the 120 additional
  sites are ones the narrower filter dropped for lacking `extra="forbid"`, such
  as `{'strict': True, 'frozen': True}` and `{'frozen': True, 'extra':
  'forbid'}`.
- **40** production calls add a genuine key (`arbitrary_types_allowed`,
  `validate_assignment`). These are the divergences the canonical constant's own
  docstring sanctions — but **39 of the 40 also omit `validate_default`**, so a
  sanctioned divergence on one axis has been silently carrying an unsanctioned
  one on another. The docstring permits a local configuration where a module
  needs something DIFFERENT. It does not permit that module to also quietly drop
  a guarantee it never had a reason to drop, and 39 of 40 did.

The union — every production site that declares some strictness and skips
default validation — is **221**.

The concentration is worth recording, because it shows this is a copied
convention rather than scattered oversight: `application/live/remote_state_models.py`
19, `domain/calculations/registry/query_reports.py` 15,
`domain/calculations/registry/record_design_schema.py` 12, `llm/models.py` 10,
`domain/calculations/registry/binding_selector_utils.py` 7,
`llm/column_role_mapping.py` 7, `application/registry/diff.py` 6.

A correction belongs in this record rather than only in the working history.
This population was first reported as "103 sites". That figure was wrong twice:
it counted test modules alongside production, and it used the narrow filter while
being described in the language of the broad one. The production-only narrow
figure is 62. Nobody should carry 103 forward.

### narrow-step-fix-lands-on-the-shared-home-only | high | a completed row fixed the canonical config and never swept the local copies its own text names

The architecture plan's `W05.P23.S307` is marked complete and reads, in its own
words, "Validate defaults on the shared strict-frozen model configuration rather
than patching each embedding module as the gap resurfaces". The canonical config
was genuinely fixed and carries `validate_default=True` today; that half is real
and load-bearing.

The modules holding their own local copy escaped it entirely — and they are
precisely the "each embedding module" the row exists to avoid patching. Three
were found by meaning during unrelated pre-write discovery, in
`entrypoints/tui/operations/`: `projection.py`, `logs.py` and `modal.py`, each
declaring a private constant equal to the canonical minus `validate_default`.
All three are now repointed at the canonical import. The census above is what
that discovery generalised to.

This is delivered-narrower wearing the same checkbox as delivered-as-specified.
The row should NOT be reopened: what it claims on the shared constant was
delivered, and reopening it would misrepresent completed work while orphaning its
execution record. The sweep is new work and belongs in a new row citing it.

Two notes for whoever sweeps. First, the repoint must name the canonical symbol
at every use site; assigning the canonical to the old private name would be a
forwarding alias, which the architecture rules prohibit outright, and it would
leave the divergence invisible to the very census that found it — the tell that a
repoint is complete is that the module no longer imports `ConfigDict` at all.
Second, a local constant is legitimate where a module needs a DIFFERENT config,
which the canonical docstring says plainly; a strict subset is not that. A weaker
config nobody chose is a defect, and a weaker config someone chose for a stated
reason is a decision — so the sweep must record a reason inline wherever it keeps
one.

### tests-that-construct-their-own-subject-prove-nothing-about-reachability | high | a closed union advertised three outcomes, production could emit one, and the two dead members had passing tests

A refusal union declares three outcome types. Counting PRODUCTION constructions
per member: 3, 0 and 0. The assembler can emit exactly one of the three
outcomes it advertises.

Both dead members are constructed — in two test modules, one at the model layer
and one in the view layer, which build them by hand and assert on them. Those
tests pass. **Passing tests over a type read as evidence the type is live, and
they are not**: a test that manufactures its own subject proves the type can be
built and says nothing whatever about whether anything builds it. A reachability
defect hides behind green tests more reliably than behind no tests at all,
because no tests at least reads as a gap.

The view layer had gone further and written rendering and disclosure handling for
both unreachable refusals, validated against hand-built fixtures — production
code for states the producer cannot produce, with a green suite over it. That is
the same false-confidence shape one layer up, and the lane that wrote it did not
catch it in its own sweep.

**The generalisable check, and it is the durable half of this finding: for every
closed union of outcome types, count PRODUCTION constructions per member. A
member at zero is either an unwritten producer or a dead branch, and tests
constructing it distinguish neither.** It is mechanical, it reaches past any one
union, and it would have found both of these without anyone suspecting them —
which is precisely the property the hand-listed subject set above lacks. This is
the second check in this document that must derive its subjects rather than
receive them, and the first one a scan can perform end to end.

The remedy is not uniform, which is why the check reports rather than fixes. A
zero-construction member is one of three things: a check intended and never
written, where the finding is the MISSING CHECK and the type is correct and
waiting; a branch genuinely unreachable, where the type, its union membership,
its validator, its rendering and its tests all go together; or a reachable
outcome the producer currently routes around. Here one member's version fields
are pinned to a single literal, so the mismatch it exists to report cannot yet be
represented — that is the first case, and deleting it would remove the slot for a
check the contract still needs.

### check-construction-sites-has-a-direction-dependency | high | the same zero-construction-site signal is a defect on an output and a missing caller on an input, and the rule as first stated would manufacture false findings

Every other entry here is an artifact that looked sound and was not. This is the
mirror — an artifact that looks wrong and is right — and it is the more dangerous
direction for anyone who has just spent a day training on the first.

The never-populated-field finding above produced a rule: check the construction
sites, not the schema. Nine declarations across five types with zero population
sites, and the model declarations tell you nothing. That rule is correct and was
made a standing requirement.

Applied to the edit contract it manufactures two FALSE defects.
`ModeloEditCompatibilityTupleV1` and `ModeloEditParseRequestV1` each have zero
non-test CONSTRUCTION sites, which reads identically to the workspace case. They
are its opposite. Both have live consuming services that take them as
parameters: `parse_modelo_edit_value(request: ModeloEditParseRequestV1)` and
`_incompatible_axis(compatibility: ModeloEditCompatibilityTupleV1)`, both in the
edit-services module.

**The discriminator is not the count, it is the direction the type faces.** A
REQUEST type with a live consumer and no constructor is a contract awaiting its
caller. A PRODUCED RECORD with a declared field nothing fills is a defect. Same
signal, opposite meaning, and nothing in the site count separates them.

The practical form, to be applied before reporting any zero-construction-site
finding: **ask whether the type is produced or consumed. If a live service takes
it as a parameter, the absence is a missing caller, not a missing producer.**

Two measurement notes. The parse-request type has four non-test sites, not two —
its definition, its own export list, the consuming module's import, and the
consuming signature — so a claim of "two sites, definition and `__all__`"
undercounts by omitting the consumer, which is precisely the evidence that
decides the direction. And the compatibility type is additionally consumed by a
same-package operation-definition field, another consumer with no constructor.

**The second-order point, and it connects this to the selector finding above: a
pattern strong enough to be predictive is strong enough to be over-applied.**
That happened twice in one campaign — once when two readers reached for a single
selector defect that turned out to be two different commands, and once here.
The second time the pattern was one its own author had established, which is
when it is hardest to doubt: nine confirmations make the tenth application feel
like recognition rather than inference.

### an-enumerated-subject-list-is-a-hardcoded-tally-in-disguise | high | a check that lists its subjects instead of deriving them is correct only about the list, and it looks more careful than the version that works

This project has ruled against hardcoded tallies repeatedly — a module count, an
import-site ceiling, an exact consumer count in a test name — on the ground that
a number encodes a moment, trains the next person to update the constant, and
then detects nothing. Every one of those rulings addressed a COUNT. None noticed
that a hand-written list of SUBJECTS is the same antipattern in different
clothes, and several of the artifacts already fixed for the count still carry the
list.

**Why it survived so many rulings is the important part.** A tally at least LOOKS
like a magic number; a reader meets `== 7` and feels the itch. An enumerated
subject list looks like thoroughness. Naming the five types a check covers reads
as more careful than deriving them, so the defect is camouflaged by the
appearance of diligence — and a reviewer scanning for magic numbers sees a
diligent list and moves on.

The worked example is the strongest available because the finding supplied its
own instance. A row was written to close a set of declared-but-never-populated
fields, and its whole subject was that a partial fix would LOOK COMPLETE FROM THE
MODEL SIDE — it said so, and it correctly prescribed re-running the
construction-site scan across every field rather than trusting the model
declarations. Its type list named four types. An AST walk of the module returns
five: a `recovery_action` on a revision-mismatch refusal type appeared in nobody's
list. So a sweeper working that row would have fixed four types, re-run a scan
scoped to those same four, obtained a clean result, and shipped with the fifth
still empty. The confirmation would have been correct about the list and wrong
about the population — inside a finding whose entire subject is that failure.

**The remedy is not a longer list.** A longer list is a better instance of the
broken method. The remedy is to DERIVE the subjects from the artifact under
check: walk the module and take the types it actually declares, so a type added
tomorrow is covered without anyone remembering to add it.

**The rule, stated to reach past gates: any check that enumerates its subjects
rather than deriving them is correct only about the enumeration.** That covers
closure checks, allowlists keyed by a hand-written set, conformance matrices,
censuses, and exemption registers — several of which have already had one
instance fixed without the class being named. Where derivation is genuinely
infeasible, the fallback is not to enumerate silently: it is to enumerate AND
assert that the enumeration still equals the derived set, so drift fails loudly
instead of passing quietly.

**There is a third member, quieter than both: a lookup keyed on a property that
HAPPENS to be shared today rather than on the identity that determines the
answer.** The worked example is a decision made correctly, which is the clearest
way to see the trap. A filing destination presents two capabilities that both
read `UNMEASURED` today — but for unrelated reasons, one permanently
unmeasurable because no producer records a verdict at all, the other merely
pending a contributor port. Its explanation map is keyed on the capability
IDENTITY. Had it been keyed on the shared disposition it would work perfectly
today and mis-answer the instant the port lands: the export capability flips to
`AVAILABLE` while the draft one stays `UNMEASURED`, and the "permanently
unmeasurable" reason would attach itself to the capability that had just become
measurable.

That one needs naming separately because of how well it hides. A tally is
VISIBLY a snapshot — someone updating it at least notices they are editing a
number. A subject list looks like thoroughness. A coincidental key looks like a
correct mapping: right shape, right types, sound structure, and nothing in it
signals that it will start lying when the coincidence ends.

So the family orders by how loudly the defect advertises itself, and the
ordering is the useful part because it says where to look hardest:

1. a hardcoded **tally** — looks like a magic number, most visible
2. a hardcoded **subject list** — looks like thoroughness, less visible
3. a **coincidental-property key** — looks like a correct mapping, least visible

All three are correct today and wrong later; they differ only in how much they
advertise it.

**The third is catchable only at design time, and that distinction must be
preserved.** A tally and a subject list can both be found by a scan — look for a
literal, or for an enumeration that should have been derived. A key that is
correct-by-coincidence cannot be detected by inspecting the code, because
nothing in it is wrong yet; the code will pass every check and every test until
the day the shared property stops being shared. The only defence is the question
asked while writing the lookup: does this key DETERMINE the answer, or does it
merely CORRELATE with it today? That belongs with the cheap habits at the end of
this document rather than with the gate findings, because no gate can carry it.

### remediation-must-precede-the-gate-that-would-catch-it | medium | landing the detector before the sweep reds a hundred sites and the pressure becomes to weaken it

The gate this family wants is straightforward: an AST census refusing any
module-local strict-frozen configuration whose keys are a strict subset of the
canonical's, admitting one only where it adds a key or carries a documented
inline reason.

Landing it today reds 62 to 221 production sites depending on where the line is
drawn. That ordering has now produced the same trap three times in one campaign:
the detector is authored, it reds a large legitimate population, and the cheapest
route to green becomes weakening the detector rather than doing the remediation.
The gate lands at the END of the sweep, and a row that pairs them must say so, or
the next executor will reasonably read the gate as the fix.

The same ordering constraint governs the bare single-code campaign-identifier
pattern in the marker scan, which reaches 22 production modules that have not
been swept, and it governed the step-notation patterns until their one production
site was swept.

### selector-narrowing-conceals-red-in-any-form | medium | a marker expression and a keyword expression hide failures identically, and one produced a false green in this audit

The integration marker concealing red in a default run is documented elsewhere.
The generalisation, found the hard way here, is that ANY narrowing selector does
it, and the harness's own banner is the mitigation being read past.

A mutation proof run during this work restored a campaign identifier to shipped
source and ran the gate under a keyword expression matching "campaign" and
"metadata". It reported three passed. The gate had not run at all: the consuming
test is named for the vault documents it forbids rather than for the metadata
family it belongs to, so the selector silently excluded the one test the proof
existed to exercise. Run by full node identifier the gate failed precisely,
naming the file and line. Restored, it passed.

A false green from a selector is worse than a false green from a marker, because
the marker case at least prints a partial-run banner naming what was deselected.
A keyword expression that matches nothing relevant prints an ordinary green.

### absence-of-old-text-cannot-verify-a-removal | medium | a narrowing note must quote what it dropped, so grepping for the dropped phrase reports unchanged on every correctly-narrowed record

A plan row was narrowed to drop a requirement for producer-supplied cycle and
depth dispositions, which a check of the projection module had shown do not
exist. The no-silent-narrowing rule requires a narrowing to state what it
excluded, so the note names the dropped requirement — which means it quotes the
exact phrase that was removed.

A grep for that phrase therefore returns a hit on the narrowed row. It reports
`unchanged` on a record that has been correctly changed, and it will keep
reporting that on every future check by every future reader, because the
quotation is supposed to be there. The presence of the old text is the EVIDENCE
OF the removal rather than the absence of it.

Both halves of this were observed first-hand and independently: the row's author
found the hit while verifying the edit had landed, and a second reader reproduced
it and confirmed the context. It is separable from a timing question that arose
at the same moment — a check run before the edit landed also showed the original
text — and the two explanations were distinguished by reading the file rather
than by either party asserting from their own tool output. Only the grep
explanation persists; the timing one resolves itself.

**The general rule: where a record is required to name what it removed,
absence-of-old-text is not a valid check for removal.** That covers every
narrowing note this campaign writes, every deprecation record, and every audit
that quotes the defect it closes — which is most of them, including this one.
Anyone verifying such work by grepping for the phrase a record dropped gets the
wrong answer on precisely the records that did the job properly.

The remedy is to key the check on the NEW marker rather than on the absence of
the old one. A phrase unique to the narrowed form cannot appear on an unnarrowed
record, so it answers the question actually being asked. This is the same
correction the selector finding above needs — run the check that discriminates,
not the one that is easy to type.

It is also this document's own thesis applied to a grep instead of a gate: a
check correct about its own subject (does this string appear) and wrong about the
question being asked (is this record still unnarrowed). The audit family is not
limited to gates. Any verification artifact can be correct and irrelevant at the
same time, and the tell is identical — it returns exactly what it would return if
everything were fine.

### the-failures-here-are-provenance-not-reasoning | medium | in every case the reasoning on the evidence held, and what failed was knowing what grade of evidence was in hand

Worth separating because it changes what to fix. Across the errors observed
directly during this work — not the relayed ones — the reasoning was sound on the
evidence held every time. What failed was knowing WHAT GRADE of evidence that
was, and when it had been taken.

The instances, all first-hand. A population figure was published as "103 sites"
from a filter that counted test modules alongside production and was described in
the language of a broader filter than the one it used. A scanner's behaviour was
reported from a probe that modelled it rather than from reading it. A tree-wide
import failure was attributed to a half-landed rename without opening the file
named in the traceback to see whether the destination existed — it did. A gate was
declared green from a run whose selector had excluded the only test that mattered.
None of these was a bad inference. Each was a correct inference over material
whose grade was not established.

The two roles fail differently and that decides who can catch what. An
ORIGINATION error — generating a claim from an ungrounded reading — is caught
only by the originator, because only they know which branch they modelled or
which filter they ran, and the fix is one file read. An AMPLIFICATION error —
carrying someone else's claim onward as fact — cannot be caught by care on the
receiving side at all, because a well-argued ungrounded claim and a measured one
are identical in shape. A claim built on the real scanner is MORE persuasive, not
less, when the invented part sits inside the harness around it.

The mechanism, therefore, is not more caution on either side. It is that
provenance travels WITH a claim: the originator states whether a figure came from
reading code or from modelling it, and the amplifier asks before carrying it
onward, particularly before it reaches anyone who will act on it. Both halves are
cheap and neither works alone — an unread label does nothing, and a question
nobody tracked the answer to does nothing.

**A third shape sits beneath both, and no provenance label catches it: a
reviewer holding two incompatible rulings without noticing, because each was
made in a different conversation about a different file.** One authorisation
ruled that the atomicity an architecture rule demands is that a move and its
consumer updates share ONE CHANGE rather than one commit, with a collection
check either side as the proof. Hours later the same reviewer ruled a
sixteen-file promotion impossible for an agent to perform, on the ground that it
needed a commit. Same operation, opposite rulings — and the second was recorded
into a plan row and carried onward as a blocker before anyone compared them. The
measured scope was 17 import statements across 16 files, only two of them
cross-package.

Nothing detects this. It is not a stale claim: both rulings were live. It is not
an ungrounded claim in the usual sense: each was reasonable inside its own
conversation. The inconsistency exists only in the union of two exchanges that no
artifact holds together — which is the concrete argument for why a ruling belongs
in a plan row rather than in a message, since a row can be compared against
another row and a message cannot.

It is also the fourth blocker in one campaign to dissolve on measurement, and the
first that a reviewer originated rather than inherited. The cheap defence is one
question asked before declaring anything blocked: **has this same shape been
ruled on elsewhere, and did I measure this instance or estimate it?** Both halves
are load-bearing — here the earlier ruling was forgotten AND the scope was never
measured, and either check alone would have caught it.

This is a more tractable problem than "be more careful", which is why it is
recorded here rather than left as a resolution. It is also the same shape as this
document's subject one level up: a gate reporting clean about the wrong subject
and a claim carrying the wrong grade of evidence are both cases where the artifact
looks exactly as it would if it were sound.

### relayed-instances-pending-their-own-evidence | low | four further instances reported by other lanes, recorded here unverified

Recorded so the family has one home, explicitly NOT verified in this audit and
not to be acted on from this record alone: a TUI route census built on a
hardcoded literal set; an executor conformance matrix asserting a twenty-item
registry against its own thirteen-item tuple; a staleness message whose
remediation instruction completes the defect it should prevent; a workspace
remnant scanner whose pass condition contradicts a legitimate docstring
explaining a retirement; and a relocation-parity test whose name pins an exact
consumer count. Each needs its own measurement before it earns a finding
heading here.

### withdrawn-docstring-only-marker-scan | low | reported as an instance of this family and refuted on reading the code

Recorded because a withdrawn finding that leaves no trace gets rediscovered. The
production half of the campaign-metadata marker scan was reported as reading
docstring ranges only, which would have made every campaign identifier in a
production comment invisible to it. That is false. The single scan helper
inspects a token when it is a COMMENT, or when it is a STRING falling inside the
supplied ranges; the ranges argument distinguishes a docstring from an arbitrary
string literal and does not gate comments at all. The helper's own docstring
states it is the one scan mechanism for both module populations, and warns that a
parallel scanner would be free to drift invisibly.

The claim came from a simulation written to answer the question without reading
the scanner: the probe skipped comments under the flag it was testing, so it
measured its author's hypothesis faithfully and the code not at all. Running a
probe outside the repository is the right discipline and it is not a substitute
for reading the implementation, because a probe against a hypothesis and a probe
against reality return the same shape of answer.

### a-closed-union-can-advertise-outcomes-nothing-emits | high | two of three refusal union members have zero production constructions, and tests constructing them directly made the gap invisible

The direction-dependency finding above establishes that a zero-construction-site
signal means different things for an input type and an output type. This is the
next question that finding does not ask: when a type is a member of a **closed
union of outcome types**, zero production constructions is neither a defect nor
a waiting contract until you know whether the *producer* was ever written.

Measured on the workspace refusal union at
`src/cadrumo/application/modelo/workspace_models.py:1254`:

| union member | production constructions | test constructions |
|---|---|---|
| `ModeloWorkspaceVersionRefusalV1` | 0 | 3 |
| `ModeloWorkspaceRevisionMismatchRefusalV1` | 0 | 2 |
| `ModeloWorkspaceDomainRefusalV1` | 3 | 1 |

The union advertises three refusal outcomes and the assembler can emit exactly
one. `ModeloWorkspaceDomainRefusalV1` is constructed at `workspace.py:1711`,
`:1722` and `:1747`. The other two are constructed nowhere in non-test source,
and there is no `contract_version` checking path anywhere in non-test source at
all — so the version refusal exists for a check nobody wrote.

`ModeloWorkspaceRevisionMismatchRefusalV1` additionally carries a model
validator at `:1194` (`_require_exact_mismatch_axes`). Because the type is never
constructed in production, **that validator has never run outside tests**: a
reader who fixes only the emission leaves a guard with no evidence it works.

**Why nothing caught it is the finding.** Both dead members ARE constructed — in
`application/modelo/tests/test_workspace_models.py` and in
`entrypoints/tui/modelo/view/tests/test_workspace_view_models.py`. The tests
build them directly and assert on them, so they pass, and passing tests over a
type read as evidence the type is live. A reachability defect hides most
reliably behind green tests that construct their own subject.

The TUI view layer is the sharper half: it carries rendering and disclosure
handling for both unreachable refusals, validated against hand-built instances.
That is view code for states the assembler cannot produce, proven by fixtures
that manufacture the state.

**Do not close this by filling `recovery_action`** on either type. The empty
field is a symptom. The adjudication is three-way, not produce-or-delete:

- the check was intended and never written — the finding is the MISSING CHECK
  and the type is correct and waiting (the version refusal looks like this, and
  deleting it would erase the evidence that a versioned contract has no version
  check);
- the refusal is unreachable by construction — then type, union membership,
  validator, view rendering and tests are removed together;
- it is reachable and the assembler takes a different path today.

**Remediation, stated as a mechanical check rather than two rows:** for every
closed union of outcome types, count production constructions per member. A
member at zero is either an unwritten producer or a dead branch, and tests
constructing it prove neither. This generalises past this union and would have
found both members without anyone suspecting them — which is exactly the
property a hand-listed subject set lacks, per the
`an-enumerated-subject-list-is-a-hardcoded-tally-in-disguise` finding above.

### corrections-and-delivered-work-that-exist-only-in-messages | high | two measurement corrections and most of a lane's delivered work have no durable record, so the session's end erases them

Two corrections were relayed upward, caught by their own author after the
original figure had already been reported, and recorded nowhere but in the
message stream:

- **S350's exemption key** is `enclosing_symbol` + role + alias + identity. It
  is NOT the triple, which **collides on 61 rows**. A reader who re-derives the
  key from the triple gets a census that silently merges 61 distinct sites.
- **S351's internal-symbol count is 4, not 6.**

Neither figure appears in any live vault document. A grep for `enclosing_symbol`
across `.vault/` returns only the search index and one archived exec record from
a different campaign.

**The same gap covers the delivered work itself.** `.vault/exec/2026-08-11-tui-architecture/`
holds records for S330, S331, S332, S334, S336 and S337. It holds none for
S322, S333, S349, S350, S351 or S358, and `W07.P16.S351` is still an open `- [ ]`
row in the plan while its promotion is present in the working tree.

`aeat-agent-orchestration` states that no plan step may be marked complete
without a matching exec record, so that delivered-as-specified,
delivered-narrower and recorded-but-not-implemented cannot wear the same
checkbox. The failure observed here is the mirror of the one that rule guards:
not a row closed without evidence, but **work delivered with no row and no
record at all**, which is invisible to every later reader rather than merely
over-claimed.

The operative constraint in this worktree is that agents do not commit, so git
carries no trace either. That makes the exec record the ONLY durable artifact
for delivered work, and its absence total rather than partial.

**Remediation:** a lane that reports delivered work must write its exec record
in the same action, not at close; and a claim corrected mid-session must land in
a document before the correction is relayed, because the relay is what creates
the false belief the correction exists to kill. A correction that lives only in
a message is strictly worse than the uncorrected figure in a row: the row can be
re-measured by anyone, while the message is visible to nobody who was not
addressed on it.

### a-cardinality-match-between-two-different-sets-reads-as-agreement | medium | two parties measured four names each, shared one element, and the matching counts disguised that they were answering different questions

The clearest instance of this document's own thesis, produced by its author while
adjudicating another instance of it.

A row named four types. One party measured `edit_contract.__all__` and found four
names. The other ran a definition-anchored search for the row's four names and
found one moved, three still private. **The two sets of four share exactly one
element.** Both measurements were correct. They answered different questions,
and the matching cardinality made that invisible: four found, four expected,
matched without ever comparing members.

**A count agreeing is not the sets agreeing.** Where a disagreement is about a
set, compare MEMBERS before arguing about the number — a cardinality match
between two different sets is the strongest available disguise for talking past
each other, because it produces the surface appearance of confirmation.

**A second failure rode on top of the first, and is the more damaging one.**
Holding the (wrong) correction, its author also supplied a mechanism for it: that
the other party's search had matched an import line rather than a definition. The
underlying rule is sound and this project makes it unusually sharp — an imported
name in a private module is the CORRECT post-relocation state, so a successful
move and an unstarted one look identical to an unanchored grep. But the other
party's search was already anchored on `^class` / `^type` and could not have
matched an import. So a real rule was attached to an incident it did not explain.

**A correct rule offered as the cause of an event it did not cause is worse than
no explanation**, because the rule's soundness transfers to the diagnosis and the
whole package reads as verified. This is reasoning from a plausible shape to a
conclusion without reading the branch — the failure this audit's other findings
repeatedly identify — arriving inside the act of correcting someone else.

**Keep the occurrence-versus-definition rule.** Anchor set membership searches on
`^class` / `^type`, never on a bare name. Strike it as this incident's cause.

**Remediation:** when a peer disputes a measurement, run THEIR exact search
before defending your own, and state which set each figure describes. The
disagreement here cost one exchange because the disputing party named the
specific search that would settle it and said it would rather be wrong than have
its lead act on the push-back. That is the behaviour that contained it, and it
ran upward against a lead's correction, which is the direction it is hardest to
run.

### bare-step-numbers-resolve-across-plans | medium | the same Step id exists in three plans, so a naive lookup silently returns a different plan's row

Step ids are canonical only WITHIN their plan. `S322`, `S333`, `S349`, `S350`,
`S351` and `S358` all exist in at least three plans in this vault:
`2026-07-01-import-centralization`, `2026-06-09-docstring-google-style`, and
`2026-08-11-tui-architecture`.

An unscoped grep for `S322` resolves to `W05.P83.S322` in the
import-centralization plan. The tui-architecture row is `W05.P23.S322`. Both are
real rows, both match, and the wrong one is returned first — with no signal that
a choice was made.

This is the audit's own subject in a new place: the lookup is CORRECT about what
it matched and wrong about the question asked. It is also the same shape as the
cardinality finding above — a match that carries no evidence of which set it came
from reads as an answer rather than as an ambiguity.

The consequence is worse than a bad read, because Step ids address MUTATIONS. A
`plan_progress` call or an exec-record scaffold resolved from a bare number can
mark or document a row in a plan nobody was working on, and the resulting
checkbox is indistinguishable from a legitimate one.

**How:** always scope a Step lookup to its plan stem, and address rows by the
full canonical identifier including wave and phase (`W05.P23.S322`), never by the
bare Step number. Anything scripting across this vault on bare Step numbers will
cross-wire plans.

Found while writing exec records for delivered work, by an executor that noticed
the resolved row did not describe the work it had done — the check that caught it
was reading the matched row's text rather than trusting the match.

### one-sweep-addressed-from-two-plans-double-counts-its-own-remainder | high | two rows in two plans name the same sweep, so each row's figure counts work the other has already done

`W01.P01.S100` in the interface plan and `W05.P23.S322` in the architecture plan
are the same sweep of bare single-code campaign identifiers from production
source, addressed from two plans that do not reference each other.

S322's safe half ran first and removed most of the population. S100's stated
figure of 68 sites across 22 modules was therefore already stale when read;
measured against the current tree the remainder is **16 sites across 9 modules**.
The modules that vanished from the set — `_row_set_assembly.py`, `recovery.py`,
`llm_classification.py`, `_operator_surface_reconciliation.py` and others — are
exactly S322's completed sites.

**Neither row can be executed correctly without knowing the other exists.** An
executor taking S100's figure at face value plans for four times the remaining
work; one closing S322 without checking S100 leaves a row whose text describes
work that no longer exists. Both rows look independently coherent, which is what
makes the duplication survive review.

**The remaining 9 modules are not arbitrary** — they are the sites S322
deliberately declined as peer-held plus one handed to another lane. So the
residue is a coordination boundary, not a leftover, and it will not shrink on its
own.

**The ordering constraint is therefore still binding.** S100 flips a scan pattern
to production scope at the END of its sweep. With 16 sites live the flip is not
ready, and `user_profile/bundle.py:188` and `:255` carry `Serialiser — S105` /
`Deserialiser — S106` banners that are ambiguous in both directions, since those
are also real ruff rule codes. See
`remediation-must-precede-the-gate-that-would-catch-it` above.

**A stripper that removes a lint directive but not its code list re-creates the
exact defect.** A first measurement of this population returned 75 modules / 123
sites because `# noqa: S106` and `# ruff: noqa: S105` were stripped of the
directive while `S106` survived and matched as a campaign id — the failure S100's
own text warns about, reproduced in fresh tooling minutes after that warning was
read. Strip the directive AND its codes, then sample the top hits before
reporting any figure.

**How:** before executing a sweep row, search the OTHER plans for the same
target population, not just the same row id. Cross-reference the rows in both
directions so neither can be executed blind.

### a-discrepancy-prompts-the-check-but-is-not-the-check | high | the wrong counts caught today were all caught because they disagreed with an expectation, and a wrong count that agrees with one has no prompt at all

Three wrong counts were caught in one session. Every one of them was caught the
same way, and it is not the way anyone intended.

- A stale-path stripper reported **75 modules / 123 sites** against a row claiming
  68 / 22. The figure was implausibly LARGE, which forced a look at the members;
  sampling showed they were ruff suppressions (`# noqa: S106`) whose directive had
  been stripped while the code survived and matched as a campaign id. True figure:
  16 / 9.
- A public-surface inventory reported **four types moved** against a row naming
  four types. The counts AGREED, so nothing forced a look, and the two sets of
  four shared exactly one member. That one was caught only because a second party
  disputed it and named the search that would settle it.
- A hand-listed set of workspace types with unpopulated fields reported four; an
  AST walk found nine across five types.

**The pattern:** in each case the check that actually worked was inspecting
members of the population. The discrepancy only PROMPTED that inspection — and in
the one case where the counts happened to agree, no prompt existed and the error
survived until an unrelated dispute exposed it.

So a measurement discipline that relies on noticing an implausible number is
calibrated on the easy half of the failure space. **A wrong count that lands in
the expected range produces no signal whatsoever**, and nothing in its shape
distinguishes it from a right one. The first case above was caught by luck of
magnitude; had the stripper erred in the other direction and returned something
near 68 / 22, it would have been reported and believed.

**Do not fix this with a discipline — disciplines fail exactly when nothing
prompts them, which is the failure mode above.** The structural form is to make
the measurement itself EMIT MEMBERS ALONGSIDE THE COUNT: a handful per bucket,
printed by the same script that produces the figure, so inspection is not a
separate step anyone has to remember. The 16 / 9 correction above was one command
away only because that script already printed per-file line numbers.

A count that arrives naked invites belief; a count that arrives with six of its
members attached invites reading. This also covers the agreeing-counts case,
where magnitude offers nothing: four types against four types still shows two
different sets the moment the members sit next to each other on screen.

**How:** emit members with every count. Where two parties report counts for what
they believe is the same set, compare MEMBERS before comparing numbers. An
agreeing count is not evidence the sets agree; see
`a-cardinality-match-between-two-different-sets-reads-as-agreement` above, and
`an-enumerated-subject-list-is-a-hardcoded-tally-in-disguise` for the same
property in a gate's subject list.

### the-supported-terminal-size-set-is-declared-three-times | high | three TUI suites each declare their own minimum/ordinary/wide triple, so no answer exists to which sizes the product supports

Found by a semantic sweep for redeclared implementations, not by a gate.

Three declarations of the same concept — the terminal sizes the interface must
remain operable at — live in three suites, and they disagree:

| declaration | site | rationale recorded |
|---|---|---|
| `[(80, 24), (120, 40), (200, 50)]` | `entrypoints/tui/tests/test_visual_verification.py:81` (`_SIZES`) | **yes** — a docstring justifies each as floor, ordinary, wide |
| `[(80, 24), (100, 30), (160, 48)]` | `entrypoints/tui/components/tests/test_widgets.py:51` (ids `narrow`/`medium`/`wide`) | no |
| `((80, 24), (120, 36), (160, 48))` | `entrypoints/tui/modelo/view/tests/test_work_review.py:570` | no |

Only the floor, 80x24, is common to all three. Every other size is one suite's
private choice, and the two undocumented triples assert the same intent in
different numbers.

**The consequence is a coverage claim nobody can state.** A layout regression
appearing only at 120x40 is caught by one suite and invisible to the other two; a
regression at 160x48 is caught by two and missed by the third. "The interface
works at the supported sizes" is not a claim this suite set can make, because
there is no supported set — there are three, and their union is an accident of
authorship rather than a decision.

This is the redeclaration hazard in its ordinary form: no suite is wrong, each is
locally coherent, and the defect exists only in their union — the same property
as `one-sweep-addressed-from-two-plans-double-counts-its-own-remainder` above.

**`_SIZES` is the canonical declaration** and the only one that records WHY each
size is there, which is what makes it the authority rather than merely the first.
It is currently private to its own test module.

**How:** promote the size set to one shared declaration the TUI suites import,
carrying its rationale with it, and delete the two private triples. Where a suite
genuinely needs a size outside the shared set, it declares that size WITH its
reason beside the shared import, so the exception is visible as an exception.
Adding a size to the shared set is then one edit that widens every suite at once,
which is the property three private triples cannot have.

**Do not resolve this by taking the union.** The union is four to five sizes
nobody chose, and it multiplies every parametrised TUI test's runtime without any
stated reason for the sizes it adds.

### a-style-rule-that-parses-is-not-a-style-rule-that-binds | medium | two TUI stylesheet declarations parsed cleanly, applied nothing, and reported no error

While bounding a summary panel that was evicting a data table off-screen at
80x24, two stylesheet attempts were made before one worked:

- `max-height: 40%` — parsed cleanly, bound nothing. The panel's parent is an
  auto-height `Vertical`, so the percentage has no definite basis to resolve
  against.
- `max-height: 40h` — parsed cleanly, bound nothing. Textual does not resolve
  that viewport unit for this property.

**Neither produced a warning, an error, or any signal.** Both left the panel
unbounded while reading, in the stylesheet, as though a bound had been declared.
A reader auditing that CSS would have counted the constraint as present.

This is the audit's subject in the declarative layer. Everywhere else in this
document the failing artefact is a check that reports clean about the wrong
subject; here it is a CONSTRAINT that reads as applied and is not. The failure
mode is the same — a surface that carries the appearance of a claim without the
substance — and it is worse in a stylesheet, because there is no execution to
step through and nothing to assert against.

**What separated the two cases was an absolute value.** Setting `max-height: 8`
DID bind, which distinguished "this property is ignored here" from "this unit
does not resolve here". Without that third probe the two failures are
indistinguishable and the natural conclusion — that the property does not work —
is wrong.

**How:** after adding a layout constraint, measure the RENDERED REGION and
confirm the constraint changed it. Do not accept a clean parse, and do not accept
a green test as evidence the rule bound — a test can pass because some other
change fixed the symptom while the declaration sits inert. Where a bound must
hold and the stylesheet cannot express it, put it in code with a docstring saying
why, or the next reader will move it back into the stylesheet where it will parse
and do nothing.

Prefer a FRACTION of the viewport over a pinned value for a constraint that
should bind only when space is scarce: a pinned cap that fixes the small terminal
forces the same restriction on the large one, where nothing was wrong.

### the-geometry-harness-has-no-caller-and-the-modelo-screens-have-no-geometry-gate | high | the appearance-defect reader is uncalled, the visual gates cover five screens that exclude the modelo surfaces, and a just-landed layout fix is correct by manual reading only

Two halves of one gap, found while verifying a layout fix.

**The canonical reader is uncalled.** `entrypoints/tui/devtools/frame.py` defines
`geometry_band(app, width)` at `:120` and `capture(app, ...)` at `:200`, reading
three appearance properties off a live app: widgets painted past the side edges,
a scrollable host whose content overflows while `max_scroll_y <= 0`, and
**multiple visible vertical scroll owners** (`:145-153`). A tree-wide search for
`geometry_band` and `capture` returns exactly one file — the module that defines
them. Nothing drives either. (`devtools/fixture.py` IS imported by tests; the
frame reader is not.)

**The visual gates cover a different set of screens.** `test_visual_verification.py`
drives `FlowScreen`, `LoginScreen`, `ProfileManagerScreen`, `RegistrationScreen`
and `StatusScreen`. `ModeloWorkReviewScreen` appears zero times, and the C2
workspace destinations are absent too.

So the three properties are proven for five screens, the reader that could prove
them for any screen has no caller, and the modelo surfaces are covered by
neither.

**The live consequence.** A layout fix bounding a summary panel at 80x24 added
`overflow-y: auto` to `#modelo-review-summary` (`work_review.py:671`) — a scroll
owner nested inside the body's own `ContentScroll`, which is exactly the shape the
third check exists to catch. Driving `geometry_band` by hand at all three sizes
reported CLEAN, and the body's `max_scroll_y` was 2109, placing the original
defect in the weaker reachable-but-not-visible class rather than the stronger
unscrollable one.

That reading is correct and it is a ONE-TIME MANUAL OBSERVATION. No gate holds it.
The next change to that stylesheet can introduce a second visible scroll owner and
nothing will say so — and the author will have the same reason to believe it is
fine that this author did: a green suite over a screen whose geometry nothing
checks.

The fix's own author put it best: it was verified by luck of construction, not by
design. The 58-passing view suite asserts behaviour and content; it asserts
nothing about painted geometry.

**How:** drive `geometry_band` over the modelo screens, or enrol them in the
visual-verification suite, so the three properties are gated rather than read. A
reader with no caller is dead capacity in the same sense as an output type with
no producer — see
`a-closed-union-can-advertise-outcomes-nothing-emits` above; the difference is
that this one is fully implemented, documented, and correct, which makes it more
likely to be rebuilt than found. It was rebuilt, weaker, during this very
investigation, by someone who had no reason to know it existed.

### an-interpolated-constant-was-wrong-by-fifteen-columns | high | a two-point interpolation put a layout transition at ~100 columns; measurement puts it at 114, which moves every conclusion drawn from it

The summary panel in the modelo work review wraps six lines to eight below a
certain width. Two points were measured — 8 rows at 80 columns, 6 rows at 120 —
and the transition was reported as "~100 columns", correctly labelled as an
interpolation rather than a measurement.

**Bisected, it is 114/115:** the summary wraps at 114 columns and is unwrapped at
115. The estimate was wrong by fifteen columns, and every conclusion drawn from it
changes:

- `100`, the only width any suite samples between 80 and 120, was believed to sit
  near the boundary. It does not — it is well inside the WRAPPING region, and
  samples the same side as the 80 floor.
- **No suite samples the unwrapped side below 120 at all**, and the true boundary
  had never been observed by anything.
- The canonical 120 clears the transition by SIX COLUMNS. That margin was invisible
  while the transition was believed to be at 100, where it looked like twenty.
  Any growth in the widest summary line pushes the transition past 120 and breaks
  the 120-column case in every suite at once.

That last point inverts the priority: the content-side wrapping row is not a
tidy-up behind a landed layout fix, it is the thing holding a six-column margin.

**How the measurement became possible, because three attempts across two lanes
failed first.** A standalone driver over the real fixtures dies with
`RuntimeError: profile custody infrastructure has not been composed`, and wrapping
it in `isolated_runtime_profile` does not help — the missing piece is the
session-scoped autouse fixture `compose_runtime_ports` in `src/cadrumo/conftest.py:147`,
which enters a large stack of port bindings.

The fix is neither to reconstruct that stack (which would duplicate it, and it
would drift) nor to write a throwaway test into `src/` (which a peer's sweep can
capture in a shared worktree). **Drive the fixture's own generator:** take
`compose_runtime_ports.__wrapped__` to unwrap the pytest decorator, call it,
`next(...)` to enter the composition, and `next(...)` again in a `finally` to
unwind. The real composition runs, nothing is duplicated, and no file enters the
tree.

**How:** a constant that gates behaviour is worth bisecting rather than
interpolating. Two endpoints and a straight line is a guess about a step function,
and the quantity that actually matters — the MARGIN between the transition and the
nearest sampled size — is precisely what an interpolation gets wrong.

### a-bisection-presumes-one-step-and-silently-reports-the-last | high | the same constant was estimated, then bisected, then swept, and each method found a different truth while looking equally definitive

One quantity — the width at which a summary panel's lines wrap — was measured
three times by three methods in one session. Each result looked complete. Two
were wrong in ways their own output could not reveal.

**Method 1, two endpoints and interpolation.** 8 rows at 80 columns, 6 at 120;
reported as "~100 columns", correctly labelled an estimate. Wrong by fifteen.

**Method 2, bisection.** Predicate `virtual_height > 6`, bisected 80..120, giving
114/115. Reported as "the transition". **A bisection presumes a monotonic SINGLE
step.** The predicate `> 6` asks only "is anything wrapping", so it necessarily
returns the LAST boundary, and nothing in a bisection's output indicates whether
earlier steps exist. It is not that the answer was wrong — 114/115 is exactly
right for the question encoded — it is that the question encoded was narrower
than the question asked, and the result does not say so.

**Method 3, a sweep across the range.** The real shape:

| width | summary rows | |
|---|---|---|
| 60, 70 | 10 | below the supported floor |
| **80**, 87, 90 | **8** | two lines wrapping, at the 80x24 floor |
| 95, 100, 110, 114 | 7 | one line wrapping |
| 115, 120 | 6 | none wrapping |

Three steps, two of them inside the supported range: one between 90 and 95, one
at 114/115.

**The consequence was a mis-scoped remediation row.** The row treating the widest
summary line was justified on the belief that one line wraps. Two do at the floor,
so treating that line alone takes 80 columns from 8 rows to 7 — not to 6. The row
would have been closed on a real improvement that did not reach its actual
objective, and its own success criterion would have been met.

**The pattern across all three:** each method answered exactly what it was asked,
and the error each time was in the question rather than the execution.
Interpolation assumed linearity; bisection assumed one step; only the sweep
assumed nothing about the shape. **Where the SHAPE of a relationship is unknown,
sample the range before narrowing on a boundary** — a sweep is a handful of extra
points and it is the only one of the three that can discover it has found more
than it went looking for.

Note also what did NOT catch these: the estimate was labelled as an estimate, and
that label prevented nothing. What caught each error was the next, less assuming
measurement — which happened only because the number was load-bearing for a
sequencing decision. Cheap to measure when something depends on it, and nothing
prompts it when nothing does. See
`a-discrepancy-prompts-the-check-but-is-not-the-check` above.

### the-nested-scroll-check-cannot-see-a-scrolling-static | medium | both the fix's author and its reviewer credited a CLEAN reading to luck, when the check structurally could not have fired

`geometry_band`'s third property counts **multiple visible vertical scroll
owners**, filtered as `isinstance(host, ScrollableContainer) and host.display and
host.show_vertical_scrollbar` (`devtools/frame.py:145-153`).

A layout fix added `overflow-y: auto` to `#modelo-review-summary` inside the
body's `ContentScroll`. Its author flagged this as exactly the shape that check
exists to catch, reported CLEAN, and concluded the fix was "verified by luck of
construction, not by design". The reviewer accepted that framing and recorded it.

**Both were wrong, in the same direction.** `#modelo-review-summary` is a
`Static`, not a `ScrollableContainer`, so the filter excludes it unconditionally.
The check could never have fired for that widget, whatever its overflow styling.
The CLEAN reading was STRUCTURAL, not lucky.

Measured at 80x24 after the fix: `type=Static`, `isinstance(ScrollableContainer)=False`,
`region.height=9`, `virtual_size.height=8`, `max_scroll_y=3`. Content 8 inside a
bound of 9, so nothing is clipped and the fix is sound on its own terms.

**The finding is the gap this exposes.** A `Static` carrying `overflow-y` can
scroll (`allow_vertical_scroll=True`, non-zero `max_scroll_y`) while being
invisible to the check that governs scroll owners. So the property "exactly one
thing in this screen scrolls vertically" is enforced for containers and
unenforced for styled statics — and an author who adds `overflow-y` to a static
will reasonably believe the gate covers it, because the gate's own name and
docstring say it does.

**Discovered by an INVALID bite proof.** An attempt to red the gate by forcing
`show_vertical_scrollbar` on that static returned CLEAN, which read at first as
"the gate does not bite". Reading the filter showed the injection targeted a
widget the check cannot apply to. A second injection against a property the check
DOES cover — widening the header to 200 columns on an 80-column screen — produced
`painted past the side edges: Static#modelo-review-header`, so the gate bites and
is proven.

A failed bite proof has two explanations — the gate is inert, or the injection is
outside its reach — and they are indistinguishable from the result alone. **Read
the predicate before concluding a gate is dead**, and prefer an injection whose
match against the predicate you have actually confirmed.

### a-property-gated-only-where-its-defect-was-found | high | the single-scroll-owner property was tested for one surface of nine, by a test built around the one instance anyone had hit

A correction to `the-geometry-harness-has-no-caller-and-the-modelo-screens-have-no-geometry-gate`
above, which framed the single-visible-vertical-scroll-owner property as
ungated. It was gated — once.

`test_a_flow_surface_has_exactly_one_visible_vertical_scroll_owner`
(`entrypoints/tui/tests/test_visual_verification.py:759`) asserts exactly that
property, for the FLOW surface only, using a bespoke `_many_page_flow` fixture
built to reproduce the case where the defect was originally found. Eight other
enrolled surfaces asserted nothing about it.

**That is a more interesting failure than an unwritten test.** Somebody
recognised the property, understood it well enough to name it in a test title,
and built a fixture to prove it — then scoped it to the instance in front of
them. The test is correct, well-named and passing. A reader searching for
whether the property is covered finds it and stops.

The generalisation is the hazard: **a gate written at the site of a defect
inherits that defect's scope**, and its name usually does not say so. The title
here is honest — it says "a flow surface" — and the honesty still did not
prevent the gap, because a property proven somewhere reads as a property proven.

The consequence was concrete. A later layout fix on a different surface added
`overflow-y: auto` inside an existing scroll host — the exact shape that test was
written to catch — and nothing fired, because the surface was not the flow
surface.

**How:** when a defect is found, ask whether the property it violates is
UNIVERSAL or local before writing the gate. Where universal, parametrise over
every enrolled surface at the point of writing; the marginal cost is one
parametrisation and it is far cheaper than the second discovery. Where genuinely
local, say so in the docstring, because the next reader's question is "is this
covered" and the answer they need is the scope, not the assertion.

See also `an-enumerated-subject-list-is-a-hardcoded-tally-in-disguise` — the same
property, one level up: there the subject list was hardcoded inside a gate, here
the subject list is the single surface the gate was born on.

### a-fix-introduced-the-defect-its-own-gate-is-named-for | high | bounding a panel created a second visible scrollbar and hid three rows, and both the gate and the reviewer cleared it

Measured on the modelo work review at 80x24, after the height-cap fix:

```
widgets painting a vertical scrollbar: ['modelo-review-body', 'modelo-review-summary']
summary  region.h=9  container.h=5  virtual.h=8   hidden rows = 3
summary  isinstance(ScrollableContainer)=False
```

**Two visible vertical scroll owners on one screen** — exactly what
`geometry_band`'s third check and
`test_a_flow_surface_has_exactly_one_visible_vertical_scroll_owner` exist to
prevent. Neither sees it, because the second owner is a `Static` and the check
filters on `isinstance(host, ScrollableContainer)`.

So the fix did not merely fail to trip the check by good fortune. **It
introduced the defect the check is named for, onto the very screen the gate was
built to protect, and the gate reported CLEAN.**

**A REVIEWER'S ARITHMETIC ERROR CLEARED IT A SECOND TIME.** Reviewing the fix, I
measured `region.height=9` against `virtual_size.height=8` and concluded "content
of 8 inside a bound of 9, nothing is clipped". `region.height` is the OUTER box:
it includes 2 rows of border and 2 of padding. The content box is
`container_size.height=5`. Against a virtual height of 8, **three of the eight
rendered rows are hidden** and reachable only by scrolling a panel nested inside
another scrolling panel.

The author's original instinct — that the pass was luck — was closer to the truth
than the reviewer's correction of it. Both were wrong about the mechanism, in
opposite directions, and the reviewer's version was the one that got recorded,
because a correction from a reviewer carries more weight than the doubt it
overrides.

**Three independent clearances of one live defect:** a gate whose predicate
excludes the widget class, a test scoped to another surface, and a reviewer
reading the wrong box of the box model. Each was individually reasonable. None
of them looked at whether a second scrollbar was actually painted — which is one
query (`walk_children` filtered on `show_vertical_scrollbar`) and answers the
question directly.

**How:** for a containment or fit question, measure `container_size` (the content
box), never `region` — the difference is exactly the chrome, and chrome is what
makes a bound look sufficient when it is not. And where a property has an
observable direct expression, observe it rather than deriving it from geometry:
ask which widgets paint a scrollbar, not whether the arithmetic implies one.

### a-uniform-error-across-a-varied-population-indicts-the-probe | high | a probe run outside the project environment reported 94 findings that did not exist, and its own uniformity was the only tell

A sweep for unswept import sites reported **94 findings**. Every entry read
`No module named 'cadrumo'`. The probe had been run with plain `python` rather
than `uv run --no-sync`, so the package was not importable and the probe was
reporting on nothing. **The real number is 2.**

The same mistake occurred independently twice more in one session: once by
another agent whose first standalone probe died the same way, and once by the
same author earlier, whose stale-path stripper reported 75 modules / 123 sites
against a true 16 / 9.

**The tell is uniformity.** A genuine sweep across a heterogeneous population
produces varied diagnostics — different missing symbols, different modules,
different failure shapes. An identical error repeated 94 times, for modules like
`cadrumo.core.logging` that plainly exist, describes the PROBE's environment
rather than the population's state.

This sharpens
`a-discrepancy-prompts-the-check-but-is-not-the-check` above. That finding says
inspect members rather than trusting counts. This one says what to look for when
you do: **variance.** A finding list whose entries are all the same is a single
finding about the harness, reported N times, and N is a measure of population
size rather than of defect count.

It is also the most dangerous shape a false positive can take, because volume
reads as severity. 94 findings demands escalation; 94 identical findings is a
misconfigured command. Nothing about the total distinguishes them.

**How:** before reporting a sweep result, group the findings by their message. If
one message accounts for all or nearly all of them, treat the probe as suspect
before treating the tree as broken — and confirm the probe runs in the project
environment (`uv run --no-sync`, never bare `python`) as the first check, since
that single misconfiguration produced all three instances recorded here.

### a-state-produced-by-your-own-instruction-reads-as-someone-elses-failure | high | a row was marked, unmarked on an instruction, then measured and reported as a marking that never happened

Twice in one session, a state created by the reporter's OWN instruction was
measured later and attributed to another agent's failure.

**Instance one.** A relocation was escalated as a peer breaking the atomic-
relocation rule. File timestamps showed it was the reporter's own delegated lane,
executing an instruction issued before a countermand arrived.

**Instance two.** A lane marked a plan row complete and reported `40/86`. A ruling
then arrived saying the row should not close; the lane unchecked it on that
instruction and reported doing so. The ruling's author subsequently measured the
file, found the row open at `39/86`, and reported it as a state change the lane
had claimed but never made — a charge of misreporting, levelled at an agent that
had done exactly as instructed and said so.

**The measurement was accurate both times. The attribution was not.** Nothing in
a file's current state records which instruction produced it, or how many
instructions were in flight when it was written. In a session with many crossing
messages, "the tree does not match the report" has at least three explanations —
the report was wrong, the report was stale, or an instruction between them
changed the tree — and the third is invisible to the measurement.

The asymmetry is what makes this worth recording: **an incorrect accusation costs
more than an incorrect measurement.** A wrong number gets corrected on the next
reading. A charge of misreporting, once made, has to be withdrawn explicitly, and
an agent that has been wrongly accused of over-claiming has a live incentive to
under-claim afterwards — which is the opposite of the reporting behaviour every
other finding in this document depends on.

**How:** before attributing a mismatch to another agent, account for your own
instructions in flight — ask what YOU asked for between their report and your
measurement. Report the mismatch as a mismatch ("the row reads open, my ruling
may explain it") rather than as a failure, and let the other party supply the
history the file cannot. See `shared-worktree-attribution`: the same discipline
that applies to peers applies to your own countermands, and is harder to apply
there because the instruction feels like context rather than a cause.

### a-clean-bite-proof-is-as-uninformative-as-a-uniform-finding-list | high | three consecutive injections returned CLEAN and none of them proved anything, because out-of-reach and inert produce identical output

The companion to
`a-uniform-error-across-a-varied-population-indicts-the-probe` above, and its
exact inverse.

That finding says an all-identical finding list describes the probe rather than
the tree. This one says the same of an EMPTY one. Three consecutive attempts to
red a geometry gate returned CLEAN. In every case the injection was outside the
check's reach rather than the check being inert — a `Static` forced to show a
scrollbar against a predicate filtering on `isinstance(host, ScrollableContainer)`.

**CLEAN means "the gate saw nothing", which is what a working gate and a
mis-aimed injection both produce.** Nothing in the result distinguishes them, and
a bite proof is precisely where CLEAN is most tempting to over-read — it is the
one context where the reader has already decided the gate is the subject, so a
null result reads as a verdict on the gate.

**What resolved it, both times: evaluate BOTH predicates over the same tree and
print what each saw.**

```
painted a scrollbar        : ['host', 'styled']
seen by the old predicate  : ['host']
```

That isolates the CHANGE rather than the surface. It cannot pass for an
unrelated reason, it names the exact population the widening admits, and it is
the only form of proof that distinguishes "the gate now catches this" from "the
gate is running".

**Why this particular defect survived is worth recording separately:** it
requires a `Static` with a MOUNTED CHILD WIDGET plus a height bound. Inline
content never paints a bar. So it was not merely unchecked — it was hard to
stumble into, which is the combination that keeps a defect alive longest: rare
enough that nobody meets it by accident, and invisible to the one check named
for it.

**How:** a bite proof must show the gate's output CHANGING, not merely being
non-empty. Prefer a differential — old predicate versus new, over one tree — to a
single injection, and never accept CLEAN from an injection whose match against
the predicate you have not separately confirmed.

### a-closing-condition-stated-as-a-measured-number-goes-stale-when-you-change-the-thing-measured | high | a row's target transition of 94/95 was invalidated by the same campaign's own layout fix, twice, and hitting it would have meant nothing

A remediation row was given the closing condition *"upper transition measured at
94/95, canonical 120 clearing by 25 columns"* — deliberately expressed as an
outcome rather than an action, to prevent the row closing on effort instead of
effect.

The numbers were derived from a content-width model of `screen − 7`. A later fix
in the SAME campaign replaced a panel with a `Collapsible`, whose toggle indent
changed the model to roughly `screen − 14`. A separate change removed 7 columns
from the widest line. **The two cancelled**, and the measured transition stayed
at 114/115 — so a real 7-column improvement produced no movement at all in the
number the row was to be judged by.

Had the condition been checked without the sweep, the row would have read as
failing while the work succeeded. Had the earlier geometry persisted, it would
have read as passing at a number that no longer meant what it meant when written.

**The defect is in the FORM of the condition.** An absolute measured constant is
a valid target only while everything else holding it still is stable — and in an
active campaign the thing holding it still is precisely what the campaign is
changing. This row's target was invalidated twice in one afternoon by its own
campaign's other rows.

**A structural condition survives what a numeric one cannot.** The real objective
was never "94/95"; it was *"the widest line is no longer the binding constraint
— the irreducible identifier line is"*. That statement is invariant under content
width changes, chrome changes, and font or indent changes, because it names a
RELATIONSHIP between two measured quantities rather than either one's value.

**How:** express a closing condition as a relationship or an ordering where one
exists — which line binds, which value dominates, which of two paths is taken —
and record the absolute measurement beside it as an OBSERVATION with its date and
the geometry it was taken under. The observation is then evidence rather than the
criterion, and its going stale is informative instead of disqualifying.

See `no-plan-step-marked-complete-without-a-matching-exec-record` in
`aeat-agent-orchestration`: an outcome-shaped criterion is the defence against
closing on effort, and a numeric one is how that defence quietly decays.

### every-scope-count-today-undercounted-and-always-downward | high | four independent scope figures were low, never high, because a search finds the shape it was written for

Four scope measurements in one session, each taken carefully, each an undercount:

| reported | actual | what was missed |
|---|---|---|
| 4 types with unpopulated fields | 9 across 5 types | a hand-listed set; an AST walk found the rest |
| 1 dead refusal union member | 2 of 3 | only the member someone had noticed was checked |
| 3 declarations of the terminal size set | **6** | one hid behind a `_GEOMETRIES` alias, invisible to a literal-shape search |
| 1 wrapping line at the 80-column floor | 2 | a two-endpoint measurement cannot see a second step |

**Never once in the other direction.** No scope figure today was too large. That
asymmetry is structural rather than coincidental: a search returns instances of
the shape it encodes, so anything expressed differently — aliased, computed,
spelled another way, or of a kind the searcher had not conceived — is absent from
the result with no signal that it was excluded. A search cannot report what it
could not have matched.

The alias case is the cleanest instance. Five declarations were inline literals
and were found; the sixth was bound to a `_GEOMETRIES` name, and a search for the
literal shape returned five with no indication a sixth existed. The count was
wrong and looked complete, and the same search re-run would confirm it forever.

**The consequence is not merely a wrong number.** Every one of these figures was
used to size a remediation: how many types to fix, whether a defect was isolated,
how many suites to sweep, whether one line or two needed shortening. An
undercount makes a row look smaller than it is, so it is scheduled as smaller,
and then closes having done less than its own text describes.

**How:** for any scope count that will size a decision, search by MEANING as well
as by shape — semantic search finds an aliased or restructured declaration that a
literal pattern cannot — and prefer a structural walk (AST, live object graph,
loaded snapshot) over a text search wherever one exists. Where only a text search
is available, state the pattern used beside the count, so a later reader can see
what it could not have matched. And treat a scope figure as a LOWER BOUND until
something other than the original search has confirmed it.

Related: `a-discrepancy-prompts-the-check-but-is-not-the-check`,
`an-enumerated-subject-list-is-a-hardcoded-tally-in-disguise`,
`a-bisection-presumes-one-step-and-silently-reports-the-last`.

### four-more-frame-readers-are-in-the-state-the-gated-one-was | high | one of five band readers is now gated; the other four are implemented, exported, and driven by nothing but a name-only export assertion

After gating `geometry_band`, the same measurement was applied to its siblings in
`entrypoints/tui/devtools/frame.py`. Each reads a distinct band off a live app:

| reader | external references | what they are |
|---|---|---|
| `geometry_band` | gated | now driven per surface per size |
| `engine_band` | 1 | name-only tuple in an export assertion |
| `focus_band` | 1 | name-only tuple in an export assertion |
| `key_band` | 1 | name-only tuple in an export assertion |
| `screen_text` | 1 | name-only tuple in an export assertion |

The single reference in each case is the same line — a tuple of expected export
names in `dev/tests/test_public_devtool_homes.py`. It asserts the symbols are
exported. It never executes them.

So `capture()` assembles five bands, one of which is now proven per surface and
four of which are proven to exist. Focus order, key bindings, engine state and
rendered text are read by working, documented code that no gate drives — the
exact state `geometry_band` was in when a layout defect it was written to catch
reached the tree unnoticed.

**This is the dead-capacity shape at its most deceptive**, per
`the-geometry-harness-has-no-caller...` above: an unused-symbol sweep clears all
four, because each IS referenced. The reference simply proves nothing about
behaviour.

**The remediation is known and cheap**, because the pattern was built for the
fifth: a parametrised test driving the reader over every enrolled surface at
every declared size, plus a bite proof showing the OUTPUT CHANGE rather than a
non-empty result. Four bands, one established shape.

**Found by a probe that first returned all-zero.** A count of CALL sites (`name(`)
reported zero callers for every devtools symbol, including one demonstrably used
as `register=registration_attempt` — a REFERENCE, not a call. The uniform zero was
the tell, per `a-uniform-error-across-a-varied-population-indicts-the-probe`, and
re-counting on any occurrence gave the real figures above. Third instance today
of a search missing what its pattern could not match.

### re-run-the-detector-after-the-sweep | high | the control for an undercount is not a better search, because you cannot search for the shape you failed to imagine

`every-scope-count-today-undercounted-and-always-downward` above diagnoses the
problem: a search returns instances of the shape it encodes, so an aliased,
computed or differently-spelled instance is absent with no signal it was
excluded. Its remedy — search by meaning as well as shape, prefer a structural
walk — helps but still depends on anticipating the miss.

**A control that does not require anticipating it:** after completing a sweep,
RE-RUN THE ORIGINAL DETECTOR. Whatever still matches was invisible to the
original enumeration.

This is how the sixth terminal-size declaration was actually found. Five inline
literals were enumerated and swept; re-running the detector afterwards still
matched, and the survivor was a set bound to a `_GEOMETRIES` alias that the
literal-shape search had never returned. No better query found it — the
remediation was the confirming instrument.

It works because it inverts the epistemics. A search asks "what matches my
pattern", and cannot report what the pattern could not match. Re-running after a
sweep asks "what still matches after I removed everything I knew about" — and any
survivor is, by construction, something the original enumeration did not contain.
The sweep converts an unknown unknown into a residual.

**Two conditions make it valid.** The detector must be unchanged between runs —
refining it invalidates the comparison. And the sweep must genuinely remove each
swept instance rather than exempt it, or survivors are indistinguishable from
allowlisted entries.

**How:** treat a sweep as producing two artefacts — the change, and a re-run of
the detector over the changed tree. A clean re-run is the completeness evidence
the original count could never supply; a dirty one names precisely the instances
the enumeration missed. Record both. Where a sweep closes a row claiming to have
handled N instances, the re-run is what distinguishes "N was the population" from
"N was what the search could see".

### a-rationale-that-enumerates-instances-goes-stale-as-the-population-grows | high | a correctly-reasoned exclusion list stayed correct about what it named and silently wrong about what appeared afterwards

`_INTERACTIVE_SURFACES` in `entrypoints/tui/tests/test_visual_verification.py`
selects the surfaces whose tab cycle is gated. Its docstring is a model of the
kind usually asked for: it names its exclusions and gives a reason for each —
`status` is read-only chrome with no operator input, `question` is driven by the
flow engine's paged navigation rather than a plain tab cycle.

**Both reasons are still true.** Neither has decayed. The list is nonetheless
wrong, because the enrolled surface set grew from four to nine and the
enumeration did not:

```
in set     registration 5   form 3   manager 28   login 4     focusables
excluded   status 1   status-populated 1   question 4         rationale covers
excluded   manager-populated 28   modelo-review 3             rationale does NOT
```

`status-populated` inherits `status`'s reason by construction. `manager-populated`
carries 28 focusable controls — identical to `manager`, which IS in the set — and
was never added when the populated variants appeared. `modelo-review` was
enrolled hours ago. So focus order is unproven on two surfaces that the stated
rationale never excluded and never mentions.

**The mechanism is distinct from the other undercounts in this document.** Those
were searches that could not match a shape. This is a rationale that was COMPLETE
WHEN WRITTEN and became partial without any edit, any failure, or any signal.
Nothing changed about the constant; the world around it changed. A reader
checking it finds named exclusions with sound reasons and stops — the quality of
the rationale is what makes it persuasive, and being persuasive is what makes it
dangerous.

**The fix is in the FORM of the rationale, not its content:** state the
PREDICATE, not the instances that satisfied it when written. "Surfaces with a
real tab cycle; read-only chrome and engine-paged navigation are excluded" is
checkable against any surface that appears later. "`status` and `question` are
excluded because..." is checkable only against `status` and `question`.

This is the same form change as
`a-closing-condition-stated-as-a-measured-number-goes-stale-when-you-change-the-thing-measured`
above — a relationship survives what an enumeration cannot — applied to a
rationale rather than a criterion. Both fail silently, both look rigorous, and
both are repaired by naming the rule instead of listing what currently satisfies
it.

**How:** where a subset carries a rationale, write the membership PREDICATE.
Where the predicate cannot be stated, that is evidence the subset is incidental
rather than principled, and worth knowing.

### an-executor-refused-an-instruction-that-violated-a-standing-mandate | high | the lead specified putting a plan Step id in shipped test source, which is the violation another row exists to remove

A gate was deliberately left red, and the lead required the assertion message to
name the plan row carrying the defect — so a peer sweeping a red tree would read
an instruction not to green it the easy way.

**That instruction violated `vaultspec-system`'s Code Stands Alone mandate:**
source must never reference `.vault/` document stems or Step ids. It is the exact
violation `W05.P23.S322` exists to remove, and which the same executor had swept
from 17 sites earlier the same day.

The executor did not comply and did not simply refuse. It **achieved the stated
intent in domain terms**, which is the harder and better outcome: the assertion
now states the defect and carries the instruction — *"DO NOT RESOLVE THIS BY
REMOVING THIS SURFACE FROM THE INTERACTIVE PREDICATE: the predicate is correct
and the surface does have a tab cycle to prove"* — without citing any document.
A peer reads the instruction; no vault identifier enters shipped source.

**Two things are worth separating here.** The lead's INTENT was sound: a
deliberate red needs to defend itself against the smallest greening change. The
lead's MECHANISM was prohibited. An executor that had complied would have
produced a correct-looking gate carrying a mandate violation, authorised from
above, in the same session and by the same agent that had just removed 17 of
them.

**The general point:** a delegating agent's instructions are not exempt from the
project's standing rules, and the executor is frequently better placed to notice
— it holds the local context the lead is compressing away, and it had personally
swept this exact violation hours earlier. An instruction that conflicts with a
mandate should be met with the intent satisfied by other means, not with
compliance and not with a bare refusal.

**Postscript, and the same trap twice:** verifying the file was clean, a search
for step-id-shaped tokens returned one hit — `# noqa: S105`, a ruff rule code, not
a Step id. That is precisely the collision documented in
`one-sweep-addressed-from-two-plans-double-counts-its-own-remainder` above, where
a stripper counted `S105`/`S106` suppressions as campaign identifiers. The
verifier walked into the trap the audit already records, which is its own
evidence for how narrow the tell is.

### two-readings-of-one-property-disagreed-and-only-one-was-run | high | a root cause was derived, reported and retracted because membership was tested by two methods that were never compared

Investigating why `tab` did not move focus on a screen, `active_bindings` was
read two ways in two scripts:

```python
keys = [b.key for (_ns, b, _e, _t) in screen.active_bindings.values()]   # -> no "tab"
"tab" in screen.active_bindings                                          # -> True
```

The first was run and reported. The second was not run until later. They
disagree, and the second is correct: the binding is present, inherited, in the
modal binding chain, enabled, with `_check_action_state` returning True.

**A complete root cause was built on the first reading** — that Textual's
`Screen.BINDINGS` were not being merged, evidenced by `shift+tab`'s absence,
which has exactly one source and therefore looked like proof. It was reported to
another agent as settled, with a remediation and a suggested tree-wide sweep
keyed to that tell. Every element of it was false, and it was retracted before
being acted on only because the property was re-measured by the other method.

**The failure is not the wrong reading. It is that two ways of asking the same
question existed and were never compared.** There was no reason to expect them to
differ, which is exactly why the cross-check felt unnecessary — and a
cross-check that feels necessary is one you were already going to run.

This is the same discipline recorded in
`a-clean-bite-proof-is-as-uninformative-as-a-uniform-finding-list` above
("evaluate both predicates over the same tree and print what each saw"), applied
there to gate injections and NOT applied here to a measurement about to be handed
on as fact. A method established for one context did not transfer to another by
itself.

**What survives is the inventory**, and it is worth more than the false cause:
binding inheritance, declaration shape, `_inherit_bindings` and `check_action`
are all confirmed fine; a bare-app repro of the exact widget structure
(`ScrollableContainer > Vertical > two collapsed Collapsibles > Static >
DataTable`) tabs correctly, and so does the same repro with the project's own
`ContentScroll` and `ContentDataTable` substituted. So the defect is in key
DISPATCH, not binding resolution — a present, enabled binding whose keypress does
not invoke an action that works when called directly.

**How:** where a property can be queried more than one way, query it both ways
BEFORE reporting — especially when reporting to someone who will act on it. And
treat a single elegant tell (`shift+tab` has one source, so its absence proves
the merge failed) with more suspicion than a clumsy one: the elegance is what
stops the second check being run.

### a-retraction-is-timestamped-exactly-like-the-claim-it-withdraws | high | a correct root cause was withdrawn as an error because it was re-measured after someone fixed it

A screen's `tab` key did not move focus. The cause was diagnosed as Textual's
inherited `Screen.BINDINGS` not being present, evidenced by `shift+tab`'s absence
— a key with exactly one source. It was reported to another agent as settled.

Re-measuring an hour later showed `tab` present, inherited, enabled, and the
focus cycle working. **The finding was retracted as a mistake**, with a
methodological post-mortem attached: two ways of reading `active_bindings` had
disagreed and only one had been run.

**The retraction was wrong.** `HEAD` at `work_review.py:273` contains:

```python
self._bindings = BindingsMap(Binding("q", ...), Binding("escape", ...), Binding("f3", ...))
self.refresh_bindings()
```

A wholesale runtime replacement of the screen's binding map, discarding every
inherited entry — `tab`, `shift+tab`, and Screen's copy binding. Exactly the
reported cause. **The receiving agent had acted on the diagnosis and fixed all
four sites** — `work_review.py`, `flows/app.py` twice, `profile/status.py` —
between the diagnosis and the re-measurement. The re-measurement was accurate
about a tree that had been repaired in response to the very finding being
retracted.

**The two-readings flaw was real and was not what produced the disagreement.**
That is the trap, and it is sharper than "check the timestamp": a genuine
methodological error was available as an explanation, it FIT, and adopting it
ended the search. **A wrong explanation that fits is more dangerous than no
explanation**, because no explanation leaves you still looking. Having a
credible fault of your own to blame is the most effective way to stop
investigating.

**Retracting feels like the careful move, which is precisely why it escapes
scrutiny.** Asserting a finding invites challenge; withdrawing one reads as
humility and rigour, so nobody — including the author — asks for evidence. This
document's own rule, that a refutation is timestamped exactly like the claim it
refutes, had been written for three other agents on the same day by the agent who
then failed it here.

**How:** before withdrawing a finding, check whether the SUBJECT changed between
the original measurement and the re-measurement — file mtimes, a diff against
HEAD, the working-tree state. In an active shared tree that check costs one
command. Be most suspicious when you have a plausible fault of your own to
assign: verify the timing FIRST, and only then decide whether the methodological
flaw also needs recording on its own merits. And apply the same standard to a
retraction as to an assertion — what was measured, when, against which tree.

**Outcome:** the defect was fixed across all four sites, and a gate now asserts
that every enrolled surface retains the keys `Screen.BINDINGS` guarantees,
derived from Textual rather than hardcoded, over all nine surfaces rather than
only the focus-enrolled subset. The remaining generalisation is greppable: any
screen assigning `_bindings` wholesale silently loses `tab`, `shift+tab` and
copy.

### the-host-load-stamp-invalidates-a-measurement-and-was-printed-in-the-log-being-read | high | a hang was nearly attributed as a real defect three times, and the line refuting each attempt was in the same output

Two tests in `entrypoints/tui/operations/tests/test_operation_modal_lifecycle.py`
time out. Three attempts to attribute it, each refuted by a line already in the
captured log:

1. Reported as possibly-mine by its lane, correctly labelled **UNATTRIBUTED**,
   noting the runs were taken while the host carried ~50 concurrent python
   processes.
2. Re-run with `-n 0` and read as "reproduces single-process at low load". The
   log's own stamp read `python_processes=52, processes=719`. **`-n 0` controls
   the run's workers, not the host.** The reader was about to upgrade
   UNATTRIBUTED to confirmed on evidence that said the opposite.
3. Re-run with `--timeout=150` to separate HUNG from SLOW-UNDER-LOAD. It timed
   out — at `cpu=100.0%`, `python_processes=78`. A saturated host cannot
   distinguish the two, so the discriminator discriminated nothing.

**The instrumentation worked perfectly and was the thing being overlooked.** A
`CADRUMO-HOST-LOAD` line is emitted per test carrying cpu, memory, total
processes and python processes. It stated in every run that the environment was
unfit for the conclusion being drawn. Its presence is the reason each attempt
could be caught — and its being ignored twice is the reason each was made.

This is the environmental counterpart to every provenance finding in this
document. Those ask *what grade of evidence is this, and when was it taken.* This
adds: *what was the machine doing while it was taken.* A red under saturation and
a red under quiet are the same text.

**The correct disposition is a blocked row, not a finding.** Attribution requires
a quiet host, which is the same precondition two other rows already carry for
unrelated reasons. Investigating now spends effort on a measurement that cannot
support a conclusion either way, and the likeliest outcome is a confident wrong
attribution — the failure this document records nine times.

**How:** read the load stamp before reading the result. Where a suite emits one,
quote it beside any timing-derived or flake-derived claim. And treat "I disabled
parallelism" as controlling YOUR process only — in a shared host with other agents
running suites, the machine is the shared resource, not the test runner.

### a-filter-that-cannot-match-produces-a-plausible-number | medium | `grep -h` suppressed the filenames a `/tests/` exclusion needed, turning a 4-site production finding into a 58-site alarm

A sweep for tax-amount rounding counted call shapes with:

```sh
grep -rhoE 'quantize\([^)]*\)' --include=*.py src/cadrumo | grep -v "/tests/"
```

`-h` suppresses filenames, so the downstream `grep -v "/tests/"` had no path to
match against and excluded nothing. The result — **58** bare
`quantize(Decimal("0.01"))` sites — was reported internally as a possible
rounding-mode defect across production tax code, on the reasoning that Python's
default is banker's rounding while AEAT expects half-up.

**The real production figure is 4**, and all four are non-tax: two run-health
diagnostics, one telemetry mean, one percentage-change projection. No filed
amount is affected. The tax paths use explicit `ROUND_HALF_UP` (37 occurrences).
The formula engine's `localcontext()` sets `prec = 28` and no rounding, which
affects only the 28th significant digit and is immaterial for money.

**The failure is a filter that was structurally incapable of filtering, in a
pipeline that ran without error and produced a believable number.** 58 is not
absurd for a codebase this size — it did not trip the implausible-magnitude tell
that caught the 75/123 and 94-findings cases. What caught it was listing the
MEMBERS: the file list showed three directories, which cannot hold 58 sites.

This is a third distinct form of the same family. A search cannot report what its
pattern could not match; a uniform result describes the probe; and now: **a
filter downstream of a flag that removes its input silently passes everything.**
All three produce output that looks like a measurement.

**How:** when a pipeline filters on a field, confirm the field is present in the
input — `-h`, `-o` and `--only-matching` all strip the context a later stage may
need. And the general remedy already recorded applies unchanged: list the members
before reporting the count, as routine rather than on suspicion. Here the members
were three directory names and the discrepancy was immediate.

**The sweep itself found nothing**, which is a legitimate and reportable outcome:
rounding mode is explicit on every tax-facing path checked.

### assigning-a-private-name-a-framework-base-already-uses-hangs-instead-of-erroring | high | one attribute name collided with Textual's own shutdown flag; the symptom was a test hanging forever, with nothing to grep for

`OperationModal.__init__` set `self._closing = False` to track whether its
observation poll should stop. **`_closing` is Textual's own flag on
`MessagePump`**, assigned inside `MessagePump.__init__` — so it exists only at
runtime, is invisible to `dir()` on the class, and no editor or type checker
flags the collision.

Setting it True to stop the poll made the subsequent real close take
`MessagePump._close_messages`'s already-closing early return WITHOUT posting its
stop sentinel. The pump never ended; `Screen.remove` waited on it, `App._shutdown`
waited on that, and the test harness's `__aexit__` waited forever.

**The symptom carries no signal.** Not an exception, not a wrong value — a
process that stops. Nothing to grep for, no stack frame in the offending file,
and the file that names the flag is three layers from where the wait happens.
Confirmed by a pending-task dump at the hang: `_closing=True`, `_closed=False`,
an EMPTY message queue and NO workers, with the screen pop parked in
`_replace_screen`.

**Pre-existing at HEAD** (three sites), not introduced by the surrounding
async-lock work — though a later change did route a second close path through the
same flag, widening its reach without creating it.

**The gate derives its reserved surface rather than listing it:** an AST walk
over the `__init__` bodies of the textual-owned ancestors in each node class's
MRO, collecting every private name they assign. Hardcoding was not available,
precisely because these names exist only at runtime — the property that made the
defect invisible is the same one that forces the gate to be derived. Public names
are excluded deliberately: a census found `title`/`sub_title` set on four
screens, and those are reactives Textual intends a screen to set, so including
them would have produced four false reds. An anchor assertion names one known
Textual private, so a framework refactor reds the gate loudly instead of silently
emptying its reserved set.

Bite-proven against the REAL pre-fix source — the detector fed the actual HEAD
text of the offending class read from git, not a synthetic stand-in. Pre-fix
`['_closing']`, post-fix `[]`. The file went from two hangs to 7 passed in 26s.

**A method note the fix depended on, and a fourth member of this document's
silent-instrument family.** The first instrumentation attempt located the hang in
the wrong place: Textual captures stdout inside its test harness, so printed
progress marks simply stop appearing — **indistinguishable from the program
stopping**. That produced a confident wrong conclusion (that the event loop was
dead) which measurement later refuted. Write probe marks to a FILE when the
framework under test owns the output stream.

That joins `a-uniform-error-across-a-varied-population-indicts-the-probe`,
`a-clean-bite-proof-is-as-uninformative-as-a-uniform-finding-list`, and
`a-filter-that-cannot-match-produces-a-plausible-number`: four distinct ways an
instrument failed silently and its silence was read as data.

### ship-the-stricter-assertion-and-let-it-fail | medium | reasoning about a gate's correct scope cost more than running the wrong one, twice in one evening

A gate was specified to assert that every screen retains the affordances Textual
gives it. The specification said assert the inherited ACTIONS. The executor
shipped exactly that, ran it, and three surfaces went red — not defects: a focused
`Input` legitimately owns the copy key when a text cursor is present, so the
action offered is `Input.copy` rather than `screen.copy_text`.

**The gate reported that the specification was wrong.** Restated over KEYS — the
operator keeps the affordance, whoever answers it — it is correct and green.

The same evening, a hang investigation ran the same way: instrumenting and
reading the state settled in minutes what had survived three rounds of
reasoning about contention.

**The asymmetry is what makes this a rule rather than an anecdote.** A red from a
real gate is cheap and reversible — it costs one run and names the exact
surfaces that disagree with your assumption. A wrongly-scoped gate that PASSES is
neither: it is silent, it looks like coverage, and it is only discovered when the
defect it was supposed to catch ships. So when the correct scope of an assertion
is genuinely uncertain, the stricter version is the cheaper experiment, and its
failures are data rather than rework.

This inverts the usual instinct, which is to reason the scope out in advance and
ship the version you are confident in. That instinct optimises for not seeing a
red, and a red is the least expensive thing in the exchange.

**Conditions.** The stricter version must be RUN, not merely written — the whole
value is in the failure list. And the failures must be adjudicated rather than
assumed wrong: three false reds here were false because a real widget legitimately
owns the key, which required reading why each surface disagreed. A red that is
waved away as noise teaches nothing, and a red that is accommodated by weakening
the gate teaches worse than nothing — see
`remediation-must-precede-the-gate-that-would-catch-it`.

Related: `a-property-gated-only-where-its-defect-was-found` — the same preference
for letting the broader assertion tell you where it does not hold, rather than
narrowing it pre-emptively to the case in hand.

### a-crashed-worker-silently-drops-tests-and-reports-a-clean-total | high | a run of a five-test file reported "1 failed, 2 passed" and nothing anywhere said the other two never executed

Running a five-test module under the parallel runner with a thread-method
timeout, the summary read:

```
[gw0] node down: Not properly terminated
worker 'gw0' crashed while running ...::test_wrong_recovery_reentry_publishes_no_capsule
1 failed, 2 passed in 101.54s
```

The file contains **five** tests. Three are accounted for. **Two never ran, and
the summary does not say so** — it presents "1 failed, 2 passed" in the same shape
it would use for a complete run. The dropped tests appear nowhere: not as errors,
not as skips, not as a count mismatch.

The mechanism: a thread-method timeout kills the worker PROCESS rather than
raising inside the test, so the worker dies before reporting, and the remaining
tests assigned to it are simply never distributed.

**Every red-log reading in this tree is affected.** A reader triaging failures
takes the FAILED list as the set of things wrong. Where a worker crashed, that
list is a subset of unknown size, and the total looks plausible because the
arithmetic is internally consistent — 1 + 2 = 3, and nothing states that 5 were
collected. This is the direct cause of the vague failure counts recorded
elsewhere on this branch.

It is also the sharpest instance in this document of an instrument failing
silently: not a wrong number, but a MISSING population reported at full
confidence. Compare `a-uniform-error-across-a-varied-population-indicts-the-probe`
and `a-filter-that-cannot-match-produces-a-plausible-number` — in both, output
existed to inspect. Here the evidence of loss is absent by construction.

**How:** compare COLLECTED against REPORTED on any run used to draw a conclusion.
`--collect-only -q` gives the denominator; the summary gives the numerator; a
mismatch means tests were dropped. Treat any run containing `node down` or
`worker ... crashed` as having an unknown-size hole, and re-run the affected file
serially before reading its failures. A gate asserting collected-equals-reported
would make the hole visible without anyone remembering to look, and is the
natural remedy — the count is available on both sides.

**Do not read a suite total as a completeness claim.** It is an arithmetic
summary of what was reported back, and a process that dies reports nothing.

### a-remediation-line-that-reproduces-the-failure-it-explains | medium | an honest, correct warning ended with advice that recreated the exact state it was warning about

Running a unit-marked module with `-m integration` selects nothing. The harness
detects this and says so clearly — `NOTHING RAN`, `A green result here means the
selection matched nothing, NOT that the code is sound` — which is exactly the
banner this project built to stop a zero-match run reading as a pass.

Its last line read:

> re-run with -m integration (or `just test-integration`)

**The operator had just run `-m integration`.** Following the instruction
reproduces the identical empty selection. The diagnosis was right, the severity
was right, and the one actionable sentence sent the reader in a circle.

The advice was hardcoded, so it was correct for the case its author had in mind —
an operator on the default unit lane, for whom `-m integration` is the right next
step — and silently wrong for the case where the reader has already chosen that
lane, which is precisely the case where a targeted run surprises someone.

**Fixed** by deriving the advice from the selector actually used: when the
selected lane is already the one that would otherwise be suggested, point at
`-m ''`, which cannot be empty for a module that collected anything at all.

**The proof for a remediation fix is to FOLLOW THE ADVICE**, not to read it. The
new line was executed: 8 tests ran where the old advice had produced another
zero. A remediation that is merely different from the failing command is not
verified; one that has been run and resolved the state is.

**How:** treat every actionable line in an error as code that will be executed by
someone in the state that produced the error. Ask what happens if the reader is
ALREADY doing what you are about to suggest — hardcoded advice is correct for the
author's imagined reader and wrong for anyone who arrived by a different route.
The same shape as `a-rationale-that-enumerates-instances-goes-stale-as-the-population-grows`:
a statement true of the case in front of the author, silently false for the
others.

### a-probe-that-perturbs-its-subject-produces-state-evidence-that-outranks-the-truth | high | three instrumentation attempts each changed the behaviour under test, and one of them silently disabled the very send it was measuring

An intermittent hang was to be attributed by separating STATE questions ("does
the send ever fire") from TIMING questions ("does it fire late"), on the sound
reasoning that a code path which never executes does not execute faster on an
idle machine. The state question was instrumented three times. All three answers
were artifacts.

**Probe 1** wrapped the screen's `__init__` to log its callbacks. The trace read
cleanly: screen constructed, neither confirm nor cancel nor the refusal path ever
fires, test hangs. That is a textbook state observation — load-independent,
specific, and apparently decisive. The control run immediately afterwards, same
session, no plugin: **5 passed**. The probe was the cause.

**Probe 2 manufactured the defect it was looking for.** It wrapped the confirm
handler, which is decorated with Textual's `@on(Button.Pressed, ...)`. Replacing
that attribute DETACHES the handler from the framework's registry, so the button
genuinely stops working and the wait becomes genuinely infinite — a probe for
"does the send fire" that silently prevented the send.

**Probe 3** touched only undecorated methods and hung at a different point again,
control still green.

**A state claim is more dangerous than a timing claim when it is wrong.** The
whole argument for preferring state evidence is that a busy host cannot fake it —
which is true, and which is exactly why a state claim arrives with more authority
and invites less challenge. An instrument that alters its subject produces
evidence wearing that authority. Reported before the control ran, probe 1's trace
would have closed the question wrongly and been harder to reopen than the timing
claim it replaced.

**Two concrete rules, both earned here:** never monkeypatch a decorated event
handler or a framework node's constructor — the decoration is registration, and
replacing the attribute deregisters it. And run the CONTROL in the same session
as the probe, not from memory of an earlier run, because on an intermittent
phenomenon a remembered green is not a control.

**What the accidents did establish** is worth more than what they were looking
for: there is a reachable state — screen pushed, confirm handler inert, app still
running, screen never unmounting — in which the worker waits forever with no
error and no diagnostic, because every existing guard keys on unmount or
app-stop. The escapes cover "the producer is gone"; the uncovered case is **"the
producer is present but inert"**. Three probes reached that state by accident,
which also means it can be induced deliberately — so it has a testable subject
even though the original hang does not.

### a-gate-that-imports-the-tree-it-guards-cannot-run-when-that-tree-is-broken | high | the parse gate reused the project's canonical scanner and was therefore unimportable in exactly the state it exists to detect

The syntax gate was written to reuse `_project_inventory._python_files`, which
wraps the project's canonical `scan_directory`. Reuse over re-implementation is
the correct instinct and the rule this campaign has applied all day.

**It made the gate useless in the only state that matters.** While an in-flight
peer sweep left `core/redaction/__init__.py` unparseable, importing the gate
failed:

```
dev.tests.test_every_source_file_parses
  -> cadrumo.core.directory_scan -> cadrumo.core.errors._registry
  -> cadrumo.core.redaction -> IndentationError
```

A gate whose own import traverses the package cannot report on a package that
cannot be imported. The reuse that is right everywhere else is wrong here, and
the distinguishing property is narrow: **this gate's subject is the tree's
ability to be parsed at all**, so it must owe that tree nothing.

Rewritten to walk with `os.walk` and the standard library only, with the reason
in its docstring so the next reader does not "fix" it back to the shared helper.
It then ran against the broken tree and reported four offenders.

**And the population moved under the measurement.** Those four were reported at
one moment; three consecutive samples fourteen seconds later returned ZERO. The
sweep producing them was still running and its owner was fixing them as fast as
they appeared.

That amends an earlier finding in this document. `re-run-the-detector-after-the-sweep`
treats serial rediscovery — fix one, re-run, find the next — as evidence the
population was never enumerated. **That inference holds only for a STATIC
population.** Against a live producer, enumeration cannot converge: every list is
stale by the next save, and fixing entries is competing with the thing creating
them. The tell is the same in both cases and the correct action is opposite —
enumerate harder, or stop and let the producer finish.

**How:** distinguish the two before acting. A population that changes between two
consecutive samples is being produced, not merely under-enumerated; the response
is to identify the producer and wait, not to sweep. And run a whole-tree gate at
a SETTLE POINT rather than during a sweep, because during one it reports a
snapshot that was already wrong when printed.

### a-settle-condition-is-the-wrong-gate-on-recording-durable-work | high | a rule written to answer "has this producer stopped" was applied to block a record whose truth did not depend on any producer

A three-part settle condition was agreed for deciding when a tree-wide sweep had
finished: parse clean, no new untracked modules across two checks minutes apart,
no source mtimes inside the last several minutes. It is correct for the question
it was written for.

It was then applied to a different question — may an execution record be written
for a completed gate — and blocked it. That was wrong, for a reason the executor
identified and the author had not:

**In a shared worktree with several active lanes, a globally quiet tree may never
occur.** Waiting for one makes an unrelated lane's activity block an unrelated
record, indefinitely, with no mechanism to end the wait. The condition was
measured settled at one moment and unsettled four minutes later by a DIFFERENT
lane editing unrelated files — not the sweep the condition was written about.

**The fix is to split the claim rather than wait or overstate it.** A record can
state two different kinds of thing:

- properties of the ARTEFACT — the gate is import-independent, the injected cases
  bite, the failure path was itself defective and is fixed, its first real outing
  caught four live offenders. None of these depend on the tree being quiet, and
  all remain true tomorrow.
- properties of the ENVIRONMENT — the tree currently parses, the suite currently
  passes. These are snapshots and were already stale when written.

The record as written asserts the first, explicitly disclaims the second, names
the files that failed the condition, and calls its passing runs snapshots. That
is both honest and unblocked.

**The general form:** before letting a condition gate an action, ask whether the
action's TRUTH depends on the condition or only its CONVENIENCE. A settle
condition governs whether a MEASUREMENT of the tree is meaningful. It does not
govern whether a proof about an artefact may be recorded — and conflating the two
produces an indefinite block that looks like rigour.

See also `a-closing-condition-stated-as-a-measured-number-goes-stale-when-you-change-the-thing-measured`:
the same failure one level up. There a criterion decayed because the campaign
changed what it measured; here a criterion blocked because it measured something
the work did not depend on.

### the-corrections-ran-both-ways-and-each-direction-caught-a-different-class | high | the executor caught what the delegating view had compressed away; the lead caught what the local view could not see was miscounted

Recorded because the pattern is structural rather than a matter of who was more
careful, and it predicts where to look next time.

**Executor to lead — three refused instructions, all correctly.** A redundant
guard ordered by the lead, which would have passed the lead's own acceptance
criteria while leaving the real cause live. A plan Step id the lead told the
executor to put in shipped source — the exact mandate violation the executor had
swept from seventeen sites hours earlier. And a settle condition the lead used to
block a record whose truth did not depend on it.

The executor's own account of why is better than "good judgement": in each case
**it held local context the delegating view had compressed away.** It had read
the three existing escapes, so it could see the gap the lead described was not
there. It had swept seventeen instances of the violation, so the collision was
unmissable. It had just measured the condition failing against an unrelated lane.
That is an argument for the executor RAISING such things, not for the executor
being right by disposition.

**Lead to executor — four corrected figures and one refuted theory.** A
six-consumer count that was one. A `wc -l` reporting line-matches as files. A
coverage-gap claim generalised from testing one check of seven. And an
environmental theory about a timeout that was really an uncached tree parse —
which would otherwise have consumed a quiet-host investigation that could only
have found nothing.

These are the inverse class: not context the lead lacked, but claims whose SUBJECT
or UNIT was wrong in ways invisible from inside the work that produced them. A
figure looks right to its author precisely because they know what they meant.

**The common root under almost every error tonight, in both directions:** a
measurement taken correctly and then reported as something adjacent — a different
unit, a different subject, a different moment. Reasoning held nearly everywhere;
provenance did not. Every finding in this document is a variation on that.

**How:** delegate with the expectation that the executor will refuse some
instructions, and treat a refusal as information about compressed context rather
than as friction. Review returning claims for their unit and subject rather than
their logic, because the logic will usually be sound. And expect the two failure
classes to be asymmetric: the delegating view loses detail, the local view loses
perspective, and neither is corrected by the other trying harder.

### the-timeout-everyone-attributed-to-the-share-was-an-uncached-full-tree-parse | high | four observations were read as I/O stalls; the cause was a gate re-parsing 6396 files three times and walking every tree per symbol

`test_relocation_parity.py` timed out repeatedly and was read across four
observations as an environmental stall on the network-backed worktree — the
failure mode `aeat-local-execution` names for this checkout.

**It is CPU-bound.** Measured, host at 50%:

```
discover 6396 files             0.35s
read + parse all files         24.30s      (x3 uncached = 72.9s)
one full ast.walk, all trees    4.05s      6,198,901 nodes
8 canonical symbols x 4.05s    32.4s
```

`_source_trees()` read and `ast.parse`d every file under three roots with **no
cache**, from **three** call sites; `_class_definition_sites` then walked every
tree once per symbol. ~105s of work before the module asserts anything, which is
exactly the 110s runs and 240s timeouts.

Fixed with `@lru_cache(maxsize=1)` — the parse is pure over a tree the tests do
not mutate. The stack moved off `ast.walk` entirely; the module is now 4 passed
in 243s.

**The disproof was already in the session.** A whole-tree `ast.parse` had been
run earlier for an unrelated syntax sweep: 6487 files, seconds. That established
reading this tree is cheap, so a scan taking minutes was never explicable by read
latency. Two measured facts, both held by the same agents, never joined.

**How:** before accepting an environmental explanation for a timeout, measure the
COST OF THE WORK independently of the run that was slow. An environmental story
is unfalsifiable by the observation it explains; only a measurement of what the
code does can test it.

### a-gate-pinning-a-consumer-tally-reddened-on-correct-work | high | a check named for "exactly seven direct consumers" failed because legitimate work removed one, and updating seven to six would have re-armed it

`test_manager_pilot_has_one_canonical_home_and_exactly_seven_direct_consumers`
hardcoded seven consumer filenames AND pinned the count in its own name. It
failed because the visual suite's populated fixture stopped driving the UI seam
— its docstring says "the property under test is rendering, not the seam" — and no
longer needs the settling barrier. Verified gone at HEAD, not just the working
tree.

So a CORRECT change reddened the gate, which is what `aeat-quality-gates` forbids
pinning a tally for: a count encodes a moment, trains everyone to update the
constant, and then detects nothing.

**The tempting fix re-arms the trap.** Seven to six is one edit, leaves the
identical gate waiting for the next legitimate consumer change, and is attractive
because it is smaller than asking what the check is for.

Rewritten to the property: one definition site, and every consumer a level-1
from-import of the canonical module from inside the canonical package — plus an
explicit **non-vacuity** assertion, because a property gate can pass over an
empty population where a tally gate cannot. Five predicates bite-proved
individually: healthy passes; empty, wrong level, wrong module, outside-package
and plain-import each red.

**How:** when a gate fails on a count, ask first whether the change that moved the
count was correct. If it was, the count is the defect — fix the assertion's
SUBJECT, and add a non-emptiness check, because the property version can pass
over nothing.

### the-session-held-the-refutation-of-its-own-claim-and-did-not-join-it | high | three times, the measurement disproving a live conclusion had already been taken, by the same agents, in the same session

The failure that recurred most was not a missing measurement. It was a
measurement already in hand and never connected to the claim it refuted.

**One — the load stamp.** A hang was twice about to be attributed to a code defect
on the strength of "it reproduces at low load". The `CADRUMO-HOST-LOAD` line
reading `python_processes=52`, and later `cpu=100.0%`, was printed in the same log
being read, above the traceback being quoted.

**Two — the tree parse.** A module's timeout was attributed across four
observations to I/O stalls. Earlier in the same session, for an unrelated sweep,
every tracked file had been parsed in seconds — establishing that reading this
tree is cheap, and therefore that a minutes-long scan could not be read latency.

**Three — the two readings.** A property was queried two ways in two scripts; only
one was run, and its answer produced a complete and wrong root cause. The second
query existed, was one line, and had the same author.

**What makes this class distinct** from the search-and-count failures: there the
instrument was defective. Here every instrument worked and every number was
correct. What failed was ASSOCIATION — holding two true facts and not putting them
in the same sentence. No discipline about measurement quality touches it.

**It concentrates on environmental explanations** for a structural reason: "the
share is slow", "the host is loaded", "it is flaky" fit every symptom, so they
survive every observation. Explanatory reach reads as confirmation when it is the
property that should provoke suspicion.

**How:** before accepting an environmental or intermittency explanation, state
what measurement would refute it, then check whether that measurement has already
been taken in this session. Twice it had, and once it was in the file being quoted
from.

### every-file-parses-and-every-import-resolves-are-different-properties | medium | a gate written after a broken sweep covers only the breakage class that produced it, and its name invites the wider inference

`test_every_source_file_parses` was written after an in-flight sweep left four
files syntactically invalid. It does what it says and was proven to do it.

**It cannot see a deleted module whose importers remain.** That sweep later moved
on to removing modules while their consumers still imported them, and the gate
reported **zero unparseable files** throughout — correctly, because every file
still parses perfectly. `ast.parse` is a syntax check; an unresolvable import is
not a syntax error.

So "every source file parses" and "every import resolves" are different
properties, and only the first is gated. The gate's name states the first
accurately, which is exactly what makes the wider inference tempting: **"the parse
gate covers broken sweeps"** is the sentence a reader forms, and it is wrong for
two of the three breakage classes one sweep produced in a single evening — invalid
syntax, deleted modules with live importers, and a registry whose entries no
longer match its consumers.

This is the document's own subject applied to a gate written by its authors, an
hour after writing it: the check is correct about its subject and the reader
generalises to the subject they wanted. It was caught only because the executor
CHECKED whether the parse gate covered the new breakage instead of assuming the
gate it had just verified would.

**No second gate is proposed.** The suite itself detects unresolvable imports —
noisily, as a collection error attributed to whichever module happens to import
first, which is the attribution problem recorded elsewhere in this document. A
gate could assert every first-party module imports, but that is expensive, it
duplicates what collection already does, and nobody has established that the
noisy detection is insufficient rather than merely unpleasant.

**How:** state a gate's scope in terms of what it does NOT cover when the
adjacent failure modes are plausible. A gate named for a property invites the
reader to credit it with the CATEGORY the property belongs to, and the name alone
cannot carry that distinction.

### the-wrong-inference-was-free-and-the-right-answer-cost-one-command | high | in every case the correct check was cheap and got skipped, because the reasoning already felt complete

The closing observation of the session, and the one that unifies most of this
document.

Three times in the final hours, a conclusion about a system was drawn from one of
its parts. Each time the correct answer was available for the cost of a single
command, and each time that command was skipped:

- **Is this module CLI-specific?** A grep found zero framework references. The
  right check was to BLOCK the package at the meta-path and import it — the
  dependency was in the package `__init__`, invisible to any question about the
  module.
- **Is the taxonomy the home for this field?** The remedy was read and accepted.
  The right check was to READ THE GUARD around it — it fires only when a parent
  setting is overridden, and the field in question has no parent.
- **Does the parse gate cover this breakage?** The gate had just been verified.
  The right check was to RUN IT against the new breakage — a deleted module whose
  importers remain is not a syntax error, and the gate reported clean throughout.

**None of these were difficult.** They were steps that felt SKIPPABLE because the
reasoning already felt complete — which is precisely the mechanism recorded in
`a-retraction-is-timestamped-exactly-like-the-claim-it-withdraws`: a wrong
explanation that fits ends the search. Here the explanation that fits is the
reader's own inference, and what it ends is the verification.

The economics are the point. A wrong inference costs nothing at the moment it is
formed and is indistinguishable from a right one until something forces the
check. The check costs one command. **The asymmetry is enormous and runs entirely
against the intuition**, because the inference arrives feeling finished and the
command feels like confirming what you already know.

**How:** when a conclusion is about a SYSTEM and the evidence is about a PART,
name the command that would settle it and run that command. If naming it is easy
and running it is cheap, the reasoning-only path was never the economical one —
it only felt that way. And treat "this feels already established" as the signal
to check rather than the licence to skip: every instance in this document
arrived wearing that feeling.

### a-truncating-write-on-a-flaky-mount-is-a-data-loss-risk-with-a-two-line-fix | medium | an edit to a shared plan file failed with OSError, and the same call could have emptied it

An edit to the interface plan failed with `OSError: [Errno 22] Invalid argument`
— the network-backed mount, or a concurrent lock. `Path.write_text` opens with
TRUNCATE, so a failure between the truncate and the write leaves an empty file.

Nothing was lost: the author checked integrity before doing anything else and
found 96 rows intact with the edit absent, meaning `open()` failed BEFORE
truncating. The rewrite then went through a temporary file and `os.replace`
rather than retrying the truncating write.

**The exposure was general, not incidental.** Every `write_text` and every
whole-file rewrite performed against a tracked file on this mount tonight — by
either agent, across gates, hooks and conftest edits — carried the same failure
mode. It never fired, which is why nobody noticed it was there.

**And it is the same outcome as the loss already recorded in this document,
reached from the opposite direction.** Five plan rows were destroyed by a peer
committing a stale copy. A half-completed truncating write destroys the same file
without any peer involved. One is a coordination failure and the other is a
durability failure; the artefact is equally gone, and no check in this repository
reports either.

**How:** write a shared file by creating a temporary sibling and calling
`os.replace`, which is atomic on both POSIX and Windows — the reader sees the old
content or the new, never a truncated file. It costs two lines. On a mount whose
flakiness under concurrent I/O is already documented in this project's own
execution rules, the truncating form is not a reasonable default.

**And check integrity BEFORE retrying a failed write.** A retry that succeeds
over an emptied file produces a plausible-looking result and destroys what was
there; the author checked first, which is the only reason the distinction between
"failed before truncating" and "failed after" was recoverable at all.

### a-ranking-query-cannot-answer-an-absence-question | high | an enumeration piped through `head` was read as complete, and absence-from-the-visible-portion was asserted as absence

The fifth and last counting failure of the session, and the only one where the
command was correct and the answer was broken on the way to reading it.

An enumeration of positional CLI declarations was piped through `head -12` to keep
the output readable. One name sat below the cut, with a single occurrence. Its
absence from the VISIBLE portion was read as absence from the data — and then
asserted, in a plan row, as the reason another agent's example was wrong. It was
not wrong; it was present at `_custody_command_specs.py:118`.

**This completes a family of five, all producing believable numbers from commands
that ran without error:**

- `wc -l` counting LINE MATCHES and reported as FILES
- `grep -h` stripping the filenames a downstream path filter needed, so the filter
  passed everything
- a predicate that could not match the shape it sought, so absence read as clean
- `-c` and `-o` not composing, returning a uniform zero
- and this: a correct query, a correct unit, a correct filter, TRUNCATED for
  display and then read as the data

The first four are defects in the query. **This one is a defect in the reading**,
which is why it survived an evening of watching for the other four: nothing about
the command was wrong.

**The corollary is narrow and actionable: `head -N` answers "what is most
common" and never "is X present".** A ranking query and an absence query are
different questions, and a truncated ranking cannot answer the second. Where the
claim is that something does NOT occur, query for that thing specifically —
`grep -c 'name="name"'` — rather than scanning a shortened list for its absence.

**And the distinction that matters more than the error:** the example was not
WRONG, it was TOO WEAK — one positional declaration against two bindings does not
establish that the bound name targets that command, whereas twenty-two bindings
against six declarations does. Collapsing "wrong" into "weak" is what produced
confidence in a refutation that had not actually been made. The two failures need
different responses: a wrong example is replaced, a weak one is strengthened, and
only the first justifies overturning the claim it supported.

## Recommendations

Append a new row citing `W05.P23.S307`, scoped to the local-configuration sweep,
carrying both population definitions and both figures rather than one number.
Leave `S307` closed.

Sweep by FILE, in concentration order, not by crawling the site list. The seven
largest holders carry roughly a third of the population between them, which is
the practical consequence of this being a copied convention rather than
scattered oversight: the shape was propagated by people following a neighbouring
module, so it clusters, and a file-ordered sweep converges far faster than a
site-ordered one. Judge each site as it is reached — repoint to the canonical
where the divergence is unintended, and record an inline reason where a genuine
divergence is kept. Treat any default that then fails validation as a latent
defect to report, never as a regression to work around; that instruction is
already in `S307`'s own text and is the reason the sweep is worth more than
tidiness.

Land the subset-refusing census gate only once the sweep is complete, and pair it
in the same row with an explicit statement that it is not the fix.

For the family as a whole, the durable practice is a question rather than a
mechanism: of any green gate, ask what it actually asserted, and whether that is
the same as what its readers believe it covers. No freshness check finds a gate
that was never right about the thing it is trusted for.

### An absolute-only import census reports live code as dead

**Pathway:** repository-wide import analysis feeding de-export and dead-code work.

A census used to identify package namespaces with no facade-route importers
resolved `ast.ImportFrom` by matching `node.module` against a full dotted path.
A relative import carries the bare tail in that field -- `_parsers`, not
`adapters.inbound.declaracion._parsers` -- so every relative edge was invisible.

Measured on this tree: **35,735 relative import edges against 17,269 absolute**
inside `src/cadrumo`. The census therefore saw roughly a third of the graph.
It did not degrade at the margin: re-run with `level` resolved by walking the
importer's own package upward, the number of namespaces with zero facade-route
importers was **0**, where the original reported four.

What is lost is the distinguishability of two opposite states. An
absolute-only scan returns an empty consumer list for a live namespace and for
a dead one alike, and nothing in its output declares the blind spot -- so the
result reads as a clean measurement rather than a partial one. Acting on it
removed `extract_pages_text` from `adapters/inbound/declaracion/_parsers`,
whose real consumer `_detect.py:23` imports it relatively; the package stopped
importing, and the breakage surfaced only because the change was probed with an
actual `import` afterwards.

**Remediation.** Any import census over this tree resolves `level > 0` before
comparing, and asserts a plausibility floor on its own totals -- a scan of
`src/cadrumo` reporting fewer than ~30,000 internal edges is missing the
relative ones and must not be acted on. Independently, a de-export is proven by
importing the affected package, not by re-reading the census that proposed it:
the census and the deletion share an assumption, so only execution is a second
opinion.
