"""Strict roundtrip across the WithholdingObservationRepository boundary (#28 P03).

Persists per-perceptor-clave :class:`WithholdingObservation` records at
``SensitivityClass.FINANCIAL`` keyed by ``(modelo, filing_year, period,
sha256(perceptor_tax_id), clave, subclave)`` — the DEDICATED store the calc-mesh
percepciones-count resolver reads so Modelo 190 counts percepciones (registros de
tipo 2) distinctly.

Anti-tautology: a populated observation carries every field non-default, and one
perceptor under two claves persists as TWO distinct rows (the percepciones key
includes clave/subclave) — a save-drops-field or key-collision regression
surfaces as inequality or a lost row on reload. The plaintext NIF must never
appear in the object key (only its sha256); the clave/subclave are
non-identifying AEAT codes and stay plain.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core import Period
from ....core.external_constants import UTF_8_ENCODING
from ....domain.calculations.registry import WithholdingObservation
from ....tests.secure_sql import isolated_runtime_profile
from .._withholding_observations_repository import (
    WithholdingObservationRepository,
    persist_withholding_observations,
    withholding_observation_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _observation(
    *,
    nif: str,
    clave: str,
    subclave: str = "",
    dinerario: Decimal = Decimal("1000"),
) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=f"row-{nif}-{clave}-{subclave or '-'}",
        perceptor_tax_id=nif,
        perceptor_legal_name="Perceptor Ejemplo SL",
        country_code="ES",
        transaction_date=date(2024, 3, 15),
        clave=clave,
        subclave=subclave,
        percibido_dinerario=dinerario,
        percibido_especie=Decimal("50"),
        retencion_practicada=dinerario * Decimal("0.19"),
        ingreso_a_cuenta=Decimal("5"),
    )


def test_withholding_observation_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """A populated WithholdingObservation roundtrips byte-for-byte through the encrypted repo."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _observation(nif="11111111H", clave="A", subclave="01")
        repo = WithholdingObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        repo.save_observation(
            modelo="190",
            filing_year=2024,
            period=period,
            observation=original,
            source_kind="aggregate_pull",
            captured_at=None,
            source_metadata={"origin": "pull"},
        )
        loaded = repo.load_observations("190", period)

        assert loaded == (original,)


def test_corrupt_clave_or_subclave_refused_on_reload() -> None:
    """Anti-tautology (#29): a persisted observation whose clave/subclave was
    corrupted to an invalid token is REFUSED when reconstituted.

    The repository deserialises each stored record through
    ``WithholdingObservation`` validation (``model_validate`` -- the same path
    ``load_observations`` runs), so a save-valid / load-corrupt regression cannot
    pass silently now that ``clave`` is the typed RetencionClave and ``subclave`` is
    numeric. If this ever passes with a corrupt token, every roundtrip above is
    tautological.
    """
    valid = _observation(nif="11111111H", clave="A", subclave="01")

    corrupt_clave = valid.model_dump()
    corrupt_clave["clave"] = "ZZ"  # not an AEAT clave letter (A-L)
    with pytest.raises(ValidationError):
        WithholdingObservation.model_validate(corrupt_clave)

    corrupt_subclave = valid.model_dump()
    corrupt_subclave["subclave"] = "XX"  # subclave is numeric
    with pytest.raises(ValidationError):
        WithholdingObservation.model_validate(corrupt_subclave)


