"""The relation-prefill zero-resolution candidate set is registry-grounded and fail-closed.

An unresolved cross-period relation normally yields a blank the operator fills by
hand. For a source modelo the taxpayer has no obligation to file at all, the
resolver instead folds the leg in as an explicit zero, so a Modelo 100 does not
demand a synthetic Modelo 130 (or 131) filing for the estimation method the
taxpayer does not use. Which sources are eligible for that zero is the decision
this module pins.

Two properties matter, and they pull in opposite directions:

* The eligible set must come from the revision's own
  ``dependency_classifications`` (the ``conditional_on_economic_activity`` rows),
  never a modelo list written into the resolver. A hardcoded pair silently
  outlives a revision that changes which sources are conditional.
* It must stay NARROWER than the clean-state gate's non-filer set, which also
  carries the ``taxpayer_files_source = false`` arm - the suffered-retenciones
  sources (111, 123, 184, 190, 193 on Modelo 100). Those are absent because the
  PAYER files them, not because no obligation exists: the retención the taxpayer
  suffered is a real credit. Folding those legs in as zero would strip the credit
  from the declaration, so they must stay unresolved and operator-supplied.

Real registry authority is paired with a deterministic application-owned
profile projection fake. The test keeps the derivation itself pure and does
not reach encrypted storage or composition roots.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

import pytest

from cadrumo.application.user_profile.profile_read_ports import ProfilePathValuesReadPort

from ....core.modelo import Modelo
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.user_profile.values import UserProfileFact
from ..relation_prefill import (
    _economic_activity_conditional_source_modelos,
    _not_applicable_source_modelos_for_bucket,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from ....domain.calculations.registry.schema import RegistrySnapshot

#: Modelo 100 filing years whose revisions declare the pagos-fraccionados dependency pair.
_M100_YEARS: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025)

_PROFILE_ID = "30030030-0300-4300-8300-300300300300"


def _m100_snapshot(filing_year: int) -> RegistrySnapshot:
    return published_snapshot(Modelo("100").value, filing_year=filing_year, period="0A")


class _ProfilePathValuesFake:
    """Deterministic inward fake for the application profile projection port."""

    def __init__(self, values: Mapping[str, str] | None) -> None:
        self._values = values

    def load_path_values(self, *, bucket_id: str) -> Mapping[str, str] | None:
        del bucket_id
        return self._values


def _render_profile_value(value: object) -> str:
    """Render a typed profile fact into the port's canonical string shape."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _profile_reader(extra_facts: tuple[UserProfileFact, ...]) -> ProfilePathValuesReadPort:
    """Build the path projection used by a pure relation-prefill test."""
    return _ProfilePathValuesFake(
        {
            "identity.tax_id": "00000000T",
            "identity.legal_name": "Relation Prefill Grounding",
            "tax_residence.ccaa": "madrid",
            "tax_residence.jurisdiction_scope": "common_regime",
            **{fact.path: _render_profile_value(fact.value) for fact in extra_facts if fact.value is not None},
        },
    )


class TestCandidateSetIsRegistryGrounded:
    """The eligible-source set is read off the revision, not written into the resolver."""

    @pytest.mark.parametrize("filing_year", _M100_YEARS)
    def test_candidate_set_equals_the_revisions_conditional_classifications(self, filing_year: int) -> None:
        """The candidate set is exactly the revision's ``conditional_on_economic_activity`` rows."""
        snapshot = _m100_snapshot(filing_year)
        declared = frozenset(
            classification.source_modelo
            for classification in snapshot.revision.dependency_classifications
            if classification.conditional_on_economic_activity
        )

        assert _economic_activity_conditional_source_modelos(snapshot) == declared, (
            f"Modelo 100 {filing_year}: the candidate set must be read off the revision's "
            "dependency_classifications, so a revision that changes which sources are "
            "conditional on economic activity changes the set without a code edit"
        )

    @pytest.mark.parametrize("filing_year", _M100_YEARS)
    def test_candidate_set_excludes_every_source_the_taxpayer_never_files(self, filing_year: int) -> None:
        """A ``taxpayer_files_source = false`` source is never eligible for the zero-resolution.

        This is the load-bearing exclusion. Those sources are the suffered
        retenciones the payer files; their value is a real credit the taxpayer
        must declare, so the leg must stay unresolved rather than fold in as
        zero.
        """
        snapshot = _m100_snapshot(filing_year)
        payer_filed = frozenset(
            classification.source_modelo
            for classification in snapshot.revision.dependency_classifications
            if not classification.taxpayer_files_source
        )
        candidates = _economic_activity_conditional_source_modelos(snapshot)

        assert not (candidates & payer_filed), (
            f"Modelo 100 {filing_year}: sources {sorted(candidates & payer_filed)} are filed by the "
            "PAYER, so folding their relation in as zero would strip the taxpayer's retención "
            "credit from the declaration"
        )

    def test_the_exclusion_is_not_vacuous_for_modelo_100(self) -> None:
        """Modelo 100 really does declare payer-filed sources, so the exclusion above bites."""
        snapshot = _m100_snapshot(2025)
        payer_filed = frozenset(
            classification.source_modelo
            for classification in snapshot.revision.dependency_classifications
            if not classification.taxpayer_files_source
        )

        assert len(payer_filed) >= 2, (
            "Modelo 100 2025 must declare payer-filed retención sources for the "
            f"never-suppressed guard to be a real constraint; found {sorted(payer_filed)}"
        )


