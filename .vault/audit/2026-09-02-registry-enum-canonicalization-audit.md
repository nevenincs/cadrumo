---
tags:
  - '#audit'
  - '#registry-enum-canonicalization'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:e6373a2840c80245acce5b8b461aa2bbc4fe6f1298c55cc9b54ad03943133e32'
related: []
---

# `registry-enum-canonicalization` audit: `Ad-hoc conformance vocabularies in shipped registry data`

## Scope

Every conformance-bearing scalar in the shipped registry tree, against the
Python schema that is supposed to define it. 19,511 TOML files under
`src/cadrumo/_data/registry` were parsed and their string values collected per
key; every key whose values form a small closed set was then checked against
the type the schema gives it. The schema side was read by AST across
`src/cadrumo/domain/calculations/registry`, and semantic duplication was
searched with vaultspec-rag rather than text matching, which is how two of the
findings below were reached at all.

The audit asks one question: is the Python module the authority for a value
set, or has the TOML become the de-facto authority that Python merely echoes?

## Findings

### degenerate-review-status-literal | critical | A one-member Literal certifies 531 shipped rows and is structurally incapable of failing

`schema_base.py` declares `ReviewStatus = Literal["reviewed"]`. It has exactly
one member, so `review_status = "reviewed"` is the only representable value and
"not reviewed" cannot be written down. 531 legal-source rows carry that stamp.
A conformance field that cannot express its own negation is not a check; it is
a constant wearing the shape of one, and every report that counts it as review
provenance overstates what the tree knows about itself.

The same field name carries a real vocabulary a few lines away.
`LegalReference.review_status` is typed `LegalReviewStatus`, which has
`pending_review`, `agent_reviewed` and `operator_reviewed`, requires a reviewer
and a date for the two reviewed members, and rejects the token `"reviewed"`
outright. `SourceReference.review_status`, in the same file family and reading
from the same TOML tree, is the degenerate Literal. Two vocabularies, one key
name, no way for a reader or a gate to tell which governs a given block.

### dev-metastate-in-shipped-data | high | Build-process provenance ships in the wheel as untyped strings

`engineered_by` and `reviewed_by` are bare `str` on the governance stamp. That
is how `reviewed_by = "agent-prepared-pending-operator"` became a load-bearing
value: a sentence about which agent produced a file, inside data distributed to
users, with no type to constrain it and no enum to enumerate the alternatives.
The registry gates then branch on it. Whether such provenance belongs in
shipped data at all is the architectural question; that it is untyped is the
defect.

### duplicate-encoding-members | high | Two enum members name one codec and split 401 registry files between them

The fixed-width codec enum declares `ISO_8859_1 = "iso-8859-1"` and
`LATIN_1 = "latin-1"` as separate members. Python resolves both to the single
codec `iso8859-1`; they are the same encoding spelled two ways. The registry
splits across them, 152 files to the first and 249 to the second. Any equality
comparison against one member is therefore wrong for the other set, silently,
and the split is invisible to a reader who does not know the codec aliases.

### inline-literal-vocabularies | high | 152 inline Literal unions declare 110 vocabularies, 28 of them in more than one place

The registry schema carries 152 inline `Literal[...]` string unions covering
110 distinct vocabularies, while the wider codebase already defines 636 enums.
28 of those vocabularies are declared at more than one site: the three-token
handoff-kind set appears at five, the settlement-direction pair at five, the
quarter tokens at three. A vocabulary defined at the point of use is not a
canonical definition; it is a copy. When one copy gains a member the others
keep validating the old set, so a TOML value can be conformant against one
reading of the schema and not another, with nothing to report the divergence.

### duplicate-review-status-enums | medium | Two byte-identical enums, and the docstring justifying the split omits the twin

`LegalReviewStatus` and `RevisionReviewStatus` declare the same three members
with the same values. Both were returned as the top two hits for a single
vaultspec-rag query, which is how the pair was found; a text search for either
name does not reach the other. `RevisionReviewStatus` carries a careful
docstring justifying why it must be distinct from the same-shaped vocabularies
the codebase already ships, and enumerates four of them by name. It does not
name `LegalReviewStatus`, the one it exactly duplicates.

### encoding-alias-compensating-normaliser | medium | A normaliser already exists to hide the duplicate members, and it names the canonical spelling

Found by vaultspec-rag semantic search, not by name: `schema_exports.py` carries
`_normalise_fichero_boe_encoding`, which folds the two spellings together before
the one place that compares encodings across the records of a layout. Its docstring
states the reason plainly, that the two tokens are Python codec aliases for one
charset.

This refines the sibling finding on the duplicate members rather than restating
it, and in two directions. It is milder than that finding implies: the remaining
uses of the value are `encode` and `decode` calls, which Python resolves
identically for either spelling, so no payload is mis-encoded today and the sole
comparison site is defended. It is also worse: the defence is a helper that a
future comparison must remember to call, and nothing enforces that it is called.
A compensating normaliser at the point of use is the same shape as a vocabulary
declared at the point of use, which is the pattern this campaign exists to
remove.

The finding also settles a question the recommendations left open. The alias map
the normaliser consults already elects `iso-8859-1` as the canonical form, and
carries a second alias pair for the Windows codepage on the same basis. The
collapse therefore has a direction the codebase itself has already chosen, and
the 249 files spelling the non-canonical token are the ones that move.

### sweep-blind-to-toml-quoting-broke-the-load | critical | A repair regex matched one TOML quoting style and left the tree unloadable

The first codec sweep matched `encoding = "latin-1"` and rewrote 249
declarations, then reported zero remaining by re-running the same
double-quote-only pattern. It was checking its own blind spot. 141 further
declarations used TOML single quotes, were never seen, and survived. With the
duplicate enum member removed in the same change, the registry stopped loading
entirely: the first modelo whose export layout carried a single-quoted
declaration refused with a validation error on every record in it.

Two lessons, and the second is the transferable one. A verification that re-uses
the search expression of the edit it is verifying cannot find what that
expression cannot match, so a sweep must confirm against a deliberately broader
reading of the tree than the one it wrote. And a data sweep paired with the
removal of the value the un-swept rows depend on has no safe intermediate state,
so the two halves must either land together or be ordered so the permissive half
survives until the sweep is proven complete.

The breakage was introduced and repaired inside one session; it never reached a
commit. It is recorded because the shape is general and the campaign will sweep
several more vocabularies the same way.

### degenerate-evidence-tier-literal | high | A second one-member Literal sits two lines from the first and was missed

`LegalReference.evidence_tier` is `Literal["legal_authority"]`, the identical
defect this audit opened with, on the same model as the review-status field and
two lines above it. The first pass inventoried closed vocabularies by collecting
TOML values and asking which were enum-backed; a field whose every row carries
one value looks like a settled vocabulary from the data side and is only visible
as degenerate from the type side.

The method that missed it is the finding. A value-frequency census cannot
distinguish a vocabulary that happens to be uniform in the current tree from one
that is structurally incapable of varying, so the schema side must be read for
one-member unions directly rather than inferred from the data.

### review-status-has-two-consumers-not-one | medium | The degenerate stamp is read by legal parameters as well as sources

`ReviewStatus` is consumed at two models, not the one this audit first named:
`SourceReference.review_status` and `LegalParameter.review_status`. The 530 rows
carrying the token split into source blocks and legal-parameter blocks, and the
two halves are not equivalent for the repair. The legal-parameter rows already
carry a reviewer and a date, and their reviewer tokens map mechanically onto the
real vocabulary's reviewed members. The source rows carry neither, so they fall
to the pending member.

The cost of retyping is therefore materially smaller than first stated: the rows
that become an explicit backlog are the source blocks alone, and the remainder
convert without a judgement call.

### standing-accepted-exception-to-the-typed-enum-mandate | high | A prior accepted ADR permanently exempts a registry value set from enum typing

`2026-06-01-registry-period-code-union-cli-boundary-adr` is accepted and records
an explicit, permanent exception to the typed-enum mandate: the period axis is
not a closed enum because one member is a regex form that cannot be enumerated,
and the record states the exception is documented precisely so later audits do
not re-flag it.

Any gate this campaign adds that asserts zero inline unions across the registry
schema would re-flag exactly that deviation, so the two records are in direct
tension and this campaign cannot simply assert its rule over the top. The
follow-on decision must either scope the gate so a documented structural
exception is outside its subject, or supersede the earlier record explicitly.
Discovering it late is itself the lesson: a campaign that proposes a tree-wide
rule has to search the decision corpus for prior rulings on the same subject
before proposing, not after.

### non-enumerable-unions-block-a-zero-count-gate | high | Several closed unions in scope cannot become enum members at all

The registry schema carries unions over non-string values, single-member
structural tags used as pydantic discriminators, and at least one field
constrained by regex rather than membership. None of these can be expressed as a
named string enum, and a discriminator tag in particular cannot be an enum member
because the union machinery requires the literal itself.

A gate that counts inline unions and demands zero would therefore never reach
zero honestly, and the campaign would be pushed toward either an exemption list,
which is the mechanism it exists to remove, or a false count. The gate needs a
mechanical predicate that separates a vocabulary from a structural literal, and
the follow-on decision must state that predicate rather than describe the goal.

### one-member-literals-are-not-syntactically-separable | high | The gate can be mechanical for multi-member vocabularies and cannot be for one-member ones

An earlier reading assumed a one-member string union could be told from a
legitimate structural pin by whether it carries a default equal to its own
member. Measured across the registry schema's annotated model fields, the split
is 10 with such a default and 29 without, and the 29 are not a clean class. They
include the shape tag that names a row-producing selector, the scope pins that
restrict a binding to one modelo and one quarter, the headings quoted verbatim
from an annex, and the jurisdiction constant, none of which is a conformance
claim and all of which are correct as written. They also include the two
degenerate conformance fields this campaign opened on.

The distinction is therefore semantic, not syntactic. A one-member union is a
defect when the field asserts assurance a reader relies on, and correct when it
pins the scope or shape the model covers, and no property of the annotation
separates those two readings.

What this settles for the gate. Multi-member string unions on model fields are
mechanically decidable and number 59 in the registry schema; every one of them is
a vocabulary and can be required to resolve to a named enum with no judgement
call. One-member unions cannot be counted toward a zero, so a gate that includes
them would need either a list of permitted pins, which is the mechanism this
campaign exists to remove, or a false count. The two degenerate conformance
fields are named defects to be repaired individually rather than a class to be
gated.

