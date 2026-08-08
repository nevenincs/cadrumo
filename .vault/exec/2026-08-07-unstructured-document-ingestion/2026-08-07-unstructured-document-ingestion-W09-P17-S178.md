---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:82f1816e6e0f43e4258bfd58043fa3cb50bd6811ea1122562e44672468ea4efd'
step_id: 'S178'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Surface a stated country code the vocabulary does not carry, since the resolver returns nothing for it and the provenance builder skips a null pair, so the operator sees an absent country and nothing else, indistinguishable from a record that stated none. That is precisely the failure the required alpha-3 column exists to close, reproduced one layer up where no refusal guards it. Emit the degradation through the notice channel already extended into the extract envelope, naming the unrecognised code, or attach an unanchored-equivalent envelope. Silence is the one outcome that should not be available

## Scope

- `src/cadrumo/application/ledger`

## Description

- Carry each party's verbatim stated country token on the draft, beside the
  resolved alpha-2 the bundled vocabulary produces.
- Ground the stated token as a copied structured value, so an unplaceable
  country earns a provenance envelope naming the element it was read from.
- Add the record-token status authority to the domain, admitting both ISO
  spellings, and route the country advisory through it.
- Carry the stated token onto the counterparty side and classify it at confirm,
  which is what makes the declared-relief guard's sparing reachable.
- Route the ISO user-assigned alpha-3 ranges to the unassigned kind.
- Project both stated fields onto the extract payload.
- Repoint the advisory fixtures at the field a document can actually populate.
- Add the end-to-end gate, in both spellings and both directions, with its probe
  selected from the vocabulary rather than pinned to one country.
- Scope the catalogue-gap exemption to the counterparty's own residency slot,
  which this row's wiring is what made reachable.
- Adopt the shared uncatalogued-specimen helper instead of a local candidate pool.

## Outcome

The structured reader's country lookup returned nothing for two different
events -- the record stated no country, and the record stated a token the
bundled vocabulary does not carry -- and both left the resolved alpha-2 field
empty. Downstream, empty meant no provenance envelope and no advisory, so an
unplaceable country was byte-identical to a document with no address block.

That was the visible half. The larger half was a correctness guard being
silently disabled. A guard withholds a declared export or intra-community
relief whose counterparty residency was not established, and it spares the case
where a well-formed code names a jurisdiction our own vocabulary merely lacks --
our gap, not the document's. Its own docstring calls that sparing the difference
between a guard and a trap. Production classified the counterparty's code off
the resolved draft field, which is empty for precisely the codes the exemption
exists for, so the sparing could never fire and every legitimate export naming
an uncatalogued country was refused. The guard's tests supplied the status
directly, so the logic was proven and the wiring was not.

The record's own token is now carried verbatim on the draft, on a field separate
from the resolved one. Putting a three-letter token into a field contracted as
alpha-2 would have traded a silent absence for a silent lie, and every consumer
keyed on the resolved form would have inherited it. The token earns an ordinary
structured envelope, the advisory reads it, and the confirm path classifies it
into the guard.

The classification lives in the domain rather than in the ledger layer, as one
function two consumers share. The printed-value status axis answers only about
alpha-2 and correctly declines to call an address line a bad country code; a
structured record's country element is schema-typed, so the record-token sibling
admits the alpha-3 spelling Facturae states. Its alpha-3 user-assigned ranges
are judged from a reserved-range set rather than from length, because the
catch-all otherwise reported a reserved code as a gap in our data -- the
opposite operator instruction, and one that ends in ungrounded registry data.

Visibility is not placement. The stated token does not reach the establishment
ladder, so an unplaceable country still resolves no territory. The side
attribute carrying it is named a token rather than a code precisely because the
ladder takes a same-named parameter wanting the resolved form: two same-shaped
attributes on one object, one safe in that slot and one not, is a swap that
type-checks.

Modified files:

