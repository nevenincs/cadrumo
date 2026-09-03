---
tags:
  - '#plan'
  - '#registry-declaration-hardening'
date: '2026-09-02'
tier: L3
related:
  - '[[2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit]]'
  - '[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]'
  - '[[2026-06-10-period-revision-resolution-adr]]'
  - '[[2026-08-27-registry-temporal-coverage-design-authority-declaration-adr]]'
modified: '2026-09-03'
body_schema: body-v2
body_hash: 'sha256:70b3e9a1b7840802bcc11417cf6846fe44bf46416fa0ca8a6774eaf59f2c879d'
---

<!-- RETIRED: S73, S188 -->

# `registry-declaration-hardening` plan

## Description

The registry declares the same fact in many places and reconciles the copies afterwards with
agreement validators. The breadth was measured before this plan was written: a revision's temporal
validity expressed at eight sites, one citation restated at eleven, applicability at seven, capability
grade in five encodings, a rendered amount's semantics at six - against the validator modules in
the registry package whose job is to notice when the copies disagree - the `_validate*` family, fifty-one
of them when last counted, which is a figure a reader can re-derive by listing the package rather than
trusting this sentence. Those five figures were attributed to the governing audit and are not in it: searching that
record finds them only where a later entry quotes this sentence, and no sibling document carries them
either. They came from a measurement made before this plan and not carried into the record that
survived, so they are stated here as history rather than as evidence a reader can check.

Two have since been re-derived, and the results are instructive about the rest. The temporal sites
are now declared as data beside the screen that compares them, with the boundary written down: six
year-level sites, not eight, because a deadline window's opening, closing and payment dates say WHEN
within a year a filing is due rather than WHICH years a revision serves, and folding them in inflates
a restatement count with facts that cannot disagree. The gap between six and eight is a difference
between two definitions, not an error in either, and it is only visible because one of them is now
written down.

The citation figure moves the other way and is worth more than the number it replaces. Counting every
declared field on a registry declaration type whose name pairs `ref` with `legal` or `source`, a
citation can be restated across 25 declaration types and 48 fields, not eleven - and the split is 24
`legal_refs` against 24 `source_refs`, so nearly every type able to cite a law is also able to cite a
source, in parallel fields. Whatever eleven counted, the surface a reader must keep consistent today
is several times wider, and the symmetry says the two citation kinds were declared as a pair 24
separate times rather than once with two projections.

The corpus answers the same question differently and both answers are worth carrying. The provenance
screen measures 31,608 citing sites against the references they name, and states the ratio its own
report is built on: a citation is repeated by roughly nineteen children for every one place a fix
lands. So 48 fields across 25 types is how many places COULD restate a citation, and nineteen is how
many typically do. Neither is eleven, and a plan quoting one number where the surface and the corpus
disagree by that much was hiding the more interesting fact - that the restatement is concentrated in
the citing children rather than spread across the declaration types.

Applicability re-derives to two different numbers and the plan's is neither, which is the clearest
demonstration of why a boundary matters more than a count. Ten declared fields carry the word:
one on the revision, five inside the rule definition that field holds, two on a deadline window and
two on a live cross-reference decision. But the rule's five are the CONTENTS of one declaration
reached through one field, not five places that can disagree, so under the boundary that asks which
declarations can independently state whether something applies, the answer is three: the revision's
rules, a deadline window's conditions, and a cross-reference decision's predicates. Three or ten
depending on the question; seven is neither, so the original counted something else again.

The amount-semantics figure is the only one whose number survives, and the way it survives is worth
reading. Six declared fields say how an amount is written - two roundings, two units, a decimals and
a signed - which matches the six on record. Under a stricter boundary, how an amount reaches the
WIRE, only two of those six qualify. And the fact that decides the scale of a monetary field is in
neither count, because it is not declared anywhere: the `money` wire type multiplies by one hundred
in the renderer's codec rather than in any declaration, so the one semantic that has produced a live
filing-correctness defect in this corpus is the one no declaration states. A count of declared places
cannot see it, which is why the count matching is not the same as the count being right.

The capability-grade figure could not be re-derived at all: no boundary survives saying what counts
as an encoding of it, and the schema today carries one optional grade field with a documented reading
and a documented absence, which is the shape this plan recommends rather than the defect it alleges.
One live example carries the argument better than the five figures above, because it can be counted
today and its cost is visible. The filing envelope is declared two ways: twenty revisions use the
typed slot, which carries record identity, prefix extent, total and closer derivations, a schema
version, a digest-bearing source reference and a product-identity requirement; thirty-one revisions
across sixteen modelos spell the same envelope as an ordinary record, where none of those facts has a
home and all survive as offsets. The typed form's advantage is in use rather than theoretical:
eighteen of those envelopes declare `aeat-product-software-identity-v1` as their product-identity
requirement, so the fact modelo 714 cannot state is one eighteen of its peers state in a field. The
cost is not hypothetical - three iterations of this campaign went
into deciding whether four bytes at position 93 of one modelo's envelope should be authored, and the
answer, that they are delegated to the software house and this product must not write them, is a fact
the typed slot states in a field and the record spelling cannot state at all.

A second live example is larger and cost this campaign a wrong recommendation. A casilla's label is a
property of the casilla, and the catalogues key it by revision, so the Spanish catalogues carry 27,569
casilla label strings of which 10,586 are the surplus of a label restated under a further revision -
4,733 for modelo 100 alone, and 3,173 for modelo 200, where the two revisions' shared labels are
byte-identical on every one. Across all four shipped locales the surplus is 28,129 strings. Both
Spanish figures are corrections: the ad-hoc query that first produced them reported 29,522 and 11,286,
and only became reproducible once it was made a module. The consequence is that declaring a revision
costs a full re-translation of text that has not changed, and 156 labels missing from one revision were
first
recorded here as work to author by hand before the operator pointed out that the derivation, not the
translation, is the deliverable. The tooling exists - `dev.locales` scaffolds keys, carries a
revision's keys onto renamed ids, and applies generated migrations - and what is missing is one label
per casilla with a per-revision override only where the official text genuinely differs.

The remaining two await the same treatment. Detection after the fact is the wrong
shape. This plan
moves the registry toward declaring a fact once and deriving its projections, and builds the tooling
that can prove it.

Measurement has since changed what the later Waves are for, and the Steps record it. The screens
that measure the declaration conditions run from one entry point over a single loaded registry -
the count is whatever `SCREENS` in the analysis package enumerates, ten at the time of writing -
each proving its own detection against a constructed defect, and the gates behind them are whatever
the declaration-invariant module holds - twenty-one at the time of writing, of which three are
detector proofs showing a gate bites rather than gates themselves. Both figures are written the way
the screen count above is, because both moved while this plan was being executed: the gates were
recorded as sixteen with two proofs beside them, and neither number was wrong when written.

Two later tools sit outside that entry point deliberately, because neither can run over a single
loaded registry. The selection probe asks a modelo's revisions whether they resolve using the
period codes each declares, so it takes a coordinate rather than sweeping the corpus. The
load-claim screen spawns clean subprocesses in both cache regimes, because the question it asks -
whether a module a rule calls live is one a load actually imports - cannot be answered from
inside a process that has already imported the tooling. Each gate was written after finding the hole it closes rather than in
advance, and several caught the author within an iteration of being written - one rejected the very
correction made to satisfy it, twice.

Several conditions turned out to be clean corpus-wide and are gated as invariants carrying no
tolerance rather than as counts; several others turned out larger or differently shaped than the
audit first recorded, and two claims the audit made were withdrawn outright when measured. The
screens are the evidence the Wave six decisions are written from, which is why they precede those
decisions rather than waiting on them.

The capability screen answers the question that opened this work directly, because it turned out to
be answerable from the declarations rather than needing judgement. It is named rather than numbered:
it was the tenth when this was written, and an eleventh would have silently re-pointed the sentence
at a screen that answers something else. Its census is the source for what follows, so these figures move as the registry does and are
re-derivable by running it. Of 58 modelos, 23 declare applicability only - the censal and
informational ones, correctly carrying no filing machinery - and 4 declare calculation only. Sixty-nine
revisions reach filing grade, and every one of them carries a layout, which is stronger than the
qualifier this sentence used to attach: there is no filing-grade revision today with nowhere to put
its answer. When first written these read 22, 5 and 68; each moved by one while the argument they
support did not, which is what a figure quoted from a live census does. What that claim
rests on is thinner than the number suggests: 31 layouts spell their envelope as a record where the
export boundary cannot see it, 5 revisions can render a fichero and cannot say when it is due, and 4
declare a filing calculation class with no formula behind it.

Three of those conditions were first measured as much larger and corrected before being reported: an
envelope condition counted 52 where 31 are real, a formula condition would have counted 14 where 4
are real, and the suite census counted 35,287 findings where 1,633 are things anyone would act on.
Each overstatement came from counting sites rather than the unit someone fixes, or from treating a
declared and correct shape as a defect. Conditions clean corpus-wide are gated as invariants carrying no tolerance
rather than as counts; conditions still carrying findings are deliberately not gated, because gating
them would need a tolerance and a tolerance is the ratchet this project retired. Several conditions
turned out larger or differently shaped than the audit first recorded, and several claims were
withdrawn outright when measured, including two of this plan's own.

Two defects touching filing data were located during execution and neither is repairable from here.
One monetary field in a revision currently in force emits an unscaled magnitude beside five identical
siblings; its cause is a footnote reference read as a statement of representation, and correcting the
predicate makes 183 fields newly eligible, each needing a reviewed rule in the same change. One
informativa ships a declarado record whose repeating structure the current inputs no longer produce;
the shipped bytes are correct, regenerating that tree would collapse every counterparty into one
record, and only the record-design parser can supply the second field the map would need.

A third class emerged late and is worth carrying separately: gates in this area fail by not running
rather than by going red. A modelo inspection gate asserted a revision identifier that never existed
and had therefore never passed, and is now repaired. Eleven tests cover a filing-proof surface the
codebase removed and refuses. One screen built by this plan was enrolled and gated for days with
nothing proving it could detect what it guarded. Each was invisible because the suite already carried
failures read as background, and the remedy in every case was a gate over the tooling rather than
over the registry.

Three blockers are load-bearing and none is a design question. Files another contributor holds block
the predicate correction, the parser descent, the release-predicate relocation and the ratchet
removal. The filing-export proof cannot proceed by engineering at all, because the corpus holds no
official emitted-byte reference and a vector whose expected bytes came from this project's own writer
would prove only self-consistency. Wave six waits on four decisions that are written and proposed but
not accepted.

Two blockers are load-bearing and neither is a design question. Wave two and part of Wave three
cannot proceed while another contributor holds the files their Steps must move, because the
architecture rule requires a relocation to move a definition and every consumer in one change.
Wave three's proof enrolment cannot proceed at all by engineering: the corpus contains no
official emitted-byte reference for any modelo, and a vector whose expected bytes came from this
project's own writer would prove only that the writer agrees with itself. That Wave's first Step
is therefore evidence acquisition, and it is the critical path to the product's central claim.

It is sequenced so that measurement comes first. Four figures published during the audit
were wrong, each because a consumer reassembled the resolved export surface by hand and
dropped one of its three linkage paths. Wave one removes that whole class of error by
providing the surface whole; every later gate reads it through that accessor rather than
rebuilding it. Wave two returns the project to having a standing regression gate at all,
which means moving the release-eligibility predicate out of contributor tooling into the
shipped application, since a predicate that only exists development-side cannot gate
anything. Wave three makes the filing-export proof real: the mechanism is built and
carries zero enrolled coordinates, so no exported byte has ever been checked against an
official record design. Wave four adds the missing edge gates. Wave five corrects the data
defects that need no decision. Wave six applies the general contract.

The first five Waves need no architectural decision and are grounded in the audit alone.
Wave six is different in kind: none of the four decisions it depends on has been written,
and the feature's proposed coverage decision is itself resting on a problem statement the
refactor has overtaken. Every Step in Wave six is therefore authoring or migration that
cannot begin until those records exist and are accepted, and the Phase that holds the four
decisions is the gate on the Phase that applies them.

While Wave six's decisions remain unwritten, the work has extended into the surface those
decisions will eventually be applied to. The same question the registry raised - is this
fact declared once, or restated - turns out to be answerable about the codebase itself, and
the answers are of the same kind. One name defined in two modules of one layer is a
restatement no boundary explains; a constant whose name carries two values is a restatement
a reader cannot even detect by grepping. Both are now measured, adjudicated and gated, and
the nine same-layer collisions divide into three that are correct, four whose name misleads,
one that is a genuine duplicate, and one where the two definitions disagree about what they
accept and no rename can settle it.

Three of these screens were not built, and their absence is part of the result. Type
declarations sharing an exact field shape number 81, and every one of the seven sharpest is
correct by construction - a protocol matching its implementation, three commands whose
schema names are their output contract. A lane-visibility gate was built and then narrowed,
because the tree already answered the reachability half of its question per test rather than
per module. A category is worth gating only when a member of it is more likely wrong than
right, and this plan has now declined that test three times as often as it has passed it.

What the extension found in passing matters more than the screens. The conformance closure
suite - sixteen ordinary unit tests that prove real filing outcomes - is named by no CI lane
and has never run, and one of its tests has been failing throughout this campaign's
measurements under the description of inherited baseline. The remedy is one path in one
recipe, and the Step that names it is deliberately left open.

## Steps

## Wave `W01` - measurement integrity

Establish one accessor that returns a revision's resolved export casilla surface whole, and move every screen onto it. Four defective figures in the governing audit came from three different partial reassemblies of that surface, so no later Wave can be trusted to measure itself until this lands. Downstream Waves W03 and W04 depend on it.

### Phase `W01.P01` - resolved surface accessor

Deliver one accessor returning a revision's complete resolved export casilla surface, and move every consumer onto it.

- [x] `W01.P01.S01` - Add a resolved-surface accessor returning the union of binding-derived fields, projection endpoints and record row mappings; `dev/registry/analysis/resolved_export_surface.py`.
- [x] `W01.P01.S02` - Prove the accessor with a detector test that fails if any one of the three linkage paths is dropped; `dev/registry/tests/test_resolved_export_surface.py`.
- [x] `W01.P01.S03` - Refactor the export-reference screen onto the accessor and delete its private walk; `dev/registry/analysis/export_ref_symmetry.py`.
- [x] `W01.P01.S04` - Promote the accessor to its canonical home beside the export derivation it wraps; `src/cadrumo/domain/calculations/registry/export.py`.
- [x] `W01.P01.S05` - Repoint the development accessor at the canonical one and delete the duplicate walk; `dev/registry/analysis/resolved_export_surface.py`.
- [x] `W01.P01.S83` - Document the three linkage paths and require every export coverage figure to come from the resolved accessor; `dev/registry/mappings/README.md`.
- [x] `W01.P01.S103` - Gate that no screen module reaches for the binding derivation instead of the resolved-surface accessor; `dev/registry/tests/test_declaration_invariant_gates.py`.

## Wave `W02` - gate restoration and residue removal