This also supersedes the census figures the audit opened with. Those counted
every Literal subscript anywhere in the package, which mixed model-field
annotations with type aliases, call-site annotations and non-string unions, and
the total was not reproducible under any single scoping. The defensible measure
is annotated model fields in the registry schema, excluding tests: 59
multi-member string unions, 39 one-member string unions, 6 non-string unions.

### named-literal-aliases-evade-the-proposed-gate | critical | Naming a union moves it out of sight of a gate that looks only at fields

The registry schema declares 51 further closed vocabularies as named type
aliases, 9 in the current alias syntax and 42 as plain assignments, on top of
the 59 spelled directly at a model field. Fields annotated with them are
ordinary conformance fields carrying ordinary closed sets, and three were
confirmed by inspection rather than inferred: a finding kind, a coverage gate
status and a declared axis.

The gate as scoped in the decision record counts unions spelled at a model
field. An alias is not spelled at the field, so every one of these reads as
clean, and the zero the gate would report is reachable without changing
anything: moving an inline union into an alias satisfies it. A gate that can be
satisfied by renaming is not a gate, and this one would have shipped with the
campaign's own count as its evidence.

The census that produced the 59 has the same blind spot for the same reason, so
the figure is a floor rather than a total. The two populations are not
equivalent, though, and the difference matters for the repair. An alias is
already a single named definition, which is most of what the campaign wants; it
is the wrong KIND of definition, because a string union cannot carry members,
docstrings or a derived subset the way an enum can, and cannot be narrowed or
iterated. Promoting an alias is therefore a retyping, while promoting an inline
union is an extraction followed by a retyping.

The predicate the gate needs is transitive: resolve a field's annotation through
any alias chain before deciding whether it names a closed union. Anything less
measures spelling rather than structure, which is the failure mode this campaign
was opened to remove.

### transitive-census-supersedes-every-earlier-count | high | Resolving alias chains raises the vocabulary count from 59 to 96 and gives the campaign its real scope

Resolving each model field's annotation through any alias chain before judging
it gives the first count that cannot be satisfied by renaming. Registry schema
model fields, excluding tests: 96 carry a multi-member closed string vocabulary,
54 spelled at the field and 42 reached through one of 54 alias names. 76
distinct vocabularies, of which 13 are used at more than one field. Separately,
41 fields carry a one-member union and 5 a non-string union, both outside the
gate's subject.

Every earlier figure in this audit is superseded. The 59 was a floor that missed
the alias population entirely, and the 152 before it counted subscripts rather
than fields. The three numbers are not corrections of one measurement but three
different measurements, and only this one answers the question the gate has to
ask.

The duplicated thirteen are where the campaign's value concentrates, because
each is a vocabulary the schema already repeats verbatim across models: an
evidence tier at three fields, a calculation class at three, a source kind of
seven members at three, a rectification scope at three, a condition mode at
four.

### evidence-tier-is-both-a-vocabulary-and-a-rubber-stamp | high | The same concept is a four-member union on one model and a one-member union on another

The evidence tier is declared with four members on the source reference, the
coverage gate and the live cross-reference decision, and with exactly one member
on the legal reference. The same word names a real vocabulary in three places
and a constant in the fourth, in the same package, and one of the four-member
declarations sits in the same file as the degenerate one.

This is the campaign's whole thesis in a single field. A reader cannot tell from
the key which reading applies, a report that aggregates across the four cannot
be meaningful, and the degenerate declaration certifies its rows for free while
its three siblings genuinely discriminate. It also explains why the defect
survived: from the data side the legal-reference rows look like a settled
vocabulary that happens to be uniform, and only the type reveals that it could
never have been anything else.

The repair is not to widen the degenerate field to the four-member set by
assumption. Whether a legal reference can attain the other three tiers is a
question about the subject, and the enum must be introduced with whatever
members the domain actually admits rather than by copying the neighbour.

### evidence-tier-pin-was-misjudged-and-is-correct | medium | The second degenerate field is a legitimate domain pin, and this audit called it a defect twice

Two earlier findings named the legal reference's evidence tier as a degenerate
conformance field of the same class as the review status. That is wrong, and the
correction matters more than the field does.

The model is a legal-authority citation row and says so in its own docstring. A
legal reference is legal authority by definition, so the one-member declaration
pins what the model IS rather than certifying anything about it. The coverage
aggregation reinforces this: it reads the tier from source references and live
cross-references, and never from legal references at all, so the pinned value
does not enter any tier count and cannot inflate one.

It is therefore the same class as the scope pins already judged correct, and the
campaign must not retype it. Widening it to the four-member vocabulary would
assert that a legal reference could attain the other three tiers, which is a
claim about the subject that nothing supports.

Why it was misjudged twice is the transferable part. The field carries a key
name shared with a real four-member vocabulary elsewhere in the same package,
and the earlier readings inferred the defect from that collision plus the
one-member shape. Both signals were present and neither was sufficient. The
distinguishing question is not whether a vocabulary is degenerate but whether
the field makes an assertion a reader relies on: the review status claims
assurance that may or may not exist, while the tier restates the model's own
identity. Only the first can be false.

The name collision remains a legibility cost, since one key means a
discriminator on three models and an identity restatement on a fourth, but that
is a naming observation and not a conformance defect.

### enum-promotion-needs-a-coercion-hop | critical | Retyping a union as an enum stops the tree loading unless the boundary hop is added in the same change

The first vocabulary promoted to a real enum was a rectification scope declared
three ways: a private union alias, a public alias re-exporting it, and a consumer
importing the public name and re-privatising it. Collapsing all three onto one
`StrEnum` was correct and the tree stopped loading immediately: every one of the
56 declarations carrying the value failed as a bare string where a member was
required.

The cause is a property of the schema rather than of the change. Registry models
validate strictly, which refuses a plain token for an enum-typed field, so each
enum-typed field reaches its member through a boundary coercion hop the schema
base already provides as a factory. A union has no such requirement, so the hop
is exactly the thing a promotion has to add and exactly the thing that looks
unnecessary while the union is still in place.

This is the third appearance of one shape in this campaign, and the shape is now
clear enough to state generally: a repair that narrows what a value may be must
land the widening that keeps existing rows valid in the same change. The codec
collapse withdrew a spelling while rows still used it. This promotion withdrew a
type while rows still carried the old shape. In both cases the tree was
unloadable between the two halves, and in both cases the local verification
passed because it tested the half that had landed.

The transferable check is therefore not a better regex or a wider grep but a
different question: after this edit, can the registry still be loaded? That
question would have caught all three instances immediately, and it costs one
call.

### degenerate-review-status-retired-499-rows-now-read-unreviewed | high | The rubber stamp is gone and the tree reports less assurance than it did

The one-member review status has been retired onto the merged vocabulary and its two
consumers now reference that vocabulary directly, with no alias standing between
them. All 530 rows moved in the same change as the type, because withdrawing the
only token they carried without sweeping them first makes the tree unloadable.

The rows resolved from the reviewer token each already carried. 499 source rows
carry neither a reviewer nor a date, so they cannot honestly claim a review and now
read as pending. 24 parameter rows name an agent, several of them naming an
outstanding operator action in the same breath, and read as agent-reviewed, which is
exactly what that member means. The remaining 7 name the operator alone.

The campaign's visible assurance therefore fell by 499 rows without a single fact
changing, which is the intended outcome and the one most likely to be misread as a
regression. Nothing in the tree reads either field, so no gate moved; what changed is
that the rows can now say they are unreviewed, which the previous type made
unrepresentable.

### seven-rows-assert-an-untyped-operator-countersignature | high | The only rows promoting a free-text token into countersigned authority, and they cover live tax rates

Seven parameter rows carried the bare reviewer token naming the operator, and the
retype transcribed them onto the countersigned member. The claim was already in the
tree and is not created here, but this is the single place in the registry where an
unverifiable string becomes a typed assertion of operator signoff, and it deserves
naming rather than quiet transcription.

The rows are not incidental. Three are the IRPF imputación rates keyed to whether a
cadastral revision is recent, and four are the IVA recargo de equivalencia rates
including the tobacco rate. These are values a filing depends on.

The tension is with a principle the codebase states plainly elsewhere: the dev-side
stamping vocabulary deliberately omits the countersigned member because an agent
writing that an operator reviewed something is the dishonesty the conformance
feature exists to detect. That principle governs the write path and says nothing
about transcribing an existing declaration, so the retype is not a breach of it. It
does mean these seven are the rows a future verification should reach first, and
that no further row should acquire that member without a person behind it.

### vocabularies-nested-in-generics-evade-the-census-again | high | A third counting method, and the gate predicate must walk the whole annotation subtree

The transitive census resolved alias chains but still read only a field's outermost
annotation, so a union used as a mapping key or a container element stayed invisible.
Walking the full annotation subtree finds 11 further fields carrying 9 further
vocabularies: a settlement direction keying a reconciliation mapping at two fields, a
corpus tier at two, a dependency role and treatment, an export repeat mode, and two
extraction axes.

This is the third counting method this campaign has used and the third to be
superseded, and the pattern in the three failures is the same one the campaign
exists to remove. Each method measured a SPELLING -- the token at the field, then
the token behind an alias, now the token inside a generic -- when the property that
matters is structural: does this field admit a closed set of strings, however the
annotation is written.

The consequence for the gate is concrete and non-negotiable. Its predicate must
resolve alias chains AND walk nested annotations, or a union survives by being moved
one level inward, which is a rename in a second disguise. A gate satisfiable by
either move is not measuring the defect.

The consequence for the campaign's arithmetic is that no total in this audit should
be read as final. The right reading of every figure here is a floor established by
the method that produced it, and the method has been wrong three times.

### item-two-sweep-missed-every-test-fixture | medium | The token lived in Python fixtures as well as shipped data, and the sweep read only the data tree

Retiring the degenerate review status swept the shipped registry tree and left the
same token standing in test fixtures: inline TOML inside Python test modules,
keyword arguments constructing the model directly, and TOML text assembled inside a
list literal. Eight fixture files and two constructed lines carried it, and the
first deadline-ownership test to run after the retype refused with the token the
type no longer admits.

The repair was the same reading the shipped rows got, since the fixtures carry
neither reviewer nor date either. The lesson is the recurring one in a new place: the
sweep was scoped to where the value was expected to live rather than to everywhere it
occurs, and a value that appears in fixtures is not confined to the data tree just
because that is where its production rows sit.

