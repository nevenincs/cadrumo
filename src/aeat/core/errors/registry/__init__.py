"""Registry submodules."""

from ._adapters import _DECLARED_ERROR_CODES as adapters_codes  # noqa: N811
from ._application import _DECLARED_ERROR_CODES as application_codes  # noqa: N811
from ._core import _DECLARED_ERROR_CODES as core_codes  # noqa: N811
from ._domain import _DECLARED_ERROR_CODES as domain_codes  # noqa: N811
from ._entrypoints import _DECLARED_ERROR_CODES as entrypoints_codes  # noqa: N811

_ALL_DECLARED_ERROR_CODES = (
    *domain_codes,
    *adapters_codes,
    *entrypoints_codes,
    *core_codes,
    *application_codes,
)
