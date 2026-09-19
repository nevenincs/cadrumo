---
tags:
  - '#audit'
  - '#cadrumo-product-rename'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:066ccd8433f30af4fcc46db4797834f103f597c2fdb208bc2ecc1b174e5e39dc'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-14-cadrumo-product-rename-s76-residue-audit]]"
---

# `cadrumo-product-rename` audit: `W06.P15.S81 formal code review of the product-rename change set`

## Scope

The mandatory vaultspec formal code review (plan step `W06.P15.S81`) of the
`cadrumo-product-rename` change set for issue #476, performed at HEAD by an
independent read-only reviewer with no implementer context, against four axes:
safety (no data-stranding, no live-write surface), intent (the
`cadrumo-product-authority-names` naming law applied by ownership/referent),
architecture (zero shims or legacy-compatibility surfaces), and quality
(residue completeness against the S76 residue audit). The reviewer verified
claims independently — including live-artifact runs of the installed CLI —
rather than trusting the campaign's self-audit trail.

**Verdict: PASS.** No critical or high finding open at HEAD; one medium
finding is known, deferred, and correctly tracked (below).

## Findings

### identity-authority-sound | low | Verified sound: single runtime identity authority matches the binding decision

`src/cadrumo/core/product_identity.py` is the one runtime authority
(`PRODUCT_IDENTITY`: display `CADRUMO`, prose `Cadrumo`, package `cadrumo`,
CLI executable `aeat`, MCP executable `cadrumo-mcp`, env prefix `CADRUMO_`,
authority short name `AEAT`), matching the accepted casing/executable
decision exactly. Live-artifact proof: `uv run --no-sync aeat --version`
prints `CADRUMO 0.2.1`, and the Spanish `--help` surface uses
`CADRUMO`/`AEAT`/`CADRUMO_*` and `aeat <comando>` guidance correctly.

### packaging-and-scripts-sound | low | Verified sound: three distributions and exactly two console scripts

`pyproject.toml` names `cadrumo`; the companion packaging trees name
`cadrumo-data-manuals` and `cadrumo-data-official`. `[project.scripts]`
declares exactly `aeat` and `cadrumo-mcp` — no second human alias, no stray
former-name residue in README, RELEASING, or pyproject.

### no-shim-regression-guard | low | Verified sound: anti-shim regression is real, not tautological

`src/cadrumo/tests/test_console_script_imports.py` asserts in a real
subprocess that `import aeat` fails and no former-name package directory
exists. No compatibility shim, alias module, or deprecated re-export was
introduced anywhere in the rename.

### authority-referent-law | low | Verified sound: AEAT retained by referent, product renamed by ownership

Sampled `Aeat*` classes (`AeatSession`, `AeatLoginAssertion`,
`AeatCorpusDriftError`) all name genuine AEAT-portal/authority concepts. MCP,
plugin, and marketplace manifests carry product identity as
`cadrumo`/`Cadrumo`/`CADRUMO` with lowercase `aeat` only as the CLI surface.
The registry taxonomy, official corpus paths, and the AEAT drift-detector
workflow correctly retain the authority name. Storage crypto
domain-separation tags (e.g. the encrypted-column AAD strings) were correctly
left untouched — they never encoded product identity, so no encrypted data is
stranded.

### adr-authority-graph-coherent | low | Verified sound: the casing-authority reconciliation commit is intentional

The apparent revert restoring `status: accepted` on the Stage-A release ADR
(commit `03cd792be3`) was independently reviewed by the campaign's
authority-lock audit and reflects a deliberate non-overlapping-scope design
between the two governing ADRs, with the stale Stage-B content explicitly
voided by a status note. Coherent at HEAD; not a defect.

### aeat-settings-mixin-residue | medium | Deferred and tracked: `Aeat*Settings` mixin chain carries majority-app-owned fields

`AeatTimeoutSettings` / `AeatRuntimeSettings` / `AeatIntegrationSettings`
(`src/cadrumo/core/_config_timeouts.py`, `_config_runtime_fields.py`,
`_config_integration_fields.py`, inherited by `Settings` in
`core/config.py`) mix AEAT-scoped fields with fields that have no AEAT
relationship (LLM endpoints, file-lock timeouts, log rotation); per the
naming law a majority-app-owned class should not carry the `Aeat*` prefix.
Already recorded as finding S76-4 of the residue audit and deliberately
deferred because `core/config.py` carries live uncommitted peer WIP — an
atomic rename commit would risk bundling the foreign hunk. The reviewer
concurs with the deferral. Remediation: a follow-up rename Step once the
peer edit lands.

## Recommendations

Treat S81 as cleared with verdict PASS. The single medium finding is a
tracked deferral, not a blocker, so S82 resolves with zero
immediately-actionable findings and the deferral rationale recorded; S83's
re-run obligation is correspondingly scoped to gates affected by remediation
(none). The remaining open steps are the external operator-owned release
gates (S61 Trusted Publisher confirmation, S85 issue closure) plus the S84
shared-worktree delivery audit. Schedule the `Aeat*Settings` mixin rename as
a follow-up Step gated on the peer edit to `core/config.py` landing.