### canonical-scan-supersedes-all-four-counts-at-118-fields | high | The campaign finally has one structural measurement instead of four spellings

The counting is now a module rather than an ad-hoc script, and it resolves instead
of matching: alias chains are followed and the whole annotation subtree is walked, so
a field is in scope when its annotation admits a closed set of two or more strings
however that annotation happens to be written. It reports 118 model fields carrying
95 distinct vocabularies.

That is higher than every previous figure, and the sequence of four is the finding.
Each earlier method measured where the tokens were written, and each was superseded
within a day by a place they were also written. Both moves that defeated the earlier
methods -- renaming a union into an alias, pushing it one level inward as a mapping
key -- are the kind a future author makes without intending an evasion at all, which
is precisely why a spelling-based gate cannot hold.

The scan also corrects two vocabularies this audit had already named. The evidence
tier is declared at four fields, not the three reported earlier: a portal
compatibility reference carries it too, reached through an alias. The corpus tier is
likewise at four, two of them nested inside a container and two reached through an
alias and nested, a combination no earlier method could see at all.

The module records its own blind spot rather than leaving the zero to overstate
itself. It reads annotations, so a vocabulary enforced by a validator comparing
against a tuple of literals, or by a membership test against a module constant, is
invisible to it. Those are reachable by semantic search and not by any AST census,
which is the same limitation the helper-body census in this package documents for
semantic mirrors. The zero this scan can report is a zero for declared annotations,
and the gate built on it must claim no more than that.

### two-vocabularies-collide-on-one-name-and-must-not-merge | high | Same word, overlapping members, different axes, both reached from one module

Promoting the deadline cadence field produced an immediate load failure: the enum
introduced for it shadowed an existing enum of the same name already imported into
the same module, and the module broke on a member the new one did not have.

The two are not duplicates and must not be merged. The core vocabulary describes a
period's SHAPE and carries instalment and extended members; the registry field
describes a filing CADENCE and carries an ad-hoc member the other has no equivalent
for. They share three member values, which is what makes the collision look like
duplication from a distance and is exactly why it is not.

This is a case the campaign had not met. Every earlier promotion resolved a
vocabulary that was genuinely repeated, and the operation was mechanical once the
sites were found. Here the sites were found correctly and the mechanical step was
still wrong, because naming the enum is a domain judgement rather than a
transcription: the concept needed its own name, and the field's key was a false guide
to what the concept was.

The general rule this settles for the remaining promotions. Before introducing an
enum, check whether the name is already bound in the modules that will import it,
and read the members rather than the key. Two vocabularies sharing a key name and
some members is a signal to distinguish them, not to unify them, and the campaign's
own charter is the reason: one definition per value set is right, and forcing two
value sets into one definition is the same error wearing the campaign's clothes.

The renamed cadence vocabulary carries a docstring stating the distinction so a later
reader does not attempt the merge this finding refused.

### the-scan-cannot-tell-repetition-from-deliberate-narrowing | critical | Five data-type vocabularies are a subtype lattice with its own gate, and promoting them would widen what four surfaces accept

The scan reports two fields sharing a five-member scalar vocabulary and offers them
as a duplicated pair to promote. They are not a pair. A gate already in this package
records that five surfaces declare a vocabulary for the same field name and that four
of them are deliberate narrowings of the fifth: a casilla may hold a tax identifier or
an account number where a manual input may not. Its own prose says collapsing the five
into one would widen what several surfaces accept rather than remove duplication.

That gate is also the better answer to the problem this campaign was opened on. It
does not restate any vocabulary; it reads each from the model that declares it and
asserts the containment relationship holds, on the stated grounds that a test listing
the members would drift the moment either side changed and would then be asserting its
own copy. The relationship it defends had been maintained by hand and held only
because nobody had broken it.

So the campaign's central signal is weaker than it looked. Two fields sharing a member
set may be one vocabulary repeated, which is a defect, or two narrowings that coincide
today, which is a contract. The scan sees only the members and cannot separate them,
and the difference is invisible to any measurement of the annotation.

Three consequences follow. Promotion cannot be applied from the duplicated list
without reading each candidate's intent first, and this is the second candidate in two
iterations where the mechanical step would have been wrong. The correct end state for
a lattice is one canonical enum with the narrowings expressed as derived subsets over
it, not five independent enums and not one widened enum. And the gate this campaign
plans must not assert that every closed vocabulary is exactly one enum, because that
assertion is false here and would force the lattice to be flattened to satisfy it.

There is a further hazard specific to promotion. The existing containment gate reads
its vocabularies through the typing introspection that works on a literal union and
does not work on an enum, so promoting any member of the lattice without repairing
that gate would leave it reading nothing while still reporting green.

### a-lattice-is-rooted-not-flattened | high | The evidence tier shows the shape every narrowing should take

The evidence tier existed at three independent levels: the full vocabulary, a subset
naming the tiers that ground an entity on published material rather than on the law,
and a one-member pin for the law alone on two models. Nothing derived any level from
another, so a member added to the full set never reached the narrowings and a
narrowing could drift outside the set it was supposed to narrow.

The repair kept every level and removed only their independence. The full vocabulary
is one enum; the subset is a tuple of its members rather than a restated pair of
strings; the pins are expressed as a single-member literal OVER that enum rather than
as a string that happens to match. A member added to the vocabulary now reaches every
narrowing by construction.

This answers the question the data-type lattice raised and could not settle. A
narrowing is not duplication and must not be collapsed, but it also must not be
independent. Rooting it in the canonical definition preserves the contract and
removes the drift, and it is the shape the rest of this campaign's lattices should
take.

### the-load-check-proves-loading-not-resolution | medium | A missing import survived the standing check and surfaced only in an application test

The one-call registry load has caught five breakages in this campaign and is the
cheapest verification available, so its limit is worth stating precisely. Promoting
the corpus tier moved two validator comparisons onto enum members and the import that
made them resolvable was not added. The load check passed anyway, because the
validator branch those comparisons sit in is not reached while loading the bundled
tree. The failure appeared later, in an application-level export test, as a plain
name error.

The check therefore proves that the tree loads, not that every path in the modules it
touched resolves. It remains the right first call after any narrowing edit; it is not
a substitute for running the owning tests, and an edit that changes a comparison
inside a conditional branch is exactly the shape it cannot see.

### a-sweep-destroyed-the-proof-the-campaign-had-just-written | high | Canonicalising every occurrence removed the deliberate counter-example

Sweeping the retired encoding spelling across the source and development trees
rewrote a test written one iteration earlier whose entire purpose was to prove that
spelling is refused. The sweep canonicalised the input, leaving a test named for a
refusal that no longer supplied anything to refuse: green, and asserting nothing.

This is the eighth appearance of the over-broad sweep in this campaign and the most
instructive, because the earlier seven missed occurrences and this one destroyed a
deliberate occurrence. A repair sweep and a negative fixture are indistinguishable by
pattern -- both contain exactly the token being retired -- and only intent separates
them.

The rule that follows is narrow enough to apply. A sweep that removes a value must
exclude the tests that prove the value is removed, and the cheapest way to honour it
is to run the owning tests immediately after the sweep rather than only at the end of
the iteration, because a proof turned vacuous still passes and will not announce
itself.

### a-design-blocker-was-asserted-without-being-tested | high | Two vocabularies were reported blocked on a constraint a five-line check disproved

Two remaining vocabularies were reported as blocked because a coercion hop supposedly
cannot attach to a mapping key the way it attaches to a scalar field. The claim was
never tested. A five-line model under the same strict configuration the registry uses
accepts raw string keys through a hop on the key type and still refuses an unknown
key, so the constraint does not exist and both vocabularies were promotable the whole
time.

The error is worth recording because none of this campaign's other disciplines catch
it. The sweeps, the load check, the counter and the review rounds all operate on
edits that have been made; nothing operates on a claim made in a status report about
work not yet attempted. The claim was inferred from the SHAPE of the annotation --
a key position looks unlike a field position -- which is the same reasoning that
produced two retracted one-member findings and one wrongly merged cadence enum.

The rule is the cheap one: a stated limitation is a hypothesis until a call is made
against it, and in this codebase that call is usually under ten lines. Reporting a
blocker costs the campaign a decision it did not need to defer.

### promotion-breaks-annotations-the-counter-cannot-see | high | Collection fields typed on a promoted vocabulary lose their coercion silently

Promoting the evidence tier left four fields elsewhere annotated as tuples of that
vocabulary. They had been correct against a string union and became refusals against
an enum, because a container element gets no coercion hop from the field that holds
it. The failure surfaced two promotions later, in an application projection, as a
validation error naming an element index.

The counter cannot find this class and should not be extended to. It searches for
closed vocabularies still spelled as unions, which is what to promote; these fields
are already typed on the vocabulary, which is what promotion produces. They are not
candidates, they are collateral, and the two populations are disjoint by
construction.

So the promotion procedure needs a step the counter does not supply. After the enum
lands, every annotation naming it must be reviewed for whether it needs the coercing
alias rather than the bare member type -- container elements, mapping values and
defaults included. The counter finds what to promote; it does not find what
promotion breaks, and reading its output as a complete worklist is what allowed this
to reach an application test.

### the-charter-reached-zero-and-the-long-tail-is-not-debt | high | Sixteen promotions took duplicated vocabularies from fourteen to zero, and the seventy-four that remain are a different claim

The campaign's charter was that a value set with two declarations has two definitions.
Measured by the canonical scan, that population was fourteen and is now zero across
sixteen promotions, and a gate asserts it with no allowlist, no baseline and nothing
to add an exception to.

Seventy-four single-site vocabularies remain and are deliberately not counted as
outstanding defects. A union declared once is already one definition; promoting it
buys typing, member documentation and uniformity with the rest of the schema, not
de-duplication. Reporting them as remaining work would restate the campaign's success
as failure, and asserting zero of them in the gate would assert a goal this campaign
neither met nor set.

The distinction matters for whoever picks this up. Closing the long tail is a
reasonable follow-on with its own argument; it is not the completion of this one.

### the-gate-asserts-only-what-its-instrument-can-prove | high | Three limits are written into the gate rather than discovered later

The gate names what it does not claim, because each limit was learned the hard way
during the campaign and would otherwise be read as a hole.

