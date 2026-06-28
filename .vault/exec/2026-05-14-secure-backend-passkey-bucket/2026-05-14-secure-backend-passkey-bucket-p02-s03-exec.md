---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P02.S03'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P02.S03

Implement the keystore separation contract at
`src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py`. The
contract enforces the ADR-1 section 3 / ADR-2 section 2 invariant that
the KEK / DEK / passphrase artefacts never co-locate with the ciphertext
tree.

- Created: `src/aeat/adapters/persistence/storage/bucket/_keystore_paths.py`
- Created: `src/aeat/adapters/persistence/storage/bucket/test_keystore_paths.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/__init__.py`

## Description

`keystore_root(root)` returns `<root>/keystore/` as a sibling of
`<root>/buckets/`. `keystore_path(root, bucket_id)` returns
`<root>/keystore/<bucket_id>/`; the bucket id is validated against the
same empty / path-separator rejection used in `_layout.py` so the
keystore subpath cannot escape its parent.

`validate_keystore_separation(root, bucket_id, configured_keystore=None)`
is the fail-closed validator. It resolves the configured keystore path
(or the default `keystore_path` if none is provided) and rejects any
resolution that lands under either `<root>/buckets/` or under the
per-bucket `db/` directory. `Path.resolve(strict=False)` is used so the
check is OS-portable and independent of whether the directories exist
yet (configuration validation runs before provisioning).

## Open-question default honoured

The plan's "Keystore concrete path layout" open question is resolved per
the orchestrator default: keystore directory at
`<aeat-root>/keystore/<bucket-id>/`, sibling to `<aeat-root>/buckets/`.
OS-keystore (Keychain Services, DPAPI, libsecret) integration is deferred
to P03 and is independent of this filesystem-side helper.

## Tests

`test_keystore_paths.py` (8 tests; `pytest.mark.unit` +
`pytest.mark.domain_persistence`):

- `keystore_root` sits as a sibling of `buckets/`.
- `keystore_path` resolves the per-bucket subdir.
- Empty / path-separator bucket ids are rejected.
- Default separation validates.
- A path nested under the buckets parent is rejected.
- A path nested under the per-bucket `db/` directory is rejected.
- An external path (e.g. `<root>/elsewhere/<bucket>`) passes.

`uv run pytest src/aeat/adapters/persistence/storage/bucket/test_keystore_paths.py -x -q` :
8 passed.

`uv run ruff check` and `uv run ty check` clean on the new modules and
on the modified `__init__.py`.
