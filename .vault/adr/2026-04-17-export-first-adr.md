---
tags:
  - "#adr"
  - "#export-first"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-12-gsuite-bootstrap-audit]]"
  - "[[2026-04-16-submission-safety-sweep-adr-audit]]"
  - "[[2026-04-18-auth-provider-ecosystem-research]]"
  - "[[2026-04-27-export-first-research]]"
---

# export-first-adr

## status

Proposed — 2026-04-17. Supersedes the implicit "first live filing" milestone direction encoded in `0.2.0-alpha` (milestone #4) and the "unattended filing" framing of `0.3.0-beta` (milestone #5).

## context

The Kent UX journey audit (`.vault/audit/2026-04-17-kent-ux-journey-audit.md`) enumerated twenty concrete walls between `git clone` and a submitted Modelo 130. The walls are concentrated in three places: onboarding, the middle of the financial pipeline (T1→T2 bridge, T6 aggregation), and the review/approval step. The submission pipeline and its `--i-understand-this-is-real` safety gate are comparatively mature, but they are gated on correctness the project has not yet delivered: the tool cannot today produce a verifiably correct Modelo 130 draft without the user writing Python twice (to bridge `aeat financial ingest` into the catalogue and to aggregate the classified catalogue into casilla-level numbers).

Two additional facts make continuing to anchor releases on "live filing" strategically wrong:

1. **AEAT has no sandbox.** Every live submission is legally binding and irrevocable. Live-write safety charter #116 encodes six non-negotiable rules around this. Shipping the live-write path before calculation correctness is end-to-end verified is a legal and reputational risk the project cannot responsibly take.

2. **Live filing is not what Kent needs first.** Kent needs correct numbers, reviewable traces, and a file he can upload himself to the AEAT portal. The AEAT portal already provides a perfectly functional import/upload surface and will continue to do so. Removing the "auto-submit" requirement removes the most legally-loaded feature from the MVP without removing any user-facing value.

Read-side AEAT live calls are a different story. Kent cannot verify his filing without access to previously submitted information (expedientes, justificantes, datos fiscales, notificaciones). Live reads must stay on the critical path.

## decision

The project re-anchors its product direction to a **produce-verify-export** flow. Live AEAT submission writes are removed as a near-term feature goal and are moved to the final release milestone (1.0.0), gated behind an explicit opt-in and the existing #116/#117 charter. Live AEAT reads remain on the critical path and stay in their existing milestones. Calculation correctness, human-in-the-loop review, and export to AEAT-importable formats become the engineering anchors of every pre-1.0.0 milestone.

The canonical happy path becomes:

```
auth  →  live-read sync (expedientes, justificantes, inbox, datos-fiscales)
     →  financial ingest (T1)  →  normalise (T2)  →  enrich (T3)  →  classify (T4)
     →  persist (T5)  →  aggregate to casilla (T6)
     →  compute (formula engine)  →  review (trace + operand display)
     →  approve (explicit human gate, persisted)
     →  export (AEAT-importable file: PDF + modelo-specific format)
     →  [user manually uploads the exported file via the AEAT portal]
     →  re-sync: fetch the resulting justificante back into local state
     →  verify: local draft checksum matches the justificante
```

Live submission (`aeat submission submit`) is not part of this flow. It continues to exist as code, protected by the #116/#117 gate, but is **hidden from `--help` by default, relocated to a dedicated `aeat live-submit` group, and activated only by an explicit env flag**. It is not shipped as a user-facing feature until every other milestone has closed.

## scope

**In scope for this ADR (what changes):**

- Milestones are renamed and reframed. `0.2.0-alpha` becomes the *produce-verify-export* milestone. `0.3.0-beta` becomes the *export-hardening + live-read verification* milestone. `1.0.0` becomes the *live-filing opt-in* milestone.
- New `area:export`, `area:review`, `area:submission`, `ux`, `ux:error-messages`, `ux:cli-output`, and `charter` labels are added.
- New EPICs are filed: `aeat submission export` (produce AEAT-importable files) and `aeat review` (explicit approval state on drafts).
- Existing issues whose titles advertise "first live filing" or "unattended filing" are retitled. Their scope may be split (live-read scope stays; live-write scope moves to 1.0.0).
- A ROADMAP.md is published anchoring each milestone to a Kent-centric question.

**Explicitly out of scope:**

- Removing or weakening the live-read surfaces (expedientes, justificantes, inbox, datos-fiscales). These remain prioritised — they are how Kent verifies his exports against AEAT's own records.
- Removing or weakening the `aeat submission preflight` and `aeat submission dry-run` commands. These gain importance under this ADR: they are the final pre-export validation.
- Deleting the `aeat submission submit` implementation. It stays as code. Only its activation and discoverability change.
- Changing the live-write safety charter #116. This ADR builds on #116 and does not replace it.

## consequences

**Positive:**

- The legal exposure surface shrinks to zero live-write paths by default. The project ships with the write-path disabled, not merely rate-limited.
- Engineering capacity re-concentrates on correctness (formula engines for 303 and 390, T1→T2 persistence, T6 aggregation, bulk categorisation, review approval state). These are the walls Kent hits first.
- The MVP becomes shippable sooner. Kent can produce a verifiable, reviewable, importable file and use the existing AEAT portal upload surface to self-file. The tool's value proposition stops being "auto-file" and becomes "correctly compute, transparently review, cleanly export."
- Trust posture improves: users and auditors see an explicit "we do not file for you" stance.

**Negative / costs:**

- The product narrative changes. "End-to-end automated tax filing" becomes "end-to-end automated preparation, manual final submission." Mitigation: this is honest, it is a valid product in its own right, and it is a strictly larger market (many users would *prefer* not to hand a tool write-access to AEAT).
- Some work done under the assumption of live-filing-as-MVP becomes premature. Mitigation: the work itself is not lost — it is gated and moved to milestone 1.0.0, not deleted.
- Export is a new feature surface with its own research burden (which file formats does AEAT's portal accept per modelo?). Mitigation: this research is genuinely needed anyway and would have been a blocker inside the live-submit path too.

**Neutral:**

- #116 and #117 remain in force. This ADR does not weaken them; if anything, it makes them easier to honour because the default ships with live-write disabled.
- Live-read auth work (#141 and the auth cluster) continues unchanged. Reads block on cert auth; writes stay off.

## alternatives considered

1. **Ship live filing with stronger gates.** Rejected: the root cause of Kent's blocker is not a weak submission gate; it is missing upstream correctness. Strengthening the gate does not make the numbers correct.
2. **Keep the current milestone names but change the priority order internally.** Rejected: the milestone titles are the de-facto roadmap. External contributors read them as commitments. Renaming is cheaper than explaining.
3. **Delete the submission code entirely.** Rejected: the dry-run, preflight, and safety-gate code is valuable infrastructure for export verification too. Only the activation of the live-submit entry-point changes.

## rollout

This ADR mandates the issue and milestone refactor documented in the companion plan `.vault/plan/2026-04-17-export-first-roadmap-plan.md`. The plan lists every new issue to file, every existing issue to retitle/rescope, and every milestone to rename. Execution is gated on user approval of the plan. No GitHub state is changed by this ADR alone.
