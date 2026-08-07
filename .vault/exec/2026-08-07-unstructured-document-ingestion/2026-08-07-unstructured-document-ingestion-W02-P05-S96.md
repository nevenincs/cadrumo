---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:7de010a8a572dc497d503a2487f5a861aa21bad7f5a5a750502e9632c367cbf6'
step_id: 'S96'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Prove the reading path on non-Spanish invoices by extending the bundled corpus fixtures to at least one intra-community invoice whose labels and regime legend are printed in another official EU language, asserting the reader recovers base, cuota, both parties and the legend without any Spanish label appearing on the document, so the field contract is shown to be language-independent rather than assumed to be

## Scope

- `src/cadrumo/application/ledger/tests`

## Description

The bundled corpus held a Hungarian-language adversarial PDF, but its only
assertion was that text extraction yielded some content. No fixture anywhere was
printed in a language other than Spanish AND read for its fields, so the claim
that the field contract is language-independent rested on the reader design
rather than on an observation.

- Add an EN16931 UBL intra-community invoice to the bundled corpus: a Swedish
  supplier billing a Spanish recipient in Swedish kronor, with the item
  description and the statutory mention in German, and a provenance sidecar
  declaring it synthetic with the reason it was authored.
- Carry the printed statutory mention through the structured readers, which
  dropped it entirely: it reached the operator only from the reading model, so
  the one path that recovers it EXACTLY was the one that lost it.
- Read the mention from the document-level note in UBL and CII and from the
  legal-literals block in Facturae, as free text in the document's own language
  rather than matched against a list of Spanish phrases.
- Add a gate asserting the reader recovers base, cuota, both parties and the
  legend off that document.
- Add a control asserting the fixture prints no Spanish label, so the
  language-independence claim cannot quietly stop being true.

## Outcome

The multi-region, multi-language, multi-currency case from the standing goal now
exists as a real document in the corpus and is read end to end. The proof runs
on the structured reader, which reaches no model at all, so the recovery is
exact and the assertions are about the reader rather than about a model's mood.

The legend is the recovery that matters most. An intra-community supply prints a
base and no cuota, which is exactly what an exempt and a zero-rated supply also
print. Strip the mention and the record is indistinguishable from an ordinary
zero-cuota sale, and the recipient's self-assessed IVA is never assessed.

## Verification

Cache posture: `-p no:cacheprovider`, serial `-n0`, marker expression stated.

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_fx_conversion_provenance.py src/cadrumo/application/ledger/tests/test_evidence_foreign_currency_and_language.py -n0 -p no:cacheprovider -m "unit or integration"
    collected 12 items
    12 passed in 10.01s

The structured-reader and CLI conformance surfaces, which the legend carry and
the new confirm option both cross:

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py src/cadrumo/tests/test_fx_stamp_singularity.py src/cadrumo/adapters/inbound/einvoice src/cadrumo/application/aggregation/tests/test_fx_conversion.py -n0 -p no:cacheprovider -q -m "unit or integration"
    544 passed in 110.26s

Mutation proof, applied from outside the repository to the imported module
object; nothing under `src` was edited.

    [MUTATION LANDED] drop_legend_carry: the structured reader drops regime_legend, as it did before this change
    1 failed, 11 passed in 26.33s

The red came from the property under test, not from fixture setup:

    E   AssertionError: the statutory mention the document prints did not survive the structured read
    E   assert None == 'Steuerfreie innergemeinschaftliche Lieferung'

## Notes

The Step row asks for a document whose LABELS print in another EU language. A
structured e-invoice has no labels: its field names are namespaced XML tags,
language-neutral by construction. What this fixture does carry in German is
every piece of free text an issuer writes, the statutory mention and the item
description. So the structured path is language-independent by construction
rather than by evidence, and what this Step proves is the free-text recovery,
which is the part that can actually fail.

The path where language genuinely bites is the text-layer reader, which turns
printed labels into fields. It could not be exercised: it requires an on-host
reading model, none runs in this environment, and the campaign brief bars
loading one. Its language independence remains unproven and is named here rather
than implied.

Confirming ANY intra-community invoice was impossible through the evidence path
before this Step, in any language: the invoice writer refuses a supply that does
not state its Modelo 349 clave, and the confirm boundary offered no way to
supply one. That was fixed here because it blocked the Step outright, with the
CLI option and its help string set in all four locale catalogues.

A recargo de equivalencia document currently raises a spurious arithmetic
closure blocker on the text-layer path. It is known, owned elsewhere, and no
fixture here depends on it.
