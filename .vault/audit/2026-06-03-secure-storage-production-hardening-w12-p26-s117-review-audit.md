---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S117]]'
---

# `secure-storage-production-hardening` Code Review

## S117-001 | LOW | Session-store namespace constants were duplicated outside the registry

Initial audit found that `_session_store.py` hardcoded `aeat.outbound.aeat.auth.sessions` and schema version `1` even though the same namespace already existed as `AEAT_BROWSER_SESSION_NAMESPACE` in the central storage namespace registry. That left the session store vulnerable to schema, sensitivity, or namespace drift if the registry changed.

Resolution: `_session_store.py` now derives namespace, classification, and schema version from `AEAT_BROWSER_SESSION_NAMESPACE`.

Status: closed.

## S117-002 | LOW | Tests reached through a private session-store namespace constant

Initial audit found that the authenticator raw-payload helper used `_session_store._SESSION_NAMESPACE`, coupling test setup to an implementation detail and preserving the duplicate namespace surface.

Resolution: the helper now writes raw records through `AEAT_BROWSER_SESSION_NAMESPACE`, matching production code and keeping the namespace authority centralized.

Status: closed.

## S117-003 | INFO | Registry scanner now recognises central namespace constants imported by auth adapters

The namespace registry discovery test already audits production secure-object namespaces, but it missed the auth adapter's relative import spelling for central namespace constants. The scanner now recognises that import form, so future production code can use registered namespace constants without disappearing from the registry audit.

Status: closed.

## S117-004 | INFO | Runtime roundtrip proves encrypted storage and hashed lookup

The session-store roundtrip test uses the real active-bucket secure-object repository. It now asserts the stored row uses the registered namespace, session sensitivity, registered schema version, and a 32-byte hashed lookup key instead of the raw logical path.

Status: closed.

## S117-005 | INFO | Remaining rows stay open

S117 does not close the browser factory, site-health, export format, record-spec, or censo-live rows. Those remain pending as W12.P26.S118 through W12.P26.S122.

Status: open follow-up.

## S117-006 | LOW | Raw-payload helper duplicated session-store key normalization

Mandatory review found that the authenticator raw-payload helper wrote `path.as_posix()` directly even though production session-store calls routed through the store's key-normalization helper. If the logical key format changes later, the test helper could silently drift from production behavior.

Resolution: `_session_store.py` now exposes `logical_object_key()`, and the raw-payload helper uses it instead of duplicating the key derivation.

Status: closed.
