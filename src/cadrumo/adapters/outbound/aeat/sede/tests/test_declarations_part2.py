"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ......core.casilla_id import validated_casilla_id, validated_casilla_id_map
from ......core.casilla_value_kind import CasillaValueKind
from ......core.period import Period
from ......domain.calculations.registry.bindings_previous_filing import previous_filing_source_reference
from ..declarations_observations import (
    _submitted_file_coverage_for_casillas,
    non_numeric_observed_casillas,
    observed_casillas_from_submitted_file,
    observed_header_facts_from_submitted_file,
    resolve_previous_filing_bindings_from_filed_declarations,
)
from ._declarations_support import (
    _COTEJO_DOCUMENT_URL,
    _DECLARATIONS_LISTING_BASE_PATH,
    _DECLARATIONS_LISTING_URL,
    _FIXTURE_ROOT,
    _MODELO_130_COMPUTED_CASILLAS,
    _REGISTER_DOWNLOAD_URL,
    _SUBMITTED_FILE_100_2023_0A,
    UTC,
    AnyHttpUrl,
    CasillaId,
    Decimal,
    Declaracion,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    InputKind,
    ObservedCasillaValue,
    Path,
    RegistryValidationError,
    SedeParseError,
    _declaration_pdf_payload,
    _filed_observation,
    _isolate_secure_object_backend,  # noqa: F401
    _modelo_130_snapshot,
    _modelo_snapshot,
    _observed_casillas_from_declaration_pdf,
    _read_guard_policy_from_snapshot,
    _submitted_file_payload,
    assert_declarations_read_browser_action,
    assert_declarations_read_http,
    calculate_registry_snapshot,
    date,
    datetime,
    hashlib,
    parse_export_payload,
    registry_observation_from_filed_declaration,
    resolve_export_layout,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.usefixtures("_isolate_secure_object_backend"),
]
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = validated_casilla_id(
    "0224",
    surface="_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA",
)
_M100_CASILLA_0180: CasillaId = validated_casilla_id("0180", surface="_M100_CASILLA_0180")
_M100_CASILLA_0695: CasillaId = validated_casilla_id("0695", surface="_M100_CASILLA_0695")
_M100_CASILLA_0067: CasillaId = validated_casilla_id("0067", surface="_M100_CASILLA_0067")
_M130_PAGOS_FRACCIONADOS_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "05",
    surface="_M130_PAGOS_FRACCIONADOS_ANTERIORES_CASILLA",
)
_M130_RESULTADOS_NEGATIVOS_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "15",
    surface="_M130_RESULTADOS_NEGATIVOS_ANTERIORES_CASILLA",
)
_M130_SALDO_NEGATIVO_FIN_PERIODO_CASILLA: CasillaId = validated_casilla_id(
    "saldo-negativo-fin-periodo",
    surface="_M130_SALDO_NEGATIVO_FIN_PERIODO_CASILLA",
)
_SUBMITTED_FILE_111_2025_1T = _FIXTURE_ROOT / "submitted-files" / "modelo-111-2025-1T-redacted.txt"
_M111_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("28", surface="_M111_RETENCIONES_CASILLA")
_M111_RESULTADO_CASILLA: CasillaId = validated_casilla_id("30", surface="_M111_RESULTADO_CASILLA")


def _casilla_values(values: Mapping[object, Decimal]) -> dict[CasillaId, Decimal]:
    return validated_casilla_id_map(values, surface="sede declarations part2 casilla values")


