---
tags:
  - '#adr'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:6e073096cc7933c76025e4c121f037310b969840126d034981afa1dec1f0a121'
related:
  - "[[2026-07-13-data-output-standardization-research]]"
---

# `data-output-standardization` adr: `Data output location and naming standardization` | (**status:** `accepted`)

## Problem Statement

Every category of generated data — durable outputs, on-disk caches, logs,
diagnostic dumps, temp/scratch staging, test artifacts, and dev-tool
generators — currently decides its own location and naming. The six-axis
discovery (see related research) found: ~22 of ~29 settings-declared output
directories default to `PROJECT_ROOT/var/...`, which resolves inside
site-packages on an installed run, while only 7 destinations use the
installed-run-aware state root; two durable caches live loose in the shared
OS temp directory (one with no settings authority at all); artifact naming is
split across the retired `aeat` product brand and `cadrumo`; growth lifecycle
(rotation/TTL/retention) exists for 3 artifact families and is absent for 7;
agent/dev scratch has no mandated location, naming schema, or gitignore
coverage; and the test suite redirects output dirs through ~3 divergent
ad-hoc fixture families. The project pollutes the operator machine, the OS
temp dir, and the repo root with unmanaged, inconsistently-named artifacts.

## Considerations

- The installed-run state-root seam already exists and is accepted: the
  claude-ecosystem-packaging decision moved `cadrumo_local_storage_root` (and
  tokens/logs/secrets/blobs/audit/db) to a platform user-data dir on
  installed runs, keeping `PROJECT_ROOT/var/storage` for the dev loop. This
  ADR extends that derivation; it does not replace it.
- The product-identity doctrine (cadrumo-product-authority-names) classifies
  by ownership/referent: app-owned artifact names are `cadrumo`/`CADRUMO`;
  `aeat` names only the tax authority, its evidence, and its protocol.
- `no-legacy-compatibility` mandates hard-cut renames: old names are deleted
  or refused, never bridged. The storage-namespace refusal
  (`_namespace_registry.py` refusing `aeat.`/`aeat-test.`) is the precedent.
- `sensitive-financial-data-secure-storage-only` already governs sensitive
  bytes; this ADR governs everything that legitimately lives OUTSIDE the
  encrypted store (caches, logs, staging, exports, scratch).
- Managed-lifecycle exemplars already in-tree: LLM run-telemetry
  (retention-days prune), status cache (TTL), workflow-runs (rotation).
- The atomic-write pattern exists in four dialects of varying strength; the
  master-key variant (`O_EXCL`, 0o600, fsync, pid+token tempname) is the
  strongest.

## Considered options

- **O1 — Per-surface spot fixes** (rename the stale prefixes, move the two
  temp caches, leave the rest): cheapest, but leaves the split-brain root
  defect and the lifecycle vacuum untouched; rejected.
- **O2 — Single root taxonomy, all output dirs derived from the state root,
  with per-category lifecycle declarations and a hard-cut naming schema**
  (chosen): one derivation seam, one naming authority, gate-enforceable.
- **O3 — Platformdirs-style multi-root split** (separate OS-native
  data/cache/log/state roots per category): most OS-idiomatic, but
  fragments the operator's mental model ("where is my Cadrumo data") across
  4+ OS locations, complicates backup/archive/GDPR-export flows that today
  assume one root, and multiplies the test-isolation surface; rejected — the
  taxonomy lives UNDER the one root instead.

## Constraints

- Pre-release, zero-legacy regime: no migration of existing on-disk artifacts;
  old locations/names are abandoned or refused, never read.
- The dev checkout loop must keep working with repo-relative defaults
  (`PROJECT_ROOT/var/storage` root) so gitignore and developer muscle memory
  survive.
- Two-root env-var reality during the transition: renames of `AEAT_*`-prefixed
  app-owned SETTINGS fields ride the per-field adjudication table (R6) and
  must sweep docs, locales, error suggestions, and the agent harness per the
  cli-pull-and-file-standard lesson (conformance gates do not scan every
  surface).
