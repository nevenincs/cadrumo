"""Read runtime identity without acquiring an endpoint or opening a profile."""

import json
import sys
from importlib.metadata import version

from cadrumo.core.storage_environment import configured_storage_root

storage = configured_storage_root().resolve(strict=True)
if sys.platform == "win32":
    from cadrumo_client.transport.windows import WindowsEndpoint

    identity = WindowsEndpoint(storage_root=storage).storage_identity
else:
    from cadrumo_client.transport.posix import posix_storage_identity

    identity = posix_storage_identity(storage)

json.dump(dict(storage=str(storage), storage_identity=identity, version=version("cadrumo")), sys.stdout)
