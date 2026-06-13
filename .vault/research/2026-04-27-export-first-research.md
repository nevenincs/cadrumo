---
tags:
  - '#research'
  - '#export-first'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-12-gsuite-bootstrap-audit]]"
  - "[[2026-04-16-submission-safety-sweep-adr-audit]]"
  - "[[2026-04-17-export-first-adr]]"
---



# `export-first` research: product direction pivot from live-filing to produce-verify-export

The early roadmap anchored releases on automated live AEAT submission, framing
milestone 0.2.0-alpha as "first live filing" and 0.3.0-beta as "unattended filing."
This research investigated whether that direction was achievable and safe, given the
state of calculation correctness, the AEAT legal context, and Kent's actual unblocking
needs.

## Evidence base

The following documents form the evidence base consolidated here:

- `2026-04-17-kent-ux-journey-audit` — enumerated twenty concrete walls between
  `git clone` and a submitted Modelo 130. Walls are concentrated in onboarding, the
  T1→T2 bridge, T6 aggregation, and the review/approval step. The submission pipeline
  is comparatively mature but gated on correctness the project had not yet delivered:
  producing a verifiably correct draft required the user to write Python manually at
  two pipeline stages. This audit was the primary evidence that anchoring on live
  submission was premature.

- `2026-04-17-kent-revise-review-audit` — assessed the revise-and-review loop and
  confirmed that Kent had no human-in-the-loop approval path and no exportable artifact
  he could independently upload. The audit identified the lack of an explicit approval
  state on drafts and the absence of AEAT-importable export formats as the practical
  blocking gaps, reinforcing that the value proposition should be "correctly compute,
  transparently review, cleanly export" rather than "auto-file."

- `2026-04-12-gsuite-bootstrap-audit` — covered the Google Workspace integration
  bootstrap context, referenced by the export-first ADR as background on the broader
  Kent capability dependency chain.

- `2026-04-16-submission-safety-sweep-adr-audit` — documented the live-write safety
  audit triggered by charter #116. Confirmed that AEAT has no sandbox (every live
  submission is legally binding and irrevocable) and that the existing safety gates
  are sound but cannot compensate for incorrect upstream numbers. Provided the legal
  and safety grounding for the ADR's decision to defer live submission.

## Consolidated finding

The combined evidence established that shipping live AEAT submission before
calculation correctness was end-to-end verified was a legal and reputational risk the
project could not responsibly take. AEAT's portal already provides a fully functional
import/upload surface, so removing auto-submit from the MVP removes the most legally
loaded feature without removing any user-facing value. The ADR re-anchored the product
direction to produce-verify-export: Kent produces a correct, reviewable draft; exports
an AEAT-importable file; and manually uploads it — retaining full control and giving
the project time to verify calculation correctness before any live write path is opened.