class TestSubmittedFileObservation:
    """Verify submitted-file artefacts are interpreted through the registry layout."""

    def test_redacted_submitted_file_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_130_snapshot()
        body = _submitted_file_payload()
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period=Period.from_year_and_code(2026, "1T"),
            expediente_id="202610013522222A",
            estado="ALTA",
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
            content_type="application/octet-stream",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        )

        observed = observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )

        assert {item.casilla_id: Decimal(item.value) for item in observed} == _casilla_values(
            {
                "01": Decimal("100"),
                "02": Decimal("25"),
                "03": Decimal("75"),
                "04": Decimal("15"),
                "05": Decimal("0"),
                "06": Decimal("0"),
                "07": Decimal("15"),
                "08": Decimal("0"),
                "09": Decimal("0"),
                "10": Decimal("0"),
                "11": Decimal("0"),
                "12": Decimal("15"),
                "13": Decimal("0"),
                "14": Decimal("15"),
                "15": Decimal("0"),
                "16": Decimal("0"),
                "17": Decimal("15"),
                "18": Decimal("0"),
                "19": Decimal("15"),
            },
        )

    def test_low_numbered_identifiers_survive_submitted_file_capture(self) -> None:
        """A low-numbered NIF and a 01-09 province survive the real Sede capture path.

        Modelo 180's declarante and perceptor NIF header slots, and the
        perceptor's own NIF, legal-representative NIF, provincia,
        inmueble-provincia, inmueble-codigo-municipio and
        inmueble-codigo-postal casillas all declared ``padding =
        "left_zero"`` even though every one of them always exactly fills
        its slot: a NIF is nine fixed alphanumeric characters, a province
        code is a fixed two digits from a closed 01-52 table, an INE
        municipality code and a Spanish postal code are both fixed
        five-digit province-prefixed identifiers. ``left_zero``'s parse
        side (``_unpad``) strips leading "0" characters unconditionally,
        so a genuinely low-numbered value -- a DNI issued under
        00100000, a taxpayer in provinces 01-09 -- silently lost its
        leading digits the moment a previously-filed declaration was
        captured through this exact production path and persisted as an
        :class:`ObservedCasillaValue`/:class:`ObservedHeaderFact`. This
        test fails before the ``padding = "none"`` fix and passes after.
        """
        snapshot = _modelo_snapshot("180", filing_year=2026, period="0A")
        declarante_fields: dict[tuple[int, int], str] = {
            (1, 1): "1",
            (2, 4): "180",
            (5, 8): "2026",
            (9, 17): "00011111Z",
            (136, 144): "000000001",
            (145, 160): " " + "100050".zfill(15),
            (161, 175): "19010".zfill(15),
        }
        perceptor_fields: dict[tuple[int, int], str] = {
            (1, 1): "2",
            (2, 4): "180",
            (5, 8): "2026",
            (9, 17): "00011111Z",
            (18, 26): "00098765Z",
            (27, 35): "00087654X",
            (36, 75): "ARRENDADOR EJEMPLO".ljust(40),
            (76, 77): "01",
            (78, 78): "1",
            (79, 92): "N" + "2500".zfill(13),
            (93, 96): "0000",
            (97, 109): "475".zfill(13),
            (110, 113): "2025",
            (114, 114): "1",
            (115, 134): "1234567VK4713C0001XY",
            (135, 139): "CL".ljust(5),
            (140, 189): "CALLE MAYOR".ljust(50),
            (190, 192): "NUM",
            (193, 197): "12".ljust(5),
            (198, 200): "BIS",
            (201, 203): "A".ljust(3),
            (204, 206): "1".ljust(3),
            (207, 209): "2".ljust(3),
            (210, 212): "03".ljust(3),
            (213, 215): "B".ljust(3),
            (216, 255): "EDIFICIO CENTRAL".ljust(40),
            (256, 285): "MADRID".ljust(30),
            (286, 315): "MADRID".ljust(30),
            (316, 320): "01001",
            (321, 322): "01",
            (323, 327): "01001",
        }

        def _record(length: int, fields: dict[tuple[int, int], str]) -> str:
            buffer = [" "] * length
            for (start, end), value in fields.items():
                buffer[start - 1 : end] = value
            return "".join(buffer)

        body = (_record(500, declarante_fields) + _record(500, perceptor_fields)).encode("latin-1")
        declaration = Declaracion(
            modelo="180",
            ejercicio=2026,
            period=Period.from_year_and_code(2026, "0A"),
            expediente_id="202610013522223B",
            estado="ALTA",
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
            content_type="application/octet-stream",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        )

        observed_casillas = observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observed_by_casilla = {item.casilla_id: item.value for item in observed_casillas}
        assert observed_by_casilla["perc.nif"] == "00098765Z"
        assert observed_by_casilla["perc.nif-representante-legal"] == "00087654X"
        assert observed_by_casilla["perc.provincia"] == "01"
        assert observed_by_casilla["perc.inmueble-provincia"] == "01"
        assert observed_by_casilla["perc.inmueble-codigo-municipio"] == "01001"
        assert observed_by_casilla["perc.inmueble-codigo-postal"] == "01001"

        header_facts = observed_header_facts_from_submitted_file(snapshot=snapshot, body=body)
        presenter_tax_id_values = {fact.value for fact in header_facts if fact.header_key == "presenter.tax_id"}
        assert presenter_tax_id_values == {"00011111Z"}

    def test_modelo_130_redacted_submitted_file_matches_registry_calculation(self) -> None:
        snapshot = _modelo_130_snapshot()
        body = _submitted_file_payload()
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period=Period.from_year_and_code(2026, "1T"),
            expediente_id="202610013522222A",
            estado="ALTA",
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
            content_type="application/octet-stream",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        )
        observed = observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observed_values = {item.casilla_id: Decimal(item.value) for item in observed}
        # Casillas 05 (pagos fraccionados anteriores) and 15
        # (resultados-negativos-anteriores) are previous-filing bound registry
        # casillas; they must route through binding_values keyed by the binding
        # id, not through inputs alone. The _formula_runtime smuggle guard
        # refuses inputs["05"]/inputs["15"] without matching binding entries.
        prior_payments_value = observed_values.get(_M130_PAGOS_FRACCIONADOS_ANTERIORES_CASILLA, Decimal("0"))
        carry_forward_value = observed_values.get(_M130_RESULTADOS_NEGATIVOS_ANTERIORES_CASILLA, Decimal("0"))
        input_values = {
            casilla.id: observed_values[casilla.id]
            for casilla in snapshot.revision.casillas
            if casilla.input_kind != InputKind.COMPUTED and casilla.id != _M130_RESULTADOS_NEGATIVOS_ANTERIORES_CASILLA
        }
        binding = next(
            item for item in snapshot.revision.bindings if item.id == "irpf.previous_year_economic_activity_net_income"
        )
        source_reference = previous_filing_source_reference(binding)
        source_casilla_ids = source_reference.source_casilla_ids
        previous_year_values: dict[CasillaId, Decimal] = {
            casilla_id: value
            for casilla_id, value in zip(
                source_casilla_ids,
                (Decimal("3000"), Decimal("4000"), Decimal("2000"), Decimal("4000")),
                strict=True,
            )
        }
        binding_values = resolve_previous_filing_bindings_from_filed_declarations(
            snapshot.revision,
            (
                _filed_observation(
                    modelo=source_reference.source_modelo,
                    ejercicio=2025,
                    period=source_reference.required_periods[0],
                    casilla_values=previous_year_values,
                ),
            ),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )
        binding_values["modelo-130-pagos-fraccionados-anteriores"] = prior_payments_value
        binding_values["modelo-130-resultados-negativos-anteriores"] = carry_forward_value
        computed_casillas = {
            casilla.id for casilla in snapshot.revision.casillas if casilla.input_kind == InputKind.COMPUTED
        }
        assert computed_casillas == _MODELO_130_COMPUTED_CASILLAS | {_M130_SALDO_NEGATIVO_FIN_PERIODO_CASILLA}

        calculated = calculate_registry_snapshot(
            snapshot,
            inputs=input_values,
            date_context={"filing_period": date(2026, 3, 31)},
            binding_values=binding_values,
        )

        assert {casilla_id: calculated.values[casilla_id] for casilla_id in _MODELO_130_COMPUTED_CASILLAS} == {
            casilla_id: observed_values[casilla_id] for casilla_id in _MODELO_130_COMPUTED_CASILLAS
        }
        assert calculated.values[_M130_SALDO_NEGATIVO_FIN_PERIODO_CASILLA] == Decimal("0.00")

    def test_submitted_file_coverage_scores_fully_extracted_modelo_130_filing(self) -> None:
        # The extracted coverage helper resolves the export layout and scores the
        # observed casillas against the registry-expected set. The M130 redacted
        # submitted file yields every expected result casilla, so coverage is 1.0.
        snapshot = _modelo_130_snapshot()
        body = _submitted_file_payload()
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period=Period.from_year_and_code(2026, "1T"),
            expediente_id="202610013522222A",
            estado="ALTA",
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
            content_type="application/octet-stream",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        )
        casillas = observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )

        coverage = _submitted_file_coverage_for_casillas(snapshot=snapshot, body=body, casillas=casillas)

        # The helper must agree with the leaf coverage scorer it composes.
        resolved = resolve_export_layout(snapshot)
        parsed = parse_export_payload(resolved.layout, body)
        expected = {
            casilla_id
            for casilla_id, fields in resolved.fields_by_casilla.items()
            if any(field.id in {f.field_id for f in parsed.fields} for field in fields)
        }
        observed_ids = {casilla.casilla_id for casilla in casillas}
        assert coverage == len(observed_ids & expected) / len(expected)
        assert coverage == pytest.approx(1.0)

    def test_modelo_111_live_redacted_submitted_file_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_snapshot("111", filing_year=2025, period="1T")
        profile = snapshot.extraction_profiles["modelo-111-export-record"]
        body = _submitted_file_payload(_SUBMITTED_FILE_111_2025_1T)
        declaration = Declaracion(
            modelo="111",
            ejercicio=2025,
            period=Period.from_year_and_code(2025, "1T"),
            expediente_id="202511113520436S",
            estado="ALTA",
            presented_at=datetime(2025, 7, 21, 20, 15, 9, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
            content_type="application/octet-stream",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 5, 5, 6, 9, 7, tzinfo=UTC),
        )

        observed = observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observed_values = {item.casilla_id: Decimal(item.value) for item in observed}
        calculated = calculate_registry_snapshot(
            snapshot,
            inputs={
                casilla_id: value
                for casilla_id, value in observed_values.items()
                if casilla_id not in {_M111_RETENCIONES_CASILLA, _M111_RESULTADO_CASILLA}
            },
            date_context={},
        )
        parsed = parse_export_payload(resolve_export_layout(snapshot).layout, body)
        parsed_fields = {field.field_id: field.value for field in parsed.fields}

        assert set(observed_values) == {t.casilla_id for t in profile.target_casillas}
        assert parsed_fields["modelo-111-tax-id"] == "Y0000001S"
        assert parsed_fields["modelo-111-surnames"] == "SANITIZED SURNAME"
        assert observed_values[_M111_RETENCIONES_CASILLA] == calculated.values[_M111_RETENCIONES_CASILLA]
        assert observed_values[_M111_RESULTADO_CASILLA] == calculated.values[_M111_RESULTADO_CASILLA]

    def test_modelo_100_redacted_xml_dictionary_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2023, period="0A")
        body = _submitted_file_payload(_SUBMITTED_FILE_100_2023_0A)
        declaration = Declaracion(
            modelo="100",
            ejercicio=2023,
            period=Period.from_year_and_code(2023, "0A"),
            expediente_id="202310013522222A",
            estado="ALTA",
            presented_at=datetime(2024, 2, 1, 19, 15, 34, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
            content_type="application/xml",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 5, 5, 10, 0, 0, tzinfo=UTC),
        )

        observed = observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observed_values = {item.casilla_id: item.value for item in observed}
        body_text = body.decode("utf-8")

        assert len(observed) == 77
        assert observed_values[_M100_CASILLA_0180] == "26.26"
        assert observed_values[_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA] == "37.37"
        assert observed_values[_M100_CASILLA_0695] == "87.87"
        # `0067` (CURBA, "Urbana") is an `LGC` row, so the parser hands back a
        # bool -- and this assertion previously read "True", pinning a Python
        # repr into filed-artefact evidence against a REAL AEAT artefact. The
        # artefact says `<CURBA>S</CURBA>`; inverted rather than deleted, so it
        # now holds the boundary to the token AEAT wrote.
        assert observed_values[_M100_CASILLA_0067] == "S"
        assert "True" not in observed_values.values(), (
            "a Python bool repr reached filed-artefact evidence; observations record the "
            "artefact's own token, so nothing here may spell a value the way Python does"
        )
        assert 'nif="Y' not in body_text
        assert 'nif="00000000T"' in body_text
        assert "CL SANITIZADA 0000 LOCALIDAD" in body_text

    def test_modelo_100_redacted_xml_observation_roundtrips_through_encrypted_store(self, tmp_path: Path) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2023, period="0A")
        body = _submitted_file_payload(_SUBMITTED_FILE_100_2023_0A)
        declaration = Declaracion(
            modelo="100",
            ejercicio=2023,
            period=Period.from_year_and_code(2023, "0A"),
            expediente_id="202310013522222A",
            estado="ALTA",
            presented_at=datetime(2024, 2, 1, 19, 15, 34, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
            content_type="application/xml",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 5, 5, 10, 0, 0, tzinfo=UTC),
        )
        store = FiledDeclaracionObservationStore(
            tmp_path / "observations",
        )
        encrypted_artefact = store.persist_artefact(
            (declaration.modelo, declaration.ejercicio, declaration.period, declaration.expediente_id),
            artefact,
            body,
        )
        observed = observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=encrypted_artefact,
        )
        observation = FiledDeclaracionObservation(
            modelo=declaration.modelo,
            ejercicio=declaration.ejercicio,
            period=declaration.period,
            expediente_id=declaration.expediente_id,
            status=declaration.estado,
            presented_at=declaration.presented_at,
            authenticated_identity="00000000T",
            artefacts=(encrypted_artefact,),
            casillas=observed,
            extraction_coverage={"submitted_file": 1.0},
        )
        manifest_path = store.persist_observation(observation)
        loaded = store.load_observation(manifest_path)

        assert loaded == observation
        assert encrypted_artefact.storage_ref is not None
        assert store.load_artefact(encrypted_artefact.storage_ref) == body


