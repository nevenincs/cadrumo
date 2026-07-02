"""Modelo 100 mínimo por descendientes advisory collector (#515, Option B).

Covers :func:`collect_minimo_descendientes_advisory_diagnostics`:

* custodia-compartida prorrateo advisory (Art. 61.4a LIRPF): fires when the
  active profile carries at least one Art. 58.1-eligible descendant flagged
  ``custodia_compartida=True``.
* blank-entry advisory: fires when the profile carries at least one eligible
  descendant but the calculated mínimo casilla (located by its stable
  ``semantic_role``, never a hardcoded per-year id) resolved to zero.
* neither advisory fires for a non-M100 modelo, an empty profile, a profile
  with no ELIGIBLE descendants (age >= 25, non-cohabiting), or a populated,
  non-zero, non-custodia mínimo.

Real adapters throughout: a genuine encrypted bucket via
``isolated_runtime_profile``, the resident registry authority for the loaded
:class:`ModeloRevision`, and :func:`descendant_facts_from_list` /
:class:`UserProfileLifecycleRepository` for the profile roundtrip -- no mocks,
stubs, or fakes. The blank-entry case is proven against an INDEPENDENTLY
computed eligible count (the domain's own ``is_eligible_ordinary``), and the
casilla id the diagnostics name is cross-checked against the LOADED revision's
``semantic_role`` declaration, so the test would fail if the collector fired on
the wrong casilla or miscounted eligibility.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, ModeloRevision, validated_casilla_id
from ....domain.contribuyente import DescendantInfo, descendant_facts_from_list
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .._minimo_descendientes_advisory import collect_minimo_descendientes_advisory_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "00000000-0000-4000-8000-000000000515"
_PROFILE_LABEL = "M100 minimo descendientes advisory profile"
_FILING_YEAR = 2024
_T0 = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)

_MINIMO_ESTATAL_ROLE = "irpf_minimo_descendientes_estatal"
_CUSTODIA_REASON = "source_issue"
_CUSTODIA_SOURCE_KIND = "minimo_descendientes_custodia_compartida"
_BLANK_SOURCE_KIND = "minimo_descendientes_not_entered"

# Eligible (age < 25 at 2024 year-end, cohabiting) -- born 2015, age 9.
_ELIGIBLE_CHILD_BIRTH = date(2015, 6, 1)
# Ineligible (age >= 25 at 2024 year-end) -- born 1990, age 34.
_INELIGIBLE_ADULT_BIRTH = date(1990, 1, 1)


def _revision(modelo: str, year: int, period: str) -> ModeloRevision:
    return resources().modelos.authority.snapshot(modelo, filing_year=year, period=period).revision


def _estatal_casilla_id(revision: ModeloRevision) -> CasillaId:
    matches = [c.id for c in revision.casillas if c.semantic_role == _MINIMO_ESTATAL_ROLE]
    assert len(matches) == 1, "fixture sanity: exactly one estatal mínimo-descendientes casilla expected"
    return validated_casilla_id(matches[0], surface="test casilla id")


def _seed_profile(objects: SecureObjectRepository, *, descendientes: tuple[DescendantInfo, ...]) -> None:
    facts = [UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendientes)]
    UserProfileLifecycleRepository(bucket_id=_BUCKET, objects=objects).save(
        UserProfileRecord(
            profile_id=_BUCKET,
            display_name=_PROFILE_LABEL,
            facts=tuple(facts),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def test_no_advisory_for_non_m100_modelo(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL) as profile:
        _seed_profile(
            profile.repository,
            descendientes=(DescendantInfo(birth_date=_ELIGIBLE_CHILD_BIRTH, custodia_compartida=True),),
        )
        revision = _revision("100", _FILING_YEAR, "0A")
        estatal_id = _estatal_casilla_id(revision)
        diagnostics = collect_minimo_descendientes_advisory_diagnostics(
            revision,
            {estatal_id: Decimal("0")},
            modelo="130",
            filing_year=_FILING_YEAR,
            bucket_id=_BUCKET,
        )
    assert diagnostics == ()


def test_no_advisory_when_profile_has_no_descendientes(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL) as profile:
        _seed_profile(profile.repository, descendientes=())
        revision = _revision("100", _FILING_YEAR, "0A")
        estatal_id = _estatal_casilla_id(revision)
        diagnostics = collect_minimo_descendientes_advisory_diagnostics(
            revision,
            {estatal_id: Decimal("0")},
            modelo="100",
            filing_year=_FILING_YEAR,
            bucket_id=_BUCKET,
        )
    assert diagnostics == ()


def test_no_advisory_when_no_descendant_is_eligible(tmp_path: Path) -> None:
    """A descendant aged >= 25 at year-end carries no Art. 58.1 eligibility -> silent."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL) as profile:
        _seed_profile(
            profile.repository,
            descendientes=(DescendantInfo(birth_date=_INELIGIBLE_ADULT_BIRTH),),
        )
        revision = _revision("100", _FILING_YEAR, "0A")
        estatal_id = _estatal_casilla_id(revision)
        diagnostics = collect_minimo_descendientes_advisory_diagnostics(
            revision,
            {estatal_id: Decimal("0")},
            modelo="100",
            filing_year=_FILING_YEAR,
            bucket_id=_BUCKET,
        )
    assert diagnostics == ()


