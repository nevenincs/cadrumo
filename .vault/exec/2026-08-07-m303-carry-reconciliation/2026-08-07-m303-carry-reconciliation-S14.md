---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:19638717a87e40ed2f8f582796e9fe7ae65afbf6db882c3d1b02d9f3debe602f'
step_id: 'S14'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
## Description

- Take the fichero route this row named, rather than widening the extraction-profile targeting model.
- Build the typed header fact in `core`, carrying the header key, the token, the artefact kind and the export parser's own source locator.
- Make the discarding projection the canonical typed one, and reduce the flat key-to-token mapping to a derived view over it.
- Add the typed field to the filed observation and to the persisted observation payload, as its own save parameter.
- Prove the fact survives storage rather than proving the capture assembled it.

## Outcome

This row asked for a decision between two representations and observed that one of them is far cheaper. The fichero route was taken, and the row's own reasoning is why: `parse_export_payload` already returns the header fields, only the observation projection discarded them, so the route needs no schema change at all while widening the profile targeting model would have been a change to a registry schema serving every modelo.

The limitation this row recorded stands unchanged and is not worked around. An extraction profile still cannot target a non-casilla record field, because its targeting collection admits only casilla ids. Nothing here widens that, and nothing here needs to: the header facts are recovered from the parsed fichero, which is the alternative the row named as acceptable.

What that means for the generalisation the row was careful to state, that this reaches past Modelo 303 to every non-casilla header AEAT prints and encodes: the fichero route generalises with it. The typed fact keys on the registry export layout's own `header_key` rather than on anything Modelo 303 specific, so a second modelo whose diseño declares headers is already served. The `header_key` axis is a constrained string rather than an enum for that reason among others, measured at 69 distinct values across the bundled modelos including loader-generated slugs.

The value limit this row's sibling asked to be carried into the typed representation's own docstring is there, since a record is read once and a docstring is read by everyone who touches the field.

## Verification

The typed roundtrip across the encrypted observation boundary, real adapters throughout, every defaultable payload field non-default:

    uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_observation_header_facts_roundtrip.py -n0 -q -m ""
    3 passed in 46.95s

The producer end, asserted on what came back out of storage:

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_header_facts_reach_storage.py -n0 -q -m ""
    2 passed in 58.44s

Mutation from a plugin loaded outside the repository, dropping the typed argument on the way to the payload, with the rebinding asserted to have held the original callable:

    MUTATION APPLIED: source_headers dropped on the way to the persisted payload (1 holder)
    4 failed, 1 passed in 58.61s

The survivor asserts the flat metadata projection carries no header, touches no persistence, and is correct to live. It is also the discriminating half: without it, a later change could route the facts back through the flat mapping, satisfy every arrival assertion, and drop the locators silently.

## Notes

Relationship to the sibling rows, since this row's decision is what they turn on.

`S12` is closed by the same change and carries the fuller record. Its open half was exactly the persistence gap: the projection reached the observation and the persisted provenance was assembled from a fixed key set copying one key, so the fact died one layer below where that row was looking. The typed field closes it because a structural field cannot be dropped by a projection that copies a hand-listed set of keys.

`S13` is NOT unblocked by this and is deliberately left open. It asks whether the disposition can be recovered from the printed declaración render for filings that hold no submitted-file artefact, and it instructs that its first task is establishing whether that population is even non-empty. This change makes the disposition available wherever the fichero IS held, which narrows what `S13` would be for, but it does not answer the population question and must not be read as having done so. If every filed Modelo 303 stores a submitted file, `S13` has no subject and should close rather than be built, and that is still unmeasured.

An extraction-profile consequence worth stating because it is the opposite of what a reader might expect: nothing in this change makes the profile targeting model any more able to address a header. A later reader looking for the header facts will find them on the observation and in the persisted payload, and will find no profile that mentions them. That is the intended shape rather than an omission.

Residual, carried from `S12` rather than repeated in full: nothing refuses a wholesale loss of the header channel, because the field must default for producers that legitimately have no headers, so strict inequality is the only detection available.

Attribution: the source landed under peer bare whole-index commit subjects rather than under any subject of mine, and one of those sweeps briefly published a HEAD that imported the core type without the module defining it. The paired records for this row and `S12` are the only place that attribution exists.