class TestDeclaracionPdfObservation:
    """Verify declaration-copy PDFs are interpreted through registry profiles.

    The bbox-anchored extraction path is exercised entirely in memory: the
    decrypted declaration bytes are parsed via ``parse_declaracion_bytes`` and
    never written to a plaintext scratch file
    (sensitive-financial-data-secure-storage-only).
    """

    def test_declaration_pdf_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_130_snapshot()
        profile = snapshot.extraction_profiles["modelo-130-declaracion-pdf"]
        values = {
            target.casilla_id: Decimal(index).quantize(Decimal("0.01"))
            for index, target in enumerate(profile.target_casillas, start=1)
        }
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period=Period.from_year_and_code(2026, "1T"),
            expediente_id="202610013522222A",
            estado="ALTA",
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            declaration_copy_link_text="Ver",
        )

        observed = _observed_casillas_from_declaration_pdf(
            snapshot=snapshot,
            declaration=declaration,
            body=_declaration_pdf_payload(values, profile=profile),
        )

        assert {item.casilla_id: Decimal(item.value) for item in observed} == values

    def test_declaration_pdf_parse_failure_redacts_identifier_and_chained_error(self) -> None:
        snapshot = _modelo_130_snapshot()
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period=Period.from_year_and_code(2026, "1T"),
            expediente_id="20269999CANARY123",
            estado="ALTA",
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            declaration_copy_link_text="Ver",
        )

        with pytest.raises(SedeParseError) as exc_info:
            _observed_casillas_from_declaration_pdf(
                snapshot=snapshot,
                declaration=declaration,
                body=b"not a declaration PDF",
            )

        err = exc_info.value
        assert err.__cause__ is None
        assert err.__context__ is None
        assert "20269999CANARY123" not in str(err)
        assert "20269999CANARY123" not in str(getattr(err, "context", {}))

    def test_modelo_111_declaration_pdf_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_snapshot("111", filing_year=2025, period="1T")
        profile = snapshot.extraction_profiles["modelo-111-declaracion-pdf"]
        values = {
            target.casilla_id: Decimal(index).quantize(Decimal("0.01"))
            for index, target in enumerate(profile.target_casillas, start=1)
        }
        declaration = Declaracion(
            modelo="111",
            ejercicio=2025,
            period=Period.from_year_and_code(2025, "1T"),
            expediente_id="202511113520436S",
            estado="ALTA",
            presented_at=datetime(2025, 7, 21, 20, 15, 9, tzinfo=UTC),
            justificante_link_text="Ver",
            declaration_copy_link_text="Ver",
        )

        observed = _observed_casillas_from_declaration_pdf(
            snapshot=snapshot,
            declaration=declaration,
            body=_declaration_pdf_payload(values, modelo="111", ejercicio=2025, profile=profile),
        )

        assert {item.casilla_id: Decimal(item.value) for item in observed} == values


