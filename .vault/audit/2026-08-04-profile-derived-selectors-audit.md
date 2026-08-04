---
tags:
  - '#audit'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:b10aebba0f79ef158e3d00f63921f2c8ea7d59966778bb06e492627f21354afc'
related:
  - "[[2026-08-04-profile-derived-selectors-adr]]"
  - "[[2026-08-04-profile-derived-selectors-plan]]"
  - "[[2026-08-04-minimo-descendientes-eligibility-adr]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
---

# `profile-derived-selectors` audit: `Closing audit: what the derived-selector campaign knowingly accepts and what it hands on`

## Scope

Both campaigns' plans read complete, and the plan's own Verification section requires one
behaviour to be either covered by a test or recorded here as knowingly accepted before
closure. Neither had happened. This document is that record, plus the handover the deferred
effective-dating campaign needs and does not have.

The findings below come from an adversarial review run by an auditor that had measured this
surface before the campaign started, briefed to be hostile to the coordinator's claims. The
coordinator drove both campaigns, wrote both plans, adjudicated the design rulings, executed
several Steps personally and wrote every exec record, so its own account is not independent
evidence.

## Findings

### A stale derived fact permanently locks a profile, and the plan under-described it

Knowingly accepted, with the severity restated because the plan's own description of this
hazard was too mild.

The write refusal judges the FULL MERGED fact set on every edit, not the incoming delta
(`_lifecycle.py:190,197`, batch at `:282-283`, ACTIVE promotion at `:363`, loop at
`_validation.py:161-162`). So a bucket carrying a fact at a derived path from before the
refusal existed has that fact re-judged on every subsequent edit to any other field, refusing
a write the operator never made.

Two things make it worse than "a stale fact refuses an unrelated edit", and neither was in the
plan:

It is not exempted in incomplete-setup mode. The issue code is not a member of the
completeness set (`_validation.py:107-109`), so relaxing completeness does not relax this.

There is no in-band remedy. The refusal is on the PATH and does not consult the value
(`_validation.py:173-183`), and the ADR states the intent plainly: it refuses every value
including a clear. So the operator cannot remove the offending fact either. Every
single-field edit, every batch edit and the ACTIVE promotion carry it back into the
validator. Such a bucket cannot be edited, cleared or promoted through the lifecycle API at
all.

The campaign met this hazard twice and treated the symptom without closing the general case.
Two commits exist solely because seeded derived facts began refusing: one stopped fixture
profiles seeding derived paths, one stopped the wizard projecting the guarderia sum. The
fixtures were changed; the mechanism was not addressed and not recorded.

Why it is nonetheless accepted rather than fixed now: the compatibility posture is
pre-release with no released data, so no taxpayer bucket can carry such a fact. Only a
developer bucket predating the refusal can, and the sanctioned remedy for pre-release data is
recreation rather than migration. Accepting it is consistent with the project's standing
posture.

What is NOT acceptable, and what this record exists to prevent, is the acceptance being
implicit. It is now explicit, with its real consequence named.

A remedy exists and is deliberately not taken here, because it is an ADR-level change rather
than a closing tidy: exempting a CLEAR from the refusal would let an operator remove a stale
fact without reopening the override channel, since a clear cannot inject a value. That
contradicts the ADR's stated rule as written, which was reasoned about new writes rather than
about removing a fact that predates the rule. It belongs in a decision record, not in this
audit.

### The deferred effective-dating campaign inherited scope that nobody wrote down

One sentence of handover exists anywhere in the vault: the two genuinely operator-input
year-suffixed fields belong to that campaign. Everything else it now owns is undocumented,
and this section is the handover.

It owns unifying four fact-index builders across two orderings. The binding resolver's own
index takes raw declaration order; only two of the four projections honour window order. The
ADR's rejection of effective-dating depends on this divergence, so it is now a named
prerequisite with no record naming it. The review also found a case the original research
missed: one function mixes BOTH orderings internally, layering an unwindowed lookup beside a
windowed one in the same mapping. Inert while nothing sets a window; a live defect the moment
one does, and the kind that surfaces after windows land rather than before.

It owns re-introducing an as-of channel from scratch. The one declared hook was retired by
this campaign, deliberately, so a second unread temporal axis would not sit beside the new
placeholder. That was the right call and it means the next campaign starts from zero rather
than from a dormant field.

It inherits a hardening precedent. The accepted-but-unimplemented snapshot ruling has now been
cited as load-bearing justification to reject a design, while remaining unimplemented. Each
citation makes it costlier to revisit, and it has never been tested against reality.