def test_one_perceptor_two_claves_persist_as_distinct_percepciones(tmp_path: Path) -> None:
    """One perceptor under two claves persists as TWO distinct rows (percepciones key)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = WithholdingObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        records = (
            _observation(nif="11111111H", clave="A"),
            _observation(nif="22222222J", clave="A"),
            # Same NIF as the first, different clave — a distinct percepción, not an overwrite.
            _observation(nif="11111111H", clave="G"),
        )
        for record in records:
            repo.save_observation(
                modelo="190",
                filing_year=2024,
                period=period,
                observation=record,
                source_kind="aggregate_pull",
            )
        loaded = repo.load_observations("190", period)
        # All three rows survive (no key collision); the two 11111111H rows are
        # distinct because the clave is part of the key.
        assert len(loaded) == 3
        assert {(o.perceptor_tax_id, o.clave, o.subclave) for o in loaded} == {
            ("11111111H", "A", ""),
            ("22222222J", "A", ""),
            ("11111111H", "G", ""),
        }
        # Distinct percepciones = 3; distinct perceptores = 2 (the #28 vs #6 delta).
        assert len({o.perceptor_tax_id for o in loaded}) == 2


def test_object_key_hashes_the_nif_never_cleartext() -> None:
    """The object key carries the sha256 of the NIF, never the plaintext; clave/subclave stay plain."""
    key = withholding_observation_key("190", 2024, Period.from_year_and_code(2024, "0A"), "11111111H", "A", "01")
    assert "11111111H" not in key
    digest = hashlib.sha256("11111111H".encode(UTF_8_ENCODING)).hexdigest()
    assert digest in key
    assert key == f"190:2024:0A:{digest}:A:01"


def test_blank_subclave_keys_as_dash() -> None:
    """A blank subclave is keyed as '-' so the grammar segment is never empty."""
    key = withholding_observation_key("190", 2024, Period.from_year_and_code(2024, "0A"), "11111111H", "B", "")
    assert key.endswith(":B:-")


def test_period_scoping_excludes_other_windows(tmp_path: Path) -> None:
    """load_observations returns only the requested (modelo, year, period)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = WithholdingObservationRepository()
        obs = _observation(nif="33333333P", clave="C")
        repo.save_observation(
            modelo="190",
            filing_year=2023,
            period=Period.from_year_and_code(2023, "0A"),
            observation=obs,
            source_kind="aggregate_pull",
        )
        assert repo.load_observations("190", Period.from_year_and_code(2024, "0A")) == ()
        assert repo.load_observations("190", Period.from_year_and_code(2023, "0A")) == (obs,)


def test_anti_tautology_strict_payload_rejects_dropped_field() -> None:
    """The envelope payload is strict: a dropped required field raises, never silently defaults."""
    from datetime import UTC, datetime

    from .._withholding_observations_repository import _WithholdingObservationEnvelopePayload

    full = {
        "modelo": "190",
        "filing_year": 2024,
        "period": Period.from_year_and_code(2024, "0A"),
        "observation": _observation(nif="44444444A", clave="A"),
        "captured_at": datetime.now(UTC),
        "source_kind": "aggregate_pull",
    }
    _WithholdingObservationEnvelopePayload.model_validate(full)
    partial = {k: v for k, v in full.items() if k != "observation"}
    with pytest.raises(ValidationError):
        _WithholdingObservationEnvelopePayload.model_validate(partial)


def test_replace_observations_drops_removed_percepcion_no_stale_row(tmp_path: Path) -> None:
    """Re-persisting a SHRUNK set removes the dropped percepción — no stale over-count."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = WithholdingObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        full = (
            _observation(nif="11111111H", clave="A"),
            _observation(nif="11111111H", clave="G"),
            _observation(nif="22222222J", clave="A"),
        )
        repo.replace_observations(
            modelo="190", filing_year=2024, period=period, observations=full, source_kind="aggregate_pull",
        )
        assert len(repo.load_observations("190", period)) == 3
        # Re-pull dropped the 11111111H/clave-G percepción.
        repo.replace_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=full[:1] + full[2:],
            source_kind="aggregate_pull",
        )
        loaded = repo.load_observations("190", period)
        assert len(loaded) == 2
        assert {(o.perceptor_tax_id, o.clave) for o in loaded} == {("11111111H", "A"), ("22222222J", "A")}


def test_persist_helper_writes_set_readable_by_load(tmp_path: Path) -> None:
    """The shared write helper persists the set the resolver later reads (one source, both surfaces)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        period = Period.from_year_and_code(2024, "0A")
        observations = (
            _observation(nif="11111111H", clave="A"),
            _observation(nif="11111111H", clave="G"),
        )
        persist_withholding_observations(modelo="190", filing_year=2024, period=period, observations=observations)
        loaded = WithholdingObservationRepository().load_observations("190", period)
        assert set(loaded) == set(observations)
