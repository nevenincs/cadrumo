# Renta WEB Open replay payloads

This directory holds JSON replay payloads captured from AEAT's
Renta WEB Open simulator at
`https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul`.

Each file is named after the scenario it grounds:
`{scenario_id}.json`. The contents are loaded by
`RentaWebOpenReplayDriver` (see
`src/aeat/domain/calculations/registry/_renta_web_open_oracle.py`)
and consumed by `RentaWebOpenOracle.verify_payload` to compare the
registry's computed casilla values against AEAT's open-simulator
output for the same synthetic inputs.

## Schema

```json
{
  "observed": {
    "0432": "30000.00",
    "0435": "25000.00",
    "0500": "30000.00"
  },
  "raw_evidence_locator": "playwright-traces/renta-web-open-2026-05-08-...zip"
}
```

`observed` is a flat string→string mapping of casilla number to
the value the simulator returned. `raw_evidence_locator` points to
the captured Playwright trace evidence.

## Capture procedure

Capture is a live operation; it requires `AEAT_LIVE_TESTS_ENABLED=1`
plus a Playwright runtime with network access to AEAT. Use the live
capture entry point in
`src/aeat/adapters/outbound/aeat/sede/_renta_web_open.py`
(`collect_renta_web_open_observation`). After capture, copy the
observation into a JSON file named after the scenario id and commit
both the payload and the Playwright trace.

## Why this matters

Without these payloads, the registry's chain-behaviour scenarios
verify only registry self-consistency. With these payloads, every
formula's output is independently confirmed by AEAT's own
calculator. This is the grounding mandate the plan's Phase H6
enforces (see `.vault/plan/2026-05-07-renta-full-coverage-plan.md`).
