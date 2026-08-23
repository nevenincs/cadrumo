---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:39e14feb0998a83081cc7b9664f357f42ab345203bbf12387243251cde83cd1f'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# `secure-storage-performance-hardening` audit: `W02.P03.S09 lazy node kernel review`

## Scope

Independent intent, safety, and quality review of `W02.P03.S09`. The review
covered the accepted campaign ADR, research, reference, and plan; the reusable
lazy-node kernel and root registration migration; focused real-import fixtures;
and the vendored Click/Typer resolution protocol. I exercised the focused test
lanes and Ruff, inspected every live `LazySubcommand` construction site, and
ran an external adversarial probe whose declared optional package raised a
same-namespace missing-internal-module error.

## Findings

### optional-dependency-classification | high | A missing internal module in an optional package is silently degraded

`_dependency_is_explicitly_optional` in
`src/cadrumo/entrypoints/cli/_command_suggestions.py` accepts both an exact
declared dependency and every dotted descendant of it. Consequently a loaded
optional package that raises `ModuleNotFoundError(name="declared.internal")`
is treated exactly like the declared top-level package being absent. An
external probe using `LazyFactoryTarget(...,
optional_dependencies=frozenset({"declared"}))` observed the loader returning
the unavailable surface (`DEGRADED x`) instead of surfacing the internal
defect. The committed negative fixture names an unrelated transitive package,
so it does not bite on this same-namespace failure mode. This violates the
Step's fail-loud rule and can hide a corrupt or incomplete optional
installation behind a plausible unavailable-command response.

Resolution evidence (2026-08-23): fixed in the reviewed working tree.
Classification now requires exact membership of `ModuleNotFoundError.name` in
the target's declared dependency set. A real installed-package fixture raises
its own dotted missing internal module and the focused test proves the original
`ModuleNotFoundError` escapes. The separate unrelated-transitive-dependency
case remains covered. External reproduction now refuses loudly rather than
degrading. Finding closed.

### exhaustive-nested-materialisation | high | Full-tree consumers cannot drain nested lazy nodes

`materialise_lazy_subcommands` in
`src/cadrumo/entrypoints/cli/_command_suggestions.py` traverses only Typer's
`registered_groups` and indexes each Typer node by `node.info.name`. A nested
`LazySubcommand` is returned directly as a materialized Click command by
`CadrumoTyperGroup.get_command`; it is not added to its parent's Typer
`registered_groups`. The new token-by-token resolver and live walker can reach
that node, but `full_command_tree`, operator-surface drift, and JSON-schema
conformance still call the old materializer under an explicit promise of
exhaustiveness. Once S13/S14 register nested lazy descendants, those consumers
can report success while omitting entire descendant families. The focused S09
test proves `resolve_command_path`, but does not prove the supported full-tree
materialization boundary.

Resolution evidence (2026-08-23): fixed in the reviewed working tree.
`materialise_lazy_subcommands` now traverses the actual vendored Click
`list_commands` / `get_command` graph with command-identity cycle protection.
A two-level lazy fixture invokes only the full materializer and proves both the
parent and nested loader are materialized. Finding closed.

### final-re-review | low | No open findings remain after the corrective pass

The final diff retains explicit module-and-attribute targets, deterministic
loader/callback/policy/command identity and caching, collision-refusing
registrations, branch-specific child registry keys, token-by-token resolution
without sibling enumeration, deferred optional-extra inventory loading,
fail-loud required-dependency behavior with the original exception as cause,
and vendored Click/Typer protocol use. The focused loader, census, and loading
contract lanes pass 22 tests; scoped Ruff passes. No production code was
modified by this review.

## Recommendations

- Match optional degradation against exact declared `ModuleNotFoundError.name`
  values only. Add a real-import negative fixture in which the optional target
  raises a missing dotted child of its own declared package, and assert the
  original `ModuleNotFoundError` (or the typed required refusal with that exact
  cause) escapes.
- Rework `materialise_lazy_subcommands` to drain nested nodes through the
  vendored Click `list_commands` / `get_command` protocol, or an equivalently
  complete explicit registry graph. Add a two-level lazy fixture that calls
  only `materialise_lazy_subcommands` and proves the grandchild loader was
  materialized and visible to an exhaustive consumer.
- Both recommendations are implemented and verified; no follow-up action is
  open for S09.
