---
tags:
  - '#adr'
  - '#locale-catalogue-sharding'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:d32278cd02b2071e28115c3dd2b861ceb991354d0d48493d5ea3ab94cd2ed9ae'
related:
  - '[[2026-08-16-locale-catalogue-sharding-research]]'
  - '[[2026-08-04-modelo-localization-cascade-adr]]'
  - '[[2026-08-07-dev-harness-bleed-adr]]'
  - '[[2026-07-21-locale-key-resolution-adr]]'
---

# `locale-catalogue-sharding` adr: `domain-sharded locale catalogue architecture with lazy on-demand loading and dual fallback` | (**status:** `accepted`)

## Problem Statement

The centralized runtime locale catalogues at `src/cadrumo/locales/{es,en,ca,hu}.yml` have expanded to over 46,900 translation keys and 86,000 lines (3.3 MB to 4.0 MB per file) following the migration to canonical dotted schema keys in `2026-08-04-modelo-localization-cascade-adr`. Over 89.1% (41,805 keys) of these files represent Modelo Casilla schema text across 73 distinct tax forms, with the remaining 10.9% representing CLI, error, wizard, flow, and domain copy.

Maintaining these monolithic files creates severe engineering friction:
1. High git merge conflict frequency when multiple developers or autonomous agents concurrently modify unrelated Modelos or CLI strings.
2. Full parse latency (0.65s to 1.55s per file under C loaders; 9s under pure Python) paid on startup and test execution even when only a handful of CLI keys are queried.
3. Heavy write churn where editing a single translation leaf forces reading, modifying, and rewriting an entire 4 MB file.
4. IDE editor degradation and unwieldy PR diffs across 86,000 lines of YAML.

The system requires a modular sharding architecture that partitions the locale corpus into manageable domain- and Modelo-scoped files, provides smart routing based on dot-notation targets, implements on-demand lazy loading, and guarantees a seamless rollout via dual-tier fallback so that downstream consumers notice zero disruption.

## Considerations

- The canonical dotted key contract (`modelo.schema.<modelo-id>...`, `cli.<group>...`, `errors.<domain>...`) established in `2026-08-04-modelo-localization-cascade-adr` must remain unchanged.
- Revision schema objects must remain strictly language-neutral; translations must not be moved back into registry TOML trees (`aeat-locales-cli.md`).
- Key-to-file routing must be completely deterministic, bijective, and transparent to callers of `tr()`, `lookup_translation()`, and `resolve_modelo_localization()`.
- Rollout must be zero-downtime: during the transition, active campaigns may still write to monolithic catalogues; the loader must support dual-tier fallback between monolithic files and sharded directories.
- On-demand lazy loading must only parse and allocate memory for shards containing requested keys, avoiding loading all 41,805 Modelo schema keys during CLI execution.
- Single-leaf edits (`dev.locales set`, `remove`) must read and write only the targeted shard file under `catalogue_write_guard`.
- The `dev.locales` maintenance harness (`scaffold`, `audit`, `status`, `set`, `remove`, `allow-identical`) must manage the sharded tree natively.

## Considered options

- **Option A: Retain monolithic files with enhanced in-memory caching.** Rejected: does not solve git merge collisions, 86k-line diff fatigue, or lock contention during concurrent write operations.
- **Option B: Move translations back into per-modelo registry TOML.** Rejected: violates `2026-08-04-modelo-localization-cascade-adr` and `aeat-locales-cli.md`, re-coupling regulatory schema compilation with natural-language text.
- **Option C: Big-bang cutover without dual fallback.** Rejected: risks broken consumer paths during campaign transitions if ongoing tasks commit to monolithic files while sharded tooling is deploying.
- **Option D: Domain- and Modelo-sharded catalogues with smart routing, on-demand lazy loading, and dual-tier rollout fallback.** Chosen: shards catalogues under `locales/<locale>/<domain>.yml` and `locales/<locale>/modelo/schema/<modelo_id>.yml`, implements smart dot-notation routing, loads shards on-demand, and transparently falls back between monolithic files and shards during rollout.

## Constraints

- Dotted key syntax in production code is invariant. Zero call sites of `tr()`, `resolve_modelo_localization()`, or `lookup_translation_entry()` may change.
- Strict parity across all four supported languages (`es`, `en`, `ca`, `hu`) must be maintained across all shards.
- Spanish (`es`) remains the mandatory, authoritative source locale.
- The translation honesty allowlist `_intentional_identical.json` remains unified at the root of `src/cadrumo/locales/`.
- The catalogue write guard (`catalogue_write_guard`) must serialize writers and detect out-of-band modifications across sharded files.

## Implementation

### D1 - Shard locale catalogues into deterministic domain and Modelo subdirectories

The monolithic files `src/cadrumo/locales/{es,en,ca,hu}.yml` are structured into sharded directory trees under `src/cadrumo/locales/<locale>/`:

