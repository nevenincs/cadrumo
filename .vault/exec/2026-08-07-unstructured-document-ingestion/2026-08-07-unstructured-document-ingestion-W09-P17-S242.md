---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d9c0b2953e48a516a46348fd67d905d523171080daa2c998645bd0d288f0c6a6'
step_id: 'S242'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Make the counterpart observation's country REQUIRED, removing the default that made an absent country Spanish at the operator boundary.
- Make the Modelo 232 vinculada row's country required, on the same grounds.
- Make the Modelo 184 member row's country OPTIONAL rather than required, because its producer has no country to supply.
- Correct the fixtures that stated no country, and the two that asserted the Spanish default as the contract.
- Add a gate proving the refusal and the readiness consequence behind it.

## Outcome

Three counterparty-facing country fields inferred Spain from silence. The shape is why a search for a fallback found none of them: these are FIELD DEFAULTS rather than or-expressions, so they do not read as a fallback at any call site, and two of the three have no call site at all.

The counterpart observation is the sharpest, because it is an operator boundary — the aggregate command validates each supplied observation directly against it. The Modelo 349 readiness rule asks for a GROI check when the country IS Spain and a NIF-IVA check when it is not, so a row omitting its country was read as domestic and the NIF-IVA verification an intra-community counterparty must pass was never required of it. Modelo 349 is the recapitulativa de operaciones intracomunitarias, where a Spanish counterparty is the one thing the row cannot be.

Refusing is right rather than admitting an absent value, because every consumer branches on the country: an optional field would move the same guess into each of them and the shape of the mistake would survive the fix.

The member row is deliberately treated differently, and the difference is the finding. Its production producer builds from attribution profile facts that carry nif, name, share and base and no territory at all, so requiring a country there would refuse every profile-resolved row while naming a fact no surface records — the refusal-nobody-can-answer shape this campaign has already rejected once. Absence is therefore representable rather than demanded, and the honest fix upstream is to record the socio's country on the profile.

## Verification

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_counterpart_country_is_never_assumed_spanish.py -n0 -q -m unit
    3 passed in 3.83s

    uv run --no-sync pytest src/cadrumo/domain/modelos -n0 -q -m unit
    224 passed in 61.85s (0:01:01)

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests src/cadrumo/entrypoints/cli/tests/test_modelo_aggregate_payload_parity.py -n0 -q -m unit
    860 tests ran; 11 were DESELECTED by -m 'unit' and never executed.
    860 passed, 11 deselected in 77.93s (0:01:17)

The mutation was applied from outside the repository through a pytest plugin. Restoring the default and rebuilding the model: the plugin then LOADED a real observation omitting the country and asserted it came back as Spain before declaring the mutation applied, so the window is proven open rather than announced. The refusal case red; the two cases that state a country stayed green.

## Notes

An upstream gap was found rather than papered over: the attribution profile records no country for a socio, which is why the member row cannot demand one. That is worth its own row.

Two fixtures asserted the Spanish default as the contract. They were corrected rather than worked around; a fixture that encodes a defect is worse than no fixture.

A wide combined run reported twenty-one failures across the modelo suites. None mentioned either field. Sampled files that failed there passed when run alone in the same tree and passed against HEAD, so the failures were cross-suite interference rather than this work. A later run of that directory alone collected almost nothing, and the log showed the cause: a concurrent lane's in-flight module was raising an ImportError during collection. The reading was repeated in three configurations before anything was attributed.

**Coverage of Modelo 232 is PARTIAL, and reads as complete unless this is stated.** The vinculada fichero row's country was made required here; the registry binding observation for the SAME modelo and the same fact was not, and still defaults to Spain. The two are separate paths -- the fichero row does not appear in the row-set assembly at all -- and the assembly leg double-defaults its value, so absence never reaches the model that could refuse it.

That asymmetry is arguably worse than the original state. A reader meeting the required field would reasonably conclude the axis is handled for this modelo, while the path that actually feeds the calculation still infers Spain from silence.

The cause was a process one rather than a search one: the site appeared in this Step's own census output and was set aside on the plan row's framing that the registry defaults are plausibly correct by domain. That framing was carried forward labelled as unverified, and labelling an assumption does not discharge it. A sibling lane afterwards read the class rather than the framing and found it is the related-party observation for Modelo 232, whose declarable population includes foreign related parties and territories classified as paraisos fiscales.
