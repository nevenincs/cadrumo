---
tags:
  - "#exec"
  - "#aeat-access-gate"
date: 2026-04-17
modified: '2026-04-17'
title: "Code Review Record: Live AEAT Access Blocker & Verification Gate (#167)"
related:
  - "[[2026-04-17-aeat-access-gate-plan]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-17-aeat-access-gate-phase1-summary-exec]]"
---

# Code Review Record: Live AEAT Access Blocker & Verification Gate (#167)

## Round 1 — Findings

The vaultspec-code-reviewer persona audited the PR across ten
dimensions. Summary:

- **R1-R6 write-gate compliance** — PASS.
- **Credential / secret discipline** — PASS.
- **Public API discipline** — **FAIL (Block-A)**. `browser/session.py`
  imported `build_client_certificates_kwarg` directly from
  `aeat.adapters.outbound.aeat.auth._certificate_backends._playwright_context`, crossing
  a subpackage boundary into a private module.
- **Type safety** — PASS. Zero new `# type: ignore` that mask bugs.
- **Test posture** — PASS. `@pytest.mark.unit` / `@pytest.mark.live`
  only; zero mocks / patches / `unittest.mock` / `pytest_mock`.
- **Pydantic v2 strict** — PASS. Every new record declares
  `ConfigDict(strict=True, frozen=True, extra="forbid")`.
- **No new env vars** — PASS. `AEAT_SESSION_IDLE_TTL` is a code
  constant.
- **Protocol vs concrete** — PASS. `BrowserSessionFactory` correctly
  declared as a callable Protocol.
- **NIF parser** — PASS. DNI / NIE accepted, CIF rejected, `IDCES-`
  prefix stripped, CN fallback works.
- **Vaultspec compliance** — PASS. Frontmatter and wiki-links clean.

Also recorded three Block-B / Block-C nits (`test_access_gate_is_frozen`
had an inert `object.__setattr__` scaffolding line; the
`test_authenticate_returns_session_and_tags_context` name over-promised
versus what it exercised; `started_ns` variable name was
misleading since it held seconds not nanoseconds).

## Round 2 — Remediation

- **A1 fixed**: `build_client_certificates_kwarg` is now re-exported
  from `aeat.adapters.outbound.aeat.auth.__init__` and `browser/session.py` imports it
  through the subpackage root (`from aeat.adapters.outbound.aeat.auth import
  build_client_certificates_kwarg`).
- **B1 fixed**: removed the inert scaffolding line from
  `test_access_gate_is_frozen`.
- **B2 fixed**: renamed and rewrote the authenticator test
  (`test_authenticator_synchronous_surface`) to reflect what it
  actually asserts — that the synchronous helpers work under the
  async context manager without requiring network access. Full
  `authenticate()` flow remains covered by the live test.
- **B3 fixed**: renamed `started_ns` → `start_seconds` in
  `AeatAuthenticator.verify_login()`.
- Block-C nits (docstring wording around `profile` duck-typing,
  cosmetic logic flow in `check_live_access_gate`) left as-is;
  they do not affect correctness and are documented here.

## Final verification

```
uv run --active ruff check src/aeat/             → All checks passed!
uv run --active just typecheck                   → All checks passed!
uv run --active pytest -m unit                   → 1183 passed, 1 skipped
```

Live tests skip by default per `pyproject.toml` `addopts = "-v --tb=short -m 'not live'"`.

## Sign-off

Round-2 pass is APPROVED. The ten dimensions all pass after
remediation; the nine-point write gate is byte-identical; the new
public surface (`AeatAuthenticator`, `AeatSession`,
`AeatLoginAssertion`, `AeatAccessGate`, `AeatGateEnvSnapshot`,
`extract_nif_from_subject`, four new errors) is cohesively re-
exported from `aeat.adapters.outbound.aeat.auth` with no private-module leakage.
