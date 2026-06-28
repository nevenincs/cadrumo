---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-04-calculation-truth-registry-phase-0c-submitted-file-observation-exec]]'
---



# `calculation-truth-registry` Code Review

PHASE0C-001 | MEDIUM | Submitted-file context fields were parsed but not checked against the declaration row

The first review pass found that `capture_filed_declaration_observation` parsed submitted-file casillas through the registry export layout but did not explicitly compare the submitted payload's modelo, filing year, and period fields to the declaration row before returning observations. That could allow a wrong file context to be normalized if an AEAT row interaction or caller-provided snapshot were inconsistent.

Resolution: `capture_filed_declaration_observation` now verifies submitted-file context fields before emitting observations. A mismatch raises `SedeParseError`. `test_period_mismatch_raises_parse_error` covers this failure path with a registry-rendered submitted file and a mismatched declaration period.

Review status: no open critical, high, medium, or low findings remain for the submitted-file observation slice.

PHASE0C-002 | LOW | Live-captured submitted-file evidence is encrypted and verified

The current submitted-file parser coverage now reads a committed redacted Modelo
130 artefact and exercises registry layout parsing plus declaration-row context
validation. The fixture is static during the test and the test no longer
generates the submitted file through the exporter.

After reauthentication, the live capture command captured one Modelo 130 filing
from AEAT's filed-declaration register. The normalized observation decrypts
through the store API and reports three encrypted artefacts, 19 observed
casillas sourced from `submitted_file`, and submitted-file extraction coverage
of `1.0`.

The capture exposed and resolved a storage-path issue: observation manifests now
use opaque hashed paths instead of embedding modelo, period, or expediente
metadata in directory names.

Review status: no critical, high, or medium findings are open for the secure
storage and submitted-file parser coverage batch.
