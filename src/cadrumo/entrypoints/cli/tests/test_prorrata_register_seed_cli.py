"""CLI surface tests for the LIVA art. 105 prorrata seed and sector lifecycle.

Exercises ``aeat app ledger prorrata seed / seed-sector / settle-sector``
through the real Typer surface against an isolated encrypted backend. The
carried seed's source is a real stamped Modelo 303 settlement observation
written through :class:`CalculationObservationRepository`, and every assertion
reads the resulting state back through the register verbs or the real
:class:`ProrrataRegisterService`.

The detector-teeth case constructs a register entry that contradicts the prior
settlement observation, proving
:func:`~application.prorrata_register.seed.cross_check_prorrata_entry_against_prior_observation`
reaches the operator as a refusal rather than the command succeeding quietly.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....application.calculations.cross_period_clean_state import CrossPeriodCleanStateBlocker
from ....application.calculations.observations_repository import CalculationObservationRepository
from ....application.prorrata_register.service import ProrrataRegisterService
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n.render import output_language, tr
from ....core.modelo import Modelo
from ....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.prorrata_register.register import ProrrataRegisterEntry
from ....tests.registry_observations import registry_grounded_modelo_observation
from ._cli_surface_profile_fixture import _isolated_backend
from ._cli_surface_support import _invoke, _json

__all__ = ["_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SOURCE_KIND = "aeat_sede_justificante"
_CAPTURED_AT = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_CURRENT_YEAR = 2026
_PRIOR_YEAR = 2025
_SETTLEMENT_PERIOD = "4T"
_PRIOR_DEFINITIVE = Decimal("87")

_PORCENTAJE_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="prorrata seed CLI surface test casilla id",
)

#: Every user-facing translation key the seed / sector-lifecycle verbs resolve.
_NEW_TRANSLATION_KEYS = (
    "cli.app.ledger.prorrata.seed_help",
    "cli.app.ledger.prorrata.seed_sector_help",
    "cli.app.ledger.prorrata.settle_sector_help",
    "cli.app.ledger.prorrata.seed_ejercicio_help",
    "cli.app.ledger.prorrata.con_derecho_volume_help",
    "cli.app.ledger.prorrata.sin_derecho_volume_help",
    "cli.app.ledger.prorrata.seed_blocked",
    "cli.app.ledger.prorrata.seed_source_absent",
    "cli.app.ledger.prorrata.seed_regulated_override_standing",
    "cli.app.ledger.prorrata.seed_local_authority",
    "cli.app.ledger.prorrata.seed_sector_prior_definitive_absent",
    "cli.app.ledger.prorrata.settle_sector_entry_absent",
)


def _law_determined_prior_revision_id() -> str:
    snapshot = bundled_authority().snapshot(
        Modelo.M303.value,
        filing_year=_PRIOR_YEAR,
        period=_SETTLEMENT_PERIOD,
    )
    return str(snapshot.revision.id)


def _store_prior_settlement_observation(percentage: Decimal = _PRIOR_DEFINITIVE) -> None:
    """Write the prior Modelo 303 settlement observation into the active profile."""
    repository = CalculationObservationRepository()
    observation = registry_grounded_modelo_observation(
        modelo=Modelo.M303.value,
        filing_year=_PRIOR_YEAR,
        period=_SETTLEMENT_PERIOD,
        casilla_values={_PORCENTAJE_ID: percentage},
    )
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=_SOURCE_KIND,
            captured_at=_CAPTURED_AT,
            stamped_revision_id=_law_determined_prior_revision_id(),
        )
    )


def _seed(*extra: str):
    return _invoke(["--format", "json", "app", "ledger", "prorrata", "seed", "--ejercicio", str(_CURRENT_YEAR), *extra])


def _register_entries() -> list[dict[str, object]]:
    listing = _invoke(["--format", "json", "app", "ledger", "prorrata", "list"])
    assert listing.exit_code == 0, listing.output
    payload = STR_KEYED_MAPPING_ADAPTER.validate_python(_json(listing))
    raw_entries = payload["entries"]
    assert isinstance(raw_entries, list)
    entries: list[dict[str, object]] = []
    for raw in raw_entries:
        assert isinstance(raw, dict)
        entries.append({str(key): value for key, value in raw.items()})
    return entries


def _notice_codes(result) -> set[str]:
    return {notice["code"] for notice in json.loads(result.output).get("notices", [])}


def _refusal_text(result) -> str:
    """Return the JSON error envelope's prose in the active output language.

    Refusal copy is localized, so the assertions compare against the same
    catalogue rendering the command emitted rather than against English
    literals that only hold under one locale.
    """
    return json.dumps(json.loads(result.output)["error"], ensure_ascii=False)


def test_seed_persists_the_carried_prior_definitiva_entry() -> None:
    """The seeded entry is written and reads back through the real service."""
    _store_prior_settlement_observation()

    result = _seed()
    assert result.exit_code == 0, result.output
    payload = _json(result)

    assert payload["entry"]["ejercicio"] == _CURRENT_YEAR
    assert payload["entry"]["provisional_percentage"] == str(_PRIOR_DEFINITIVE)
    assert payload["entry"]["provisional_provenance"] == (ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA.value)
    assert payload["entry"]["source_observation_ref"] == f"303:{_PRIOR_YEAR}:{_SETTLEMENT_PERIOD}"
    assert payload["findings"] == []
    assert payload["source"] == {
        "modelo": Modelo.M303.value,
        "filing_year": _PRIOR_YEAR,
        "period": _SETTLEMENT_PERIOD,
        "casilla_id": str(_PORCENTAJE_ID),
        "stamped_revision_id": _law_determined_prior_revision_id(),
        "authority": "local_prior_observation",
    }

    # The origin of the percentage is labelled honestly on the notice channel.
    assert "ledger.prorrata.seed.local_authority" in _notice_codes(result)

    # The entry is readable back through the real application service.
    stored = ProrrataRegisterService().get(_CURRENT_YEAR)
    assert stored is not None
    assert stored.provisional_percentage == _PRIOR_DEFINITIVE
    assert stored.provisional_provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
    assert stored.source_observation_ref == f"303:{_PRIOR_YEAR}:{_SETTLEMENT_PERIOD}"

    entries = _register_entries()
    assert len(entries) == 1
    assert entries[0]["provisional_percentage"] == str(_PRIOR_DEFINITIVE)


def test_seed_surfaces_the_carried_entry_contradiction_rather_than_succeeding() -> None:
    """Detector teeth: a contradicting standing entry refuses and names the finding.

    The register carries a ``carried_prior_definitiva`` entry whose percentage
    disagrees with the prior settlement observation. That is exactly the
    contradiction ``cross_check_prorrata_entry_against_prior_observation``
    reports, and the seed verb must refuse and surface it.
    """
    _store_prior_settlement_observation()

    service = ProrrataRegisterService()
    service.declare(
        ProrrataRegisterEntry(
            ejercicio=_CURRENT_YEAR,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=Decimal("42"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            source_observation_ref=f"303:{_PRIOR_YEAR}:{_SETTLEMENT_PERIOD}",
        )
    )

    refused = _seed()
    assert refused.exit_code != 0, refused.output
    assert CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE.value in refused.output
    assert "contradicts the prior Modelo 303" in refused.output
    assert "42" in refused.output
    assert str(_PRIOR_DEFINITIVE) in refused.output

    # The refusal wrote nothing: the contradicting entry is untouched, so the
    # operator's disagreement stays visible instead of being overwritten.
    standing = service.get(_CURRENT_YEAR)
    assert standing is not None
    assert standing.provisional_percentage == Decimal("42")


def test_seed_is_idempotent() -> None:
    """Seeding twice converges on one entry and does not double-apply."""
    _store_prior_settlement_observation()

    first = _seed()
    assert first.exit_code == 0, first.output
    second = _seed()
    assert second.exit_code == 0, second.output

    assert _json(second)["entry"] == _json(first)["entry"]
    assert _json(second)["count"] == 1

    entries = _register_entries()
    assert len(entries) == 1
    assert entries[0]["provisional_percentage"] == str(_PRIOR_DEFINITIVE)

    stored = ProrrataRegisterService().get(_CURRENT_YEAR)
    assert stored is not None
    assert stored.provisional_percentage == _PRIOR_DEFINITIVE


def test_seed_without_a_prior_observation_refuses_as_absent_not_zero() -> None:
    result = _seed()
    assert result.exit_code != 0, result.output
    expected = tr(
        "cli.app.ledger.prorrata.seed_source_absent",
        locale=output_language(),
        prior_ejercicio=_PRIOR_YEAR,
        ejercicio=_CURRENT_YEAR,
    )
    assert expected in _refusal_text(result)
    assert ProrrataRegisterService().get(_CURRENT_YEAR) is None


def test_seed_refuses_to_displace_a_standing_regulated_override() -> None:
    """An art. 105.Dos authorisation outranks the carry and is never overwritten."""
    _store_prior_settlement_observation()
    service = ProrrataRegisterService()
    service.record_aeat_autorizada(
        ejercicio=_CURRENT_YEAR,
        provisional_percentage=Decimal("55"),
        authorisation_reference="aeat-auth-2026-01",
    )

    refused = _seed()
    assert refused.exit_code != 0, refused.output
    assert ProrrataProvisionalProvenance.AEAT_AUTORIZADA.value in refused.output

    standing = service.get(_CURRENT_YEAR)
    assert standing is not None
    assert standing.provisional_percentage == Decimal("55")
    assert standing.provisional_provenance is ProrrataProvisionalProvenance.AEAT_AUTORIZADA


def test_sector_lifecycle_settles_then_seeds_the_next_ejercicio() -> None:
    """settle-sector computes the definitive; seed-sector carries it forward."""
    elected = _invoke(
        [
            "app",
            "ledger",
            "prorrata",
            "elect-general",
            "--ejercicio",
            str(_PRIOR_YEAR),
            "--percentage",
            "50",
            "--sector",
            "arrendamiento",
        ]
    )
    assert elected.exit_code == 0, elected.output

    settled = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "prorrata",
            "settle-sector",
            "--ejercicio",
            str(_PRIOR_YEAR),
            "--sector-id",
            "arrendamiento",
            "--con-derecho-volume",
            "80000.00",
            "--sin-derecho-volume",
            "20000.00",
        ]
    )
    assert settled.exit_code == 0, settled.output
    definitive = _json(settled)["entry"]["definitive_percentage"]
    assert definitive is not None
    assert _json(settled)["entry"]["definitive_volume_con_derecho"] == "80000.00"

    seeded = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "prorrata",
            "seed-sector",
            "--ejercicio",
            str(_CURRENT_YEAR),
            "--sector-id",
            "arrendamiento",
        ]
    )
    assert seeded.exit_code == 0, seeded.output
    seeded_entry = _json(seeded)["entry"]
    assert seeded_entry["sector_id"] == "arrendamiento"
    assert seeded_entry["provisional_percentage"] == definitive
    assert seeded_entry["provisional_provenance"] == (ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA.value)
    assert _json(seeded)["prior_ejercicio"] == _PRIOR_YEAR

    stored = ProrrataRegisterService().get(_CURRENT_YEAR, sector_id="arrendamiento")
    assert stored is not None
    assert stored.provisional_percentage == Decimal(str(definitive))


def test_seed_sector_without_a_prior_definitive_refuses_as_absent() -> None:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "prorrata",
            "seed-sector",
            "--ejercicio",
            str(_CURRENT_YEAR),
            "--sector-id",
            "arrendamiento",
        ]
    )
    assert result.exit_code != 0, result.output
    expected = tr(
        "cli.app.ledger.prorrata.seed_sector_prior_definitive_absent",
        locale=output_language(),
        sector_id="arrendamiento",
        prior_ejercicio=_PRIOR_YEAR,
        ejercicio=_CURRENT_YEAR,
    )
    assert expected in _refusal_text(result)
    assert ProrrataRegisterService().get(_CURRENT_YEAR, sector_id="arrendamiento") is None


def test_settle_sector_without_an_entry_refuses() -> None:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "prorrata",
            "settle-sector",
            "--ejercicio",
            str(_PRIOR_YEAR),
            "--sector-id",
            "arrendamiento",
            "--con-derecho-volume",
            "80000.00",
            "--sin-derecho-volume",
            "20000.00",
        ]
    )
    assert result.exit_code != 0, result.output
    expected = tr(
        "cli.app.ledger.prorrata.settle_sector_entry_absent",
        locale=output_language(),
        ejercicio=_PRIOR_YEAR,
        sector_id="arrendamiento",
    )
    assert expected in _refusal_text(result)


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("translation_key", _NEW_TRANSLATION_KEYS)
def test_every_supported_locale_resolves_the_new_keys(locale: str, translation_key: str) -> None:
    """A catalogue that echoes the key back has no translation for it."""
    rendered = tr(translation_key, locale=locale)
    assert rendered != translation_key
    assert rendered.strip() != ""