- `src/cadrumo/domain/iva/_establishment.py`
- `src/cadrumo/domain/iva/__init__.py`
- `src/cadrumo/application/ledger/_evidence_draft.py`
- `src/cadrumo/application/ledger/_confirm_establishment.py`
- `src/cadrumo/application/ledger/_country_vocabulary_advisory.py`
- `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`
- `src/cadrumo/application/ledger/tests/test_structured_country_degradation.py` (new)
- `src/cadrumo/application/ledger/tests/test_country_vocabulary_narrowing.py`
- `src/cadrumo/application/ledger/tests/test_evidence_draft_provenance.py`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_country_cli.py`

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva src/cadrumo/adapters/inbound/einvoice -n0 -q -m unit
    1954 passed, 26 deselected, 16 warnings in 160.67s (0:02:40)

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_structured_country_degradation.py -n0 -q -m unit
    21 passed in 10.88s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -n0 -q -m integration
    163 passed in 48.71s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_country_cli.py -n0 -q -m integration
    5 passed in 8.61s

Four mutation probes, each loaded from outside the repository as a pytest plugin
so nothing under the source tree changed, each rebinding the name in the
CONSUMING module because a definition-site patch would print APPLIED and reach
nothing, and each judged on the gate going red rather than on the banner.

Neutering the status the confirm path's relief exemption is keyed on:

    [MUTATION APPLIED] confirm-path record_country_code_status neutered
    2 failed, 19 passed in 11.20s
    [MUTATION] neutered status called 5 times

Neutering the status the country advisory is keyed on:

    [MUTATION APPLIED] advisory-path record_country_code_status neutered
    4 failed, 17 passed in 13.03s
    [MUTATION] neutered advisory status called 14 times

Dropping the record's stated token on the way to the draft, which restores the
original defect end to end:

    [MUTATION APPLIED] _stated_country_code dropped
    9 failed, 12 passed in 10.90s
    [MUTATION] dropping reader called 38 times

Emptying the ISO alpha-3 user-assigned ranges, which restores the misrouting a
reserved code took before this change:

    [MUTATION APPLIED] _USER_ASSIGNED_ALPHA3 emptied (was 1092 codes)
    1 failed, 20 passed in 11.21s

Under every probe the stated-no-country cases stay green, which is what makes
each red an observable change in the distinction rather than a broadly broken
run.

### Round three: the exemption my wiring switched on

Making the catalogue-gap exemption reachable also made a latent over-spare live.
The exemption was keyed on the counterparty's country status but suppressed the
refusal for EVERY outstanding residency, so once a counterparty happened to be
uncatalogued a declared zero-rated export was honoured with NEITHER party
established -- the filer's own territory unknown and forgiven on the
counterparty's excuse. That is the under-declaration direction, and it was
unreachable until this row started delivering the stated token to the guard at
all, which makes it this row's to close rather than a finding to hand on.

The exemption now forgives one slot: the counterparty's own, named by
`_counterparty_residency_field(direction)` beside the identification sibling that
already resolved the same question for the other axis. A caller that cannot say
which party is the counterparty forgives nothing, which fails closed -- the safe
direction for a relief claim.

The local derived-probe machinery was deleted in favour of the shared
`country_vocabulary_specimens` helper, which another lane landed for the same
hostage problem while this row was in flight. Its candidates are drawn from
AEAT's own SII enumeration and from Facturae's, so a specimen is a code a real
submitted document can actually state -- better sourced than the hand-listed pool
it replaced, and one boundary for every suite instead of one per suite.

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva src/cadrumo/adapters/inbound/einvoice -n0 -q -m unit
    2 failed, 1964 passed, 26 deselected, 16 warnings in 202.42s (0:03:22)

Both failures were phantom: that run read the tree mid-sweep. Re-run immediately
afterwards against a settled tree, with every file of this surface byte-identical
to HEAD:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_ingestion_category_resolution.py src/cadrumo/application/ledger/tests/test_structured_country_degradation.py src/cadrumo/application/ledger/tests/test_grounding_anchor.py -n0 -q -m unit
    1 failed, 98 passed in 11.97s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_grounding_anchor.py -n0 -q -m unit
    43 passed in 1.22s

The one remaining failure belonged to another lane's uncommitted edit of the
anchor module and passes when that suite is run against a settled read.

A fifth mutation probe, restoring the unscoped exemption by returning early on
the status alone:

    [MUTATION APPLIED] relief exemption unscoped (forgives every residency slot)
    4 failed, 44 passed in 20.87s
    [MUTATION] unscoped exemption called 23 times

Four reds across two suites, which is what makes the scoping load-bearing rather
than decorative.

### Round four: the empty cell, and prose that had gone false

Re-review found the spelling-by-kind matrix carried three cases and one hole.
Uncatalogued alpha-2, uncatalogued alpha-3 and unassigned alpha-2 each had a
case; unassigned alpha-3 had none, and that is the cell this row's own
classifier change was about. It matters most on the relief path rather than the
advisory: a reserved alpha-3 misread as a catalogue gap is FORGIVEN, which moves
a declared zero-rated export claimed on a code with no referent towards being
honoured, from the spelling Facturae states. Both siblings are now gated, and
emptying the reserved alpha-3 set reds three cases for three distinct reasons
instead of only the anchor -- so the mutation reports coverage rather than
reporting its own probe.

The file's argument rested on Thailand, and one sentence asserted Thailand had
since been enrolled. That was written while it was momentarily true mid-session
and it is false at HEAD, where the code still reports uncatalogued. A gate whose
prose asserts a vocabulary state is the same hostage the derived specimens were
introduced to remove, committed in prose instead of in a constant. The argument
now rests on the property -- a country the vocabulary cannot place, whichever one
that is today -- while the ISO reserved ranges stay pinned and say why, since no
enrolment can turn one of those into a country.

One anchor docstring claimed more than the code does. The status axis asks the
same resolver the specimen was selected through, so the assertion is not an
independent second opinion; what it genuinely discriminates is that the specimen
is outside the reserved ranges and that the alpha-3 branch fires. It now says
that.

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva src/cadrumo/adapters/inbound/einvoice -n0 -q -m unit
    1976 passed, 26 deselected, 16 warnings in 218.43s (0:03:38)

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_structured_country_degradation.py -n0 -q -m unit
    25 passed in 13.33s

    [MUTATION APPLIED] _USER_ASSIGNED_ALPHA3 emptied (was 1092 codes)
    3 failed, 22 passed in 12.53s

Re-review also reported both relief cases failing whenever anything imports the
IVA domain at session start, with the filer residency unresolved. That was a
valid measurement against the tree it was taken from -- the round-two cases
asserted the relief STANDS, which needs the filer's territory to resolve. The
round-three rewrite removed the dependency for an unrelated reason: those cases
now assert the refusal and its narrowed reason, and the single case asserting the
claim stands supplies the filer's scope explicitly rather than reading a profile.
A no-op control importing the domain at session start and mutating nothing was
run twice against the current file and passed 25 both times, so the sensitivity
is structurally gone rather than accidentally quiet, and no marker is warranted.

## Notes

The gate was first written against Thailand, which was measured uncatalogued.
Another lane enrolled Thailand while this row was in flight and the country
vocabulary was observed changing size twice inside one session, at which point
eight cases failed for a reason unrelated to the behaviour under test. The probe
is now selected from the vocabulary at run time by the property it needs --
carried in neither spelling -- and an anchor class asserts the selection still
means what it says, so a future enrolment produces one named red pointing at the
candidate list rather than a suite that quietly stops exercising its subject.

Two findings were raised in review and both are closed here: the ISO alpha-3
user-assigned ranges misrouting to the catalogue-gap kind, and the counterparty
side attribute colliding by name with an establishment-ladder parameter that
wants the resolved form. A third review finding reported the domain classifier
as a duplicate of a peer's uncommitted work; it was this row's own in-flight
promotion, seen mid-session, and there is one definition.

The declared-relief over-spare was first recorded here as reported-not-changed,
on the reading that it predated this row. That was wrong in the way that matters:
the exemption could not fire at all before this row wired the stated token into
the guard, so the row is what made the over-spare live. It is fixed above rather
than handed on. Another lane reached the same conclusion independently and from
the other side -- its structured-record relief helper documents that the
exemption forgives only the counterparty's slot and supplies the filer's
territory for exactly that reason -- which is convergent confirmation rather than
a second opinion asked for.

One thing is still reported rather than changed: the establishment ladder's own
parameter is named for a stated code while receiving the resolved one, which is
confusing at its definition site as well as at the call site renamed here.

Three-letter tokens that are plainly not countries -- a currency code, a totals
marker -- classify as a catalogue gap. That is deliberate and documented: the
element is schema-typed as a country code, so a token that is not one is a
document defect worth naming rather than silence.

No new operator string was introduced: the two existing country notice codes and
their four locale catalogues carry the report unchanged.
