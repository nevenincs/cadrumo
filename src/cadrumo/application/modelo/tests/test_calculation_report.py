"""The calculation report builder and its CSV serialiser, over the real registry.

Every case here runs against the published authority through the shared fixture
revision in :mod:`._calculation_report_fixture`, so row identity, section order
and grounding are the registry's. What each test varies is one input to the
builder -- the language, the persisted provenance, the export instant -- so the
report's treatment of that input is observable on its own.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.calculation_report_format import CalculationReportDocumentFormat
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import override_locales_root
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.filing.software_identity import AeatSoftwareIdentityGrade
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.verification_report import VerificationCompletenessStatus
from ..calculation_report import (
    CALCULATION_REPORT_NOTICE_LOCALE_KEY,
    CalculationReportNoticeUnavailableError,
    CalculationReportRowRole,
    CalculationReportValueState,
    ModeloCalculationReport,
    ModeloCalculationReportRow,
    calculation_report_row_role,
    local_calculation_report_notice,
)
from ..calculation_report_document import (
    CALCULATION_REPORT_CSV_FIELDNAMES,
    CALCULATION_REPORT_CSV_PREAMBLE_PREFIX,
    CALCULATION_REPORT_DIGEST_PREAMBLE_KEY,
    calculation_report_csv_preamble_lines,
    serialize_calculation_report,
)
from ..calculation_report_provenance_key import OPAQUE_PROVENANCE_FAMILY
from ..settlement_casilla import DECLARATION_RESULT_SEMANTIC_ROLES, SETTLEMENT_SEMANTIC_ROLES
from ._calculation_report_fixture import (
    EXPORTED_AT,
    FILING_RECORD_ID,
    FILING_YEAR,
    GENERATION,
    MEASURED_CASILLA,
    MODELO,
    NOT_APPLICABLE_CASILLA,
    PERCEPTOR_NIF,
    PERCEPTOR_SOURCE_REF,
    SOURCE_FINGERPRINT,
    SOURCE_REF,
    TAXPAYER_NAME,
    TAXPAYER_TAX_ID,
    UNFAMILIED_SOURCE_REF,
    VERIFICATION_REPORT_ID,
    ZERO_CASILLA,
    build_fixture_report,
    fixture_report_digest,
    source_trace,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _row(report: ModeloCalculationReport, casilla_id: str) -> ModeloCalculationReportRow:
    return next(row for row in report.rows if row.casilla_id == casilla_id)


def _table_rows(payload: bytes) -> dict[str, dict[str, str]]:
    """Parse the published CSV table back, dropping the commented preamble."""
    table = "\n".join(
        line
        for line in payload.decode("utf-8").splitlines()
        if not line.startswith(CALCULATION_REPORT_CSV_PREAMBLE_PREFIX)
    )
    return {row["casilla_id"]: dict(row) for row in csv.DictReader(io.StringIO(table))}


def _csv(report: ModeloCalculationReport) -> bytes:
    return serialize_calculation_report(report, document_format=CalculationReportDocumentFormat.CSV).payload


def test_rows_follow_registry_section_order_and_casilla_numbering(operation: PinnedAuthorityOperation) -> None:
    """The report's row order is the snapshot's own casilla order, unchanged."""
    report, snapshot = build_fixture_report(operation)

    assert tuple(row.casilla_id for row in report.rows) == tuple(casilla.id for casilla in snapshot.revision.casillas)
    definitions = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    for row in report.rows:
        assert row.section_path == definitions[row.casilla_id].section
        assert row.number == definitions[row.casilla_id].number
        assert row.label == definitions[row.casilla_id].label
        assert row.legal_refs == tuple(definitions[row.casilla_id].legal_refs)
        assert row.source_refs == tuple(definitions[row.casilla_id].source_refs)


def test_value_zero_absent_and_not_applicable_are_four_distinct_readings(
    operation: PinnedAuthorityOperation,
) -> None:
    """A figure, a zero, an unrealised casilla and a non-applicable one each read differently."""
    report, _ = build_fixture_report(operation)

    measured = _row(report, MEASURED_CASILLA)
    assert measured.value_state is CalculationReportValueState.VALUE
    assert Decimal(str(measured.value)) == Decimal("10000.00")

    zero = _row(report, ZERO_CASILLA)
    assert zero.value_state is CalculationReportValueState.VALUE
    assert Decimal(str(zero.value)) == Decimal("0.00")

    not_applicable = _row(report, NOT_APPLICABLE_CASILLA)
    assert not_applicable.value_state is CalculationReportValueState.NOT_APPLICABLE
    assert not_applicable.value is None

    absent = [row for row in report.rows if row.value_state is CalculationReportValueState.ABSENT]
    assert absent
    assert all(row.value is None for row in absent)


def test_the_csv_spells_a_zero_an_absence_and_a_non_applicability_differently(
    operation: PinnedAuthorityOperation,
) -> None:
    """The three readings survive serialisation as three different cells."""
    report, _ = build_fixture_report(operation)
    rows = _table_rows(_csv(report))

    assert rows[ZERO_CASILLA]["value"] == "0.00"
    assert rows[ZERO_CASILLA]["value_state"] == CalculationReportValueState.VALUE.value
    assert rows[NOT_APPLICABLE_CASILLA]["value"] == ""
    assert rows[NOT_APPLICABLE_CASILLA]["value_state"] == CalculationReportValueState.NOT_APPLICABLE.value

    absent_casilla = next(
        row.casilla_id for row in report.rows if row.value_state is CalculationReportValueState.ABSENT
    )
    assert rows[absent_casilla]["value"] == ""
    assert rows[absent_casilla]["value_state"] == CalculationReportValueState.ABSENT.value


def test_a_row_carries_only_the_source_traces_naming_its_own_casilla(
    operation: PinnedAuthorityOperation,
) -> None:
    """A resolver trace reaches the casilla it named and no other row."""
    report, _ = build_fixture_report(operation)

    measured = _row(report, MEASURED_CASILLA)
    assert len(measured.source_provenance) == 1
    trace = measured.source_provenance[0]
    assert trace.resolver_id == "ledger_renta_income_aggregation"
    assert trace.source_ref_digest.startswith("collectible_invoice:hmac-sha256:")
    assert SOURCE_REF.removeprefix("collectible_invoice:") not in trace.source_ref_digest
    # The resolver recorded a canonical content digest, which is carried verbatim
    # so a store holder can compare it against the source object directly.
    assert trace.source_content_digest == f"sha256:{SOURCE_FINGERPRINT}"

    assert [row.casilla_id for row in report.rows if row.source_provenance] == [MEASURED_CASILLA]


def test_a_trace_without_a_content_digest_says_so_rather_than_inventing_one(
    operation: PinnedAuthorityOperation,
) -> None:
    """A resolver that emitted no fingerprint leaves the content digest absent."""
    report, _ = build_fixture_report(
        operation,
        source_provenance=(source_trace(SOURCE_REF, fingerprint=None),),
    )

    assert _row(report, MEASURED_CASILLA).source_provenance[0].source_content_digest is None


def test_header_names_the_traceability_coordinates_it_was_given(operation: PinnedAuthorityOperation) -> None:
    """Every coordinate a reader joins back to the store is present and typed."""
    report, snapshot = build_fixture_report(operation)
    header = report.header

    assert header.modelo == MODELO
    assert int(header.filing_year) == FILING_YEAR
    assert header.calculation_revision_state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert header.verification_report_id == VERIFICATION_REPORT_ID
    assert header.verification_outcome is VerificationCompletenessStatus.COMPLETE
    assert header.filing_record_id == FILING_RECORD_ID
    assert header.registry_snapshot_ref.revision_id == snapshot.revision.id
    assert header.authority_logical_generation == GENERATION
    assert header.software_identity_grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK
    assert header.report_language is OutputLanguage.ES
    assert header.exported_at == EXPORTED_AT
    assert header.row_count == len(report.rows)
    # The fixture revision carries no ledger snapshot, and the header says that
    # rather than substituting an empty digest.
    assert header.ledger_filing_snapshot_fingerprint is None


def test_the_filer_is_named_in_full_on_the_report_and_in_the_csv(operation: PinnedAuthorityOperation) -> None:
    """The taxpayer's own NIF and name are shown, not masked.

    The report is the operator's record of their own declaration; an accountant
    reading it must be able to tell whose return it is. This is the opposite of
    how a THIRD party is treated, which the provenance cases cover.
    """
    report, _ = build_fixture_report(operation)
    payload = _csv(report)

    assert report.header.taxpayer_tax_id == TAXPAYER_TAX_ID
    assert report.header.taxpayer_name == TAXPAYER_NAME
    assert TAXPAYER_TAX_ID.encode("utf-8") in payload
    assert TAXPAYER_NAME.encode("utf-8") in payload
    assert TAXPAYER_TAX_ID.encode("utf-8") in report.canonical_bytes()


def test_every_row_carries_the_role_that_separates_a_result_from_an_input(
    operation: PinnedAuthorityOperation,
) -> None:
    """A derived row names its formula and reads as computed; a supplied row as input."""
    report, snapshot = build_fixture_report(operation)
    definitions = {casilla.id: casilla for casilla in snapshot.revision.casillas}

    for row in report.rows:
        assert row.semantic_role == definitions[row.casilla_id].semantic_role
        assert row.formula_id == definitions[row.casilla_id].formula
        assert row.row_role is calculation_report_row_role(
            declared_input_kind=row.declared_input_kind,
            semantic_role=row.semantic_role,
        )

    derived = [row for row in report.rows if row.declared_input_kind is InputKind.COMPUTED]
    assert derived, "Modelo 130 declares computed casillas"
    assert all(row.formula_id is not None for row in derived)
    assert all(
        row.row_role
        in {
            CalculationReportRowRole.COMPUTED,
            CalculationReportRowRole.SUBTOTAL,
            CalculationReportRowRole.RESULT,
        }
        for row in derived
    )

    supplied = [row for row in report.rows if row.declared_input_kind in {InputKind.MANUAL, InputKind.BOUND}]
    assert supplied
    assert all(row.formula_id is None for row in supplied)
    assert all(row.row_role is CalculationReportRowRole.INPUT for row in supplied)

    csv_rows = _table_rows(_csv(report))
    for row in report.rows:
        assert csv_rows[row.casilla_id]["row_role"] == row.row_role.value


def test_every_declared_input_kind_maps_to_exactly_one_row_role() -> None:
    """The role set is total over the registry's input kinds, so nothing defaults."""
    roles = {kind: calculation_report_row_role(declared_input_kind=kind, semantic_role=None) for kind in InputKind}

    assert set(roles) == set(InputKind)
    assert roles[InputKind.MANUAL] is CalculationReportRowRole.INPUT
    assert roles[InputKind.BOUND] is CalculationReportRowRole.INPUT
    assert roles[InputKind.COMPUTED] is CalculationReportRowRole.COMPUTED
    assert roles[InputKind.INFORMATIONAL] is CalculationReportRowRole.INFORMATIONAL
    assert roles[InputKind.PROJECTION_ONLY] is CalculationReportRowRole.PROJECTION_ONLY


