---
tags:
  - '#research'
  - '#compatibility-checkpoint'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-09-compatibility-lifecycle-adr]]"
  - "[[2026-07-08-released-data-durability-adr]]"
---

# `compatibility-checkpoint` research: `persisted-format readiness for the released-regime flip`

The release calculator proposes `1.0.0`, and the compatibility tripwire refuses a
1.0 cut while the regime is pre-release, so the version bump and the durability
commitment are now one question: is every persisted format ready to have its
durability floor frozen? This pass enumerates the formats, their live versions and
floors, the machinery each carries, and how recently that machinery and those
shapes last moved. The picture is asymmetric. Three formats carry a complete
lineage tier, two durable formats carry none and cannot be enrolled, one versioned
format is undeclared entirely, and the enforcement substrate itself is one day old
on the main branch.

## Findings

### Ten persisted formats are declared; five are durable

`PERSISTED_FORMATS` (`src/cadrumo/core/compatibility_lifecycle.py:94-107`) declares
`secure_object`, `bundle`, `archive`, `bucket_dek`, and `bucket_manifest` as
durable, and `profile_session`, `login_throttle`, `config_reset_journal`,
`bucket_lock`, `bucket_output_language_hint` as regenerable. Only durable formats
may carry a frozen floor; `misclassified_floor_keys`
(`src/cadrumo/core/compatibility_lifecycle.py:139-154`) refuses a floor naming a
regenerable format.

### Three durable formats carry a complete lineage tier and a freezable floor

`secure_object` holds floor `SECURE_OBJECT_DURABILITY_FLOOR = 1`
(`src/cadrumo/adapters/persistence/storage/_schema_lineage.py:41`) with every
registered namespace at `SECURE_OBJECT_SCHEMA_VERSION_V1 = 1`
(`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:19`); ceiling
semantics and the empty per-hop upgrader registry are wired into the row decode and
repository read paths
(`src/cadrumo/adapters/persistence/storage/sql/_secure_object_row_codec.py:156,192,264,332`,
`src/cadrumo/adapters/persistence/storage/sql/secure_objects.py:210`). Current
version 1, freezable floor 1.

`bundle` holds `BUNDLE_SCHEMA_VERSION = 3` and `BUNDLE_DURABILITY_FLOOR = 3`
(`src/cadrumo/application/user_profile/_bundle.py:58,63`), with the supported set
derived as floor-to-current and an empty hop table walked at
`src/cadrumo/application/user_profile/_bundle.py:142`. Current version 3, freezable
floor 3.

`archive` holds `_ARCHIVE_SCHEMA_VERSION = 3` and `_ARCHIVE_DURABILITY_FLOOR = 3`
(`src/cadrumo/application/bucket_maintenance/_service.py:118,123`). This tier
deliberately carries no upgrade dispatch: archive version differences are
container-structural, so the floor is pinned equal to current until a version-aware
reader exists. Current version 3, freezable floor 3.

### Two durable formats carry no floor, no upgrader, and cannot be enrolled

`bucket_dek` and `bucket_manifest` are declared durable but have no
durability-floor constant, no upgrader registry, and no tier lineage gate.

`bucket_dek` is the wrapped-DEK document with `schema_version: Literal[1]` under a
strict frozen model
(`src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py:78`).
It refuses every direction of drift by field declaration alone. Losing the ability
to read it strands every byte in the bucket.

`bucket_manifest` declares `schema_version: int = Field(ge=1)`
(`src/cadrumo/adapters/persistence/storage/bucket/_manifest.py:91`) and is written
from a bare local literal, `manifest_schema_version = 2`
(`src/cadrumo/application/user_profile/_profile_repository.py:330`). There is no
named current-version constant, no floor, and no read-side version gate at all
beyond the lower bound, so a manifest stamped at any version loads.

The central enrollment invariant restricts a frozen floor key to the canonical set
`secure_object`, `bundle`, `archive`
(`src/cadrumo/tests/test_compatibility_lifecycle_gate.py:50,113-123`), so freezing
a floor for either format fails that gate today.

### No gate asserts that a durable format carries a floor

The enrollment invariant runs one way: every frozen floor must name a live tier.
Nothing asserts the converse, that every durable entry in `PERSISTED_FORMATS`
appears in a populated `RELEASED_FORMAT_FLOORS`. The predicate set
(`src/cadrumo/core/compatibility_lifecycle.py:110-154`) offers
`undeclared_persisted_formats`, `stale_persisted_format_declarations`, and
`misclassified_floor_keys`, and no durable-without-floor counterpart. A flip
freezing only the three tier formats therefore passes every gate green while two
durable formats, including the key document that unlocks the bucket, carry no
durability guarantee at all.

### One versioned persisted format is undeclared and passes by omission

`blob_manifest` is the only entry in the storage path registry carrying a
`schema_version`, declared with kind `BLOB_OBJECT`
(`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:1090-1096`;
`BLOB_MANIFEST_SCHEMA_VERSION = 1` at line 40). The enrollment gate discovers only
path definitions whose kind is `FILE`, plus three explicitly named non-file keys
(`src/cadrumo/tests/test_persisted_format_enrollment.py:56-74`), so `blob_manifest`
is invisible to discovery and absent from `PERSISTED_FORMATS`. It is a persisted
format that reached the main branch with no durability declaration, which is the
exact failure class that gate's own docstring states cannot occur by construction.

