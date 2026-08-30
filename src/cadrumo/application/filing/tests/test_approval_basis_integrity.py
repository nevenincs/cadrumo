"""The persisted approval basis is shape-constrained and its checksum is verified.

Two contracts on the approval metadata a draft carries once approved:

* ``ModeloApprovalBasis`` holds eight stale-detection fingerprints and a version.
  Every one was an unconstrained ``str``, so a blank, short, over-long,
  uppercase or non-hex value persisted and read back as if it were a
  content-addressed claim.

* ``approve_draft`` computes ``review_checksum`` over the basis, but
  ``refresh_review_status`` only checked that the checksum was *present* and
  then compared the basis fields, never re-deriving the checksum from the basis
  it had just loaded. A persisted approved draft whose checksum was replaced
  therefore stayed ``APROBADO`` while its aggregate claim was false.

The shapes asserted here are read off a genuinely approved draft rather than
assumed: seven fingerprints are SHA-256 hex-64, while
``draft_payload_fingerprint`` carries the draft's own 16-character content
address, so the eight are deliberately NOT one uniform type.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.filing.schema import APPROVAL_BASIS_VERSION, ModeloApprovalBasis, ModeloDraft
from ....domain.submission import ModeloDraftStatus
from ....tests.filing import build_registry_filing_draft_from_decimals
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    approve_draft,
    build_runtime_schema_provider,
    compute_review_checksum,
    empty_prior_filing_observations_fingerprint,
    empty_profile_activity_fingerprint,
    refresh_review_status,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "3f8c21a4-9d0e-4b77-8c1a-5e2b7d904f16"
_Q1_2026 = Period.from_year_and_code(2026, "1T")
_HEX64 = "a" * 64

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_PAGOS_PREVIOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")

_CASILLA_INPUTS: dict[CasillaId, str] = {
    _M130_INGRESOS_CASILLA: "12500.00",
    _M130_GASTOS_CASILLA: "3500.00",
    _M130_PAGOS_PREVIOS_CASILLA: "250.00",
    _M130_RETENCIONES_CASILLA: "100.00",
    _M130_AGRARIAN_VOLUME_CASILLA: "2000.00",
    _M130_AGRARIAN_WITHHELD_CASILLA: "10.00",
    _M130_HOME_DEDUCTION_CASILLA: "0.00",
    _M130_PRIOR_RETURN_CASILLA: "0.00",
}
_BINDING_INPUTS = {
    "irpf.previous_year_economic_activity_net_income": "13000.00",
    "modelo-130-pagos-fraccionados-anteriores": "250.00",
    "modelo-130-resultados-negativos-anteriores": "0.00",
}

_DIGEST_FIELDS = (
    "draft_review_fingerprint",
    "transaction_catalogue_fingerprint",
    "invoice_catalogue_fingerprint",
    "prior_filing_observations_fingerprint",
    "profile_activity_fingerprint",
    "category_profiles_fingerprint",
    "schema_formula_fingerprint",
)


def _ready_draft() -> ModeloDraft:
    return build_registry_filing_draft_from_decimals(
        modelo="130",
        period=_Q1_2026,
        casilla_decimals=_CASILLA_INPUTS,
        binding_decimals=_BINDING_INPUTS,
        status=ModeloDraftStatus.LISTO_PARA_PRESENTAR,
    )


def _approve(bucket_id: str) -> ModeloDraft:
    """Approve a real registry-backed draft through the production path."""
    schema_provider = build_runtime_schema_provider(
        modelos=("130",),
        filing_year=_Q1_2026.filing_year,
        period=_Q1_2026,
    )
    return approve_draft(
        _ready_draft(),
        bucket_id=bucket_id,
        approved_by="operator",
        schema_provider=schema_provider,
        prior_filing_observations_fingerprint=empty_prior_filing_observations_fingerprint(),
        profile_activity_fingerprint=empty_profile_activity_fingerprint(),
    )


def _valid_basis(**overrides: object) -> ModeloApprovalBasis:
    fields: dict[str, object] = {
        "draft_payload_fingerprint": "bc92044f18e612b9",
        "draft_review_fingerprint": _HEX64,
        "transaction_catalogue_fingerprint": _HEX64,
        "invoice_catalogue_fingerprint": _HEX64,
        "prior_filing_observations_fingerprint": _HEX64,
        "profile_activity_fingerprint": _HEX64,
        "category_profiles_fingerprint": _HEX64,
        "schema_formula_fingerprint": _HEX64,
    }
    fields.update(overrides)
    return ModeloApprovalBasis.model_validate(fields)


def test_real_approval_basis_has_the_shapes_this_module_pins(tmp_path: Path) -> None:
    """Read the fingerprint shapes off a genuinely approved draft.

    This is the grounding for the constraints below: it establishes empirically
    that seven fields are SHA-256 hex-64 while ``draft_payload_fingerprint``
    carries the draft's 16-character content address. A uniform hex-64 rule
    across all eight would refuse a value the approval path actually writes.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        approved = _approve(profile.bucket_id)

    basis = approved.approval_basis
    assert basis is not None
    assert basis.version == APPROVAL_BASIS_VERSION

    assert basis.draft_payload_fingerprint == approved.draft_id
    assert len(basis.draft_payload_fingerprint) == 16

    for field in _DIGEST_FIELDS:
        value = getattr(basis, field)
        assert len(value) == 64, f"{field} is not a hex-64 digest: {value!r}"
        assert value == value.lower()
        assert all(character in "0123456789abcdef" for character in value)