def test_a_settlement_role_decides_the_result_and_subtotal_rows() -> None:
    """The result and subtotal roles come from the product's one settlement vocabulary."""
    result_role = next(iter(DECLARATION_RESULT_SEMANTIC_ROLES))
    subtotal_role = next(iter(SETTLEMENT_SEMANTIC_ROLES - DECLARATION_RESULT_SEMANTIC_ROLES))

    assert (
        calculation_report_row_role(declared_input_kind=InputKind.COMPUTED, semantic_role=result_role)
        is CalculationReportRowRole.RESULT
    )
    assert (
        calculation_report_row_role(declared_input_kind=InputKind.COMPUTED, semantic_role=subtotal_role)
        is CalculationReportRowRole.SUBTOTAL
    )
    # A positional role names no meaning, so it decides nothing and the input
    # kind answers instead.
    assert (
        calculation_report_row_role(declared_input_kind=InputKind.COMPUTED, semantic_role="dr303_23")
        is CalculationReportRowRole.COMPUTED
    )


def test_the_digest_is_taken_over_exactly_the_canonical_bytes(operation: PinnedAuthorityOperation) -> None:
    """A consumer that embeds the canonical bytes embeds what the digest describes."""
    report, _ = build_fixture_report(operation)
    canonical = report.canonical_bytes()

    assert report.report_sha256 == hashlib.sha256(canonical).hexdigest()
    assert json.loads(canonical.decode("utf-8")) == report.canonical_payload()
    assert report.report_sha256.encode("ascii") not in canonical
    # Sorted keys and compact separators, so no second spelling of one report.
    assert canonical == json.dumps(
        report.canonical_payload(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def test_changing_one_header_fact_or_one_row_changes_the_digest(operation: PinnedAuthorityOperation) -> None:
    """The digest covers every fact the report carries."""
    report, _ = build_fixture_report(operation)
    later, _ = build_fixture_report(operation, exported_at=EXPORTED_AT.replace(minute=30))
    translated, _ = build_fixture_report(operation, report_language=OutputLanguage.EN)
    fewer = ModeloCalculationReport(
        header=report.header.model_copy(update={"row_count": len(report.rows) - 1}),
        rows=report.rows[:-1],
    )

    assert later.report_sha256 != report.report_sha256
    assert later.rows == report.rows
    assert translated.report_sha256 != report.report_sha256
    assert fewer.report_sha256 != report.report_sha256

    with pytest.raises(ValueError, match="row_count"):
        ModeloCalculationReport(header=report.header, rows=report.rows[:-1])


def test_rebuilding_from_the_same_revision_is_byte_deterministic(operation: PinnedAuthorityOperation) -> None:
    """Two builds of one stored revision agree byte for byte, document included.

    Nothing in the report is read from a wall clock or from an unordered
    collection, so the canonical bytes are a pure function of the revision, the
    snapshot, the traceability coordinates, the language and the export timestamp
    the caller passes in. That is what lets a later reader prove the document in
    front of them renders the revision it names.
    """
    first, _ = build_fixture_report(operation)
    second, _ = build_fixture_report(operation)

    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.report_sha256 == second.report_sha256
    assert _csv(first) == _csv(second)


def test_a_second_process_rebuilds_the_same_report_digest() -> None:
    """Determinism holds across interpreters, not only across calls in one.

    A fresh process rebuilds the registry snapshot, re-derives every id and
    re-serialises the report from scratch. A digest that agreed within one
    process but not across two would mean the report depends on some state the
    first process happened to hold.
    """
    source_root = str(Path(__file__).resolve().parents[4])
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cadrumo.application.modelo.tests._calculation_report_fixture import fixture_report_digest;"
            "print(fixture_report_digest())",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": source_root},
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == fixture_report_digest()


def test_a_perceptor_tax_identity_in_provenance_reaches_neither_the_report_nor_the_csv(
    operation: PinnedAuthorityOperation,
) -> None:
    """A third party's NIF is digested at the builder, so no serialisation carries it.

    The retenciones resolver records a source reference built from the perceptor's
    tax identifier, which is a person other than the filer. The report is carried
    off-host by operators, so that identity must not travel in it; the family
    stays legible so a reader still knows what kind of source the row rests on.
    """
    report, _ = build_fixture_report(operation, source_provenance=(source_trace(PERCEPTOR_SOURCE_REF),))
    payload = _csv(report)

    measured = _row(report, MEASURED_CASILLA)
    assert measured.source_provenance
    assert all(trace.source_ref_digest.startswith("perceptor:hmac-sha256:") for trace in measured.source_provenance)
    assert all(PERCEPTOR_NIF not in trace.source_ref_digest for trace in measured.source_provenance)

    assert PERCEPTOR_NIF.encode("ascii") not in report.canonical_bytes()
    assert PERCEPTOR_NIF.encode("ascii") not in payload
    assert PERCEPTOR_NIF not in report.model_dump_json()


def test_a_reference_that_is_a_bare_identifier_is_digested_whole(
    operation: PinnedAuthorityOperation,
) -> None:
    """A reference with no family token has nothing printed from it at all.

    Detector teeth for the family split: the shipped resolvers all prefix a
    family, so this fixture reference is the shape the rule must fail closed on.
    Printing its leading segment would print the identifier itself.
    """
    report, _ = build_fixture_report(operation, source_provenance=(source_trace(UNFAMILIED_SOURCE_REF),))
    payload = _csv(report)

    digest = _row(report, MEASURED_CASILLA).source_provenance[0].source_ref_digest
    assert digest.startswith(f"{OPAQUE_PROVENANCE_FAMILY}:hmac-sha256:")
    assert UNFAMILIED_SOURCE_REF not in digest
    assert UNFAMILIED_SOURCE_REF.encode("ascii") not in report.canonical_bytes()
    assert UNFAMILIED_SOURCE_REF.encode("ascii") not in payload


def test_the_report_states_in_its_own_language_that_it_is_not_aeat_evidence(
    operation: PinnedAuthorityOperation,
) -> None:
    """The statement is catalogue-sourced and follows the report's language."""
    spanish, _ = build_fixture_report(operation, report_language=OutputLanguage.ES)
    english, _ = build_fixture_report(operation, report_language=OutputLanguage.EN)

    assert spanish.header.local_calculation_notice == local_calculation_report_notice(OutputLanguage.ES)
    assert english.header.local_calculation_notice == local_calculation_report_notice(OutputLanguage.EN)
    assert spanish.header.local_calculation_notice != english.header.local_calculation_notice
    for language in OutputLanguage:
        notice = local_calculation_report_notice(language)
        assert notice.strip()
        assert "," not in notice, "the statement survives a delimited preamble line without splitting a cell"


def test_a_catalogue_without_the_statement_refuses_the_report(tmp_path: Path) -> None:
    """A report that cannot say what it is must not be produced.

    Detector teeth for the statement: the shipped catalogues carry the key in
    every language, so the absence is exercised against a fixture catalogue.
    """
    (tmp_path / "es.yml").write_text("application: {}\n", encoding="utf-8")
    (tmp_path / "en.yml").write_text("application: {}\n", encoding="utf-8")

    with override_locales_root(tmp_path), pytest.raises(CalculationReportNoticeUnavailableError) as refusal:
        local_calculation_report_notice(OutputLanguage.EN)

    assert CALCULATION_REPORT_NOTICE_LOCALE_KEY in str(refusal.value.context)


def test_csv_states_it_is_a_local_calculation_above_its_table(operation: PinnedAuthorityOperation) -> None:
    """The preamble carries the statement, every header fact and the content digest."""
    report, _ = build_fixture_report(operation)
    document = serialize_calculation_report(report, document_format=CalculationReportDocumentFormat.CSV)
    text = document.payload.decode("utf-8")
    preamble = calculation_report_csv_preamble_lines(report)

    assert all(line.startswith(CALCULATION_REPORT_CSV_PREAMBLE_PREFIX) for line in preamble)
    assert all(document.payload.count(line.encode("utf-8")) == 1 for line in preamble)
    assert any(report.header.local_calculation_notice in line for line in preamble)
    assert (
        f"{CALCULATION_REPORT_CSV_PREAMBLE_PREFIX}{CALCULATION_REPORT_DIGEST_PREAMBLE_KEY}: {report.report_sha256}"
        in preamble
    )
    assert text.startswith(CALCULATION_REPORT_CSV_PREAMBLE_PREFIX)
    assert document.media_type == "text/csv"
    assert document.filename_extension == "csv"
    assert document.row_count == len(report.rows)


def test_csv_table_reads_back_as_the_rows_it_was_built_from(operation: PinnedAuthorityOperation) -> None:
    """Parsing the published table recovers each row's state, value and provenance."""
    report, _ = build_fixture_report(operation)
    payload = _csv(report)
    table = "\n".join(
        line
        for line in payload.decode("utf-8").splitlines()
        if not line.startswith(CALCULATION_REPORT_CSV_PREAMBLE_PREFIX)
    )
    parsed = _table_rows(payload)

    assert tuple(next(iter(csv.reader(io.StringIO(table))))) == CALCULATION_REPORT_CSV_FIELDNAMES
    assert len(parsed) == len(report.rows)
    measured = _row(report, MEASURED_CASILLA)
    assert measured.source_provenance[0].source_ref_digest in parsed[MEASURED_CASILLA]["source_provenance"]
    assert parsed[ZERO_CASILLA]["source_provenance"] == ""
