---
tags:
  - '#research'
  - '#dependency-provisioning'
date: '2026-07-06'
modified: '2026-07-17'
related: []
---

# `dependency-provisioning` research: `typed dependency probes and workstation doctor grounding`

This research backfills the same-feature grounding for the accepted
`2026-06-15-dependency-provisioning-adr`. It re-read the ADR, searched the vault
and code indexes with `vaultspec-rag`, and confirmed the live provisioning
surface, optional-extra registry, `config check` command, package metadata, and
tests with targeted grep/read slices before recording the bridge.

## Findings

- The accepted decision defines a single missing-dependency contract:
  probe availability, return a typed status or refusal with an exact remediation,
  and surface it through `aeat config check` rather than raw tracebacks or silent
  skips. It also keeps the workstation doctor under the `config` root and keeps
  probes read-only. Source: `2026-06-15-dependency-provisioning-adr`, Problem
  Statement, Constraints, and Implementation.
- The application probe layer implements the typed status shape. `DependencyStatus`
  is a strict, frozen row with `service`, `available`, `detail`, and
  `remediation`. `probe_ollama_vision` performs a short-timeout `/api/tags` read
  and returns `ollama serve` or `ollama pull <model>` remediation; it does not run
  inference. `probe_playwright_browser` uses a filesystem cache check and returns
  `playwright install chromium` when absent. Sources:
  `src/aeat/application/provisioning.py:1`,
  `src/aeat/application/provisioning.py:48`,
  `src/aeat/application/provisioning.py:74`, and
  `src/aeat/application/provisioning.py:169`.
- Subprocess providers and optional Python extras share the same row shape.
  `probe_subprocess_providers` wraps provider CLI availability into
  `DependencyStatus`; `probe_optional_extra` and `probe_optional_extras` enumerate
  the core optional-extra registry and return install hints rather than raising.
  Sources: `src/aeat/application/provisioning.py:119` and
  `src/aeat/application/provisioning.py:200`.
- The optional-extra registry lives in `core`, so adapters can guard lazy imports
  without importing application services. `OPTIONAL_EXTRAS` currently lists the
  Google, browser, and Anthropic extras; `MissingOptionalExtraError` is both an
  AEAT/core error and an `ImportError`, with a concrete install hint. Sources:
  `src/aeat/core/_optional_extras.py:1`,
  `src/aeat/core/_optional_extras.py:69`,
  `src/aeat/core/_optional_extras.py:79`, and
  `src/aeat/core/_optional_extras.py:107`.
- The package metadata mirrors the capability-gated install surface. `pyproject`
  declares `google`, `browser`, and `anthropic` extras and documents graceful
  degradation through `dependency-provisioning`; the dev-only torch placement is
  separately recorded in the dependency-group comments and is not a product core
  dependency. Sources: `pyproject.toml:98`, `pyproject.toml:114`,
  `pyproject.toml:120`, `pyproject.toml:127`, and `pyproject.toml:261`.
- `aeat config check` is the workstation doctor path. It resolves the active
  profile's `ServiceCapability` decisions, gathers Ollama, subprocess provider,
  Playwright, optional-extra, and preflight rows, emits the typed `config.check`
  envelope, and exits with code `2` when an enabled modeled capability has a
  missing dependency. The modeled issue gates currently cover `llm_vision`,
  `cloud_evidence_upload`, and `google_export`; Playwright/browser is reported as
  a dependency row but is not an issue gate because no browser capability exists
  in the current `ServiceCapability` enum. Sources:
  `src/aeat/entrypoints/cli/_config/_check_cli.py:1`,
  `src/aeat/entrypoints/cli/_config/_check_cli.py:24`,
  `src/aeat/entrypoints/cli/_config/_check_cli.py:44`,
  `src/aeat/entrypoints/cli/_config/_check_cli.py:62`, and
  `src/aeat/core/_capabilities.py:37`.
- The JSON payload documents the emitted contract. `ConfigCheckResult` carries
  profile id, `ok`, capability rows, dependency rows, preflight rows, and issues;
  `CheckDependencyPayload` mirrors the `DependencyStatus` shape and names the
  probes that feed it. Source:
  `src/aeat/entrypoints/cli/_config/_check_payloads.py:36` and
  `src/aeat/entrypoints/cli/_config/_check_payloads.py:83`.
- Real-behavior tests cover the non-crashing probe contract. They exercise an
  unreachable Ollama endpoint, missing and present Playwright cache roots,
  subprocess provider status rows, optional-extra status rows, and
  `MissingOptionalExtraError` as an instructive AEAT error caught by the central
  boundary. Sources: `src/aeat/application/tests/test_provisioning.py:31`,
  `src/aeat/application/tests/test_provisioning.py:43`,
  `src/aeat/application/tests/test_provisioning.py:72`,
  `src/aeat/application/tests/test_provisioning.py:102`, and
  `src/aeat/application/tests/test_provisioning.py:113`.
- The packaging preflight protects the dependency surface mechanically. The
  dependency-surface script checks that the optional-extra registry matches the
  project metadata and validates frozen exports before reporting dependency
  counts. Source: `dev/packaging/dependency_surface.py:47`.
- No new ADR or implementation plan is recommended from this bridge. The reviewed
  path matches the accepted ADR's operational boundary: missing dependencies are
  typed rows or typed refusals with remediation, not tracebacks; probes are
  read-only; and the current browser/Playwright row is honestly diagnostic rather
  than capability-blocking because the capability enum has no browser member.
