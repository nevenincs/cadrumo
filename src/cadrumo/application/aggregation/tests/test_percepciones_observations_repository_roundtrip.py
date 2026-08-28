"""Strict roundtrip across the PercepcionObservationRepository boundary.

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
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import PathContainmentError, SecureObjectRowIdentityError
from ....adapters.persistence.storage.crypto.encrypted_columns import secure_object_key_digest
from ....core import AggregationCaptureKind, Period
from ....core.aggregation import RetencionClave
from ....core.external_constants import UTF_8_ENCODING
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation, aggregate_withholding_by_clave
from ....tests.secure_sql import isolated_runtime_profile
from .._percepciones_observations_repository import (
    PercepcionObservationRepository,
    percepcion_observation_key,
    persist_percepcion_observations,
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
        clave=RetencionClave(clave),
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
        repo = PercepcionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        repo.save_observation(
            modelo="190",
            filing_year=2024,
            period=period,
            observation=original,
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
            captured_at=None,
            source_metadata={"origin": "pull"},
        )
        loaded = repo.load_observations("190", period)

        assert loaded == (original,)


def test_corrupt_clave_or_subclave_refused_on_reload() -> None:
    """Anti-tautology: a persisted observation whose clave/subclave was
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
        repo = PercepcionObservationRepository()
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
                source_kind=AggregationCaptureKind.AGGREGATE_PULL,
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
        # Distinct percepciones = 3; distinct perceptores = 2 (the percepciones-count
        # vs perceptor-count delta).
        assert len({o.perceptor_tax_id for o in loaded}) == 2


def test_object_key_hashes_the_nif_never_cleartext() -> None:
    """The object key carries the sha256 of the NIF, never the plaintext; clave/subclave stay plain."""
    key = percepcion_observation_key("190", 2024, Period.from_year_and_code(2024, "0A"), "11111111H", "A", "01")
    assert "11111111H" not in key
    digest = hashlib.sha256("11111111H".encode(UTF_8_ENCODING)).hexdigest()
    assert digest in key
    assert key == f"190:2024:0A:{digest}:A:01"


def test_blank_subclave_keys_as_dash() -> None:
    """A blank subclave is keyed as '-' so the grammar segment is never empty."""
    key = percepcion_observation_key("190", 2024, Period.from_year_and_code(2024, "0A"), "11111111H", "B", "")
    assert key.endswith(":B:-")


def test_period_scoping_excludes_other_windows(tmp_path: Path) -> None:
    """load_observations returns only the requested (modelo, year, period)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = PercepcionObservationRepository()
        obs = _observation(nif="33333333P", clave="C")
        repo.save_observation(
            modelo="190",
            filing_year=2023,
            period=Period.from_year_and_code(2023, "0A"),
            observation=obs,
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        assert repo.load_observations("190", Period.from_year_and_code(2024, "0A")) == ()
        assert repo.load_observations("190", Period.from_year_and_code(2023, "0A")) == (obs,)


def test_anti_tautology_strict_payload_rejects_dropped_field() -> None:
    """The envelope payload is strict: a dropped required field raises, never silently defaults."""
    from datetime import UTC, datetime

    from .._percepciones_observations_repository import _PercepcionObservationEnvelopePayload

    full = {
        "modelo": "190",
        "filing_year": 2024,
        "period": Period.from_year_and_code(2024, "0A"),
        "observation": _observation(nif="44444444A", clave="A"),
        "captured_at": datetime.now(UTC),
        "source_kind": AggregationCaptureKind.AGGREGATE_PULL,
    }
    _PercepcionObservationEnvelopePayload.model_validate(full)
    partial = {k: v for k, v in full.items() if k != "observation"}
    with pytest.raises(ValidationError):
        _PercepcionObservationEnvelopePayload.model_validate(partial)


def test_replace_observations_drops_removed_percepcion_no_stale_row(tmp_path: Path) -> None:
    """Re-persisting a SHRUNK set removes the dropped percepción — no stale over-count."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = PercepcionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        full = (
            _observation(nif="11111111H", clave="A"),
            _observation(nif="11111111H", clave="G"),
            _observation(nif="22222222J", clave="A"),
        )
        repo.replace_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=full,
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        assert len(repo.load_observations("190", period)) == 3
        # Re-pull dropped the 11111111H/clave-G percepción.
        repo.replace_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=full[:1] + full[2:],
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
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
        persist_percepcion_observations(modelo="190", filing_year=2024, period=period, observations=observations)
        loaded = PercepcionObservationRepository().load_observations("190", period)
        assert set(loaded) == set(observations)


def test_failed_replacement_leaves_the_prior_window_intact(tmp_path: Path) -> None:
    """A replacement that cannot be committed leaves the declared window untouched.

    The set-replace used to commit each stale-row delete before looping through
    the saves one at a time, so a refusal part-way through destroyed the prior
    declared set and left only the rows written before the failure. The next
    calculate then read that partial window as the operator's declared truth —
    a silent under-count whose own evidence had already been deleted. Nothing
    may reach storage until the whole replacement is prepared.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = PercepcionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        declared = (
            _observation(nif="11111111H", clave="A"),
            _observation(nif="22222222J", clave="A"),
            _observation(nif="33333333P", clave="B"),
        )
        repo.replace_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=declared,
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )

        replacement = repo.build_observation_payload(
            modelo="190",
            filing_year=2024,
            period=period,
            observation=_observation(nif="44444444A", clave="A"),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        stale_identifiers = tuple(repo.extract_identifier(row) for row in repo.iter_records())
        with pytest.raises(PathContainmentError):
            repo.replace_records((replacement,), (*stale_identifiers, "190:2024:0A:../escape:A:-"))

        survived = repo.load_observations("190", period)
        assert set(survived) == set(declared)


def test_replacement_carries_over_a_row_present_in_both_sets(tmp_path: Path) -> None:
    """A key in both the old and the new set is updated, never deleted.

    Writes and deletions commit in one transaction with writes applied first, so
    a row whose key is carried across the replacement must be excluded from the
    stale set — otherwise it is upserted and then removed in the same unit of
    work and the operator loses a percepción they still declare.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = PercepcionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        repo.replace_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=(
                _observation(nif="11111111H", clave="A"),
                _observation(nif="22222222J", clave="A"),
            ),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        carried = _observation(nif="11111111H", clave="A", dinerario=Decimal("2500"))
        repo.replace_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=(carried,),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )

        assert repo.load_observations("190", period) == (carried,)