Return the registry to having a standing regression gate that continuous integration can reach, by moving the release-eligibility predicate into the shipped application beside the models it already owns and wiring a coordinate-identity gate. Removes the retired ratchet residue and repoints the documents and recipes that still name the deleted audit command. Depends on nothing; blocked in part on files another contributor holds.

### Phase `W02.P02` - ratchet residue removal

Delete the retired baseline and ratchet remnants and repoint every document and recipe that still names the deleted audit command.

- [x] `W02.P02.S06` - Delete the dead baseline and ratchet models left by the retired audit command; `dev/registry/conformance/manager.py`.
- [ ] `W02.P02.S07` - Repoint the registry conformance recipe at the closure command; `justfile`.
- [ ] `W02.P02.S08` - Declare the development-to-application boundary contract for the registry tooling; `.importlinter`.
- [ ] `W02.P02.S09` - Move the tomlkit dependency declaration so the last authoring migrator can be retired; `pyproject.toml`.
- [x] `W02.P02.S10` - Delete the applicability fragment authoring migrator now its output has landed; `dev/registry/authoring_migrate_applicability_fragments.py`.
- [x] `W02.P02.S95` - Restore the modelo 038 inspection gate whose four stale assertions predate the modelo's re-grounding onto the 2024 orden; `dev/registry/tests/test_static_inspection.py`.
- [x] `W02.P02.S96` - Retire the eight tests driving the disabled single-channel proof authority, and re-site the three payload-acceptance tests whose modelo 200 fixture lost both its export layouts and its filing grade; `dev/registry/tests/test_filing_export_live_proof.py`.
- [x] `W02.P02.S97` - Sweep the registry suites for gates that cannot pass and record each as owned, dispositioned or retired; `dev/registry/tests`.
- [x] `W02.P02.S107` - Retire the developer registry package re-export facade and its enforcing inventory assertion, repointing the one symbol consumer at the defining module; `dev/registry/__init__.py`.
- [ ] `W02.P02.S108` - Promote the eleven src-side private modules that non-test dev consumers reach across the package boundary, leaving the eleven test imports alone; `src/cadrumo,src/cadrumo_harness`.
- [ ] `W02.P02.S109` - Rewrite the modelo 151 live-filing closure test onto the two-channel authority and delete the single-channel proof authority, once an enrolled conformance vector lets that authority produce a satisfied outcome; blocked behind the official emitted-byte reference and the vector enrolment it feeds; `dev/registry/conformance/tests/test_real_closure_outcomes.py`.
- [ ] `W02.P02.S110` - Resolve the twenty-four filing tests demanding filing grade from modelos 200, 038 and 036, which now declare calculation or applicability grade; `src/cadrumo/application/filing/tests`.
- [x] `W02.P02.S111` - Retire the generation pipeline package re-export facade so the initialiser is an inert namespace marker; `dev/registry/pipeline/__init__.py`.
- [x] `W02.P02.S112` - Bring the conformance test directory into the lane measurement, since every full-lane run so far covered only dev/registry/tests; `dev/registry/conformance/tests`.
- [x] `W02.P02.S113` - Reduce the remaining five package initialisers in the registry development tree to inert namespace markers; `dev/registry`.
- [x] `W02.P02.S114` - Gate that every package initialiser in the registry development tree carries nothing but a docstring, proven against a constructed re-export; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P02.S115` - Clear the vault record citations from the registry source module and the four modelo 390 casilla declarations that carried them; `dev/registry/pipeline/_source_defects.py`.
- [ ] `W02.P02.S116` - Decide the seven remaining code-boundary violations outside the registry tree, and the eleven package initialisers elsewhere in dev that carry exports; `dev`.
- [x] `W02.P02.S117` - Cut the seventeen hundred isolated snapshots the closure composers take for one hundred and twenty-eight rows, without memoising above the authority; `src/cadrumo/application/registry/temporal_coverage.py`.
- [x] `W02.P02.S118` - Add an authority accessor returning the admitted revision identifier without the isolating deep copy, and move the temporal coverage composer onto it; `src/cadrumo/domain/calculations/registry/authority.py`.
- [x] `W02.P02.S119` - Re-point the forty-four stale branch adjudication keys the private-to-public module rename invalidated; `dev/registry/analysis/modelo_branch_classification.toml`.
- [x] `W02.P02.S120` - Adjudicate the seven split-out modules and twenty-one newly reachable modules the refactor created, which needs grounded rulings rather than key repair; `dev/registry/analysis`.
- [x] `W02.P02.S121` - Decide whether the static load closure should exclude function-scoped import edges, or hoist the deferred import that makes it disagree with a real load; `dev/registry/analysis/load_census.py`.
- [x] `W02.P02.S125` - Probe every construct-evidence coordinate through the identifier accessor and materialise only the snapshot the ledger reads; `src/cadrumo/domain/calculations/registry/coverage.py`.
- [x] `W02.P02.S126` - Remove the plan step identifiers embedded in the modelo 200 revision declarations; `src/cadrumo/_data/registry/aeat/modelos/200/revisions`.
- [x] `W02.P02.S127` - Extend the code-boundary detection to plan step identifiers, which it does not match today because it looks for document stems only; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P02.S128` - Re-site or convert the twenty-four filing tests that demand filing grade from modelos 200, 038 and 036, per the specification recorded in the audit; `src/cadrumo/application/filing/tests`.
- [x] `W02.P02.S136` - Expose the coverage facts a ledger reads as their own isolated projection, since deep-copying a whole snapshot to read four collections costs a hundred times what those collections cost; `src/cadrumo/domain/calculations/registry/authority.py`.
- [x] `W02.P02.S137` - Gate the coverage facts projection on answering identically, refusing identically, and isolating what it hands out; `src/cadrumo/domain/calculations/registry/tests/test_coverage_facts.py`.
- [x] `W02.P02.S152` - Delete the ledger bindings parent module left behind by its own split, whose fifty-nine of sixty definitions exist identically in the modules that replaced it; `src/cadrumo/domain/calculations/registry/ledger_bindings.py`.
- [x] `W02.P02.S153` - Collapse the duplicated list type guard and mapping predicate onto their canonical definitions; `src/cadrumo/domain/iva`.
- [x] `W02.P02.S154` - Collapse the config payload result schema onto one construction, replacing four identical private helpers and one inline copy; `src/cadrumo/entrypoints/cli/config/_command_spec_schema.py`.
- [x] `W02.P02.S155` - Collapse the duplicated JSON locator, flow traversals and profile projection onto canonical definitions; `src/cadrumo`.
- [x] `W02.P02.S157` - Collapse the remaining duplicate function bodies across the shipped package onto canonical definitions, from twenty-seven bodies to five; `src/cadrumo`.
- [x] `W02.P02.S158` - Remove the exported casilla data type alias that gave a canonical registry type a second public name; `src/cadrumo/application/modelo/edit_models.py`.
- [x] `W02.P02.S159` - Remove the two dead source-policy aliases that gave canonical constants a second unused name; `src/cadrumo/application/modelo/calculation_source_policy.py`.
- [x] `W02.P02.S160` - Resolve the two classes sharing a name across modules, collapsing the duplicated record protocol and naming the profile custody digest model for its layer; `src/cadrumo`.
- [x] `W02.P02.S161` - Collapse the redaction label, the familia section identifier and the modelo edit responsible owner onto single declarations; `src/cadrumo`.
- [x] `W02.P02.S162` - Judge the remaining twenty duplicated name-and-value constants, separating one fact stated twice from two facts that happen to agree; `src/cadrumo`.
- [x] `W02.P02.S163` - Gate that every deliberately collapsed concept keeps exactly one definition, so a whole-tree sweep cannot silently restore the duplicates; `dev/tests/test_canonical_definitions_stay_singular.py`.

### Phase `W02.P03` - release predicate relocation

Move the release-eligibility predicate into the shipped application beside the models it already owns.

- [ ] `W02.P03.S11` - Move the release-eligibility predicate beside its models in the application registry package; `src/cadrumo/application/registry/closure.py`.
- [ ] `W02.P03.S12` - Reduce the development closure module to a thin caller carrying no predicate; `dev/registry/conformance/closure.py`.
- [ ] `W02.P03.S13` - Prove the relocated predicate through the real authority with one refusal case per reason; `src/cadrumo/application/registry/tests/test_closure_predicate.py`.

### Phase `W02.P04` - coordinate identity gate

Wire a standing regression gate comparing the satisfied filing-coordinate set by identity rather than by count.

- [ ] `W02.P04.S14` - Record the satisfied filing-coordinate set as registry data rather than development state; `src/cadrumo/_data/registry/aeat/closure/coordinates.toml`.
- [ ] `W02.P04.S15` - Compare the live coordinate set against the recorded one by identity and name the regressed limb; `src/cadrumo/application/registry/closure_capture.py`.
- [ ] `W02.P04.S16` - Prove the gate detects a removed coordinate using an isolated temporary registry tree; `src/cadrumo/application/registry/tests/test_closure_capture_gate.py`.
- [ ] `W02.P04.S17` - Wire the coordinate gate into the repository gate lane; `justfile`.
- [x] `W02.P04.S62` - Gate the declaration conditions that hold corpus-wide as invariants carrying no tolerance; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P04.S63` - Run every declaration screen from one entry point over a single loaded authority; `dev/registry/analysis/screens.py`.
- [x] `W02.P04.S64` - Gate that every screen module is enrolled in the runner so none can drop out silently; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P04.S67` - Document the declaration screen suite and its two honesty rules for contributors; `dev/registry/README.md`.
- [x] `W02.P04.S68` - Gate that the contributor README documents exactly the screens that run; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P04.S84` - Gate that every symbol the contributor READMEs name still resolves to a module or attribute; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P04.S98` - Gate that every screen searches a non-empty population so silence cannot mean an absent subject; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P04.S100` - Gate that every screen module carries a test module so no gate rests on unproven detection; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P04.S101` - Gate that every enrolled screen completes over the whole corpus and describes what it counted; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P04.S104` - Gate that running every screen leaves the shipped registry byte-for-byte untouched; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P04.S105` - Correct the five screen labels that described one kind while counting several, including one that inverted its sense; `dev/registry/analysis/screens.py`.
- [x] `W02.P04.S106` - Gate that every kind a screen emits live is named in its own docstring; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W02.P04.S122` - State per modelo what the product can actually calculate and file, as a screen reading the declarations rather than a maintained list; `dev/registry/analysis/modelo_capability.py`.
- [ ] `W02.P04.S123` - Migrate the thirty-one revisions across sixteen modelos that spell their envelope as a record onto the typed envelope slot eighteen others already use across seven modelos, since the export boundary sets renders_filing_envelope from that slot alone and skips the product-identity requirement entirely without it, silently, for the twenty of the thirty-one that can be filed; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W02.P04.S124` - Resolve the twenty-five revisions carrying an export layout or envelope while declaring a grade below filing, twenty-two at applicability and three at calculation, starting with modelos 185 and 222 whose 2025 revisions ship a committed generated tree at applicability; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W02.P04.S129` - Re-ground the capability screen's envelope condition against the official designs, replacing the fifty-two-row count with the thirty-one real record-spelled cases; `dev/registry/analysis/modelo_capability.py`.
- [ ] `W02.P04.S130` - Withdraw the modelo 714 envelope authoring: offsets 93 to 96 and 101 to 109 are delegated to the entidad desarrolladora, which the coverage validator classifies omissible because this product holds no EEDD registration and writing one would invent a regulatory identity; `src/cadrumo/_data/registry/aeat/modelos/714/revisions`.
- [ ] `W02.P04.S131` - Decide modelo 100, which declares filing grade for an XML layout that refuses at render for want of a grounded aux version token; `src/cadrumo/_data/registry/aeat/modelos/100/revisions`.
- [x] `W02.P04.S132` - Report structurally when a revision ships a committed export tree while declaring a grade below filing; `dev/registry/analysis/modelo_capability.py`.
- [ ] `W02.P04.S133` - Re-review modelo 222, whose attestation reaches scheduling and applicability only and describes two casillas and no export layout while the revision now ships seventy-six casillas, a typed envelope and a committed tree; `src/cadrumo/_data/registry/aeat/modelos/222/revisions`.
- [ ] `W02.P04.S135` - Declare a revision-level deferral rationale slot, modelled on the casilla export-exemption reason, then author it for modelos 189, 280 and 345 whose 2025 revisions each carry a layout at applicability grade; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W02.P04.S138` - Report provenance findings on the reference that is outside rather than on every child citing it; `dev/registry/analysis/provenance_consistency.py`.
- [x] `W02.P04.S139` - Count the actionable unit in the screen runner census, not every site exhibiting it; `dev/registry/analysis/screens.py`.
- [x] `W02.P04.S140` - Stop counting the official part split as a finding in the suite census, since the screen reports it for visibility and not as a defect; `dev/registry/analysis/screens.py`.
- [x] `W02.P04.S141` - Report a revision that reaches filing grade with a layout while declaring no deadline window; `dev/registry/analysis/modelo_capability.py`.
- [ ] `W02.P04.S142` - Author deadline windows for the five filing-grade revisions declaring none: modelo 145's 2012-01-31-y-siguientes, 151's 2015-2022, 165's 2016-2022, 308's 2019-y-siguientes and 309's 2023-y-siguientes; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W02.P04.S143` - Report a filing-grade revision whose modelo claims a filing calculation class while declaring no formula; `dev/registry/analysis/modelo_capability.py`.
- [ ] `W02.P04.S144` - Resolve modelos 296, 308, 349 and 360, which claim a filing calculation class with no formula behind it; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W02.P04.S145` - Gate that a screen stating how many conditions it reports agrees with what it documents and emits; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [ ] `W02.P04.S146` - Resolve modelo 308's 2019-y-siguientes, the one filing-grade revision failing two capability axes at once, and decide whether the fourteen below-filing multi-axis revisions belong with it; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W02.P04.S147` - Author the missing Scope and Summary sections in the two feature documents whose attested body schema requires them; `.vault`.
- [x] `W02.P04.S151` - Document the distinction between a screen and an authoring aid in the contributor README, and how the gates tell them apart; `dev/registry/README.md`.
- [ ] `W02.P04.S436` - Restore the typed filing envelope on modelo 322 revision 2026-y-siguientes, which reverted to the record spelling its three predecessors did not use and so exports without the product software identity that revision 2024-2025 refuses to omit; `src/cadrumo/_data/registry/aeat/modelos/322/revisions`.

## Wave `W03` - filing-export proof made measurable

Turn the two-channel filing-export proof from a built-but-empty mechanism into one carrying real enrolled coordinates, so that a generated tree without a vector refuses as missing evidence rather than reading as unmeasured. Repairs the generated-source verifier that currently raises. Depends on W01 for its measurement surface and on W02 for the gate that would hold it.

### Phase `W03.P05` - generated source verifier repair

Repair the verifier that raises when probing a generated artefact source, which blocks the generated provenance path.

