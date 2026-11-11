"""Filed AEAT observations feed the calculation history repository."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from cadrumo.adapters.inbound.justificante.parser import parse_justificante_bytes
from cadrumo.adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from cadrumo.adapters.outbound.aeat.sede.schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaValue,
)
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.filed_capture_history_support import (
    CAPTURED_AT,
    M303_POSTERIOR_CASILLA,
    MODELO_130_FIXTURE_CSV,
    MODELO_303_FIXTURE_CSV,
    SYNTHETIC_PROFILE_ID,
    modelo_130_justificante_pdf_bytes,
    modelo_303_justificante_pdf_bytes,
    prior_303_observation,
    profile_backend,
    registry_snapshot,
    secure_backend,
    seed_current_130_filing,
    seed_current_303_filing,
    stored_130_justificante_observation,
    stored_303_justificante_observation,
    stored_justificante_observation,
)
from cadrumo.application.calculations.m303_carry_ingress import M303CarryIngressError
from cadrumo.application.calculations.observations_repository import ObservationSourceKind
from cadrumo.application.live.filed_capture_finalizer import FiledCaptureFailurePolicy, finalize_filed_capture
from cadrumo.application.live.filed_observation_persistence import (
    FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
    FiledJustificanteUnreachedReason,
    enroll_filed_justificante_evidence,
    persist_filed_calculation_observation,
    select_latest_filed_observations_in_history_order,
)
from cadrumo.application.modelo.filing_chain_reconciliation import FilingReconciliationOutcome
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.casilla_value_kind import CasillaValueKind
from cadrumo.core.config import Settings
from cadrumo.core.json_contract import NoticeSeverity
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.published_authority import published_supported_filing_years
from cadrumo.domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
    revision_id_for_observation,
)

from .filed_capture_history_ports_support import SESSION_BUCKET_ID, filed_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_history_selection_is_invariant_to_the_order_duplicated_periods_arrive_in() -> None:
    """A period with two active filings collapses to one, and input order cannot change which.

    The register can return an original and a later-presented amendment for the
    same period, both registered ALTA. Selection must keep exactly one per
    period and keep the later one -- and it must reach that answer by ranking,
    not by whichever row happened to be seen last. Feeding the identical set in
    reverse is what separates those two implementations: a last-write-wins
    reduction agrees with a max-by-rank one on a conveniently ordered input and
    disagrees the moment the order flips.

    Ordinary single-filing periods sit in the same batch so a selector that
    collapsed everything to one row per modelo-year would not pass.
    """
    original_3t = prior_303_observation(
        year=2024,
        period="3T",
        expediente_id="202430300000303C",
        pending_compensation=Decimal("300.00"),
        presented_at=datetime(2024, 10, 18, 12, 5, 11, tzinfo=UTC),
    )
    amendment_3t = prior_303_observation(
        year=2024,
        period="3T",
        expediente_id="202430300000505E",
        pending_compensation=Decimal("355.00"),
        presented_at=datetime(2025, 3, 14, 11, 20, 36, tzinfo=UTC),
    )
    original_4t = prior_303_observation(
        year=2024,
        period="4T",
        expediente_id="202430300000404D",
        pending_compensation=Decimal("400.00"),
        presented_at=datetime(2025, 1, 27, 16, 42, 58, tzinfo=UTC),
    )
    amendment_4t = prior_303_observation(
        year=2024,
        period="4T",
        expediente_id="202430300000606F",
        pending_compensation=Decimal("444.00"),
        presented_at=datetime(2025, 3, 14, 11, 58, 9, tzinfo=UTC),
    )
    single_1t = prior_303_observation(
        year=2024,
        period="1T",
        expediente_id="202430300000101A",
        pending_compensation=Decimal("100.00"),
        presented_at=datetime(2024, 4, 22, 10, 14, 3, tzinfo=UTC),
    )
    observations = (single_1t, original_3t, original_4t, amendment_3t, amendment_4t)

    selected = select_latest_filed_observations_in_history_order(observations)
    reversed_selection = select_latest_filed_observations_in_history_order(tuple(reversed(observations)))

    periods_selected = [observation.period for observation in selected]
    assert len(periods_selected) == len(set(periods_selected)), (
        "a period survived more than once, so duplicated filings were not collapsed"
    )
    assert set(periods_selected) == {observation.period for observation in observations}, (
        "collapsing dropped a period entirely instead of choosing one filing within it"
    )
    winners = {observation.period: observation.expediente_id for observation in selected}
    assert winners[amendment_3t.period] == amendment_3t.expediente_id
    assert winners[amendment_4t.period] == amendment_4t.expediente_id
    assert winners[single_1t.period] == single_1t.expediente_id
    assert reversed_selection == selected, (
        "selection depends on the order the register rows arrived in, so it is not ranking them"
    )


_SYNTHETIC_REQUEST_TYPE = "SYNTHETIC-REQUEST-TYPE"


def test_persisted_source_metadata_carries_the_register_request_type_signal(tmp_path: Path) -> None:
    """AEAT's own request-type signal now survives to persisted provenance.

    This test previously pinned the OPPOSITE: the capture path read the register
    row's request type into the raw observation and the source metadata was built
    from a fixed key set that dropped it, so the one signal distinguishing an
    original filing from an amendment was gone before anything downstream could
    read it. Its docstring said to reverse it when the carry-through landed, and
    this is that reversal -- the absence assertions are gone rather than relaxed.

    Carrying the signal is NOT electing on it. No selection logic reads this key,
    and which identifier an amendment-aware election should key on stays an open
    decision; what changed is that the evidence survives so that decision can be
    made against persisted data instead of requiring a re-capture.

    Modelo 130 keeps this off the IVA compensation machinery a Modelo 303
    observation additionally drives, so the persistence boundary is exercised on
    its own. The metadata mapping mirrors what the live capture path writes off
    the register row.
    """
    observation = _filed_130_observation().model_copy(
        update={"metadata": {"tipo_solicitud": _SYNTHETIC_REQUEST_TYPE, "observaciones": ""}},
    )
    assert observation.metadata["tipo_solicitud"] == _SYNTHETIC_REQUEST_TYPE, (
        "the raw observation does not carry the signal, so this test cannot show it being carried"
    )

    with secure_backend(tmp_path):
        persist_filed_calculation_observation(
            observation,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )
        loaded = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))

    assert loaded is not None
    assert loaded.source_metadata["aeat_tipo_solicitud"] == _SYNTHETIC_REQUEST_TYPE
    # The surrounding provenance is asserted too, so a change that carried the
    # request type while dropping a sibling key would not read as a pass.
    assert loaded.source_metadata["aeat_expediente_id"] == observation.expediente_id
    assert loaded.source_metadata["aeat_register_status"] == "ALTA"


def test_persisted_source_metadata_omits_an_absent_request_type_rather_than_writing_it_empty(
    tmp_path: Path,
) -> None:
    """A register row with no request type leaves the key ABSENT, never empty.

    An empty string would be indistinguishable from AEAT declaring an empty
    request type, so a later amendment-aware reader could not tell "the row did
    not say" from "the row said nothing". Absence is the honest encoding, and
    this pins it in both directions: the blank-string case and the
    key-entirely-missing case both omit it.
    """
    blank = _filed_130_observation().model_copy(update={"metadata": {"tipo_solicitud": "   "}})
    missing = _filed_130_observation().model_copy(update={"metadata": {"observaciones": ""}})

    with secure_backend(tmp_path / "blank"):
        persist_filed_calculation_observation(
            blank,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )
        blank_row = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))
    with secure_backend(tmp_path / "missing"):
        persist_filed_calculation_observation(
            missing,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )
        missing_row = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))

    assert blank_row is not None
    assert missing_row is not None
    assert "aeat_tipo_solicitud" not in blank_row.source_metadata
    assert "aeat_tipo_solicitud" not in missing_row.source_metadata
    # Anchor: the metadata was built at all, so the absences above mean something.
    assert "aeat_expediente_id" in blank_row.source_metadata
    assert "aeat_expediente_id" in missing_row.source_metadata


def test_the_request_type_signal_survives_a_strict_persistence_roundtrip(tmp_path: Path) -> None:
    """The carried key crosses the real encrypted boundary and reloads equal.

    Real key provider, real SQLite, real serializer: the field is written through
    the production persist path and read back through the production load path,
    then the whole reloaded provenance envelope is compared rather than just the
    one key, so a save that carried the request type while re-defaulting a
    neighbouring field fails here.
    """
    observation = _filed_130_observation().model_copy(
        update={"metadata": {"tipo_solicitud": _SYNTHETIC_REQUEST_TYPE, "observaciones": "OBS"}},
    )
    with secure_backend(tmp_path):
        persist_filed_calculation_observation(
            observation,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
            justificante_csvs=("CSV13020261T",),
        )
        first = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))
        second = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))

    assert first is not None
    assert second is not None
    assert first == second
    assert first.source_metadata == {
        "aeat_register_status": "ALTA",
        "aeat_expediente_id": observation.expediente_id,
        "authenticated_identity": SYNTHETIC_PROFILE_ID,
        "aeat_tipo_solicitud": _SYNTHETIC_REQUEST_TYPE,
        "aeat_justificante_csv": "CSV13020261T",
    }


def test_a_receipt_reaches_its_filing_even_though_its_identifier_is_not_the_register_expediente_id(
    tmp_path: Path,
) -> None:
    """A receipt that belongs to the filing is enrolled and reconciled; its own identifier is not consulted.

    This test previously pinned the OPPOSITE. A justificante carries AEAT's
    Número de justificante and the register row carries an expediente id; those
    are different AEAT identifier namespaces for the same filing, and the
    production comparison fed the expediente id into the receipt's
    presentation-identifier check. Since no receipt body ever carries the
    register's expediente id, that comparison could never agree, so a receipt
    agreeing on modelo, ejercicio, period and taxpayer identity was still
    rejected and nothing was stamped. Its docstring said to reverse it once the
    comparison was settled, and this is that reversal -- the rejection
    assertions are gone rather than relaxed.

    What replaced the broken axis is a csv comparison the caller performs
    itself, against a csv recovered from the URL the bytes were fetched under.
    That axis is exercised in both directions by
    ``test_a_receipt_is_refused_when_its_csv_is_not_the_csv_its_bytes_were_fetched_under``
    and the two-filings discrimination test below, so this test's job is
    narrower: the divergent identifiers no longer keep a legitimate receipt from
    reaching the filing's reconciliation, which records the register expediente.
    """
    # DO NOT "tidy" these two into agreement. Their divergence is still the
    # premise: it is what makes the stamp below evidence that the identifier is
    # no longer consulted, rather than evidence that two equal values agreed.
    register_expediente_id = "202613000000101A"
    receipt = parse_justificante_bytes(modelo_130_justificante_pdf_bytes())
    assert receipt.presentation_id is not None
    assert receipt.presentation_id.strip().casefold() != register_expediente_id.strip().casefold(), (
        "the receipt's presentation identifier and the register expediente id no longer diverge, "
        "so this fixture pair cannot exercise the divergence"
    )

    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_130_justificante_observation(store, expediente_id=register_expediente_id)
        filing = seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )
        current = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )

    assert result.justificante_csvs == (receipt.csv,)
    assert [(item.filing_record_id, item.outcome) for item in result.reconciliation_results] == [
        (filing.filing_record_id, FilingReconciliationOutcome.UNVERIFIABLE),
    ]
    assert result.conflicting_filing_record_ids == ()
    assert current is not None
    assert current.aeat_accepted is False


def test_a_receipt_is_refused_when_its_csv_is_not_the_csv_its_bytes_were_fetched_under(
    tmp_path: Path,
) -> None:
    """The csv check is what refuses a mis-paired artefact, now that the identifier axis is gone.

    The stored artefact records the cotejo document URL its bytes were fetched
    under, and that csv came from AEAT's own cotejo redirect rather than from
    the PDF. Here the URL names one filing's csv while the stored bytes are the
    receipt of another, which is the shape a storage or selection defect
    re-associating an artefact after capture would produce.

    Everything else agrees, so this refusal is attributable to the csv axis
    alone: same modelo, ejercicio, period and taxpayer identity, and a filing
    record present and ready to be stamped.
    """
    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_130_justificante_observation(store, captured_csv="QQQQ7777WWWW3333")
        seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )
        current = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )

    assert result.justificante_csvs == ()
    assert result.filing_record_ids == ()
    assert result.conflicting_filing_record_ids == ()
    assert current is not None
    assert current.external_evidence is None
    assert current.aeat_accepted is False


def test_a_receipt_is_refused_when_no_csv_can_be_recovered_from_the_artefact_url(
    tmp_path: Path,
) -> None:
    """A source URL carrying no csv is reported as a non-match, never an exception.

    The recovery helper raises on a URL with no usable ``CSV`` query, and this
    function runs inside an enrollment loop over every artefact. Letting that
    propagate would abort the whole enrollment over one malformed URL, so it
    joins the other swallowed outcomes instead.
    """
    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_130_justificante_observation(store)
        artefact = observation.artefacts[0]
        observation = observation.model_copy(
            update={
                "artefacts": (
                    artefact.model_copy(
                        update={"source_url": AnyHttpUrl(str(artefact.source_url).split("?", 1)[0])},
                    ),
                ),
            },
        )
        seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )

    assert result.justificante_csvs == ()
    assert result.filing_record_ids == ()


def test_the_csv_check_tells_two_same_period_filings_apart_where_the_other_axes_cannot(
    tmp_path: Path,
) -> None:
    """Two Modelo 303 filings for one period are discriminated by csv alone.

    A period can carry more than one filing -- an original and a substitutive,
    say -- and they share modelo, ejercicio, period and taxpayer identity. Those
    are every axis the match predicate consults, so the predicate cannot tell
    the two apart; the first block below asserts exactly that, which is what
    makes the csv axis load-bearing rather than redundant.

    So the same receipt bytes are enrolled twice against two register rows that
    differ only in expediente id. The row whose artefact URL names the csv
    printed on those bytes reaches its filing's reconciliation. The row whose URL
    names the other filing's csv is refused before any reconciliation.
    """
    receipt = parse_justificante_bytes(modelo_303_justificante_pdf_bytes())
    other_filing_csv = "QQQQ7777WWWW3333"
    assert receipt.csv.strip().upper() != other_filing_csv, (
        "the two filings' csvs no longer diverge, so nothing here can be discriminated"
    )

    # The four surviving axes are identical for both filings, so the predicate
    # returns True for each. Only the csv separates them.
    for expediente_id in ("202630300000411A", "202630300000412B"):
        assert receipt.matches_filing_target(
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            tax_id="00000000T",
        ), f"the predicate must accept the receipt for {expediente_id}, or the two are already separable"

    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        filing = seed_current_303_filing(bucket_id=bucket_id)

        wrong_filing = stored_303_justificante_observation(
            store,
            expediente_id="202630300000412B",
            captured_csv=other_filing_csv,
        )
        refused = enroll_filed_justificante_evidence(
            wrong_filing, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )
        after_refusal = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )

        right_filing = stored_303_justificante_observation(store)
        accepted = enroll_filed_justificante_evidence(
            right_filing, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )
        after_acceptance = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )

    assert refused.justificante_csvs == ()
    assert refused.reconciliation_results == ()
    assert after_refusal is not None
    assert after_refusal.external_evidence is None
    assert after_refusal.aeat_accepted is False

    assert accepted.justificante_csvs == (receipt.csv,)
    assert [item.filing_record_id for item in accepted.reconciliation_results] == [filing.filing_record_id]
    assert after_acceptance is not None
    assert after_acceptance.aeat_accepted is False


def _artefact_replaced(
    observation: FiledDeclaracionObservation,
    **updates: object,
) -> FiledDeclaracionObservation:
    artefact = observation.artefacts[0]
    return observation.model_copy(update={"artefacts": (artefact.model_copy(update=updates),)})


def _manifest_mismatch_observation(store: FiledDeclaracionObservationStore) -> FiledDeclaracionObservation:
    observation = stored_130_justificante_observation(store)
    return _artefact_replaced(observation, byte_count=observation.artefacts[0].byte_count + 1)


def _unparsable_pdf_observation(store: FiledDeclaracionObservationStore) -> FiledDeclaracionObservation:
    return stored_justificante_observation(
        store,
        modelo="130",
        pdf_bytes=b"%PDF-1.4 not a receipt",
        authenticated_identity="00000000T",
        expediente_id="202613000000199Z",
        captured_csv=MODELO_130_FIXTURE_CSV,
    )


def _csv_unresolvable_observation(store: FiledDeclaracionObservationStore) -> FiledDeclaracionObservation:
    observation = stored_130_justificante_observation(store)
    stripped = str(observation.artefacts[0].source_url).split("?", 1)[0]
    return _artefact_replaced(observation, source_url=AnyHttpUrl(stripped))


def _csv_mismatch_observation(store: FiledDeclaracionObservationStore) -> FiledDeclaracionObservation:
    return stored_130_justificante_observation(store, captured_csv="QQQQ7777WWWW3333")


def _filing_target_mismatch_observation(store: FiledDeclaracionObservationStore) -> FiledDeclaracionObservation:
    # The csv agrees, so this reaches the filing-target axis rather than stopping
    # at the csv one: a Modelo 130 receipt filed under a Modelo 303 register row.
    return stored_justificante_observation(
        store,
        modelo="303",
        pdf_bytes=modelo_130_justificante_pdf_bytes(),
        authenticated_identity="00000000T",
        expediente_id="202630300000199Z",
        captured_csv=MODELO_130_FIXTURE_CSV,
    )


_UNREACHED_JUSTIFICANTE_CASES = (
    ("manifest-mismatch", _manifest_mismatch_observation),
    ("unparsable-pdf", _unparsable_pdf_observation),
    ("csv-unresolvable", _csv_unresolvable_observation),
    ("csv-mismatch", _csv_mismatch_observation),
    ("filing-target-mismatch", _filing_target_mismatch_observation),
)


def test_each_unreached_justificante_outcome_reports_its_own_reason(tmp_path: Path) -> None:
    """Five dead ends that used to share one shape now name themselves.

    A capture that extracted casillas while enrolling nothing reported an
    unexplained zero, indistinguishable from a period with no receipt. Each case
    below reaches the same "no evidence" outcome by a different route, and the
    assertion is that the reasons are DISTINCT -- a branch that collapsed any two
    of them back together would still produce five notices and still pass a
    count-only check, so the set of reasons is what is compared.
    """
    reasons: dict[str, str] = {}
    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        for case_id, mutate in _UNREACHED_JUSTIFICANTE_CASES:
            store = FiledDeclaracionObservationStore(tmp_path / f"unreached-{case_id}")
            observation = mutate(store)
            seed_current_130_filing(bucket_id=bucket_id)

            result = enroll_filed_justificante_evidence(
                observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
            )

            assert result.justificante_csvs == (), case_id
            assert len(result.notices) == 1, case_id
            notice = result.notices[0]
            assert notice.severity is NoticeSeverity.WARNING, case_id
            assert notice.code == FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE, case_id
            assert notice.context is not None
            assert notice.context["expediente_id"] == observation.expediente_id, case_id
            reasons[case_id] = notice.context["reason"]

    # Derived from the enum, never a hand-listed copy of it: a member added
    # without a case here fails this assertion instead of going unwatched. Only
    # UNREADABLE_ARTEFACT is excluded, because reaching it means secure storage
    # failed to return bytes it holds, which this harness cannot stage without a
    # test double standing in for the real store.
    expected = {
        reason.value
        for reason in FiledJustificanteUnreachedReason
        if reason is not FiledJustificanteUnreachedReason.UNREADABLE_ARTEFACT
    }
    assert set(reasons.values()) == expected, reasons
    assert len(set(reasons.values())) == len(reasons), (
        f"two cases reported the same reason, so the outcomes are not distinguished: {reasons}"
    )


def test_an_enrollment_that_saves_evidence_raises_no_unreached_notice(tmp_path: Path) -> None:
    """The notice channel stays empty on the success path.

    Without this, a change emitting the notice unconditionally would still pass
    every case above while telling an operator that a successful enrollment
    reached no evidence.
    """
    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_130_justificante_observation(store)
        seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )

    assert result.justificante_csvs == (MODELO_130_FIXTURE_CSV,)
    assert result.notices == ()


def test_fixture_csv_constants_still_match_the_receipts() -> None:
    """The csvs the support helpers state independently are the csvs AEAT printed.

    The helpers deliberately do not read these out of the PDFs, because a URL
    built from the receipt's own csv would make every csv comparison in this
    module compare one value against itself. That independence costs a way to
    drift, and this is the anchor that catches the drift: replace a fixture and
    the constants stop describing it.
    """
    assert parse_justificante_bytes(modelo_130_justificante_pdf_bytes()).csv == MODELO_130_FIXTURE_CSV
    assert parse_justificante_bytes(modelo_303_justificante_pdf_bytes()).csv == MODELO_303_FIXTURE_CSV


def test_an_incomplete_prior_filing_observation_never_reaches_the_store(tmp_path: Path) -> None:
    """Official Modelo 303 evidence without its carry pair is refused at the write door.

    The prefill would otherwise have to refuse it later; the canonical ingress
    refuses it before storage, so no reader can ever see the incomplete filing.
    """
    support = published_supported_filing_years()
    assert support is not None
    year = support.horizon
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=year,
        period="1T",
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=year,
            period="1T",
            casilla_values={M303_POSTERIOR_CASILLA: Decimal("1200.00")},
        ),
    )
    with bundled_indexed_authority().operation(), secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        with pytest.raises(M303CarryIngressError):
            repository.prepare_observation_envelope(
                observation,
                source_kind="aeat_sede_justificante",
                captured_at=CAPTURED_AT,
                stamped_revision_id=revision_id_for_observation(observation),
            )
        assert tuple(repository.iter_records()) == ()


def _filed_130_observation(
    *,
    expediente_id: str = "13020260410ABCD1234EFGH5678",
    presented_at: datetime = CAPTURED_AT,
) -> FiledDeclaracionObservation:
    """One Modelo 130 filed observation that enrols as registry-grounded evidence.

    Deliberately NOT Modelo 303. The provenance stamp is modelo-agnostic, while a
    303 observation additionally drives the IVA compensation wallet on the way to
    persistence -- a side effect with nothing to do with provenance, whose failure
    would be indistinguishable here from a provenance divergence. Modelo 130
    exercises the same single stamping site with nothing else attached.
    """
    period = Period.from_year_and_code(2026, "1T")
    body = b"130-2026-1T-submitted-file"
    external = Settings.external_constants().aeat
    declarations_url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl(declarations_url),
        content_type="application/octet-stream",
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=presented_at,
    )
    return FiledDeclaracionObservation(
        modelo="130",
        ejercicio=2026,
        period=period,
        expediente_id=expediente_id,
        status="ALTA",
        presented_at=presented_at,
        authenticated_identity=SYNTHETIC_PROFILE_ID,
        artefacts=(artefact,),
        casillas=(
            ObservedCasillaValue(
                casilla_id=validated_casilla_id("03"),
                value="1500.00",
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:03",
                confidence=1.0,
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
        registry_snapshot_ref=registry_snapshot("130", 2026, "1T").snapshot_ref,
    )


def test_discovery_driven_capture_stamps_the_same_official_source_kind(tmp_path: Path) -> None:
    """A discovery-nominated pair is provenance-identical to a single-pair capture.

    This is the point of the test, not a formality. The design deliberately adds
    NO sixth ``ObservationSourceKind`` for a backfilled historical filing, on the
    ground that an imported filing IS an AEAT-sourced filed declaración rather
    than a lesser-trust echo of one. That is only safe if the discovery signal
    genuinely cannot reach the stamp -- so the same synthetic declaración is
    pushed through the single-pair finalizer policy and through the bulk policy a
    discovery-driven sweep uses, into two real repositories on real encrypted
    backends, and the two persisted rows are compared whole.

    The comparison excludes nothing. ``captured_at`` is derived from the filing's
    own ``presented_at``, so it is genuinely equal on both paths and is asserted
    equal rather than waved through; the registry observation, the revision stamp,
    the source metadata and the member NIF are each asserted equal, and then the
    two rows are compared with ``==`` so a field added later is covered without
    this test being edited.
    """
    observation = _filed_130_observation()
    period = Period.from_year_and_code(2026, "1T")

    with secure_backend(tmp_path / "single"):
        single_finalization = finalize_filed_capture(
            (observation,),
            policy=FiledCaptureFailurePolicy.FAIL_FAST,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path / "single"),
        )
        single_row = CalculationObservationRepository().load_observation("130", period)

    # A discovery-driven sweep reaches capture through the bulk grid, whose
    # finalizer policy is BEST_EFFORT because partial success is the expected
    # outcome of a history walk. That policy is the ONLY thing the discovery route
    # changes about finalization, which is why it is the arm under test.
    with secure_backend(tmp_path / "discovered"):
        discovered_finalization = finalize_filed_capture(
            (observation,),
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path / "discovered"),
        )
        discovered_row = CalculationObservationRepository().load_observation("130", period)

    assert single_row is not None
    assert discovered_row is not None
    assert discovered_finalization.failures == ()
    assert single_finalization.calculation_observation_keys == discovered_finalization.calculation_observation_keys

    assert single_row.source_kind is ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
    assert discovered_row.source_kind is ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
    assert discovered_row.source_kind.is_official_aeat

    assert discovered_row.observation == single_row.observation
    assert discovered_row.stamped_revision_id == single_row.stamped_revision_id
    assert discovered_row.source_metadata == single_row.source_metadata
    assert discovered_row.member_nif == single_row.member_nif
    assert discovered_row.captured_at == single_row.captured_at == observation.presented_at
    assert discovered_row == single_row


def test_no_discovery_signal_token_reaches_the_observation_provenance(tmp_path: Path) -> None:
    """The persisted provenance names no discovery signal, so it cannot depend on one.

    The parity assertion above compares two runs and would pass if both were
    wrong in the same way. This closes that side: a signal token reaching
    ``source_metadata`` would make the stored provenance vary with WHICH signal
    nominated the pair, which is exactly the distinction the domain does not have.
    """
    from cadrumo.core.filed_history_discovery_signal import FiledHistoryDiscoverySignal

    with secure_backend(tmp_path):
        finalize_filed_capture(
            (_filed_130_observation(),),
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )
        row = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))

    assert row is not None
    assert row.source_metadata
    stored = " ".join((*row.source_metadata.keys(), *row.source_metadata.values())).casefold()
    for signal in FiledHistoryDiscoverySignal:
        assert signal.value not in stored


def test_the_official_source_kind_set_gains_no_discovery_specific_member() -> None:
    """No sixth kind was introduced, and the official set is still exactly three.

    Gated on membership of the official set rather than on a total count of the
    enum, so adding a genuinely unrelated NON-official kind does not force an edit
    here -- while adding a discovery-specific official kind, which this test
    settles against, fails.
    """
    official = {kind for kind in ObservationSourceKind if kind.is_official_aeat}
    assert official == {
        ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        ObservationSourceKind.AEAT_SEDE_LIVE_CAPTURE,
        ObservationSourceKind.AEAT_CSV_REGISTER,
    }
    assert not any("discover" in kind.value or "history" in kind.value for kind in ObservationSourceKind)
