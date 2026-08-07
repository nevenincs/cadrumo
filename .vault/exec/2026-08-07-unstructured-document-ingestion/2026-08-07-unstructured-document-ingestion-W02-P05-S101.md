---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:2fdecb312a87a9fb9fe0c3d41bb5a353964dc23a923bae9517c85c7e2b9a500d'
step_id: 'S101'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Probe the semantic index for the bundled-corpus reference and validation mechanism before editing.
- Re-derive the bundled LIVA article inventory rather than trusting the dispatched premise.
- Resolve the place-of-supply articles against the consolidated law and its extracted sidecar.
- Run the evidence gate over the three place-of-supply legal entries.
- Prove each `required_text` phrase discriminates its own article from its neighbours.
- Diagnose the tree-wide registry validation failure surfaced by the gate run.

## Outcome

**No corpus fetch was required, and no file was changed. The dispatched premise was
false.**

LIVA arts. 68, 69 and 70 are already bundled and already grounded:

- The consolidated law `ley-37-1992.html` carries all three, and its extracted
  sidecar exposes them as anchored units `#a68`, `#a69`, `#a70` with the correct
  place-of-supply titles (entregas de bienes; prestaciones de servicios, reglas
  generales; prestaciones de servicios, reglas especiales).
- Legal catalogue entries `ley-37-1992:art-68`, `:art-69` and `:art-70` already
  exist, already carry `required_text`, and already point at those anchors.

The premise arose from an inventory that counted only per-article extract files
(`ley-37-1992-art-NN.html`). The catalogue uses two citation shapes: per-article
extracts, and anchors into the whole consolidated law. Arts. 68, 69 and 70 use
the second shape, which is the shape the grounding rule prefers over
hand-authoring a duplicate excerpt.

Version currency: the bundled consolidated text stamps "última actualización
publicada el 28/02/2026". Last amending norm per article - art. 68, Ley 31/2022
art. 76.1; art. 69, Ley 28/2014 art. 1.12 and 1.13; art. 70, Ley 13/2023
disposición final 1.2.1. The 2010 VAT Package is reflected: art. 69.Uno.1º
localises a B2B service at the customer's establishment, which agrees with the
already-bundled art. 84.Uno.2º.a) reverse charge for non-established suppliers.
No discrepancy to report.

The `required_text` check is not tautological here: the sidecar's declared source
digest equals the SHA-256 of the fetched payload, so the validated text is
mechanically extracted from the authority rather than author prose.

## Verification

Evidence gate over the three entries, run in-process against the bundled root:

    verify_legal_catalogue({art-68, art-69, art-70}, source_root=bundled_path())
    EVIDENCE GATE: PASS -> ['ley-37-1992:art-68', 'ley-37-1992:art-69', 'ley-37-1992:art-70']

Discrimination matrix - each phrase tested against all three article units, so an
`OK` verdict means the phrase matched its own article and neither neighbour:

    [OK] art-68 own=a68 matches=['a68']  "Artículo 68. Lugar de realización de las entregas de bienes."
    [OK] art-68 own=a68 matches=['a68']  "El lugar de realización de las entregas de bienes"
    [OK] art-69 own=a69 matches=['a69']  "Lugar de realización de las prestaciones de servicios. Reglas generales"
    [OK] art-69 own=a69 matches=['a69']  "Cuando el destinatario sea un empresario o profesional que actúe como tal"
    [OK] art-70 own=a70 matches=['a70']  "Lugar de realización de las prestaciones de servicios. Reglas especiales"
    [OK] art-70 own=a70 matches=['a70']  "Los relacionados con bienes inmuebles que radiquen en el citado territorio"
    ALL PHRASES UNIQUELY DISCRIMINATING: True

Anti-tautology binding of the validated text to the fetched authority:

    sidecar source_sha256 : 58f98b80ca2b01fda4a8c3e5dff1f7e61e6c91b2902ae4b7723317f247a71a69
    actual  html   sha256 : 58f98b80ca2b01fda4a8c3e5dff1f7e61e6c91b2902ae4b7723317f247a71a69
    MATCH: True

Registry suite, unit lane, serial, cache provider disabled:

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/ -n0 -p no:cacheprovider -q -m unit -k "legal or catalogue or normative or corpus"
    97 failed, 305 passed, 3362 deselected, 8 errors in 208.82s (0:03:28)

Those 97 failures and 8 errors are a pre-existing baseline, not this Step's: no
file was modified here, and the corpus surface was clean throughout. Every one of
them reduces to a single root signature, recorded below.

## Notes

**Tree-wide registry break, owned elsewhere, blocking the whole registry gate.**
All 97 failures and 8 errors collapse to one cause:

    legal reference 'ley-37-1992:art-94' corpus text missing required text
    '20 bis, 21, 22, 23, 24 y 25 de esta Ley'

The mechanism is a stale extraction sidecar. The per-article payload
`ley-37-1992-art-94.html` was refreshed from live BOE and does contain the phrase,
and the entry's `required_text` was updated to match, but the accompanying
`.extracted.json` was not regenerated. The gate reads the sidecar, not the HTML,
so it still sees the pre-refresh text. The sidecar proves its own staleness: its
declared `source_sha256` (7aeb7cf6...) does not equal the SHA-256 of the HTML
beside it (0104bf5d...). The same article resolves correctly through the
consolidated law's anchor, which contains the current phrase.

Left unfixed deliberately: it is outside this Step's scope and it is a
filing-grade legal surface, so it needs its own owner. Two candidate repairs -
regenerate the sidecar, or repoint `corpus_ref` at the consolidated anchor, which
is the shape arts. 68, 69 and 70 already use.

**Gap worth a row:** nothing enforces that an extraction sidecar's declared
`source_sha256` matches the payload beside it. That single comparison would have
caught this at the commit that introduced it, and it is the same check that
guarantees the anti-tautology property relied on above.

**Instrument warnings, both hit and both false alarms.** A first pass reported
zero occurrences of every LIVA article including bundled ones, and mangled
accented output. Neither was corpus damage: the regex used `\W*` where the
character was `í` (a word character), and the mangling was stdout encoding. Read
these files through Python with an explicit UTF-8 decode, and re-read through a
second instrument before believing a surprising result.
