---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e6b7f493706604f9c55dec0db6142c8b89bb2e0316264d661f680795d089c989'
step_id: 'S09'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Guard the multi-recipient case at the projection consumer so a batch-read record carrying several recipients surfaces rather than silently picking one, gated by a multi-recipient fixture test, inherited requirement from the einvoice batch-reader lane and ## Scope

- `src/cadrumo/application/ledger` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Guard the multi-recipient case at the projection consumer so a batch-read record carrying several recipients surfaces rather than silently picking one, gated by a multi-recipient fixture test, inherited requirement from the einvoice batch-reader lane

## Scope

- `src/cadrumo/application/ledger`

## Description

**This record was reconstructed by audit from evidence at HEAD. It was not authored
by whoever implemented the Step.** The module and its gate landed inside an anonymous
sweep commit with no exec record and the plan row stayed open; a later audit read the
code, re-ran the gate and wrote this.

- Add `src/cadrumo/application/ledger/_aeat_record_projection.py`, the projection
  from one AEAT-declared record onto the single-counterparty ledger shape.
- Return the sole recipient when a record names exactly one, and `None` when it names
  none, which a factura simplificada legitimately does.
- Refuse a record naming more than one recipient, enumerating every party WITH its
  identifier scheme rather than reporting a count, so the operator can see which
  parties the single-counterparty shape cannot hold.
- Gate it against the bundled multi-recipient corpus submission, including a
  fixture-anchor test asserting the document still carries the case under test.

## Outcome

The constraint that only ONE counterparty fits now lives at the projection, which is
where it belongs. The batch reader keeps every recipient a SII or VERI*FACTU record
states, because `IDDestinatario` is `[0..1000]` in the schema and a party set cannot
be split back apart once discarded; the narrowing happens here, loudly.

The gate is anchored rather than synthetic: it parses the bundled submission through
the shipped reader, and a dedicated fixture-anchor test fails if that document stops
carrying two recipients under two identifier schemes — so a corpus change cannot make
the guard pass vacuously.

**Named honestly, because it bears on how much this Step protects today:** the
projection function has no production caller at audit time. Nothing in the tree
outside the module itself, its own gate and the package facade consumes a parsed AEAT
batch record, so no live path yet reaches the guard. That is not a defect in this
Step — there is no silent-collapse site elsewhere, because there is no other
projection — but the guard is a correct constraint waiting for its consumer rather
than one currently exercised end to end.

Introducing commit, established by first-add archaeology: `4a941f78fc`. The
requirement itself was named earlier, by `ebaef1115d`.

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

Run at audit time against HEAD, sequential, cache disabled, default marker lane
(`unit and not external_tool and not os_keychain`). The module is unit-marked, so all
six of its cases execute in that lane; the 185 deselected tests belong to the CLI
conformance module run alongside it:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_aeat_record_projection.py src/cadrumo/entrypoints/cli/tests/test_evidence_provenance_payload_parity.py src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -n0 -p no:cacheprovider -q
    12 passed, 185 deselected in 1.68s

The gate module is `test_aeat_record_projection.py`. The assertion carrying this Step
is `test_the_first_recipient_is_never_returned_silently`, which states the exact
defect as an outcome rather than testing the guard's internals;
`test_several_recipients_refuse_and_name_every_party_with_its_scheme` holds the
refusal to enumerating parties with schemes; and
`test_the_bundled_submission_still_names_two_recipients_under_two_schemes` is the
fixture anchor that keeps the whole module from passing vacuously.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The absence of a production caller is recorded in the Outcome above rather than here,
because it qualifies what the Step delivers rather than describing an incident.