It inherits compute-always as a constraint. The injectors now overwrite whatever the index
holds. Consistent with the refusal today, but a constraint any future window design must
accept rather than discover.

One adjacent confusion to warn the next author about: the term as-of is live vocabulary in
this tree with a DIFFERENT referent, naming which registry revision the law selects rather
than which profile fact is effective. A grep will land on the law's axis.

### The promise of restraint was kept, and this is measured rather than asserted

The campaign claimed it would touch no window semantics. The window-ordering module is
byte-identical across the entire campaign window, and across all eight campaign commits the
count of changed lines touching the window fields is zero for every one. Nothing new depends
on window ordering. Both standing rulings are untouched.

The retired as-of channel is genuinely gone with no misleading residue: no field, no registry
key, no test, no stale docstring. A future author will find nothing suggesting one exists.

This matters because restraint is the class of claim that goes unverified — nothing fails
when it is broken.

### A checked Step had no execution record

One Step was marked complete without its record, breaching the closure discipline. It was the
Step resolved by ruling rather than by execution — the refusal copy follows the module's own
formatted-string convention rather than gaining a locale key — and the ruling was recorded in
a sibling Step's record instead of its own. Corrected during this audit.

### A Step was closed while part of its scope was undone

Found by the coordinator during this review rather than by an auditor, and recorded because
the pattern matters more than the instance. The entry-surface Step carried a fix for a stale
flag help string. The executor completed the rest and reported the help string as still
outstanding in its own report. The coordinator read that report, wrote the exec record, and
checked the Step anyway.

The consequence is operator-facing and sits directly downstream of this campaign's own
refusal: an operator refused at the write door is told to edit the source facts, reaches for
help, and cannot discover how. The Step is reopened.

The pattern this belongs to is the campaign's most reliable failure mode: the coordinator
closes on reports rather than on artefacts. Every correction in both campaigns came from
measurement contradicting something written down, including four of the coordinator's own
judgements.

### CORRECTION to Finding A: the remedy was taken, and the governance bar this audit set was walked past

A second adversarial pass measured this document against the code and found three of
Finding A's statements false at HEAD. Recorded here rather than by editing them away, because
the discrepancy is the finding.

Finding A states there is no in-band remedy, that the refusal does not consult the value, and
that such a bucket cannot be edited, cleared or promoted at all. All three were true when
written and are false now. The refusal was changed to exempt a clear, so a write of a value is
still refused while a clear is admitted, and a profile in that state is recoverable. The cited
line range no longer points at what the text describes.

The substantive half is governance, not staleness. This audit stated the remedy "belongs in a
decision record, not in this audit" -- it set its own bar and declared the change ADR-level.
The change then shipped as an ordinary fix commit, with no ruling added to the decision
record, and this document was not updated to say its stated residual had closed. The vault's
account of what the campaign accepts therefore OVERSTATED the risk being accepted. That is the
inverse of the usual failure and the same class: the record and the code disagreed, and the
record is what a later reader trusts.

The exemption itself is sound and is now ruled on in the decision record where this audit said
it belonged. Its reasoning is that a clear cannot inject a value, so it cannot reopen the
override channel, and the injectors compute always -- a stored value at a derived path is
already inert for calculation. Its tests filter on the issue code rather than on message
prose, pin both directions, and keep the surviving residual visible: a stale VALUED fact still
blocks an unrelated edit, and the recovery is to clear it first.

### Two coverage claims in the execution records are weaker than they read

Both confirmed by probe, both cheap, neither blocking.

A record states an advisory collector is "wired into the calculation diagnostics coordinator
and unit-tested", which reads as two forms of coverage and is one. Both minimo collectors are
wired, and no test drives that coordinator and observes either: deleting either wiring line
fails nothing. The record separately discloses that no end-to-end test proves the advisory
reaches an operator, so the operator surface was admitted; what was not admitted is that the
intermediate hop is unguarded too.

Separately, the ruling that corrected this campaign's most consequential defect -- proration
of a conjunta return by an unmarried couple -- has no test entering its branch. Reverting it
to the pre-correction behaviour passes the suite. Its AEAT oracle is already bundled and
already cited by the fixture that grounds only the other half of the same worked example. That
is opened as a Step against the sibling campaign and blocks its closure.

### What this audit's own accuracy record now shows

Three of this document's substantive claims about HEAD were wrong within hours of writing, and
one novel claim it made was right and had been missed by the reference pass that preceded it.
The useful reading is not that the audit was poor but that a closing document written by the
agent that drove the campaign decays as fast as the campaign moves, and is not self-checking.
It held only because a hostile reader measured it against the code.

### The one operator carve-out with no entry surface is recorded nowhere

