---
tags:
  - '#audit'
  - '#tui-surface-evaluation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:bce8a6f954bf60fa5c1061a5785b442362c8450e0a2223efd8cbea0a4760ec51'
related: []
---

# `tui-surface-evaluation` audit: `TUI surface evaluation: rendering, localization, navigation and capability gaps`

## Scope

Evaluation — not testing — of the seven full-screen terminal surfaces, along
three operator axes the operator named: rendering, localization consistency,
and navigation; plus three capability axes reported as missing: profile
credential management, sync controls, and the modelo 036 censo path.

Six reviewers drove the surfaces through a purpose-built evaluation harness
that renders each screen headlessly and reports, per frame, the painted cells,
the focus chain, the active key bindings, the flow engine's own state, and
geometry advisories. Findings were verified against source before acceptance;
where a reviewer's conclusion and the code disagreed, the code won.

Three limits on this audit, stated so the coverage is not overread. First, no
live AEAT session was exercised: every reading is against real local storage,
real encryption and the real application doors, but offline. Second, the
harness itself proved unfaithful in two of its six surface builders (see the
harness-fidelity finding), and although every finding initially blamed on that
turned out to be sound, the instrument was not trustworthy for part of the
window. Third, some axes were not reached: conditional-page gating on the paged
flow, submit-gating visibility on an unanswered required page, a deep walk of
the real multi-page wizard content, and vertical behaviour at heights below
twenty-four rows. Absence of a finding on those is absence of evidence.

The shared question and review screens were initially driven through the
retired paged surface, which made every finding about them an inference. That
inference has since been discharged: a harness surface for the live
modelo-work wizard was built, composing the flow through the same
`select_flow_frontend` sequence the wizard entrypoint uses over a real work
unit, and driven at the floor width under both appearances. The widget tree is
identical and the geometry results reproduce, so the findings do transfer. They
are now measured rather than inferred.

Every surface was driven at eighty by twenty-four, one hundred by thirty, one
hundred and twenty by forty and two hundred by fifty, under both appearances.
That sweep was read off the harness geometry band, which checks widget
positions — so it is evidence about overflow and unreachability, and not about
legibility. A defect found later on the same surfaces at the same widths, where
a table silently drops a column, is invisible to that band and was found by
reading the painted text instead. Treat the clean geometry result as bounded
accordingly.

## Findings

### tui-no-notice-channel | critical | the full-screen surfaces cannot render an operator notice at all

The CLI contract makes the typed notice the sole channel for operator-facing
non-blocking diagnostics — warnings, advisories, next-step hints. There are
zero notice references across every module of the terminal adapter package,
not merely on the status page. Every advisory the application layer produces
therefore reaches a command-line operator and is structurally invisible to a
full-screen one. The concrete instance already in the tree: the overview layer
raises an informational advisory telling an operator to run the filing-history
sweep when the bucket holds no official-source observations, and that advisory
has nowhere to land on any screen. This is not a missing panel on one page; it
is an entire operator surface with no diagnostic channel. Remediation: a
notices band on the shared surface spine, rendered from the same typed notice
objects the envelope carries, so a diagnostic cannot exist for one frontend and
not the other.

### form-fields-painted-secrets-in-clear | critical | a profile-export passphrase was rendered on screen as it was typed

The generic full-screen form substrate had no field-masking capability of any
kind: before this campaign there was not one reference to a password or secret
attribute anywhere in `adapters/inbound/tui/_form_screen.py`, and its edit
dialog rendered every collected value in clear. The profile-export bundle
passphrase has been collected through that dialog since 2026-07-25, so for
roughly two weeks an operator exporting a profile typed the passphrase
protecting that bundle and watched it painted back in clear on the terminal —
exposed to anyone overlooking the screen, to a screen capture, and to a
recorded session. Nothing stored it in clear; this is a display-surface
confidentiality defect, not a storage one. The first fix — a secret flag on the field model, wired to the input widget and
applied to the export passphrase — was necessary and NOT sufficient, and the
gap it left is the more interesting half. A property-based gate written
afterwards, driving every action that opens a form and checking every masked
field it finds, caught two further live leaks on the same surface:

- the row-selected handler REBUILT the field for the edit dialog and dropped
  the secret flag, so masking was lost while the operator typed — upstream of,
  and worse than, the original symptom
