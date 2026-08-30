"""Wizard catalogue error registry and envelope contracts."""

import pytest

from ..errors.error_codes import build_error_envelope, get_registered_error_code
from ..errors.hierarchy import CadrumoError
from ..setup_answers import ProjectAnswersNotRegisteredError
from ..wizard_catalogue import WizardCatalogueAlreadyRegisteredError, WizardCatalogueNotRegisteredError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ERROR_CASES: tuple[tuple[type[CadrumoError], str], ...] = (
    (WizardCatalogueNotRegisteredError, "INTERNAL_WIZARD_CATALOGUE_NOT_REGISTERED"),
    (WizardCatalogueAlreadyRegisteredError, "INTERNAL_WIZARD_CATALOGUE_ALREADY_REGISTERED"),
    (ProjectAnswersNotRegisteredError, "INTERNAL_PROFILE_PROJECT_ANSWERS_NOT_REGISTERED"),
)


@pytest.mark.parametrize(("error_cls", "expected_code"), _ERROR_CASES)
def test_error_classes_are_cadrumo_errors_with_registered_codes(
    error_cls: type[CadrumoError], expected_code: str
) -> None:
    assert issubclass(error_cls, CadrumoError), error_cls.__name__
    assert get_registered_error_code(error_cls).code == expected_code


@pytest.mark.parametrize(("error_cls", "_expected_code"), _ERROR_CASES)
def test_envelope_roundtrip(error_cls: type[CadrumoError], _expected_code: str) -> None:
    del _expected_code
    try:
        instance = error_cls()
    except TypeError:
        instance = error_cls("test message")
    envelope = build_error_envelope(instance)
    assert envelope.code == get_registered_error_code(error_cls).code
    assert envelope.message, error_cls.__name__
