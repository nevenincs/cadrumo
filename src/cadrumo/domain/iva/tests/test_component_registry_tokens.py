from __future__ import annotations

import copy

import pytest
from pydantic import TypeAdapter, ValidationError

from ....core.registry_token import StrictRegistryToken
from ..components import (
    IvaComponentPresence,
    IvaKindApplicability,
    IvaRetencionExpectation,
    IvaRetencionRole,
)
from ..errors import IvaValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TOKEN_CASES: tuple[tuple[type[StrictRegistryToken], str], ...] = (
    (IvaComponentPresence, "IVA component-presence"),
    (IvaRetencionExpectation, "IVA retención-expectation"),
    (IvaRetencionRole, "IVA retención-role"),
    (IvaKindApplicability, "IVA kind-applicability"),
)


def _assert_registered_boundary_refusal(
    token_type: type[StrictRegistryToken],
    value: object,
    *,
    subject: str,
) -> None:
    with pytest.raises(ValidationError) as refused:
        TypeAdapter(token_type).validate_python(value)

    callback_error = refused.value.errors()[0]["ctx"]["error"]
    assert isinstance(callback_error, ValueError)
    registered = callback_error.__cause__
    assert isinstance(registered, IvaValidationError)
    assert str(registered) == f"{subject} must be a registry-projected token"


@pytest.mark.parametrize(("token_type", "subject"), _TOKEN_CASES)
def test_unvalidated_construction_requires_registry_projection(
    token_type: type[StrictRegistryToken],
    subject: str,
) -> None:
    with pytest.raises(
        TypeError,
        match=f"^{subject} tokens must be projected from the facts registry$",
    ):
        token_type("sample")


@pytest.mark.parametrize(("token_type", "subject"), _TOKEN_CASES)
@pytest.mark.parametrize(
    "value",
    (
        pytest.param("", id="empty"),
        pytest.param(None, id="none"),
        pytest.param(17, id="integer"),
    ),
)
def test_registry_constructor_rejects_empty_and_non_string_values(
    token_type: type[StrictRegistryToken],
    subject: str,
    value: object,
) -> None:
    with pytest.raises(ValueError, match=f"^{subject} token must be a non-empty string$"):
        token_type.from_registry(
            value,  # ty: ignore[invalid-argument-type]  # reason: refusal case
        )


@pytest.mark.parametrize(("token_type", "subject"), _TOKEN_CASES)
def test_typed_boundary_admits_own_projection_and_refuses_raw_or_sibling_tokens(
    token_type: type[StrictRegistryToken],
    subject: str,
) -> None:
    adapter = TypeAdapter(token_type)
    projected = token_type.from_registry("sample")
    assert adapter.validate_python(projected) is projected

    _assert_registered_boundary_refusal(token_type, "sample", subject=subject)
    for sibling_type, _sibling_subject in _TOKEN_CASES:
        if sibling_type is not token_type:
            sibling = sibling_type.from_registry("sample")
            _assert_registered_boundary_refusal(token_type, sibling, subject=subject)


@pytest.mark.parametrize(("token_type", "_subject"), _TOKEN_CASES)
def test_projected_token_keeps_text_name_and_string_serialization(
    token_type: type[StrictRegistryToken],
    _subject: str,
) -> None:
    projected = token_type.from_registry("sample")
    adapter = TypeAdapter(token_type)

    assert type(projected) is token_type
    assert str(projected) == "sample"
    assert projected.value == "sample"
    assert projected.name == "sample"
    assert adapter.dump_python(projected) == "sample"
    assert adapter.dump_json(projected) == b'"sample"'


@pytest.mark.parametrize(("token_type", "_subject"), _TOKEN_CASES)
def test_copy_and_deepcopy_return_the_projected_token_instance(
    token_type: type[StrictRegistryToken],
    _subject: str,
) -> None:
    projected = token_type.from_registry("sample")

    assert copy.copy(projected) is projected
    assert copy.deepcopy(projected) is projected