It does not claim every closed vocabulary is an enum, because the long tail above is
not a defect. It does not claim a vocabulary appears once in the type system, because
two narrowings of the casilla taxonomy are contracts that were rooted rather than
removed, and flattening them would widen what those surfaces accept. And its zero is a
zero for DECLARED ANNOTATIONS: the scan reads annotations, so a value set enforced by
a validator comparing against a tuple, or by a membership test against a module
constant, is invisible to it and to the gate.

That third limit is inherited, not chosen, and stating it is the difference between a
gate and a claim. A green result here means no vocabulary is declared twice in an
annotation; it does not mean the codebase has one definition per value set everywhere.
Finding the rest is semantic search by meaning, which is how this campaign found an
aliasing normaliser and two byte-identical enums no name search reached.

### the-campaign-misjudged-its-own-work-five-times | medium | Every wrong call came from reading a shape instead of running a check

Five substantive claims made during this campaign were wrong, and the pattern is one
pattern. Two one-member unions were called defects because they had one member, when
the field restated its own model's identity. A cadence enum was nearly merged with a
period-shape enum because they shared a name and three values. A coercion hop was
reported as impossible on a mapping key. A containment gate was reported as certain to
go blind on promotion, when it went blind on the opposite side from the one predicted.

Each was an inference from the SHAPE of a declaration, stated as fact, and each was
refuted by a check costing under ten lines. The disciplines this campaign accumulated
-- the load check, the counter, the sweep rules, the review rounds -- all operate on
edits already made. None of them examines a claim about work not yet attempted, which
is where every one of these five originated.

The transferable rule is cheap enough to always apply: a stated limitation is a
hypothesis until a call is made against it, and in a codebase with a live interpreter
that call is almost always shorter than the sentence asserting the limitation.

### the-zero-was-registry-scoped-and-was-reported-as-if-global | critical | Package-wide the same predicate finds forty-two duplicated vocabularies, three of them crossing the scanned boundary

The scan, and therefore the gate, reads one package: the registry schema. Run over the
whole product package instead, the identical predicate finds 42 duplicated
vocabularies, and 3 of those have one declaration inside the scanned package and one
outside it. Those three are invisible to the shipped instrument by construction, not
by oversight, because it cannot see across the boundary it is scoped to.

The sharpest is the casilla data-type vocabulary. Its nineteen members were rooted
into a canonical enum inside the registry during this campaign, and the same nineteen
members are declared again at a modelo edit surface in the application layer. The
campaign built the canonical definition and never saw the copy.

The reporting failure is the finding. The registry-scoped zero is real and the gate's
own docstring says "schema field", but the progress reports said "duplicated fourteen
to zero" without the qualifier carrying any weight, which reads as a claim about the
codebase. It is not one. Every future statement of this number needs its scope
attached, and the follow-on question -- whether the gate should widen to the package
or a second gate should own the boundary -- is open and unargued.

A smaller error rode along: the canonical data-type enum was reported as having twenty
members and has nineteen. It was never counted.

### a-peer-commit-dropped-two-promotions-and-the-gate-caught-it | high | The tree is co-owned, and the gate proved to be the thing that noticed

Two promotions that had landed and verified -- the date axis and the casilla data type
-- are absent from the working tree. Neither was reverted by this campaign. A peer
session committed the registry package as it saw it, twice, and those snapshots
predated the two later promotions; both files are now clean against the peer's
commits, so the work is gone rather than merely uncommitted.

The peer's commit subjects name this campaign's own work, so the two sessions are
promoting the same vocabularies into the same files concurrently. That is a
coordination failure rather than a technical one, and it has a cost worth recording:
re-landing now means writing files another session is actively committing, which is
how the two promotions were lost in the first place.

What worked is the gate. It went red on the exact two vocabularies within one call of
the regression, named both, and cost nothing to run. A campaign whose verification
depended on a forty-minute suite would have reported completion and learned this much
later, if at all.

### three-sessions-share-one-worktree-and-this-one-swept-the-others | critical | The vanishing work is mutual, the git identity cannot separate us, and an earlier finding misattributed it

An earlier finding said a peer session's commits dropped two of this campaign's
promotions. The peer has since stated it has made no commits at all this session and
has never edited the five files involved, and the evidence supports that: sixty-five
commits landed after this campaign's own, every one under the same author identity, so
authorship cannot distinguish which session produced any of them. A third writer is
batch-committing the shared tree, and one of its commits lands three seconds after a
commit carrying the peer's helper work. The attribution in that finding was a guess
presented as a fact and is withdrawn.

The real condition is worse and symmetric: three sessions are working in ONE worktree,
not in worktrees of their own. This campaign's own commit swept the peer's uncommitted
consumer-repointing three times -- a shared key helper across nine command-spec
modules, a bucket identifier across six live CLI modules, and a record index. In each
case the peer's new canonical definition survived, because a new file is added rather
than reverted, while the consumer side went back. That leaves the worst available
state: the shared helper and the duplicates it was written to replace, sitting side by
side, with nothing failing to announce it. The peer found it only by re-running its own
census and seeing two counts that had reached zero standing at nine and five.

That failure mode is this campaign's central defect wearing someone else's clothes. A
de-duplication effort whose consumer sweep is silently reverted produces exactly the
duplication it exists to remove, and produces it invisibly, because a duplicate is not
a crash.

Two practices follow, and the second is the one that generalises. Sessions sharing a
tree must not use a whole-tree commit, because a whole-tree commit in a shared tree is
indistinguishable from a revert of everything uncommitted. And a campaign that measures
its own progress must re-run its counter after any commit it did not make, since the
count is the only thing that reports a silent revert -- no test failed for the peer, and
none failed here either until the canonicalization gate went red.

## Recommendations

Collapse the duplicate codec members to one, which is a correctness repair
rather than a design change and can land on its own evidence.

Replace the degenerate `Literal["reviewed"]` with the real vocabulary, and
expect the 531 stamps to stop being free. The failures that surface are the
finding, not a regression.

Promote each duplicated inline vocabulary to a single canonical enum and make
the schema reference it, so the value set has one definition and the TOML has
one authority.

Gate the result the way the cross-package private-import rule is now gated:
derived from the tree on every run, with no allowlist to add a new exception
to, so a fresh ad-hoc vocabulary has to be fixed rather than recorded.

A follow-on ADR must decide two things this audit deliberately does not: which
provenance is legitimately declared in shipped registry data versus which is
development metastate that belongs outside the wheel, and whether a closed
vocabulary may ever be expressed as an inline union or must always resolve to a
named enum the schema imports.

The remaining work this campaign deliberately did not do, each with its own argument
rather than as a continuation of this one.

Seventy-four single-site vocabularies could be promoted for typing and documentation.
That is a uniformity argument, not a de-duplication one, and it should be made on its
own terms.

The scan's blind spot is real and unmeasured. A vocabulary enforced by a validator or
a membership test rather than by an annotation is invisible to every instrument this
campaign built, and nobody has counted that population. A semantic sweep is the only
method that reaches it.

Seven legal-parameter rows assert an operator countersignature transcribed from a
free-text token, covering IRPF imputacion and IVA recargo de equivalencia rates. They
are the only place in the tree where an unverifiable string became typed countersigned
authority, and they warrant either verification or downgrade.

## Finding 36 — the identity-check verdict had five declarations, not three

The scan named three sites for `[invalid, unknown, valid]`. Reading the members rather
than the key found two more that no field annotation could expose: `SedeVerdict`, a
private alias in `adapters/outbound/aeat/sede/_adapter_utils.py`, and a membership
tuple in `entrypoints/cli/_app_live_verify_cli.py` testing `value in (None, "valid",
"invalid", "unknown")`. The private alias is the sharper defect: it sat in an
underscore module, so no other package was permitted to import it, which is precisely
why the two checkers beside it spelled the union inline instead.

Resolved as `core/identity_check_verdict.py` with two rooted forms — the `StrEnum` for
the producer, and `IdentityCheckVerdictValue` for the payload fields. `SedeVerdict` and
`VerifyVerdict` are both deleted; six modules now import one definition.

The producer's output still compares equal to its raw token, so no downstream string
comparison changed behaviour. Verified, not assumed.

## Finding 37 — the last registry-boundary crossing is closed

`[any, non_negative, non_positive]` was declared by `CasillaConstraints.sign` in the
registry schema and restated by `SheetCellConstraint.sign` in the spreadsheet storage
layer. This was the one vocabulary the wide scan reported as crossing the boundary, and
it is the exact shape of the concern that opened this campaign: the registry declares
the schema, and a second layer had quietly declared it again. A member added to the
registry would have left the workbook accepting a value the engine rejects.

Promoted to `schema_base.py` in all three rooted forms. 811 shipped TOML rows declare
`sign`, and the tree loads, which is what proves the coercion hop accepts the real
tokens rather than only the synthetic one a unit test would have supplied.

Package-wide count after both: 26 duplicated vocabularies, **0 crossing the registry
boundary**. Registry-scoped duplicated remains 0.

## Finding 38 — the scan's blind spot is now measured, not just declared

Both findings above turned on declarations the scan structurally cannot see: a function
return type, a private alias, and a membership tuple in a validator. The module has
always documented this limit. What is new is that it has now cost two real defects in
two consecutive targets, which makes it the campaign's dominant remaining risk rather
than a footnote — the annotation count can reach zero while the vocabulary surface has
not.

## Finding 39 — the decimal separator was declared ten times across five files

The scan named three fields. Grepping the raw token pair found ten annotation sites in
five modules: the three fields, plus a detector's return type, a `Counter` type
parameter, an evidence helper's return, and three function parameters in the provider
base and the bulk importer. Every one of the seven extra sites is a form the scan
structurally cannot reach, because it reads field annotations only.

Resolved as `DecimalSeparator` in `core/decimal/grammar.py`, beside the separator
normalisation that already lived there. 372 provider and invoice tests pass, 33 tabular
dialect tests pass.

## Finding 40 — one token, two vocabularies, correctly left apart

`ObservationSourceKind` already declared `operator_manual`, which made it look like the
canonical home for `[aeat_live, local_filing, operator_manual]`. It is not. It splits
the AEAT origins three ways for filing-grade evidence and uses `app_filing` where the
sheet vocabulary says `local_filing`. Unifying them would have let a workbook cell
claim a filing-grade AEAT origin it never established.

