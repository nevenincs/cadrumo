---
tags:
  - '#adr'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-10-21'
body_hash: 'sha256:097a8fa1ffbdb1f3eb536a2f512a8fda96f512f5e833542cf5f336195b1348eb'
related:
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-03-claude-ecosystem-packaging-code-review-audit]]'
---
# `claude-ecosystem-packaging` adr: `Python distribution packaging: wheel split, storage root and integrity boundary` | (**status:** `accepted`)

## Amendment 2026-10-21: plugin delivery withdrawn

By operator instruction on 2026-10-21, the Claude Code plugin capability is withdrawn. This record no longer rules on any plugin bundle, plugin manifest, marketplace, plugin install gate or plugin-vehicle bootstrap. What remains is the Python distribution packaging: the three-distribution wheel split, the installed-run storage default, the resource-resolution seam, the integrity boundary, the no-install-time-fetch constraint and the data budget. The MCP harness, its server entrypoint `cadrumo-mcp` and the `.mcpb` artifact are unaffected.

## Current authority amendment (2026-07-15)

The accepted
`[[2026-07-15-distribution-installation-readiness-adr]]` partially supersedes this
decision without retiring its non-conflicting architecture. The three-distribution
physical split, mirrored `cadrumo_data` namespace, single resource-resolution seam,
and present-byte integrity enforcement remain accepted.
The following earlier rulings no longer govern:

- the `cadrumo[corpus-sources]` optional-extra and supported slim-only installation
  mode are retired; every command-bearing `cadrumo` installation requires both
  exact-version data companions through the base runtime dependency closure;
- local token-based publication is retired; immutable tested-cohort promotion through
  the successor ADR's sole protected GitHub Actions OIDC authority governs;
- absence handling is a fail-closed integrity diagnostic for an incomplete or damaged
  environment, not a supported degraded product mode or a compatibility surface.

## Problem Statement

Cadrumo had no user-facing distribution. Nothing was published to a package
index and the only install path was a developer checkout with `uv sync`. This ADR decides
the Python distribution chain: what gets published where, how the installed product
stores taxpayer data, and how the corpus integrity chain survives a physical split.

## Considerations

- **Measured artifact reality.** The wheel is 171.8 MB; `_data/corpus` is
  93.9% of its compressed weight. Dropping only the corpus source binaries
  (`*.pdf`/`*.xls`/`*.xlsx`) yields a ~36 MB wheel, under PyPI's 100 MB cap
  with headroom, while keeping every byte the grounding search and legal
  gates read (extracted text, normative html, registry, terminology, agent
  data). A corpus-binaries companion wheel would be ~139-165 MB (routine
  PyPI grant territory; `torch` precedent is 500 MB).
- **Publication policy.** This ADR originally chose local, human-gated
  `uv publish` with a scoped token. The distribution-installation-readiness ADR
  supersedes that ruling: one protected GitHub Actions OIDC authority promotes
  an already-tested immutable cohort and never rebuilds release bytes.
- **License is publication-ready.** `license = "Apache-2.0"` (SPDX, PEP 639)
  with the `LICENSE` file auto-packaged; the mcpb manifest's stale
  `"see repository"` field is a cosmetic alignment.
- **Dependency hygiene.** `vaultspec-rag[mcp]` rides the base dependency set
  today; it is developer tooling and must be demoted before first release.
- **Installed-run user-data defect (blocking).** `Settings.cadrumo_local_storage_root`
  defaults to `PROJECT_ROOT / "var" / "storage"` where `PROJECT_ROOT` walks up
  from the installed module, inside the virtualenv, and under `uvx` inside
  uv's ephemeral cache, where the taxpayer's encrypted store could be wiped by
  a cache prune. The installed default must become a platform user-data
  directory; the checkout default stays for the dev loop.

## Considered options

**D1 - Published distribution shape.**
- *D1a: single `aeat` wheel + PyPI file-size grant (171.8 MB).* One artifact,
  no split seam; but every install downloads the corpus binaries and release
  cadence is hostage to an SLA-less grant. Rejected.
