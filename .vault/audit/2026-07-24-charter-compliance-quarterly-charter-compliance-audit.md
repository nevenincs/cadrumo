---
tags:
  - '#audit'
  - '#charter-compliance'
date: '2026-07-24'
modified: '2026-07-24'
related: []
---

# `charter-compliance` audit: `quarterly charter compliance`

## Summary

Quarterly charter-compliance pass over the four safety axes, run at HEAD after roughly two hundred commits landed in a single day -- including a CLI verb hard-cut, an environment-source severance, a keychain custody change, and a large branch merge. That churn is exactly what silently flips a default, so every axis was re-measured rather than carried forward.

Three axes are COMPLIANT and were confirmed by measurement, not by reading intent. The fourth could not be verified at all, and that is this pass's finding.

## Live-write defaults: COMPLIANT

No live-submission surface exists to gate. A sweep for a submit or live-submit command registration across the CLI entrypoints returns zero, and the package directory the charter's static check names as the sole permitted home for live-write code is ABSENT from the tree entirely. There is therefore no path that can file, mutate, notify, or submit remotely, gated or otherwise.

The opt-in control defaults closed: constructing real settings yields an empty value for the live-tests field, so the gate is off unless an operator sets it explicitly. Eleven safety tests across the authentication gate and the Renta-WEB-open live-proof module pass at HEAD.

One measurement note worth recording rather than hiding: the first run of those safety modules reported eleven passed and ONE DESELECTED. Rather than accept the green, the deselected case was chased down -- it is gated on an external-tool marker, not a hidden integration test, so no safety coverage is being skipped. The green was honest, but it was only knowable by checking.

## Bootstrap order: COMPLIANT

The bootstrap-exempt set holds twelve configuration verbs, and both retired spellings from the verb hard-cut are correctly absent from it. A stale exemption would have been the likely residue of that cut, and there is none.

The write-policy allowlist question is deliberately NOT re-audited here. It is being verified independently against the campaign's own closure step, and duplicating it would produce a second opinion on the same surface rather than more assurance.

## Default output language: COMPLIANT

The resolved default is Spanish, and the shipped environment template agrees. The charter's concern -- that a maintainer whose own language is Hungarian might drift the default toward it -- does not hold: nothing has moved.

The audit checklist names this control by its pre-rename environment variable. The variable now carries the product prefix. The checklist item is stale in NAME only; the value and the behaviour are unchanged, and the checklist should be refreshed so a future pass does not read a missing variable as a missing control.

## The four-factor gate: NOT VERIFIABLE

This is the finding. The four-factor gate could not be verified because its DEFINITION could not be located in the tree.

A repository-wide sweep across source, documentation, and the decision corpus returns exactly one reference to it: a single line in an unrelated decision record noting that the change did not alter "the 4-factor safety charter". Nothing defines what the four factors ARE. There is no implementation, no test asserting four distinct conditions, and no charter document enumerating them that a search could reach.

The scepticism this pass was asked to apply is that a factor which is declared but unenforced is the failure mode -- the shape found elsewhere tonight, where four protected environments existed with zero required reviewers, so the human gate the surrounding text described did not actually exist. The situation here is one step earlier and harder: the gate cannot be tested against its specification because the specification is not discoverable. An unverifiable gate is not the same as a broken one, and it is NOT being reported as a defect in the gate itself. It IS being reported as a gap in the audit's own foundation, because a quarterly control that cannot be checked provides no assurance while appearing on the checklist as though it does.

The audit issue points at two external tracking items for the underlying rules and acceptance criteria. Those were not read within this pass, so it is possible the four factors are enumerated there and simply never landed in-tree. That possibility does not resolve the gap: a safety control whose definition lives only outside the repository cannot be enforced by any gate inside it.

## Recommendations

Locate or author the four-factor definition and land it in-tree next to the code it governs, then add a test that asserts each factor independently rather than asserting the gate as a whole. Until that exists, this axis should be marked unverifiable on the checklist rather than passed.

Refresh the checklist's environment-variable name to its post-rename spelling.

Treat the absence of a live-write package as the compliant state it is, and keep the static check that names it -- a check that passes because its target does not exist still fails loudly the moment someone creates it.
