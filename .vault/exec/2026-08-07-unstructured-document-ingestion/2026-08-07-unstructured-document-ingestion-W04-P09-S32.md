---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9c0a9691b9cd0e7b0bb81a17b0cdcace053c2f0103f4848de6d7deb363bcbc3d'
step_id: 'S32'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Add the injection regression gate: an instruction-shaped transcription must cross the S2-S3 boundary with no unanchored value and no out-of-schema key, proven by mutation

## Scope

- `src/cadrumo/llm/tests`

## Description

- Build the acquisition-stage transcription of the already-bundled adversarial injection specimen through the real extractor, so the text the boundary is exercised with is the document's own.
- Gate the first property: a proposed value whose printed form does not occur in that transcription must not ground.
- Gate the second property: a payload carrying the keys the specimen's own instruction names must be refused whole, and each named key must be refused on its own.
- Drive the hostile payload across a real loopback HTTP server through the production client, so the refusal is demonstrably the schema boundary rather than an earlier layer.
- Record, as passing assertions, the two cases the anchor check does not catch, and the arithmetic leg that does.

## Outcome

Two independent properties are gated, each proven separately rather than through one shared assertion.

No unanchored value crosses the boundary: a figure absent from the document, a wholly fabricated figure and an empty anchor all fail to ground, while the document's own printed total does ground. That last one is the positive control, without which a check that refused everything would score as a pass.

No out-of-schema key survives: the specimen's instruction names five keys of its own, the compliant payload is refused whole, and each of the five is refused individually so the whole-payload refusal cannot be one key carrying the other four. A payload identical but for those keys parses cleanly, which is what makes the refusals about the keys rather than about the payload.

The transport half runs against a real loopback server speaking the provider wire shape. The reply it serves is authored by the test, and the module docstring says so plainly: no model is loaded and no inference runs. What that buys is a genuine assertion that the hostile keys survive the client path unmodified, which is what makes the schema boundary the demonstrated refuser rather than an assumed one.

### The specimen chose itself, and corrected a mistake in the premise

The adversarial injection document was already bundled, so no fixture was authored. It is well suited beyond convenience: it is a genuine invoice carrying a real instruction paragraph, so it exercises the case where an attacker must leave a plausible document behind.

The first choice of injected figure was wrong and the premise-anchoring test caught it. The anchor search is a substring match, and the obvious injected total occurs inside the document's own printed base. The gate now uses a figure genuinely absent from the document, and the near miss is preserved as its own assertion rather than quietly avoided, because it is a property of the check and not a quirk of this fixture.

### What the gate deliberately does not claim

The anchor check verifies that a value's printed form is present in the document, not that it plays the role claimed for it. Two consequences are recorded as measured, passing assertions rather than left to be discovered later.

An injected sentence that prints its own plausible figure passes the anchor check. And more sharply, a short figure anchors inside a longer printed one, so a total of zero anchors against any document printing a value that ends the same way, which is a large share of real invoices. Closing that needs a boundary-aware anchor search and belongs to the module that owns the check, not to this gate.

Both cases are caught downstream by the arithmetic closure, which is asserted here alongside them. The boundary's real strength is therefore recorded as the conjunction of the two legs rather than overstated as the anchor check alone.

### The vision lane is not claimed

The text lane's anchor is checked against a transcription produced by a separate deterministic reader, so the check has an independent witness. The vision lane reads image to fields in one model call and produces no transcription, so its anchor is reported by the very model that produced the value; a model complying with an instruction can equally invent the anchor supporting it.

No assertion is made about the vision lane, because none would be honest: a test passing because a model dutifully reported an invented anchor would prove nothing while displaying a pass. The difference is stated in the suite rather than assumed away, and the one structural assertion made instead is that the text-lane check genuinely requires a document it did not write.

## Verification

    uv run --no-sync pytest src/cadrumo/llm/tests/test_injection_regression.py -n 0
    21 passed in 21.95s

Collected 21, zero deselected.

    uv run --no-sync pytest src/cadrumo/llm/tests/ -n 0
    260 passed, 3 deselected in 184.55s (0:03:04)

Collected 263. The three deselected are the live provider round-trip and two dependency-absence cases, all excluded by the suite's own marker expression and none of them belonging to this step; every one of this step's twenty-one ran.

    uv run --no-sync ruff check <touched file>
    All checks passed!

    uv run --no-sync --group typecheck basedpyright <touched file>
    0 errors, 0 warnings, 0 notes

Both properties were mutation-proven independently, each from a throwaway plugin on the interpreter path outside the repository, with nothing inside the tree edited.

Making the anchor check ground a value with no printed form reds four: the three unanchored cases and the structural assertion that the text-lane check needs a document it did not write. None of the schema tests move.

Making the candidate schema drop out-of-schema keys instead of refusing them reds seven: the whole-payload refusal, all five per-key refusals, and the transport case that ends in the same refusal. None of the anchor tests move.

The two blast radii do not overlap, which is what makes them proofs of two properties rather than one.

## Notes

The git index was locked when this step finished: a zero-byte lock file whose modification time had not advanced in over two minutes, which reads as a dead holder rather than contention. Per standing instruction it was left untouched and the commit deferred rather than worked around. It cleared on its own a few minutes later and the work committed normally, which is the outcome that instruction exists to produce.

The target package carries substantial concurrent work: several reader and grounding modules and four sibling test files were modified by another lane throughout, and a closely related anchor gate was untracked beside this one. That neighbouring gate was read in full before authoring, precisely to avoid duplicating it; it covers what the reader reports, while this one covers what survives the crossing into the checking stage. Nothing owned by that lane was edited.

The transcription is constructed in the test from already-public interfaces rather than by promoting the acquisition function to the package facade, because that facade was itself under concurrent edit. Promotion remains the better shape once the contention clears.
