"""Behaviour tests for observed Modelo 100 PDF parsing."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.schema_extraction import ExtractionProfileDefinition, ExtractionTargetDefinition
from ...pdf import source_pdf_reference_path
from .._parser import parse_borrador
from .._schema import ArtefactKind, BorradorParseMode, InboundBorradorObservation
from ..errors import BorradorParseError

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]


_CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA = validated_casilla_id(
    "0550",
    surface="test_modelo_100_summary.cuota_integra_general_estatal",
)
_CUOTA_INTEGRA_TOTAL_CASILLA = validated_casilla_id(
    "0595",
    surface="test_modelo_100_summary.cuota_integra_total",
)
_RETENCIONES_CASILLA = validated_casilla_id("0699", surface="test_modelo_100_summary.retenciones")
_PAGOS_FRACCIONADOS_CASILLA = validated_casilla_id(
    "0700",
    surface="test_modelo_100_summary.pagos_fraccionados",
)
_CUOTA_RESULTANTE_CASILLA = validated_casilla_id(
    "0720",
    surface="test_modelo_100_summary.cuota_resultante",
)

_OBSERVED_VALUES: dict[CasillaId, str] = {
    _CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA: "3500.00",
    _CUOTA_INTEGRA_TOTAL_CASILLA: "6440.00",
    _RETENCIONES_CASILLA: "1200.00",
    _PAGOS_FRACCIONADOS_CASILLA: "1800.00",
    _CUOTA_RESULTANTE_CASILLA: "3140.00",
}


def _render_borrador_pdf_bytes(
    *,
    artefact_kind: str = "BORRADOR",
    csv: str | None = None,
    casilla_values: Mapping[CasillaId, str] | None = None,
) -> bytes:
    """Render one Modelo 100 borrador PDF to bytes via a single ReportLab Canvas."""
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    values = casilla_values if casilla_values is not None else _OBSERVED_VALUES
    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 60
    page.drawString(50, y, "AGENCIA TRIBUTARIA")
    y -= 18
    page.drawString(50, y, "Declaracion IRPF - Modelo 100")
    page.drawRightString(width - 50, y, "Ejercicio: 2025")
    y -= 18
    page.drawString(50, y, "NIF: 00000000T")
    y -= 18
    if artefact_kind == "BORRADOR":
        page.drawString(50, y, "BORRADOR")
        y -= 18
    elif artefact_kind == "PREDECLARACION":
        page.drawString(50, y, "VISTA PREVIA - Documento no valido para presentar")
        y -= 18
    for casilla_id, raw in values.items():
        amount = _spanish_amount(Decimal(raw))
        page.drawString(50, y, f"{casilla_id} Valor observado {amount}")
        y -= 16
    if csv is not None:
        page.drawString(50, 40, f"Codigo Seguro de Verificacion: {csv}")
    page.save()
    return buffer.getvalue()


def _write_borrador_pdf(tmp_path: Path, payload: bytes, *, artefact_kind: str = "BORRADOR") -> Path:
    """Write pre-rendered borrador PDF bytes into a per-test ``tmp_path`` file."""
    path = tmp_path / f"modelo_100_2025_{artefact_kind.lower()}.pdf"
    path.write_bytes(payload)
    return path


def _generate_pdf(
    tmp_path: Path,
    *,
    artefact_kind: str = "BORRADOR",
    csv: str | None = None,
    casilla_values: Mapping[CasillaId, str] | None = None,
) -> Path:
    payload = _render_borrador_pdf_bytes(
        artefact_kind=artefact_kind,
        csv=csv,
        casilla_values=casilla_values,
    )
    return _write_borrador_pdf(tmp_path, payload, artefact_kind=artefact_kind)


@pytest.fixture(scope="module")
def default_borrador_pdf_bytes() -> bytes:
    """Render the default-content BORRADOR Modelo 100 PDF once per module.

    Several tests share the identical default artefact (``_OBSERVED_VALUES``,
    ``artefact_kind='BORRADOR'``, no CSV). Building the ReportLab Canvas once
    and re-writing the cached bytes into each test's own ``tmp_path`` keeps
    per-test filesystem isolation intact (the rename tests still mutate only
    their own copy) while paying the Canvas-construction cost a single time.
    """
    return _render_borrador_pdf_bytes(artefact_kind="BORRADOR", csv=None, casilla_values=None)


def _profile(
    *,
    target_casilla_ids: tuple[CasillaId, ...] = (
        _CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA,
        _PAGOS_FRACCIONADOS_CASILLA,
    ),
    min_coverage: Decimal = Decimal("1"),
) -> ExtractionProfileDefinition:
    return ExtractionProfileDefinition(
        id="modelo-100-observed-values",
        surface="borrador_pdf",
        artefact_kind="modelo_100_renta",
        accepted_artefact_kinds=("declaration_pdf",),
        parser="cadrumo.adapters.inbound.borrador.parse_borrador",
        target_casillas=tuple(
            ExtractionTargetDefinition(
                casilla_id=cid,
                match_strategy="numeric_casilla",
                value_kind="amount",
            )
            for cid in target_casilla_ids
        ),
        confidence="strict",
        min_coverage=min_coverage,
        failure_semantics="fail_hard",
        legal_refs=("rd-439-2007:art-110",),
        source_refs=("aeat-modelo-130-instructions",),
    )


def _spanish_amount(value: Decimal) -> str:
    whole, decimals = f"{value:.2f}".split(".")
    groups: list[str] = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    return f"{'.'.join(reversed(groups))},{decimals}"


class TestArtefactKindDetection:
    """Detect the correct :class:`ArtefactKind` per artefact marker."""

    def test_detects_borrador(self, tmp_path: Path, default_borrador_pdf_bytes: bytes) -> None:
        pdf = _write_borrador_pdf(tmp_path, default_borrador_pdf_bytes)
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.BORRADOR
        assert filing.csv is None

    def test_detects_predeclaracion(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(tmp_path, artefact_kind="PREDECLARACION")
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.PREDECLARACION
        assert filing.csv is None

    def test_detects_declaracion_with_csv(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(
            tmp_path,
            artefact_kind="DECLARACION",
            csv="MNOP4321QRST8765",
        )
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.DECLARACION
        assert filing.csv == "MNOP4321QRST8765"

    def test_predeclaracion_with_csv_like_footer_does_not_surface_filed_csv(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(
            tmp_path,
            artefact_kind="PREDECLARACION",
            csv="MNOP4321QRST8765",
        )

        filing = parse_borrador(pdf)

        assert filing.artefact_kind is ArtefactKind.PREDECLARACION
        assert filing.csv is None

    def test_unrecognised_error_omits_source_filename(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(tmp_path, artefact_kind="UNRECOGNISED")
        sensitive_pdf = tmp_path / "12345678Z-renta-borrador.pdf"
        pdf.rename(sensitive_pdf)

        with pytest.raises(BorradorParseError) as exc_info:
            parse_borrador(sensitive_pdf)

        rendered = str(exc_info.value)
        assert sensitive_pdf.name not in rendered
        assert str(sensitive_pdf) not in rendered
        assert "<input-pdf>" in rendered


class TestObservedValues:
    """Extract printed casilla rows without claiming Modelo 100 completeness."""

    def test_extracts_observed_casilla_rows(self, tmp_path: Path, default_borrador_pdf_bytes: bytes) -> None:
        pdf = _write_borrador_pdf(tmp_path, default_borrador_pdf_bytes)
        filing: InboundBorradorObservation = parse_borrador(pdf)
        assert filing.modelo == "100"
        assert filing.ejercicio == "2025"
        assert filing.tax_id == "00000000T"
        extracted = {value.casilla_id: value.printed_value for value in filing.values}
        assert extracted == {casilla_id: Decimal(raw) for casilla_id, raw in _OBSERVED_VALUES.items()}
        assert filing.registry_extraction_profile_id is None
        assert filing.extraction_coverage is None
        assert filing.source_pdf_path == source_pdf_reference_path(filing.source_pdf_sha256)
        assert pdf.name not in str(filing.source_pdf_path)

    def test_parse_logs_do_not_expose_source_filename(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        default_borrador_pdf_bytes: bytes,
    ) -> None:
        pdf = _write_borrador_pdf(tmp_path, default_borrador_pdf_bytes)
        sensitive_pdf = tmp_path / "12345678Z-renta-borrador.pdf"
        pdf.rename(sensitive_pdf)

        with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.inbound.borrador._parser"):
            parse_borrador(sensitive_pdf)

        rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
        assert "12345678Z-renta-borrador.pdf" not in rendered_logs
        assert "source=<input-pdf>" in rendered_logs

    def test_registry_profile_filters_targets_and_records_coverage(
        self,
        tmp_path: Path,
        default_borrador_pdf_bytes: bytes,
    ) -> None:
        pdf = _write_borrador_pdf(tmp_path, default_borrador_pdf_bytes)
        profile = _profile()

        filing = parse_borrador(
            pdf,
            extraction_profile=profile,
            parse_mode=BorradorParseMode.REGISTRY_PROFILE,
        )

        assert {value.casilla_id for value in filing.values} == {
            _CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA,
            _PAGOS_FRACCIONADOS_CASILLA,
        }
        assert filing.registry_extraction_profile_id == "modelo-100-observed-values"
        assert filing.extraction_coverage == Decimal("1")

    def test_registry_profile_fails_below_required_coverage(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(tmp_path, casilla_values={_CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA: "3500.00"})
        profile = _profile()

        with pytest.raises(BorradorParseError, match="coverage below minimum"):
            parse_borrador(
                pdf,
                extraction_profile=profile,
                parse_mode=BorradorParseMode.REGISTRY_PROFILE,
            )

    def test_registry_profile_mode_requires_profile(self, tmp_path: Path, default_borrador_pdf_bytes: bytes) -> None:
        pdf = _write_borrador_pdf(tmp_path, default_borrador_pdf_bytes)

        with pytest.raises(BorradorParseError, match="requires a registry extraction profile"):
            parse_borrador(pdf, parse_mode=BorradorParseMode.REGISTRY_PROFILE)


class TestDetectionDisambiguation:
    """Make the precedence of artefact markers observable."""

    def test_csv_plus_borrador_body_classifies_as_declaracion(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(
            tmp_path,
            artefact_kind="DECLARACION",
            csv="MNOP4321QRST8765",
        )
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.DECLARACION

    def test_vista_previa_banner_trumps_borrador_header(self, tmp_path: Path) -> None:
        pdf = _generate_pdf(tmp_path, artefact_kind="PREDECLARACION")
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.PREDECLARACION


class TestSparseExtraction:
    """Only printed rows are returned for sparse PDFs."""

    def test_sparse_predeclaracion_yields_observed_values_only(self, tmp_path: Path) -> None:
        sparse = {
            _CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA: "100.00",
            _CUOTA_INTEGRA_TOTAL_CASILLA: "220.00",
        }
        pdf = _generate_pdf(
            tmp_path,
            artefact_kind="PREDECLARACION",
            casilla_values=sparse,
        )
        filing = parse_borrador(pdf)
        assert filing.artefact_kind is ArtefactKind.PREDECLARACION
        assert {value.casilla_id for value in filing.values} == set(sparse)


class TestOverrides:
    """Verify the explicit ``artefact_kind_override`` entry-point arg."""

    def test_artefact_kind_override_skips_detection(self, tmp_path: Path, default_borrador_pdf_bytes: bytes) -> None:
        pdf = _write_borrador_pdf(tmp_path, default_borrador_pdf_bytes)
        with pytest.raises(BorradorParseError, match=r"BORRADOR|DECLARACION|artefact|kind"):
            parse_borrador(pdf, artefact_kind_override=ArtefactKind.DECLARACION)


class TestBorradorParseErrorAttributes:
    """BorradorParseError carries structured attributes matching discipline parity.

    These tests assert on typed attributes rather than message strings so that
    callers can introspect failure details without fragile string parsing.
    """

    def test_coverage_failure_populates_missing_and_coverage(self, tmp_path: Path) -> None:
        # PDF has only 0550; profile requires 0550 + 0700 with full coverage.
        pdf = _generate_pdf(tmp_path, casilla_values={_CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA: "3500.00"})
        profile = _profile(
            target_casilla_ids=(
                _CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA,
                _PAGOS_FRACCIONADOS_CASILLA,
            ),
            min_coverage=Decimal("1"),
        )

        with pytest.raises(BorradorParseError) as exc_info:
            parse_borrador(pdf, extraction_profile=profile, parse_mode=BorradorParseMode.REGISTRY_PROFILE)

        err = exc_info.value
        assert err.missing == (_PAGOS_FRACCIONADOS_CASILLA,)
        assert err.coverage == Decimal("1") / Decimal("2")
        assert err.malformed == ()
        assert err.ambiguous == ()

    def test_coverage_failure_missing_sorted_tuple(self, tmp_path: Path) -> None:
        # Profile requires three casillas; PDF only has 0550 — both absent IDs surface sorted.
        pdf = _generate_pdf(tmp_path, casilla_values={_CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA: "100.00"})
        profile = _profile(
            target_casilla_ids=(
                _CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA,
                _CUOTA_INTEGRA_TOTAL_CASILLA,
                _PAGOS_FRACCIONADOS_CASILLA,
            ),
            min_coverage=Decimal("1"),
        )

        with pytest.raises(BorradorParseError) as exc_info:
            parse_borrador(pdf, extraction_profile=profile, parse_mode=BorradorParseMode.REGISTRY_PROFILE)

        err = exc_info.value
        assert err.missing == (_CUOTA_INTEGRA_TOTAL_CASILLA, _PAGOS_FRACCIONADOS_CASILLA)
        assert err.coverage == Decimal("1") / Decimal("3")

    def test_default_raise_has_empty_structured_attributes(self) -> None:
        # A bare raise (e.g. from _require_match) leaves all attributes at defaults.
        err = BorradorParseError("could not locate required field: NIF")
        assert err.missing == ()
        assert err.malformed == ()
        assert err.ambiguous == ()
        assert err.coverage is None

    def test_explicit_population_of_all_attributes(self) -> None:
        err = BorradorParseError(
            "test",
            missing=(_CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA,),
            malformed=(_PAGOS_FRACCIONADOS_CASILLA,),
            ambiguous=(_CUOTA_INTEGRA_TOTAL_CASILLA,),
            coverage=Decimal("0.5"),
        )
        assert err.missing == (_CUOTA_INTEGRA_GENERAL_ESTATAL_CASILLA,)
        assert err.malformed == (_PAGOS_FRACCIONADOS_CASILLA,)
        assert err.ambiguous == (_CUOTA_INTEGRA_TOTAL_CASILLA,)
        assert err.coverage == Decimal("0.5")