The same trap appeared a second time in the same target: `_LOCAL_FILING_PROVENANCE` in
`binding_prefill.py` feeds both a `provenance` field and a `source_kind` field, and the
source kinds beside it are a different set entirely. That constant was left alone. Only
`relation_prefill.py`'s constant, which feeds `RelationValue.provenance` and nothing
else, was retired onto the member.

Promoted as `SheetRelationProvenance` in the calc-sheets records module, the module the
adapter already imported from, so the edge is one that existed rather than a new one.
48 owning tests pass.

Package-wide after three targets: 24 duplicated, 0 crossing the registry boundary.

## Finding 41 — publication_kind: ten annotations across seven modules and two layers

The scan named three fields. The tokens named ten annotation sites in seven modules --
the capsule records and their two writers, the profile aggregate and summary views, the
custody service, and a Protocol property on the custody port -- plus four value
literals. The Protocol property return type is a shape none of the earlier counting
methods could have reached.

Promoted to `ProfilePublicationKind` in `core/profile_publication.py`, chosen because the
custody adapters and the profile application code both already import from `core` and
neither may import the other.

Left deliberately apart: `ProfileRestoreAuthority` (`password`, `recovery_artifact`) sits
directly beside `publication_kind` in the same module and answers the adjacent question
of what authorised a restore. Same class of axis, different vocabulary, not merged.

446 user_profile tests pass. Four failures and five errors in that package are unrelated
and pre-existing: a bounded-regular-file guard in `custody/filesystem.py`, two undeclared
retryable error codes, a lock-ordering timeout, and a cross-process roundtrip test whose
subprocess imports `build_profile_custody_port` from the package `__init__`, which
declares `__all__ = ()` and exports nothing by design. That last one is a test written
against a facade the architecture rule removed; it cannot have passed recently.

Package-wide after four targets: 23 duplicated, 0 crossing the registry boundary.

## Finding 42 — the canonical enum existed, under a subject-specific name

`[optional, required]` was declared five times: three inline fields, one alias
(`ManualCasillaRequirement`), and one real enum, `ProfileKeyRequirement` in
`domain/contribuyente/keys.py`, whose members are byte-identical.

The judgement this target turned on is whether those are one vocabulary or several.
Three enums nearby share SOME of the members and were left alone, correctly:
`IvaComponentPresence` adds `unknown` and `zero_by_law`, `RequirementStatus` and
`ProfileFieldClassification` split applicability out. Each is a finer taxonomy, and
collapsing any of them would lose a distinction the domain relies on.

`ProfileKeyRequirement` is different. Its member set is exactly the pair, and the only
thing separating it from the other four sites is its subject -- profile keys rather than
casillas or findings. A two-member modality applied to five subjects is one vocabulary
declared five times, not five vocabularies, so it was retired onto a generic
`Requirement` in `core/requirement.py` and the name `ProfileKeyRequirement` is gone.

Deliberately not a `bool`: a boolean field named `required` reads identically whether it
was set or defaulted, and cannot carry a third member if one is ever needed. The types
that DO need a third member remain separate types.

822 contribuyente and wizard tests pass, 281 diagnostics and payload tests pass.
Unrelated failures confirmed by cause, not by assumption: a missing translation key
raised from `application/flows/scripted.py`, a forbidden `future_extension` field in an
auth payload round-trip, and four more instances of the known modelo 200 authority-grade
refusal.

Package-wide after five targets: 22 duplicated, 0 crossing the registry boundary. Across
those five, the scan reported 15 declaration sites and the raw tokens had 38.

## Finding 43 — diagnostic status, and a near-miss that must NOT be unified

`[fail, ok, warn]` had one alias (`DiagnosticStatus`) and two inline copies in the CLI
payloads, plus 26 produced values and four comparisons in `diagnostics.py` that no
annotation scan reaches. The alias became the enum, and every producer now returns a
member.

`config_payloads.py:1004` declares `Literal["ok", "fail"]` -- the same vocabulary minus
`warn`. That is a genuine narrowing, not a fourth declaration, and it was rooted as
`Literal[DiagnosticStatus.OK, DiagnosticStatus.FAIL]` rather than collapsed. A surface
that cannot warn should keep saying so in its type.

The near-miss is `HealthSeverity` in `preflight.py`: `ok`, `warn`, `error`. Two of three
members are identical and the third means the same thing under a different token. This
is the first case the campaign has met where two vocabularies are arguably one and the
member-set predicate cannot tell -- the scan groups on members, so it will never report
these as duplicates however long they diverge.

It was NOT unified, and the reason is not squeamishness: `ok`, `warn` and `error` are
serialised tokens on a preflight surface, and rewriting `error` to `fail` changes what
that surface emits. That is a wire-format change, which needs its own decision rather
than being smuggled in under a de-duplication sweep. Recorded here so the decision is
visible rather than lost.

386 diagnostics and payload tests pass. Eight failures in that batch were each traced to
cause: four are the known modelo 200 authority-grade refusal, and three more were
re-run in isolation -- two passed, proving them xdist contention rather than regressions,
and the third fails in `external_import_actions.py` on missing M303 filing evidence,
which touches none of the three edited files.

Package-wide after six targets: 21 duplicated, 0 crossing the registry boundary.

## Finding 44 — two clave sets that share a field name and five letters, kept apart

The M349 clave de operación was declared three times: a private alias
`_M349_CLAVE_OPERACION` in `domain/modelos/row_models.py` used at two fields, and two
inline copies on the wire mirrors in `operation_definitions.py`. Same root cause as the
sede verdict: the alias was underscore-private, so the wire mirrors in another package
were not permitted to import it and respelled the set instead. Making it public is the
fix; the duplication was a symptom of the privacy.

`_M347_CLAVE_OPERACION` sits forty lines away with `A`–`G`. It shares the field name
`clave_operacion` and five of its seven letters with the M349 set, and it was declared
twice on the same pattern. Both were promoted, as two separate public enums, and the
docstrings say why they are not one: the forms draw from different Órdenes
(HAC/174/2020 Anexo II and EHA/3012/2008), so a letter valid on one is not thereby
valid on the other. Proven rather than asserted -- a `B` is accepted on a 347 row and
refused on a 349 row.

Member meanings were deliberately NOT paraphrased into the docstrings. The Orden
defines them, and a gloss written from memory beside a filing-grade code set is a second
authority that can drift from the first; the citation carries the meaning instead.

Both wire mirrors are operation surfaces, so both fields take the
`Literal[Enum.MEMBER, ...]` form. Verified against the live model rather than inferred:
the mirror accepts the raw letter `E` and hydrates it to a member.

64 row-model tests and 155 M349/M347 tests pass. The one failure asserts a
human-readable substring against an error that now carries a translation key, part of an
unrelated in-flight i18n migration.

Package-wide after seven targets: 19 duplicated, 0 crossing the registry boundary.

## Finding 45 — one vocabulary under three names, plus a fourth copy in a frozenset

`write_route` was the worst fragmentation the campaign has found. Three rival names for
one value set -- `WriteRoute` in `command_spec.py`, `CommandWriteRouteScope` in
`_command_policy.py`, and an inline spelling in `_command_schema.py` -- plus
`_WRITE_ROUTES`, a frozenset the spec validator checked membership against, and a bare
`str` parameter in `storage_write_policy.py` comparing the tokens directly.

Two of those four are invisible to the scan by construction: an alias it collapses only
when the NAME matches, and a frozenset that is not an annotation at all. The gate's own
test already proves two rival aliases count as two declarations; this is that case in
production.

Unified as `CommandWriteRoute` in `command_spec.py`. The frozenset is gone -- the
validator now tests membership against the enum itself, which cannot drift from the
member list because it IS the member list. Verified rather than assumed: a known route
passes and an unknown one is refused.

`DiagnosticAudience` landed in the same pass: an alias plus an inline copy plus four
producers. The OAuth `audience` parameter in `oauth_flow.py` shares the word and means a
JWT ``aud`` claim; it was not touched.

## Finding 46 — a stale reference left by this session's own earlier rename

`test_command_spec_kernel.py` pointed at `_command_spec.py`, a filename the earlier
private-to-public promotion removed. That is debt from this session's own campaign, so
the path was corrected.

Correcting it exposed the real defect rather than fixing the test: `command_spec.py`
carries a relative import at line 16, so the `runpy.run_path` the test uses to prove the
kernel is import-light cannot succeed for any filename. The test's premise no longer
holds. It was left failing and reported rather than adjusted to pass, because the two
available repairs -- give the module a package context, or make it genuinely standalone
-- are different decisions about what the kernel guarantees.

Package-wide after nine targets: 17 duplicated, 0 crossing the registry boundary.

## Finding 47 — the canonical enum was in the same package, thirty lines up

`[apply, reject]` was declared at seven sites across three packages. `OperationResponseIntent`
already existed in `application/operations/interactions.py`, and the file's own concrete
response models already used it correctly as `Literal[OperationResponseIntent.APPLY]`.
One inline copy sat in that same module, thirty lines below the enum it should have used.

This is the third time the definition already existed and the sites spelled it anyway.
The pattern is not that authors cannot find the enum; it is that no form existed for
"either member" -- the enum had only single-member narrowings in use, so a field
admitting both had nothing to import and wrote the pair out. Adding
`OperationResponseIntentValue` gives that surface something to root against, and the
single-member narrowings on the concrete responses stay narrow, which is the point of
having both forms.

Two of the seven sites are `frozenset[Literal[...]]` -- a collection of the vocabulary
rather than one of it. Same vocabulary, different cardinality; not a second vocabulary.

365 operations tests and the TUI/censal consumers pass. Four failures in the package are
unrelated and were traced rather than assumed: three are an extra-fields refusal in
`_OperationRequestResolutionHeader` inside `registry.py`, a file this change never
touched and which contains no reference to the promoted symbol, and one is 29 projection
claims joining no surface, an auth and user-profile wiring gap.

Package-wide after ten targets: 16 duplicated, 0 crossing the registry boundary.

## Finding 48 — a whole module restating its neighbour's vocabularies

`_command_schema.py` did not duplicate one vocabulary; it duplicated a family.
`CommandCapability`, `CommandSideEffectClass`, `CommandPerformanceClass` and
`CommandParameterKind` each restated a `command_spec.py` alias of identical members
under a `Command`-prefixed name, and `_command_schema.py` already imported from
`command_spec.py`, so nothing had prevented it importing these too.

