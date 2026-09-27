"""Priority for a test keyring backend that only an explicit selection makes usable.

``keyring`` chooses its default backend by priority from every
:class:`~keyring.backend.KeyringBackend` subclass defined in the process, so a
test backend with a fixed positive priority becomes the default of any process
that merely imports it -- every pytest worker imports every test module at
collection. That process would then write credentials to a store its own child
processes never see.
"""

from __future__ import annotations

import os

_BACKEND_SELECTION_ENV = "PYTHON_KEYRING_BACKEND"


def explicit_selection_priority(qualified_name: str) -> float:
    """Return a positive priority only when ``PYTHON_KEYRING_BACKEND`` names ``qualified_name``.

    Read once, as the backend's module loads. A child process that selects the
    backend through the environment always imports it after that selection, so
    it sees a usable keychain; any other importer sees a backend that ranks below
    keyring's own fail backend and is never chosen by detection.
    """
    return 1 if os.environ.get(_BACKEND_SELECTION_ENV, "").strip() == qualified_name else -1


__all__ = ["explicit_selection_priority"]
