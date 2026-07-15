---
tags:
  - '#adr'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-research]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
---

# `claude-ecosystem-packaging` adr: `Claude ecosystem plugin as the first product distribution` | (**status:** `accepted`)

## Problem Statement

Cadrumo has zero user-facing distribution. Nothing is published to a package
index, the only install path is a developer checkout with `uv sync`, and the
shipped `.mcpb` Desktop Extension is a manifest-only zip whose
`server.type = "binary"` entry assumes `cadrumo-mcp` is already on the user's
PATH — installed on a clean machine it is a dead extension. The harness-userdocs kickoff exposed this as the blocker for any
truly user-facing documentation: there is no honest "install it" sentence to
write. Operator directive (2026-07-03): make the Claude ecosystem the first
packaged destination and deliver the Cowork/Desktop plugin after rigorous
research, planning, and implementation.

This ADR decides the full distribution chain: what gets published where, how
the runtime reaches a machine that has neither Python nor `uv`, what the
installable consumer artifact is, and which prior decisions it supersedes.

## Considerations

- **The consumer fit is exact.** Claude Cowork (GA on macOS + Windows) targets
  non-technical users running long agentic tasks over local files behind human
  confirmation gates — the same reader, interaction model, and safety posture
  the harness was designed for (CONFIRM elicitation, on-host evidence, R9
  consent). One plugin format spans Claude Code, Cowork, Claude Desktop, and
  claude.ai; a single plugin bundles an MCP server declaration, skills, and
  agents; marketplaces are git repos installable from a plugin-browser UI.
- **The plugin content payload already exists.** `aeat app agent --output`
  (verified live) materialises the single authored harness source into
  `.claude/{rules,agents,skills}` + `CLAUDE.md` — 7 rules, 7 personas,
  34 skills. A plugin is a re-targeting of this materialiser plus manifests,
  preserving the one-authored-source discipline of harness-refoundation R4.
- **Measured artifact reality.** The wheel is 171.8 MB; `_data/corpus` is
  93.9% of its compressed weight. Dropping only the corpus source binaries
  (`*.pdf`/`*.xls`/`*.xlsx`) yields a ~36 MB wheel — under PyPI's 100 MB cap
  with headroom — while keeping every byte the grounding search and legal
  gates read (extracted text, normative html, registry, terminology, agent
  data). A corpus-binaries companion wheel would be ~139-165 MB (routine
  PyPI grant territory; `torch` precedent is 500 MB).
- **Publication policy.** GitHub Actions is banned on this repo and the
  accepted release-please decision scopes PyPI publishing out as a non-goal;
  Trusted Publishing (OIDC) is therefore unavailable without a policy
  exception. The policy-clean path is a local, human-gated `uv publish` with
  a scoped token, extending the existing LOCAL-ONLY + HUMAN-GATED release
  discipline (`just release` / `just release-apply`, release-please@16,
  version truth in `pyproject.toml`).
- **License is publication-ready.** `license = "Apache-2.0"` (SPDX, PEP 639)
  with the `LICENSE` file auto-packaged; the mcpb manifest's stale
  `"see repository"` field is a cosmetic alignment.
- **Dependency hygiene.** `vaultspec-rag[mcp]` rides the base dependency set
  today; it is developer tooling and must be demoted before first release.
  The `agent` extra (`mcp>=1.12,<2`) gates the `cadrumo-mcp` runtime.
- **Installed-run user-data defect (blocking).** `Settings.cadrumo_local_storage_root`
  defaults to `PROJECT_ROOT / "var" / "storage"` where `PROJECT_ROOT` walks up
  from the installed module — inside the virtualenv, and under `uvx` inside
  uv's ephemeral cache, where the taxpayer's encrypted store could be wiped by
  a cache prune. The installed default must become a platform user-data
  directory; the checkout default stays for the dev loop.
