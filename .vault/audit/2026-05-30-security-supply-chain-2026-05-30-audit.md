---
tags:
  - '#audit'
  - '#security-supply-chain-2026-05-30'
date: '2026-05-30'
modified: '2026-05-30'
related: []
---



# `security-supply-chain-2026-05-30` audit: dependency and supply-chain posture

## Scope

Read-only review of AEAT dependency declarations, lockfile sources, custom
indexes, CI workflows, and developer-tool pinning. Inputs: `pyproject.toml`,
`uv.lock`, `.github/workflows/*.yml`. No `.pre-commit-config.yaml` exists at
the repo root (prek is disarmed per project memory). Goal: surface
known-CVE installs, unsigned or non-default indexes, loose version pins,
unpinned GitHub Actions, and secrets-exposure risks. No mutating commands
were run; venv state untouched.

## Findings

### F1 — All runtime dependencies use lower-bound-only constraints (MEDIUM)

`pyproject.toml:20-87`. Every runtime dependency is declared with `>=X`
and no upper cap (anthropic, cryptography, sqlalchemy, pydantic, torch,
typer, httpx, playwright, formulas, pikepdf, pypdfium2, openpyxl, etc.).
A future major release of any of these (e.g. pydantic 3.x, sqlalchemy
3.x, cryptography breaking key APIs) will be silently selected by
`uv sync` on a fresh clone or `uv lock --upgrade`. For a tax-filing app
processing PII and crypto keys, that is a wide blast radius for
silently-introduced behaviour changes. Risk: supply-chain instability,
not exploitation. `uv.lock` blunts the immediate exposure, but anyone
running `uv sync --refresh` or building outside the lockfile (Docker
images, CI fallbacks) inherits unbounded version selection.

Remediation: cap each runtime dep at the next major (`pydantic>=2.12.5,<3`,
`sqlalchemy>=2.0.36,<3`, `cryptography>=47.0.0,<48`, etc.). Keep lower
bounds aligned with current usage. Re-cap on each verified major upgrade.

### F2 — Dev-tool pins equally unbounded; lint/type/security stack drifts on rebuild (MEDIUM)

`pyproject.toml:134-184`. `ruff>=0.15.12`, `ty>=0.0.1a1`, `pyright>=1.1.409`,
`semgrep>=1.85.0`, `pytest>=9.0.3`, `pytest-xdist>=3.6.0`, `prek>=0.2.0`.
`ty>=0.0.1a1` is alpha; any future alpha bump can change emitted
diagnostics and shift the CI gate. Lint/type drift is not a direct
exploitation risk but materially degrades the security gates' stability
(semgrep rule semantics change between minors; ruff's `S` rules evolve).

Remediation: cap dev tools at the next minor (`ruff>=0.15.12,<0.16`,
`semgrep>=1.85.0,<2`, `ty<0.1`). Pin `pyright` and `pytest-xdist`
similarly. Lock the dev gate to the version range that was demonstrated
to pass review.

### F3 — `tree-sitter-language-pack<1.6.3` override is unbounded below (LOW)

`pyproject.toml:121-123`. `override-dependencies` declares
`tree-sitter-language-pack<1.6.3` to dodge a missing-cp313-wheel issue,
but specifies no floor. A transitive resolver collapse to a very old
pre-1.x release would silently downgrade the language pack and any
parsers built on it (vaultspec-rag indexer). Risk: parser-regression
denial of service against the dev tool, not the production app.

Remediation: tighten to `>=1.5,<1.6.3` (or whatever the current floor
is). Drop the override once the upstream cp313 wheel is published.

### F4 — `torch>=2.4` runtime dep is over-broad and routed through a non-PyPI index on linux/win32 (LOW-MEDIUM)

`pyproject.toml:80, 125-133`. `torch>=2.4` resolves on linux/win32 from
`https://download.pytorch.org/whl/cu130` (an official Astral / PyTorch
index; HTTPS; `explicit = true`, so it cannot leak to unrelated
packages). The index itself is trustworthy. Risk surface: (a) the
unbounded major opens torch 3.x to be selected silently; (b) `torch` is
only declared because transformers can fall back to a CPU path
(`deptry.ignore_unused`), which means a multi-GB wheel ships into every
install for an unused feature. That's a large attack surface (native
code, CUDA runtime) for a feature the production app does not actively
exercise. Confirmed via `tool.deptry.ignore_unused = ["torch", ...]`.

Remediation: either remove `torch` from `[project.dependencies]` and
move to `[project.optional-dependencies]` (e.g. an `llm-local` extra),
or cap `torch>=2.4,<3`. The current shape ships GPU+CUDA wheels by
default to every operator.

### F5 — GitHub Actions pinned to floating major tags, not commit SHAs (MEDIUM)

