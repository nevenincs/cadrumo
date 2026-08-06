---
tags:
  - '#research'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:8c6881ce31c198d37107e43ad3799cc3335d1913c9f1ab68c052634f62da7426'
related:
  - '[[2026-06-28-product-packaging-adr]]'
  - '[[2026-07-02-arch-remediation-data-budget-adr]]'
  - '[[2026-05-15-corpus-registry-packaging-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
---

# `claude-ecosystem-packaging` research: `Claude ecosystem as the first packaged product destination`

Research into making the Claude ecosystem (Claude Cowork, Claude Code, Claude
Desktop, claude.ai — one unified plugin format) the first packaged, truly
user-facing product destination for the `aeat` CLI plus the `aeat-mcp` agent
harness. Trigger: the harness-userdocs kickoff exposed that no user-facing
distribution exists at all — nothing is published to any index, and the current
`.mcpb` bundle is a manifest-only pointer that cannot work on a machine without
a developer checkout. Operator directive (2026-07-03): the Claude ecosystem is
the first target; deliver the Cowork/Desktop plugin after rigorous research,
planning, and implementation.

## Findings

### F1 — The distribution gap is total (verified)

- The package name `aeat` returns HTTP 404 on `pypi.org/pypi/aeat/json`
  (checked 2026-07-03): nothing is published anywhere a user could install
  from, and the name is unclaimed.
- The only working install path is developer-grade: repo clone, `uv sync`
  dependency groups, `playwright install`. `docs/workstation-setup.md` cites
  `pip install "aeat[google]"` forms that cannot resolve for an outside user
  today.
