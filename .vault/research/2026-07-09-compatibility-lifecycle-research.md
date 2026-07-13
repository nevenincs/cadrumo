---
tags:
  - '#research'
  - '#compatibility-lifecycle'
date: '2026-07-09'
modified: '2026-07-10'
related: []
---

# `compatibility-lifecycle` research: `compatibility-lifecycle checkpoint governance`

## Findings

Read-only grounding pass (authorized fable architecture decision) over the durability
substrate and the governing rules, feeding ADR `2026-07-09-compatibility-lifecycle-adr`.

**The transition is ungoverned.** The `released-data-durability` campaign installed the
per-format forward-gating mechanism but left the pre-release → post-release posture flip
without an owner, trigger, or enforcement:
- Secure-object: `SECURE_OBJECT_DURABILITY_FLOOR = 1`, `register_secure_object_schema_upgrader`
  (empty registry), chain-upgrade on read — `src/aeat/adapters/persistence/storage/_schema_lineage.py:45,50`.
- Bundle: `BUNDLE_SCHEMA_VERSION = 3`, `BUNDLE_DURABILITY_FLOOR`, `BUNDLE_PAYLOAD_UPGRADERS`
  (empty) with the upgrade hop running BEFORE strict validation —
  `src/aeat/application/user_profile/_bundle.py:52,57,65`.
- Archive: `_ARCHIVE_SCHEMA_VERSION = _ARCHIVE_DURABILITY_FLOOR = 2`, a floor/ceiling gate with
  NO upgrade dispatch, pinned floor==current by
  `test_archive_schema_lineage.py::test_floor_is_pinned_to_current_until_a_version_aware_reader_exists`
  — `src/aeat/application/bucket_maintenance/_service.py:103,109`.

**The floor-pin is the precedent shape.** That test binds future authors ("a version bump
cannot land without a conscious, gate-enforced decision") while reading no old shapes and
migrating nothing — establishing that a dormant gate is not maintained-compatibility code.

**`no-legacy-compatibility` already carves out the compatible category** it forbids
maintaining: "a `max_supported_version` ceiling that refuses a FUTURE shape is
forward-compatibility [kept]"; "CREATE is not migration". A regime constant + empty
registries + test-time assertions fall in that category — policy metadata, not read-tolerance.

**`Settings` is the wrong home for the regime marker.** `src/aeat/core/config.py` documents
`Settings` as "populated from environment variables and `.env`" with `override_settings()` —
env/machine/test-varying and monkeypatchable, unfit for a compliance regime that must be a
property of the codebase commit and enforced in CI.

**Conclusion feeding the ADR:** decide the transition now as a one-way repo-committed core
constant (`COMPATIBILITY_REGIME`) plus a version-milestone tripwire, with regime-switched
lineage gates that are dormant (no-op) today but whose `RELEASED` branch is proven by pure
synthetic-input tests — and a companion rule that leaves `no-legacy-compatibility` verbatim
for the pre-release regime. See `[[2026-07-08-released-data-durability-adr]]` for the
mechanism this governance switches.