- **Bootstrap reality.** Claude Desktop/Cowork ship Node.js, not Python or
  `uv`. Candidate bootstraps: `uvx --from cadrumo[agent]==X.Y.Z cadrumo-mcp`
  (one-time cached download, range-request metadata; requires `uv` on the
  machine), a bundled-deps
  `.mcpb` (`server.type = "python"`; official Python path, compiled-extension
  portability cautioned), or a platform executable (heaviest engineering).

## Considered options

Four decision axes, each with its alternatives.

**D1 — Published distribution shape.**
- *D1a: single `aeat` wheel + PyPI file-size grant (171.8 MB).* One artifact,
  no split seam; but every install downloads the corpus binaries, `uvx`
  first-run pulls 172 MB, and release cadence is hostage to an SLA-less grant.
  Rejected.
- *D1b: slim `aeat` wheel + `aeat-data` companion as a REQUIRED pinned
  dependency.* Keeps the integrity gate untouched (binaries always present)
  but chains every install — and therefore the plugin delivery — to the
  companion's SLA-less size grant. Rejected.
- *D1c (chosen): slim `cadrumo` wheel (~36 MB, every runtime surface:
  extracted text, normative html, registry, terminology, agent data) plus the
  `cadrumo-data-manuals` and `cadrumo-data-official` companion wheels carrying
  the corpus source binaries, consumed through the OPTIONAL
  `cadrumo[corpus-sources]` extra, with principled integrity-gate tolerance.*
  Code inspection (research F10) proved the binaries are production-runtime
  inputs today — the always-on registry gate SHA-256-hashes all 56 cited
  binaries at first load and hard-fails on absence — so this option REQUIRES
  the gate change: every PRESENT binary stays byte-exact hash-enforced
  (semantics unchanged); a binary declared as companion-shipped but absent
  yields a loud advisory naming the missing set and the install hint, never
  silence; the four `aeat app registry` verification verbs refuse
  instructively without the companions; with both companions installed,
  behaviour is byte-identical to today. Dev/CI keeps the full tree and the
  full byte-exact proof.
- In every variant the surfaces the grounding search and legal gates read
  stay in the runtime wheel (bundled-corpus rules), and no variant
  introduces install-time fetching.

**D2 — Runtime bootstrap for machines without Python.**
- *D2a: `uvx --from cadrumo[agent]==X.Y.Z cadrumo-mcp` declared in the
  plugin's MCP server config.* Cleanest update story (pin per plugin release),
  one-time cached download, no per-platform builds; requires `uv` on the
  machine — the plugin/docs carry a one-line `uv` install step. Preferred with
  the ~36 MB wheel.
- *D2b: `.mcpb` with `server.type = "python"` and bundled `lib/` deps.*
  Officially the primary Python path but compiled-extension portability is
  cautioned, per-platform bundles multiply artifacts, and Cowork's `.mcpb`
  support is unconfirmed. Kept only as a secondary artifact if measurement
  shows demand.
- *D2c: platform executables (PyInstaller-class) shipped in plugin `bin/`.*
  No prerequisites at all, but heaviest engineering (3-platform build matrix,
  signing, size) for a pre-beta; rejected for the first release, revisitable.

**D3 — Consumer vehicle.**
- *D3a: Claude plugin (marketplace repo; skills + agents + MCP server
  declaration generated from the single authored source).* One-click install
  across Cowork/Code/Desktop/claude.ai; supersedes harness-refoundation R8's
  `.mcpb`-primary ruling. Chosen.
- *D3b: keep `.mcpb` primary (status quo R8).* The bundle is currently a
  dead pointer, Cowork support unconfirmed, and it reaches only classic
  Desktop; rejected as primary.