- the summary table wrote the raw value into its value column regardless of the
  flag, so a committed secret sat in clear on the form itself with no
  navigation required. **This is where the export passphrase actually lived.**

So the original account of this defect was incomplete: masking the input alone
left the secret painted one row below it. Both are now fixed and the gate is a
property over every secret-bearing field reachable from any manager action,
naming no dialog. Worth recording how the gate was proven: an early version
asserted the secret's absence from an exported screenshot and gave a false
negative, because an eighteen-character sentinel came back truncated to five in
the export — a width accident reading as a pass. Reading the stored cell
directly fixed it. An absence assertion that can pass because the value was
merely clipped is not an absence assertion.

Note the repository already gates exactly this property — a shipped
appearance test asserts a typed secret never appears in the rendered cells —
but only for the registration screen. The form substrate was outside that
gate's reach, which is the same gate-hole shape as the profile manager sitting
outside the appearance gates. Remediation beyond the fix: extend the
never-paint-a-secret gate to every surface that can collect one, rather than
naming surfaces individually.

### restart-wiped-the-flow-unconfirmed | high | one mis-struck chord destroyed every answer, and a test called it the contract

`ctrl+n` on the question and review screens called the engine's restart
transition directly, with no confirmation of any kind: every committed answer
was wiped and the cursor returned to the first page, with no undo. The engine's
own docstring states that restart wipes the whole state and that "the
confirmation is a frontend responsibility" — a responsibility the frontend
never discharged. On a long flow this is dozens of pages of operator input
destroyed by a single chord adjacent to other bound chords. The surface is
live: the paged flow application is reached by the modelo amend and modelo work
wizards, so this was reachable by a real operator mid-wizard.

The aggravating detail is the test. `test_ctrl_n_restarts_the_flow_from_the_first_page`
asserted precisely this behaviour, so the defect was encoded as the contract
and every run confirmed it — the failure mode the quality rules name as worse
than no test at all. Fixed during this campaign: a modal confirmation opening
focused on Cancel, escape and cancel declining, only an explicit accept
carrying out the wipe, with the old test rewritten to assert state survives
while the dialog is open and a cancel-preserves-state test added alongside.
Single-page reset was deliberately left unguarded — its blast radius is one
answer the operator can re-enter in seconds, and guarding it would train the
reflex that makes the real confirmation worthless.

### censo-divergences-were-illegible | high | the reconciliation worked and the screen hid the result

A cotejo persists each disagreement between AEAT and the operator's own record
as typed divergence rows. Both surfaces rendered them as raw internals. On the
manager, each divergence produced three rows whose labels ended in the
untranslated internal leaf names — `axis`, `artefact_value`, `source` — leaking
English field names onto a Spanish screen, and the row meant to say WHICH field
disagrees printed the raw dotted schema path instead, truncated to three
characters at a hundred columns. The read-only status page was worse: label and
value were both raw identifiers, with no operator-facing text on the row at
all, a behaviour its own docstring documented.

So the mechanism designed to tell an operator that AEAT disagrees with them
completed successfully and then presented the result in a form only someone
holding the internal data model could read. Confirmed by seeding two real
divergences through the production apply door and driving both surfaces, not by
reasoning about the code. Fixed by resolving the disputed field's real label
and translating the three leaf suffixes, in all four catalogues; both surfaces
consume the same promoted facade symbol, so they cannot drift apart on what a
divergence axis is called. Deliberately scoped to this one namespace rather
than generalised into an indexed-leaf translator, because sibling namespaces
are repeatable sections with their own declared labels — a different shape.

### manager-value-column-is-off-screen-at-the-floor | high | the value column sits past the right edge with no cue that it exists

At eighty columns the profile manager's tables fail to show fact values, and
two reviewers observed it differently on the same surface at the same width.
One, driving a profile of short and empty values, reported the value column
absent entirely — status and field name only, every row on the page. The other,
after writing a roughly one-hundred-and-sixty character note, saw the value
column present but the content hard-cropped mid-word at the panel's inner edge,
with no ellipsis, no overflow marker, and nothing signalling that the stored
value is longer than what is painted. The stored value is intact in both cases;
this is presentation only.

**Resolved: the column is off-screen, not absent and not collapsed.** Neither
first reading was the mechanism. The decisive evidence is behavioural — pressing
the table's page-right binding brings the value column into view while status
and most of the field name scroll off to the left, which a missing or
zero-width column could not do. The cause is content-driven overflow: the table
sizes every column to its own widest cell and sums those widths with no clamp
against the container, and the field-name column on a section with long labels
is wide enough on its own to push the value column past the right edge while
the viewport sits at its default leftmost scroll position. Nothing computes a
width that collapses, and no responsive rule drops the column by design.

