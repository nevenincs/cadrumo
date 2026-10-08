"""Host-environment scrubbing for child processes that run the product.

A child that exercises the product must see the configuration its scenario
states and nothing the invoking workstation happened to export. Two scrubs
cover the two situations that arise:

* :func:`ambient_product_settings_removed` drops product settings only, for
  children that still run inside the repository environment.
* :func:`clean_product_env` additionally drops the interpreter-selection
  variables, for children that must resolve the product from their own
  installation rather than from the invoking checkout or virtual environment.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final

from cadrumo.core.product_identity import PRODUCT_IDENTITY

#: Settings prefix of the product before its rename. The product refuses state
#: that still carries it, so an ambient value would fail a child before the
#: scenario ran.
_FORMER_PRODUCT_ENVIRONMENT_PREFIX: Final = "AEAT_"

_INTERPRETER_SELECTION_NAMES: Final = (
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONUSERBASE",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "UV_PROJECT_ENVIRONMENT",
)


def ambient_product_settings_removed(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return ``environ`` without current or former product settings.

    Names match case-insensitively because the product's settings loader does.
    """
    source = os.environ if environ is None else environ
    prefixes = (PRODUCT_IDENTITY.environment_prefix.upper(), _FORMER_PRODUCT_ENVIRONMENT_PREFIX)
    return {key: value for key, value in source.items() if not key.upper().startswith(prefixes)}


def clean_product_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return ``environ`` without product settings or Python path configuration."""
    environment = ambient_product_settings_removed(environ)
    for name in _INTERPRETER_SELECTION_NAMES:
        environment.pop(name, None)
    return environment
