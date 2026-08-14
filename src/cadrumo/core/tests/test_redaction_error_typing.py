from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from ..errors import ERROR_REGISTRY, RedactionError, get_registered_error_code
from ..redaction import redact, redact_for_cli_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def redact_with_non_string_value() -> None:
    redact(cast(str, 12345), rules=())


def redact_cli_output_with_non_string_value() -> None:
    redact_for_cli_output(cast(str, {"not": "a string"}))


@pytest.mark.parametrize("call", (redact_with_non_string_value, redact_cli_output_with_non_string_value))
def test_redaction_entrypoints_raise_redaction_error(call: Callable[[], object]) -> None:
    with pytest.raises(RedactionError) as raised:
        call()

    assert raised.type is RedactionError


def test_redaction_error_typing_and_registry() -> None:
    assert not issubclass(RedactionError, ValueError)
    assert get_registered_error_code(RedactionError("test")).code in ERROR_REGISTRY
