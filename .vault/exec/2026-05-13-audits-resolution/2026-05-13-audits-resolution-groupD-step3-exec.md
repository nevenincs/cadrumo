---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-eliminate-shims-audit]]"
---

# audits-resolution group-d step-3

## scope

Plan row D3: replace the master-key keychain monkeypatch surface with
a real injection seam.

## changes

`src/aeat/adapters/persistence/storage/master_key/_master_key.py`:

- New `KeyringClient` protocol declares the three operations the
  provider depends on: `probe_backend()`, `get_password()`,
  `set_password()`.
- New `_RealKeyringClient` is the production default that wraps the
  third-party `keyring` module's calls plus the
  `fail.Keyring` / `null.Keyring` no-op detection.
- `KeyringMasterKeyProvider.__init__` accepts an optional `client:
  KeyringClient | None`; the production default is
  `_RealKeyringClient()`.
- `_probe_backend` is now an instance method that delegates to the
  client; `get_master_key` routes every keyring call through
  `self._client`.
- `get_master_key_provider` factory threads an optional
  `keyring_client: KeyringClient | None` through to the
  constructed provider.

`src/aeat/adapters/persistence/storage/master_key/_test_master_key.py`:

- New `_FakeKeyringClient` real-type stand-in carries a `(service,
  username) -> password` dict plus optional probe / get / set
  overrides. Every monkeypatch.setattr call site that previously
  patched `keyring.get_password`, `keyring.set_password`,
  `keyring.get_keyring`, or `KeyringMasterKeyProvider._probe_backend`
  now constructs an appropriate `_FakeKeyringClient` and either
  passes it directly to `KeyringMasterKeyProvider(client=...)` or
  routes it through `get_master_key_provider(keyring_client=...)`.

The eight rewritten tests cover: malformed-stored-value rejection,
wrong-size value rejection, set_password failure, no-op-backend
refusal, per-service cache isolation, round-trip disagreement
detection, KEYRING-backend failure propagation, AUTO fallback
when keyring is unavailable, AUTO refusal when the keyring is
locked, and AUTO file-fallback when locked+file exists.

## verification

`grep -n 'monkeypatch.setattr'
src/aeat/adapters/persistence/storage/master_key/_test_master_key.py`
returns nothing.

`pytest src/aeat/adapters/persistence/storage/master_key/ -q`
returns 50 passed plus 1 skipped (the POSIX-only file-mode test).