That makes it worse than the truncation it was first taken for, and a
navigability defect rather than a cosmetic one: an operator on a long-label
section at eighty columns sees a table that appears to have no value column at
all, with no rendered horizontal scroll affordance cueing them that there is
more to the right. Truncation at least shows that something is there.

The remedy is therefore a design choice among three, and needs a decision
rather than a patch: guarantee the value column space with a fixed or
percentage width split, wrap the field-name label instead of letting it grow
its column, or at minimum surface a visible horizontal-scroll affordance. The
first changes the whole table's proportions, which is why it was left rather
than improvised.

The operator consequence is the same either way and is what matters: proofing a
long razón social, address or note on a narrow terminal, there is no on-screen
signal that what is displayed is not what is stored.

The instrument note matters as much as the defect. The harness geometry band
reports `ok` for this surface at that width, and correctly so: nothing is
painted past an edge, no scroll host overflows, the screen does not scroll. A
table that silently drops a column is a rendering defect the band is
structurally blind to, because it checks positions rather than content. The
rendering sweep that cleared every surface at four widths under both
appearances was reading that band. Its clean result is therefore evidence about
overflow and not about legibility, and this finding is the proof that the two
are different questions.

### manager-tables-are-anonymous-tab-stops | medium | twenty-five focus stops nothing can tell apart

The profile manager renders one table per profile schema section — twenty-five
of them — and each is a genuine, operable tab stop with a row cursor and an
edit action, so the cycle is not broken. What is missing is identity: no stop
could be named. Nothing — not the harness, not an accessibility tool, not a
screen reader — could report which of the twenty-five held focus without
cross-referencing scroll position. This is an observability and accessibility
gap rather than a navigation break. Initial focus lands on the first real
action button, the cycle closes, and auto-scroll tracks focus into view through
all twenty-five, so what is wrong is naming, not movement.

**Left unfixed, and the reason is the finding's real content.** Giving each
table a stable section-derived identifier was tried and reverted. Textual
mounts these widgets dynamically, and a same-id remount before the framework
finishes the previous widget's asynchronous removal is a registry collision —
a constraint already documented in a sibling screen, where dynamic widgets are
mounted anonymously on purpose for exactly this reason. The manager re-renders
on any shape-changing write, so a language switch or an action press crashed on
the second render. Notably the unit lane did not catch it; the
language-switch integration test did, which is worth remembering when a change
looks safe because the fast tests are green.

So the honest statement is that the anonymity is load-bearing under the current
destroy-and-remount rendering strategy, and naming the stops requires either
reusing table instances across renders or an identity scheme that survives the
asynchronous-removal race — a scoped design task, not a one-line fix.

**Focus legibility was subsequently settled, and it does not compound.** The
coordinator speculated that unnameable stops plus an invisible focus state
would together make the surface unnavigable. Measured against real styled
frames rather than plain-text captures, that is refuted: the focused row paints
the theme's own primary accent in both appearances — warm orange on near-black
in dark, rust on cream in light — with no low-contrast state in either. An
operator can always SEE which table holds focus; what they cannot get is a
machine-readable name for it. The accessibility half of the finding stands, the
compounding hypothesis does not.

### hungarian-carried-an-english-stem | medium | "census" appeared inside Hungarian compounds on a live surface

Three manager action strings glued the raw English word "census" into Hungarian
compounds — rendering as "Kitöltés az AEAT **census**adataiból" — a
mixed-language screen on a live operator surface. Fixed using the Hungarian
equivalent this catalogue already uses around twenty times for the same
concept, so the correction follows established usage rather than inventing
vocabulary. The other five action labels were clean in Hungarian and all six
clean in Catalan.

### credential-recovery-has-no-terminal-surface | medium | a TUI-only operator cannot manage recovery codes at all