- *D1b (adopted by the successor ADR): slim `cadrumo` wheel plus both data
  companions as REQUIRED exact-version dependencies.* This was rejected here
  before real installed-tax-work evidence existed. The successor research proved
  that a root-only installation cannot perform the product's grounded calculation
  claim, while the two companion files remain independently distributable below
  the package-index cap. It is now the governing dependency closure.
- *D1c (chosen here for the physical split; optionality retired): slim `cadrumo`
  wheel (~36 MB, every runtime surface:
  extracted text, normative html, registry, terminology, agent data) plus the
  `cadrumo-data-manuals` and `cadrumo-data-official` companion wheels carrying
  the corpus source binaries through mandatory exact-version base dependencies,
  with fail-closed integrity diagnostics for an incomplete environment.*
  Code inspection (research F10) proved the binaries are production-runtime
  inputs today: the always-on registry gate SHA-256-hashes all 56 cited
  binaries at first load and hard-fails on absence. Every PRESENT binary
  stays byte-exact hash-enforced; an absent required binary refuses
  instructively and never becomes a supported slim-only mode. With both
  companions installed, behaviour is byte-identical to the full source tree.
- In every variant the surfaces the grounding search and legal gates read
  stay in the runtime wheel (bundled-corpus rules), and no variant
  introduces install-time fetching.

**D4 - Publication flow.**
- *D4a: local, human-gated `uv publish` with a scoped PyPI token.* Chosen by
  this ADR, then superseded by the distribution-installation-readiness ADR.
- *D4b: protected GitHub Actions Trusted Publishing (OIDC) that promotes an
  immutable tested cohort without rebuilding.* Governing current authority per
  the successor ADR.

## Constraints

- **No install-time legal-data fetching** (product-packaging ADR, proposed but
  treated as binding here): reviewed data ships in artifacts. Any size
  strategy is a shipped-artifact strategy; downloaders are rejected.
- **Bundled-corpus verification chain** (`legal-grounding-verifies-bundled-
  authoritative-corpus`, corpus-registry-packaging ADR): the extracted text,
  normative html, and registry the gates verify against MUST remain in the
  runtime wheel. Only surfaces nothing in the installed product reads may
  move to a companion distribution.
- **Data budget** (arch-remediation-data-budget ADR, accepted): `_data` <=
  550 MB with a CI gate; the split decided here must keep the gate meaningful
  (budget per distribution, not evaded by the split).
- **Publication authority is singular.** The successor ADR's protected GitHub
  Actions OIDC promotion lane is the sole release publisher. Local recipes may
  build or diagnose candidates but may not upload release artifacts.
