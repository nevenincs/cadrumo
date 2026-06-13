---
tags:
  - "#research"
  - "#cert-pre-expiry-gate"
date: 2026-04-13
modified: '2026-04-13'
title: "Certificate Pre-Expiry Health Check + Workflow Gate"
related:
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-13-cert-pre-expiry-gate-adr]]"
  - "[[2026-04-13-cert-pre-expiry-gate-plan]]"
---

# Research: Certificate Pre-Expiry Health Check

## Problem

Issue #94: today the project only surfaces a certificate problem *after*
`not_after` has elapsed, via `CertificateExpiredError` raised from
`aeat.adapters.outbound.aeat.auth.certificate.load_certificate`. For a Spanish autónomo whose
FNMT certificate has a 24-month validity and lives on a single
workstation, that means the pipeline keeps working silently until the
day of expiry and then catastrophically fails mid-deadline.

## Evidence in current codebase

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` — `load_certificate` raises
  `CertificateExpiredError` only after expiry; no pre-expiry path.
- `src/aeat/entrypoints/cli/doctor.py` — audits Google Workspace/GCP, never touches
  the AEAT cert.
- `src/aeat/application/workflow/_engine.py` — `RUNNING_PREFLIGHT` stage already
  calls `CertificateBundleProtocol.load()` but never inspects
  `LoadedCertificate.not_after`.
- `src/aeat/entrypoints/cli/submission/submit.py` — live submit gated only by
  `--i-understand-this-is-real`, not by certificate freshness.

## Related surfaces already on main

- `aeat.adapters.outbound.aeat.auth` public API — extendable without touching sibling branches
  (f/95 browser+status, f/93 filing).
- `aeat.application.workflow._engine._stage_running_preflight` — already owns the
  cert-load probe, natural place to bolt on the pre-expiry gate.
- `aeat.entrypoints.cli.doctor.Row` / `State` — already structured; trivial to add a
  cert row.
- `aeat.core.config.Settings` — already carries `aeat_certificate_path`;
  threshold fields slot next to existing cert section.

## Constraints

- Strict pydantic v2 for every record; enum StrEnum for severity.
- Errors inherit from `aeat.core.errors.AeatError`.
- No mocks in tests; synthetic self-signed PKCS#12 generated at runtime
  (existing `test_certificate.py` already shows the pattern).
- Must not touch `aeat.adapters.outbound.aeat.browser`, `aeat.status`, `aeat.application.filing`, or
  `src/aeat/domain/financial/*` (sibling branches in flight).

## Prior art in this repo

- `aeat.domain.deadlines` uses a threshold-driven enum (`ObligationStatus.DUE_SOON`)
  reading `aeat_deadline_due_soon_days` from Settings — the same shape
  applies here with `aeat_cert_warn_days` / `aeat_cert_critical_days`.
- `aeat.adapters.outbound.aeat.auth.test_certificate.py::_build_pkcs12_bundle` already
  generates real PKCS#12 bundles at runtime — reusable for the new
  health tests.