Recovery code creation, rotation and verification, and the forgotten-passphrase
recovery path, all exist in the application layer with working command-line
verbs, and none has any full-screen surface. The asymmetry is total in one
direction: a headless operator can do everything, and an operator working in
the terminal application can do nothing about a lost or rotated recovery code
without dropping to a shell. Passphrase change previously shared this gap and
was closed during this campaign. Recovery deliberately was not, and the reason
is sound: enrolment requires displaying a twenty-four word mnemonic once and
demanding a full retype with echo suppressed, and the existing form primitive
has no show-once semantics and no way to stop a displayed value round-tripping
back into a collected field. Building it quickly would have risked the one
thing that door exists to protect. Named under Recommendations as an ADR
question, because the governing custody decision requires a one-shot display on
"the terminal device" and no decision rules on whether a rendered modal
satisfies that.

### m036-sequence-unenforced | high | a baja before an alta is accepted and persisted

`application/modelo/_m036_lifecycle.py:283` records a declaration with no
sequence check whatsoever: no read of prior declarations, no ordering guard.
Two dedicated error classes exist for exactly this — `Modelo036PriorAltaRequiredError`
and `Modelo036TerminalStateError` at `domain/modelos/_errors.py:49,53`, both
registered in the error registry — and neither is constructed anywhere outside
its own definition. Recording a modificación or a baja with no prior alta, or
any declaration after a baja, is accepted; the malformed sequence is emitted as
a censo declaration event and persisted, and the module's own docstring states
that this feeds downstream profile-state re-derivation. A behaviour-phrased
semantic sweep for an ordering guard under any other name returned nothing.
Remediation: enforce the sequence at the recording door using the two error
classes already defined for it.

### censo-certificate-drops-secondary-activities | high | only the first activity on the certificate survives

`domain/censo/_certificado.py:79-111` projects the certificate onto profile
facts by taking `certificado.actividades[0]` — a single index, no loop. A
taxpayer with a second local or a second IAE epígrafe has that data on the
AEAT certificate and silently loses everything past the first entry at
projection. Nothing warns; the cotejo reports success. This is silent
truncation of authoritative tax data, which is the worst available outcome:
the operator has no signal that the record is now narrower than the evidence.
Remediation: either iterate the activities onto indexed fact paths, or refuse
explicitly when the certificate carries more than the schema can represent.
Silence is the one option that must not stand.

### censo-regimen-never-reconciled | high | AEAT states the régimen, the operator self-declares it, and the two never meet

The certificate's `situacion_tributaria` and `obligaciones_periodicas` axes are
display-only and become no profile fact. Meanwhile a régimen axis does exist on
the profile schema — the Ley 49/2002 special-regime option and renunciation
fields, typed, carrying legal references and anchored to modelo 036 casillas
651 through 654 — and it is populated by the setup wizard from the operator's
own answers and consumed by deadline derivation at `domain/deadlines/_profiles.py:118-142`.
So the authoritative AEAT statement of the régimen is shown and discarded,
while a hand-declared value drives the filing calendar. The cotejo mechanism
exists precisely to reconcile profile facts against AEAT, and on this axis it
reads the correct answer and declines to adopt it. A stale or mistaken
self-declaration yields a wrong deadline schedule with no detection.
Remediation is an architecture decision, named under Recommendations.

### staleness-push-model-dead | medium | a whole staleness design is declared for two axes and wired for neither

`WorkUnit.censo_stamped_stale_at` / `censo_stale_reason` and their ledger
counterparts, the two dependent-stamped-stale bucket events, and
`CensoStaleRefusedError` form a stamp-on-write staleness design that has no
writer, no emitter and no raiser anywhere in production. Two live mechanisms
already cover the ground by a different shape, both pull/compare-at-read: the
verify-time ledger drift gate pins the ledger state at calculate and compares
live at verify, returning a blocking finding; and the approval basis
fingerprints the full canonical profile projection and compares it on review
refresh. Building the declared push model would therefore introduce a third
shape for one concept. Note the refusal error's docstring claims it applies to
calculate, verify, file, build draft, approve draft and export draft — wider
than anything that exists, so the registry currently advertises a guarantee the
tree does not honour. Remediation: retire the push-model fields, events and
error on both axes.

### censo-preapproval-window-unguarded | medium | a censo change between calculate and verify is invisible

Of the two live staleness mechanisms, the drift gate covers the
calculate-to-verify window for ledger rows only, and the approval basis
activates only after a draft is approved. A work unit that is calculated, then
has its address changed by an applied censo pull, then verified or exported
without ever being approved, passes with no check: there is no profile-facts
equivalent of the pinned ledger snapshot. The exposure is bounded by the
preceding finding — only the address, postcode, cadastral reference and primary
activity reach the record at all — but within that set it is real.

