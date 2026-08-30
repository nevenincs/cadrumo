"""Unit tests for :class:`cadrumo.domain.portals.PortalMetadata`."""

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
from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata

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


def test_invalid_metadata_payloads_are_rejected() -> None:
    """Invalid metadata payloads fail through the real pydantic model."""
    invalid_cases: tuple[tuple[str, dict[str, object], str], ...] = (
        (
            "non-https-url",
            {
                "url": _sede_url(portal_path("portal_m303_iva_autoliquidacion")).replace(
                    "https://",
                    "http://",
                    1,
                ),
            },
            r"url scheme must be https",
        ),
        (
            "host-subdomain-mismatch",
            {"url": _www1_url(portal_path("portal_m303_iva_autoliquidacion"))},
            r"does not match subdomain",
        ),
        (
            "filing-non-gcode-path",
            {"url": _sede_url(PORTAL_NON_GCODE_PATH_CANARY)},
            r"url path must match",
        ),
        (
            "censo-non-gcode-path",
            {
                "portal": Portal.PORTAL_M036_CENSAL,
                "category": PortalCategory.CENSO,
                "url": _sede_url(PORTAL_CENSO_NON_GCODE_PATH_CANARY),
            },
            r"url path must match",
        ),
        (
            "anonymous-mixed-auth",
            {"auth_methods": frozenset({AuthMethod.ANONYMOUS, AuthMethod.CERTIFICATE})},
            r"AuthMethod.ANONYMOUS must be the sole method",
        ),
        (
            "empty-auth-methods",
            {"auth_methods": frozenset()},
            r"at least 1 item",
        ),
        (
            "external-modelo-field",
            {"modelo": "303"},
            r"Extra inputs are not permitted",
        ),
        (
            "label-non-string",
            {"label": {"en": "x", "hu": "x"}},
            r"valid string",
        ),
        (
            "label-blank",
            {"label": " "},
            r"label must not be empty or whitespace-only",
        ),
        (
            "purpose-blank",
            {"purpose": "   "},
            r"purpose must not be empty or whitespace-only",
        ),
        (
            "active-with-replacement",
            {"replaced_by": Portal.PORTAL_M036_CENSAL},
            r"replaced_by must be None when active is True",
        ),
        (
            "retired-without-replacement-notes",
            {
                "portal": Portal.PORTAL_M037_CENSAL_SIMPLIFICADA,
                "category": PortalCategory.CENSO,
                "url_stability": UrlStability.RETIRED,
                "active": False,
                "replaced_by": None,
                "notes": (),
            },
            r"retired portal without replaced_by must carry a non-empty notes",
        ),
    )

    for case_id, overrides, match in invalid_cases:
        try:
            with pytest.raises(ValidationError, match=match):
                PortalMetadata.model_validate(_base_kwargs(**overrides))
        except AssertionError as exc:
            raise AssertionError(f"invalid metadata payload case failed: {case_id}") from exc


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
