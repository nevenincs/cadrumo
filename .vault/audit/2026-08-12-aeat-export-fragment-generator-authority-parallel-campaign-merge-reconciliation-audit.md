---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:4cfb4b9a624f5edfa0f1eb41899ad89c4235d10282d072c2a6af4abcb0be76ae'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-casilla-schema-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `parallel campaign merge reconciliation`

## Scope

Two machines executed the same plan steps of the same two campaigns on diverged
history and were reconciled into one tree. The local side carried 289 commits since
the merge base; the incoming side carried 9. Both had independently executed
casilla-schema `S03`, `S14`, `S15` and export-fragment `S55`, `S56`, `S57`, `S60`.
142 paths conflicted, spanning the calculation engine, registry, ledger, filing and
export surfaces, the CLI, all four locale catalogues, and the vault records.

The reconciliation goal was a canonical superset rather than a side-pick: keep the
better implementation of each overlapping concept, carry across capability only one
side had, and close the duplicate authorities the parallel execution created.

Adjudication was grounded three ways. Symbol sets were computed for all three merge
stages, so "absent from ours" could be separated into *never existed* (a genuine
graft) and *deliberately retired by ours* (a resurrection to refuse). Tax-semantic
disputes were settled against the bundled official record designs and the corpus,
not against diff size. Every ruling was verified against the tree rather than
accepted from a report.

## Findings

### auto-merge-silent-duplication | critical | Clean auto-merges duplicated identical additions, and the worst damage never appeared as a conflict

Where both sides added the same construct at slightly different positions, git kept
both with no conflict to review. The resulting files stage clean and read plausibly
in a diff, but the duplicate shadows the original. Three distinct sub-classes
appeared, each invisible to the tool that catches the others.

Duplicate definitions, caught by `ruff --select F811`: a repeated enum member in the
registry export-semantics vocabulary, which raised `TypeError` at class creation and
was the single reason nothing in the repository would import; a repeated payload-axis
mapping entry beside it; a triple-duplicated import block in the registry facade; and
four verbatim-duplicated wizard catalogue constants.

Duplicate parameters and keyword arguments, which are hard `SyntaxError` at
collection and never reach `F811`: four separate instances in one calculate-input
module alone - a model field, a parameter repeated in two different function
signatures, and a repeated call keyword.

Stale name-divergent copies, caught by neither: a local fixture builder duplicating
one that already had a canonical home under a different name, so no redefinition was
reported while the local copy rotted against two contract changes. One file carried
three copies of the same builder.

### retired-surface-resurrection | high | The incoming side carried 25 symbols this tree had deliberately deleted

Because the incoming side branched before several retirements, it still carried
surfaces this tree removed on purpose - among them the whole application verification
package, deleted under an accepted ADR with a structural absence gate, and a
registry-domain bound-input resolver that had existed at 63 sites at the merge base.
Taking the incoming side anywhere near these would have resurrected deleted code
under cover of a merge. The three-stage symbol comparison is what made the difference
visible: measured against the local tree alone, a deliberate retirement and a genuine
capability gap look identical.

### exonerado-390-population-vs-capacity | high | A grounded ruling was reversed after reading the official record design directly

The two sides disagreed on the M303 exonerado-390 activity-row rule: contiguous slots
of any length versus exactly six. The incoming rule was adopted first, on the
reasoning that the official record fixes exactly six activity pairs. That reasoning
conflated the record's **capacity** with the filer's **obligation**.

Reading the DP30304 block directly settles it: the `Validación` column reads
`Obligatorio` for the identity constants and the end-of-record marker and is **empty
for every activity field**. Both row fields reject blanks, so requiring six rows would
force a single-activity taxpayer to fabricate five activities they do not carry on -
a false declaration. The contiguous rule is canonical; capacity remains enforced by
the slot bound. A supporting claim that older design epochs carry three slots rather
than six was also checked and is false; every epoch carries six.

### representable-versus-unrepresentable-populations | medium | The same shape of demand can be correct or fabricating, and the test is representability

A prorrata register coverage gate demanded a current-year entry, superficially the
same shape as the exonerado rule just overturned. It is correct, and the distinguishing
property is whether the demanded population can be stated truthfully. The prorrata
regime vocabulary carries a "none applies" member, so requiring a declaration compels
a statement, not a claim - every real population is representable. The exonerado rule
had no such escape. A demand that can only be satisfied by inventing facts is the
defect; a demand that can be satisfied by declaring absence is a completeness gate.

### position-and-count-pinned-gates | medium | The incoming side's gates repeatedly encoded a moment rather than a property

