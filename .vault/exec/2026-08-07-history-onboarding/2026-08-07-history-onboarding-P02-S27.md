---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:2648d0871dc7263ee76693db8e44091266c363d8f0c1148b9fcb530e7a963e17'
step_id: 'S27'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
## Description

The register row carries AEAT's own request-type field, the capture path reads it
into the raw observation's metadata, and the persistence boundary then builds its
source metadata from a fixed key set that does not include it. So the one signal
that could distinguish an original filing from an amendment is discarded before
any selection logic could read it -- and no selection logic reads it today.

This Step pins that loss rather than repairing it. A separate row already owns
carrying the field through, and which identifier an amendment-aware election
should key on is not settled; a half-fix landed here would be worse than a
visible gap.

## Outcome

Added `test_persisted_source_metadata_drops_the_register_request_type_signal` to
`src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.

The observation is Modelo 130, not Modelo 303. That is deliberate: the fact is
modelo-agnostic, and a 303 observation additionally drives the IVA compensation
wallet on the way to persistence, so a failure there would be indistinguishable
here from the metadata behaviour under test. Modelo 130 exercises the persistence
boundary on its own.

The test asserts in order: the raw observation DOES carry the signal (otherwise
the absence below proves nothing), the persisted metadata was built at all (the
expediente key is present), the request-type key is absent, and the request-type
VALUE is absent from every other key -- so a rename cannot make the test pass
vacuously.

Its docstring states the reversal condition explicitly.

## Verification

The test passes. Proven to bite by a runtime mutation that makes the metadata
builder carry the request type through -- exactly the pending change. The test
reds on `assert 'tipo_solicitud' not in {...}` with the added key visible in the
failure output.

## Notes

An earlier draft of this test used a Modelo 303 observation and could not run: the
IVA compensation history path reads a field the derivation dataclass does not
declare, raising `AttributeError`. That defect is pre-existing at HEAD, lives in
files this Step did not touch, and already reds thirteen long-standing tests in
the same module. It was not patched here. Re-targeting to Modelo 130 both avoids
it and makes the test a better instrument, since the boundary under test is
reached with nothing else attached.

The Modelo 130 observation builder is the one the sibling provenance-parity work
introduced, reused rather than duplicated.
