# Renta WEB Open replay payloads

This directory holds JSON replay payloads captured from AEAT's
Renta WEB Open simulator at
`https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul`.

Each file is named after the scenario it grounds:
`{scenario_id}.json`. The contents are loaded by
`RentaWebOpenReplayDriver` (see
`src/cadrumo/domain/calculations/registry/renta_web_open_oracle.py`)
and consumed by `RentaWebOpenOracle.verify_payload` to compare the
registry's computed casilla values against AEAT's open-simulator
output for the same synthetic inputs.

## Schema

```json
{
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
  "raw_evidence_locator": "playwright-traces/renta-web-open-2026-05-08-...zip"
}
```

`expected_by_casilla_id` and `observed_by_casilla_id` are the canonical
registry-keyed comparison surfaces. Their keys must be current `casilla.id`
values from the Modelo 100 registry revision under test. `expected` and
`observed` are legacy human-readable audit evidence only; they are not matcher
inputs and must never replace the canonical casilla-id blocks.
`raw_evidence_locator` points to the captured Playwright trace evidence.

## Capture procedure

Capture is a live operation; it requires `AEAT_LIVE_TESTS_ENABLED=1`
plus a Playwright runtime with network access to AEAT. Use the live
capture entry point in
`src/cadrumo/adapters/outbound/aeat/sede/renta_web_open.py`
(`collect_renta_web_open_observation`). After capture, copy the
observation into a JSON file named after the scenario id and commit
both the payload and the Playwright trace.

## Why this matters

Without these payloads, the registry's chain-behaviour scenarios
verify only registry self-consistency. With these payloads, every
formula's output is independently confirmed by AEAT's own
calculator. An engine value is only externally grounded when a
bundled replay payload carries the expected figure for it.