Three instances of one root cause: assertions pinned to corpus tallies, to a bridge
call count, and to line numbers. Every one was a latent failure the moment either side
added code, and this merge's 289-commit divergence detonated all of them. The tallies
were replaced by the properties they stood for; the line-keyed exemptions were re-keyed
to path plus enclosing function, then proven to bite by shifting every module's line
numbers and confirming the gate still passed, and by renaming an exempted function away
and confirming it failed loudly. A line-keyed exemption detaches silently, so a reasoned
exclusion quietly becomes a blanket one.

### m303-external-import-scope-reduction | medium | A working path was withdrawn, correctly, and the narrowing is recorded rather than absorbed

The incoming side added an unconditional refusal to M303 external filing-evidence
import. It first read as an unfinished stub that removed working behaviour. It is not:
this tree never supplied filing-instance evidence on that path at all, so it was
silently creating evidence-less M303 revisions, and the only available way to satisfy
the new contract would have been a test helper that hardcodes "not exonerado, not
insolvent, no joint return" - fabricating declarations in production. Refusing is the
honest behaviour, and the refusal is authored in all four locale catalogues.

The narrowing is real and is stated here rather than absorbed: M303 external import has
no working path until a typed filing-facts input surface exists to supply the filing
instance evidence from the operator rather than inferring it. Non-M303 external import
is unaffected, and M303 evidence can still enter through calculation with
caller-supplied evidence.

### absent-authority-must-refuse-not-default | medium | A generic caller may declare absence only because the engine fails closed on it

Four generic calculation callers - the worksheet pull, the parity harness, the IRPF
cuota differential, and observation recomputation - omitted the M303 filing-fact
arguments and inherited them from a default. Each now states the absence explicitly.
The safety of that declaration does not rest on those paths being M303-free today,
which is the fragile reason: the pull path passes whatever snapshot it is handed, so a
303 snapshot reaches it the moment worksheet support is added.

It rests on the engine refusing an absent scope rather than defaulting it. The module
formula raises when the simplified-regime scope is `None`, and returns zero only for an
explicit not-claimed decision. A simplificado filer reaching a generic path therefore
gets a loud refusal, never a silent general-regime figure. Pull-versus-calculate casilla
parity holds for the same reason - neither path computes an M303 module value, rather
than both computing the same one. The distinction matters because the fragile version of
this reasoning stops being true silently as soon as someone widens a caller.

### m303-fichero-boe-layout-unauthored | medium | M303 export is unreachable end to end, and predates the merge

M303 carries zero `export_layouts` fragments in all three merge stages, while ten other
modelos carry them. Export therefore refuses with an unsupported-layout error for every
M303 revision, and two end-to-end tests that assert a successful M303 fichero-BOE export
encode intended rather than achievable behaviour. Nothing in the merge caused this and
nothing in the merge can close it: authoring the layout is regulatory work against the
official diseño, governed by the export-mirrors-official-structure rule, not a
merge-resolution task. Weakening the assertions would fake a filing-grade export gate.

### absence-can-be-load-bearing-in-a-fixture | medium | A more-complete fixture was the wrong fixture, because the missing field carried the classification

Reshaping a fixture to stop routing through a refused verb required replicating a prior
filed period directly. The first attempt supplied that prior revision with real
filing-instance evidence, on the reasoning that a fully-populated fixture is more
honest. It changed the outcome: absent evidence is precisely what marks a revision as
externally-imported AEAT evidence rather than an app-produced local filing, so
populating it reclassified the period as a local recurrence and moved the IVA wallet
reconciliation result.

The corrected fixture leaves the field absent and carries a comment recording that the
absence is load-bearing rather than an oversight - without which the next reader deletes
it as incomplete. The general lesson is that "replicate the end state exactly" is a
substantive instruction when a field's *absence* is part of a classification, and that
completeness is not automatically the safer direction in a fixture.

### stricter-contract-tail-exceeds-its-measured-blast-radius | medium | Measuring constructors under-counted the consumers of a required-field change

Adopting the stricter required `filing_instance_evidence` contract was validated by
measuring construction sites: 90 of 95 already supplied it, so the sweep looked like
five one-line edits, and the enforcing gate went green after those five. The tail was
larger. Fixtures that call higher-level actions which construct revisions internally are
a different population from direct constructors, and they surfaced as roughly three
dozen further failures once the tree could run.

The contract is still right and was not reverted. The lesson is about the measurement:
an AST census of direct construction sites does not bound the blast radius of a
required-field change, because it cannot see callers that reach the constructor through
an action. A gate proving direct constructors comply can be green while the indirect
population is untouched.

