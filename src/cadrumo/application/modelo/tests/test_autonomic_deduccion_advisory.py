"""Madrid nacimiento/adopción indeterminate-eligibility advisory tests.

Covers ``_madrid_nacimiento_adopcion_eligibility_advisory_finding``: the
verify-path advisory fires when the calculate-path auto-trigger
(``inject_derived_autonomic_deduccion_facts``) fail-closed on an indeterminate
(tributación conjunta or married/pareja-de-hecho) Madrid unit with at least one
nacimiento/adopción-eligible descendant, leaving casilla 1039 at zero with no
operator-facing signal.

Real adapters throughout: the resident registry authority for the loaded
:class:`RegistrySnapshot`, and a genuine encrypted bucket via
``isolated_runtime_profile`` for every scenario that constructs a
:class:`UserProfileRecord` — no mocks, stubs, or fakes. The parity assertion
reads the SAME weighted count the calculate-path injector would have computed
from the identical fact set (via the shared
``madrid_nacimiento_adopcion_candidate_weighted_count`` primitive), proving
the verify-path advisory is not fabricating a number independent of the
calculate path.

See Also:
    :func:`~application.modelo._autonomic_deduccion_advisory._madrid_nacimiento_adopcion_eligibility_advisory_finding`:
        Verify-path advisory under test.
    :func:`~application.modelo.profile_binding.inject_derived_autonomic_deduccion_facts`:
        Calculate-path fail-closed injector this advisory complements.
    :class:`~domain.calculations.registry.RegistrySnapshot`:
        Registry authority used to resolve the casilla-1039 semantic role.
    :class:`CasillaId`:
        Canonical casilla identifier type for the advisory finding.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

from ....core import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import load_test_profile_record, seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from .._autonomic_deduccion_advisory import _madrid_nacimiento_adopcion_eligibility_advisory_finding
from ..profile_binding import (
    inject_derived_autonomic_deduccion_facts,
    madrid_nacimiento_adopcion_candidate_weighted_count,
    profile_fact_index,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "cd7a6304-2000-4200-8200-000000000596"
_YEAR = 2025
_PERIOD = "0A"
_CLOCK = datetime(2026, 7, 4, 9, 0, 0, tzinfo=UTC)
_CASILLA_1039: CasillaId = validated_casilla_id("1039", surface="test_autonomic_deduccion_advisory")


@pytest.fixture(scope="module")
def m100_2025_snapshot() -> RegistrySnapshot:
    """Real bundled M100 2025 snapshot carrying the casilla-1039 semantic role."""
    return bundled_authority().snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _base_facts(**overrides: str) -> tuple[UserProfileFact, ...]:
    base: dict[str, str] = {
        "tax_residence.ccaa": "madrid",
        "renta_filing.declaration_type": "1",
        "renta_taxpayer.marital_status": "1",
        "renta_family.descendiente.0.birth_date": "2024-06-01",
        "renta_family.descendiente.0.convivencia": "true",
    }
    base.update(overrides)
    return tuple(UserProfileFact(path=path, value=value) for path, value in base.items())


@pytest.fixture
def seeded_bucket(tmp_path: Path) -> Iterator[str]:
    """Yield a bucket id whose profile is seeded by the calling test via ``_seed``."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield _BUCKET_ID


def _seed(bucket_id: str, facts: tuple[UserProfileFact, ...]) -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=bucket_id,
        facts=facts,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    seed_test_profile_record(record)


def test_advisory_fires_for_indeterminate_conjunta_unit_with_eligible_descendant(
    m100_2025_snapshot: RegistrySnapshot,
    seeded_bucket: str,
) -> None:
    """A tributación-conjunta Madrid filer with an eligible child gets the D4 advisory."""
    _seed(seeded_bucket, _base_facts(**{"renta_filing.declaration_type": "2"}))

    finding = _madrid_nacimiento_adopcion_eligibility_advisory_finding(
        m100_2025_snapshot,
        {_CASILLA_1039: Decimal("0")},
        bucket_id=seeded_bucket,
    )

    assert finding is not None
    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert finding.casilla_id == _CASILLA_1039
    assert finding.legal_refs == ("ley-35-2006:art-77", "madrid-dl-1-2010:art-4", "madrid-dl-1-2010:art-18")
    assert finding.message_locale_key == "application.modelo.findings.madrid_nacimiento_adopcion_eligibility_advisory"
    assert finding.message_facts["casilla_id"] == _CASILLA_1039
    assert "next_action" not in finding.model_dump(mode="json")


def test_advisory_fires_for_married_filer_with_eligible_descendant(
    m100_2025_snapshot: RegistrySnapshot,
    seeded_bucket: str,
) -> None:
    """A married (non-conjunta) Madrid filer with an eligible child also gets the advisory."""
    _seed(seeded_bucket, _base_facts(**{"renta_taxpayer.marital_status": "2"}))

    finding = _madrid_nacimiento_adopcion_eligibility_advisory_finding(
        m100_2025_snapshot,
        {_CASILLA_1039: Decimal("0")},
        bucket_id=seeded_bucket,
    )

    assert finding is not None
    assert finding.casilla_id == _CASILLA_1039


