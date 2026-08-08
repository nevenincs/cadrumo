---
tags:
  - '#audit'
  - '#tui-surface-evaluation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b2fba4a54c1911d573a3cc50f303336b18b1bb7ebd5f7ec97d1fe827ac35c0e1'
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
flow, submit-gating visibility on an unanswered required page, styled-frame
legibility of focus states, and a deep walk of the real multi-page wizard
content. Absence of a finding on those is absence of evidence.

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
confidentiality defect, not a storage one. Fixed during this campaign by adding
a secret flag to the field model, wiring it to the input widget, and applying
it to the export passphrase as well as the newly-added passphrase-change
fields. Note the repository already gates exactly this property — a shipped
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

### manager-value-column-vanishes-at-the-floor | medium | a whole column disappears at eighty columns, and the geometry check cannot see it

At eighty columns the profile manager's tables drop the value column entirely,
leaving only status and field name — every row on the page, not just
divergences. The operator sees which facts exist and none of their values.

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
asynchronous-removal race — a scoped design task, not a one-line fix. Also
still unconfirmed: whether the focused table's cursor row is legible against
the unfocused state in a real styled frame, which was reasoned from framework
defaults rather than seen.

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

### hungarian-footer-overflows-at-eighty-columns | medium | a live wizard footer paints past the screen edge and cuts mid-word

Driven at eighty columns under Hungarian, the question screen's footer region
paints beyond the right edge and the binding text truncates mid-word. Spanish
and Catalan clip cleanly inside the footer box at the same width; the Hungarian
binding labels are long enough to push the widget past the edge entirely. The
footer is shared by every screen of the paged flow application, which includes
the modelo amend and modelo work wizards — both genuinely operator-facing — so
this is not confined to the retired setup surface. Not fixed: the two remedies
are shortening the Hungarian labels, which is a translation-quality judgement,
or changing how the footer degrades under width pressure, which is a design
decision.

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
