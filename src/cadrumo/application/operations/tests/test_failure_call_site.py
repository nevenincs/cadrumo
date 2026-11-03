"""Dependency failures retain application code coordinates without private values."""

import pytest
from pydantic import BaseModel

from .._supervisor_execution import _application_frame, _raising_frame

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class EmptyModel(BaseModel):
    pass


def test_dependency_error_names_application_caller_without_exception_contents() -> None:
    private_attribute = "private_taxpayer_value_must_not_be_logged"
    try:
        getattr(EmptyModel(), private_attribute)
    except AttributeError as error:
        assert private_attribute in str(error)
        origin = _raising_frame(error)
        caller = _application_frame(error)
    else:
        pytest.fail("fixture must raise in the dependency")
    assert origin.endswith(":__getattr__")
    assert "test_failure_call_site.py:" in caller
    assert caller.endswith(":test_dependency_error_names_application_caller_without_exception_contents")
    assert private_attribute not in origin + caller


def test_unraised_error_has_no_invented_application_frame() -> None:
    assert _application_frame(AttributeError("private detail")) == "-"
