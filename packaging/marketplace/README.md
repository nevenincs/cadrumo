# neve marketplace

The Claude marketplace repository content for **neve** — an ecosystem
namespace for installable Claude plugins. It currently serves the
[`cadrumo`](https://github.com/nevenincs/cadrumo) Spanish-tax assistant plugin;
future plugins are additional `plugins[]` entries under the same `neve`
marketplace name.

A Claude marketplace is a git repository carrying a
`.claude-plugin/marketplace.json` that lists one or more installable plugins.
At release time this directory is served from the public marketplace
repository; users add it once with `/plugin marketplace add nevenincs/neve-marketplace`
and then install any plugin as `<plugin>@neve` (e.g. `/plugin install cadrumo@neve`)
in Claude Code, or through the plugin browser in Claude Desktop / Cowork.

## Layout

- `.claude-plugin/marketplace.json` — the marketplace manifest, name `neve`.
  Each `plugins[]` entry sources a plugin from its subtree (today: the single
  `./plugins/cadrumo` entry).
- `plugins/cadrumo/` — the plugin tree the marketplace serves. **Generated, never
  hand-edited.** Materialised from the single authored operator-harness source
  by the Cadrumo plugin generator, so the marketplace and the plugin cannot
  drift. Regenerated on every release.

## Regenerating the served plugin tree

The manifest and the `plugins/cadrumo/` subtree are both emitted by the harness
materialiser (`cadrumo_harness.materialise_marketplace`) from one source. Regenerate
before cutting a release so the served plugin matches the published `cadrumo`
wheel version.
