# Cross-version compatibility fixtures

This directory is the committed corpus of cross-version persisted-format
fixtures the compatibility-lifecycle governance gate
(`src/aeat/tests/test_compatibility_lifecycle_gate.py`) requires once the
codebase flips to the `RELEASED` compatibility regime.

It is **empty by design today.** The regime is `PRE_RELEASE`
(`aeat.core.COMPATIBILITY_REGIME`), the `no-legacy-compatibility` posture is
in force, and every persisted format's durability floor equals its current
version — so there are no pre-current shapes to keep readable and no
old-version fixtures to hold. Fabricating an old-shape fixture now would
violate `no-legacy-compatibility` (it would be maintained compatibility for a
version nothing released).

At the release checkpoint (the accepted flip commit that sets
`COMPATIBILITY_REGIME = RELEASED` and freezes
`aeat.core.RELEASED_FORMAT_FLOORS`), and thereafter whenever a persisted
format's version is bumped above its frozen released floor, a real fixture
captured from that older version is committed here under a per-format
subdirectory (`secure_object/`, `bundle/`, `archive/`) named by the version
it was written under. The coverage harness then asserts a fixture exists for
every version from the frozen floor up to the current version, so a bump that
strands an older shape fails the gate.