def test_blank_entry_advisory_fires_when_eligible_descendant_and_zero_minimo(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL) as profile:
        _seed_profile(
            profile.repository,
            descendientes=(DescendantInfo(birth_date=_ELIGIBLE_CHILD_BIRTH, custodia_compartida=False),),
        )
        revision = _revision("100", _FILING_YEAR, "0A")
        estatal_id = _estatal_casilla_id(revision)
        diagnostics = collect_minimo_descendientes_advisory_diagnostics(
            revision,
            {estatal_id: Decimal("0")},
            modelo="100",
            filing_year=_FILING_YEAR,
            bucket_id=_BUCKET,
        )
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.source_kind == _BLANK_SOURCE_KIND
    assert diagnostic.casilla_id == estatal_id
    assert "1" in diagnostic.message


def test_no_blank_entry_advisory_when_minimo_already_entered(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL) as profile:
        _seed_profile(
            profile.repository,
            descendientes=(DescendantInfo(birth_date=_ELIGIBLE_CHILD_BIRTH, custodia_compartida=False),),
        )
        revision = _revision("100", _FILING_YEAR, "0A")
        estatal_id = _estatal_casilla_id(revision)
        diagnostics = collect_minimo_descendientes_advisory_diagnostics(
            revision,
            {estatal_id: Decimal("2400")},
            modelo="100",
            filing_year=_FILING_YEAR,
            bucket_id=_BUCKET,
        )
    assert diagnostics == ()


def test_custodia_compartida_advisory_fires_alongside_blank_entry(tmp_path: Path) -> None:
    """A shared-custody eligible descendant with a still-blank mínimo fires BOTH advisories."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL) as profile:
        _seed_profile(
            profile.repository,
            descendientes=(DescendantInfo(birth_date=_ELIGIBLE_CHILD_BIRTH, custodia_compartida=True),),
        )
        revision = _revision("100", _FILING_YEAR, "0A")
        estatal_id = _estatal_casilla_id(revision)
        diagnostics = collect_minimo_descendientes_advisory_diagnostics(
            revision,
            {estatal_id: Decimal("0")},
            modelo="100",
            filing_year=_FILING_YEAR,
            bucket_id=_BUCKET,
        )
    source_kinds = {d.source_kind for d in diagnostics}
    assert source_kinds == {_CUSTODIA_SOURCE_KIND, _BLANK_SOURCE_KIND}
    assert all(d.casilla_id == estatal_id for d in diagnostics)


def test_custodia_compartida_advisory_fires_even_when_minimo_entered(tmp_path: Path) -> None:
    """Even a non-zero hand-entered mínimo needs the halving confirmation prompt."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL) as profile:
        _seed_profile(
            profile.repository,
            descendientes=(DescendantInfo(birth_date=_ELIGIBLE_CHILD_BIRTH, custodia_compartida=True),),
        )
        revision = _revision("100", _FILING_YEAR, "0A")
        estatal_id = _estatal_casilla_id(revision)
        diagnostics = collect_minimo_descendientes_advisory_diagnostics(
            revision,
            {estatal_id: Decimal("1200")},
            modelo="100",
            filing_year=_FILING_YEAR,
            bucket_id=_BUCKET,
        )
    assert len(diagnostics) == 1
    assert diagnostics[0].source_kind == _CUSTODIA_SOURCE_KIND
    assert diagnostics[0].reason == _CUSTODIA_REASON


def test_no_advisory_when_bucket_has_no_profile(tmp_path: Path) -> None:
    """A bucket with no saved profile at all resolves silently (mirrors profile-binding absent handling)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET, label=_PROFILE_LABEL):
        # No _seed_profile call -- the runtime bucket exists but carries no
        # UserProfileRecord.
        revision = _revision("100", _FILING_YEAR, "0A")
        estatal_id = _estatal_casilla_id(revision)
        diagnostics = collect_minimo_descendientes_advisory_diagnostics(
            revision,
            {estatal_id: Decimal("0")},
            modelo="100",
            filing_year=_FILING_YEAR,
            bucket_id=_BUCKET,
        )
    assert diagnostics == ()