- [x] `W03.P05.S18` - Define the applicability probe the generated artefact source is missing so the verifier stops raising; `src/cadrumo/domain/calculations/registry/static_inspection.py`.
- [ ] `W03.P05.S19` - Prove the generated provenance path verifies one generated tree end to end; `src/cadrumo/application/registry/tests/test_generated_provenance_verifier.py`.
- [x] `W03.P05.S55` - Extract the source applicability overlap rule to one definition both the live source and its diagnostic copy delegate to; `src/cadrumo/domain/calculations/registry/schema_references.py`.
- [x] `W03.P05.S56` - Prove the diagnostic copy answers applicability identically to its source across the whole catalogue; `src/cadrumo/domain/calculations/registry/tests/test_static_generated_source_applicability.py`.
- [x] `W03.P05.S85` - Declare the generated-artefact inspection sources read-only so a richer source carrier satisfies the protocol; `src/cadrumo/domain/calculations/registry/static_inspection.py`.
- [x] `W03.P05.S86` - Re-render one revision from its authored inputs and byte-compare it against the shipped tree without publishing; `dev/registry/pipeline/render_check.py`.
- [ ] `W03.P05.S94` - Descend the record-design intermediate into printed subdivisions that carry distinct facts so each has a parser field to anchor; `src/cadrumo/domain/calculations/registry/record_design_pdf_state.py`.
- [ ] `W03.P05.S87` - Author the declarado repeat, its nine per-row casilla identities and the nine binding attributions once the parser gives each subdivision a field to anchor; `dev/registry/mappings/modelo_347`.
- [ ] `W03.P05.S88` - Republish only the four trees whose record bytes already match, never the two carrying record drift; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W03.P05.S89` - Separate record drift from a stale provenance attestation in the re-render comparison so a caller can tell which trees are safe to republish; `dev/registry/pipeline/render_check.py`.
- [x] `W03.P05.S90` - Pin both comparison outcomes against the revisions in the corpus that exhibit each; `dev/registry/tests/test_render_check.py`.
- [x] `W03.P05.S91` - Sweep every published generated tree and record which reproduce, which carry a stale attestation and which carry record drift; `dev/registry/pipeline/render_check.py`.
- [x] `W03.P05.S92` - Record why each non-reproducing generated tree does not reproduce and whether it is safe to republish; `dev/registry/pipeline/generated_tree_dispositions.toml`.
- [x] `W03.P05.S93` - Gate that every non-reproducing tree carries a live disposition and every disposition names a tree that still fails; `dev/registry/tests/test_render_check.py`.
- [ ] `W03.P05.S156` - Close the modelo 390 coverage hole, which declares revisions through 2025 while the current filing year resolves to nothing; `src/cadrumo/_data/registry/aeat/modelos/390/revisions`.

### Phase `W03.P06` - proof vector enrolment

Author filing-export conformance vectors as registry data for the generated trees and make an absent vector refuse rather than read as unmeasured.

- [x] `W03.P06.S102` - Point the three emitted-byte acceptance tests at the two-channel authority the coverage composer now requires, starting with the guard that an empty proof cannot become evidence; `dev/registry/tests/test_filing_emitted_byte_acceptance.py`.
- [ ] `W03.P06.S57` - Acquire one official emitted-byte reference for a single modelo revision, or an independently reviewed equivalent; the official corpus already holds record designs, forms, instructions, manuals, calendars, e-invoice schemas and GROI servlet responses, and no filled fichero; `src/cadrumo/_data/corpus/aeat_official`.
- [ ] `W03.P06.S20` - Declare the filing-export conformance vector schema as registry data beside the generation provenance; `src/cadrumo/domain/calculations/registry/schema_exports.py`.
- [ ] `W03.P06.S21` - Author the conformance vector for the modelo 303 twenty twenty five generated tree as the reference case; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2025/export/_conformance.vector.toml`.
- [ ] `W03.P06.S22` - Enrol filing export conformance vectors from official record-design examples, which the empty canonical tuples are honestly refusing in the meantime; `dev/registry/filing_export_proof.py`.
- [ ] `W03.P06.S23` - Gate that a generated tree carrying no conformance vector keeps refusing as missing evidence rather than reading as unmeasured; `src/cadrumo/application/filing/export_proof.py`.
- [ ] `W03.P06.S24` - Author the conformance vectors for the remaining generated trees; `src/cadrumo/_data/registry/aeat/modelos`.

## Wave `W04` - edge gates

Add the missing semantic gates on the edges between declaration axes: wire-type compatibility, grade earned from its prerequisites, and parent-consistent provenance, plus a regression guard on export-reference symmetry. Each reads the resolved surface through the W01 accessor and proves detector teeth against a constructed defect. Depends on W01.

### Phase `W04.P07` - wire type compatibility gate

Screen and then gate the mapping between a casilla's declared type and the type its rendered export field carries.

- [x] `W04.P07.S25` - Screen the declared casilla type against the type its resolved export field carries; `dev/registry/analysis/wire_type_compatibility.py`.
- [x] `W04.P07.S26` - Prove the wire-type screen against a constructed incompatible declaration; `dev/registry/tests/test_wire_type_compatibility.py`.
- [ ] `W04.P07.S27` - Declare the twenty-seven distinct casilla-to-wire type transitions as validated registry data, the largest being money to decimal and ratio to decimal; `src/cadrumo/domain/calculations/registry/export_value_policy.py`.
- [x] `W04.P07.S69` - Screen every monetary field for a wire type that applies no scale to the emitted digits; `dev/registry/analysis/monetary_scale.py`.
- [x] `W04.P07.S70` - Prove the monetary scale screen exempts the self-scaling wire types and reports the unscaled ones; `dev/registry/tests/test_monetary_scale.py`.
- [ ] `W04.P07.S75` - Publish the three enrolled trees that render but were never committed, using the operator publish verb that already reaches the publication authority: modelo 308 2019-y-siguientes, modelo 360 2010-y-siguientes and modelo 390 2022, against twenty-eight revisions that render and carry a publication manifest; `dev/registry/pipeline/_tree_publication.py`.
- [ ] `W04.P07.S71` - Declare the scale the official design specifies for each monetary field rendered by an unscaled wire type; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W04.P07.S72` - Gate that every monetary field declares a scale or is rendered by a self-scaling wire type; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W04.P07.S74` - Screen sibling amount fields of one record for disagreeing scale representations; `dev/registry/analysis/monetary_scale.py`.
- [x] `W04.P07.S78` - Measure whether the thirty-two footnoted corporate-tax amounts are also rendered unscaled; `dev/registry/analysis/monetary_scale.py`.
- [ ] `W04.P07.S76` - Refuse a bare footnote pointer as a stated wire fact, which cannot land until a field may be declared eligible with its representation unsupported: coverage is exact and evidence admits only official_source or reviewed_policy, so today the correction forces either twenty-nine invented policies or none at all; `dev/registry/pipeline/_render_profile.py`.
- [ ] `W04.P07.S77` - Prove the eligibility predicate treats a footnote-only content cell as stating no wire fact; `dev/registry/tests/test_render_profile.py`.
- [ ] `W04.P07.S79` - Author reviewed representation rules for the forty-one fields the eligibility correction newly admits, of which reading the eleven grounding notes shows twelve have wording that settles representation and twenty-nine have wording about applicability or cross-field agreement instead, so the latter must be derived from extent and type or stay advisory; `dev/registry/render_profiles`.
- [x] `W04.P07.S80` - Require a declared scale for every monetary export field in the new-modelo authoring checklist; `dev/registry/newmodelo/checklist.py`.
- [x] `W04.P07.S81` - Require a sibling-amount comparison in the authoring checklist and stop pinning the checklist item count in its tests; `dev/registry/newmodelo/tests`.
- [x] `W04.P07.S82` - Document which fields a render profile may govern and why a footnote reference removes one from its reach; `dev/registry/render_profiles/README.md`.
- [x] `W04.P07.S148` - Resolve a footnote pointer to the note it names, so the reviewed rules the eligibility correction makes due can be grounded in the design's own wording; `dev/registry/analysis/footnote_pointer_notes.py`.
- [ ] `W04.P07.S149` - Transcribe the thirteen bundled record designs that ship without an extracted text, which leaves evidence tooling blind to them; `src/cadrumo/_data/corpus/aeat_official/disenos_registro`.
- [x] `W04.P07.S150` - Make the pointer triage repeatable, deriving each design's transcription from the source reference rather than by searching its directory; `dev/registry/analysis/footnote_pointer_notes.py`.
- [x] `W04.P07.S387` - Report the fields whose wire fact sits behind a footnote pointer, deciding membership through the shipped eligibility predicate rather than a second copy of its clauses, and resolve each pointer to the note wording a reviewed rule would be grounded in; `dev/registry/analysis/footnote_only_wire_facts.py`.
- [x] `W04.P07.S388` - Pin the counterexample that stops a vocabulary miss being read as a note stating no wire fact, since modelo 200 nota 1 states a filling rule in full while carrying none of the words the reading aid looks for; `dev/registry/tests/test_footnote_only_wire_facts.py`.
- [x] `W04.P07.S389` - Retire the unreproducible one hundred and forty-nine: five bases measured through the live predicate give 41, 30, 80, 4,184 and 95, none of them 149 or 183, and the absent-naturaleza population that looked like a plausible provenance is already eligible so was never pending authoring; `dev/registry/render_profiles`.
- [x] `W04.P07.S390` - Scope note definitions to the sheet that prints them, since a workbook numbers each pages notes from one and modelo 200 defines Nota 1 on six of seventy-seven sheets, which the design-wide reader concatenated into one entry and used to resolve a pointer on a sheet defining no such note; `dev/registry/analysis/footnote_pointer_notes.py dev/registry/tests/test_footnote_pointer_notes.py`.
- [x] `W04.P07.S391` - Measure how far the design-wide note reading reached: 38 of 215 transcriptions repeat a note label across sheets, accounting for 225 definitions a design-wide reader absorbed, with modelo 303 carrying the condition in every revision and modelo 220 defining one label on twelve of thirteen sheets; `dev/registry/analysis/note_label_scope.py dev/registry/tests/test_note_label_scope.py`.
- [x] `W04.P07.S392` - Recognise a sheet heading that carries spaces, since capturing a single token matched DP200001 but failed on every sheet named like dr M202 (1), which sent an entire designs notes to an empty sheet name where no field could match them and read exactly like a design with no notes; `dev/registry/analysis/footnote_pointer_notes.py`.
- [x] `W04.P07.S393` - Accept the three separators the corpus uses between a note label and its wording, since requiring the colon made every note of modelo 202 invisible including the three that state how each AEAT type is aligned padded and signed; `dev/registry/analysis/footnote_pointer_notes.py`.
- [x] `W04.P07.S394` - Measure whether designs state their wire conventions once per AEAT type rather than per field, since modelo 202 settles alignment padding and sign for An Num and N in three general notes that no field cites, which would make the reviewed rules derivable from a handful of per-type conventions instead of authored one field at a time; `dev/registry/analysis`.
- [x] `W04.P07.S395` - Report the design notes that state a wire convention for a whole AEAT type, matching only codes the designs own fields carry: seventeen of thirty-one designs carry fifty-eight such notes resolving to forty-nine design-and-type pairs that govern 5,232 fields, which is the grounding the per-field pointer route does not have; `dev/registry/analysis/type_convention_notes.py dev/registry/tests/test_type_convention_notes.py`.
- [x] `W04.P07.S396` - Join the fields needing a reviewed rule against the type conventions their design states: of 41 fields, 9 are grounded and the 32 that are not collapse to two modelo-and-type pairs, both in modelo 200, which is the size the rules-authoring step should carry; `dev/registry/analysis/rule_grounding_coverage.py dev/registry/tests/test_rule_grounding_coverage.py`.
- [x] `W04.P07.S397` - Read the unnumbered NOTA lines the corpus carries, claiming only the shape that can be read without absorbing a neighbour, and leave what such a note governs unsettled: 47 of the 52 designs carry exactly one, so per-sheet counting distinguishes nothing, and modelo 200 prints its amounts convention on one sheet of seventy-seven while the fields it would govern sit elsewhere; `dev/registry/analysis/footnote_pointer_notes.py`.
- [x] `W04.P07.S398` - Settle what an unnumbered NOTA governs: modelo 200 states how amounts are written on a sheet carrying no amount field while the 5,665 fields it describes sit on 74 others, and corpus-wide 47 of 51 designs print one such note while 4 repeat one identical text and none differs by sheet, so the sheet is where these are found and the design is what they govern; `dev/registry/analysis`.
- [x] `W04.P07.S399` - Admit design-level unnumbered notes as grounding now that their scope is settled, which is what modelo 200s thirty-two ungrounded fields need since its amounts convention states their integer width sign and decimal places; `dev/registry/analysis/rule_grounding_coverage.py`.
- [x] `W04.P07.S400` - Write the verification criterion for the note-evidence work and replace the unreproducible field counts the rules-authoring and figure-recovery steps carried, with every figure taken from a screen that can be re-run; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W04.P07.S401` - Enrol the three screens the note-evidence work added, which the standing enrolment and README-table gates both refused until done, and project the grounding screen onto its residue so the runner does not carry two adjacent rows agreeing by construction; `dev/registry/analysis/screens.py dev/registry/README.md`.
- [x] `W04.P07.S402` - Widen the enrolment and README gates to discover a screen by either entry point, since two screens reading the design corpus present screen_corpus and the gate looking only for screen_authority passed while they sat unenrolled, and enrol them in a corpus table whose signature does not force arguments they ignore; `dev/registry/tests/test_declaration_invariant_gates.py dev/registry/analysis/screens.py dev/registry/README.md`.
- [x] `W04.P07.S403` - Declare the screen entry points once and route all six gates through it, since five carried their own copy of the narrow test and three never checked a corpus screens kinds counts or identity, and carry the modelo on the corpus findings the widened identity gate then found in breach; `dev/registry/analysis/screens.py dev/registry/tests/test_declaration_invariant_gates.py dev/registry/analysis/note_label_scope.py dev/registry/analysis/unnumbered_note_scope.py`.
- [x] `W04.P07.S404` - Name the encoding constant in the six modules this work added that passed a raw literal, and record that the convention one module describes as required by the tree holds at 44 sites against 138 that do not, so it is an aspiration rather than an established rule; `dev/registry`.
- [x] `W04.P07.S405` - Finish the pass over which screen population each gate sees: run both runners in the whole-corpus and no-mutation gates, and give the population gate the design transcriptions and their parsed notes plus a docstring saying it checks named populations rather than every screen; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W04.P07.S406` - Gate the gap between enrolment and execution so a table added without a runner fails by name, write the verification criterion for the nine narrow gates, and correct the breakdown that said five carried the module walk when two did; `dev/registry/tests/test_declaration_invariant_gates.py .vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W04.P07.S407` - Count the note a field itself cites as grounding, which is the strongest kind and was missing entirely: it covers 38 of the 41 fields and settles the three that modelo 200s amounts note cannot, since a one-character field is not fifteen integers and two decimals; `dev/registry/analysis/rule_grounding_coverage.py dev/registry/tests/test_rule_grounding_coverage.py`.
- [x] `W04.P07.S408` - Emit the authoring worklist grouped by the note that grounds each field, since the cost is readings not fields: forty-one fields resolve to eleven items and the largest covers twenty-six at one width, with each item carrying its widths so a note that cannot serve them all is visible; `dev/registry/analysis/rule_grounding_coverage.py dev/registry/tests/test_rule_grounding_coverage.py`.
- [x] `W04.P07.S409` - Read the eleven grounding notes and record which settle representation, since zero ungrounded is not a readiness signal: the largest work item covers twenty-six fields with a note stating who must fill them rather than how they are written; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W04.P07.S410` - Identify a grounding note by its design as well as its sheet and label, since grouping by label alone merged modelo 303s DP30302 nota 5 across three transcriptions where it carries 330 characters in one and 209 in another; `dev/registry/analysis/rule_grounding_coverage.py dev/registry/tests/test_rule_grounding_coverage.py`.
- [x] `W04.P07.S411` - Report note labels whose wording differs between a modelos designs, since 24 of the 111 keys shared across designs carry more than one text and modelo 200s DP200001 nota 1 appears in ten designs with two, so a rule carried forward by name can end up grounded in wording that changed; `dev/registry/analysis/note_text_drift.py dev/registry/tests/test_note_text_drift.py`.
- [x] `W04.P07.S412` - Flag a work item whose grounding note drifts between designs, since four of thirteen do and cover seven fields whose rules must be authored per design, with the flag passed in so it defaults to no claim rather than to a claim of stability; `dev/registry/analysis/rule_grounding_coverage.py dev/registry/tests/test_rule_grounding_coverage.py`.
- [ ] `W04.P07.S413` - Let a render profile declare a field eligible with its representation unsupported, since exact coverage plus a two-valued authority discriminator obliges an author to assert official source or reviewed policy for twenty-nine fields whose only located wording is about applicability; `dev/registry/pipeline/_render_profile.py dev/registry/render_profiles`.
- [x] `W04.P07.S414` - Rewrite the note-evidence criterion to record that zero ungrounded is not readiness: twelve of forty-one fields have wording that settles representation, four of thirteen notes drift between designs, and the correction is blocked on a profile that cannot declare a representation unsupported; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W04.P07.S424` - Read gates from each screens own entry point rather than the runner table, since projections hid four emitted kinds from the kind-naming gate including all three grounded kinds behind an empty residue, and guard the direction that holds by refusing a projection that reports a kind its screen never emits; `dev/registry/analysis/screens.py dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W04.P07.S427` - Record that all twenty-six unscaled monetary fields sit in filing-grade revisions rather than below it, and that a gate forbidding two conditions of one screen from firing on one revision would be wrong since per-field findings share a revision coordinate legitimately; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.

