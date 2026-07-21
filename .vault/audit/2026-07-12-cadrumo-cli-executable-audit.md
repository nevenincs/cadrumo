---
tags:
  - '#audit'
  - '#cadrumo-cli-executable'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-07-12-cadrumo-cli-executable-adr]]"
---

# `cadrumo-cli-executable` audit: `runtime-and-documentation-boundary`

## Scope

Reviewed the Cadrumo product / AEAT authority / `aeat` executable repair across
the current console binding, runtime identity, operator-surface ownership
validation, console and documentation conformance tests, and authentication
guide. The review also compared the active executable ADR with the linked
rename plan and reference.

## Findings

### rename-plan-executable-conflict | medium | The active rename plan still requires the rejected Cadrumo command

The accepted `cadrumo-cli-executable` decision makes `aeat` the one human CLI,
but `2026-07-12-cadrumo-product-rename-plan` W03.P05.S24 and its verification
item 2 still require `cadrumo` as the human executable. The implemented
`pyproject.toml` binding and `PRODUCT_IDENTITY.cli_executable` correctly follow
the accepted decision, so a later executor following the plan would restore a
rejected second command or invalidate the real proof. Reconcile the plan before
checking its executable step.

### cli-reference-stale-python-root | low | Documentation tooling still describes the retired Python import root

`dev/docs/cli_reference.py` runs against `cadrumo.entrypoints.cli`, but several
developer-facing docstrings still name `aeat.entrypoints.cli`. The retained
`aeat` token is correct for command examples and the current language setting,
but it is incorrect as a Python-module reference and contradicts the
no-`aeat`-import guarantee. Retarget only those qualified module references to
`cadrumo`.

### remediation-review | low | No actionable findings

The follow-up remediation resolves the earlier plan and documentation-tooling
drift. The rename plan now names `aeat` as the sole human executable and
`cadrumo-mcp` as the distinct MCP command. The CLI-reference generator isolates
the Cadrumo configuration environment and imports the Cadrumo CLI directly.

`_CadrumoDotEnvSettingsSource` excludes only the five former product dotenv
names before strict settings parsing. The focused real-behavior regression proves
that the legacy storage and passphrase names are ignored, `AEAT_AUTH_PROVIDER`
continues to configure the authority, and an unrelated dotenv key still raises a
validation error. The current console declaration has one `aeat` script pointed
directly at Cadrumo, the root CLI tests use Cadrumo settings, and the
authentication guide correctly names `CADRUMO_SECRET_PASSPHRASE` while retaining
AEAT and Censo authority language. Focused verification reported 123 passing
tests; direct `aeat --help` and `import cadrumo` succeed, while `import aeat`
continues to fail.

### prior-findings-resolved | low | The earlier findings are retained as historical evidence

The plan conflict and stale Python-root documentation recorded above were
resolved by the follow-up remediation. The current plan retains `aeat` as the
sole human command and `cadrumo-mcp` as the distinct MCP command; the current
CLI-reference tooling imports Cadrumo directly. The preceding entries remain
as the audit trail, not as outstanding work.

## Recommendations

The settled design retains the direct `aeat = cadrumo.entrypoints.cli:main`
console binding, keeps `cadrumo-mcp` distinct, and does not add an `aeat`
Python package. The final focused real-behavior suite passed 123 tests across
product identity, hard-cut imports, configuration, operator-surface validation,
root CLI help, documentation conformance, and generated CLI-reference
conformance. The live checks also confirmed that `aeat --help` runs and
`import aeat` fails.
