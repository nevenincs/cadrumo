---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a7a2f98bc548df48c835bc641183562b20ca5e3f76bfc167b7d0e24546c66c74'
step_id: 'S166'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

- `src/cadrumo/application/ledger`
- `src/cadrumo/entrypoints/cli`

## Description

- Add `attribution_unverified` to the per-field provenance envelope, beside the anchor and role-evidence axes it belongs with.
- Add a party-attribution module owning the party table, the enrolled address-field set derived from it, the establishing-origin set, the stamping pass and the operator advisory.
- Expose a printed-evidence-only reading on the establishment ladder so a diagnostic can name a territory by quoting the domain rather than re-deriving the boundary.
- Apply the stamping pass inside the single grounding entry point the reading router uses, after the anchor check rather than beside it.
- Emit the advisory from `review show` as a typed warning Notice on the envelope, with matching text-mode lines rebuilt from the same notice.
- Mirror the stamp onto the extract and confirm provenance payload so the envelope-parity gate keeps passing.
- Author the notice message in all four locale catalogues through the locales CLI.

## Outcome

The stamp is per field, which is the shape the retiring gate needs: one party's postal code can read attributed while the country beside it does not, and a regression proves exactly that pair disagreeing. A draft-level or party-level flag could not express it, so the two states would have shipped together indefinitely.

The advisory reaches the operator through the envelope's one diagnostic channel rather than the review payload. That payload deliberately prints each party's postal code and country and never the territory read off them, on the recorded ground that a second copy of a regulatory boundary must not live on the review surface. An advisory about a territory therefore has no target there. The notice names the territory each party's values would establish, quoted from the ladder's own printed-evidence walk, so the operator gets a concrete claim to contest while the boundary keeps one home.

There is a second and independent reason the Notice channel is right, established by the postal-shape lane after this row was scoped. Every discrepancy kind blocks by construction: there is no advisory tier on the findings channel, and the confirmation gate refuses to import when a kind is unmapped. So the choice was never between a quieter finding and a notice. An attribution stamp routed through findings would REFUSE CONFIRMATION on every draft carrying an unresolved party, which on the majority population is exactly the alert-fatigue failure the ledger contract names for the unconsumed-IVA advisory -- an alert that fires on the ordinary case trains operators to dismiss it, and then it protects nobody on the case that matters. The Notice channel is therefore not merely the sanctioned route for this diagnostic; it is the only one that produces an advisory at all rather than a refusal. This record originally justified the route on the review-payload conflict alone, which is true and weaker.

The establishment ladder has NO production caller at HEAD: outside its own module and the package facade's lazy map, nothing routes a document's parties into it. The notice is therefore written conditionally throughout — it says where the values WOULD place each party, never that a territory was established — and the context key carrying it is named for that mood. The values are the ladder's declared inputs, so the warning is about real exposure, but nothing has yet consumed them on a live path.

Both mutation probes bite with a positive control proving the patched callable ran: neutralising the stamping pass reds nine tests across both layers at twelve recorded invocations, and silencing only the CLI surfacing reds four at five invocations with the control confirming the real advisory was non-empty every time. The second probe is the one that matters — it proves the stamp is not merely recorded but delivered, which is the difference between this row and a checkbox.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_party_attribution.py -n0 -q -m unit
    9 passed in 2.53s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_attribution_cli.py -n0 -q -m integration
    5 passed in 7.20s

    uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/entrypoints/cli/tests -n0 -q -m unit --deselect <peer-red module>
    19 failed, 1715 passed, 3033 deselected, 15 warnings in 222.25s (0:03:42)

    uv run --no-sync pytest <owned surface plus the json-schema and documented-command conformance gates> -n0 -q -m integration
    578 passed, 1070 deselected in 125.50s (0:02:05)

Mutation probe one, the stamping pass neutralised on the consumer namespace at plugin module scope:

    9 failed, 5 passed in 5.86s
    {"invocations": 12, "envelope_counts": [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5]}

Mutation probe two, the CLI surfacing silenced with the stamp left intact:

    4 failed, 1 passed in 5.66s
    {"invocations": 5, "real_results": ["advisory", "advisory", "advisory", "advisory", "advisory"]}

## Notes

Every one of the 19 unit-lane failures is owned elsewhere and reproduces without this change: the establishment-ladder regressions are the registration-asymmetry rewrite that landed mid-run and whose own tests still encode the superseded ruling; the descendiente help and payload parity families, the CLI module-size ceiling, and a transient collection break from a syntax error in an uncommitted parser file belong to other lanes. The parser break was waited out rather than touched, and the provenance parity gates it had masked pass once it cleared — those two DID need this change, because they mirror the provenance envelope whole and the new field had to reach the payload.

The locale parity and honesty gates are red on 17 missing keys, 60 extras and 40-plus key echoes, none of which is this row's key; the scaffold drift check reports it clean.

The broad CLI integration lane exceeds ten minutes on this host and was narrowed to the owned surface plus the two envelope conformance gates rather than left unrun.

A peer's bare commit swept every source file and all four catalogues of this change into HEAD before it could be committed under its own pathspec. Nothing was lost and nothing of the peer's was taken, but the change is not attributable to a commit of its own.