class TestReadOperationGuard:
    """Verify declaration-reader remote operations are fail-closed."""

    def test_modelo_100_declaration_reader_uses_snapshot_guard(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2025, period="0A")
        policy = _read_guard_policy_from_snapshot(snapshot)

        assert policy.classification == "authenticated_read_surface"
        assert policy.requires_authentication is True
        assert policy.requires_aeat_authorization is True
        assert_declarations_read_http(
            "GET",
            _DECLARATIONS_LISTING_URL,
            policy=policy,
        )
        with pytest.raises(RegistryValidationError, match="remote write method"):
            assert_declarations_read_http(
                "POST",
                _DECLARATIONS_LISTING_URL,
                policy=policy,
            )

    @pytest.mark.parametrize(
        "url",
        (
            f"{_COTEJO_DOCUMENT_URL}?CSV=S3RASL6U73H49Y83",
            _REGISTER_DOWNLOAD_URL,
        ),
    )
    def test_allowed_get_read_surfaces(self, url: str) -> None:
        assert_declarations_read_http("GET", url)

    @pytest.mark.parametrize("action", ("open-cotejo-pdf", "download-filed-data-file"))
    def test_allowed_browser_actions(self, action: str) -> None:
        assert_declarations_read_browser_action(action)

    def test_unclassified_browser_action_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
            assert_declarations_read_browser_action("new-unreviewed-declarations-click")

    def test_register_download_external_host_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
            assert_declarations_read_http(
                "GET",
                f"https://example.test{_DECLARATIONS_LISTING_BASE_PATH}/zkau?dtid=z_test&cmd_0=download",
            )

    def test_non_read_method_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="remote write method"):
            assert_declarations_read_http(
                "POST",
                f"{_COTEJO_DOCUMENT_URL}?CSV=S3RASL6U73H49Y83",
            )

    def test_mutating_action_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="browser action token"):
            assert_declarations_read_browser_action("Presentar declaracion")