`.github/workflows/ci.yml:37,43,49,97`,
`.github/workflows/l1-anchor-drift.yml:26,27,38`,
`.github/workflows/aeat-drift-detector.yml:43,46,49,79,86`.
All third-party actions are pinned by tag: `actions/checkout@v4`,
`astral-sh/setup-uv@v5`, `actions/cache@v4`, `actions/upload-artifact@v4`,
`actions/github-script@v7`, `taiki-e/install-action@just`. Tag-pinning
means the action's owner (or an attacker who compromises that owner's
GitHub account) can repoint `v4` to a malicious commit and execute it
in the next workflow run with `contents: read` and, on the drift
detector, `issues: write` + access to AEAT cl@ve-movil identity
secrets. GitHub's official supply-chain guidance is to pin by 40-char
commit SHA with the tag in a comment.

Remediation: replace each `uses: org/action@v4` with
`uses: org/action@<40-char-sha>  # v4.1.7`. Renovate or Dependabot can
keep SHAs current. Highest priority on the drift detector, which has
access to the cl@ve-movil identity secrets.

### F6 — Drift workflow runs uv sync against floating deps on every scheduled run (MEDIUM)

`.github/workflows/aeat-drift-detector.yml:55-60`. The bootstrap step
runs `uv sync` (no `--frozen`), then `uv run vaultspec-core install
--force`, then `uv run playwright install --with-deps chromium` inside
a workflow that holds AEAT identity secrets. Any compromise of a
transitive dep between scheduled runs would execute attacker code with
the cl@ve-movil credentials present in env. The `l1-anchor-drift.yml`
workflow correctly uses `uv sync --frozen` (line 31); the AEAT drift
detector does not.

Remediation: switch to `uv sync --frozen` in `aeat-drift-detector.yml`.
Force lockfile bumps to land in a reviewed commit, not at scheduled
runtime.

### F7 — Pre-commit hook ecosystem disabled; no signature verification on developer machines (LOW)

`prek>=0.2.0` is declared as a dev dep but per user memory
("prek_disarmed", "Never destructive git in shared worktree") prek is
permanently off. Project policy is acknowledged; the supply-chain
consequence is that no hook layer verifies dependency hashes,
signatures, or banned-imports on developer commits. The CI workflow
(`just hooks`) is the only enforcement surface; a developer-machine
compromise would land unchecked. Risk is bounded by the CI gate but
the gate cannot detect a malicious commit that disables itself before
it runs.

Remediation: out of scope for this audit, but acknowledged as a known
trade-off. If reinstated, configure `prek` with hash-pinned hook revs.

### F8 — Custom PyPI index uses a global mirror without hash verification gate (LOW)

`pyproject.toml:125-133`, `uv.lock:56`. The PyTorch CUDA wheel is fetched
from `https://download.pytorch.org/whl/cu130`. uv records the package
hash in `uv.lock`, which is the supply-chain control; this is fine as
long as the lockfile is always used. Risk is bounded as long as `uv sync
--frozen` is used in CI and Docker; otherwise the index could be
hijacked at the TLS layer (PyTorch CDN compromise is the realistic
threat). No remediation required given lockfile coverage; called out
for completeness.

### F9 — `pytest-rerunfailures` and `time-machine` carry no audit floor (LOW)

`pyproject.toml:152,161`. These are test-only deps but
`pytest-rerunfailures` ships as a pytest plugin that auto-loads on every
`pytest` invocation. A future major could change rerun semantics and
mask flaky-test bugs (which is itself a security signal: flaky security
gates are weaker security gates). `time-machine` patches the C clock and
is loaded as a plugin too; a malicious release would affect every test
run.

Remediation: cap both at the next major. Audit plugin auto-load behaviour
on each upgrade.

### F10 — No SBOM, no `uv pip audit` / `pip-audit` step in CI (LOW)

`.github/workflows/ci.yml` does not run any dependency vulnerability
scanner. Semgrep is invoked against source code, not dependency
manifests. There is no `cyclonedx`/SBOM generation step. This means a
known CVE landing in a transitive dep (e.g. cryptography, pikepdf,
pdfplumber, anthropic) would not be surfaced until someone manually
runs an audit.

Remediation: add a `uv run --no-sync pip-audit -r <export>` step (or
`uv tool run pip-audit`) to the CI job, fail-soft initially, then
fail-hard once the baseline is clean.

## Recommendations

- Highest impact, lowest cost: pin GitHub Actions to commit SHAs (F5)
  and switch the AEAT drift detector to `uv sync --frozen` (F6). These
  protect the workflows that hold cl@ve-movil identity secrets.
- Medium-term: cap all runtime + dev deps at the next major (F1, F2,
  F4, F9). The lockfile defends new clones; the caps defend
  `uv lock --upgrade` runs and external rebuilds.
- Low-cost hygiene: add `pip-audit` to CI (F10), move `torch` to an
  optional extra (F4), and tighten the tree-sitter override (F3).

## Summary

Total findings: 10.
HIGH: 0.
MEDIUM: 5 (F1, F2, F5, F6, plus the upper half of F4).
LOW: 5 (F3, F7, F8, F9, F10).

No active CVE-bearing pin observed in `uv.lock` against current
runtime deps within the scope of file inspection (no live `pip-audit`
run was permitted under the no-mutation rule). Most concerning
finding: F5 (GitHub Actions tag-pinning) combined with F6 (unfrozen
`uv sync` in the secret-bearing drift workflow) — together they form a
realistic supply-chain attack path against AEAT identity credentials.