### no-registry-data-loss | low | Every apparently-missing export tree was verified absent from all three stages

Several failures reported that a revision "has no exports", which would be the
signature of registry data lost in the merge. All seventeen empty registry directories
were checked against base, ours and theirs: every one carries zero tracked content in
every stage. They are tool-run residue, git cannot track them, and the failures are
pre-existing on both parents. No registry data was lost.

### loader-cache-race-is-fail-closed | low | The concurrent-write race produces false positives only

Registry-suite failures under parallel execution frequently reported that the registry
directory changed during cache fingerprinting. Sequential re-runs pass. The race aborts
fingerprinting rather than serving stale data, so it can redden a healthy tree but
cannot green a broken one. No result in this reconciliation rests on a stale cache.

## Recommendations

Treat a large merge as a duplication event, not only a conflict event. Run
`ruff --select F` for redefinitions and duplicate parameters, and an AST sweep for
repeated class-body fields, repeated enum members, and local copies of constructs that
already have a canonical home. The conflict markers are the visible half; the clean
auto-merges are where the import-breaking damage was.

When one side lacks a symbol, resolve *why* before grafting. Compare all three merge
stages: absent-at-base is a capability gap to carry across, present-at-base-and-removed
is a retirement to preserve. Without that split, a deliberate deletion and a genuine
loss are indistinguishable.

When two sides encode a tax rule differently, read the official record design rather
than adjudicating between reports. The decisive question is whether the stricter rule
demands a population the filer can state truthfully. If it can only be satisfied by
inventing facts, it is a fabrication rule regardless of how well it matches the
record's layout.

A follow-on decision is required on the withdrawn-layout identifier contract. The
withdrawn-layout gate asserts one decision per layout subject, while M303 declares its
removal per revision under a shared subject. Adding the missing subjects to the gate's
set exchanges a set-equality failure for an identifier-pattern failure, so the contract
question - one decision per subject, or one per revision - must be settled before the
gate can pass.

Bound a required-field change by its *consumers*, not by its construction sites. An AST
census of direct constructors is a necessary check and an insufficient one; the sweep is
not finished until the callers that reach the constructor through an action are swept
too, and a green constructor gate does not evidence that.

Five carry-forwards remain open and are not merge-induced: the REAGP compensación
category has no decomposition rows and needs a grounded ruling on what it decomposes
into, which is tax work rather than merge work; a group of tests remains coupled to an
M303 revision this tree deliberately parked as unlanded, which cannot be closed without
landing that revision's registry data; and the M303 fichero-BOE export layout is
unauthored, so M303 export is unreachable end to end until it is written against the
official diseño; a group of justificante fixtures carries hyphenated CSV literals that the
`AeatCsv` pattern rejects, since a real Código Seguro de Verificación carries no
separators - the pattern and the literals are each byte-identical across all three merge
stages and the carrying files were not conflicted, so the constraint is right and the
fixtures are wrong; and the IVA wallet refusal builds its operator message from the
decision's reason identity while its tests assert on the divergence code, which is a
question about what the operator sees in a blocking refusal rather than a merge
resolution.

## Process observation

Five times during this reconciliation an agent declined an instruction from the
coordinator and was right to: the exonerado population rule, a retired-symbol reference
that was an anti-regression guard rather than a use, a deduction-authority parameter
shape, a duplicate assertion the coordinator asked to be written a second time, and a
fixture whose subject the coordinator had misidentified. In four of those the
coordinator had already stated a conclusion; in the fifth the instruction was a binary
that did not fit the case.

The common factor is not agent quality - it is that a directive carrying a conclusion
invites compliance, whereas a directive carrying the *evidence standard* invites
verification. Every one of the five was caught by an agent going to the corpus, the
validator, or the surrounding code rather than to the instruction. Briefs on work of
this kind should state what would have to be true for a ruling to hold, and should say
plainly that a contradicting finding is wanted rather than tolerated.

The inverse also occurred and is worth recording beside it. A reported cluster of thirty
failures was dismissed by the coordinator after a search for the wrong constraint shape
returned nothing, and the reporter had in fact cited two incorrect details. Both parties
were partly wrong and the cluster was real. What recovered it was the reporter restating
the finding with corrected specifics rather than withdrawing it, and the coordinator
re-checking rather than standing on the earlier refutation. A refutation that rests on a
failed search is weaker evidence than it feels, because a search can fail for reasons
unrelated to the claim - here the constraint was expressed as a pattern on an annotated
type alias rather than as the length bound that was searched for.
