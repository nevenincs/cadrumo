# Renta WEB Open replay payloads

Development artefacts. These captures do not ship with Cadrumo and are not
reachable from an installed product; they exist to produce a quality signal
over the registry and nothing else.

This directory holds JSON replay payloads captured from AEAT's Renta WEB Open
simulator at
`https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul`.

Each file is named after the scenario it grounds: `{scenario_id}.json`. The
contents are loaded by `RentaWebOpenReplayDriver` (see
`dev/registry/parity/renta_web_open_oracle.py`) and consumed by
`RentaWebOpenOracle.verify_payload`.

Read what that comparison actually does, because the obvious reading is wrong.
`verify_payload` is handed the expected values taken from the capture's own
`expected_by_casilla_id`, and compares them against the same capture's
`observed_by_casilla_id`. Both sides come out of one file. The replay therefore
proves that a capture is **internally self-consistent** — it does not run the
registry engine, and it never has. No value this repository computes is checked
by this path.

## Coverage

Every capture in this directory is a **2025 Modelo 100** capture. There are no
captures for any other modelo, and none for any other filing year. That is the
whole corpus, and it is a floor on what the replay signal can prove: a clean
replay report says the 2025 Modelo 100 figures below agree with AEAT's
simulator, and says nothing at all about anything else.

## Schema

```json
{
  "scenario_id": "modelo-100-2025-employee-default-minimo-madrid",
  "profile_overrides": {},
  "expected": {
    "Resultado de la declaración": "0.00",
    "Cuota diferencial": "0.00"
  },
  "observed": {
    "Resultado de la declaración": "0,00",
    "Cuota diferencial": "0,00"
  },
  "expected_by_casilla_id": {
    "0610": "0.00",
    "0670": "0.00"
  },
  "observed_by_casilla_id": {
    "0610": "0,00",
    "0670": "0,00"
  },
  "raw_evidence_locator": "https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?EJER=2025&TACCESO=COLAB"
}
```

`expected_by_casilla_id` and `observed_by_casilla_id` are the canonical
registry-keyed comparison surfaces. Their keys must be current `casilla.id`
values from the Modelo 100 registry revision under test. `expected` and
`observed` are human-readable audit evidence only; they are not matcher inputs
and must never replace the canonical casilla-id blocks.

`raw_evidence_locator` names where the figures came from. In every capture
committed here it is the simulator entry URL — the public Renta WEB Open page
for the 2025 exercise — and not a stored artefact. No trace, recording, or
other retained capture evidence exists for these payloads, so the locator is a
provenance statement about the surface, not a pointer to anything a reader can
open and re-examine.

## Capture procedure

**There is none.** The live capture entry point these payloads were produced by
no longer exists anywhere in the repository: there is no
`collect_renta_web_open_observation` function and no
`adapters/outbound/aeat/sede/renta_web_open` module. Nothing in the tree can
drive the simulator and emit a payload in this shape.

These captures are therefore **frozen 2025 artefacts**. They can be replayed,
but they cannot currently be re-derived, re-verified against the live
simulator, corrected, or extended to another filing year or scenario. Adding a
2026 capture, or refreshing one of these after an AEAT simulator change, would
first require building a capture path that does not exist today. Do not treat
the absence of a procedure here as an oversight to be worked around by
hand-authoring a payload: a hand-written file in this directory would carry
AEAT provenance it does not have.

## What this does and does not establish

These payloads hold real AEAT figures, and that is their value: they are an
independent record of what AEAT's own calculator produced for a known synthetic
profile. Keeping them is worthwhile.

What they do **not** currently establish is that this registry agrees with
those figures. Nothing wires the engine to them, so a green replay report is
not evidence of agreement, and the corpus must never be cited as if it were.

The gap is not hypothetical. Driving the registry directly for these same
scenarios yields casilla 0520 (`Minimo personal y familiar. Parte autonomica`)
= 5550.00 for **every** comunidad autonoma, because the 2025 formula resolves
every CCAA key to a single shared parameter. The captures here record 5550.00
for Cataluna but 5606.00 for Canarias, 5789.00 for Galicia and 5956.65 for
Madrid. So the engine and AEAT disagree on three of the four regional captures,
and the replay reported `match` on all five throughout. Whether the registry is
under-modelled or the captures measure something else is unresolved and needs
official AEAT authority to settle; until it is settled, treat casilla 0520 as
NOT externally confirmed.

A capture without an override for `autonomous_community` is a further gap: the
engine refuses to evaluate without that enum, so `modelo-100-2025-employee-
default-minimo.json`, whose `profile_overrides` is null, could not be replayed
against the engine even if the wiring existed. Its territory is undeclared.