```text
src/cadrumo/locales/
  _intentional_identical.json
  es/
    cli.yml
    application.yml
    errors.yml
    wizard.yml
    flows.yml
    profile.yml
    docs.yml
    adapters.yml
    common.yml
    modelo/
      general.yml
      schema/
        100.yml
        200.yml
        303.yml
        ...
        <modelo_id>.yml
  en/ ... (identical shard tree)
  ca/ ... (identical shard tree)
  hu/ ... (identical shard tree)
```

Top-level domains with significant key volume receive dedicated YAML files. Modelo schema keys (`modelo.schema.<id>.*`) are sharded per Modelo into `modelo/schema/<id>.yml`. Small namespaces are grouped in `common.yml`.

### D2 - Smart dot-notation key routing

A canonical router maps dotted translation keys to shard file paths:

```python
def route_key_to_shard(dotted_key: str) -> Path:
    parts = dotted_key.split(".")
    root = parts[0]
    if root == "modelo":
        if len(parts) > 2 and parts[1] == "schema":
            return Path("modelo") / "schema" / f"{parts[2]}.yml"
        return Path("modelo") / "general.yml"
    if root in ("cli", "errors", "wizard", "application", "flows", "docs", "profile", "adapters"):
        return Path(f"{root}.yml")
    return Path("common.yml")
```

Loading all shards under `locales/<locale>/` and deep-merging their parsed mappings reconstructs the unified logical dictionary with 100% equivalence to the flat namespace.

### D3 - On-demand lazy shard loading and memory optimization

The runtime catalogue loader (`cadrumo.core.i18n._render` / `LazyLocaleCatalogue`) resolves translations on-demand:
1. Fast in-memory cache lookup for `(locale, dotted_key)`.
2. If absent, route `dotted_key` to target shard via `route_key_to_shard(dotted_key)`.
3. If target shard is unparsed, parse only that shard file into memory and mark loaded.
4. Unrequested Modelos (e.g. Modelo 100 with 23,964 keys) remain completely unparsed and unallocated in memory during CLI and unrelated form executions, reducing startup memory and parse latency by >90%.

### D4 - Dual-tier rollout fallback

To ensure zero consumer breakage and support ongoing parallel campaigns:
- The loader supports dual mode: if a key is not yet present in the sharded directory (or during transition), it seamlessly checks the monolithic `<locale>.yml` file.
- Writing tools (`dev.locales set`, `scaffold`) write directly to the sharded structure, with a sync utility to update the legacy monoliths if required during transitional phases.
- Once cutover is complete across all active branches, legacy monolithic `.yml` files are deleted cleanly.

### D5 - Maintenance harness (`dev.locales`) integration

`LocaleManager` in `dev/locales/manager.py` is updated to:
- `load_locale(locale_code)`: Reads and deep-merges all `*.yml` shards in `locales_dir / locale_code` (or falls back to monolithic file if directory absent).
- `set_locale_value(locale, dotted_key, value)`: Resolves the exact shard via `route_key_to_shard(dotted_key)`, reads only that shard under `catalogue_write_guard`, inserts the leaf, and atomically rewrites only that shard.
- `set_locale_values(locale, values)`: Groups updates by target shard and executes targeted rewrites.
- `remove_locale_value(locale, dotted_key)`: Removes the leaf from the target shard, pruning empty parent mappings and removing empty shard files if no keys remain.
- `scaffold()`: Scans codebase keys, partitions keys across target shards, and updates each shard with preserved existing translations, prune extra keys, and proper formatting.

## Rationale

Partitioning the 46,900 keys across ~82 domain- and Modelo-specific files directly eliminates git merge collisions and tooling latency while keeping the entire localization architecture 100% compatible with existing runtime key resolution.

Benchmarks in `tmp/smoke_test_sharding.py` and `tmp/test_lazy_loader.py` prove:
- **100% Parity:** Exact zero-error match across all 46,900 keys in all 4 locales.
- **On-demand Lazy Speed:** CLI help lookup parses only `cli.yml` in 19.37 ms (vs 1,548 ms for monolith), leaving 44,779 unrelated keys unparsed.
- **Single-Leaf Writes:** Reduced from 1,500 ms to 35.58 ms (42x faster).
- **Safe Rollout:** Dual-tier fallback successfully resolves keys from monoliths or shards interchangeably.

## Consequences

- The monolithic `src/cadrumo/locales/{es,en,ca,hu}.yml` files transition to sharded directory trees under `src/cadrumo/locales/{es,en,ca,hu}/`.
- All runtime key derivation, translation lookups, and domain facades (`tr`, `lookup_translation`, `resolve_modelo_localization`) continue functioning with zero caller changes.
- Startup latency and memory consumption drop significantly due to on-demand shard loading.
- Developer CLI commands (`python -m dev.locales set`, `remove`, `scaffold`, `audit`, `status`) operate at shard granularity under write guard.
- Git blast radius for localization edits is bounded to specific feature domains and tax forms.
