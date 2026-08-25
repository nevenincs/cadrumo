"""Parity tests for the Cl@ve session and login-assertion detail shapes.

The two Cl@ve providers each used to declare their own copy of the same
provider-neutral fields: identical ``dni_nie`` / ``landing_url`` on the session
details, and identical ``session_cookie_present`` / ``landing_url`` on the
login-assertion details, with only the ``kind`` discriminant and some prose
differing. Two independent declarations of one contract drift silently — one
side can lose a ``min_length`` or change a default and nothing notices.

The shared fields now live on one canonical base per detail family. These tests
pin the invariant that survives any future refactor: the provider-neutral
fields of the two Cl@ve providers are the SAME fields with the SAME
constraints, while the discriminant stays explicitly narrowed per provider.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

from ......application.auth.session_types import (
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
    ClavePermanenteLoginAssertionDetail,
    ClavePermanenteSessionDetail,
)
from ......core import AuthProviderKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SESSION_SHARED_FIELDS = ("dni_nie", "landing_url")
_ASSERTION_SHARED_FIELDS = ("session_cookie_present", "landing_url")
_DNI_NIE = "X1234567L"

type ClaveSessionDetail = ClaveMovilSessionDetail | ClavePermanenteSessionDetail
type ClaveLoginAssertionDetail = ClaveMovilLoginAssertionDetail | ClavePermanenteLoginAssertionDetail


def _constraint_signature(field: FieldInfo) -> tuple[object, ...]:
    """Return the comparable validation shape of ``field``.

    Annotation, default and every declared metadata constraint (``min_length``
    and friends) participate, so a provider that quietly relaxes one of them
    produces a different signature.
    """
    return (
        field.annotation,
        field.default,
        field.is_required(),
        tuple(repr(constraint) for constraint in field.metadata),
    )


@pytest.mark.parametrize(
    ("movil", "permanente", "shared_fields"),
    [
        pytest.param(
            ClaveMovilSessionDetail,
            ClavePermanenteSessionDetail,
            _SESSION_SHARED_FIELDS,
            id="session-detail",
        ),
        pytest.param(
            ClaveMovilLoginAssertionDetail,
            ClavePermanenteLoginAssertionDetail,
            _ASSERTION_SHARED_FIELDS,
            id="login-assertion-detail",
        ),
    ],
)
def test_shared_cleve_fields_have_identical_constraints_across_providers(
    movil: type[BaseModel],
    permanente: type[BaseModel],
    shared_fields: tuple[str, ...],
) -> None:
    """Every provider-neutral field validates identically on both providers."""
    for name in shared_fields:
        assert name in movil.model_fields, f"{movil.__name__} lost the shared field {name!r}"
        assert name in permanente.model_fields, f"{permanente.__name__} lost the shared field {name!r}"
        assert _constraint_signature(movil.model_fields[name]) == _constraint_signature(
            permanente.model_fields[name],
        ), f"Cl@ve providers disagree on the {name!r} contract"


@pytest.mark.parametrize(
    ("movil", "permanente", "shared_fields"),
    [
        pytest.param(
            ClaveMovilSessionDetail,
            ClavePermanenteSessionDetail,
            _SESSION_SHARED_FIELDS,
            id="session-detail",
        ),
        pytest.param(
            ClaveMovilLoginAssertionDetail,
            ClavePermanenteLoginAssertionDetail,
            _ASSERTION_SHARED_FIELDS,
            id="login-assertion-detail",
        ),
    ],
)
def test_shared_cleve_fields_come_from_one_declaration(
    movil: type[BaseModel],
    permanente: type[BaseModel],
    shared_fields: tuple[str, ...],
) -> None:
    """The shared fields are inherited from one common base, not re-declared.

    Identical constraints today are not enough: two independent declarations
    are exactly what drifts. This pins the single declaration site.
    """
    common_bases = set(movil.__mro__) & set(permanente.__mro__)

    for name in shared_fields:
        owners = [base for base in common_bases if name in vars(base).get("__annotations__", {})]
        assert owners, (
            f"{movil.__name__} and {permanente.__name__} share no base declaring "
            f"{name!r}; the field has been re-forked per provider"
        )
        # Walk BOTH providers: a re-declaration on either side is a second
        # declaration site, and a check that walks only one is blind to half
        # the drift it exists to catch.
        for detail in (movil, permanente):
            declaring = [base for base in detail.__mro__ if name in vars(base).get("__annotations__", {})]
            assert len(declaring) == 1, (
                f"{name!r} is declared {len(declaring)} times across {detail.__name__}'s bases "
                f"({[base.__name__ for base in declaring]}); it must have one declaration site"
            )


@pytest.mark.parametrize(
    ("detail", "expected_kind"),
    [
        pytest.param(ClaveMovilSessionDetail, AuthProviderKind.CLAVE_MOVIL, id="movil-session"),
        pytest.param(ClavePermanenteSessionDetail, AuthProviderKind.CLAVE_PERMANENTE, id="permanente-session"),
        pytest.param(ClaveMovilLoginAssertionDetail, AuthProviderKind.CLAVE_MOVIL, id="movil-assertion"),
        pytest.param(
            ClavePermanenteLoginAssertionDetail,
            AuthProviderKind.CLAVE_PERMANENTE,
            id="permanente-assertion",
        ),
    ],
)
def test_each_detail_narrows_the_discriminant_to_its_own_provider(
    detail: type[BaseModel],
    expected_kind: AuthProviderKind,
) -> None:
    """Sharing a base must not blur which provider a detail belongs to."""
    field = detail.model_fields["kind"]

    assert field.default == expected_kind
    with pytest.raises(ValidationError):
        detail.model_validate({"kind": "certificate", "dni_nie": _DNI_NIE})


@pytest.mark.parametrize(
    "detail",
    [
        pytest.param(ClaveMovilSessionDetail, id="movil"),
        pytest.param(ClavePermanenteSessionDetail, id="permanente"),
    ],
)
def test_session_detail_refuses_an_empty_identity_on_both_providers(detail: type[ClaveSessionDetail]) -> None:
    """The non-empty identity constraint cannot hold on one provider only."""
    with pytest.raises(ValidationError):
        detail(dni_nie="")


@pytest.mark.parametrize(
    "detail",
    [
        pytest.param(ClaveMovilSessionDetail, id="movil"),
        pytest.param(ClavePermanenteSessionDetail, id="permanente"),
    ],
)
def test_session_detail_accepts_an_identity_and_defaults_the_landing_url(detail: type[ClaveSessionDetail]) -> None:
    """The shared happy path still holds after the factoring."""
    record = detail(dni_nie=_DNI_NIE)

    assert record.dni_nie == _DNI_NIE
    assert record.landing_url is None


def test_movil_session_detail_keeps_its_provider_specific_fields() -> None:
    """Factoring the shared fields must not drop the QR-flow signals."""
    record = ClaveMovilSessionDetail(
        dni_nie=_DNI_NIE,
        used_non_qr_fallback=True,
        verification_code="ABC",
    )

    assert record.used_non_qr_fallback is True
    assert record.verification_code == "ABC"
    assert "used_non_qr_fallback" not in ClavePermanenteSessionDetail.model_fields
    assert "verification_code" not in ClavePermanenteSessionDetail.model_fields


@pytest.mark.parametrize(
    "detail",
    [
        pytest.param(ClaveMovilLoginAssertionDetail, id="movil"),
        pytest.param(ClavePermanenteLoginAssertionDetail, id="permanente"),
    ],
)
def test_login_assertion_detail_defaults_to_no_live_cookie(detail: type[ClaveLoginAssertionDetail]) -> None:
    """The cookie signal defaults closed on both providers."""
    record = detail()

    assert record.session_cookie_present is False
    assert record.landing_url is None


@pytest.mark.parametrize(
    "detail",
    [
        pytest.param(ClaveMovilSessionDetail, id="movil-session"),
        pytest.param(ClavePermanenteSessionDetail, id="permanente-session"),
        pytest.param(ClaveMovilLoginAssertionDetail, id="movil-assertion"),
        pytest.param(ClavePermanenteLoginAssertionDetail, id="permanente-assertion"),
    ],
)
def test_details_stay_strict_and_frozen(detail: type[BaseModel]) -> None:
    """Inheriting the shared base must not relax the strict-frozen config."""
    assert detail.model_config.get("frozen") is True
    assert detail.model_config.get("extra") == "forbid"