### Two evidence-bearing readers refuse on strict equality above the lineage policy

The ceiling-plus-upgrade policy is applied only on the SQL secure-object path. The
blob-manifest scan
(`src/cadrumo/adapters/persistence/storage/blob_store/_blob_store.py:443`) and the
attachment-manifest validator
(`src/cadrumo/adapters/persistence/storage/attachment.py:97`) each compare the
stored version for inequality against the current constant and refuse. Both
describe encrypted evidence bytes. Registering an upgrader for their namespaces
would not make an older record readable, because these readers reject before the
policy is consulted, so a frozen floor covering them would be a guarantee the read
paths do not honour.

### The enforcement substrate is one day old on the main branch

The entire compatibility-lifecycle and schema-lineage mechanism was removed from
the tree on 2026-07-17 by untargeted commits sweeping accumulated working-tree
changes, remained absent for eight days with no superseding decision record, and
was restored on 2026-07-25 in commit `e36927cf7b`. The restore was reconciled
against the intervening change rather than blind-reverted, and it retired an
undocumented exact-version replacement that had displaced the ceiling policy in the
interim. The substrate has therefore existed in its intended form on the main
branch for roughly one day, and has never run a full release cycle.

### A cosmetic rename bumped a durable format and raised its floor with it

Commit `34e04e3986` (2026-07-12, cutting sealed bundles to the Cadrumo product
name) raised `_ARCHIVE_SCHEMA_VERSION` from 2 to 3 and `_ARCHIVE_DURABILITY_FLOOR`
from 2 to 3 in the same change. The driver was a product rename, not a data-shape
need. Under the released regime that commit is illegal: the floor is frozen, so the
rename would have owed a version-aware archive reader, a committed v2 fixture, and
a restorability test. This is direct evidence of the durability cost the flip
imposes on ordinary refactoring work, measured on this codebase within the last
fortnight.

### The version and the regime are now coupled by the tripwire

`pyproject.toml:3` declares `0.2.1`. The release calculator computes `1.0.0` from
two correctly-labelled breaking-change footers (log at
`var/release/release-please.log`). The tripwire at
`src/cadrumo/tests/test_compatibility_lifecycle_gate.py:82-89` asserts the package
major stays below 1 while the regime is pre-release, reading the installed
distribution metadata or falling back to `pyproject.toml`. Applying the proposed
bump without flipping reds the suite by design. The version calculator takes no
input from durability state; the coupling is one-directional and deliberate.

### The flip commit has three constants, not two

Beyond `COMPATIBILITY_REGIME` and `RELEASED_FORMAT_FLOORS`, the coverage harness
ranges over a third flip-time constant recording each released format's current
version (`src/cadrumo/tests/test_compatibility_lifecycle_gate.py:59,97-110`), whose
key set is bound equal to the floors by its own gate. The fixture corpus root
`src/cadrumo/_data/compat_fixtures/` exists and is empty, as the pre-release
posture requires, since fabricating an old-version fixture before a real
post-checkpoint bump is barred.

### Option space the decision must choose between

Flip to the released regime at `1.0.0`, freezing the three tier floors. Or defer
the commitment, releasing the breaking changes as `0.3.0` under the pre-1.0
convention where breaking changes ride minor bumps, leaving the tripwire satisfied
and no floor frozen. Or flip at `1.0.0` only after the durable-format gap closes:
enroll `blob_manifest`, give `bucket_dek` and `bucket_manifest` a tier or
reclassify them, route the two strict-equality readers through the lineage policy,
and add the durable-implies-floor gate.

### Not investigated

Whether any installation outside the operator's own machines currently holds
persisted taxpayer data; the distributed install base and whether a released
artefact is already in third-party hands; whether the release tooling can be
configured to hold at the pre-1.0 line while the breaking-change footers stand; and
the Spanish retention horizon's interaction with a deferred flip beyond what the
prior durability record already establishes.

## Sources

- `src/cadrumo/core/compatibility_lifecycle.py:94-107,110-154`
- `src/cadrumo/adapters/persistence/storage/_schema_lineage.py:41`
- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py:19,40,1090-1096`
- `src/cadrumo/adapters/persistence/storage/sql/_secure_object_row_codec.py:156,192,264,332`
- `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py:210`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py:78`
- `src/cadrumo/adapters/persistence/storage/bucket/_manifest.py:91`
- `src/cadrumo/adapters/persistence/storage/blob_store/_blob_store.py:443`
- `src/cadrumo/adapters/persistence/storage/attachment.py:97`
- `src/cadrumo/application/user_profile/_bundle.py:58,63,142`
- `src/cadrumo/application/user_profile/_profile_repository.py:330`
- `src/cadrumo/application/bucket_maintenance/_service.py:118,123`
- `src/cadrumo/tests/test_compatibility_lifecycle_gate.py:50,59,82-89,97-123`
- `src/cadrumo/tests/test_persisted_format_enrollment.py:56-74`
- `pyproject.toml:3`
- `var/release/release-please.log`
- commits `e36927cf7b` (2026-07-25) and `34e04e3986` (2026-07-12)

Semantic code search was degraded during this pass, serving a fraction of the tree
while reporting itself healthy, so every finding above was established by direct
file read and targeted `rg`, and no absence claim rests on a search miss.