def test_valid_basis_constructs() -> None:
    """Positive control: the coherent shape is accepted, so refusals below discriminate."""
    basis = _valid_basis()

    assert basis.version == APPROVAL_BASIS_VERSION
    assert basis.schema_formula_fingerprint == _HEX64


@pytest.mark.parametrize("field", _DIGEST_FIELDS)
@pytest.mark.parametrize("malformed", ["", "a" * 63, "a" * 65, "A" * 64, "z" * 64, " " + "a" * 63])
def test_basis_refuses_a_malformed_digest_fingerprint(field: str, malformed: str) -> None:
    """A stale-detection digest must be a real content-addressed claim."""
    with pytest.raises(ValidationError):
        _valid_basis(**{field: malformed})


@pytest.mark.parametrize("malformed", ["", "bad", "BC92044F18E612B9", "z" * 16, "a" * 15, "a" * 17])
def test_basis_refuses_a_malformed_draft_content_address(malformed: str) -> None:
    """``draft_payload_fingerprint`` is the draft's own 16-hex content address."""
    with pytest.raises(ValidationError):
        _valid_basis(draft_payload_fingerprint=malformed)


@pytest.mark.parametrize("version", ["bogus-v0", "", "review-basis-v3"])
def test_basis_refuses_an_unknown_version(version: str) -> None:
    """The version names the basis layout this code computes, not free text."""
    with pytest.raises(ValidationError):
        _valid_basis(version=version)


def test_tampered_review_checksum_is_refused_on_refresh(tmp_path: Path) -> None:
    """A persisted approved draft whose checksum was replaced must not stay approved.

    The whole point of ``review_checksum`` is to be an aggregate claim over the
    basis. ``refresh_review_status`` checked only that it was present, so a
    draft with every basis field unchanged and an all-zero checksum refreshed
    to ``APROBADO`` — the tamper survived the reload unchallenged.

    The probe uses the real encrypted repository: approve, persist, replace only
    the checksum, reload through the production read path, refresh.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        schema_provider = build_runtime_schema_provider(
            modelos=("130",),
            filing_year=_Q1_2026.filing_year,
            period=_Q1_2026,
        )
        approved = _approve(profile.bucket_id)
        assert approved.status is ModeloDraftStatus.APROBADO
        assert approved.review_checksum is not None

        repository = ModeloDraftRepository(bucket_id=profile.bucket_id)
        # Only the checksum moves; every basis field and the draft's own
        # content address stay exactly as approved.
        repository.save(approved.model_copy(update={"review_checksum": "0" * 64}))

        reloaded = repository.load(approved.draft_id)
        assert reloaded is not None
        assert reloaded.approval_basis == approved.approval_basis

        refreshed = refresh_review_status(
            reloaded,
            bucket_id=profile.bucket_id,
            schema_provider=schema_provider,
            prior_filing_observations_fingerprint=empty_prior_filing_observations_fingerprint(),
            profile_activity_fingerprint=empty_profile_activity_fingerprint(),
        )

    assert refreshed.status is not ModeloDraftStatus.APROBADO


def test_untampered_approved_draft_survives_refresh(tmp_path: Path) -> None:
    """Positive control: an intact approval still refreshes to APROBADO.

    Without it the tamper test would also pass if refresh simply demoted every
    draft it was handed.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        schema_provider = build_runtime_schema_provider(
            modelos=("130",),
            filing_year=_Q1_2026.filing_year,
            period=_Q1_2026,
        )
        approved = _approve(profile.bucket_id)
        repository = ModeloDraftRepository(bucket_id=profile.bucket_id)
        repository.save(approved)

        reloaded = repository.load(approved.draft_id)
        assert reloaded is not None

        refreshed = refresh_review_status(
            reloaded,
            bucket_id=profile.bucket_id,
            schema_provider=schema_provider,
            prior_filing_observations_fingerprint=empty_prior_filing_observations_fingerprint(),
            profile_activity_fingerprint=empty_profile_activity_fingerprint(),
        )

    assert refreshed.status is ModeloDraftStatus.APROBADO
    assert approved.approval_basis is not None
    assert refreshed.review_checksum == compute_review_checksum(approved.approval_basis)


def test_approved_at_is_utc(tmp_path: Path) -> None:
    """The approval instant a real approval stamps is UTC-aware."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        approved = _approve(profile.bucket_id)

    assert approved.approved_at is not None
    assert approved.approved_at.tzinfo is not None
    assert approved.approved_at.utcoffset() == datetime.now(UTC).utcoffset()