- Registry loader cache changes must preserve the cross-process/xdist sharing
  semantics (`registry_disk_cache_enabled` fingerprint keying).
- The relocation-atomicity and apidocs-scaffold disciplines apply to any
  module moves this campaign performs.

## Implementation

**R1 — One root, five categories.** `cadrumo_local_storage_root` remains the
single operator-facing root (platform user-data installed, `var/storage`
checkout). A category taxonomy lives under it: `state` (existing secrets,
blobs, audit, tokens, buckets), `cache/<name>`, `logs`, `exports`, and
runtime `staging` (OS temp, always context-managed). Every settings dir field
whose default is currently `PROJECT_ROOT/var/...` moves into the state-root
derivation table (`_STATE_ROOT_DERIVED_DIRS` generalised): explicit env
overrides keep working, but the DEFAULT for every output dir derives from the
root. `PROJECT_ROOT`-anchored output defaults are eliminated. The dormant
`cadrumo_submission_browser_trace_dir` / `cadrumo_status_browser_trace_dir`
pair is deleted (no consumer; no-dormant discipline) and re-introduced only
when a writer lands. The vestigial-vs-live status of each `var/financial/*`
catalogue dir is verified during planning; vestigial fields are deleted, live
ones derived.

**R2 — No durable artifact in the OS temp dir.** The corpus text cache gains
a settings field and moves to `<root>/cache/corpus-text/` (scoped per user by
construction); the registry disk pickle's production default moves from
`gettempdir()` to `<root>/cache/registry/` (the test-only redirect env var
stays); both filenames rename `aeat_*` → `cadrumo_*`. The registry cache dir
gains fingerprint-count eviction (keep newest N); the corpus cache gains a
version/size guard. The OS temp dir remains legitimate ONLY for
context-managed, self-cleaning staging (`TemporaryDirectory`/`mkstemp` inside
`with`/try-finally), which is exempt because it cannot outlive the process.

**R3 — Declared lifecycle per artifact family.** Every durable generated
family declares exactly one lifecycle: rotation (logs — `cadrumo.log` moves
to a size-capped rotating handler), TTL (status cache, unchanged),
retention-days prune (run-telemetry precedent extended to LLM cache, LLM
usage JSONL, run traces, wallet diagnostic dumps), or explicitly
unbounded-by-design (audit/evidence surfaces, documented). A structural test
enumerates settings dir fields and asserts each maps to a declared lifecycle
class — new fields fail the gate until classified.

**R4 — Naming schema, hard-cut.** App-owned generated-artifact names use the
`cadrumo` stem: temp prefixes `cadrumo-<purpose>-` (rename `aeat-secret`,
`aeat-workbook-`, `aeat-xls-conversion-`, `aeat-review-package-`,
`aeat-scale-bench-`), cache files `cadrumo_<name>` (rename both temp-cache
filenames), CWD provenance literals `.aeat-ledger-*`/`.aeat-manual-ledger`
rename to `cadrumo-ledger-*`/`cadrumo-manual-ledger` marker forms. Directory
stems under the root stay English generic for framework concepts and Spanish
for AEAT-domain nouns per the existing stem rule; the export-filename schema
is fixed as `modelo-<id>-<year>-<period>` with canonical AEAT period tokens
(e.g. `modelo-303-2026-1T`), used by tests and any future default composer.
No aliases, no read-tolerance of old names.

**R5 — One scratch convention.** Repo-root `scratch/` is the sole mandated
dev/agent scratch location, with schema
`scratch/<yyyy-mm-dd>-<owner-or-session>-<label>/` for directories and the
same stem for loose files; `.gitignore` keeps ignoring all of it, gains a
`.runtime-*/` pattern (the ad-hoc `.runtime-sNN-*` convention is retired and
its existing dirs cleaned up), repairs the dead `src/cadrumo/...` corpus-manual
rules to `src/cadrumo/...`, and broadens root-level scratch patterns so
one-off scripts/dumps cannot land tracked. The currently tracked repo-root
run artifacts (`revert.patch`, `rail-snap.md`, `add_frontmatter.py`,
`test_docs_output.txt`, `scratch_pathspec.txt`) are deleted from tracking.
Naked `test_*.py` under `scratch/` are deleted (stale imports) — the
tests-topology rule already forbids their shape.