### setup-paged-flow-retired-with-orphaned-wiring | medium | the paged setup wizard is unreachable, and its locale-rebuild machinery is orphaned

Every interactive invocation on a capable host is routed to the profile
manager; the paged flow is deliberately not an interactive surface, and the
routing function's own docstring names parallel authority as the reason. The
projected setup definition survives in production only for the scripted
headless path, which renders no screen. Consequently `run_flow_tui` has zero
production callers, and with it the locale-rebuild hook it exists to wire —
so the output-language page's live re-render is dead code. This is a
dead-code finding, not an operator-facing defect, but it is load-bearing for
anyone evaluating "the setup wizard": the real interactive setup experience is
the registration screen followed by the profile manager.

### hungarian-footer-overflows-at-eighty-columns | medium | a live wizard footer clips its last key hint mid-word, legibility not reachability

Driven at eighty columns under Hungarian, the question screen's footer region
paints beyond the right edge and the binding text truncates mid-word. Spanish
and Catalan clip cleanly inside the footer box at the same width; the Hungarian
binding labels are long enough to push the widget past the edge entirely. The
footer is shared by every screen of the paged flow application, which includes
the modelo amend and modelo work wizards — both genuinely operator-facing — so
this is not confined to the retired setup surface.

Severity, split deliberately: the control is **clipped, not unreachable**. The
save-and-exit chord still fires regardless of what the footer paints, because
the footer renders key hints and does not gate the binding on its own visible
width. So an operator loses the ability to READ that the affordance exists,
not the affordance. That is a real defect on a live surface and a materially
lesser one than a control that cannot be reached. Not fixed: the remedies are
shortening the Hungarian labels, a translation-quality judgement, or changing
how the footer degrades under width pressure, a design decision. A semantic
sweep found no existing in-repo pattern for narrow-width footer degradation to
follow.

### sync-controls-absent-everywhere | medium | scope, dry-run, divergence, progress and cancellation exist for neither sync surface

Neither the Google Sheets calculation sync nor the filing-history sweep offers
scope selection, a dry-run preview, divergence reporting, progress or
cancellation — and the absence is at the command-line layer too, not only in
the terminal surfaces. Separately, no last-sync provenance mechanism exists
anywhere in the tree: nothing records when a synchronisation last ran or what
it captured. A reusable shape does exist in-tree and should be cited rather
than reinvented: the censo cotejo is preview-by-default, commits behind an
explicit apply flag, persists non-adopted values as typed divergence rows, and
raises a standing warning while any divergence remains open.

### google-sheets-sync-has-no-terminal-surface | medium | a real capability reachable only from the command line

The Sheets calculation export, verify, pull and compute capability has no
presence on any full-screen surface. Class: the capability exists and the
surface is missing. Left open rather than wired, as the composition is
materially larger than the adjacent filing-history action that was closed.

### manager-outside-the-visual-gates | medium | the busiest surface is not enrolled in the appearance gates

The shipped visual-verification gates enrol the registration, form, status and
question surfaces. The profile manager — the one interactive surface for
managing a profile, and the densest of them — is absent, so nothing pins its
geometry, focus behaviour or appearance under either theme. This is the
durable finding behind the retracted item below: a surface outside the gates
is where an appearance defect can live unnoticed.

### harness-fidelity | high | two of six harness surface builders were stand-ins, and one produced a fabricated finding

The evaluation harness asserted in its own docstring that every surface is
composed the way production composes it. Two builders broke that promise. The
profile manager was constructed with no actions at all, so the screen rendered
with zero buttons; the login screen ordered its rows by opaque bucket
identifier rather than the operator's casefolded label and preselected no row,
so it opened with focus on the picker rather than the passphrase field. Both
are the same shape: a constructor argument that defaults to empty, producing a
screen that renders cleanly while showing less than the real one. Both are
fixed by calling the production composition rather than reproducing its
arguments. The generalisable lesson: an evaluation instrument's fidelity to
production is itself a claim requiring proof, and a stand-in that renders
cleanly is indistinguishable from the real surface until something is compared
against the production entry point.

A third instrument defect surfaced late and is worth recording with the other
two: the harness gesture that sets a widget value directly resolved its
selector against the application rather than the top screen, and the framework
does not descend into a pushed modal that way. So every such gesture aimed at
any dialog — the field editor, the language chooser, the confirmation prompt
added during this campaign — failed for every reviewer, silently making modal
content undrivable. Fixed. A related rough edge was found and deliberately left:
a gesture is written to the session journal before it is replayed, so one
failing gesture persists and breaks every subsequent command until it is undone.