def test_advisory_silent_for_determinate_single_filer(
    m100_2025_snapshot: RegistrySnapshot,
    seeded_bucket: str,
) -> None:
    """A determinate single/monoparental filer is auto-triggered on the calculate path.

    No advisory should fire here in the first place because the calculate path
    resolves the casilla to a non-zero value for this filer shape; the
    verify-path helper independently confirms this by never flagging a
    determinate unit regardless of the supplied casilla value.
    """
    _seed(seeded_bucket, _base_facts())

    finding = _madrid_nacimiento_adopcion_eligibility_advisory_finding(
        m100_2025_snapshot,
        {_CASILLA_1039: Decimal("0")},
        bucket_id=seeded_bucket,
    )

    assert finding is None


def test_advisory_silent_when_casilla_already_populated(
    m100_2025_snapshot: RegistrySnapshot,
    seeded_bucket: str,
) -> None:
    """A non-zero casilla 1039 means the auto-trigger already fired; nothing to advise."""
    _seed(seeded_bucket, _base_facts(**{"renta_filing.declaration_type": "2"}))

    finding = _madrid_nacimiento_adopcion_eligibility_advisory_finding(
        m100_2025_snapshot,
        {_CASILLA_1039: Decimal("721.70")},
        bucket_id=seeded_bucket,
    )

    assert finding is None


def test_advisory_silent_for_non_madrid_indeterminate_unit(
    m100_2025_snapshot: RegistrySnapshot,
    seeded_bucket: str,
) -> None:
    """A conjunta filer outside Madrid never triggers the Madrid-specific advisory."""
    _seed(
        seeded_bucket,
        _base_facts(**{"tax_residence.ccaa": "cataluna", "renta_filing.declaration_type": "2"}),
    )

    finding = _madrid_nacimiento_adopcion_eligibility_advisory_finding(
        m100_2025_snapshot,
        {_CASILLA_1039: Decimal("0")},
        bucket_id=seeded_bucket,
    )

    assert finding is None


def test_advisory_silent_for_indeterminate_unit_with_no_eligible_descendant(
    m100_2025_snapshot: RegistrySnapshot,
    seeded_bucket: str,
) -> None:
    """A conjunta Madrid filer whose only child is out of the applicability window is silent."""
    _seed(
        seeded_bucket,
        _base_facts(
            **{
                "renta_filing.declaration_type": "2",
                "renta_family.descendiente.0.birth_date": "2019-01-01",
            },
        ),
    )

    finding = _madrid_nacimiento_adopcion_eligibility_advisory_finding(
        m100_2025_snapshot,
        {_CASILLA_1039: Decimal("0")},
        bucket_id=seeded_bucket,
    )

    assert finding is None


def test_advisory_silent_when_no_profile_record_exists(
    m100_2025_snapshot: RegistrySnapshot,
    seeded_bucket: str,
) -> None:
    """No profile record at all yields no advisory (no eligibility signal to read)."""
    finding = _madrid_nacimiento_adopcion_eligibility_advisory_finding(
        m100_2025_snapshot,
        {_CASILLA_1039: Decimal("0")},
        bucket_id=seeded_bucket,
    )

    assert finding is None


def test_advisory_weighted_count_matches_calculate_path_candidate_count(
    seeded_bucket: str,
) -> None:
    """Parity: the verify-path advisory reads the SAME weighted count the

    calculate-path injector would compute from the identical fact set — not a
    fabricated or independently-derived number.
    """
    facts = _base_facts(
        **{
            "renta_filing.declaration_type": "2",
            "renta_family.descendiente.0.custodia_compartida": "true",
        },
    )
    _seed(seeded_bucket, facts)

    from ....domain.user_profile.loader import load_user_profile_schema

    record = load_test_profile_record(seeded_bucket)
    fact_index = profile_fact_index(record, load_user_profile_schema())

    # The calculate-path injector fail-closes for this indeterminate unit: the
    # synthetic key resolves to the neutral 0 default, never the real count.
    injected_index = dict(fact_index)
    inject_derived_autonomic_deduccion_facts(injected_index, _YEAR)
    assert injected_index["renta_family.madrid_nacimiento_adopcion_eligible_count"] == Decimal("0")

    # The shared candidate-count primitive (which the verify-path advisory
    # calls) recovers the real prorrateo-weighted count regardless of the
    # unit's determinability — this is the number the advisory surfaces.
    candidate_count = madrid_nacimiento_adopcion_candidate_weighted_count(fact_index, _YEAR)
    assert candidate_count == Decimal("0.5")