All four retired. `CommandCapabilityClass` is a real dataclass, not an alias, and
survives; the rename was ordered longest-name-first so it was never eaten by the
`CommandCapability` substring -- the same prefix hazard that produced
`CommandCommandWriteRouteValueValue` a target earlier, avoided this time by ordering
rather than by luck.

## Finding 49 — two enums with one conversion function between them

`JsonType` (a `StrEnum` in `_verb_input_schema.py`) and `CommandJsonType` (a `Literal`
in `_command_schema.py`) carried the same four members, and `_verb_input_schema.py:231`
called `JsonType(p.json_type)` to convert one into the other. That call existed only
because both declarations did. The same held for `VerbParamKind` against
`command_spec.py`'s `ParameterKind`.

Neither could simply import the other: `_verb_input_schema` imports `_command_schema`
which imports `command_spec`, so only the kernel can hold a vocabulary all three need.
Both now live in `command_spec.py`, and `ParameterKind` became a real enum rather than
staying a bare `Literal`. Its two consumers are frozen dataclasses, not pydantic models,
which is why the conversion carries no strict-validation risk -- checked before the edit
rather than discovered after it.

This target was found only because a too-broad slice deleted `CommandJsonType` by
accident and lint reported it undefined. Restoring it required asking where it belonged,
which surfaced the duplicate. Worth recording honestly: the mistake found the finding.

159 CLI schema tests pass. The four failures are byte-identical to the set failing before
this change: the 19th modelo-work command spec, the kernel `run_path` premise, the Google
typer-authority check, and the root parameter contract.

Package-wide after twelve targets: 12 duplicated, 0 crossing the registry boundary.

## Finding 50 — a bare Enum blocked its own reuse

`ProfileAuthenticationPosture` in `command_spec.py` already held the three postures, and
two payload surfaces wrote the tokens out anyway. The reason was structural, not
carelessness: it subclassed `Enum`, not `StrEnum`, so its members are not strings. A
`Literal[Posture.MEMBER, ...]` over a bare `Enum` cannot accept the plain token a
serialised payload carries, which left those fields nothing to import.

This is the same shape as the private alias and the missing both-members literal, and it
completes the pattern the campaign keeps meeting: duplication is almost never an author
declining to reuse a definition. It is a definition that cannot be reached from the
boundary that needs it -- because it is private, because it lacks the form that boundary
requires, or because it is the wrong base class.

Converted to `StrEnum`. Every existing use compares with `is` against a member, so
widening member-to-token equality changes nothing that was relied on; that was checked
across all uses before the edit, not assumed from the declaration's shape.

`MachineSecretPresence` was hosted for the first time -- both sites spelled
`Literal["absent", "present"]` and no canonical existed -- and `CommandNodeKind` needed
only an import, having existed in `command_spec.py` all along.

193 CLI schema tests pass, up from 159, with the same four pre-existing failures and no
new ones.

Package-wide after fifteen targets: 9 duplicated, 0 crossing the registry boundary. The
`_command_schema.py` / `command_spec.py` pair alone accounted for eight of the
vocabularies cleared in the last two ticks: one module restating its neighbour's
vocabulary is a far larger source of duplication than any single scattered field.

## Finding 51 — three within-file and near-file duplications

`OverviewLocalFilingState` and `OverviewCalendarEventType` both already existed in
`calendar_models.py`; the CLI payload module spelled both out twice each. Neither needed
a new enum, only the both-members literal -- the same missing form as
`OperationResponseIntent`, now the fifth instance of that specific cause.

The local filing literal is worth naming precisely: its enum's docstring insists it is
"intentionally separate from `OverviewAeatSubmissionState` so a ready or imported local
record cannot imply official AEAT submission". Rooting the payload field on that enum
preserves the separation the docstring asserts; the inline spelling did not enforce it at
all, it merely happened to list the same three tokens.

`SheetRoundingRule` was hosted for the first time. Its two fields sit in one file and a
third site -- the producer's return type in `engine.py`, plus four returned tuples and a
comparison -- was invisible to the scan.

Not unified, and the distinction matters: `engine.py:423` declares
`Literal["decimal", "money", "integer", "ratio"]`, sharing `money` and `integer` with the
rounding rule. That is the casilla data type, which says what a value IS; the rounding
rule says how it is rounded. A ratio is a data type and never a rounding rule;
`integer-ceiling` is a rounding rule and never a data type.

## Finding 52 — a second test asserting against the inert-package rule

`test_calendar_model_ownership.py` asserts `set(overview.__all__) >= {...}` for a dozen
calendar model names. `application/overview/__init__.py` declares `__all__ = ()` and
documents itself as an inert namespace, which is what `aeat-architecture-boundaries`
requires of every package initialiser.

This is the second such test found in this campaign -- the first expected
`build_profile_custody_port` from the persistence storage package initialiser. Both
assert the behaviour the inert-package rule removed, so both fail on every run and
neither can pass while the rule stands. Reported rather than repaired: deciding whether
these tests should be rewritten against the defining modules or deleted belongs with
whoever owns that migration, and two independent instances suggest there may be more.

Package-wide after eighteen targets: 6 duplicated, 0 crossing the registry boundary.

## Finding 53 — five landed, and the count reaches one

`SnapshotLifecycleState` and `ModeloWorkWizardPromptChannel` already existed; the CLI
spelled both out anyway, the first needing only a both-members literal and the second
being a rival alias (`WizardPromptChannel`) in the CLI payload module.
`ProfileDeletionHoldOwner`, `LiveCaptureMode` and `M303CompensationBasis` were hosted for
the first time; the deletion-hold owner had a third site the scan could not see, a
constructor parameter in `custody_hold.py`.

A real defect was introduced and caught here: inserting the `M303CompensationBasis` enum
before `class M303CompensationAvailableDerivation` placed it directly beneath that
class's `@dataclass(frozen=True, slots=True)` decorator, producing an enum decorated as a
dataclass. Ruff's RUF049 reported it; the decorator was restored to the class it was
written for, and both were then asserted directly -- the enum is not a dataclass, the
derivation is. Inserting text before a class is unsafe whenever the class is decorated.

97 + 11 + 54 + 34 tests pass across the five areas.

## Finding 54 — the last count is a FALSE POSITIVE, and the gate cannot reach zero honestly

The single remaining duplicate is `["1", "2"]`, declared by `M184NaturalezaInmueble` in
`domain/modelos/row_models.py` and `IndicadorAuxiliarActividad` in
`domain/iva/regimen_simplificado_rows.py`. These are not one vocabulary. One is the
nature of a property on Modelo 184; the other is an auxiliary-activity indicator in the
IVA simplified regime. They come from different forms, are already correctly named, and
each is a single declaration used at its own sites. Nothing about them should be merged.

They collide only because both AEAT code sets happen to use the digits 1 and 2, and the
scan's predicate is member-set equality. This is the mirror of the `HealthSeverity` case:
there the predicate cannot see two vocabularies that ARE one under different tokens; here
it insists two vocabularies are one because their tokens match. Member-set equality
finds candidates; it does not decide vocabulary identity.

Three ways to reach zero, and none may be taken silently:

1. Merge them. Wrong: it would let an M184 property nature validate an IVA activity
   indicator, and the shared digits are a coincidence of AEAT numbering.
2. Exempt the pair. Forbidden: the operator ruled out hand-maintained exception lists,
   and that mechanism is what this campaign exists to remove.
3. Change the predicate so a field rooted in a distinct NAMED type counts as a distinct
   vocabulary. This is coherent and allowlist-free, but it is a real trade: under it the
   `WriteRoute` / `CommandWriteRouteScope` pair -- two named aliases that genuinely WERE
   one vocabulary -- would not have been reported. It removes a false positive by
   accepting a class of false negative, and that class is exactly the module-restates-its
   -neighbour pattern that produced eight of this campaign's findings.

The gate therefore stands at one, and that one is a measurement of the instrument's
limit rather than of the codebase. Widening the gate to package scope is deferred: it
would assert a zero that is not true, and the choice above belongs to the operator.

Package-wide after twenty-three targets: 1 duplicated (this false positive), 0 crossing
the registry boundary. Registry-schema-scoped remains 0 with 73 vocabularies at 73 fields.

## Finding 55 — the blind spot, measured for the first time

The annotation scan's limitation has been documented since the instrument was written
and quantified only by anecdote: every target had more sites than it reported. A second
scan now reads the four positions it cannot -- function parameters and return types,
module-level literal aliases, membership containers, and inline membership tests.

It finds 1410 declarations in those positions, 1366 distinct member sets, and 28 sets
declared in more than one place. That population has never been visible to any gate in
this campaign, and it is roughly the same order as the annotation population the campaign
has spent its whole life reducing.

Several are inside the registry, which is where the operator's original concern sits:
`[decimal, integer, money, ratio]` at three sites, `[decimal, integer, money]` at three,
`[A, B, D]` at four across two withholding modules, `[authenticated_read_surface,
public_read_surface]` at three, and `[live, replay]` at three.

## Finding 56 — two numeric narrowings, told apart rather than merged

`{decimal, integer, money, ratio}` is the set a formula may consume as a scalar operand.
`{decimal, integer, money}` is the set written right-justified and zero-padded in a
fixed-width export. They differ by `ratio`, and that difference is the whole point: a
ratio is a scalar a formula can read and is not a zero-padded numeral.

Both are now `Final` frozensets of `CasillaDataType` MEMBERS in `schema_base.py`, beside
the enum they narrow, and the five sites that spelled them out import them.

A `StrEnum` member hashes as its own string, so a frozenset of members accepts a raw
token and a member alike. That was verified against the live enum before the edit rather
than inferred -- had it been false, every one of these membership tests would have
started returning `False` and the export would have silently switched padding.

869 registry export and formula tests pass.

## Finding 57 — an isolation floor that this campaign's own promotion moved

`test_record_design_source_selection.py` pins the exact set of globals
`resolve_record_design_binary` may reference, to prove record-design selection never
consults export-layout machinery. It failed with one extra name: `RegistrySourceKind`.

That is this campaign's debt. The selector used to compare `source.kind` against a bare
string; the earlier promotion made it compare against the member the schema defines,
which added a global reference. The test's own comment anticipates exactly this -- it
warns that a floor pinning a stale spelling "reds on someone else's correct relocation".

The floor was updated rather than the code reverted, because the isolation the test
protects is untouched: `RegistrySourceKind` is defined in `schema_base`, which is schema
vocabulary and not an export layout, and the test's separate assertion that the selector
imports no export-layout module still has to hold on its own. 22 tests pass.

