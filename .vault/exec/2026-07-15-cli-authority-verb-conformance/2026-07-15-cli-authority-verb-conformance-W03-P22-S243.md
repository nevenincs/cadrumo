---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:6836f12fa68fa66cf0ff8e2817c7c1f1bd1361c3117ee04034d65be30094327b'
step_id: 'S243'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove duplicate namespace, version, sensitivity, catalogue-key, and custody literals from transaction, invoice, modelo participation, and bucket persistence consumers and bind them to registry definitions

## Scope

- `src/cadrumo/domain/transactions/`
- `src/cadrumo/domain/invoices/`
- `src/cadrumo/domain/modelos/`
- `src/cadrumo/domain/buckets/`

## Description

- Scan all four cited trees for raw namespace, sensitivity, schema-version and catalogue-key literals rather than trusting the sibling plan's closed checkbox.
- Find fourteen surviving metadata declarations in the modelo tree and establish that no production module reads any of them.
- Confirm each registry value is byte-identical to the literal it duplicates before deleting anything.
- Delete the twelve repository constants, the two public participation-index constants, and the two package re-exports.
- Repoint the four roundtrip probes that read them at the registered definitions.
- Correct the adapter comment that recorded the duplication as intended.
- Re-examine what detection the deleted literals had been providing, find four namespace strings left unpinned, and add the deliberate pin that replaces the incidental one.

## Outcome

Not satisfied at HEAD. Implemented under commit `34ae25afda`.

Three of the four cited trees were clean: transactions, invoices and buckets carry no namespace, sensitivity or schema-version literal in production, and the only surviving product-prefixed string among them is a docstring example of a command path. The modelo tree was not clean, and the sibling plan's closed checkbox did not describe it.

Four modelo repository modules each declared a namespace string, a catalogue object key, and a catalogue schema version, twelve constants in total. A fifth module declared a participation-index namespace and schema version and exported both publicly through the package. All fourteen duplicated values the registry already owned. None of the fourteen was read by any production module: the repositories that actually write these stores live in the profile persistence adapters, and each of those had already been bound to the registered definition, reading the namespace, the required default object key, and the schema version off it. The domain constants were vestigial, left behind when persistence moved into the adapters.

They were not harmless, because the roundtrip probes read them. Each probe asserted the on-disk namespace, object key, and envelope version using the domain literal while production wrote at the registry-sourced value, so the two were separate authorities that happened to agree. The probes were green only by coincidence of equality, which is precisely the drift this step exists to close. The participation-index case was the most explicit: the adapter carried a comment stating that the registry value mirrors the domain-owned string, recording the duplication as a deliberate arrangement rather than a defect.

Before deleting, each registry value was compared against the literal it replaced by importing the compiled definitions and printing them. All five namespaces matched exactly, all five schema versions were one, and the four catalogue namespaces all carried the singleton default object key, so the change is behaviour-preserving. The fourteen declarations and the two package re-exports are gone, and the four probes now bind to the registered definitions, leaving one source for the value a probe asserts and the value production writes. The deliberately wrong-sensitivity control in one probe was left alone, since asserting a mismatched class is that probe's job.

The pre-release no-legacy posture governs the two public exports: they were deleted outright rather than aliased, and a tree-wide sweep confirms no surviving reference under source, dev tooling, or docs.

Removing a duplicate can remove detection along with it, so the question of what the deleted literals had been doing was put explicitly. They had been an incidental pin. A namespace string is the on-disk address previously-written rows live at, and one of the deleted declarations carried a comment saying so, warning that the string was preserved across a rename to avoid orphaning persisted envelopes. While the probes hardcoded that string, an edit to the registry's namespace would have failed them. Once both sides read the registry, a registry edit moves them together and the probes stay green.

That detection was assumed to have relocated to the registry's own suite, and the assumption was wrong: of the five namespace strings, only the participation index was pinned there. The four catalogue namespaces had no literal pin anywhere. A deliberate pin was therefore added, following the pattern the registry suite already uses for other namespaces, asserting each of the four namespace strings, its schema version, its singleton catalogue object key, its sensitivity, and that it resolves from the registry under its own key. Two guards make it more than a restatement: resolving each definition through the authority set stops a definition satisfying the test while absent from the registry, and asserting the four addresses are distinct catches a copy-paste that collapsed two, which every per-definition assertion would otherwise pass.

The pin was proven capable of failing rather than assumed to work. Renaming the work-unit namespace in the registry made it fail with the expected string diff; the registry file was then restored and confirmed byte-identical to the committed content, with the suite green again at twenty-six tests.

Verified with sixty tests across the four repointed roundtrip modules plus the work-unit module, one hundred and eighty-one across the whole modelo tree, twenty-six across the registry suite carrying the new pin, and thirty-four across both namespace adoption gates and the registry suite. Type checking and both lint passes are clean on the touched files, and collect-only is clean at fourteen thousand three hundred and eighty-nine tests.

## Notes

Semantic code search was degraded and reported itself healthy, with an empty degraded-reasons list; a probe naming the namespace registry returned only unrelated interface modules and never the registry itself. Every finding here came from direct read and targeted grep, and the equality check that licensed the deletion came from importing the compiled definitions rather than reading declarations.

This step and its sibling cite overlapping but not identical surfaces, and the sibling's closed checkbox was wrong for the modelo tree. The same file-citation drift was recorded against the neighbouring adoption-gate step, which is now three occurrences in this campaign rather than two. The pattern is consistent: a step's scope citation drifts from the work more readily than the work drifts from the step, and a reader with only the plan cannot see it.

The step's wording names modelo participation and bucket persistence consumers, but the fourteen real declarations sat in the four modelo catalogue repositories plus the participation index. Bucket persistence carried nothing to remove. The step's own scope list, which names the whole modelo tree, is the accurate boundary.

The shared index held another agent's staged size-budget work at commit time. It was excluded by naming only authored paths on the commit, and that peer landed its own commit immediately afterward, so nothing was swept or lost.

The function-local import ratchet gate is red at HEAD for unrelated reasons: two ceilings carry headroom over their live counts. This was confirmed to pre-date this work by restoring both touched files to their committed content and observing the identical failure, then restoring the authored versions. It is another campaign's to reconcile.
