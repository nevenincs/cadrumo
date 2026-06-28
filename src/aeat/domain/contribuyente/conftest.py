"""Domain-profile test fixtures.

Profile keys are compiled from the wizard catalogue and registered into the
domain registry when the wizard package is imported. Import the real package
here so domain-profile tests are not order-dependent on broader suite startup.

Importing :mod:`aeat.application.wizard` seeds the :class:`ProfileKey` registry
through :func:`aeat.domain.contribuyente._keys.register_profile_keys`.
"""

from __future__ import annotations

from ...application import wizard as _wizard  # noqa: F401