Worth stating plainly: a promotion that replaces a string comparison with a member
reference changes a function's global set, and any test asserting that set exactly will
fail. This is the second class of collateral the campaign has produced, after imports.

## Finding 58 — a Protocol property, five files, and narrowings that had to survive

`["live", "replay"]` was the shape the annotation scan is least able to see: a Protocol
property return type. It appeared twice in full and five times as a single-member
narrowing -- three live drivers returning `Literal["live"]` and two replay drivers
returning `Literal["replay"]`.

Promoted to `CheckerDriverMode` in `checker_oracle_flow.py`, where the Protocol lives.
The narrowings were rooted as `Literal[CheckerDriverMode.LIVE]` and
`Literal[CheckerDriverMode.REPLAY]` rather than widened to the both-members alias. That
distinction is not cosmetic: a live driver reporting itself as a replay, or the reverse,
is exactly the confusion that would let evidence-replay results be read as live AEAT
observations. The type keeps saying which one each driver is.

## Finding 59 — a legally grounded subset, spelled four times

`{"A", "B", "D"}` is the set of Modelo 190 claves whose rows carry the identification
block. It appeared four times across two registry modules, three of them assigning the
same local name `clave_abd`, which is a vocabulary with a name that never became a
declaration.

`RetencionClave` already existed in `core/aggregation.py`, carrying the full A-L
catalogue and its Orden citation. The subset is now `IDENTIFICATION_BLOCK_CLAVES`, a
frozenset of its MEMBERS, so a change to the catalogue cannot leave the subset naming a
letter it no longer has. Member meanings were not restated; the enum cites the Orden and
one citation is enough.

283 withholding, oracle and sede tests pass.

Blind-spot scope after three targets: 28 -> 24 member sets declared in more than one
place. Annotation scope is unchanged at 1, which is the point: this work is invisible to
the shipped gate, and the gate's number would have looked identical had none of it
happened.

## Finding 60 — a six-token registry vocabulary compared as bare strings

`schema_verification.py` decides what a live cross-reference may do by comparing
`surface` against six bare string tokens, and two of the groupings were written out
repeatedly: the read surfaces three times and the simulator surfaces once, with the same
tokens also compared in `remote_state_guard.py` and `live_parity.py`.

Declared as `LiveVerificationSurface` with two named subsets. `READ_SURFACES` is the
one that carries weight: those surfaces must refuse synthetic data AND are restricted to
safe HTTP methods, and both rules were enforced by separately written pairs. A surface
added to the set now inherits both rules at once rather than one of them, which is
exactly the failure mode a duplicated membership test produces -- it does not break, it
under-enforces.

The `surface` parameters stay annotated `str`. A member compares equal to its token so
nothing about validation changes, and retyping a validated field is a separate decision
from naming the vocabulary. Verified the two subsets are disjoint rather than assuming
it.

333 verification, remote-state and parity tests pass; the single failure is the known
modelo 714 coverage gap.

## Finding 61 — two tokens for what may be one concept, left alone

`schema_verification.py` uses `static_official_documentation`; the
`CrossReferenceClassification` alias in `remote_state_guard.py` uses
`static_official_only`. The two vocabularies overlap on three tokens and diverge on the
rest, and this pair reads like one concept under two spellings.

Not unified, for the same reason as `HealthSeverity`: these are declared tokens on a
registry surface, and deciding they are one concept means changing what one of them
emits. That is a registry-declaration change with its own grounding requirement, not a
de-duplication edit. Recorded so the question is visible.

## Finding 62 — the campaign's own rule, broken by the campaign

`ProfileHealthStatus` was a `Literal` alias of eight verdicts whose docstring carried an
explicit warning: `profile_locked` must never be absorbed into `missing_profile_record`
or `profile_record_unreadable`, because "collapsing the three told an operator whose
profile was merely locked that their financial records were gone". That warning was
prose at one site and three separately hand-written pairs everywhere else.

It is now a `StrEnum` with `RECORD_FAULT_STATUSES` naming the two, and
`UNREADABLE_PROFILE_STATUSES` derived from that set by union rather than restated, so
the two cannot disagree about which record faults exist. The warned-about member is now
structurally excluded, proven rather than asserted.

The promotion also broke sixteen tests, and the cause is the exact rule this campaign
has been writing into its own procedure since the first target: `ActiveProfileHealth`
is a strict frozen model, and its `status` field was given the BARE enum. Strict
validation refuses a raw token for a bare enum, so every construction from a persisted
string failed with `Input should be an instance of ProfileHealthStatus`. The field needed
the literal-over-members form.

Two things are worth recording beyond the fix. First, the load check passed throughout:
the tree loads, every module imports, and nothing about the failure was visible until the
owning tests ran. That is the whole reason the procedure puts the tests immediately after
the load check rather than treating a clean import as success.

Second, the first test run used a broad `-k` filter and reported 126 failures, in which
these sixteen were invisible. Running the EDITED MODULE's own tests found them at once.
A wide selection is not a stronger check than a narrow one; it is a noisier one, and
noise hides regressions rather than surfacing them.

After the fix: 47 failures fell to 39 and 98 passes rose to 106 in that package, with
the `ActiveProfileHealth` class of error gone entirely. The 39 that remain are the
`_WorkflowRunEnvelopeHeader` extra-fields refusal in `adapters/persistence/workflow.py`
-- a file this change never touched, and the same shape as the known
`_OperationRequestResolutionHeader` failure -- plus the inert-package cluster.

Blind-spot scope: 23 -> 21 member sets declared in more than one place.

## Finding 63 — a narrowing that keeps a legal distinction

`["notificacion", "comunicacion", "pendiente", "unknown"]` and its two-member subset
were spelled six times in one sede module: the full set on the strict observation field
and a parser return, the subset on three parameters and the summary-table extractor.

`SedeNotificationTipo` now holds all four and `SummaryTableTipo` names the subset.
The subset is a real narrowing rather than a second vocabulary: a summary table names
one of the two kinds or says nothing at all, so `PENDIENTE` and `UNKNOWN` are
unreachable there. Keeping it narrow stops a pending row being passed where a resolved
kind is required -- and the distinction it protects is legal, since a notificacion opens
a response window and a comunicacion does not.

The observation model validates strictly, so the field takes the literal over the
members. That was checked BEFORE the edit this time, which is the direct consequence of
the previous finding.

43 notifications tests pass.

## Finding 64 — two custody effects that must not be confused

`["process-secret-revocation", "local-session-acceleration"]` appeared at four
annotations and four call sites across five modules. They are not two points on one
axis: one destroys a process secret, the other caches a local session, and a receipt
attributed to the wrong one claims a secret was revoked when it was not.

Now `CustodyReceiptOwner`, with the receipt field taking the literal-over-members form
because `ProfileCustodyOwnerReceipt` is strict-frozen -- again checked first.

Ruff reported `S105 possible hardcoded password` on the member whose name contains
`SECRET`. That is a false positive on a receipt kind, suppressed narrowly with the
reason inline rather than by widening any lint configuration.

34 custody tests pass.

Blind-spot scope: 21 -> 19 member sets declared in more than one place. Annotation scope
unchanged at 1, still the M184/IVA false positive, and the gate still cannot honestly
reach zero.

## Finding 65 — the same name, declared twice, in two places at once

Two vocabularies were not merely duplicated by member set: the SAME NAME was declared
twice.

`_InvoiceGrouping` appeared byte-identically in `_invoice_row_materialization.py` and
`invoice_bindings.py`, two modules of the same registry package where the second already
imports the first. The name was underscore-private, which is what stopped the importing
module using it, so it wrote the three tokens out again. It is now `InvoiceGrouping`,
public, defined once. This is the sixth instance of the campaign's dominant cause: a
definition that cannot be reached is a definition that gets rewritten.

`WizardPersistMode` appeared in `application/wizard/persistence.py` and again inside a
`TYPE_CHECKING` block in `entrypoints/cli/config/_manager_dispatch.py`. The CLI copy
carried a docstring asserting "This module is the canonical home -- the package facade
imports it rather than restating the literal pair." That claim was false at the moment it
was written: the application module already held the same declaration. The CLI now
imports it, and the claim is true of exactly one place.

Worth recording as a general point: a comment asserting canonicality is not canonicality.
Both of this campaign's instrument scans measure structure precisely because prose about
where a definition lives cannot be trusted to match where it actually lives.

28 invoice and 310 wizard tests pass. Five wizard failures are the known i18n migration
plus one xdist worker crash on a test that never references the changed symbol.

Blind-spot scope: 19 -> 17 member sets declared in more than one place.

## Finding 66 — a vocabulary with legal authority, and a decorator avoided

`["REBECA", "rebeca_eu_eea", "scheduled_canary_route"]` is the vessel-register set that
gates the maritime exemption, grounded in Ley 19/1994 Arts. 73.2, 73.3, 75.1 and 75.3.
It was written out at the fact field, at the eligibility test beside it, and again at
the application parser that produces it.

Now `VesselRegistry`, with `ELIGIBLE_VESSEL_REGISTRIES` built as `frozenset(VesselRegistry)`
rather than by relisting the three: a register added to the vocabulary cannot be left out
of the eligibility test, which is exactly what a hand-written copy invited. The
upper-case `REBECA` is reproduced as declared, because these are stored values and not
display text, and no member meaning was paraphrased beside the Orden citation.

`MaritimeWorkerFacts` carries `@dataclass(frozen=True, slots=True)`. The insertion was
anchored on the decorator line rather than the class line, and both were asserted
afterwards -- the enum is not a dataclass, the facts record still is. This is the same
hazard that previously produced an enum decorated as a dataclass, avoided by procedure
rather than by luck.

## Finding 67 — a cross-process wire contract, stated twice

The supervised key-derivation child accepts five operations. The supervisor builds the
token and the worker both dispatches on it and validates the payload's required fields
against it, so each of the two wrap tokens and two unwrap tokens appeared twice across
two modules.

`_kdf_operations.py` now holds `KdfOperation` with `UNWRAP_OPERATIONS` and
`WRAP_OPERATIONS`. The two sets are kept separate rather than derived from one another
with a direction flag, because they demand different required fields and a single set
would let one payload shape satisfy the other's check.