### Phase `W04.P08` - grade earned gate

Screen and then gate whether a declared authority grade is supported by its derived prerequisites or carries a reasoned disposition.

- [x] `W04.P08.S28` - Screen whether a declared authority grade is supported by its derived prerequisites; `dev/registry/analysis/grade_earned.py`.
- [x] `W04.P08.S29` - Prove the grade screen against a constructed unearned grade declaration; `dev/registry/tests/test_grade_earned.py`.

### Phase `W04.P09` - provenance parent consistency gate

Screen and then gate child citations against the source manifest of their owning revision.

- [x] `W04.P09.S30` - Screen child citations against the source manifest of their owning revision; `dev/registry/analysis/provenance_parent_consistency.py`.
- [x] `W04.P09.S31` - Prove the provenance screen against a constructed out-of-manifest citation; `dev/registry/tests/test_provenance_parent_consistency.py`.
- [x] `W04.P09.S415` - Separate a reference absent from every revision of its modelo from one missing between manifests that agree elsewhere: the 1,389 index rows are 414 references of which 213 are systemic and 201 are drift, and the per-revision index cannot tell the two corrections apart; `dev/registry/analysis/provenance_consistency.py dev/registry/tests/test_provenance_consistency.py`.
- [x] `W04.P09.S416` - Rule out a dangling reference in the provenance population and report where to look first: all 414 pairs resolve in catalogues of 1,374 legal and 499 source ids, seventeen references are cited by a single child and ninety-nine by a hundred or more; `dev/registry/analysis/provenance_consistency.py`.
- [x] `W04.P09.S417` - Screen the mirror direction, 263 manifest references no child cites, since the two surfaces disagree both ways: 59 revisions declare a subset of what their children cite and 69 declare references nothing cites, so the citing-side population measures a contract nobody declared; `dev/registry/analysis/provenance_consistency.py dev/registry/tests/test_provenance_consistency.py`.
- [ ] `W04.P09.S418` - Decide what a revision manifest declares relative to its childrens citations before correcting either side, since the two disagree in both directions and no rule states which contains which; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W04.P09.S419` - Give the mirror condition its own module so the runner reports it, since it landed reachable only from source and the runner showed the citing side alone, which is the invisibility failure this package had just corrected elsewhere; `dev/registry/analysis/manifest_uncited_references.py dev/registry/tests/test_manifest_uncited_references.py dev/registry/analysis/screens.py dev/registry/README.md`.
- [x] `W04.P09.S420` - Test a published export tree by its generation provenance manifest rather than by the directory that also holds authored layout fragments, and record that modelos 185 and 222 ship published filing bytes for revisions declaring applicability grade; `dev/registry/analysis/modelo_capability.py`.
- [ ] `W04.P09.S421` - Resolve the contradiction in modelos 185 and 222 revision 2025-y-siguientes, which ship a provenance-attested published export tree while declaring applicability grade, so the registry says they cannot file and the repository ships their filing bytes; `src/cadrumo/_data/registry/aeat/modelos/185 src/cadrumo/_data/registry/aeat/modelos/222`.
- [x] `W04.P09.S422` - Retire the capability condition that duplicates the grade screen: its 25 revisions are exactly the grade screens under-declared findings whose prerequisite is export_layout, set-equal both ways, so one stated a symptom the other states as a conclusion naming its cause; `dev/registry/analysis/modelo_capability.py`.
- [x] `W04.P09.S423` - Sweep every screen condition for a duplicated population and record the negative result: none is identical to another, subset relations at revision granularity are arithmetic rather than meaning, and population identity is a coincidence rather than an invariant so it must not become a gate; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W04.P09.S425` - Report the six filing-grade revisions whose declared window spans years no deadline covers, giving the undated-year computation one home in the temporal screen rather than parsing it back out of that screens finding prose; `dev/registry/analysis/modelo_capability.py dev/registry/analysis/temporal_site_agreement.py dev/registry/tests/test_modelo_capability.py`.
- [ ] `W04.P09.S426` - Declare deadline windows for the eleven filing-grade revisions that cannot date a filing: five carry none at all and six leave years of their own closed window uncovered, modelo 347 for seven years of fourteen; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W04.P09.S428` - Report how much of every screen condition sits in a filing-grade revision, counting findings that carry no revision as unmeasured rather than as safe, since eight of eleven conditions that first appeared to have no filing exposure had never been graded at all; `dev/registry/analysis/filing_exposure.py dev/registry/tests/test_filing_exposure.py`.
- [x] `W04.P09.S429` - Correct the exposure report which counted the wire-type screens census of 13,624 examined transitions as findings where 29 diverge, by carrying each screens runner count beside the population measured so a census is visible without a declaration that does not exist; `dev/registry/analysis/filing_exposure.py dev/registry/tests/test_filing_exposure.py`.
- [x] `W04.P09.S430` - Declare on the runner table whether a screens entry point returns findings or a census, since nothing said so and inferring it counted 13,624 examined transitions as defects, and state plainly that no mechanical test can verify the declaration because a findings screen may project onto a smaller subset than the census does; `dev/registry/analysis/screens.py dev/registry/analysis/filing_exposure.py dev/registry/tests/test_filing_exposure.py`.
- [x] `W04.P09.S431` - Rank fileable revisions by how many distinct conditions name them, since 67 of 69 carry at least one and choosing work by condition means touching nearly every revision, with modelo 200 2025-y-siguientes carrying nine; `dev/registry/analysis/filing_exposure.py dev/registry/tests/test_filing_exposure.py`.
- [ ] `W04.P09.S432` - Resolve the five revisions declaring filing grade without the completeness manifest their grade requires, in modelos 145, 165 twice, 308 and 360, since every other grade finding under-declares and these five over-declare; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W04.P09.S433` - Declare which screen a screen is built on and exclude derived screens from the revision ranking, since the grounding screen re-describes the pointer screens 41 findings and made modelo 200 look like nine conditions where seven are independent, gating the containment that is verifiable; `dev/registry/analysis/screens.py dev/registry/analysis/filing_exposure.py dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W04.P09.S434` - Sweep for other undeclared screen derivations and record that none exists: the two flags are a CLI-only import and a screen consuming others for attributes rather than population, so import-reach is a prompt not a verdict, and give both entry types the same declarations; `dev/registry/analysis/screens.py`.
- [x] `W04.P09.S435` - Verify the record-spelled envelope consequence in the shipped export path rather than from the screens docstring, confirming that renders_filing_envelope is set from the typed slot alone and that all eighteen typed layouts declare a product identity requirement while the thirty-one record-spelled ones cannot; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W04.P09.S437` - Compare a revisions declared capability with its predecessors in the same modelo, since nothing does: modelo 322 lost its typed envelope and product identity requirement between two consecutive filing-grade revisions and the capability screen reports each revision alone; `dev/registry/analysis`.
- [x] `W04.P09.S438` - Retire the spent ordering constraint in the parallelization prose, which carried the retired 183 figure and sequenced the predicate ahead of publication to prevent a conversion that has already happened, since all forty-one newly eligible fields sit in revisions whose trees are published; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W04.P09.S439` - Re-measure all three parallelization constraints: the generator verb is registered and its lifted status holds, the conformance vector tuple is still empty so that constraint binds, and the unpublished renderable trees are three not two in modelos 308, 360 and 390; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W04.P09.S440` - Re-measure the registry directorys failure figures: 1,152 passing and 36 failing with 30 in the four generated-tree modules, against the twenty-seven of thirty-five written in the constraint, and confirm the single conformance failure the third constraint rests on; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.

### Phase `W04.P10` - export reference symmetry guard

Keep the casilla-to-export-field edge symmetric with a regression guard proven against a constructed defect.

- [x] `W04.P10.S32` - Restate the export-reference guard as a regression guard proven by constructed fixture; `dev/registry/tests/test_export_ref_symmetry.py`.

## Wave `W05` - temporal and identity data corrections

Correct the registry data defects the audit recorded that need no architectural decision: the ambiguous selection coordinate, the revision directory names that misstate their own windows, and the forward-dated authorisation years. Each rename is an identifier change and moves code, tests, generated output and stamps atomically. Requires operator approval before any rename lands.

### Phase `W05.P11` - selection ambiguity correction

Resolve the ambiguous filing coordinate so temporal selection refuses nothing that law can decide.

- [ ] `W05.P11.S33` - Consult declared validity bounds during temporal selection so an ad-hoc coordinate resolves without an operation date; `src/cadrumo/domain/calculations/registry/temporal.py`.
- [ ] `W05.P11.S34` - Prove the modelo 308 twenty eleven coordinate resolves and that a genuinely ambiguous one still refuses; `src/cadrumo/domain/calculations/registry/tests/test_temporal_selection.py`.
- [x] `W05.P11.S60` - Screen each revision's window, period selector and deadline windows against one another; `dev/registry/analysis/temporal_site_agreement.py`.
- [x] `W05.P11.S61` - Prove the temporal site screen detects a deadline year moved outside its declared window; `dev/registry/tests/test_temporal_site_agreement.py`.

### Phase `W05.P12` - revision identifier corrections

Rename the revision directories whose names misstate the window they declare, atomically across every referencing surface.

- [ ] `W05.P12.S35` - Rename the modelo 151 revision whose name claims 2025 while its window opens in 2023; `src/cadrumo/_data/registry/aeat/modelos/151/revisions`.
- [ ] `W05.P12.S36` - Rename the modelo 185 revision whose name claims 2025 while its window opens in 2026; `src/cadrumo/_data/registry/aeat/modelos/185/revisions`.
- [ ] `W05.P12.S37` - Rename the modelo 720 revision whose name claims 2013 while its window opens in 2012; `src/cadrumo/_data/registry/aeat/modelos/720/revisions`.
- [ ] `W05.P12.S38` - Rename the modelo 322 revision whose name claims a 2008 to 2022 span while it declares 2022 only; `src/cadrumo/_data/registry/aeat/modelos/322/revisions`.
- [ ] `W05.P12.S39` - Close or rename the modelo 194 revision named for a single year while declared open-ended; `src/cadrumo/_data/registry/aeat/modelos/194/revisions`.
- [ ] `W05.P12.S40` - Close or rename the modelo 721 revision named for a single year while declared open-ended; `src/cadrumo/_data/registry/aeat/modelos/721/revisions`.
- [ ] `W05.P12.S41` - Correct the forward-dated enrolled years on the modelo 202 authorisation entry; `src/cadrumo/_data/registry/aeat/authorization.d/202.toml`.
- [ ] `W05.P12.S42` - Gate a revision directory name against the window the revision declares; `src/cadrumo/domain/calculations/registry/validate_revision_identity.py`.
- [x] `W05.P12.S53` - Screen every revision directory name against the temporal window the revision declares; `dev/registry/analysis/revision_name_window.py`.
- [x] `W05.P12.S54` - Prove the name-window screen against a declared window moved away from its name; `dev/registry/tests/test_revision_name_window.py`.

## Wave `W06` - declaration contract

Decide and then apply the general declaration contract that makes restatement unconstructable rather than merely detected: every field owned, derived, or attesting to an owned fact. Governs the temporal, identity, provenance and value-semantics axes together. Entirely gated on four architectural decisions that do not yet exist, so every Step here is authoring or migration that cannot begin until those records are accepted.

### Phase `W06.P13` - declaration contract decisions

Author the four architectural decision records the contract requires before any migration can begin.

The Phase holds more than that heading says, and it is left standing rather than quietly widened
because the Steps carry its identifier and a rename would orphan every reference to them. Counted
rather than estimated: of its 168 Steps, 80 name a decision or a record under `.vault`, 83 name
development tooling, two name `src` and three name something else. So the heading describes about
half of what is here, not a corner of it - and the other half is the tooling those decisions turned
out to need, the screens that measure each declaration condition and the gates that hold them.

Inside that tooling half a third strand grew unplanned, and it is worth naming because no heading
anywhere covers it: the work of proving an instrument can still see what it measures. It exists
because a figure this plan quoted was wrong four separate times, and each correction found the same
shape - a screen, a probe or a gate reporting a clean result it was no longer able to earn. A future
plan should give that its own Phase from the start; this one records where it actually happened.

- [x] `W06.P13.S43` - Decide the declaration-kind contract of owned, derived and attesting fields; `.vault/adr`.
- [x] `W06.P13.S44` - Decide the temporal identity contract, its coverage evidence record and the non-temporal axis slot; `.vault/adr`.
- [x] `W06.P13.S58` - Screen every casilla identifier into a named grammar and report which modelos mix grammars; `dev/registry/analysis/casilla_id_grammar.py`.
- [x] `W06.P13.S59` - Prove the grammar screen refuses to absorb an unclassifiable page-qualified tail; `dev/registry/tests/test_casilla_id_grammar.py`.
- [x] `W06.P13.S45` - Decide the casilla identifier grammar contract and its per-modelo declaration; `.vault/adr`.
- [x] `W06.P13.S46` - Decide the casilla-to-wire type derivation contract and its attested overrides; `.vault/adr`.
- [x] `W06.P13.S65` - Screen cross-revision continuity chains for grammar crossing, singletons and orphan evolutions; `dev/registry/analysis/continuity_integrity.py`.
- [x] `W06.P13.S66` - Gate that no continuity chain crosses an identifier grammar and no evolution names a chain that does not exist; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W06.P13.S99` - Prove the continuity screen detects a chain crossing a grammar and an evolution naming a chain no casilla carries; `dev/registry/tests/test_continuity_integrity.py`.
- [ ] `W06.P13.S134` - Decide a typed slot for withheld promotion, since a revision can declare a family inapplicable but cannot record why it carries filing machinery at a lower grade; `src/cadrumo/domain/calculations/registry/schema.py`.
- [x] `W06.P13.S164` - Census the public names more than one module defines, classifying entrypoint convention, typing overload, cross-layer and same-layer collisions; `dev/quality/name_collision_census.py,dev/quality/tests/test_name_collision_census.py`.
- [x] `W06.P13.S165` - Canonicalise the export record encoding spelling in the provenance fixtures onto the ExportEncoding enum; `dev/registry/tests/test_provenance_manifest.py`.
- [x] `W06.P13.S166` - Report that the closed-vocabulary enum conversion reclassified 141 semantically unchanged export records as record drift; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S167` - Teach the render comparison to separate a changed serializer from a changed value, so record drift names a tree whose meaning moved; `dev/registry/pipeline/render_check.py,dev/registry/tests/test_render_check.py`.
- [x] `W06.P13.S168` - Key the generated tree disposition gate on the explained state rather than on byte equality; `dev/registry/pipeline/render_check.py,dev/registry/tests/test_render_check.py`.
- [x] `W06.P13.S169` - Route the generated tree byte comparison through the same parse helper the render comparison uses; `dev/registry/tests/test_generated_export_trees.py,dev/registry/pipeline/render_check.py`.
- [x] `W06.P13.S170` - Carry the workbook evidence tier as the typed enum its own signature already declared; `dev/registry/parity/_workbook_parity.py`.
- [x] `W06.P13.S171` - Separate the twice-reproducible determinism claim from the shipped-tree equality claim in the envelope proof; `dev/registry/tests/test_m303_generated_envelope_proof.py`.
- [x] `W06.P13.S172` - Report every test module the default lane cannot select, separating a module in another lane from one no lane selects at all; `dev/quality/default_lane_visibility.py,dev/quality/tests/test_default_lane_visibility.py`.
- [x] `W06.P13.S173` - Adjudicate every same-layer name collision and gate that each stays explained and each explanation stays live; `dev/quality/name_collision_dispositions.toml,dev/quality/tests/test_name_collision_dispositions.py`.
- [x] `W06.P13.S174` - Report constants whose name carries more than one value and gate that no public name does; `dev/quality/constant_value_agreement.py,dev/quality/tests/test_constant_value_agreement.py`.
- [x] `W06.P13.S175` - Keep the evidence tier change inside the reviewed module size rather than raising the baseline; `dev/registry/parity/_workbook_parity.py`.
- [x] `W06.P13.S176` - Measure the load census residue left by the concurrent rename campaign and record it as inherited rather than adjudicating another writer's moving modules; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S177` - Measure type declarations sharing a field shape and establish that shape identity is not concept identity, so no gate follows; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S178` - Confirm this campaign's gates are lane-reachable and report the conformance files that no lane path covers; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S179` - Retire the lane screen's duplicate reachability assertion and scope it to the question the canonical gate does not answer; `dev/quality/default_lane_visibility.py,dev/quality/tests/test_default_lane_visibility.py`.
- [x] `W06.P13.S180` - Reconcile the reachability gate's location note with the directory it actually occupies; `dev/tests/test_lane_reachability.py`.
- [ ] `W06.P13.S181` - Name dev/registry/conformance/tests in the dev tooling lane, accepting the three-minute serial floor its live-mode closure test imposes, or split that test out first; `justfile`.
- [x] `W06.P13.S182` - Establish the red the conformance lane will inherit and separate it from a concurrent writer's transient import breakage; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S183` - Record in the plan Description how the declaration question extended from the registry to the codebase and which screens were declined; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S184` - Report the operator path leaked into a sibling campaign's committed audit and confirm this feature's documents carry none; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S185` - Compose the development closure refusal vocabulary from the application's instead of restating its seven values; `dev/registry/conformance/closure.py`.
- [x] `W06.P13.S186` - Remove the constants orphaned by deleting the retired audit command's models; `dev/registry/conformance/manager.py`.
- [x] `W06.P13.S187` - Gate that the development refusal vocabulary keeps containing the application's and adds only the locally owned reasons; `dev/registry/conformance/tests/test_closure.py`.
- [x] `W06.P13.S189` - Remeasure the cross-package private imports reachable from dev and correct the promotion Step to name the surface that actually carries them; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S190` - Name the revision render input assembly so the publication path can obtain the same seven values the comparison derives; `dev/registry/pipeline/render_check.py`.
- [x] `W06.P13.S191` - Gate that the derived render inputs keep supplying every revision-describing value the publication limb requires; `dev/registry/tests/test_generated_tree_publication.py`.
- [x] `W06.P13.S192` - Apply the empty-population defence to this campaign's own gates, which two of them lacked; `dev/quality/tests/test_name_collision_dispositions.py,dev/quality/tests/test_default_lane_visibility.py`.
- [x] `W06.P13.S193` - Establish that the empty filing export proof authority refuses rather than passing, and correct the enrolment Step to name its real blocker; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S194` - Establish that the closure test rewrite is blocked behind vector enrolment and record the ordering constraint; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S195` - Distinguish a crashed pytest worker from a failing assertion and re-run the affected path serially before concluding; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S196` - Sweep every recorded run in this campaign for lost-worker markers and establish that its headline numbers are from clean runs; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S197` - Add the measurement integrity criterion that the four failed measurements make due; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S198` - Settle the crashed-worker test serially and attribute the feature health warnings to the untracked scaffold that carries them; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S199` - Attempt to size the footnote-pointer correction and establish that the first measurement read an attribute the object does not carry; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S200` - Take the footnote sizing again from the record design intermediate and bound the result to the designs actually read; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S201` - Sweep every registry-reachable record design for bare footnote pointers and put the correction's premise in question; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S202` - Take a lane measurement that reconciles its own collected count against its result and carries no lost-worker markers; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S203` - Withdraw the stale-scope finding after splitting the fifteen by Step state and reading what each scope names; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S204` - Ground the temporal axis migration in the modelo 720 revision whose opening year makes its own record design unloadable; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S205` - Read the four misstated revision openings against the windows and selectors they declare and separate the naming errors from the under-declaration; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S206` - Split the misstated opening condition by direction and withdraw the selector condition that reported thirty five correct declarations; `dev/registry/analysis/revision_name_window.py,dev/registry/tests/test_revision_name_window.py`.
- [x] `W06.P13.S207` - Report the five revisions declaring an open-ended window their selector does not carry, after confirming every member refuses the year beyond its name; `dev/registry/analysis/revision_name_window.py,dev/registry/tests/test_revision_name_window.py`.
- [x] `W06.P13.S208` - Stop the single-year condition contradicting the unselectable-window condition on the five revisions both were reporting; `dev/registry/analysis/revision_name_window.py,dev/registry/tests/test_revision_name_window.py`.
- [x] `W06.P13.S209` - Establish that the modelo 369 schemes disambiguate by period family and withdraw the unreachability the probe appeared to show; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S210` - Probe revision selection with the codes each revision declares, so a wrong-shaped question cannot be read as a registry refusal; `dev/registry/analysis/revision_selection_probe.py,dev/registry/tests/test_revision_selection_probe.py`.
- [x] `W06.P13.S211` - Sweep every modelo with the declared-code probe and teach it to ask a well-formed question at a mid-year revision split; `dev/registry/analysis/revision_selection_probe.py,dev/registry/tests/test_revision_selection_probe.py`.
- [x] `W06.P13.S212` - Retry only an ambiguity refusal with a date, halving the probe suite runtime that was driving worker crashes; `dev/registry/analysis/revision_selection_probe.py`.
- [x] `W06.P13.S213` - Add the category membership criterion the three withdrawn and narrowed conditions make due; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S214` - Measure the plan's duplicated top-level sections against the template and establish that they predate this campaign; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S215` - Merge the plan's triplicated Description and Verification and duplicated Parallelization into one of each, proving no paragraph was lost; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S216` - Move the acceptance criteria out of Parallelization where the duplicated structure had them accumulating and retire the superseded opener; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S217` - Correct the revision name screen's stated condition count that this campaign's own parity gate caught after the conditions were split; `dev/registry/analysis/revision_name_window.py`.
- [x] `W06.P13.S218` - Reconcile the four superseded criterion wordings the similarity merge could not judge, preserving the unique clause in each; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S219` - Reconcile the two Description paragraphs whose screen counts disagreed, settling the count against the entry point rather than by length; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S220` - Retire the Steps-count claim that goes stale and record that the name-window findings were already stepped; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S221` - Prove the two revision-name conditions the corpus never exercises and gate that every documented condition is reachable; `dev/registry/tests/test_revision_name_window.py`.
- [x] `W06.P13.S222` - Sweep every screen for conditions documented but never emitted and establish that only the revision-name screen carried the defect; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S223` - Ground the twenty-one load classifications by measuring which modules a real load imports rather than which the graph reaches; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S224` - Repoint the load classification member the canonicalisation renamed and separate the one ambiguous stale name from the twelve outside the census universe; `dev/registry/analysis/load_census_classification.py`.
- [x] `W06.P13.S225` - Separate the thirteen stale census entries into a universe too narrow, a rule that over-claims and one missing module; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S226` - Include ancestor packages in the census universe so a rule naming a package a load actually holds stops reading as stale; `dev/registry/analysis/load_census.py,dev/registry/analysis/load_census_classification.py`.
- [x] `W06.P13.S227` - Correct the classification measured in the tooling's own process against a clean load in both regimes; `dev/registry/analysis/load_census_classification.py`.
- [x] `W06.P13.S228` - Re-verify every live classification against clean cold and warm loads and reclassify the one that differs between regimes; `dev/registry/analysis/load_census_classification.py`.
- [x] `W06.P13.S229` - Measure every live classification against both regimes and separate the eleven that never load from the twenty-nine that load only cold; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S230` - Screen every live classification against a clean load in both cache regimes so the forty unsupported claims are reproducible; `dev/registry/analysis/load_claim_verification.py,dev/registry/tests/test_load_claim_verification.py`.
- [x] `W06.P13.S231` - Record why the selection probe and the load-claim screen sit outside the single-registry entry point and confirm both are lane-selected; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S232` - Record that this campaign's eighty findings use a heading format the audit's preceding hundred and thirty-one do not; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S233` - Correct the heading-format count after establishing which prose headings are findings and which are section headers; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S234` - Convert twenty-six of the seventy-seven unstructured findings to the audit's own heading format, assigning each severity from its content; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S235` - Convert eighteen more findings and mark the withdrawn one at its own heading so the correction is discoverable there; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S236` - Convert nineteen more findings and reconcile the lane against its own collection at 1323; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S237` - Finish converting the seventy-seven findings to the audit's heading format and verify slug uniqueness and severity vocabulary; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S238` - Rule the newly added module by measurement and guarantee the warm probe is actually warm; `dev/registry/analysis/load_census_classification.py,dev/registry/analysis/load_claim_verification.py`.
- [x] `W06.P13.S239` - Identify the third import-graph blind spot behind the last stale member, a class named by string rather than imported; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S240` - Establish that this campaign's lane figures and the CI dev-tooling selection overlap in one directory of eighteen; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S241` - Measure which dev test directories no recipe or workflow names and size what they contain; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S242` - Establish that dev/source_connectivity/tests is already reached through the pyproject testpaths default lane, retiring the premise that it needs naming; `justfile`.
- [ ] `W06.P13.S243` - Name dev/tui/tests in a lane; its thirty-nine tests are the one file the reachability gate reports outside every lane path scope, and its coverage-table failure is now repaired; `justfile`.
- [x] `W06.P13.S244` - Establish what the never-run TUI suite reports and confirm its single failure is a coverage table naming absent interfaces; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S245` - Establish what the never-run source connectivity suite reports and separate its environmental errors from its drifted hashes; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S246` - Classify the last source connectivity failure as another writer's mid-edit syntax error rather than a suite defect; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S247` - Re-read the ninth failure once the tree parsed and record that a transient had masked a real locator drift; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S248` - Attempt the CI dev tooling selection and reject the result when its collection and its tally disagree by two hundred and sixty-three tests; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S249` - Retry the CI selection at low parallelism and record that the retry's own exit line is unusable because it was piped; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S250` - Establish that the fourth uncovered test directory is a package outliving the tests it declared; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S251` - Point the three corrected findings at their corrections from their own headings; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S252` - Diagnose the sixteen vacuity screen failures as a git dependency added without updating the temp-tree fixtures; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S253` - Establish that the import-linter boundary proofs fail while the contracts themselves pass, and that the default lane deselects them; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S254` - Bound the crashed run's usable lower bound across fifty-two modules and stop mining it rather than drifting off the registry; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S255` - Record the second live sibling-scale disagreement in modelo 353 and correct the criterion asserting there is one; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [ ] `W06.P13.S256` - Correct the modelo 353 casilla 10 declared scale against the official record design for the 2026 revision; `src/cadrumo/_data/registry/aeat/modelos/353`.
- [x] `W06.P13.S257` - Verify which screen condition each half of the monetary criterion counts before restating its figures; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S258` - Correct the claim that the modelo 353 defect is new, since the audit already records that field as unscaled; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S259` - Establish that the sibling-count assertion was already false when its module entered this campaign's measurements; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S260` - Date every current registry failure against this campaign's own lane logs and correct the publication attribution; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S261` - Diagnose the static inspection boundary failure as four application modules reaching the inspection authority since late August; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S262` - Break the embed classification failure into its three conditions and name the seven modules the refactor left unclassified; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S263` - Enrol this campaign's own footnote pointer screen in the regulatory prose parser channel it had been failing; `dev/registry/analysis/regulatory_prose_parser_channel.toml`.
- [x] `W06.P13.S264` - Restore the adjudication deleted while its collision remained and adjudicate the new destination-id collision; `dev/quality/name_collision_dispositions.toml`.
- [x] `W06.P13.S265` - Watch the newly collapsed marker verdict extractor in the canonical definitions gate and correct the claim that it was merely removed; `dev/tests/test_canonical_definitions_stay_singular.py`.
- [x] `W06.P13.S266` - Record that the contract conflict lost its optimiser-erased guard while the two contracts still differ; `dev/quality/name_collision_dispositions.toml`.
- [x] `W06.P13.S267` - Measure the CI dev tooling selection to a reconciling total and record what the pipe cost the breakdown; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S268` - Correct the lane criterion to name which lane each figure describes; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S269` - Replace the stale failure accounting with a dated one and record that one failure did belong to this plan; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S270` - Establish that a gate checking the plan's own figures is forbidden by the code-stands-alone mandate and record what replaces it; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S271` - Retire the self-referential criteria count and distinguish live figures from historical ones; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S272` - Derive the no-layout refusal fixture instead of naming a revision that has since been published; `dev/registry/tests/test_render_check.py`.
- [x] `W06.P13.S273` - Record what must replace the name-window test pinned to a revision the plan has an open Step to rename; `dev/registry/tests/test_revision_name_window.py`.
- [x] `W06.P13.S274` - Give every test pinned to a stepped defect its replacement instruction; `dev/registry/tests/test_revision_name_window.py`.
- [x] `W06.P13.S275` - Split the generated-tree ledger from the manifest-staleness assertion; `dev/registry/tests/test_render_check.py dev/registry/pipeline/generated_tree_dispositions.toml`.
- [x] `W06.P13.S276` - Record the twenty-one attestations a generator refactor left stale; `dev/registry/tests/test_render_check.py dev/registry/pipeline/generated_tree_dispositions.toml`.
- [x] `W06.P13.S277` - Repoint the TUI coverage table at the interface the flows refactor left it naming; `dev/tui/_coverage.py`.
- [x] `W06.P13.S278` - Correct the three name-window replacement instructions that named successors themselves stepped for rename; `dev/registry/tests/test_revision_name_window.py`.
- [x] `W06.P13.S279` - Correct the source-connectivity Step figure against a live collection and record the authority startup cost; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S280` - Re-measure the conformance closure test that hit the per-test timeout ceiling on an uncontended host before naming its directory in a lane; `dev/registry/conformance/tests/test_closure.py`.
- [x] `W06.P13.S281` - Establish that the src-to-dev boundary survived the marker-gate deletion, so no coverage hole exists; `dev/tests/_marker_metadata_patterns.py`.
- [x] `W06.P13.S282` - Restore a marker-integrity gate over test names from the orphaned pattern table its deleted consumer left behind; `dev/tests/_marker_metadata_patterns.py`.
- [x] `W06.P13.S283` - Rename the four development-tree test symbols that carried a plan step id, and redeem the pin that expected them; `dev/locales/tests/test_ledger_notice_action_conformance.py dev/registry/tests/test_modelo_303_semantic_maps.py dev/source_connectivity/tests/test_census_completeness.py dev/tests/test_suggestion_command_conformance.py dev/tests/test_campaign_marker_patterns.py`.
- [x] `W06.P13.S284` - Remove the plan-step citations from the registry tooling prose, leaving only the detector fixtures that must carry them; `dev/registry/pipeline/_tree_check.py dev/registry/pipeline/_tree_publication.py dev/registry/pipeline/_tree_validation.py dev/registry/analysis/m303_semantic_census.py dev/registry/tests/test_record_design_intermediate_source_boundary.py`.
- [x] `W06.P13.S285` - Give the marker scan module-scoped lint discrimination so an explained suppression is not read as campaign metadata; `dev/tests/_marker_metadata_patterns.py dev/tests/test_campaign_marker_patterns.py`.
- [ ] `W06.P13.S286` - Replace the plan-phase owning_authority values in the workspace action denominator with a durable authority, coordinating with that surface's writer; `dev/quality/modelo_workspace_action_denominator.py`.
- [x] `W06.P13.S287` - Remove three restatements from the plan prose and record the cross-Wave evidence dependency once; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S288` - Give the two superseded consolidated positions the forward pointers their precedence claims required; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S289` - Make the selection probe record the ambiguity its own retry was erasing, and re-ground the temporal criterion on the measured figure; `dev/registry/analysis/revision_selection_probe.py dev/registry/tests/test_revision_selection_probe.py`.
- [x] `W06.P13.S290` - Hold the sibling-scale pin by coordinate identity instead of a count that failed when the screen detected a second defect; `dev/registry/tests/test_monetary_scale.py`.
- [x] `W06.P13.S291` - Sweep the screen tests for frozen live-corpus counts and hold the two survivors by identity; `dev/registry/tests/test_continuity_integrity.py`.
- [x] `W06.P13.S292` - Replace the drifted proportion in the screen census and state that the eligibility figure has no reproducer in this tree; `dev/registry/analysis/screens.py dev/registry/analysis/footnote_pointer_notes.py`.
- [x] `W06.P13.S293` - Re-ground the gate and detector-proof figures on the live module and verify the nine screen-property gates exist; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S294` - Correct the accessor criterion to the two drop proofs that exist and say which paths they cover; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S295` - Declare the year-level temporal sites as data and gate each path against the live schema; `dev/registry/analysis/temporal_site_agreement.py dev/registry/tests/test_temporal_site_agreement.py`.
- [x] `W06.P13.S296` - Verify the validator-module figure against the package and give it a re-derivable form; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S297` - Record that one name-window condition is refused upstream and is a canary, and refine the validator-family claim to the agreement subset; `dev/registry/analysis/revision_name_window.py .vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S298` - Prove the one declared screen condition that was silent and unexercised, and pair it with its live-corpus silence; `dev/registry/tests/test_temporal_site_agreement.py`.
- [x] `W06.P13.S299` - Give the continuity screen a per-definition function so its two detector proofs assert the reported kind rather than the index beneath it; `dev/registry/analysis/continuity_integrity.py dev/registry/tests/test_continuity_integrity.py`.
- [x] `W06.P13.S300` - Declare the name-window screen's kinds and retire the four-regex source extraction that recovered them; `dev/registry/analysis/revision_name_window.py dev/registry/tests/test_revision_name_window.py`.
- [x] `W06.P13.S301` - Re-measure the CI lane selection to a reconciling total and move the reassembly gate onto the syntax tree; `dev/registry/tests/test_declaration_invariant_gates.py .vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S302` - Attribute the fourteen registry lane errors to a blocker-authority compile that does not finish, and name the recompilation-inside-comparison shape; `dev/registry/analysis/m200_2024_blocker_adjudications.py`.
- [x] `W06.P13.S303` - Adjudicate the availability_label collision the census surfaced and record the three-fold promoted_candidate_ids restatement; `dev/quality/name_collision_dispositions.toml`.
- [x] `W06.P13.S304` - Scrub the two operator home paths that reddened the documentation privacy gate and return the quality directory to green; `.vault/audit/2026-08-27-calculation-correctness-campaign-restrictive-default-sweep-audit.md .vault/audit/2026-09-02-object-name-declustering-pilot-rehearsal-audit.md`.
- [x] `W06.P13.S305` - Name the returned step-id symbol in the marker gate's failure and refuse the cosmetic repair; `dev/tests/test_campaign_marker_patterns.py`.
- [ ] `W06.P13.S306` - Migrate the M200 2024 cohort vocabulary off its plan step ids across five files, two public function names, five refusal messages, seven docstrings and one test name, with the owning campaign; `dev/registry/analysis/m200_2024_blocker_adjudications.py dev/registry/tests/test_m200_2024_blocker_adjudications.py`.
- [x] `W06.P13.S307` - Name the encoding once in the three modules this campaign gave bare UTF-8 literals; `dev/tests/test_campaign_marker_patterns.py dev/registry/tests/test_declaration_invariant_gates.py dev/registry/tests/test_render_check.py`.
- [x] `W06.P13.S308` - Re-check the held-file constraint against the live worktree and separate it from this execution's scope limit; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S309` - Collapse the modelo-id helper repeated in all ten screen modules into one canonical defining module; `dev/registry/analysis/corpus.py dev/registry/analysis`.
- [x] `W06.P13.S310` - Give the pipeline's two duplicated path guards one home and leave the generic duplicate-finder where it is; `dev/registry/pipeline/_tree_paths.py`.
- [x] `W06.P13.S311` - Collapse the provenance filename restatement and give the legacy filename one name instead of two; `dev/registry/pipeline/render_check.py dev/registry/pipeline/_provenance_manifest.py dev/registry/pipeline/_tree_publication.py`.
- [x] `W06.P13.S312` - Collapse the three remaining one-value-many-names constants in the registry tooling; `dev/registry/analysis/load_census_classification.py dev/registry/pipeline/render_check.py dev/registry/pipeline/_export_tree.py dev/registry/pipeline/_provenance_manifest.py dev/registry/pipeline/_tree_publication.py`.
- [x] `W06.P13.S313` - Gate that the census can follow the registry's own dynamic import, so a blinded resolver stops surfacing as stale rules; `dev/registry/tests/test_load_census_classification.py`.
- [x] `W06.P13.S314` - Teach the dynamic-import resolver the tuple-from-mapping-values shape the snapshot internals now use; `dev/registry/analysis/load_census.py`.
- [x] `W06.P13.S315` - Retire the six classification entries proven stale once the resolver could see again, and return the census to clean; `dev/registry/analysis/load_census_classification.py`.
- [x] `W06.P13.S316` - Prove the declaration evaluator resolves any construction and refuses rather than guessing; `dev/registry/tests/test_load_census_classification.py`.
- [x] `W06.P13.S317` - Give the load census a verification criterion carrying both the coverage and the instrument condition; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S318` - Verify the session's consolidations against every screen module and the corpus census; `dev/registry/analysis dev/registry/pipeline`.
- [x] `W06.P13.S319` - Correct the miscounted fact list and gate the fact claims the conditions gate deliberately skips; `dev/registry/analysis/modelo_capability.py dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W06.P13.S320` - Read the count claim rather than one spelling of it, so the fifth screen's census stops going unchecked; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W06.P13.S321` - Give the two absence gates that walk the tree a proof they looked, and record which needed none; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W06.P13.S322` - Say what the decisions Phase actually holds, counted rather than estimated; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S323` - Prove the two defining modules this session created, which the screen-test gate does not reach; `dev/registry/tests/test_corpus.py dev/registry/tests/test_tree_paths.py`.
- [x] `W06.P13.S324` - Run the only generator no test invoked, and record that filename convention cannot answer what a test covers; `dev/registry/tests/test_m303_orden_anual.py`.
- [x] `W06.P13.S325` - Gate that every public module in the registry tooling is imported by a test, proven on a planted root; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W06.P13.S326` - Make the reassembly proof exercise the gate's own walk instead of a copy of it; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W06.P13.S327` - Establish that every constructed screen proof asserts through its own screen, and that the contributor README needs no entry for the new defining modules; `dev/registry/tests dev/registry/README.md`.
- [x] `W06.P13.S328` - Correct the attribution of the five breadth figures, which the governing audit does not carry; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S329` - Establish that the capability-grade figure cannot be re-derived and that the grade is declared once today; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S330` - Re-derive the citation breadth figure against the live schema and state its boundary; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S331` - Re-derive the applicability figure to both its defensible boundaries and show the plan's is neither; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S332` - Re-derive the amount-semantics figure and record that the deciding fact is declared nowhere; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S333` - Establish that the money scale factor cannot be pinned from the development tree without a fake or a private import; `dev/registry/tests/test_monetary_scale.py`.
- [ ] `W06.P13.S334` - Pin the money wire type's hundredfold scale beside the codec that applies it, where a real export field is available; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `W06.P13.S335` - Verify a sample of the closed Steps scoped outside this execution against the live tree; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S336` - Establish that the largest screen's headline is the actionable unit and record the live restatement ratio; `dev/registry/analysis/provenance_consistency.py`.
- [x] `W06.P13.S337` - Carry both the surface and corpus answers for the citation figure in the Description; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S338` - Declare what a caller may assume about a screen finding, and learn from the gate that a runner row is not one; `dev/registry/analysis/screens.py dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W06.P13.S339` - Call the runner's output rows rather than findings, since two of them are reports; `dev/registry/analysis/screens.py`.
- [x] `W06.P13.S340` - Make two screen labels name the unit their rows are, rather than the entity those rows are about; `dev/registry/analysis/screens.py`.
- [x] `W06.P13.S341` - Carry the report-versus-finding distinction into the contributor README, and decline to gate the label wording; `dev/registry/README.md`.
- [x] `W06.P13.S342` - Add the three screen-property gates the criterion had not caught up with, naming properties before totals; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S343` - Replace the criterion's leading count and its ordinal back-references, which pointed at positions in a list that grew; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S344` - Name the screen the description referred to by position, and sweep for the same shape elsewhere; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md dev/registry`.
- [x] `W06.P13.S345` - Re-derive the capability paragraph's figures from the census and note the qualifier that has become vacuous; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S346` - Re-measure the below-filing layout population and name the two revisions whose bytes are already committed; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S347` - Verify the deadline and formula Step premises and give the deadline Step its revision identifiers; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S348` - Re-measure the multi-axis premise, which moved on both its figures, and surface the below-filing population it excluded; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S349` - Verify the registry suite end to end after the session's changes, comparing failure sets by identity; `dev/registry`.
- [x] `W06.P13.S350` - Attribute the registry failures the manifest and publication entries do not cover; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S351` - Characterise the last four registry failures so every one in the suite is attributed; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S352` - Record the completed registry attribution in the lane criterion, with its causes rather than its count; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S353` - Lift the unreachable-publication constraint, which a September second commit had already made false; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S354` - Verify the official-reference absence and record what the corpus does hold beside it; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S355` - Correct the release-predicate criterion, whose held-file blocker has lifted; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S356` - Establish that the deferral rationale has no revision-level slot and name the analogue it should follow; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S357` - Establish that the 714 envelope offsets lie past the footer's declared extent, which itself has no length; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S358` - Withdraw the declared-length request after counting the corpus, and name the official design as the authority on record extent; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S359` - Resolve why the layout coverage validator accepts modelo 714 while its cited design declares an uncovered developer-identity position; `src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py`.
- [x] `W06.P13.S360` - Connect the envelope migration to the modelo 714 offsets it explains, and measure both declaration forms; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S361` - Give the description a live countable example of one fact declared two ways, with its measured cost; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S362` - Establish that the typed envelope's product-identity requirement is declared by eighteen revisions, not merely available; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [ ] `W06.P13.S363` - Decide the never-populated engineered_by governance field, whose three stamp siblings are used by 122 of 128 revisions; `src/cadrumo/domain/calculations/registry/schema.py`.
- [x] `W06.P13.S364` - Sweep the revision schema for declared fields nothing populates and record the one exception; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S365` - Sweep the casilla and export-field types for unused declarations and attach the count to the retirement Step; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S366` - Measure the casilla number field before its retirement and surface the second number field beside it; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S367` - Resolve the two casilla number fields: they carry different facts, and the confusion is the name rather than a duplication; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S369` - Measure what the casilla number field actually holds across the corpus; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S370` - Sweep every casilla string field for heterogeneous value kinds and separate the real finding from the classifier's artefacts; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S372` - Examine the two remaining shape-sweep tails and reduce 415 to the six occurrences that are real; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S373` - Bound the accented-identifier finding by asking the direct question of every casilla field; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S374` - Sweep the export surface for encoding, line-ending and record-less defects and record that it is clean; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S375` - Gate the three export-surface properties the sweep found clean, so they stay clean; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W06.P13.S376` - Prove the three export gates against planted defects through the helpers they call; `dev/registry/tests/test_declaration_invariant_gates.py`.
- [x] `W06.P13.S377` - Record the three export-surface gates and their skip in the declaration-gate criterion; `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md`.
- [x] `W06.P13.S378` - Sweep the deadline windows for inverted spans, stray payment cutoffs and duplicate coordinates; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S379` - Write the keying rule into the contributor README beside the two rules already there; `dev/registry/README.md`.
- [x] `W06.P13.S381` - Measure whether every declared casilla localization key resolves in the shipped catalogues; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [ ] `W06.P13.S382` - Complete the localization crossing across all five key-bearing declaration families and decline to gate the one carrying findings; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.
- [x] `W06.P13.S383` - Measure the per-revision label restatement corpus-wide after the operator corrected the authoring framing; `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`.

### Phase `W06.P14` - declaration contract migration

Apply the accepted contract across the registry so restatement becomes unconstructable rather than detected.

- [ ] `W06.P14.S47` - Refuse an authored value on any field the accepted contract marks derived; `src/cadrumo/domain/calculations/registry/loader_cache.py`.
- [ ] `W06.P14.S48` - Migrate the temporal axis onto the single owned declaration and derive its projections; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W06.P14.S49` - Migrate the identifier grammar onto one declared form per modelo; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W06.P14.S50` - Retire the alias field, which carries no value on any of the 29,678 casillas, and decide the number field rather than retiring it: it restates the identifier on 24,524 casillas and carries a number the identifier does not on 5,154 semantically named ones; `src/cadrumo/domain/calculations/registry/schema.py`.
- [ ] `W06.P14.S51` - Migrate provenance onto attesting references and drop the verbatim restatements; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W06.P14.S52` - Move the non-temporal scheme axis of modelo 369 out of the revision slot; `src/cadrumo/_data/registry/aeat/modelos/369/revisions`.
- [ ] `W06.P14.S368` - Split the casilla number field by what it holds: 25,615 plain box numbers, 2,002 position ranges and 2,061 slugs that are not numbers at all; `src/cadrumo/domain/calculations/registry/schema.py`.
- [ ] `W06.P14.S371` - Transliterate the one semantic role identifier retaining an accent, which six casillas of modelo 100 carry while the other 24,042 are ASCII; `src/cadrumo/_data/registry/aeat/modelos/100`.
- [ ] `W06.P14.S380` - Derive casilla labels per modelo with a per-revision override only where the official text genuinely differs: keying per revision does not merely duplicate 28,129 strings across the four locales, it lets the copies disagree, and 931 Hungarian, 807 English and 687 Catalan casillas already carry two renderings of one byte-identical Spanish string; `dev/locales src/cadrumo/locales`.
- [x] `W06.P14.S384` - Make the cross-revision label restatement measurable: a census module in `dev/locales` reusing the roots, catalogue discovery and flattener the locale tooling already owns, reporting restated surplus, genuine divergence and single-revision labels per locale, with the classification proven on constructed input rather than against whatever the live corpus says; `dev/locales`.
- [x] `W06.P14.S385` - Measure the divergence the duplication count hides: report the casillas whose Spanish label is byte-identical across revisions while a translation of it differs, since every translation diverges on more casillas than the source text does and the excess is divergence the translations introduced; `dev/locales`.
- [x] `W06.P14.S386` - Prove the label collapse safe before any key shape changes: derive per-casilla labels with per-revision overrides, expand them back over each casillas revision set, and show the reconstruction reproduces all four shipped catalogues byte-for-byte while removing 30,049 of 87,298 strings - with the round trip shown failing on a dropped override rather than only passing; `dev/locales`.

