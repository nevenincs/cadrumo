"""Persistence adapters root package.

Marker module for the persistence layer. Concrete adapters live in
sibling subpackages: :mod:`aeat.adapters.persistence.profile` for
operator profile state and :mod:`aeat.adapters.persistence.storage` for
the SQL, blob, and envelope substrate.

This module uses :class:`SecureObjectRepository`, :class:`SensitivityClass`,
:class:`Envelope`, and :class:`StorageError`.
"""