**R6 — Env-var prefix adjudication.** The settings-field rename wave migrates
app-owned `AEAT_*` fields to `CADRUMO_*` per an ownership table authored in
the plan: browser control, proxy/rate policy, auth timeout/policy flags, and
`AEAT_IVA_CATALOGUE_ROOT` migrate (app-owned controls); authority referents
(base/sede/status URLs, template paths) stay `AEAT_*`; identity-adjacent
fields (`aeat_certificate_*`, `aeat_clave_*` DNI/NIE) are adjudicated
per-field with referent reasoning recorded. Renames are hard-cut and added to
the dotenv exclusion set only when they were product-state-selecting.

**R7 — One atomic-write helper.** The four atomic-write dialects converge on
one shared core helper offering two tiers: standard (NamedTemporaryFile
sibling + fsync + replace + parent fsync) and hardened (0o600, `O_EXCL`,
pid+token name — the master-key pattern) for secret-bearing or multi-writer
targets. The weak no-fsync variants (bucket pointer, outbound local store,
bucket manifest) migrate to it.

**R8 — Test-output isolation converges.** One public canonical isolation
surface (promoted per the top-level-reexports rule) replaces the ~22
copy-pasted `_isolated_cli_backend` fixtures and the `_isolated_storage`
family; it derives every output dir from one tmp root so a new settings dir
field is a one-site change, with a structural test asserting the fixture
covers every settings dir field. The two collection-time
`cadrumo-pytest-<pid>` roots unify into one helper that registers cleanup.
Raw `gettempdir()` use in tests is confined to the white-box registry-cache
tests that assert on the real cache location.

## Rationale

The research's D1 finding is the root cause of most scatter: the project
already DECIDED (claude-ecosystem-packaging) that durable state must not
live under `PROJECT_ROOT` on installed runs, but applied it to only 7 of ~29
destinations — R1 finishes that decision rather than inventing a new one.
The two OS-tempdir caches (D2) are the only writers that can pollute a
shared host and collide across users/CI; settings-derived cache locations
with eviction (R2) close both. Lifecycle-by-declaration (R3) generalises the
three managed exemplars the codebase already ships instead of importing a new
mechanism. The naming rulings (R4, R6) apply the accepted cadrumo ownership
doctrine to the artifact surface the rename campaign did not sweep, using
the hard-cut precedent already in-tree. R5 formalises what `scratch/` already
is de facto — the swarm's working area — and kills the parallel undocumented
`.runtime-s*` convention. R7 and R8 are consolidation of proven in-tree
patterns onto single authorities, the same shape as prior single-contract
campaigns (binding validation, period filter).

## Consequences

- Operators get one answer to "where does Cadrumo write": under the storage
  root, categorised; nothing durable in the OS temp dir; scratch only under
  `scratch/`. Uninstall/backup/GDPR-export story becomes tractable.
- The settings surface changes shape (defaults move; two dormant fields
  deleted; several fields renamed) — pre-release zero-legacy makes this
  cheap now and expensive later; doc/locale/harness sweeps are mandatory
  per rename (conformance gates do not cover every prose surface).
- The lifecycle gate and the fixture-coverage gate add two structural tests
  that future settings fields must satisfy — deliberate friction that keeps
  the taxonomy from rotting.
- Registry/corpus cache relocation touches the hottest load path; the
  xdist-sharing semantics must be preserved and re-proven, and the
  first run after the change cold-starts every cache (accepted, pre-release).
- The ~22-site test-fixture consolidation is wide but mechanical; it removes
  the 22-site manual sweep currently required per new dir field.
- Renaming `AEAT_*` policy fields is operator-visible configuration churn;
  the per-field adjudication table keeps authority-referent names stable so
  the churn is bounded to app-owned controls.