## Parallelization

Waves are sequenced. Wave one must land before Waves three and four, because both measure the
resolved surface and the accessor is what makes that measurement trustworthy. Wave two is
independent of Wave one and may run beside it. Wave three depends on Wave two for the gate that
holds its result. Wave five is independent of every other Wave except that its revision renames must
not land while another contributor holds the same directories.

Within Waves, the four Phases of Wave four are mutually independent once the accessor exists and may
proceed in parallel; each screen owns its own module and test. The three Phases of Wave two are
independent of one another. In Wave six the decision Phase gates the migration Phase absolutely, and
within the migration Phase the temporal, identifier and provenance migrations touch overlapping
manifests and must be serialised behind one writer.

Three ordering constraints were discovered by measurement rather than planned, and each overrides
the Wave order above.

The eligibility-predicate correction was to land before any further export tree was published, so that
the rules it makes due would be authored rather than retrofitted. **That constraint is spent, and
re-measuring it is what showed so.** The correction admits forty-one numeric fields, not the hundred
and eighty three this section claimed - a figure retired elsewhere in this plan and left standing here
- and every one of the forty-one sits in a revision whose export tree is ALREADY published: thirty-two
in modelo 200's `2025-y-siguientes`, six across three revisions of modelo 303, and one each in modelos
202, 222 and 353. None sits in an unpublished design.