class TestFiledObservationBindings:
    """Verify filed observations can supply registry previous-filing bindings."""

    def test_previous_filing_binding_resolves_from_filed_observation(self) -> None:
        snapshot = _modelo_130_snapshot()
        binding = next(
            binding
            for binding in snapshot.revision.bindings
            if binding.id == "irpf.previous_year_economic_activity_net_income"
        )
        source_reference = previous_filing_source_reference(binding)
        source_casilla_ids = source_reference.source_casilla_ids
        casilla_values: dict[CasillaId, Decimal] = {
            casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(source_casilla_ids)
        }

        resolved = resolve_previous_filing_bindings_from_filed_declarations(
            snapshot.revision,
            (
                _filed_observation(
                    modelo=source_reference.source_modelo,
                    ejercicio=2025,
                    period=source_reference.required_periods[0],
                    casilla_values=casilla_values,
                ),
            ),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )

        assert resolved == {
            "irpf.previous_year_economic_activity_net_income": sum(casilla_values.values(), Decimal("0")),
        }

    def test_encrypted_filed_observation_roundtrip_supplies_previous_filing_binding(self, tmp_path: Path) -> None:
        snapshot = _modelo_130_snapshot()
        binding = next(
            binding
            for binding in snapshot.revision.bindings
            if binding.id == "irpf.previous_year_economic_activity_net_income"
        )
        source_reference = previous_filing_source_reference(binding)
        source_casilla_ids = source_reference.source_casilla_ids
        casilla_values: dict[CasillaId, Decimal] = {
            casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(source_casilla_ids)
        }
        store = FiledDeclaracionObservationStore(
            tmp_path / "observations",
        )
        observation = _filed_observation(
            modelo=source_reference.source_modelo,
            ejercicio=2025,
            period=source_reference.required_periods[0],
            casilla_values=casilla_values,
        )

        manifest_path = store.persist_observation(observation)
        loaded = store.load_observation(manifest_path)
        resolved = resolve_previous_filing_bindings_from_filed_declarations(
            snapshot.revision,
            (loaded,),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )

        assert resolved == {
            "irpf.previous_year_economic_activity_net_income": sum(casilla_values.values(), Decimal("0")),
        }

    def test_justificante_values_rejected_for_registry_binding_input(self) -> None:
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: Decimal("1")},
            source_artefact_kind="justificante_pdf",
        )

        with pytest.raises(SedeParseError, match="justificante metadata"):
            registry_observation_from_filed_declaration(observation)

    def test_missing_previous_filing_observation_is_unsatisfied_not_refused(self) -> None:
        """Genuine absence resolves the binding to unsatisfied rather than raising.

        AEAT simply never confirmed this filing; that is not the same defect
        as a structurally malformed binding or observation, and the caller
        (a cross-period clean-state gate, or an operator-facing advisory)
        reports the gap rather than the resolver refusing outright.
        """
        snapshot = _modelo_130_snapshot()

        resolved = resolve_previous_filing_bindings_from_filed_declarations(
            snapshot.revision,
            (),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
        )

        assert "irpf.previous_year_economic_activity_net_income" not in resolved

    def test_observation_of_only_non_numeric_casillas_is_rejected(self) -> None:
        """Skipping every casilla leaves no evidence, and that still refuses.

        Non-numeric casillas are skipped rather than fatal, but a return whose
        every casilla was skipped enrolled nothing -- so the existing
        no-observations refusal is what stops an empty record being persisted as
        if it were evidence.
        """
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: "no-decimal"},
        )

        with pytest.raises(SedeParseError, match="no registry casilla observations"):
            registry_observation_from_filed_declaration(observation)

    def test_numeric_casillas_enrol_while_non_numeric_ones_are_skipped(self) -> None:
        """A filing's readable amounts survive casillas this channel cannot carry.

        Refusing the whole return over fields never destined for a Decimal map
        discarded its numeric evidence too. The skipped set is not lost: it is
        enumerated by ``non_numeric_observed_casillas`` for the operator.
        """
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={
                _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: Decimal("1234.56"),
                _M100_CASILLA_0180: "CL SANITIZADA 0000 LOCALIDAD",
            },
        )

        registry_observation = registry_observation_from_filed_declaration(observation)

        values = registry_observation.casilla_values
        assert values == {_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: Decimal("1234.56")}
        assert _M100_CASILLA_0180 not in values
        assert {skip.casilla_id for skip in non_numeric_observed_casillas(observation)} == {_M100_CASILLA_0180}

    def test_contradictory_observed_values_rejected(self) -> None:
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: Decimal("1")},
        ).model_copy(
            update={
                "casillas": (
                    ObservedCasillaValue(
                        casilla_id=_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA,
                        value="1",
                        value_kind=CasillaValueKind.NUMERIC,
                        source_artefact_kind="submitted_file",
                        source_locator="field:0224",
                        confidence=1.0,
                    ),
                    ObservedCasillaValue(
                        casilla_id=_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA,
                        value="2",
                        value_kind=CasillaValueKind.NUMERIC,
                        source_artefact_kind="submitted_file",
                        source_locator="field:0224",
                        confidence=1.0,
                    ),
                ),
            },
        )

        with pytest.raises(SedeParseError, match="contradictory values"):
            registry_observation_from_filed_declaration(observation)

    def test_incomplete_observation_coverage_rejected(self) -> None:
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: Decimal("1")},
            extraction_coverage={"submitted_file": 0.5},
        )

        with pytest.raises(SedeParseError, match="incomplete extraction coverage"):
            registry_observation_from_filed_declaration(observation)
