"""Fixed read-only interpreter probe; domain policy stays with its Python owners."""

import importlib.metadata
import json
import platform
import struct
import sys

request = json.load(sys.stdin)
distributions = {}
for name in request["distributions"]:
    try:
        distributions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        distributions[name] = None

json.dump(
    {
        "schema": 1,
        "implementation": sys.implementation.name,
        "version": platform.python_version(),
        "pointer_bits": struct.calcsize("P") * 8,
        "executable": sys.executable,
        "distributions": distributions,
    },
    sys.stdout,
)