So the conversion this constraint existed to prevent has already happened, in full. The work is a
correction of shipped filing data whichever order the remaining Steps run in, and sequencing the
predicate ahead of publication no longer protects anything. What replaces it is the structural
blocker recorded in the verification section: the correction cannot land honestly at all until a
render profile can declare a field eligible with its representation unsupported, because twenty-nine
of the forty-one have no wording that settles them.

The generator verb must be reachable before any generated-tree defect can be corrected. A defect whose
root cause is proven, whose corrected value is stated in the official design, and whose authored input
is uncontended is still unfixable while no supported path regenerates one revision from its inputs.
This constraint was written twice and is wrong both times. It first said the verb had to be built; it
does not, because the pipeline implements `publish_validated_generated_export_tree`. It then said the
limb existed and nothing could reach it, which was true when written and stopped being true on
2026-09-02, when an operator invocation surface was added. `python -m dev.registry.pipeline publish`
is a registered verb today and it calls that authority through the same prepared candidate the
read-only check validates. The constraint is therefore lifted, and the republication it was blocking -
the single repair behind most of this directory's failures - needs no new
machinery, only somebody with the scope to run it. Re-measured on 2026-09-03, the directory runs
1,152 passing and **36 failing** tests in twelve minutes, of which **30 sit in the four
generated-tree modules**: twenty-six in the tree comparison itself and the rest across its
publication, CLI and envelope proofs. The figures written here were twenty-seven of thirty-five, and
the proportion they expressed still holds while both numbers have moved. It gates every correction
Step touching a generated modelo, whatever Wave the Step sits in, and it also gates the enrolled
trees that render successfully and have never been committed - **three** of them on re-measurement,
not the two written here: modelo 308's `2019-y-siguientes`, modelo 360's `2010-y-siguientes` and
modelo 390's `2022`. Twenty-eight revisions produce render inputs and carry a publication manifest;
these three produce them and carry none.