A correction belongs here, because this finding was initially over-credited.
The coordinator attributed a fabricated geometry finding and a false
four-locale clearance to these stand-ins. Both attributions were wrong: the
harness had already been repaired when both readings were taken, and the two
reviewers were right on the facts while the coordinator was wrong on the
timeline. The stand-ins were real and worth fixing — the manager did render
with no actions for a period, and the login screen did order rows by an opaque
identifier and preselect nothing — but they did not corrupt the findings blamed
on them. Damage attributed to a defect should be measured, not inferred from
the defect's existence.

### manager-action-row-overflow | high | six action buttons were unreachable at every terminal width, and the coordinator retracted the finding while it was being fixed

The action panel was a plain horizontal container, which in this framework
neither wraps nor scrolls. With real AEAT-length labels the row of six buttons
overflowed the right edge **unconditionally — at eighty columns, at one
hundred, at one hundred and twenty, and still at two hundred**, where the
export button sat at columns 180 to 201. The overflowing buttons remained in
the tab order, so an operator could focus a control that could never be
scrolled into view: the host was not scrollable and the page's own scroll host
is vertical-only. This is worse than the original report, which observed it at
one width; it was never a width-dependent clip but a permanent unreachability.
It shipped with zero coverage, because the manager is not enrolled in the
appearance gates. Fixed by making the panel vertical — one full-width button
per row — which follows the house rule the gate module's own docstring states,
that these surfaces scroll vertically only; a horizontal scroll host would have
contradicted it. A regression test using real-length labels at the eighty-column
floor now pins it.

**The coordinator retracted this finding as fabricated while it was being
fixed.** The reasoning was that the harness had built the manager with no
actions when the reading was taken. That was wrong twice over. The harness
wired the real actions at 10:29:41 and the reading is timestamped 10:30:58, so
the buttons were on screen. And the repair at 10:51:43 was not unrelated peer
work, as a first correction assumed — it was this campaign's own rendering
reviewer, acting on the very lead the coordinator had forwarded, who reproduced
the defect at four widths, fixed it, and wrote the gate. So the coordinator
instructed a reviewer to strike a finding that the same reviewer had already
confirmed and closed.

Two lessons, the second being the one worth keeping. First, a finding that fails
to reproduce in a tree with many concurrent writers has two explanations — it
was never real, or it was fixed underneath you — and the reviewer's timestamp
checked against the commit log separates them cheaply. Reaching for the first
explanation is how a valid finding gets destroyed. Second, the coordinator
misattributed the harness repair to a later commit than the one that carried
it, built a confident timeline on that single unverified premise, accused a
reviewer of fabricating evidence, instructed a second reviewer to strike the
finding, and then cited the supposed fabrication as supporting evidence for a
separate finding. **A verification that produces an accusation deserves at
least the scrutiny of the claim it examines**; this one received less, because
it confirmed a story already forming.

Still open: whether the now-vertical action column has any width problem at the
eighty-column floor under Hungarian. A reviewer re-checked and found it clean —
the longest Hungarian label fits comfortably in a full-width row, and the
structurally different case is the question screen's footer, which packs its
bindings horizontally with no wrap.

### notice-band-hid-every-panel-beneath-it | critical | a fix landed by this campaign made four status panels vanish

The notices band added during this campaign shipped with two defects that
together removed most of the status page. Its stylesheet constant was defined,
exported, and consumed by nothing — the status surface imported the band and
not its styles — so no notice styling applied at all, including the severity
colour whose stated purpose is carrying meaning alongside the glyph. And the
band never set its own height, inheriting the framework container default of
one fraction, so it claimed the entire scroll column. With any notice present,
the profile, profiles, authentication and recovery panels did not paint: not
below the fold, not reachable by scrolling, absent, at every size tested up to
one hundred by fifty.

**Why nothing caught it is the finding.** Three independent layers of coverage
existed and none could see it. The band's own wiring tests asserted that a
notice paints, and it did. The appearance gates construct the status surface
with no notices at all. The evaluation harness drove status with a profile but
no session, so the producer returned nothing and the band never mounted. Every
layer built the surface in its emptiest reachable state, and a widget that
eliminates its siblings passes all of them. A regression sweep run in the same
window reported no campaign-caused failures, correctly within what it measured
and blind for exactly this reason.

