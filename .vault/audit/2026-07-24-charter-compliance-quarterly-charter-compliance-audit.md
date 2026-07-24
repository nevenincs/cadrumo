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

## The four-factor gate: RETIRED, NOT MISSING

The first pass could not find the four factors defined anywhere in the tree and reported the axis unverifiable. Reading the charter the audit references resolves it, and the answer is better than a gap: the four-factor gate was DELIBERATELY SUPERSEDED.

The charter states it directly. Earlier repository history used a four-factor live-submit gate model built from environment variables, typed confirmation, and workflow flags. That history is superseded, and the controlling policy is now simpler and stricter -- live submission is permanently forbidden, with the only acceptable accidental-live-write rate stated as zero.

So the definition is absent from the tree because the CONCEPT is retired, not because it was lost. A four-factor gate is a mechanism for permitting a dangerous operation under sufficient conditions. The charter abolished the operation outright, which makes the gate meaningless: there is no opt-in path for it to guard. That is strictly stronger than any four-factor construction, and it is consistent with the live-write axis above, where the audit found no live-submission surface exists at all.

The defect is therefore in the AUDIT CHECKLIST, not the product. The checklist instructs a future auditor to confirm the four-factor gate still fires correctly for the opt-in path. There is no opt-in path, and the gate was retired by the very charter the checklist exists to enforce. An auditor following it literally will either report a phantom failure or, worse, conclude that a permitted-submission path ought to exist and go looking for one to verify.

No four factors were invented to close this. Inventing a safety specification and then gating on it would be worse than the gap, because it would look authoritative while resting on nothing. The honest disposition is retirement of the checklist item, which is an operator decision.

## Checklist defects found

Three items in the quarterly checklist are stale against the charter and the tree. Each is small, and each is the kind that becomes a phantom finding a year from now when nobody remembers the context.

The four-factor item asks to verify a retired control, as above. It should be struck rather than reworded, because there is nothing left to verify.

The default-language item names its control by the pre-rename environment variable. The variable now carries the product prefix. The value and behaviour are unchanged; only the name moved. A future pass reading a missing variable could reasonably record a missing control.

The charter-rules item refers to six non-negotiable rules. The charter now enumerates seven, spanning product policy, runtime refusal, absence of an executable live-write path, regression defence, the live-read boundary, documentation alignment, and enforcement through review and audit. An auditor checking six of seven would silently skip one, and there is no way to tell from the checklist which.

## Recommendations

Locate or author the four-factor definition and land it in-tree next to the code it governs, then add a test that asserts each factor independently rather than asserting the gate as a whole. Until that exists, this axis should be marked unverifiable on the checklist rather than passed.

Refresh the checklist's environment-variable name to its post-rename spelling.

Treat the absence of a live-write package as the compliant state it is, and keep the static check that names it -- a check that passes because its target does not exist still fails loudly the moment someone creates it.