One missing artefact gates work in three Waves, and it is external to the repository. No
official emitted-byte reference for any modelo revision has been acquired, and
`CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS` is consequently the empty tuple. The whole of the proof
vector Phase consumes that reference, which its own Steps already say. What was not written down is
that the same absence reaches outside that Phase: the modelo 151 live-filing closure test cannot be
rewritten onto the two-channel authority, because that authority resolves a conformance vector before
it reports a satisfied outcome and the test's invariant needs a satisfied outcome to express; and
that test is the single failure in the conformance directory the lane Steps propose to name, so the
lane Step inherits the block through it. Three Steps in three Waves therefore wait on one artefact
nobody in this repository can author, and none of them is undone for want of effort. A Step blocked
on absent evidence should say so in its own text rather than read as outstanding work, which is now
the case for each.

The read-only half of that path exists and is deliberately kept separate: a comparison that renders
into a temporary directory and never writes to the registry is safe to run against filing data, and
publication is not.

A Step whose scope names a file another contributor has modified waits, whatever its Wave or
dependencies. This is not a soft preference: the architecture rule requires a relocation to move a
definition and every consumer in one change, and a partial move leaves the tree broken. At the time of
writing this blocks the whole of Wave two's residue and predicate Phases, and it blocked one screen
from being written at all, because the predicates it needed are private to a held module and restating
them would reproduce the very fault this plan removes.

That set is not static, and it is not a property of the file: two package initialisers that were held
when this constraint was written were released by a commit and became workable the same day. Re-read
`git status --porcelain` for the specific path before assuming a Step is still blocked, and before
every write. A Step deferred once is not deferred permanently.

Re-checked on 2026-09-03, that constraint has largely lifted. The whole worktree carries seven
pending paths, one of them under `src/`, and every path named by the Steps this constraint was
written about - the closure module, the export schema, the filing export proof, the modelo 151 and
185 revision directories, the justfile, the import-linter contract and the project file - is clean.
Wave two's residue and predicate Phases are no longer blocked by another contributor's diff.

What blocks them now is a different thing and should not be confused with it. This execution is
scoped to `dev/` and `.vault/`, so a Step whose scope names `src/`, the justfile or the project file
is outside what this agent may write, however clean the path. That is a limit on the executor, not on
the work, and it is worth stating separately because the two produce the same "not done" and want
opposite responses: a held file means wait, a scope limit means hand off.

A hard external constraint overrides all of the above while it lasts: an import refactor is
in flight and holds a large pending diff. Any Step whose scope names a file that refactor
has modified waits, whatever its Wave. At authoring time this blocked the recipe repoint,
the boundary contract, the ratchet residue deletion and the dependency move.

That constraint has since sharpened into a different one. The worktree is shared with a
concurrent closed-vocabulary campaign that commits across the whole tree, and its commits
land mid-Step rather than between them. Three consequences bind the work here.

A committed change from that campaign can turn this plan's gates red without any Step
running. The enum conversion moved the two registry test directories from 15 failures to
46 by changing how one field is serialised, and every one of those failures had to be
attributed before any of them could be acted on. Attribution is therefore a precondition
of every red gate, not a courtesy: a failure this plan did not cause must be named as
inherited, and one it did cause must be owned in the same breath. The reviewed-size
baseline that caught a four-line growth from this campaign's own evidence-tier repair is
the second kind, and it was fixed by shrinking the change rather than raising the ceiling.

Work whose remedy lies in that campaign's surface is reported rather than performed. The
twenty-one registry modules carrying no load classification and the fourteen rules naming
modules that no longer exist are the visible edge of a rename still in flight; adjudicating
them here would assert facts about code another writer is still moving, and the
adjudications would be stale before they were read. The same reasoning holds for the
twenty-five generated trees whose attestation that campaign staled: the remedy is
republication by the commit's owner, and this plan carries the measurement instead.

A fourth ordering constraint was found by measurement and binds two Steps that read as
independent. The modelo 151 live-filing closure test currently fails on interface drift: it
builds the single-channel proof authority, which no longer carries `assess_for`, and the
obvious repair is the one its Step already names - rewrite it onto the two-channel
authority. Doing that today changes what the test fails on rather than fixing it. The
two-channel authority was constructed against the live registry and asked for the same
coordinate, and it returns no proof at all: the conformance channel refuses with
`evidence_missing` because the canonical vector set is empty, and the secure-replay channel
refuses with `authority_unavailable`. The test asserts a satisfied filing-export limb, and
no arrangement of the two-channel authority can satisfy it while the vectors are empty.

So the closure-test rewrite sits behind the vector enrolment, and the vector enrolment sits
behind official record-design examples that this campaign cannot author. The dependency is
recorded rather than worked around, because the available workaround - stubbing the channel
the test cannot satisfy - would convert a real gap in filing evidence into a passing test,
which is the outcome the whole plan exists to prevent.

What remains fully available is the dev-owned surface, which is why every Step of `W06.P13`
lives there. A screen, its dispositions and its gate can be authored, proved
and left green without touching a file the other campaign holds.

## Verification

The plan is complete when every Step is closed. Beyond that, the criteria below decide whether the
work achieved what it was for. Each names the evidence that settles it, because a criterion whose proof is
a reading rather than a command is one nobody can check later.

No gate, screen or audit reassembles the resolved export surface. Proven from two sides. Beside the
accessor, one test asserts it returns all three linkage paths - direct field, projection reference and
row-field mapping - and two more drop a path and assert the casilla it carried disappears. Those two
cover the projection and row-field paths deliberately: they are the ones every hand-walk in this
campaign actually missed, while a walk omitting the direct field path fails visibly at once. The
criterion once claimed a drop proof for any of the three; it has two, and naming which two is worth
more than the rounder sentence.

In the declaration invariant module, a second gate asserts no analysis module reaches for the binding
derivation at all. It checks the import rather than the result, because a partial walk produces a
plausible number and only the method of reaching it differs.

The release-eligibility predicate is evaluable from the shipped application, and a coordinate-identity
gate runs in the repository gate lane, comparing the satisfied filing coordinate set by identity and
naming the limb that regressed. It asserts no count, no ceiling and no floor. Neither half holds yet, and the reason has changed: the
predicate still lives in contributor tooling, in `dev/registry/conformance/closure.py`, but that file
is no longer held. It carries no pending diff and neither does its destination in the shipped
application, so what blocks the move is scope rather than another contributor's work in progress -
the same distinction the parallelization section draws, and the third absence claim in this plan
found stale on re-check.

At least one generated export tree carries an enrolled conformance vector proving its emitted bytes
against the official record design, and a tree carrying no vector refuses as missing evidence rather
than reading as unmeasured. The second half holds and is now guarded again: the emitted-byte
acceptance suite asserts the structured refusal, naming which channel is empty, rather than the prose
that rephrasing once broke. The first half cannot be satisfied by engineering until the official
reference exists, because a vector whose expected bytes came from this project's own writer
would prove only that the writer agrees with itself.

Every screen is reachable, exercised and honest about what it measured. The properties that hold it
there, twelve of them at the time of writing: a screen is enrolled in the runner, listed in the contributor README's table, carries a test module,
searches a non-empty population, completes over the whole corpus, leaves the shipped registry
byte-for-byte untouched, names in its own docstring every finding kind it emits, and states a
condition count matching both what it documents and what it emits; and every symbol those READMEs
name still resolves, so the documentation cannot outlive the code it describes.

Three more have since joined them, and the count is written this way - the properties named, the
total second - because it has already moved twice while the properties did not. A screen module's
public surface must be imported by some test, since a module no test imports is one whose behaviour
nobody asserts. A screen's finding type must declare the modelo the contract promises, which is the
only field a caller may assume across screens. And a screen stating how many FACTS it reads must
list that many, which the condition-count gate deliberately skipped and which one screen had wrong.
Each was added
after finding the hole it closes, and two caught the author within one iteration of being written.
The kind-naming gate collects its kinds by running the screens rather than reading their source, because two
earlier static extractors were each wrong in a different direction: one under-read a screen to a
single kind and another to none, and a regex reported function names as undocumented kinds. The
condition-count gate exists because naming was not enough: two screens named every kind they emit while still
opening with a count from an earlier version of themselves, and one of those went stale in the very
edit that added the missing name. A wrong count is worse than a missing one, because it tells the
reader the list is complete.

