"""Persistence adapter namespace for profile and secure-storage backends.

This root package is a marker only; it exports no repository or envelope
classes. Concrete persistence surfaces live in
:mod:`aeat.adapters.persistence.profile` for operator profile state and
:mod:`aeat.adapters.persistence.storage` for the SQL, blob, namespace, and
encrypted-envelope substrate.

Domain and application repositories depend on the focused storage facades when
they need concrete encrypted persistence. The package root stays import-light so
layout and CLI smoke tests can import the persistence layer without
materialising database, keyring, or migration machinery.
"""