- The shipped `.mcpb` Desktop Extension (`packaging/mcpb/build.py`) zips ONLY
  `manifest.json`. The manifest declares `server.type = "binary"` with
  `command = "aeat-mcp"`, assuming the console script is already on the user's
  PATH; its own docstring records it "requires the `aeat[agent]` extra
  installed on-host". Installing it into a client on a clean machine yields a
  dead extension. Signing (the brief's known gap) is secondary to this.

### F2 — Decision lineage: the size question was already deferred to exactly this campaign

- `2026-05-15-corpus-registry-packaging-adr` (accepted) moved corpus/registry
  into the wheel and recorded: "Public PyPI publication requires either a
  file-size-limit grant or a future trim... captured for the release-engineering
  owner to resolve." This campaign is that owner arriving.
- `2026-07-02-arch-remediation-data-budget-adr` (accepted) sets a 550 MB
  `_data` budget with a CI gate, excludes tests/fixtures from the wheel, and
  keeps "split the corpus into a separate data distribution" as Option B — the
  explicit escape hatch awaiting a forcing function. PyPI's per-file cap is
  that forcing function unless a size grant is obtained.
- `2026-06-28-product-packaging-adr` (proposed) owns artifact integrity: the
  self-contained wheel, clean-install smoke lanes (`just packaging-smoke-*`,
  `.github/workflows/packaging-smoke.yml`; Docker core + browser proofs passed
  2026-06-29 from a detached clean checkout). Binding constraint inherited
  here: **install-time legal-data fetching is rejected** — reviewed data ships
  in artifacts. Any size strategy must therefore be a shipped-artifact
  strategy (size grant, or a second reviewed-data distribution that pip
  resolves as a dependency), never an ad-hoc downloader.
- `2026-07-02-agent-harness-refoundation-adr` (accepted) R8 chose "a signed
  `.mcpb` Desktop Extension as the consumer path". The plugin finding below
  supersedes the vehicle choice, not the intent (one-click install for a
  non-technical taxpayer, same server for any MCP client). R9's off-host
  consent posture and R6's gates carry over unchanged into any Claude-native
  packaging.

### F3 — Claude ecosystem landscape (July 2026, external research)

Established via web research against official sources (claude.com/blog,
code.claude.com/docs, support.claude.com, github.com/anthropics):

- **Claude Cowork** is GA on macOS and Windows (Windows since Feb 2026): an
  agentic desktop workspace for non-developers running long multi-step tasks
  over local files with human confirmation gates. Its audience and interaction
  model match the aeat harness reader exactly (non-technical taxpayer/gestor,
  CONFIRM-gated irreversible actions, on-host files).
- **One plugin format spans Claude Code CLI, Cowork, Claude Desktop, and
  claude.ai** (`.claude-plugin/plugin.json` at plugin root). A single plugin
  can bundle MCP server declarations (`.mcp.json`), skills
  (`skills/<name>/SKILL.md`), agents, commands, hooks, and executables.
  Marketplaces are git repos carrying `marketplace.json`; users install via
  a plugin browser UI (Cowork/Desktop) or `/plugin install` (Claude Code).
  Community distribution exists via the `claude-plugins-community` marketplace.
- **Runtime reality**: Claude Desktop/Cowork bundle Node.js but ship neither
  Python nor `uv`. A Python MCP server arrives via (a) `uvx <package>` from
  PyPI (community-standard, requires `uv` on the machine, not prominently
  official), (b) a `.mcpb` with `server.type = "python"` and bundled `lib/`
  dependencies (officially documented primary Python path; compiled-extension
  portability is cautioned), or (c) a platform executable.
- **Uncertainties flagged for verification during execution**: whether Cowork
  installs `.mcpb` bundles directly (unconfirmed; moot if the plugin is the
  vehicle); whether MCP elicitation (the CONFIRM gate's rich path) reaches
  Cowork/Desktop clients — the harness already has the decided degradation
  matrix (`destructiveHint` + handoff-deny) if not, and the R7 live-measurement
  harness is the proper instrument to answer it.

### F4 — The plugin content payload already exists in-repo

- `aeat app agent --output DIR` (`src/aeat/entrypoints/cli/_app_agent_workspace.py`,
  profile-independent, no secret store) materialises the shipped harness into
  the Claude-native layout via `src/aeat/agent/_workspace.py`:
  `.claude/skills/<name>/SKILL.md` (34 skills incl. reference material),
  `.claude/agents/<persona>.md` (7 personas), `.claude/rules/<rule>.md`
  (7 operator rules) aggregated by a root `CLAUDE.md`. ADR R4 keeps this as
  the optional Claude-native mirror of the single authored source
  `src/aeat/_data/agent/`.
- Verified live (2026-07-03): `aeat app agent --output <dir>` ran clean from
  the working tree and wrote 7 rules, 7 personas, and 34 skills in the
  `.claude/{rules,agents,skills}` + `CLAUDE.md` layout.
- A plugin is therefore mostly a re-targeting of this materialiser: emit
  `.claude-plugin/plugin.json` + `skills/` + `agents/` + `.mcp.json`
  (declaring `aeat-mcp`, persona via `AEAT_MCP_PERSONA`) instead of the
  workspace layout, plus a marketplace repo. Content generation is
  days-scale; the single-authored-source discipline is preserved.

### F5 — The bundled-data numbers that drive the size decision

Measured from the working tree (2026-07-03): `src/aeat/_data` totals ~485 MB —
`corpus` 464 MB (aeat_official 263 MB, manuals 175 MB, normatives 25 MB),
`registry` 21 MB. By file type the corpus is ~159 MB `.pdf` + ~116 MB `.xls` +
~37 MB `.xlsx` source binaries versus ~140 MB extracted text (`.md`/`.json`/
`.html`) that the on-host grounding search actually consumes. Slimming
candidates therefore exist WITHOUT violating the bundled-corpus rules (the
extracted text plus registry stays shipped; the source binaries could move to
a second reviewed-data distribution), but `legal-grounding-verifies-bundled-
authoritative-corpus` and the corpus-authority flow mean any split must keep
the verification chain intact and reviewed. Exact wheel/sdist sizes and
compressed breakdowns: see F8 (measured artifact report).

### F6 — What a Cowork/Desktop delivery needs end to end (gap list)

1. **A published package** — claim `aeat` on PyPI, stand up a release lane
   (trusted publishing), decide the size strategy (grant vs corpus-binaries
   split vs data-distribution; see F8), and clean the dependency surface
   (the `vaultspec-rag[mcp]` base dependency must be demoted before first
   release; the mcpb manifest's `license: "see repository"` field aligns to
   the real Apache-2.0). License metadata itself is already
   publication-ready (F8).
2. **A bootstrap decision** — how `aeat-mcp` starts on a machine with no
   Python: `uvx` (cleanest, needs uv), bundled-deps `.mcpb` (official Python
   path, portability caveats), or platform binary (heaviest engineering).
3. **The plugin artifact** — materialiser extension (F4), plugin manifest,
   `.mcp.json`, marketplace repo, optional community-marketplace submission.
4. **Verification** — a real-client install proof (Cowork and Claude Code) as
   the campaign's acceptance gate, per the R7 live-measurement discipline;
   elicitation-support measurement rides the same harness.
5. **Docs** — the harness userdocs initiative (paused, kickoff brief in
   `docs/HARNESS-USERDOCS-KICKOFF-BRIEF.md`) resumes against the real install
   story once this campaign lands.
6. **A platform user-data root (BLOCKING defect for installed runs)** —
   `PROJECT_ROOT` in `src/aeat/core/config.py` walks four parents up from the
   module file, and `Settings.aeat_local_storage_root` defaults to
   `PROJECT_ROOT / "var" / "storage"`. From an installed wheel this resolves
   INSIDE the environment (e.g. `<venv>/Lib/var/storage`); under `uvx` it
   resolves inside uv's ephemeral cached environment, where the taxpayer's
   ENCRYPTED STORE could be silently destroyed by a cache prune. The
   corpus-registry-packaging ADR already flagged moving the `var/` defaults to
   an operator-config surface as a deferred cleanup; product installation makes
   it a blocker. The installed default must become a platform user-data
   directory (e.g. `%LOCALAPPDATA%/aeat` / `~/.local/share/aeat` /
   `~/Library/Application Support/aeat`), with the checkout default preserved
   for the dev loop. Same applies to the other `var/` sub-roots (tokens, logs)
   derived from the same setting.

### F7 — PyPI publication mechanics (researcher report, 2026-07-03)

- **Size limits**: defaults are 100 MB/file and 10 GB/project. Increases are
  requested via `pypi/support` issue templates (`limit-request-file.yml` /
  `limit-request-project.yml`); a file-size bump requires at least one release
  already uploaded under the current limit. Precedents: `torch` granted
  500 MB/file, TensorFlow 100-200 MB, routine 150 MB grants. PyPI's stated
  criterion: "limit increases are generally only granted for large binaries";
  a reviewed legal corpus is within precedent but not guaranteed, and grant
  turnaround has no published SLA — a scheduling risk if the plan depends on
  one. (docs.pypi.org storage-limits; pypa/packaging-problems #96/#101;
  pypi/support #5579)
- **Data-package pattern**: `aeat` (code) + `aeat-data` (corpus wheel) with an
  exact version pin matches spaCy/NLTK practice; `spacy-lookups-data` proves
  moderate on-PyPI data packages work. PyPI has NO data-specific size
  carve-out — same limits and grant process. spaCy's own large models ship
  via GitHub Releases + downloader, which is exactly the runtime-fetch path
  the product-packaging ADR rejects; the ADR-compatible variant is a fully
  bundled `aeat-data` wheel. Combined with F8: the code wheel slims to
  ~36 MB (no grant needed); an `aeat-data` wheel carrying the corpus source
  binaries lands ~139-165 MB compressed — routine-grant territory.
- **License**: PEP 639 adopted; `license` as SPDX expression + `license-files`
  globs; `License ::` classifiers deprecated. Project already carries
  `Apache-2.0` + packaged `LICENSE` (F8) — publication-ready as-is.
- **Name + publish flow**: first upload claims the name (`aeat` verified
  unclaimed, F1). The 2026-standard Trusted Publishing (OIDC) path and
  pending-publisher name reservation **require GitHub Actions, which is
  banned on this repo** (`#github_actions_disabled`), and the accepted
  release-please ADR lists PyPI publishing as an explicit non-goal. The
  policy-clean path is **local, human-gated `uv publish`/`twine` with a
  scoped API token**, mirroring the existing LOCAL-ONLY + HUMAN-GATED
  release discipline; Trusted Publishing needs an operator-level policy
  exception (GitLab/GCP OIDC are alternatives) if ever wanted.
- **uvx with large wheels**: uv resolves metadata via HTTP range requests and
  caches wheels globally (`~/.cache/uv` / `%LOCALAPPDATA%\uv\cache`), so a
  large download is one-time per version per machine, near-instant after.
  Pin with `uvx aeat@X.Y.Z` (`--from` caches aggressively; fine for pinned
  releases). No documented MCP-server prior art at 300+ MB — with the ~36 MB
  slimmed code wheel this concern largely dissolves; the corpus-binaries
  data package is not needed at `aeat-mcp` runtime.
- **Existing release automation** (accepted `2026-04-12-release-please-adr`):
  `release-please@16` via `npx` from `just release` / `just release-apply` —
  LOCAL-ONLY, HUMAN-GATED (dry-run log, then a `chore(release)` commit + local
  unpushed tag). Version truth is `pyproject [project].version`, mirrored to
  `__version__`, gated by `tests/test_release_config.py`. **Gap**: versioning
  + CHANGELOG + tagging only; wheel building, size grants, name claim, and
  upload are all greenfield for this campaign.

### F8 — Measured artifact sizes (build report, 2026-07-03)

Built with `uv build` from the working tree (repo untouched):

- `aeat-0.1.0-py3-none-any.whl` = 180,127,465 bytes (~171.8 MB);
  `aeat-0.1.0.tar.gz` = ~180.6 MB. Both exceed PyPI's 100 MB default
  per-file cap, but by ~1.7x — not the 4-5x the raw tree suggested.
- `aeat/_data/corpus/` is 486.1 MB uncompressed / 164.7 MB compressed —
  **93.9% of the wheel's compressed weight**. Breakdown: `corpus/aeat_official`
  71.9 MB compressed, `corpus/manuals` 87.5 MB, `corpus/normatives` 5.3 MB.
  The registry TOML tree is negligible (5.8 MB compressed, 16,014 fragments).
  PDFs dominate irreducibly (103.0 MB compressed — PDFs barely compress);
  `.xls` compresses 121.7→16.9 MB.
- Tests in wheel: **zero** — the data-budget ADR exclusion is holding.
- Slimmed hypotheticals (zip-member arithmetic; a real rebuild must confirm):
  (a) drop corpus source binaries (`*.pdf`/`*.xls`/`*.xlsx` under
  `_data/corpus`, keep all extracted text + registry + agent data):
  **≈36.4 MB compressed** — comfortably under the 100 MB cap with years of
  headroom; (b) drop the whole corpus: ≈10.8 MB.
- `pyproject.toml` facts: `license = "Apache-2.0"` (SPDX) with root `LICENSE`
  auto-packaged into the wheel — **license is NOT a publication blocker**
  (the earlier "see repository" concern was the mcpb manifest's field, a
  cosmetic fix). An `agent` extra exists: `agent = ["mcp>=1.12,<2"]` gating
  the `aeat-mcp` runtime; the harness data itself (rules/personas/skills,
  ~112 KB compressed) ships unconditionally in the core wheel.
- **Dependency-hygiene flag for publication**: `vaultspec-rag[mcp]>=0.2.28`
  is currently a BASE dependency of the package. That is developer tooling
  (the repo's own semantic-search service) and must not ride a published
  product wheel; it needs demotion to a dev group or extra before first
  release.

### F9 — Plugin format exact schemas (researcher report, 2026-07-03)

Sources: code.claude.com/docs/en/{plugins,plugins-reference,plugin-marketplaces,mcp};
support.claude.com. Full verbatim schemas captured in the dispatch transcript;
load-bearing facts:

- **plugin.json**: `.claude-plugin/plugin.json`; only `name` (kebab-case) is
  required; `author` is an object; `version` set → users update only on bump;
  unrecognized top-level fields are ignored (one manifest can double for
  mcpb); `claude plugin validate --strict` is the CI gate;
  `defaultEnabled: false` recommended for external-service plugins.
- **MCP servers in plugins**: `.mcp.json` at plugin root or inline
  `mcpServers`; full interpolation — `${CLAUDE_PLUGIN_ROOT}` (ephemeral
  install dir), `${CLAUDE_PLUGIN_DATA}` (persistent per-plugin dir surviving
  updates), `${user_config.KEY}`, `${ENV_VAR:-default}`. Tool names surface
  as `mcp__plugin_<plugin>_<server>__<tool>`.
- **Persona selection UX exists**: `userConfig` prompts on enable (the
  "Configure" button); types are string/number/boolean/directory/file — NO
  enum/dropdown, so persona is a string option with a `default`, wired as
  `"env": {"AEAT_MCP_PERSONA": "${user_config.persona}"}`; the server
  validates and refuses unknown personas loudly (it already does).
  Sensitive values go to the OS keychain (~2 KB budget).
- **Skills/agents layout matches the materialiser**: `skills/<name>/SKILL.md`
  with `reference/` progressive-disclosure subdirs SUPPORTED; frontmatter
  `description` is the invocation signal. Agents: `agents/*.md` with
  `name/description/model/effort/maxTurns/tools/disallowedTools/skills`;
  plugin agents may NOT declare hooks/mcpServers/permissionMode. The
  vaultspec-style `mode:` field is not a Claude field — persona mutation
  intent must map to `tools`/`disallowedTools`.
- **marketplace.json**: `.claude-plugin/marketplace.json` with `name`,
  `owner`, `plugins[]`; source types `./path`, `github{repo,ref,sha}`,
  `git-subdir` (monorepo-friendly), `npm`. Community submission via
  Console (`platform.claude.com/plugins/submit`), automated validation +
  safety screening, SHA-pinned, nightly catalog sync. `claude-plugins-official`
  is curated, no application path.
- **Platform deltas (CRITICAL)**: local stdio MCP servers are fully supported
  in Claude Code CLI (subprocess, full FS access — the safe target) and
  should work in Claude Desktop (uncertainty whether plugin-bundled stdio vs
  the mcpb path — flagged). **Cowork: support material states connectors
  "operate through Anthropic's cloud infrastructure, requiring public
  internet accessibility rather than local network access" — if Cowork runs
  MCP in the cloud, a local encrypted-store server does NOT run there
  (MEDIUM confidence, conflicting sources; MUST be live-verified).**
  claude.ai web cannot run a local server (skills only). Net: the skills
  port everywhere; the local server's confirmed floor is Claude Code (+
  likely Desktop); Cowork is the live-test question.
- **CONFIRM mechanism upgrade**: elicitation is documented only for Claude
  Code; but the `anthropic/requiresUserInteraction` tool annotation
  (v2.1.199+) forces a permission prompt on EVERY call even under
  auto/bypass permission modes — a documented, bypass-proof CONFIRM channel
  the harness's gated verbs should adopt alongside the existing
  elicitation/degradation matrix.
- **Size discipline**: no documented plugin byte cap, but per-version cache
  copies and a 120 s git-clone timeout make multi-hundred-MB plugins
  anti-pattern; the documented pattern for heavy runtimes is a THIN plugin +
  runtime via PyPI/uvx (or a SessionStart hook installing into
  `${CLAUDE_PLUGIN_DATA}`). Supports the slim-wheel + uvx bootstrap shape.
- **Plugin state discipline**: `${CLAUDE_PLUGIN_ROOT}` is wiped on update —
  never store state there; persistent plugin-owned data belongs in
  `${CLAUDE_PLUGIN_DATA}`. The taxpayer's encrypted store is app-owned, not
  plugin-owned, reinforcing the platform user-data-root fix (F6 item 6).

### F10 — Corpus source binaries ARE production-runtime inputs (code inspection, 2026-07-03)

Verdict from a thorough read-only trace: the binaries are NOT safely dev-only
as currently coded. Two production consumers:

- **The always-on registry integrity gate (the blocker).** The production
  registry accessor loads `ValidatedRegistryAuthority` with
  `source_root = bundled _data`; `_load_authority` eagerly runs
  `validate_registry()`, whose `verify_source_catalogue` full-byte SHA-256
  hashes EVERY cited corpus binary (`verify_source_file` in
  `_corpus_catalogue.py`: hard-fail on absence, hard-fail on hash mismatch).
  56 source refs resolve to the split-candidate dirs (32 `.pdf`, 2 `.xls`,
  22 `.xlsx`; 38 under `disenos_registro`, plus calendars/forms/instructions,
  renta manuals, 2 normative pdfs). The gate fires on the first registry load
  in any process — essentially every operator calc/verify/file/export
  command. Removing the binaries without gate changes bricks the CLI.
- **`aeat app registry` verification verbs** (workbooks verify, parity
  run/replay, registry verify, manuals verify) open bundled workbooks/PDFs at
  runtime — explicit opt-in verbs that could degrade to a "data package not
  installed" refusal.

NOT production (do not block a split): Diseño-de-Registros workbook →
completeness-manifest projection is authoring-time (compiled into registry
TOML); the LibreOffice recalc parity harness is dev/CI; all fixture readers
live under excluded `tests/`. High confidence on the gate trace; the CLI was
not dynamically executed (read-only pass).

Consequence: a slim-wheel split is viable ONLY together with principled gate
tolerance — hash-verify every binary that is PRESENT (byte-exact, unchanged
semantics), and for binaries declared as shipped-in-a-companion-distribution
but absent, surface a LOUD advisory naming the missing set and the install
hint (never silence, per the no-silent-degradation discipline); the four
registry verification verbs refuse instructively when the companion is
absent. With the companion installed, behaviour is byte-identical to today.

## Open questions for the ADR
- **Persona configuration UX** — RESOLVED by F9: `userConfig` string option
  with `default`, wired to `AEAT_MCP_PERSONA` via `${user_config.persona}`;
  server-side validation stays the refusal surface (no enum type exists).
- **Cowork local-MCP execution** — the top live-verification item: does a
  plugin's local stdio server run on the user's machine under Cowork, or do
  Cowork connectors execute through Anthropic's cloud (which would exclude
  the local encrypted-store server there)? Claude Code CLI is the confirmed
  floor; Desktop likely. The delivery plan must gate the "Cowork" claim on a
  real install test, and the docs must state the verified matrix honestly.
- **CONFIRM channel** — partially resolved by F9: adopt the
  `anthropic/requiresUserInteraction` annotation on CONFIRM-tier verbs as
  the bypass-proof documented channel; elicitation + the decided degradation
  matrix remain for non-Claude clients; live measurement per R7 still
  confirms end-to-end behaviour.
- **Grant sequencing**: a size grant needs a first sub-limit upload; if
  `aeat-data` is needed, the release plan must sequence name-claim →
  sub-limit dev release → grant request → full release, with the no-SLA
  turnaround as the schedule risk.

## Sources

- PyPI name check: `https://pypi.org/pypi/aeat/json` → 404 (2026-07-03).
- Cowork plugins: `https://claude.com/blog/cowork-plugins`;
  `https://support.claude.com/en/articles/13837440-use-plugins-in-claude`;
  `https://code.claude.com/docs/en/plugins`.
- Desktop Extensions/.mcpb: `https://www.anthropic.com/engineering/desktop-extensions`;
  `https://support.claude.com/en/articles/12922929-building-desktop-extensions-with-mcpb`;
  `https://github.com/modelcontextprotocol/mcpb`.
- Skills standard: `https://code.claude.com/docs/en/skills`; `https://agentskills.io`.
- In-repo: `packaging/mcpb/build.py`, `packaging/mcpb/manifest.json`,
  `src/aeat/agent/_workspace.py`, `src/aeat/entrypoints/cli/_app_agent_workspace.py`,
  `pyproject.toml`, `src/aeat/_data` tree measurement (2026-07-03).
- Vault: the four ADRs in `related:` plus `2026-06-28-product-packaging-research`.
