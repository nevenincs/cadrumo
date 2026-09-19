---
tags:
  - '#reference'
  - '#ledger-action-test-topology'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:a8cae8d8ae52350f3381e0d45c3ffca3738e6b4386bc430b3508368f6a76cafb'
related: []
---

# `ledger-action-test-topology` reference: `Ledger action persistence-test ownership`

The live import census identified the manual ledger action integration family
as encrypted profile-persistence coverage. The governing ports-inversion ADR
and the existing `filing-test-topology` reference establish that concrete
secure-storage tests belong under the profile persistence adapter owner.

## Summary

The application-ledger consumers used the concrete fixture symbols
`_BUCKET_ID`, `_OTHER_BUCKET_ID`, `_repositories`, and `_create_manual_row`
from `ledger_action_persistence_support`. Those names are test-only storage
construction details, not application contracts, so they remain private and
are imported only by colocated profile adapter tests.

The complete dependent family is relocated to the profile persistence test
package, with `ledger_action_persistence_support` and
`remove_draft_revision_support` as sibling implementations. Application
relative imports in the moved tests resolve to their original application
modules through absolute imports; the two persistence support modules use
sibling imports. The application test `conftest.py` remains for tests that stay
inward and owns an independent local bucket value, while the profile test
`conftest.py` owns the isolated ledger runtime and `secure_objects` fixture for
the relocated integration family.

The resulting boundary has no application-to-private-support imports and no
stale application test paths. Existing assertions and concrete repositories
remain unchanged; only test topology and import roots changed.
