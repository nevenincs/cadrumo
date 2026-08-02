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
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core import BindingSourceKind, Period
from ....core.external_constants import UTF_8_ENCODING
from ....tests.secure_sql import isolated_runtime_profile
from .._errors import AggregationValidationError
from .._retencion_observations_repository import (
    RetencionObservationRepository,
    persist_retencion_observations,
    retencion_observation_key,
)
from .._retenciones import RetencionObservation, RetencionScheme

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
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
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
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
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
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
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
        "source_kind": "ledger_transaction",
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
            source_kind="aggregate_pull",
        )
        assert len({o.perceptor_nif for o in repo.load_observations("180", period)}) == 3
        # Re-pull dropped 33333333P.
        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=period,
            observations=full[:2],
            source_kind="aggregate_pull",
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
    """A replacement that cannot be persisted leaves the declared window untouched.

    The set-replace used to commit each stale-row delete before looping through
    the saves one at a time, so a refusal part-way through destroyed the prior
    declared set and left only the rows written before the failure. The next
    calculate then read that partial window as the operator's declared truth —
    a silent under-count whose own evidence had already been deleted.

    The refusal here is production-reachable: a perceptor NIF that is
    whitespace-only satisfies the observation model's length bound but has no
    canonical hashed token, so keying the row raises before it can be stored.
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
            source_kind="aggregate_pull",
        )

        unstorable = (
            _observation(nif="44444444A", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("400")),
            _observation(nif=" ", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("500")),
        )
        with pytest.raises(AggregationValidationError):
            repo.replace_observations(
                modelo="180",
                filing_year=2024,
                period=period,
                observations=unstorable,
                source_kind="aggregate_pull",
            )

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
            source_kind="aggregate_pull",
        )
        carried = _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("175"))
        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=period,
            observations=(carried,),
            source_kind="aggregate_pull",
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
            source_kind="aggregate_pull",
        )
        repo.replace_observations(
            modelo="180",
            filing_year=2024,
            period=target,
            observations=(
                _observation(nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, retencion=Decimal("100")),
            ),
            source_kind="aggregate_pull",
        )

        assert repo.load_observations("180", neighbour) == (neighbour_row,)
