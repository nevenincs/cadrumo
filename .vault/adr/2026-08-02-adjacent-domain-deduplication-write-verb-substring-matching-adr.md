---
tags:
  - '#adr'
  - '#adjacent-domain-deduplication'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:f5bb5f7c1cd84a364b6340cbe2cd6fe53a6f55da907f409a1fd776ce085937d9'
related:
  - "[[2026-04-27-live-submit-permanently-forbidden-adr]]"
  - '[[2026-08-01-adjacent-domain-deduplication-wave-two-audit]]'
---
# `adjacent-domain-deduplication` adr: `AEAT write-verb scan keeps substring matching` | (**status:** `accepted`)

## Problem Statement

The canonical AEAT write-verb denylist matches tokens as substrings of the
lowercased URL. One required read-only page collides with it: the acting-capacity
gate at `/wlpl/OVCT-CXEW/DialogoRepresentacion` contains `presentacion` inside
`Representacion`, so the scan classifies a read surface as a write surface.

The collision is latent. The IVA compensation wallet reaches that gate through a
browser navigation after a URL wait and never routes the URL through its
read-assertion helper, so nothing refuses today. It becomes live the moment any
author adds a guard call at that gate, and the refusal they will see names a
write token the page does not carry.

A decision is needed before that author arrives, because the two obvious repairs
both weaken a gate whose entire purpose is refusing live AEAT writes, and the
weakening would be invisible: a denylist that stops matching produces silence,
not an error.

## Considerations

- The governing decision is that Cadrumo never performs a live AEAT write; this
  scan is one of its enforcement surfaces.
- The scan is a DENYLIST, and a denylist's failure mode is asymmetric: a false
  positive is a visible refusal an operator can report, a false negative is
  silence on a real write.
- The scan is not the only wall. The landing refusal in the sede adapter utils
  is an ALLOW-list and documents that its sibling walls miss browser-driven
  navigation by construction — the verb scan deliberately permits `click` /
  `fill` / `press`, and the HTTP guard sees only first-party requests. The verb
  scan is defence in depth, not the last line.
- Several tokens are deliberately STEMS rather than whole words (`tgvi`,
  `cancel`, `submit`, `sign`), chosen to catch inflected and compounded forms.
  Any matcher requiring whole-segment equality discards that property.
- AEAT's own URL convention is CamelCase compound segments, evidenced by the
  bundled official procedure corpus and the portal constants
  (`RealizarPresentacionLotes`, `TGVIOnline`, `CancelarClaveMovil`,
  `SelectorAccesos`, `ObtenerClaveMovil`). Write verbs appear INSIDE segments as
  a rule, not as segments.

## Considered options

- **Keep substring matching; handle the collision by allow-list (CHOSEN).**
  Preserves every current detection; addresses the false positive at the one
  surface that has it, where the read-only status is a local, checkable fact.
- **Match whole path segments instead of substrings (REJECTED — measured).**
  Removes the false positive without touching the token set, which is why it is
  tempting. Measurement rejects it: it loses 37 real write surfaces and gains
  none.
- **Narrow the token set (REJECTED).** Trades a visible false positive for
  silent false negatives on the exact surfaces the set exists to catch. Removing
  `presentacion` alone would unguard the batch-presentation endpoints.
- **Leave as-is, documented (VIABLE FALLBACK).** The collision is latent and a
  change to a live safety constant carries its own risk. Rejected only because
  the allow-list option costs little and removes the trap for the next author.
- **Case-fold inside the token scan (REJECTED — not a defect).** Investigated
  and withdrawn; see Rationale.

## Constraints

- No change to `AEAT_WRITE_FORBIDDEN_VERB_TOKENS` or to the matcher is
  authorised by this record. It rules on direction only.
- The allow-list entry must be surface-scoped, not global: it admits one gate
  URL on one read policy, and must not become a general escape hatch.
- The canary tuple naming state-creating paths has no consumer, so no existing
  test would catch a regression in either direction. Any implementation must
  bring its own coverage rather than assuming that tuple provides it.

## Implementation

Direction only; no code lands with this record.

The matcher and the token set stay as they are. A benign collision is admitted
by an explicit read-only allow-list entry rather than by weakening the scan.

That remedy is SURFACE-SPECIFIC, and the author applying it must first establish
what the surface's allow-list actually gates. An allow-list named for one guard
may be shared by another, and an entry added to quiet a URL-scan false positive
then silently widens the second guard.

The IVA compensation wallet is the worked counterexample, and on that surface the
entry MUST NOT be written. Its read-path prefix tuple is consumed by the landing
refusal, so adding the gate path there would make a page still sitting on the
acting-capacity gate pass as a completed read. The module already excludes both
Cl@ve transit surfaces in writing, on the grounds that they are transit rather
than rest, and it records that its landing rules do not share one guarantee: the
own-name continuation's rule follows a URL wait that has already required the
traversal to reach the target, while the wallet execute rule follows a load-state
wait only. The rule with no URL wait in front of it is exactly where admitting
the gate would open a hole.

So on the wallet the collision stays documented and unadmitted. Any surface that
does take an entry lands it in the same change as the guard call it unblocks, and
brings coverage with it, because the existing state-creating canary tuple is dead
and proves nothing.

## Rationale

The knockout is measured, not argued. Both matchers were run over 797 distinct
AEAT paths and URLs scraped from the tree, under the same lowercasing production
applies. Substring matching flags 58; segment matching flags 21. The 37 that
only substring matching catches include the batch-presentation endpoint
`RealizarPresentacionLotes` and eleven of its query variants, the TGVI upload
surface `TGVIOnline` and its variants, `CancelarClaveMovil`, and the
`SvPresentacionQuery` surfaces. Segment matching catches nothing substring
matching misses.

Those URLs are not fixtures. `RealizarPresentacionLotes` and `TGVIOnline` are
published by AEAT and bundled in the official procedure corpus under the modelo
instruction files. The write verbs sit inside CamelCase compound segments, which
is exactly the shape whole-segment equality cannot see. So segment matching
would blind the scan to AEAT-documented batch presentation and to the TGVI
upload surface that the token set's own comment singles out as creating
finalized server-side state before legal presentation.

Set against that, the false positive is four corpus instances of one gate URL,
on a surface whose read-only status can be established locally and recorded once.

The case-folding option was investigated and withdrawn on evidence. Calling the
private token helper directly does miss `PRESENTAR` and `PresentarDeclaracion`,
which reads as a false-negative defect — but both production call sites
lowercase before calling it. The apparent bug was an artefact of probing a
private helper outside the precondition its callers establish, and asserting it
would have put a false claim in this record.

## Consequences

The scan keeps its known false positive, and this record is what stops the next
author repairing it in the direction that looks obvious and measures worse.

Allow-listing as the general remedy carries a trap this record now names: the
package trusts allow-lists over denylists, which makes adding an entry feel like
the safe move, and on a surface whose allow-list is shared with a landing
refusal it is the opposite. "Admit the benign collision" and "widen a page-
landing guard" can be the same edit. The check is cheap -- read what consumes
the list before adding to it -- but nothing prompts it.

Two gaps stay open and are not closed here. The wallet still reaches that gate
without routing the URL through its read assertion, so the guard is absent from
the path rather than wrong on it. And the state-creating canary tuple has no
consumer, so nothing in the suite exercises this scan's behaviour on the paths
the project itself nominates as dangerous — a guard with a declared canary set
and no test that fires it.
