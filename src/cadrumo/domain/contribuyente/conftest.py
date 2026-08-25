"""Domain-profile test fixtures.

Profile keys are compiled from the wizard catalogue and registered into the
domain registry when the wizard package is imported. Import the real package
here so domain-profile tests are not order-dependent on broader suite startup.

Importing :mod:`application.wizard` seeds the :class:`ProfileKey` registry
through :func:`domain.contribuyente.register_profile_keys`.
"""

from __future__ import annotations

from ...application.wizard import compiler as _wizard

# Importing the wizard module registers the real profile-key catalogue; retain
# that side effect while making the intentionally unused binding explicit.
del _wizard
