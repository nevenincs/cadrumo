"""Unit tests for :class:`aeat.domain.portals.PortalMetadata`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..modelos import ModeloCode
from ._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from ._codes import Portal
from ._metadata import PortalMetadata

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _base_kwargs(**overrides: object) -> dict[str, object]:
    """Return a valid FILING portal kwargs dict for use with overrides."""
    base: dict[str, object] = {
        "portal": Portal.PORTAL_M303_IVA_AUTOLIQUIDACION,
        "url": "https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G414.shtml",
        "subdomain": Subdomain.SEDE,
        "category": PortalCategory.FILING,
        "auth_methods": frozenset({AuthMethod.CERTIFICATE}),
        "url_stability": UrlStability.STABLE_PROTOCOL_GRADE,
        "related_modelo": ModeloCode.MODELO_303,
        "label": {"es": "x", "en": "x", "hu": "x"},
        "purpose_es": "x",
        "active": True,
        "replaced_by": None,
        "notes_es": (),
    }
    base.update(overrides)
    return base


def test_valid_filing_entry_constructs() -> None:
    """A well-formed FILING entry constructs without errors."""
    metadata = PortalMetadata.model_validate(_base_kwargs())
    assert metadata.portal is Portal.PORTAL_M303_IVA_AUTOLIQUIDACION


def test_url_scheme_must_be_https() -> None:
    """Non-HTTPS URLs are rejected."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(
            _base_kwargs(url="http://sede.agenciatributaria.gob.es/Sede/procedimientoini/G414.shtml")
        )


def test_url_host_must_match_subdomain() -> None:
    """A mismatch between URL host and declared subdomain fails."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(
            _base_kwargs(url="https://www1.agenciatributaria.gob.es/Sede/procedimientoini/G414.shtml")
        )


def test_filing_url_must_match_gcode_pattern() -> None:
    """Active FILING URL path must match the G-code regex."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(
            _base_kwargs(url="https://sede.agenciatributaria.gob.es/Sede/something-else.html")
        )


def test_census_url_must_match_gcode_pattern() -> None:
    """Active CENSUS URL path must match the G-code regex."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(
            _base_kwargs(
                portal=Portal.PORTAL_M036_CENSAL,
                category=PortalCategory.CENSUS,
                related_modelo=ModeloCode.MODELO_036,
                url="https://sede.agenciatributaria.gob.es/Sede/censal.html",
            )
        )


def test_retired_filing_skips_gcode_check() -> None:
    """Retired FILING/CENSUS entries bypass the G-code path check."""
    # Even with a non-G-code path, a retired entry validates.
    PortalMetadata.model_validate(
        _base_kwargs(
            portal=Portal.PORTAL_M037_CENSAL_SIMPLIFICADA,
            category=PortalCategory.CENSUS,
            related_modelo=ModeloCode.MODELO_037,
            url="https://sede.agenciatributaria.gob.es/Sede/retired-path.html",
            url_stability=UrlStability.RETIRED,
            active=False,
            replaced_by=Portal.PORTAL_M036_CENSAL,
        )
    )


def test_anonymous_is_exclusive() -> None:
    """AuthMethod.ANONYMOUS cannot coexist with any other method."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(
            _base_kwargs(auth_methods=frozenset({AuthMethod.ANONYMOUS, AuthMethod.CERTIFICATE}))
        )


def test_auth_methods_cannot_be_empty() -> None:
    """Empty ``auth_methods`` is rejected."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(_base_kwargs(auth_methods=frozenset()))


def test_related_modelo_required_for_filing() -> None:
    """FILING requires a non-None ``related_modelo``."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(_base_kwargs(related_modelo=None))


def test_related_modelo_forbidden_for_auth() -> None:
    """AUTH forbids ``related_modelo``."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(
            _base_kwargs(
                portal=Portal.PORTAL_SEDE_ROOT,
                url="https://sede.agenciatributaria.gob.es/",
                category=PortalCategory.AUTH,
                auth_methods=frozenset({AuthMethod.ANONYMOUS}),
                related_modelo=ModeloCode.MODELO_303,
            )
        )


def test_related_modelo_required_for_census() -> None:
    """CENSUS requires a non-None ``related_modelo``."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(
            _base_kwargs(
                portal=Portal.PORTAL_M036_CENSAL,
                category=PortalCategory.CENSUS,
                related_modelo=None,
                url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G322.shtml",
            )
        )


def test_related_modelo_required_for_borrador() -> None:
    """BORRADOR requires a non-None ``related_modelo``."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(
            _base_kwargs(
                portal=Portal.PORTAL_PRE303_AYUDA,
                category=PortalCategory.BORRADOR,
                url="https://sede.agenciatributaria.gob.es/Sede/iva/autoliquidacion-iva-modelo-303/pre303.html",
                url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
                related_modelo=None,
            )
        )


def test_quad_lingual_label_requires_all_three_languages() -> None:
    """Missing ``hu`` key is rejected."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(_base_kwargs(label={"es": "x", "en": "x"}))


def test_quad_lingual_label_rejects_blank_string() -> None:
    """Whitespace-only label entries fail."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(_base_kwargs(label={"es": "x", "en": " ", "hu": "x"}))


def test_purpose_es_must_not_be_blank() -> None:
    """Whitespace-only ``purpose_es`` is rejected."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(_base_kwargs(purpose_es="   "))


def test_active_with_replaced_by_is_rejected() -> None:
    """``replaced_by`` must be ``None`` when ``active is True``."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(_base_kwargs(replaced_by=Portal.PORTAL_M036_CENSAL))


def test_retired_without_replacement_requires_notes() -> None:
    """A retired portal without ``replaced_by`` must carry non-empty notes."""
    with pytest.raises(ValidationError):
        PortalMetadata.model_validate(
            _base_kwargs(
                portal=Portal.PORTAL_M037_CENSAL_SIMPLIFICADA,
                category=PortalCategory.CENSUS,
                related_modelo=ModeloCode.MODELO_037,
                url_stability=UrlStability.RETIRED,
                active=False,
                replaced_by=None,
                notes_es=(),
            )
        )


def test_retired_without_replacement_with_notes_is_valid() -> None:
    """Retired + no replacement + non-empty notes validates."""
    metadata = PortalMetadata.model_validate(
        _base_kwargs(
            portal=Portal.PORTAL_M037_CENSAL_SIMPLIFICADA,
            category=PortalCategory.CENSUS,
            related_modelo=ModeloCode.MODELO_037,
            url="https://sede.agenciatributaria.gob.es/Sede/retired.html",
            url_stability=UrlStability.RETIRED,
            active=False,
            replaced_by=None,
            notes_es=("Discontinued procedure.",),
        )
    )
    assert metadata.active is False


def test_metadata_is_frozen() -> None:
    """Instances reject post-construction attribute mutation."""
    metadata = PortalMetadata.model_validate(_base_kwargs())
    with pytest.raises(ValidationError):
        metadata.active = False  # type: ignore[misc]
