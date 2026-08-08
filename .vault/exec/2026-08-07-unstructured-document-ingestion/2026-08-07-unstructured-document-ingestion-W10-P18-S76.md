---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:9a9fdfe5fa214a0287b07832fa0f43f6b7fb4c199ebf9a9836e7ec8866da7997'
step_id: 'S76'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Sweep every W08 through W10 verb for the pull and --file naming standard, envelope and notice conformance, and documented-command coverage, gated by the conformance suites red-green proven on one deliberate violation

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Walk the live Click tree in process and audit every resolved command path for a forbidden fetch synonym and every leaf for a forbidden single-local-file option name.
- Confirm the campaign's new verbs carry the standard: the batch and invoice import surfaces name their file input `--file`, and no verb in the surface is a fetch synonym.
- Confirm the envelope and notice standard is structurally covered for the new verbs rather than covered by inspection, by reading how the schema gate selects what it checks.
- Measure documented-command coverage per verb against the reader-facing pages and the private sequence contracts.
- Add the missing positive controls for the two conformance detectors that had none, driving each through its real producer.
- Control the over-fire direction as well as the firing direction, so primary structured result data is proven not to be flagged.

## Outcome

The naming standard holds across the new surface. Walking the live tree resolves 381 command paths; none of the campaign's verbs is named with a fetch synonym, and none carries `--source`, `--path`, `--from-file` or a transport-multiplexing `--from-*` family. The single-local-file inputs are `--file` on the batch verb and on the invoice import verb.

Two tree-wide hits are deliberately not filed. A verb reading a configured folder setting and a verb mirroring to a spreadsheet are named `get` and `sync`, but the standard governs a fetch from the tax authority; neither reads from it, so promoting them would be applying the rule by spelling rather than by referent. A first sweep also flagged nine `--from-*` options, and all nine are range bounds paired with a `--to-*` sibling, or a source record to clone. The rule forbids a `--from-*` family that multiplexes TRANSPORT on one verb, not the prefix itself, so the detector was narrowed rather than the surface changed.

The envelope and notice standard needs no hand sweep on this surface, because its gate is parametrised over the registered schema keys: a new verb enrols itself the moment it registers a schema. That is the opposite of the documented-command gate, which is doc-driven. It validates invocations that documentation cites, and therefore says nothing at all about a verb no page cites. Seven of the campaign's verbs are cited in no reader-facing page and no sequence contract, so the coverage this row asks about is presently vacuous for them. That is recorded as a finding rather than closed here: the pages are authored by the main session, and a gate reddening on prose this lane cannot write would be a red gate with no owner.

The substantive gap this row closes is elsewhere. Three standards, three gates, and the suggestion-citation gate already proved its scanner can return a non-empty answer. The other two had not. The documented-command gate's option-validity and dead-subcommand checks are its high-signal content, and the schema gate's bespoke-diagnostic check carries the whole notice standard, and neither had ever been shown to fire. Every conformance assertion resting on them was equally consistent with a detector that reports nothing.

Both directions are now controlled, and the second is the one that matters here. A control proving only that the diagnostic detector fires is satisfied by a detector that fires on everything, which would flag verify findings, calendar warnings, a next-due date and a per-finding next action. Those are a command's primary output, not incidental advisories, and a gate flagging them would push authors to hide legitimate result fields from their own schemas.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_conformance_detector_controls.py -n0 -p no:cacheprovider -q -m integration
    19 passed in 11.53s

Three mutations were applied at runtime from outside the repository, rebinding each detector in the CONSUMING module's namespace rather than in the module that defines it. The controls import both detectors by name at import time, so rebinding the definition site would have reached nothing and every mutation would have read as ineffective. Each mutant carried an invocation counter and each reported a non-zero count, which is what distinguishes a mutation that was applied from one that was merely declared.

Blinding the option-validity detector to an empty verdict reddened both the fabricated-option control and the dead-subcommand control while the clean-options control stayed green. Forcing the diagnostic detector always true reddened the primary-result-data control while the smuggled-field control stayed green. Forcing it always false reddened the smuggled-field control while the primary-result-data control stayed green. Each mutation flipped the expected control and only that control, so the pair discriminates rather than firing together.

    uv run --no-sync pytest <the four conformance gates> -n0 -p no:cacheprovider -q -m integration
    2 failed, 701 passed in 183.21s (0:03:03)

## Notes

The two failures in that run are live and belong to peer lanes, not to this surface. One is an operator-surface help entry whose description exceeds the eighty-character limit its own model declares; that entry is absent from the tree read at the start of this work and arrived during it. The other is a hash-redaction rule shipping without the identifier vocabulary the suggestion gate needs in order to see what it redacts. Both sit outside this row's scope, and both belong to campaigns still holding uncommitted work, so neither was touched.

The seven undocumented verbs are the batch verb, the confirm verb, the extract verb, the two consent verbs and the two evidence review verbs. Each resolves in the live tree and each registers a schema, so the naming and envelope standards cover them; only the documentation standard does not. They need reader-facing prose before the documented-command gate can say anything about them.

The commit for this row could not be taken: the repository index lock was held with a frozen timestamp for over four minutes, which indicates the holding process died rather than that a peer is mid-write. The lock was left untouched and reported. The control file is complete on disk and will be swept in by the next blanket commit, which is how the packaging half of this dispatch landed.