Two constraints made this target more than a rename. The worker is a subprocess entry
point whose import graph is asserted by `test_kdf_worker_import_graph.py`, on the
grounds that every wrap and unwrap spawns an interpreter and an eager import is paid on
the production login path. The new module imports only `enum` and `typing`, and the
forbidden list was read before the edit rather than after. And the tokens cross a
process boundary as JSON: a member serialises to its plain token and the worker's
comparison still holds after the round trip, verified directly rather than assumed.

Ruff's `S105 possible hardcoded password` fired on the two members whose names contain
`PASSWORD`. False positives on operation names, suppressed inline with the reason rather
than by widening any lint configuration.

21 kdf tests pass, including the import graph. One real-worker test timed out under
parallel load and passes alone. 55 maritime tests pass; the one failure is registry data
-- modelo 200 casillas referencing unknown export fields -- and touches neither change.

Blind-spot scope: 17 -> 14 member sets declared in more than one place.

## Finding 68 — a security allowlist held in two copies

`{"GET", "HEAD", "OPTIONS"}` is the set of methods a live AEAT read surface may use. It
existed as an inline membership test in `schema_verification.py` and again as a private
`_READ_ONLY_HTTP_METHODS` in `remote_state_guard.py`, where the read-only mandate is
enforced. Two copies of a security allowlist is one copy too many: a method admitted to
one and not the other produces a surface the schema rejects and the guard permits, or
the reverse.

Now one `READ_ONLY_HTTP_METHODS` in `schema_verification.py`, which
`remote_state_guard.py` already imports from. `SIMULATOR_HTTP_METHODS` is derived from
it by union with `POST` rather than relisted, so a method REMOVED from the read-only set
cannot silently survive in the simulator one.

Deliberately not an enum. HTTP methods are an external vocabulary this codebase does not
close, and declaring one would assert a completeness the registry has no authority over.
What is closed is these two sets, and naming them is the whole requirement.

## Finding 69 — a mirror maintained by hand, and its own comment said so

`withholding_bindings.py` declared six fact tokens twice on adjacent lines: once as a
`frozenset` for the runtime membership check and once as a `Literal` for the strict
selector field. The selector's own comment described the type as "mirroring the runtime
check the handler does against `_WITHHOLDING_FACTS`" -- an accurate description of two
hand-maintained lists that agreed only while someone maintained both.

Now one `_WithholdingFactKind` enum with the literal and the frozenset both derived from
it. One declaration, two views. The model is strict-frozen and built from registry TOML,
so the field takes the literal over the members -- checked before the edit.

## Finding 70 — a narrowing that stops a blocked run being read as a comparison

`ParityVerdict` carries four verdicts including `blocked`. The three-verdict subset was
written out three times: on the comparison model and twice in the Renta WEB oracle.

`blocked` belongs to a whole run, never to one field: a run can be blocked before any
field is compared, and a field that was never compared is `unverifiable`, not `blocked`.
`ParityFieldVerdict` now names the narrowing once, and keeping it narrow stops a blocked
run being recorded as a field-level outcome -- which would report a comparison that never
happened as one that did.

Registry annotation-scope inline declarations fell from 72 to 69 fields. Blind-spot
scope: 14 -> 11 member sets declared in more than one place. Package-wide annotation
scope remains 1, still the M184/IVA false positive.

## Finding 71 — a casilla has no title, and the type now says so

`ModeloLocalizationField` already held four localizable fields. The two-field subset a
CASILLA can carry was written out twice, and a further single-field narrowing twice more.

`CasillaLocalizationField` now names the pair. A casilla has no title and no official
name -- those belong to the modelo and its revision -- so keeping the narrowing narrow
stops a caller asking for a casilla key that can never resolve. The single-field default
is rooted as `Literal[ModeloLocalizationFieldKind.LABEL]` rather than widened.

## Finding 72 — two rules stated three times each, declared none

`export_value_policy.py` tested `{"0", "1"}` in a projector and again in a validator,
and both error messages already spelled out "exactly ASCII 0 or 1". The rule was stated
three times and declared nowhere. `SelectedUnselectedFlag` names it: the field is a
checkbox, not a quantity, and the tokens carry meaning the digits do not.

`_validate_semantic_role_axes.py` tested `{"1".."5"}` twice on adjacent lines, as the
two halves of one comparison. Declared once as `_RELATED_PARTY_AXIS_ORDINALS`, and
deliberately NOT an enum: these are positional indices into a record design, not names,
and the set is closed by that design rather than by any domain meaning. Widening the
design previously meant remembering to widen both halves of a single expression.

The distinction between these two is the point. One vocabulary earned an enum because
its tokens mean something; the other earned only a name because they do not. Promoting
both to enums would have dressed an index up as a domain concept.

Blind-spot scope: 11 -> 8 member sets declared in more than one place. Registry
annotation-scope inline declarations hold at 69; package-wide annotation scope remains 1,
the M184/IVA false positive.

## Finding 73 — the blind-spot population reaches its floor

Five more vocabularies landed: `CommandNodeKind` promoted from alias to enum with
`NON_LEAF_COMMAND_KINDS` naming the pair a reconciliation module tested twice;
`TreeRemovalErrorPolicy` for a deletion-safety choice passed as bare strings through two
signatures; `_LOCAL_EVIDENCE_SOURCE_KINDS` for two wallet source kinds tested twice, each
paired with a different second condition; `CLOSURE_SATISFYING_OUTCOMES`; and
`_FALSE_PROFILE_TOKENS`.

Two are worth stating for what they protect rather than what they tidy.

`CLOSURE_SATISFYING_OUTCOMES` includes `NOT_APPLICABLE` deliberately: a capability
declared out of scope is not a gap, and treating it as one refuses a filing over
evidence nothing required. The pair was tested twice in `filing_export_coverage`, once
directly and once as its own negation, so the two spellings could disagree about what
counts as satisfied while both looked correct.

`_FALSE_PROFILE_TOKENS` is the pair a profile row uses to mean NO. Two descendant flags
tested it independently with different defaults. A token added to one and not the other
would make one flag read a stored NO as a YES -- and for `convive_con_contribuyente`
that decides whether a descendant counts toward the minimo familiar at all.

BLIND-SPOT SCOPE IS NOW 2, AND BOTH ARE THE PATH-SEPARATOR SETS `["", ".", ".."]` and
`[".", ".."]`. Those are traversal guards, not a domain vocabulary: every site is a
containment check asking whether a path segment escapes its root, and naming them would
create a shared constant across five unrelated modules that have no reason to import one
another. They are classified as noise, and that classification is a judgement recorded
here rather than a silent omission.

So the blind-spot population went 28 -> 2 across this campaign, and the two that remain
are declared not-defects rather than unfixed. That is a different claim from zero, and
the difference is stated on purpose.

Annotation scope is unchanged at 1 package-wide -- still the M184/IVA false positive --
and 0 registry-schema-scoped, with 69 vocabularies at 69 fields. The gate still cannot
honestly reach zero, and widening it remains an operator decision.

## Finding 74 — a hand-maintained inventory, drifting, in committed code

`test_active_bucket_consumer_coverage.py` keeps two hand-written maps of which modules
resolve the active profile bucket. Both halves now fail: `profile_custody.py` resolves it
and is in neither map, and three modules -- `recipient_replay_guard.py`,
`custody_ports.py` and `workflow/persistence.py` -- are declared but no longer resolve it.

Two of those four were edited earlier in this campaign, so the possibility that the
campaign caused it had to be excluded rather than assumed. All four are unmodified in the
working tree, which puts the drift in committed code rather than in any pending change,
and the edits made to those two changed type annotations and imports only, never a
resolver call.

The finding worth recording is the shape, not the fix. This is a hand-maintained list of
modules whose only defence against reality is that someone updates it -- the same
mechanism this campaign exists to remove, applied to a different question. Its own error
message states the failure mode exactly: "an entry that outlives its module claims
coverage of code that is not there." Repairing it means deciding, per module, whether the
refusal behaviour is exercised, which is a coverage judgement and not a de-duplication
edit. Left for the operator.

479 + 348 + 45 tests pass across this tick's targets.

## Finding 75 — the registry schema has no inline vocabularies left

The de-duplication sweep reached its floor with 69 registry schema fields still declaring
a closed vocabulary. Those were never duplicates -- each was a single declaration -- so
the gate ignored them by design. They were, however, exactly what the campaign's opening
directive named: ad-hoc values declared at the field instead of derived from a canonical
enum.

That population is now zero inline. All 26 remaining fields reach a named type, and 43
were promoted to enums across this phase.

Measuring the split was what made the work honest. Of the 41 that remained mid-phase,
only 15 were spelled inline; 26 already reached a named alias and were therefore already
one definition. Converting those buys type identity and member documentation, not the
removal of an ad-hoc value, and saying so separates the two claims rather than reporting
one number as if it were homogeneous.

## Finding 76 — enum promotion silently degrades operator-facing messages

Thirteen registry validation messages interpolated a promoted field with `!r`. Before
promotion `{field!r}` printed `'declaracion_pdf'`; after, it printed
`<ExtractionSurface.DECLARACION_PDF: 'declaracion_pdf'>`.

These are messages an operator reads when the registry refuses a filing. The degradation
is invisible to the load check and to every import smoke test: the tree still loads, the
modules still import, and only a test asserting on message text -- or a human reading a
refusal -- can see it. One such test caught the first instance; the remaining twelve were
found by grepping `!r` against the promoted field names.

Some of them predated the batch that exposed the pattern. `data_type!r` had been
rendering an enum repr since `CasillaDataType` was promoted much earlier in this
campaign, which means degraded messages shipped unnoticed for many ticks.

The rule, now part of the procedure rather than a discovery: every promotion needs a
`!r` sweep over the promoted field name, INCLUDING fields promoted in earlier batches,
because nothing else in the toolchain reports it.

## Finding 77 — three more vocabularies kept apart

`LegalParameterDataType` shares six tokens with `CasillaDataType` and adds
`bracket_table` and `keyed_bracket_table`. A parameter can be a bracket table; a casilla
cannot. Proven not a subset rather than judged by eye.

The two `regularizacion_output` vocabularies in `bindings.py` both name a 303 and a 390
destination, and are disjoint: different casillas for a different adjustment. Proven
disjoint.

`ApplicationLinkSurface` is the third vocabulary in this codebase called a "surface",
after the extraction surfaces and the live verification surfaces. One names an artefact,
one an AEAT endpoint, one a part of the product. They share no token, and the name
collision is the only thing they have in common.
