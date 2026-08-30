"""Strict roundtrip across the RetencionObservationRepository boundary.

Persists per-perceptor :class:`RetencionObservation` records at
``SensitivityClass.FINANCIAL`` keyed by ``(modelo, filing_year, period,
sha256(perceptor_nif), scheme)`` — the DEDICATED store the calc-mesh
perceptor-count resolver reads so Modelo 180/193 count perceptors distinctly.

Anti-tautology: a populated observation carries every field non-default and two
distinct perceptors plus a same-NIF/two-scheme pair; a save-drops-field or
key-collision regression surfaces as inequality or a lost row on reload. The
plaintext NIF must never appear in the object key (only its sha256).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import PathContainmentError, SecureObjectRowIdentityError
from ....adapters.persistence.storage.crypto.encrypted_columns import secure_object_key_digest
from ....core import Period
from ....core.aggregation import AggregationCaptureKind, BindingSourceKind
from ....core.external_constants import UTF_8_ENCODING
from ....tests.secure_sql import isolated_runtime_profile
from .._retencion_observations_repository import (
    RetencionObservationRepository,
    _RetencionObservationEnvelopePayload,
    persist_retencion_observations,
    retencion_observation_key,
)
from .._retenciones import RetencionObservation, RetencionScheme, aggregate_retenciones_111

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _observation(*, nif: str, scheme: RetencionScheme, retencion: Decimal) -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=f"tx-{nif}-{scheme.value}",
        perceptor_nif=nif,
        perceptor_name="Arrendador Ejemplo SL",
        scheme=scheme,
        taxable_base=retencion * Decimal("5"),
        retencion_amount=retencion,
        accrued_on="2024-03-15",
    )


def test_retencion_observation_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """A populated RetencionObservation roundtrips byte-for-byte through the encrypted repo."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("142.48"))
        captured_at = datetime.now(UTC).replace(microsecond=0)
        repo = RetencionObservationRepository()
        repo.save_observation(
            modelo="180",
            filing_year=2024,
            period=Period.from_year_and_code(2024, "0A"),
            observation=original,
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
            captured_at=captured_at,
            source_metadata={"origin": "pull"},
        )
        loaded = repo.load_observations("180", Period.from_year_and_code(2024, "0A"))

        assert loaded == (original,)


