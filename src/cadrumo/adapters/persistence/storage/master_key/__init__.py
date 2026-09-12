"""Inert namespace for master-key providers, sessions, and KDF helpers.

The defining submodules own the provider family, active-session operations,
KDF parameters, and safety guards. Callers import those contracts directly;
the package initializer exports no symbols. The shared-master providers, their
backend resolver, and its passphrase-callback alias are deleted: the active master key is the
unlocked bucket's own data key, so a process-wide key store had no
reader.

Recovery is not exported here at all. Enrolment and restore are
per-profile custody operations owned by
:mod:`cadrumo.adapters.persistence.storage.custody`, and the
shared-master wrapping primitives that once mirrored one process-wide
key under a recovery key have been deleted rather than left standing:
nothing wrote the artefact they read, so they guarded no material this
build could produce. Importing this package does not resolve providers, acquire
keys, unwrap recovery material, or write custody files.

The per-profile acceleration receipt that carries authenticated session state
across processes is NOT here: it belongs to
:mod:`cadrumo.adapters.persistence.storage.custody`, which owns per-profile
password custody.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
