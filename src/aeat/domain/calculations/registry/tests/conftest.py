"""Pytest fixtures for domain calculations registry tests.

Importing :mod:`aeat.application.wizard` triggers the import-time
``register_profile_keys`` push (in ``aeat.application.wizard._compiler``) that
populates :data:`aeat.domain.contribuyente.PROFILE_KEYS` from the compiled wizard
flows. ``test_modelo_100_registry`` imports ``PROFILE_KEYS`` at module load, which
raises ``ProfileKeysRegistrationError`` if the keys were never registered — a
global-state precondition that happens to hold in the full test suite (some peer
module imports the wizard first) but NOT when this directory is collected in
isolation. Importing the wizard catalogue here makes the registry tests
self-sufficient regardless of run scope, instead of relying on cross-test import
order. This is test scaffolding (a conftest), not production domain code, so the
domain→application import is confined to the test boundary.

Note (deeper smell, out of scope for this fix): ``PROFILE_KEYS`` is a
domain-layer constant whose population depends on an application-layer import
side-effect. Making the domain registration independent of application bootstrap
is a larger refactor tracked separately.
"""

import aeat.application.wizard  # noqa: F401  -- side-effect import: registers profile keys
