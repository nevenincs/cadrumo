---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ad9fe371e9a1aebb5bc66690023216569db1460695feaad9770d83124bf353ad'
step_id: 'S73'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Add the withdrawal verb: list consent-ledger entries, state plainly that transmitted bytes cannot be recalled, mark cloud-derived artefacts, and offer local re-derivation from the cached transcription that re-stamps provenance without rewriting history

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Add the withdrawal service: enumerate consented dispatches, mark artefacts whose provenance names an off-host transport, and re-derive one on this host from its cached transcription.
- Give the text reader's provenance stamp the transport segment it lacked, mirroring the vision reader.
- Add the two operator verbs under the evidence group, both carrying the unrecallable statement on the typed notice channel and in the payload.
- Author the nine operator strings in all four catalogues.

## Outcome

Withdrawal cannot recall a transmitted byte, so the surface says so rather than implying otherwise. The statement is a field on the survey and on both JSON envelopes, not only rendered prose, because an agent consuming the envelope never sees prose. It is unconditional: an operator with an empty history still gets it, since that is precisely the operator deciding whether to enable the route.

Re-derivation asserts rather than overwrites. The outcome names the superseded stamp beside the new one, the consent ledger is never touched, and a reader that stamps a cloud transport is refused outright — that last one is the failure that would otherwise be invisible, where the operator asks to come back on-host, the reader routes off-host anyway, and the artefact is re-stamped as re-derived while the transmission just happened again. No cached transcription means refuse, never a silent fresh read of the document.

Re-derivability is `bool | None`. The draft store keys by evidence reference and the transcription cache by content address, so without an injected resolver the join cannot be made; `None` says the question was never asked, which is a different fact from "cannot", and the two lead an operator to different actions.

A defect surfaced and was fixed because it blocked the Step: the text reader's stamp carried no transport segment while the vision reader's did. Since the survey marks cloud-derived artefacts by that segment, every text-read cloud artefact would have been invisible to a withdrawal — the artefact most needing re-derivation.

The consent ledger from the sibling Step was consumed, not duplicated. Its entries enter as an application-side projection rather than an adapter import, which keeps all six import contracts green.

## Verification

    uv run --no-sync pytest -n0 -p no:cacheprovider src/cadrumo/application/ledger/tests/test_consent_withdrawal.py -q
    17 passed in 2.50s

    uv run --no-sync pytest -n0 -p no:cacheprovider src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py src/cadrumo/application/ledger/tests/test_consent_withdrawal.py -q -m ""
    532 passed in 43.10s

Both verbs resolve against the live surface, help text rendering from the catalogues rather than a default. Every catalogue value is a real translation in all four languages, confirmed by codepoint inspection rather than by a console render, which had shown a false mojibake.

The marker filter matters here: a first attempt with `-m "unit or integration"` selected nothing and the runner said so explicitly rather than reporting green.

## Notes

Three incidents, all caused by this Step and all repaired.

**A peer's file lost four lines to a positional slice.** Backing an earlier draft out, an index-based slice between two anchors removed a peer's `derived_from` field and its comment, which sat inside the span. Caught on the post-edit diff and restored to byte-identical HEAD; nothing was committed in that state. An exact-string edit fails loudly where a positional slice silently takes whatever a peer put between the anchors.

**A stale-HEAD patch nearly reverted a landed translation.** The own-only index patches were built from a HEAD capture that a sweep had already superseded, so the Hungarian catalogue's patch would have replaced a real translation with a placeholder. The staged numstat showed three deletions against an expected zero, which is the check that caught it; the patches were reversed, the index restored to HEAD exactly, and everything rebuilt from a fresh capture. Deletions in a purely additive change are the tell.

**A verification passed for the wrong reason.** An earlier cleanup checked that no catalogue line mentioned the consent keys and read the empty result as success — while the file was, at that moment, truncated by twenty-one thousand lines. Absence satisfied the check. A size or parse assertion alongside the content grep would have caught it; the grep alone could not.

Two conditions were surfaced rather than repaired. The catalogues carry two key-echo placeholders belonging to other lanes, which this Step's scaffold run converted from missing keys into placeholders — the same debt, a different gate, and not this Step's prose to author. And the locale tooling has moved from the shipped package to `dev/locales`, which the standing locales rule still names by the old path.

The plan row's scope names the CLI, but the logic sits in the application layer with the CLI as its surface, following the layering the rest of the ledger uses.
