---
tags:
  - '#audit'
  - '#registry-enum-canonicalization'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:05518b27df8fea46f87ed959525055ed76903d12c4f19a82b06ffbf0f4479efb'
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