def test_distinct_nifs_and_schemes_persist_as_distinct_rows(tmp_path: Path) -> None:
    """Two NIFs, and one NIF across two schemes, persist as distinct rows (key carries NIF+scheme)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = RetencionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        records = (
            _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("100")),
            _observation(nif="22222222J", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("200")),
            # Same NIF as the first, different scheme — a distinct row, not an overwrite.
            _observation(nif="11111111H", scheme=RetencionScheme.WORK_INCOME, retencion=Decimal("300")),
        )
        for record in records:
            repo.save_observation(
                modelo="180",
                filing_year=2024,
                period=period,
                observation=record,
                source_kind=AggregationCaptureKind.AGGREGATE_PULL,
            )
        loaded = repo.load_observations("180", period)
        # All three rows survive (no key collision); the two 11111111H rows are
        # distinct because the scheme is part of the key.
        assert len(loaded) == 3
        assert {(o.perceptor_nif, o.scheme) for o in loaded} == {
            ("11111111H", RetencionScheme.ECONOMIC_ACTIVITY),
            ("22222222J", RetencionScheme.ECONOMIC_ACTIVITY),
            ("11111111H", RetencionScheme.WORK_INCOME),
        }
        # Distinct-NIF count for the distinct-perceptor primitive is 2, not 3.
        assert len({o.perceptor_nif for o in loaded}) == 2


def test_object_key_hashes_the_nif_never_cleartext() -> None:
    """The object key carries the sha256 of the NIF, never the plaintext value."""
    key = retencion_observation_key(
        "180",
        2024,
        Period.from_year_and_code(2024, "0A"),
        "11111111H",
        RetencionScheme.ECONOMIC_ACTIVITY,
    )
    assert "11111111H" not in key
    digest = hashlib.sha256("11111111H".encode(UTF_8_ENCODING)).hexdigest()
    assert digest in key
    assert key == f"180:2024:0A:{digest}:{RetencionScheme.ECONOMIC_ACTIVITY.value}"


def test_period_scoping_excludes_other_windows(tmp_path: Path) -> None:
    """load_observations returns only the requested (modelo, year, period)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = RetencionObservationRepository()
        obs = _observation(nif="33333333P", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("50"))
        repo.save_observation(
            modelo="180",
            filing_year=2023,
            period=Period.from_year_and_code(2023, "0A"),
            observation=obs,
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        # A different year window must not see the 2023 row.
        assert repo.load_observations("180", Period.from_year_and_code(2024, "0A")) == ()
        assert repo.load_observations("180", Period.from_year_and_code(2023, "0A")) == (obs,)


def test_anti_tautology_strict_payload_rejects_dropped_field() -> None:
    """The envelope payload is strict: a dropped required field raises, never silently defaults.

    If this proof ever passes with a partial payload, every roundtrip above would
    be tautological (a save-drops-field regression could not surface).
    """
    from .._retencion_observations_repository import _RetencionObservationEnvelopePayload

    full = {
        "modelo": "180",
        "filing_year": 2024,
        "period": Period.from_year_and_code(2024, "0A"),
        "observation": _observation(
            nif="44444444A",
            scheme=RetencionScheme.ECONOMIC_ACTIVITY,
            retencion=Decimal("10"),
        ),
        "captured_at": datetime.now(UTC),
        "source_kind": AggregationCaptureKind.AGGREGATE_PULL,
    }
    # Sanity: the full payload validates.
    _RetencionObservationEnvelopePayload.model_validate(full)
    # Dropping the load-bearing observation must raise, not default to empty.
    partial = {k: v for k, v in full.items() if k != "observation"}
    with pytest.raises(ValidationError):
        _RetencionObservationEnvelopePayload.model_validate(partial)


def test_replace_observations_drops_removed_perceptor_no_stale_row(tmp_path: Path) -> None:
    """Re-persisting a SHRUNK set removes the dropped perceptor — no stale over-count.

    Set-replace, not additive upsert: a re-pull where the operator dropped a
    perceptor must NOT leave the stale row behind, or the next calculate's distinct
    count is inflated by a perceptor no longer declared (a silent over-count).
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = RetencionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        full = (
            _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("100")),
            _observation(nif="22222222J", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("200")),
            _observation(nif="33333333P", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("300")),
        )
        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=period,
            observations=full,
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        assert len({o.perceptor_nif for o in repo.load_observations("180", period)}) == 3
        # Re-pull dropped 33333333P.
        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=period,
            observations=full[:2],
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        loaded = repo.load_observations("180", period)
        assert len(loaded) == 2
        assert {o.perceptor_nif for o in loaded} == {"11111111H", "22222222J"}


def test_persist_helper_writes_set_readable_by_load(tmp_path: Path) -> None:
    """The shared write helper persists the set the resolver later reads (one source for both surfaces)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        period = Period.from_year_and_code(2024, "0A")
        observations = (
            _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("100")),
            _observation(nif="22222222J", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("200")),
        )
        persist_retencion_observations(modelo="180", filing_year=2024, period=period, observations=observations)
        loaded = RetencionObservationRepository().load_observations("180", period)
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
        repo = RetencionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        declared = (
            _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("100")),
            _observation(nif="22222222J", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("200")),
            _observation(nif="33333333P", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("300")),
        )
        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=period,
            observations=declared,
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )

        replacement = repo.build_observation_payload(
            modelo="180",
            filing_year=2024,
            period=period,
            observation=_observation(
                nif="44444444A",
                scheme=RetencionScheme.ECONOMIC_ACTIVITY,
                retencion=Decimal("400"),
            ),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        stale_identifiers = tuple(repo.extract_identifier(row) for row in repo.iter_records())
        with pytest.raises(PathContainmentError):
            repo.replace_records((replacement,), (*stale_identifiers, "180:2024:0A:../escape:x"))

        survived = repo.load_observations("180", period)
        assert set(survived) == set(declared)


def test_replacement_carries_over_a_row_present_in_both_sets(tmp_path: Path) -> None:
    """A key in both the old and the new set is updated, never deleted.

    Writes and deletions commit in one transaction with writes applied first, so
    a row whose key is carried across the replacement must be excluded from the
    stale set — otherwise it is upserted and then removed in the same unit of
    work and the operator loses a perceptor they still declare.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = RetencionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=period,
            observations=(
                _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("100")),
                _observation(nif="22222222J", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("200")),
            ),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        carried = _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("175"))
        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=period,
            observations=(carried,),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )

        assert repo.load_observations("180", period) == (carried,)


def test_replacement_leaves_other_windows_untouched(tmp_path: Path) -> None:
    """Only the addressed (modelo, filing_year, period) window is replaced."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = RetencionObservationRepository()
        target = Period.from_year_and_code(2024, "0A")
        neighbour = Period.from_year_and_code(2023, "0A")
        neighbour_row = _observation(
            nif="99999999R",
            scheme=RetencionScheme.ECONOMIC_ACTIVITY,
            retencion=Decimal("900"),
        )
        repo.replace_observations(
            modelo="180",
            filing_year=2023,
            period=neighbour,
            observations=(neighbour_row,),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=target,
            observations=(
                _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("100")),
            ),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )

        assert repo.load_observations("180", neighbour) == (neighbour_row,)