Knowingly accepted, and recorded here because until now it existed only in a dispatch
message. The campaign kept two fields out of the derived namespace as genuine operator
input. One of them, `renta_family.cotizaciones_ss_madre_2024`, has no way for an operator to
enter it.

Four links, each measured against the tree:

No entry surface exists. The path appears nowhere under `entrypoints/` or
`application/wizard/` except one test that hand-seeds it.

It is formula-consumed. Casilla 0613 reads it through
`0181-renta-2024-incremento-guarderia-0613.toml:12`.

Its binding offers no escape. `0018-renta-2024-profile-cotizaciones-ss-madre.toml` declares
only a selector and `aggregation = { op = "copy" }`. There is no default, and
`absent_by_design` is not available to it: that flag is set at resolution time on a
carry-forward observation, not declared on a `profile` binding.

The derived-scoped advisory cannot reach it. That advisory fires only for a selected binding
whose selector matches a declared derived pattern, and this field is deliberately not
declared derived. Excluding it was correct, since declaring it derived would refuse the
operator's write to a fact only the operator can know. The consequence is that the one
diagnostic this campaign added is the one diagnostic that cannot cover it.

The hard failure itself is REASONED from those four links, not reproduced. A formula operand
with no resolved value and no default should fail the calculation, but nobody has driven a
live calculate to watch it raise. The corroboration is indirect and pointed:
`entrypoints/cli/tests/test_modelo_source_mesh_calculate.py:261` hand-seeds the path with
`Decimal("0")`, which is a test supplying a value so that calculate can complete.

The sharp part is this campaign's own doing and is better stated than left for a reader to
notice. Casilla 0613 is a three-operand `min`. This campaign gave two of those operands a
compute-always legal zero, the guarderia aggregate and the menores-3 count, recorded in
`P02-S13` as closing a latent defect nobody had set out to fix. The third operand sits one
line below them in the same expression and received neither a default nor a surface. So 0613
moved from three-ways-unresolvable to one-way-unresolvable: a real improvement, with the same
defect class surviving beside the fix, inside the same formula.

Why it is accepted rather than fixed here: the remedy is an entry surface, which is a feature
rather than a closing tidy, and the ADR already anticipated exactly this shape - a casilla
that hard-fails because a declared operator field has no entry surface, left as loud as it is
today and needing its own record together with the entry-surface work for the eligibility
inputs. That is one follow-up, not two. This section deliberately does not open a second home
for it. It makes the residual explicit and hands it to the entry-surface work being opened in
`2026-07-30-open-work-consolidation-plan`, where the sibling campaign's three descendiente
fields are already headed.

Two things a reader of that follow-up should carry. The remedy is not only an input box: this
field is one of the two the campaign classified as genuine operator input, so whatever surface
it gets must also be reachable from the refusal an operator meets when they try to write a
derived path. And the `--descendiente` flag help string is already stale against its own
parser, which accepts three keys the help does not list, so that follow-up should treat
discoverability as part of the work rather than assume a parser that accepts a key is a
surface that offers it.
## Recommendations

Earlier findings state their remedies inline, including the ones deliberately not taken and
why. This section records the handoffs that outlive the campaign.

Give `renta_family.cotizaciones_ss_madre_2024` an entry surface as part of the single
entry-surface follow-up in `2026-07-30-open-work-consolidation-plan`, alongside the sibling
campaign's three descendiente fields. Treat discoverability as part of that work: a parser
that accepts a key is not a surface that offers it, and the `--descendiente` help string is
already stale against its own parser.

Reproduce the casilla 0613 hard failure before designing the remedy. This record reasons it
from four measured links and says so; a live calculate against a profile lacking that fact
would turn the last reasoned step into a measured one and confirm the failure mode is a
refusal rather than a silent zero.

## Sources

- `src/cadrumo/application/user_profile/_lifecycle.py:190,197,282-283,363` - merged-set validation
- `src/cadrumo/application/user_profile/_validation.py:107-109,161-162,173-183,479-483` - the refusal and its blocking behaviour
- `src/cadrumo/application/user_profile/_projections.py:73,174,217,296-302` - the four builders and the mixed-ordering function
- `src/cadrumo/application/modelo/_profile_binding.py:122,143-150,220` - the unwindowed index and compute-always
- `src/cadrumo/domain/calculations/registry/_bindings.py:726-743` - the selector model after the as-of retirement
- `src/cadrumo/entrypoints/cli/_config/_descendiente.py` - the stale flag help string
- `.vault/plan/2026-08-04-profile-derived-selectors-plan.md` - the Verification criterion this record satisfies
