"""Unit tests for :class:`aeat.domain.portals.PortalMetadata`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.external_constants import load_external_constants
from ....tests.aeat_literal_fixtures import (
    PORTAL_CENSO_NON_GCODE_PATH_CANARY,
    PORTAL_NON_GCODE_PATH_CANARY,
    PORTAL_RETIRED_PATH_CANARY,
    PORTAL_RETIRED_WITH_NOTES_PATH_CANARY,
    portal_path,
)
from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _sede_url(path: str) -> str:
    return f"{load_external_constants().aeat.domains.sede}{path}"


def _www1_url(path: str) -> str:
    return f"{load_external_constants().aeat.domains.www1}{path}"


def _base_kwargs(**overrides: object) -> dict[str, object]:
    """Return a valid FILING portal kwargs dict for use with overrides."""
    base: dict[str, object] = {
        "portal": Portal.PORTAL_M303_IVA_AUTOLIQUIDACION,
        "url": _sede_url(portal_path("portal_m303_iva_autoliquidacion")),
        "subdomain": PortalHost.SEDE,
        "category": PortalCategory.FILING,
        "auth_methods": frozenset({AuthMethod.CERTIFICATE}),
        "url_stability": UrlStability.STABLE_PROTOCOL_GRADE,
        "label": "entries.portal_m303_iva_autoliquidacion.label",
        "purpose": "x",
        "active": True,
        "replaced_by": None,
        "notes": (),
    }
    base.update(overrides)
    return base


def test_valid_filing_entry_constructs() -> None:
    """A well-formed FILING entry constructs without errors."""
    metadata = PortalMetadata.model_validate(_base_kwargs())
    assert metadata.portal is Portal.PORTAL_M303_IVA_AUTOLIQUIDACION


def test_url_scheme_must_be_https() -> None:
    """Non-HTTPS URLs are rejected."""
    with pytest.raises(ValidationError, match=r"url scheme must be https"):
        PortalMetadata.model_validate(
            _base_kwargs(
                url=_sede_url(portal_path("portal_m303_iva_autoliquidacion")).replace("https://", "http://", 1),
            ),
        )


def test_url_host_must_match_subdomain() -> None:
    """A mismatch between URL host and declared subdomain fails."""
    with pytest.raises(ValidationError, match=r"does not match subdomain"):
        PortalMetadata.model_validate(_base_kwargs(url=_www1_url(portal_path("portal_m303_iva_autoliquidacion"))))


def test_filing_url_must_match_gcode_pattern() -> None:
    """Active FILING URL path must match the G-code regex."""
    with pytest.raises(ValidationError, match=r"url path must match"):
        PortalMetadata.model_validate(_base_kwargs(url=_sede_url(PORTAL_NON_GCODE_PATH_CANARY)))


def test_censo_url_must_match_gcode_pattern() -> None:
    """Active CENSO URL path must match the G-code regex."""
    with pytest.raises(ValidationError, match=r"url path must match"):
        PortalMetadata.model_validate(
            _base_kwargs(
                portal=Portal.PORTAL_M036_CENSAL,
                category=PortalCategory.CENSO,
                url=_sede_url(PORTAL_CENSO_NON_GCODE_PATH_CANARY),
            ),
        )


def test_retired_filing_skips_gcode_check() -> None:
    """Retired FILING/CENSO entries bypass the G-code path check."""
    # Even with a non-G-code path, a retired entry validates.
    metadata = PortalMetadata.model_validate(
        _base_kwargs(
            portal=Portal.PORTAL_M037_CENSAL_SIMPLIFICADA,
            category=PortalCategory.CENSO,
            url=_sede_url(PORTAL_RETIRED_PATH_CANARY),
            url_stability=UrlStability.RETIRED,
            active=False,
            replaced_by=Portal.PORTAL_M036_CENSAL,
        ),
    )
    assert metadata.url_stability == UrlStability.RETIRED
    assert metadata.active is False
    assert metadata.replaced_by == Portal.PORTAL_M036_CENSAL


def test_anonymous_is_exclusive() -> None:
    """AuthMethod.ANONYMOUS cannot coexist with any other method."""
    with pytest.raises(ValidationError, match=r"AuthMethod.ANONYMOUS must be the sole method"):
        PortalMetadata.model_validate(
            _base_kwargs(auth_methods=frozenset({AuthMethod.ANONYMOUS, AuthMethod.CERTIFICATE})),
        )


def test_auth_methods_cannot_be_empty() -> None:
    """Empty ``auth_methods`` is rejected."""
    with pytest.raises(ValidationError, match=r"at least 1 item"):
        PortalMetadata.model_validate(_base_kwargs(auth_methods=frozenset()))


def test_external_binding_fields_are_rejected() -> None:
    """Portal metadata rejects non-schema binding fields."""
    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
        PortalMetadata.model_validate(
            _base_kwargs(
                modelo="303",
            ),
        )


def test_label_rejects_non_string_payload() -> None:
    """Label keys must be strings."""
    with pytest.raises(ValidationError, match=r"valid string"):
        PortalMetadata.model_validate(_base_kwargs(label={"en": "x", "hu": "x"}))


def test_label_rejects_blank_string() -> None:
    """Whitespace-only label keys fail."""
    with pytest.raises(ValidationError, match=r"label must not be empty or whitespace-only"):
        PortalMetadata.model_validate(_base_kwargs(label=" "))


def test_purpose_must_not_be_blank() -> None:
    """Whitespace-only ``purpose`` is rejected."""
    with pytest.raises(ValidationError, match=r"purpose must not be empty or whitespace-only"):
        PortalMetadata.model_validate(_base_kwargs(purpose="   "))


def test_active_with_replaced_by_is_rejected() -> None:
    """``replaced_by`` must be ``None`` when ``active is True``."""
    with pytest.raises(ValidationError, match=r"replaced_by must be None when active is True"):
        PortalMetadata.model_validate(_base_kwargs(replaced_by=Portal.PORTAL_M036_CENSAL))


def test_retired_without_replacement_requires_notes() -> None:
    """A retired portal without ``replaced_by`` must carry non-empty notes."""
    with pytest.raises(ValidationError, match=r"retired portal without replaced_by must carry a non-empty notes"):
        PortalMetadata.model_validate(
            _base_kwargs(
                portal=Portal.PORTAL_M037_CENSAL_SIMPLIFICADA,
                category=PortalCategory.CENSO,
                url_stability=UrlStability.RETIRED,
                active=False,
                replaced_by=None,
                notes=(),
            ),
        )


def test_retired_without_replacement_with_notes_is_valid() -> None:
    """Retired + no replacement + non-empty notes validates."""
    metadata = PortalMetadata.model_validate(
        _base_kwargs(
            portal=Portal.PORTAL_M037_CENSAL_SIMPLIFICADA,
            category=PortalCategory.CENSO,
            url=_sede_url(PORTAL_RETIRED_WITH_NOTES_PATH_CANARY),
            url_stability=UrlStability.RETIRED,
            active=False,
            replaced_by=None,
            notes=("Discontinued procedure.",),
        ),
    )
    assert metadata.active is False


def test_metadata_is_frozen() -> None:
    """Instances reject post-construction attribute mutation."""
    metadata = PortalMetadata.model_validate(_base_kwargs())
    with pytest.raises(ValidationError, match=r"frozen"):
        metadata.active = False