- Any-MCP-client power users remain served by the same published `cadrumo-mcp`
  server regardless of vehicle (R8's intent, preserved).

**D4 — Publication flow.**
- *D4a: local, human-gated `uv publish` with a scoped PyPI token, extending
  the accepted release-please LOCAL-ONLY discipline (name claim via first
  upload; grant requests filed from the same lane if D1b).* Chosen.
- *D4b: Trusted Publishing (OIDC).* 2026-standard but requires CI (GitHub
  Actions banned; GitLab/GCP alternatives are new infrastructure); deferred
  to a separate operator-level policy decision.

## Constraints

- **No install-time legal-data fetching** (product-packaging ADR, proposed but
  treated as binding here): reviewed data ships in artifacts. Any size
  strategy is a shipped-artifact strategy; downloaders are rejected.
- **Bundled-corpus verification chain** (`legal-grounding-verifies-bundled-
  authoritative-corpus`, corpus-registry-packaging ADR): the extracted text,
  normative html, and registry the gates verify against MUST remain in the
  runtime wheel. Only surfaces nothing in the installed product reads may
  move to a companion distribution.
- **Data budget** (arch-remediation-data-budget ADR, accepted): `_data` ≤
  550 MB with a CI gate; the split decided here must keep the gate meaningful
  (budget per distribution, not evaded by the split).
- **No GitHub Actions** (repo policy) and **PyPI publishing a non-goal of the
  accepted release-please ADR**: this ADR extends that decision rather than
  violating it — publishing stays LOCAL-ONLY + HUMAN-GATED; any move to
  Trusted Publishing is a separate operator-level policy decision.
- **Safety rails carry over unchanged**: never-live-submit ("no such tool
  exists"), evidence bytes never off-host (R9), CONFIRM/faithfulness/persona
  gates (R6). Packaging must not weaken any of them; the plugin manifest's
  long description keeps stating the boundary.
- **Frontier-surface risk**: the plugin format, Cowork behaviour, and
  marketplace mechanics are July-2026 surfaces that postdate settled
  precedent and evolve; exact schemas must be verified against live official
  docs at implementation time, and the live-client install proof (R7
  discipline) is the acceptance gate, not documentation reading.
- **PyPI grant sequencing** (if a >100 MB companion wheel is chosen): grants
  require a first sub-limit upload and have no published turnaround SLA —
  the release sequence must not hard-block the plugin delivery on a grant.
- **Parent stability**: harness-refoundation (accepted) is stable; its R8
  distribution ruling is the one surface this ADR supersedes. The agent
  harness itself (server, gates, materialiser) is landed and live-measured.

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
- **Integrity-gate tolerance.** `verify_source_file`/`verify_source_catalogue`
  gain the companion-aware absent branch: present → byte-exact hash (today's
  semantics); absent-but-companion-declared → accumulate into one loud
  advisory with the `cadrumo[corpus-sources]` install hint; the registry
  verification verbs refuse instructively when the companion is required and
  absent. Anti-tautology tests prove a corrupted PRESENT binary still
  hard-fails.
- **Plugin generation.** Extend the `aeat app agent` materialiser with a
  plugin layout target emitting `.claude-plugin/plugin.json` (kebab-case
  name, version from package metadata, `defaultEnabled: false`, author
  object), `skills/` and `agents/` from the same authored source (agent
  frontmatter mapped to Claude fields — `tools`/`disallowedTools`, never the
  non-Claude `mode:`), `.mcp.json` declaring the stdio server as
  `uvx --from cadrumo[agent]==<pinned> cadrumo-mcp` with
  `"env": {"CADRUMO_MCP_PERSONA": "${user_config.persona}"}`, and a `userConfig`
  persona string option (server-side validation remains the refusal
  surface). `claude plugin validate --strict` becomes a packaging gate.
- **Marketplace.** A dedicated marketplace git repository carrying
  `.claude-plugin/marketplace.json` with the plugin as a `git-subdir` or
  in-repo source; the generator writes the plugin tree the marketplace
  serves. Community-marketplace submission is a post-verification follow-up,
  not a delivery gate.
- **CONFIRM hardening.** Add the `anthropic/requiresUserInteraction`
  annotation to CONFIRM-tier tools alongside the existing
  elicitation/degradation matrix, making the human gate bypass-proof in
  Claude clients.
- **Release lane.** Extend the LOCAL-ONLY, HUMAN-GATED release discipline
  with `just` publish recipes over `uv publish` + scoped token: claim the
  `cadrumo` name with the slim wheel (no grant needed), then publish the
  two sub-cap companion distributions from the same lane. The existing
  packaging-smoke lanes gain a split-install lane (core without companion →
  advisory path; with companion → byte-identical path).
- **Verification (acceptance gate).** A real-client install proof: plugin
  installed from the marketplace into Claude Code CLI (confirmed floor) and
  Claude Desktop/Cowork (live test resolves the cloud-vs-local MCP execution
  question, R7 discipline); the golden `regularizar-atrasos` itinerary runs
  end-to-end through the installed plugin. The verified support matrix — not
  aspiration — is what the userdocs state.

## Rationale

The research is decisive on every axis. The consumer fit (Cowork's audience
and confirmation-gated interaction model) matches the harness design
one-to-one, and the plugin format is the only vehicle that spans all Claude
surfaces with a one-click install — while the incumbent `.mcpb` artifact is a
provably dead pointer (F1), so D3a supersedes R8's vehicle choice while
preserving its intent (the same published server serves any MCP client). The
slim-wheel split (D1c) is forced by arithmetic and unblocked by code: the
corpus binaries are 94% of the wheel's weight (F8) yet serve only the
integrity-hash chain and opt-in verification verbs at runtime (F10), and a
grant-free ~36 MB wheel decouples the plugin delivery from PyPI's SLA-less
grant queue — the single most schedule-hostile dependency (F7). Gate
tolerance is designed inside the project's own honesty discipline: presence
stays byte-exact, absence is loud and instructive, dev/CI keeps the full
proof — the same advisory-not-silence pattern the carry and censo surfaces
already use. `uvx` bootstrap (D2a) rides uv's global cache and the slim
wheel, avoiding a 3-platform binary build matrix for a pre-beta. The local
human-gated publish lane (D4a) is the only path that respects both the
Actions ban and the accepted release-please scope, extending recipes the
team already runs.

## Consequences

**Gains.** A real product install path for the first time: a taxpayer
installs one plugin and gets the assistant, the skills, and the safety gates;
power users get `uvx --from cadrumo aeat` / `pip install cadrumo`; MCP clients
install `cadrumo[agent]` and launch `cadrumo-mcp`. The
userdocs initiative unblocks with an honest connect story. The wheel drops
171.8 → ~36 MB, PyPI publication needs no grant on the critical path, and the
release lane stays within existing policy. The CONFIRM gate gains a
documented bypass-proof channel in Claude clients.

**Costs and risks.** The integrity gate grows a second branch — the one place
this ADR touches legal-grounding enforcement; it must be reviewed against the
no-silent-degradation bar and carries anti-tautology proof obligations. The
resolution seam adds a second `importlib.resources` root for corpus binaries
(the "resource-resolution seams" cost the data-budget ADR predicted for
Option B). Cowork's local-MCP execution is unverified (MEDIUM-confidence
conflict in official material): if Cowork runs connectors in the cloud, the
delivered matrix is Claude Code + Desktop for the server with skills-only in
Cowork/web until Anthropic's surface changes — the live install test decides
what the docs may claim. The Cadrumo companion-publication timeline is
unbounded; until both companions are available, the registry verification verbs
and byte-provenance verbs degrade
with advisories for end users (dev/CI unaffected). Plugin-content updates are
coupled to marketplace repo pushes — a new release surface to keep in the
release checklist.

**Supersession.** Amends `2026-07-02-agent-harness-refoundation-adr` R8: the
Claude plugin replaces the signed `.mcpb` as the consumer path; the `.mcpb`
build remains only if measurement shows classic-Desktop demand. Extends (does
not violate) `2026-04-12-release-please-adr` and activates Option B of
`2026-07-02-arch-remediation-data-budget-adr` at the wheel boundary (source
tree unchanged). The proposed `2026-06-28-product-packaging-adr` gains a
split-install smoke lane but its core rulings stand.