def test_whitespace_variant_nifs_are_one_perceptor_in_store_and_aggregation(tmp_path: Path) -> None:
    """Canonically-equal NIF declarations resolve to ONE perceptor everywhere.

    The observation model held the NIF exactly as declared while the repository
    trimmed and uppercased it before hashing it into the object key. Two
    declarations of the same perceptor differing only in surrounding whitespace
    or letter case therefore produced two rollups and a distinct-perceptor count
    of two, while sharing a single stored row whose later write overwrote the
    earlier evidence — the calculated declaration and the persisted evidence
    disagreeing about how many perceptors exist.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = RetencionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        padded = _observation(
            nif=" 12345678z ",
            scheme=RetencionScheme.ECONOMIC_ACTIVITY,
            retencion=Decimal("10"),
        )
        canonical = _observation(
            nif="12345678Z",
            scheme=RetencionScheme.ECONOMIC_ACTIVITY,
            retencion=Decimal("20"),
        )

        # The model itself canonicalises, so the aggregation identity matches.
        assert padded.perceptor_nif == canonical.perceptor_nif == "12345678Z"

        aggregation = aggregate_retenciones_111((padded, canonical), period=period)
        assert aggregation.total_perceptors == 1
        assert len(aggregation.rollups) == 1

        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=period,
            observations=(padded, canonical),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        stored = repo.load_observations("180", period)
        assert len({o.perceptor_nif for o in stored}) == 1
        assert len(stored) == 1


def test_padded_nif_keys_to_the_canonical_object_key() -> None:
    """A padded declaration and its canonical form address the same stored row."""
    period = Period.from_year_and_code(2024, "0A")
    padded_key = retencion_observation_key("180", 2024, period, " 12345678z ", RetencionScheme.ECONOMIC_ACTIVITY)
    canonical_key = retencion_observation_key("180", 2024, period, "12345678Z", RetencionScheme.ECONOMIC_ACTIVITY)
    assert padded_key == canonical_key


def test_window_scan_refuses_a_row_filed_under_another_perceptors_key(tmp_path: Path) -> None:
    """A payload stored under a different row's key is refused, not projected.

    The object key is derived from the payload's own natural identity, so the
    two are two encodings of one fact. The window scan used to filter on the
    decrypted payload alone — trusting the payload to declare its own
    coordinates — so a record written under another perceptor's key entered the
    window it was filed into rather than the one it describes, distorting the
    distinct-perceptor count the annual declaration files.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = RetencionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        row_a = _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("100"))
        row_b = _observation(nif="22222222J", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("200"))
        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=period,
            observations=(row_a, row_b),
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        # Positive control: the untouched window projects both rows.
        assert len(repo.load_observations("180", period)) == 2

        # Rewrite B's envelope under A's row key, the substitution the scan must catch.
        key_a = repo.extract_identifier(
            repo.build_observation_payload(
                modelo="180",
                filing_year=2024,
                period=period,
                observation=row_a,
                source_kind=AggregationCaptureKind.AGGREGATE_PULL,
            ),
        )
        write_b = repo.to_secure_object_write(
            repo.build_observation_payload(
                modelo="180",
                filing_year=2024,
                period=period,
                observation=row_b,
                source_kind=AggregationCaptureKind.AGGREGATE_PULL,
            ),
        )
        repo.secure_object_repository.save_with_raw_key(
            namespace=repo.namespace,
            hashed_object_key=secure_object_key_digest(key_a),
            classification=repo.sensitivity,
            schema_version=repo.schema_version,
            written_at=write_b.written_at,
            payload=write_b.payload,
        )

        with pytest.raises(SecureObjectRowIdentityError):
            repo.load_observations("180", period)


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
    from .._retencion_observations_repository import _RetencionObservationEnvelopePayload

    with pytest.raises(ValidationError):
        _RetencionObservationEnvelopePayload(
            modelo="180",
            filing_year=2024,
            period=Period.from_year_and_code(2024, "0A"),
            observation=_observation(
                nif="11111111H",
                scheme=RetencionScheme.ECONOMIC_ACTIVITY,
                retencion=Decimal("100"),
            ),
            captured_at=captured_at,
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )


def test_envelope_accepts_a_utc_capture_instant() -> None:
    """The positive control for the refusal above."""
    from .._retencion_observations_repository import _RetencionObservationEnvelopePayload

    payload = _RetencionObservationEnvelopePayload(
        modelo="180",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        observation=_observation(
            nif="11111111H",
            scheme=RetencionScheme.ECONOMIC_ACTIVITY,
            retencion=Decimal("100"),
        ),
        captured_at=datetime(2024, 4, 15, 10, 30, tzinfo=UTC),
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )

    assert payload.captured_at.utcoffset() == timedelta(0)


def _capture_payload(period: Period) -> _RetencionObservationEnvelopePayload:
    """One fully-populated envelope: every defaultable field carries a non-default."""
    return RetencionObservationRepository().build_observation_payload(
        modelo="180",
        filing_year=2024,
        period=period,
        observation=_observation(
            nif="11111111H",
            scheme=RetencionScheme.ECONOMIC_ACTIVITY,
            retencion=Decimal("100"),
        ),
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        captured_at=datetime(2024, 4, 15, 10, 30, tzinfo=UTC),
        source_metadata={"ingestion_run": "run-7", "operator": "aggregate-cli"},
    )


def test_capture_kind_survives_the_encrypted_boundary_as_the_enum(tmp_path: Path) -> None:
    """Strict roundtrip through the real cycle: the typed axis comes back typed.

    ``source_metadata`` is populated rather than left to its default factory,
    because a save-drops-field / load-re-defaults regression is invisible when
    the fixture uses the default.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = RetencionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        built = _capture_payload(period)

        repo.save(built)
        reloaded = repo.load(repo.extract_identifier(built))

        assert reloaded == built
        assert reloaded is not None
        assert reloaded.source_kind is AggregationCaptureKind.AGGREGATE_PULL
        assert dict(reloaded.source_metadata) == {"ingestion_run": "run-7", "operator": "aggregate-cli"}


def test_a_stored_envelope_missing_the_capture_kind_refuses_to_load(tmp_path: Path) -> None:
    """Anti-tautology: delete the field on disk and prove the read refuses.

    Without this the roundtrip above could pass against a boundary that silently
    re-defaults a dropped field, and every strict-equality assertion in this
    module would be measuring the fixture rather than the persistence.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = RetencionObservationRepository()
        period = Period.from_year_and_code(2024, "0A")
        built = _capture_payload(period)
        write = repo.to_secure_object_write(built)

        corrupted = json.loads(write.payload.decode(UTF_8_ENCODING))
        assert corrupted["payload"].pop("source_kind", None) is not None, (
            "the persisted payload does not carry source_kind, so deleting it proves nothing"
        )
        repo.secure_object_repository.save_with_raw_key(
            namespace=repo.namespace,
            hashed_object_key=secure_object_key_digest(repo.extract_identifier(built)),
            classification=repo.sensitivity,
            schema_version=repo.schema_version,
            written_at=write.written_at,
            payload=json.dumps(corrupted).encode(UTF_8_ENCODING),
        )

        with pytest.raises(ValidationError):
            repo.load(repo.extract_identifier(built))


def test_an_evidence_authority_value_cannot_enter_this_store() -> None:
    """The point of typing the axis: the exemption is now enforced, not observed.

    Both aggregation stores are exempt from the official-evidence displacement
    guard BECAUSE no evidence-authority provenance can reach them. While
    ``source_kind`` was a free-form ``str`` that was true of the content and of
    nothing else, so the exemption would have expired silently the day something
    wrote an AEAT kind here. This is the refusal that makes it structural.
    """
    with pytest.raises(ValidationError):
        _RetencionObservationEnvelopePayload.model_validate(
            {
                "modelo": "180",
                "filing_year": 2024,
                "period": Period.from_year_and_code(2024, "0A"),
                "observation": _observation(
                    nif="11111111H",
                    scheme=RetencionScheme.ECONOMIC_ACTIVITY,
                    retencion=Decimal("100"),
                ),
                "captured_at": datetime.now(UTC),
                "source_kind": "aeat_sede_justificante",
            },
        )
