---
tags:
  - '#audit'
  - '#tui-surface-evaluation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:26cb9658081c85940cefc27aee7edf0cfd492b35ff2239b1b2f2cdcd0adbee8c'
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

Two limits on this audit, stated so the coverage is not overread. First, no
live AEAT session was exercised: every reading is against real local storage,
real encryption and the real application doors, but offline. Second, the
harness itself proved unfaithful in two of its six surface builders midway
through (see the harness-fidelity finding), so findings read off those two
surfaces before their repair were discarded rather than carried.

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
arguments. The cost was not hypothetical — one reviewer reported a geometry
defect naming three buttons that were not on the screen, the coordinator
relayed it as corroborated, a second reviewer was dispatched to chase it, and a
four-locale clean verdict was recorded for six button labels that had not been
rendered. The generalisable lesson: an evaluation instrument's fidelity to
production is itself a claim requiring proof, and a stand-in that renders
cleanly is indistinguishable from the real surface until something is compared
against the production entry point.

### RETRACTED manager-action-row-overflow | retracted | not reproducible; read off a stand-in

Reported as three action buttons painted past the right edge at one hundred
columns. Those buttons did not exist on the harness surface at the time of the
reading, which preceded the harness repair by twenty-one minutes. Re-driven
after repair with all six actions present: no overflow at that width. Recorded
rather than deleted, because the retraction is the evidence for the
harness-fidelity finding above. The narrower question — whether the six-button
row overflows at the eighty-column floor, particularly under Hungarian — is
open and unmeasured.

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

**Enrol the profile manager in the visual-verification gates.** Ties to the
outside-the-gates finding, and it is the only recommendation here that would
have caught the retracted item honestly rather than by accident.

**Treat an evaluation instrument's fidelity as a claim requiring proof.** Where
a harness composes a production surface, it should call the production
composition rather than reproducing its arguments, and any surface that is
legitimately synthetic should say so in its rendered output, not only in its
source. Ties to the harness-fidelity finding.
