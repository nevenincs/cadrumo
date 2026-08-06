---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s76-residue'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:295ee9aeae7f3e6d7e901fdbbd4bf914feb0ca62688ba389cc561fce3f1f9fa7'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s76-residue` audit: `S76 aeat token residue classification`

## Scope

A fresh, HEAD-current sweep of every remaining `aeat`/`AEAT`/`Aeat` token across
the repository (source, packaging, CI, docs, frontend), classified by referent
per `cadrumo-product-authority-names`: the sole lawful CLI executable, the
Spanish tax-authority referent, historical/evidentiary artefacts, immutable
corpus paths, or a genuine defect. Targeted patterns checked: a Python import
root of `aeat`, a second human CLI script alias, `Aeat`-prefixed classes,
`AEAT_*` env-var names, `pyproject.toml` package/script identity, Docker/CI
labels, MCP manifest identity, npm package manifests, and top-level repo docs.

## Findings

### S76-1 residual-cli-alias | low | The sole `[project.scripts]` entry named `aeat` is the lawful executable

`pyproject.toml` declares exactly `aeat = "cadrumo.entrypoints.cli:main"` and
the distinct `cadrumo-mcp = "cadrumo.entrypoints.mcp:main"`. No second `aeat`-style
alias or `cadrumo` CLI script exists. This matches the binding
`cadrumo-cli-executable` decision; no action needed.

### S76-2 authority-classes | low | `Aeat`-prefixed classes all name AEAT-authority concepts, none the product

A full-repo sweep of `\bAeat[A-Z][A-Za-z]*\b` in Python source enumerates
`AeatSession`, `AeatLoginAssertion`, `AeatAccessGate`, `AeatCorpusDriftError`,
`AeatOracles`, `AeatSedePaths`, `AeatPortalPaths`, `AeatDomains`,
`AeatHelpPages`, `AeatNifIvaCheckerOracle`, `AeatLiveSafety`,
`AeatGateEnvSnapshot`, and siblings. Each names a concept scoped to the AEAT
portal, its browser sessions, its live-read gate, or its oracle/corpus
fixtures — the tax-authority referent, not the product. No rename action
needed for this class set.

### S76-3 stale-envvar-docstring | low | `AeatTimeoutSettings` docstring cited a wrong (pre-rename) env-var prefix — fixed

`src/cadrumo/core/_config_timeouts.py` carried a stale module docstring
claiming its fields "still read the same ``AEAT_*`` environment variable by
field name," while every field in the class (`cadrumo_browser_navigation_timeout_ms`,
`cadrumo_live_iva_surface_timeout_ms`, etc.) is `cadrumo_*`-prefixed and reads a
`CADRUMO_*` env var — confirmed against `Settings.aeat_base_url`'s docstring,
the one field genuinely reading `AEAT_BASE_URL` (a real authority-scoped field,
correctly still `AEAT_*`). The stale claim was a leftover from before the
rename. Corrected the docstring to `CADRUMO_*` in this pass (no peer WIP on the
file; single-line fix).

### S76-4 settings-mixin-naming | medium | `AeatTimeoutSettings` / `AeatRuntimeSettings` / `AeatIntegrationSettings` mix broad app-owned config under an authority-scoped name — deferred, not fixed this pass

These three base classes (`core/_config_timeouts.py`, `core/_config_runtime_fields.py`,
`core/_config_integration_fields.py`) are inherited in a chain
(`Settings(AeatIntegrationSettings)` ← `AeatRuntimeSettings` ← `AeatTimeoutSettings`)
and hold a mix of genuinely AEAT-scoped fields (AEAT sede browser viewport/locale,
AEAT manuals HTTP timeout, live-IVA surface timeouts) alongside fields with
zero AEAT relationship: LLM provider endpoints (OpenAI, Gemini, Ollama), file-lock
timeouts, log-rotation settings. Per `cadrumo-product-authority-names`, a class
whose fields are majority app-owned should not carry the `Aeat*` prefix; this
reads as a genuine (if cosmetic) defect — the class names should be
`Cadrumo*Settings` or a neutral `*SettingsMixin` name. **Not fixed this pass**:
`src/cadrumo/core/config.py` (the direct consumer, `class Settings(AeatIntegrationSettings)`)
currently carries an unrelated, uncommitted peer edit (a validator error-message
line-wrap) in the shared working tree. Renaming the base classes would require
touching `config.py`'s class-declaration line in the same commit, and a
pathspec commit on that file would bundle the peer's unrelated hunk into this
feature's commit per `subagent-commits-require-explicit-pathspec`. Recorded here
as a residue finding for a follow-up Step once the peer edit lands or via the
apply-cached gated drive.

### S76-5 npm-package-identity | medium | Marketing frontend's npm package name was still `aeat-marketing-frontend` — fixed

`frontend/package.json` and `frontend/package-lock.json` declared
`"name": "aeat-marketing-frontend"` for the CADRUMO marketing site (a product
surface, not an AEAT-authority artefact). No other file referenced this
literal package name. No peer WIP on either file. Fixed both to
`cadrumo-marketing-frontend` in this pass.

### S76-6 frontend-locale-copy | low | Frontend locale copy (en/es/ca) uses `AEAT`/`Cadrumo` correctly throughout

A targeted sweep of `frontend/src/locales/{en,es,ca}.tsx` confirms every `AEAT`
mention is the tax-authority referent (disclaimer text, "not affiliated with
AEAT," "AEAT-compatible*" footnote) and every product mention uses `Cadrumo`.
No defect found.

### S76-7 mcp-manifest-cli-mentions | low | The mcpb manifest's `aeat` mentions name the CLI surface, not the product

`packaging/mcpb/manifest.json` names the product `"cadrumo"` /
`"Cadrumo tax assistant console"` throughout, and its two lower-case `aeat`
mentions ("Search the aeat command surface by keyword," keyword list) refer to
the `aeat` executable surface the MCP tools proxy — the correct referent. No
action needed.

### S76-8 corpus-and-ci-paths | low | Corpus subdirectory names, registry taxonomy, and drift-detector CI workflow all reference the authority correctly

`src/cadrumo/_data/registry/aeat/`, `src/cadrumo/_data/corpus/aeat_official/`,
`packaging/cadrumo_data_official/`, and `.github/workflows/aeat-drift-detector.yml`
all name AEAT the authority (registry taxonomy, official corpus, and a workflow
that detects when AEAT's own portal drifts). These are immutable-corpus /
authority-referent uses per the naming rule; none are defects.

### S76-9 stray-local-state-dir | low | An untracked `.aeat/auth/sessions` directory exists on this dev machine — out of repository scope

A stray, empty, untracked `.aeat/auth/sessions` directory (dated 2026-06-04,
pre-rename) sits at the repository root on this machine. It is not tracked by
git, carries no content, and is local runtime state (an old token-cache
location) rather than a repository defect. Not remediated as part of this
audit; flagged for operator disk hygiene, out of the rename campaign's
repository-scope mandate.

## Recommendations

Two genuine defects were found and fixed in this pass: the stale `AEAT_*`
docstring claim in `_config_timeouts.py`, and the `aeat-marketing-frontend` npm
package identity (now `cadrumo-marketing-frontend` in both `package.json` and
`package-lock.json`). One medium-severity naming residue (S76-4, the
`Aeat*Settings` mixin chain) is recorded for a follow-up Step once
`core/config.py`'s current unrelated peer edit lands, since a clean atomic
rename commit cannot currently be landed without either waiting for the peer
commit or using the apply-cached gated drive. All other `aeat` token
occurrences surveyed classify as the lawful CLI executable, the tax-authority
referent, historical evidence, or immutable corpus — no blanket-replace
candidates found.