Fixed. The durable remedy is not the height rule but the gate shape: a
surface's declared regions must all remain present when any one of them is
populated, and conditional regions must be exercised in both states.

### guard-classifier-matches-a-comment | medium | a gate reclassified real code because a comment contained a token

The classifier deciding whether a refusal is operator-guarded matches a literal
substring anywhere in the enclosing function body. A comment containing that
token flipped four unrelated raises into unguarded, moving a refusal in and out
of a gate's reviewed set across two runs of the same test with no code change.
The gate governs which refusals can reach an operator with no next step, so the
failure mode runs both ways: a false positive hides a genuinely suggestionless
refusal, and a false negative manufactures one — which is what happened. A
source-text match over a body that legitimately contains prose cannot
distinguish code from commentary; the scanner already walks the syntax tree and
the classification belongs there.

## Recommendations

**Wire a notices band into the shared full-screen spine**, rendered from the
same typed notice objects the envelope carries, so no diagnostic can exist for
one frontend and not the other. Ties to the no-notice-channel finding. This is
the highest-value item here: it is a channel, so it unblocks every advisory
already written and every one written later.

**Enforce the modelo 036 declaration sequence** at the recording door, raising
the two error classes already defined and registered for it. Ties to the
sequence-unenforced finding. No new vocabulary is required; the refusals exist.

**Stop the certificate projection losing secondary activities** — iterate onto
indexed fact paths, or refuse explicitly when the certificate carries more than
the schema represents. Ties to the dropped-activities finding. Silent
truncation is the only outcome that must not survive.

**Retire the push-model staleness fields, events and refusal error on both the
censo and ledger axes**, and correct the refusal error's docstring claim before
removal so no reader inherits a false scope. Ties to the dead push-model
finding. Two live pull-model mechanisms already hold this ground; a third shape
would be parallel authority.

**A follow-on ADR must decide whether the censo cotejo adopts the régimen and
obligations axes onto the existing taxpayer-type profile fields**, and what
happens when AEAT's statement disagrees with the operator's wizard answer on a
fact that drives the deadline schedule. It must also decide whether a
profile-facts equivalent of the calculate-time ledger pin is warranted for the
pre-approval window, or whether the approval-basis comparison is sufficient
coverage. Ties to the régimen and pre-approval-window findings. Neither
question may be settled by implementation; both change what the application
asserts about a taxpayer's legal position.

**A follow-on ADR must decide the shape of sync controls** — scope, dry-run,
divergence reporting, progress and cancellation — across both sync surfaces,
and must rule on whether dry-run carries the same meaning for an idempotent
spreadsheet overwrite as for an append-only filing capture. It should adopt the
censo cotejo shape as its precedent rather than starting from nothing, and must
also decide whether last-sync provenance is recorded, since nothing records it
today. Ties to the sync-controls finding.

**Extend the never-paint-a-secret appearance gate to every surface that can
collect a secret**, expressed as a property over collecting surfaces rather
than a list naming the registration screen. Ties to the painted-secrets
finding: the defect survived two weeks because the gate existed and its reach
was enumerated by hand.

**A follow-on ADR must decide whether secret-mnemonic recovery enrolment
belongs on a full-screen surface at all.** The governing custody decision
requires the candidate words to be displayed once on the terminal device and
fully retyped with echo suppressed; no decision rules on whether a rendered
modal satisfies "the terminal device", nor on what primitive can hold a
show-once value that must never round-trip back into a collected field. Ties to
the recovery finding. Until that is settled, recovery stays command-line only
and the terminal application should say so rather than appear to omit it.

**Audit every destructive transition on every surface for a confirmation**, not
only the one found. Restart was unguarded and its test asserted the unguarded
behaviour; the same pair of failures can exist wherever a chord reaches an
irreversible engine transition. Ties to the restart finding.

**Enrol the profile manager in the visual-verification gates.** Ties to the
outside-the-gates finding, and it is the only recommendation here that would
have caught the retracted item honestly rather than by accident.

**Treat an evaluation instrument's fidelity as a claim requiring proof.** Where
a harness composes a production surface, it should call the production
composition rather than reproducing its arguments, and any surface that is
legitimately synthetic should say so in its rendered output, not only in its
source. Ties to the harness-fidelity finding.