- **Safety rails carry over unchanged**: never-live-submit ("no such tool
  exists"). Packaging must not weaken it.
- **Physical split is not product optionality.** Companion files remain separate
  for package-index file-size limits, while every command-bearing acquisition
  resolves the complete exact-version cohort.

## Implementation

High-level layering (the plan owns steps and sequencing):

- **Product-run foundations.** Move the installed-run storage default off
  `PROJECT_ROOT`: `Settings.cadrumo_local_storage_root` (and the derived
  tokens/logs roots) defaults to a platform user-data directory when running
  from an installed distribution, keeping the checkout default for the dev
  loop. Demote `vaultspec-rag[mcp]` out of the base dependency set. Align the
  stale mcpb-manifest license field.
- **Wheel split.** Three distributions built from the ONE source tree (no
  source moves, the 550 MB `_data` budget gate keeps guarding the tree):
  `cadrumo` excludes `_data/corpus/**/*.{pdf,xls,xlsx}`;
  `cadrumo-data-manuals` packages `corpus/manuals`; and
  `cadrumo-data-official` packages `corpus/aeat_official` plus
  `corpus/normatives`, both under the mirrored `cadrumo_data` namespace. A
  resolution seam in the corpus locator tries the `cadrumo` tree first, then
  `cadrumo_data`, so authoring/dev (full checkout) and installed (split) reads
  are uniform.
- **Integrity boundary.** `verify_source_file`/`verify_source_catalogue` keep
  present bytes under exact hash enforcement. An absent required companion
  member is an incomplete-install integrity failure surfaced instructively,
  never a supported advisory-only runtime. Anti-tautology tests prove a
  corrupted PRESENT binary still hard-fails.
- **Release lane.** Build the root and both companion distributions as one
  immutable cohort, execute the installed product against those exact hashes,
  and promote the same bytes through the successor ADR's protected OIDC lane.
  No release lane rebuilds or publishes a root-only command-bearing product.

## Rationale

The physical wheel split is forced by arithmetic and unblocked by code: the
corpus binaries are 94% of the wheel's weight (F8) yet serve only the
integrity-hash chain and verification verbs at runtime (F10), and a ~36 MB
root file stays below the package-index cap. The successor evidence
establishes that all three files form one mandatory product installation.
Presence stays byte-exact and absence refuses loudly as an integrity failure.
The local human-gated publish ruling (D4a) was later replaced by immutable
tested-cohort OIDC promotion.

## Consequences

**Gains.** A real product install path for the first time: power users get
`uvx --from cadrumo aeat` / `pip install cadrumo`; MCP clients install the
declared Cadrumo cohort and launch the separate `cadrumo_mcp` entrypoint
`cadrumo-mcp`. The root wheel drops 171.8 to ~36 MB while both companion files
remain mandatory parts of the installation cohort.

**Costs and risks.** The integrity boundary spans multiple distribution files,
the one place this ADR touches legal-grounding enforcement; it must be reviewed
against the no-silent-degradation bar and carries anti-tautology proof
obligations. The resolution seam adds a second `importlib.resources` root for
corpus binaries (the "resource-resolution seams" cost the data-budget ADR
predicted for Option B). The root package cannot be released independently of
its exact-version companions; acquisition failure blocks installation instead
of creating a degraded tax product.

**Supersession.** Extends (does not violate) `2026-04-12-release-please-adr` and
activates Option B of `2026-07-02-arch-remediation-data-budget-adr` at the wheel
boundary (source tree unchanged). The accepted
`2026-07-15-distribution-installation-readiness-adr` subsequently supersedes
this ADR's optional dependency/public slim-only ruling and local publication
authority while preserving the physical-split, resource-resolution, and
integrity decisions.

## Amendment 2026-10-12: gates withdrawn by parity

Accepted under `2026-10-11-mcp-parity-full-parity-adr` and the 2026-10-12 amendment of `2026-07-02-agent-harness-refoundation-adr`. Of the safety rails this record carries over, never-live-submit is unchanged. Packaging must not narrow what the MCP server serves below what the CLI can do.

## Service boundary packaging amendment 2026-10-14

Authorized by the user's explicit service/harness separation instruction. Harness code and authored material are owned by `src/cadrumo_harness` and the separate `cadrumo-mcp` entrypoint; current `pyproject.toml` ships them in the declared Cadrumo distribution cohort without a `cadrumo[agent]` extra. Native desktop-hosted agent service is separate `cadrumo-agent-service`. Data-cohort integrity and original dates/status survive.

## Harness boundary amendment 2026-10-21: plugin generation leaves Cadrumo

Drift repair toward the cadrumo-agent vault's accepted `2026-10-15-agent-harness-adr`,
authorized by the user in session TUI-REFACTOR. That record owns personas, skills, rules
and all workspace and plugin materialisation. Cadrumo generates no Claude plugin and
materialises no workspace: `dev/packaging/claude_plugin.py` and the `build-claude-plugin`
recipe are removed, with no compatibility facade. The plugin generator moves to
cadrumo-agent, subject to that record's own plugin-retirement decision.

Cadrumo's part of the consumer path is the published `cadrumo-mcp` server and the
distribution cohort it ships in; its package is renamed from `src/cadrumo_harness` to
`src/cadrumo_mcp`, and the MCP surface serves no skill, rule or persona content. The
`src/cadrumo_harness` ownership stated in the service boundary packaging amendment of
2026-10-14 above no longer holds for authored material.

Unchanged: the physical distribution split, the mirrored `cadrumo_data` namespace, the
single resource-resolution seam, present-byte integrity enforcement, the data budget, the
OIDC release lane, never-live-submit and the on-host evidence rule. This amendment states
ownership; it is not evidence that any of it is built.
