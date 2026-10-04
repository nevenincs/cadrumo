"""Invoke the installed distribution's canonical CLI entrypoint."""

import sys
from importlib.metadata import distribution

from cadrumo.core.product_identity import PRODUCT_IDENTITY

sys.argv[0] = PRODUCT_IDENTITY.cli_executable
entry = next(
    e
    for e in distribution(PRODUCT_IDENTITY.distribution).entry_points
    if e.group == "console_scripts" and e.name == PRODUCT_IDENTITY.cli_executable
)
entry.load()()
