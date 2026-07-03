# aeat-marketplace

The Claude marketplace repository content for the
[`aeat`](https://github.com/wgergely/aeat) Spanish-tax plugin.

A Claude marketplace is a git repository carrying a
`.claude-plugin/marketplace.json` that lists one or more installable plugins.
At release time this directory is served from a dedicated public git repository;
users install the plugin from it with `/plugin marketplace add <repo>` followed
by `/plugin install aeat@aeat-marketplace` (Claude Code CLI), or through the
plugin browser (Claude Desktop / Cowork).

## Layout

- `.claude-plugin/marketplace.json` — the marketplace manifest. Its single
  `plugins[]` entry sources the plugin from the relative `./plugins/aeat`
  subtree.
- `plugins/aeat/` — the plugin tree the marketplace serves. **Generated, never
  hand-edited.** It is materialised from the single authored operator-harness
  source by the `aeat` plugin generator, so the marketplace and the plugin
  cannot drift. This subtree is git-ignored here and regenerated on every
  release.

## Regenerating the served plugin tree

The plugin subtree is emitted by the harness materialiser
(`aeat.agent.materialise_marketplace`), which writes both the
`.claude-plugin/marketplace.json` and the `plugins/aeat/` plugin tree from one
source. Regenerate before cutting a release so the served plugin matches the
published `aeat` wheel version.