A screen is a module presenting one of the declared entry points, and which entry point it presents is
now stated in one place. Nine gates were narrow in this one way, each written when `screen_authority`
was the only entry point, and when screens arrived reading the design corpus rather than the loaded
authority - taking no authority and no modelo set, so presenting `screen_corpus` - every one of them
stopped covering a whole class of screen while continuing to pass. Two carried their own copy of the
module walk; four iterated the authority table, so a corpus screen's emitted kinds, condition count,
fact count and finding identity were never read; two ran the authority runner alone, one of them
inside the fingerprint that proves the screens write nothing; and one claimed a scope its body did not
have. The entry points and the two traversals over them
are declared beside the tables, so a third entry point widens every gate at once, and a further gate
asserts the runners between them emit exactly the enrolled names - by name and not by count, because
two tables of the same size can still disagree about which screens they hold.

Widening the identity gate found a real breach rather than confirming a clean state: neither corpus
finding declared the modelo the contract promises every caller. The contract was satisfied rather than
widened, because a design transcription lives in its modelo's corpus directory and the modelo is a
fact about the file. It is read by walking up to the first `modelo_` ancestor, not at a fixed depth,
since one design of two hundred and fifteen sits one level higher than the rest and a fixed count
would have reported `disenos_registro` as a modelo. A transcription outside any modelo directory
raises, which immediately failed three constructed-design tests writing into a bare temporary
directory - the guard working, and the fixtures now build the corpus layout they claim to represent.

The pattern under all nine is worth stating once, because it is this campaign's most repeated finding
and it has appeared in screens, in readers, in a reading aid and now in the gates themselves: a check
written when the world had one shape keeps passing after the world grows a second, and passing is
exactly how it hides. Nothing in a green suite distinguishes a condition that does not occur from one
nobody is looking for.

Three gates now hold the export surface itself, on properties measured clean and then guarded so they
stay so: no export declaration carries a character outside ASCII across 25,031 fields, no modelo
declares two record encodings across 419 records, and no layout mixes terminated with unterminated
records across the 88 layouts that have records. The record-less layouts are skipped rather than
counted as agreeing, because an XML dictionary layout has no termination to disagree about, and each
gate asserts what it read before asserting what it did not find.

Each declaration gate demonstrates detection of a representative defect from a constructed fixture or
an isolated temporary registry tree, never by mutating the working tree, and each passes the normal path in the same suite. Several gates are exempt and
better for it, being proven against a live defect in the shipped registry instead of a constructed
one: the sibling scale comparison, the record-drift ledger and its companion manifest-staleness
assertion, and three of the revision-name conditions. Each says in its own docstring that the pin is
deliberate, that its failure is the correction landing rather than a regression, and what must
replace it.

Naming that replacement turned out to be the hard half. Every one of the six misnamed revisions
carries an open rename Step, so the instructions that first pointed at a live sibling were pointing
at a coordinate leaving at the same time as the one it was offered to replace. The replacement a pin
owes is a claim about the corpus after this plan lands, not the corpus today; where the kind empties
entirely, the honest instruction is to construct the case from a copy of a real revision, which is
what the sibling conditions in the same module already do.

No monetary amount is emitted at a magnitude the registry does not determine. Every monetary field is
rendered by a wire type that scales, carries a declared scale, or is one half of the official part
split, and no field disagrees with the amounts beside it in its own record. Twenty-six fields fail
the first test and two fail the second, and **every one of the twenty-six sits in a revision declaring
filing grade** - eight and six in the two revisions of modelo 347, four and four in modelo 184's, two
in modelo 200, one each in modelos 296 and 353. Each is a monetary field rendered as text, which
applies no scale, in a revision that says it can be filed. Five more declare four decimals where the
corpus otherwise uses two. The two that fail the second test are the plan's known filing-correctness
defects: modelo 200's casilla 03594 and modelo 353's casilla 10, each emitting unscaled where the
amounts beside it in the same record emit cents. The second appeared through a commit while this
plan was being executed and was caught by the gate that pins the first, which is what a gate
proven against a live defect is for.

Every field the eligibility correction newly admits has located official wording addressed to it, the
strength of that wording is reported rather than assumed, and the wording has been READ. Forty-one
fields are admitted, not the hundred and forty-nine this plan once claimed and no measurement
reproduces: thirty-eight are grounded by a note their own content cell cites, two by a convention
naming their AEAT type, one by a design-level note, and none by nothing. The conditions are counted
apart because they differ in strength - a cited note is addressed to the field, a type convention to
its class, a design note to nothing in particular - and collapsing them would credit a field with
evidence that never mentions it.

Zero ungrounded is not, however, a readiness figure, and the criterion is not met by it. Reading the
thirteen notes those forty-one fields resolve to: seven state representation and cover twelve fields,
while four state who must complete a field, when it may carry content, or which period it applies to
- and those four cover twenty-nine, the largest of them grounding twenty-six fields with a sentence
about which entities must fill them. Four of the thirteen rest on wording that differs between the
designs of their modelo, covering seven fields whose rules hold only for the design they were read
in. What the screens establish is that official wording addressed to each field exists and where to
open it; whether it settles the field is a reading, and the reading says twelve of forty-one.

That leaves the correction blocked on something structural rather than on research. A render profile
must cover exactly the eligible fields, and a rule's evidence admits only `official_source` or
`reviewed_policy`, with no way to say that nothing settles a field. So making these fields eligible
obliges an author either to assert twenty-nine policies that were not found or to leave the predicate
wrong, and this plan takes neither. The criterion is met when a field can be declared eligible with
its representation unsupported, and the forty-one are accounted for as twelve stated and twenty-nine
declared - which is what this project's rule against silent under-declaration asks for and what the
gate cannot currently express.

Reaching that took correcting the reader four times, and the corrections are the criterion's real
evidence. Note labels are scoped to the sheet that prints them, because a workbook numbers each
page's notes from one and seventy-five designs repeat a label across sheets, which a design-wide
reading merged into three hundred and fifty-seven absorbed definitions. A sheet heading may carry
spaces. A label is separated from its wording by a colon, a full stop or a table pipe. And an
unnumbered note is read as its own line and nothing after it, because every boundary rule tried
absorbed a neighbour somewhere in the corpus. Each correction changed what the corpus was understood
to contain, and each is held by a test asserting the property over the whole corpus rather than a
sample - the absorption that survived longest sat in one design out of the fifty-one that carry
such a note.

What an unnumbered note governs is settled by evidence and not by where it sits: modelo 200 prints
its amounts convention on a sheet carrying no amount field while the five thousand six hundred and
sixty-five fields it describes sit on seventy-four others, and no design in the corpus carries
differing unnumbered notes on different sheets. The reader still returns them keyed by sheet, because
that is the fact it observes, and a sibling screen reports the structure a consumer reads before
keying a rule to one.

Two conditions in this group have no live instance and keep their proofs on constructed input rather
than being deleted: an unnumbered note differing across sheets, and a field with no grounding at all.
Both were emptied by a correction, both are the case someone must not discover halfway through
authoring, and a condition with no instance and no proof stops reporting without anyone noticing. No
proof in this group reaches inside a screen to replace what it imports; each classifier takes its
inputs explicitly so its conditions are reachable from a test.

Every module the registry load reaches carries exactly one reviewed classification, and the census that
decides this can see what it is measuring. Both halves are asserted, and the second is not decoration:
the census reports a module as unclassified or a rule as stale by the same absence it reports when its
own resolver has stopped following an edge, so a clean result proves nothing unless the instrument is
known to be looking. It holds today - 411 modules in the universe, none unclassified, no stale rule -
and it holds against a resolver that reads what a declaration HOLDS rather than how it is written,
because the previous one followed a literal tuple and went blind when the same names were rebuilt from
a mapping. A gate asserts no dynamic import inside the registry package is left unresolved, which is
the condition that makes the coverage number mean anything.

Every revision directory name agrees with the window that revision declares, and a gate refuses a name
that does not. Temporal selection resolves every coordinate the law can decide and refuses only those
it genuinely cannot. Fourteen names fail the first today. The second is now measured rather than
asserted: over 441 probes across 58 modelos no coordinate refuses outright, and exactly one - modelo
308 at filing year 2011, where the windows split at the end of June - cannot be decided by the filing
year alone and needs a date. The probe used to erase that case, because the retry that answers it
also cleared the refusal, so the one coordinate this criterion is about was reported like any other.
It is now carried on the probe and counted in its summary.

The development registry lane passes, and until it does every failure in it is named and attributed.
The lane is red, and which lane is meant now has to be said. Over the registry tests directory this
plan has measured throughout, the count has moved between fifteen and forty-two, and as of the last
full run every one of the thirty-five is attributed rather than merely dated: twenty-seven share a
single cause, the generation manifests that a generator refactor left stale, and the remaining eight
are four undeclared prose parsers, one inspection boundary crossed, two frozen corpus counts drifting
and one refusal pinned to wording the command no longer uses. Five of those eight are defects this
plan named while working on something else, which is the argument for finishing an attribution rather
than counting a failure list: the same shapes recur across surfaces nobody has connected. Over the eighteen-directory selection CI actually invokes, measured
once to a reconciling total, it was 167 failures and 72 errors of 3,881 tests. Re-measured on
2026-09-03 it is 177 failures and 109 errors of 3,941 collected, with 3,653 passing and 2 skipped -
the four numbers reconcile to the collected total, which is what makes the reading trustworthy rather
than a headline. Those are not two readings of one number: the registry path shares a single
directory with the CI selection, so the smaller figure was never a subset of the larger one and the
criterion had been quoting a lane nobody runs.

The re-measurement's duration is deliberately not compared. The earlier reading completed in six and
a half minutes; this one took forty, on a host carrying a hundred and eighty-nine python processes
at full CPU while this plan's own suites ran beside it. That is a measurement of the machine, not of
the lane, and reporting it as a regression would have been the same error this campaign has already
made once with a timeout. The passing count is deliberately not recorded. It rises
whenever this plan adds a gate - it moved by two within a day of being written down - so a criterion
carrying it goes stale for the best possible reason, and a number that changes when nothing is wrong
teaches a reader to ignore it. The
first figure was down from twenty-six when the inventory was first taken. The second was corrected
twice: the conformance suite went unmeasured entirely until the scope of the measurement was
questioned, and was then reported as two failures because a single file in it had been run instead of
the directory. Measuring the directory gives three. Both errors were the same error at different
sizes, which is why the criterion names paths and not counts. Every one is accounted for, and the accounting is now
dated rather than asserted: each failure's first appearance in this plan's retained lane logs
separates what predates the work from what arrived during it. Eight predate every measurement here,
including the generated trees that do not reproduce and the boundary check naming modules an
in-flight rename moved. Five arrived mid-plan, four of them in modules another contributor added or
changed.

One belonged to this plan and was filed as inherited for six lane runs. A screen written here read
design prose without enrolling in the channel that governs reading it, and the failure naming four
undeclared parsers was counted as somebody else's because the label was applied to the failing test
rather than to its contents. It is enrolled now. The earlier claim that none belonged to this plan
was established by name, and the names inside the failure were not read. The three conformance failures are a
closure row driven by a proof authority whose only proof-producing path refuses, a guard whose
expected refusal message no longer matches what the code raises, and one in the closure suite beside
them that has not yet been read.

The lane figure is only as honest as the path it was taken over, so the run names both directories.
The conformance suite once took nearly twelve minutes for seven tests, which exceeds the default
foreground timeout and is exactly why it fell out of every earlier measurement; that cost is the
subject of the criterion below.

One concept has one declaration, and the exceptions are reasoned rather than tolerated. Duplicate
function bodies across the shipped package fell from 27 to 5, redundant copies from 45 to 8, classes
sharing a name from 2 to 0, and duplicated name-and-value constants from 23 to 16. Sixteen collapsed
concepts are held at a single definition by a gate that names each one, because a whole-tree commit
in the shared worktree had already restored a set of them silently - the duplicate that returns
works, so nothing fails.

What makes this criterion met rather than merely reduced is that every survivor was read and has a
recorded reason. Five duplicate bodies guard per-module constants and would lose the thing that
distinguishes their modules. Nine aliases give a primitive a domain name, which is meaning rather
than repetition. Three manifest versions agree at one by coincidence and must stay free to diverge.
One namespace is genuinely a single fact whose only shared home would couple two subsystems that
never otherwise meet, so the duplication is cheaper than the collapse. A criterion that counted
instead of reading would call this incomplete; the work is to distinguish them.

The registry's own audits complete well inside the budget the tests give them, and each remedy
preserves the isolation contract rather than trading it away. This was not a criterion when the plan
was written, because the cost was invisible: a conformance test failed on a three hundred second
timeout and read as a logic failure. Measured, one closure report took 210.8s for 128 rows and the
conformance audit 133.9s, both dominated by a single mechanism - a snapshot is a cached lookup plus an
isolating deep copy, the lookup costs nothing measurable and the copy is 98% of the call, and callers
were taking one per coordinate to read a single string or four small collections. The closure report
is now 15.0s and the conformance audit 22.1s. What makes those numbers acceptable rather than merely
smaller is that no caller gained access to shared registry state to get them: each remedy either
returns a value that cannot be mutated, or isolates the part actually read. A future change that
restores the cost is a regression; one that reaches the same speed by handing out cached state is
worse than the cost was. The criterion is deliberately not
"the lane is green", because this plan cannot make it green while another campaign holds the files;
it is that no failure in it is unexplained, so a new one is visible immediately. Read the exit status
from pytest itself: a run piped through a filter reports the filter, which once made a red lane read
as exit code zero.

Each of the four edge gates demonstrates detection of a representative defect from a
constructed fixture or an isolated temporary registry tree, never by mutating the working
tree, and each passes the normal path in the same suite.

Every measurement this plan rests on is one a reader can check, and the plan says how it was
taken rather than only what it showed. This criterion exists because the measurements failed
four times in ways that all looked like success. A suite reported three passing tests over a
file holding twenty-four, because a marker had deselected the rest. A gate compared two sets
that could both be empty. A worker crashed and its run reported a failing test, taking an
unknown number of tests with it. And a comparison against a remembered total answered nothing,
because the tree had moved underneath it.

What satisfies the criterion is not that the numbers are good. It is that each one names its
population, that every gate refuses to pass over an empty one, that a run's collected count
comes from the same invocation as its result, and that a reported failure is read from its own
text rather than from a summary line - because a crash and an assertion are different events
that a tally spells identically.

The evidence is that all four of those failures are recorded here with what they cost, that
the gates now assert their populations against measured floors, and that every run whose
figures this plan quotes has been swept for lost-worker markers and carries none.

Every category a screen reports has members that were read, and a member's presence implies a
remedy the other members share. That is not the criterion above restated: a measurement can be
taken correctly and still be sorted into a category mixing defects with correct declarations,
and the sorting is what a reader acts on.

The need was proved on this campaign's own screens rather than inherited. One condition was
built, run, and removed inside a single iteration once thirty-five of its thirty-six members
turned out to be correct. Another was split by direction because its four members wanted three
different corrections. A third had to stop firing on five revisions a neighbouring condition
already described more accurately, where the two rows contradicted each other outright. In
each case the count was the least informative thing about the finding.

What satisfies the criterion is that each condition names what a member has that a non-member
lacks, that the boundary is tested from both sides, and that a condition whose members are
mostly correct is withdrawn rather than kept for the sake of the one that is not.
