"""Registry submodules."""

from ._adapters import _DECLARED_ERROR_CODES as adapters_codes
from ._application import _DECLARED_ERROR_CODES as application_codes
from ._core import _DECLARED_ERROR_CODES as core_codes
from ._domain import _DECLARED_ERROR_CODES as domain_codes
from ._entrypoints import _DECLARED_ERROR_CODES as entrypoints_codes

_ALL_DECLARED_ERROR_CODES = (
    *domain_codes,
    *adapters_codes,
    *entrypoints_codes,
    *core_codes,
    *application_codes,
)