def test_whitespace_variant_tax_ids_are_one_perceptor_in_store_and_aggregation(tmp_path: Path) -> None:
    """Canonically-equal perceptor declarations resolve to ONE percepción everywhere.

    The observation model held the tax ID exactly as declared while the
    repository trimmed and uppercased it before hashing it into the object key.
    Two declarations of the same perceptor under the same clave, differing only
    in surrounding whitespace or letter case, were therefore counted as two
    distinct percepciones while sharing a single stored row whose later write
    overwrote the earlier evidence — the declared registro-tipo-2 count and the
    persisted evidence disagreeing.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = PercepcionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        padded = _observation(nif=" 12345678z ", clave="A", dinerario=Decimal("1000"))
        canonical = _observation(nif="12345678Z", clave="A", dinerario=Decimal("2000"))

        # The model itself canonicalises, so the aggregation identity matches.
        assert padded.perceptor_tax_id == canonical.perceptor_tax_id == "12345678Z"

        # One distinct (perceptor, clave, subclave) percepcion, not two.
        breakdown = aggregate_withholding_by_clave((padded, canonical))
        assert sum(row.percepcion_count for row in breakdown) == 1

        repo.replace_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=(padded, canonical),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        stored = repo.load_observations("190", period)
        assert len(stored) == 1
        assert len({o.perceptor_tax_id for o in stored}) == 1


def test_padded_tax_id_keys_to_the_canonical_object_key() -> None:
    """A padded declaration and its canonical form address the same stored row."""
    period = Period.from_year_and_code(2024, "0A")
    padded_key = percepcion_observation_key("190", 2024, period, " 12345678z ", "A", "")
    canonical_key = percepcion_observation_key("190", 2024, period, "12345678Z", "A", "")
    assert padded_key == canonical_key


def test_window_scan_refuses_a_row_filed_under_another_perceptors_key(tmp_path: Path) -> None:
    """A payload stored under a different row's key is refused, not projected.

    The object key is derived from the payload's own natural identity, so the
    two are two encodings of one fact. The window scan used to filter on the
    decrypted payload alone — trusting the payload to declare its own
    coordinates — so a record written under another percepción's key entered the
    window it was filed into rather than the one it describes, distorting the
    distinct registro-de-tipo-2 count the annual declaration files.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = PercepcionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        row_a = _observation(nif="11111111H", clave="A")
        row_b = _observation(nif="22222222J", clave="B")
        repo.replace_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=(row_a, row_b),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        # Positive control: the untouched window projects both rows.
        assert len(repo.load_observations("190", period)) == 2

        def _payload(observation: WithholdingObservation):
            return repo.build_observation_payload(
                modelo="190",
                filing_year=2024,
                period=period,
                observation=observation,
                source_kind=AggregationCaptureKind.AGGREGATE_PULL,
            )

        key_a = repo.extract_identifier(_payload(row_a))
        write_b = repo.to_secure_object_write(_payload(row_b))
        repo.secure_object_repository.save_with_raw_key(
            namespace=repo.namespace,
            hashed_object_key=secure_object_key_digest(key_a),
            classification=repo.sensitivity,
            schema_version=repo.schema_version,
            written_at=write_b.written_at,
            payload=write_b.payload,
        )

        with pytest.raises(SecureObjectRowIdentityError):
            repo.load_observations("190", period)


@pytest.mark.parametrize(
    "captured_at",
    [
        datetime(2024, 4, 15, 10, 30),
        datetime(2024, 4, 15, 10, 30, tzinfo=timezone(timedelta(hours=2))),
    ],
)
def test_envelope_refuses_a_capture_instant_without_utc(captured_at: datetime) -> None:
    """A naive or non-UTC capture instant never reaches the encrypted store.

    The sibling withholding envelopes carried a bare ``datetime`` while the
    calculation observation envelope was meant to hold the shared UTC contract,
    so each store admitted a capture instant with no zone and later comparisons
    against UTC-aware instants silently answered a different question. All three
    now use the one canonical UtcInstant.
    """
    from .._percepciones_observations_repository import _PercepcionObservationEnvelopePayload

    with pytest.raises(ValidationError):
        _PercepcionObservationEnvelopePayload(
            modelo="190",
            filing_year=2024,
            period=Period.from_year_and_code(2024, "0A"),
            observation=_observation(nif="11111111H", clave="A"),
            captured_at=captured_at,
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )


def test_envelope_accepts_a_utc_capture_instant() -> None:
    """The positive control for the refusal above."""
    from .._percepciones_observations_repository import _PercepcionObservationEnvelopePayload

    payload = _PercepcionObservationEnvelopePayload(
        modelo="190",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        observation=_observation(nif="11111111H", clave="A"),
        captured_at=datetime(2024, 4, 15, 10, 30, tzinfo=UTC),
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )

    assert payload.captured_at.utcoffset() == timedelta(0)