class TestVerdictWithinTheCandidateSet:
    """The profile decides the verdict; every arm stays inside the registry candidate set."""

    def test_no_economic_activity_suppresses_the_whole_conditional_set(self) -> None:
        """A salaried/rental-only filer owes no quarterly pago fraccionado at all."""
        bucket_id = _PROFILE_ID
        profile_reader = _profile_reader(
            (
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="capital_inmobiliario"),
            ),
        )
        snapshot = _m100_snapshot(2024)

        assert _not_applicable_source_modelos_for_bucket(
            snapshot,
            bucket_id,
            profile_path_values_reader=profile_reader,
        ) == _economic_activity_conditional_source_modelos(snapshot), (
            "a filer with no actividad económica owes neither pago-fraccionado modelo"
        )

    def test_estimacion_directa_suppresses_only_the_objetiva_modelo(self) -> None:
        """An estimación-directa autónomo files Modelo 130; Modelo 131 does not apply."""
        bucket_id = _PROFILE_ID
        profile_reader = _profile_reader(
            (
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_simplificada"),
            ),
        )
        snapshot = _m100_snapshot(2024)

        assert _not_applicable_source_modelos_for_bucket(
            snapshot,
            bucket_id,
            profile_path_values_reader=profile_reader,
        ) == frozenset({Modelo("131").value}), (
            "estimación directa suppresses only the estimación-objetiva modelo (RIRPF art. 110)"
        )

    def test_estimacion_objetiva_suppresses_only_the_directa_modelo(self) -> None:
        """An estimación-objetiva autónomo files Modelo 131; Modelo 130 does not apply."""
        bucket_id = _PROFILE_ID
        profile_reader = _profile_reader(
            (
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="objetiva"),
            ),
        )
        snapshot = _m100_snapshot(2024)

        assert _not_applicable_source_modelos_for_bucket(
            snapshot,
            bucket_id,
            profile_path_values_reader=profile_reader,
        ) == frozenset({Modelo("130").value}), (
            "estimación objetiva suppresses only the estimación-directa modelo (RIRPF art. 110)"
        )


class TestFailClosed:
    """A missing or undeclared profile fact leaves every source ENFORCED."""

    def test_absent_profile_suppresses_nothing(self) -> None:
        """No profile for the bucket means no positive not-applicable verdict."""
        bucket_id = _PROFILE_ID
        snapshot = _m100_snapshot(2024)

        assert (
            _not_applicable_source_modelos_for_bucket(
                snapshot,
                bucket_id,
                profile_path_values_reader=_ProfilePathValuesFake(None),
            )
            == frozenset()
        ), (
            "an absent profile must leave every cross-period source enforced, never fold a "
            "relation in as a zero the operator never declared"
        )

    def test_undeclared_income_categories_suppress_nothing(self) -> None:
        """Undeclared income categories are not a negative declaration."""
        bucket_id = _PROFILE_ID
        profile_reader = _profile_reader((UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),))
        snapshot = _m100_snapshot(2024)

        assert (
            _not_applicable_source_modelos_for_bucket(
                snapshot,
                bucket_id,
                profile_path_values_reader=profile_reader,
            )
            == frozenset()
        ), (
            "undeclared income categories must fail closed: the taxpayer may well carry on an "
            "economic activity, so both pago-fraccionado sources stay enforced"
        )

    def test_economic_activity_with_undeclared_regime_suppresses_nothing(self) -> None:
        """Economic activity whose estimation regime is undeclared cannot pick a modelo."""
        bucket_id = _PROFILE_ID
        profile_reader = _profile_reader(
            (
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            ),
        )
        snapshot = _m100_snapshot(2024)

        assert (
            _not_applicable_source_modelos_for_bucket(
                snapshot,
                bucket_id,
                profile_path_values_reader=profile_reader,
            )
            == frozenset()
        ), (
            "an undeclared estimation regime must fail closed here: neither pago-fraccionado "
            "source is positively not applicable, so both stay enforced"
        )

    def test_a_revision_declaring_no_conditional_source_suppresses_nothing(self) -> None:
        """A revision with no economic-activity-conditional dependency yields the empty set.

        Modelo 303 declares no ``conditional_on_economic_activity`` dependency, so
        even the maximal-suppression profile (no actividad económica) suppresses
        nothing there - the registry classification, not the profile, bounds the set.
        """
        bucket_id = _PROFILE_ID
        profile_reader = _profile_reader(
            (
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="capital_inmobiliario"),
            ),
        )
        snapshot = published_snapshot(Modelo("303").value, filing_year=2024, period="1T")
        assert _economic_activity_conditional_source_modelos(snapshot) == frozenset(), (
            "test precondition: Modelo 303 must declare no economic-activity-conditional dependency"
        )

        assert (
            _not_applicable_source_modelos_for_bucket(
                snapshot,
                bucket_id,
                profile_path_values_reader=profile_reader,
            )
            == frozenset()
        ), "a revision declaring no conditional dependency must suppress nothing regardless of the profile"
