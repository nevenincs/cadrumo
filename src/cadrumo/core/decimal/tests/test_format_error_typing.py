import pytest

from ...errors import ERROR_REGISTRY, DecimalFormatError, get_registered_error_code
from .. import format_decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_decimal_format_error_typing_registry_and_raise_site() -> None:
    assert not issubclass(DecimalFormatError, ValueError)
    with pytest.raises(DecimalFormatError):
        format_decimal(None)
    assert get_registered_error_code(DecimalFormatError("test")).code in ERROR_REGISTRY
