"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from .._declarations_observations import _submitted_file_coverage_for_casillas
from ._declarations_support import (
    _COTEJO_DOCUMENT_URL,
    _DECLARATIONS_LISTING_BASE_PATH,
    _DECLARATIONS_LISTING_URL,
    _MODELO_130_COMPUTED_CASILLAS,
    _REGISTER_DOWNLOAD_URL,
    _SUBMITTED_FILE_100_2023_0A,
    _SUBMITTED_FILE_111_2025_1T,
    UTC,
    AnyHttpUrl,
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
    _assert_read_browser_action,
    _assert_read_http,
    _declaration_pdf_payload,
    _exported_modelo_123_payload,
    _filed_observation,
    _modelo_130_snapshot,
    _modelo_snapshot,
    _observed_casillas_from_declaration_pdf,
    _observed_casillas_from_submitted_file,
    _read_guard_policy_from_snapshot,
    _submitted_file_payload,
    _temporary_sensitive_pdf_path,
    calculate_registry_snapshot,
    date,
    datetime,
    hashlib,
    os,
    parse_export_payload,
    registry_observation_from_filed_declaration,
    resolve_export_layout,
    resolve_previous_filing_bindings_from_filed_declarations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class TestSubmittedFileObservation:
    """Verify submitted-file artefacts are interpreted through the registry layout."""

    def test_redacted_submitted_file_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_130_snapshot()
        body = _submitted_file_payload()
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period="1T",
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

        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )

        assert {item.casilla_id: Decimal(item.value) for item in observed} == {
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
        }

    def test_modelo_130_redacted_submitted_file_matches_registry_calculation(self) -> None:
        snapshot = _modelo_130_snapshot()
        body = _submitted_file_payload()
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period="1T",
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
        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observed_values = {item.casilla_id: Decimal(item.value) for item in observed}
        # Casilla 15 (resultados-negativos-anteriores) is a previous-filing
        # bound registry casilla; it must route through binding_values keyed
        # by the binding id, not through inputs. The _formula_runtime smuggle
        # guard refuses inputs["15"] without a matching binding entry.
        carry_forward_value = observed_values.get("15", Decimal("0"))
        input_values = {
            casilla.id: observed_values[casilla.id]
            for casilla in snapshot.revision.casillas
            if casilla.input_kind != InputKind.COMPUTED and casilla.id != "15"
        }
        binding = next(
            item for item in snapshot.revision.bindings if item.id == "irpf.previous_year_economic_activity_net_income"
        )
        selector = binding.selector
        source_casillas = selector["source_casillas"]
        assert isinstance(source_casillas, tuple)
        previous_year_values = {
            str(casilla_id): value
            for casilla_id, value in zip(
                source_casillas,
                (Decimal("3000"), Decimal("4000"), Decimal("2000"), Decimal("4000")),
                strict=True,
            )
        }
        binding_values = resolve_previous_filing_bindings_from_filed_declarations(
            snapshot.revision,
            (
                _filed_observation(
                    modelo=str(selector["source_modelo"]),
                    ejercicio=2025,
                    period=str(selector["period"]),
                    casilla_values=previous_year_values,
                ),
            ),
            filing_year=2026,
            period="1T",
        )
        binding_values["modelo-130-resultados-negativos-anteriores"] = carry_forward_value
        computed_casillas = {
            casilla.id for casilla in snapshot.revision.casillas if casilla.input_kind == InputKind.COMPUTED
        }
        assert computed_casillas == _MODELO_130_COMPUTED_CASILLAS | {"saldo-negativo-fin-periodo"}

        calculated = calculate_registry_snapshot(
            snapshot,
            inputs=input_values,
            date_context={"filing_period": date(2026, 3, 31)},
            binding_values=binding_values,
        )

        assert {casilla_id: calculated.values[casilla_id] for casilla_id in _MODELO_130_COMPUTED_CASILLAS} == {
            casilla_id: observed_values[casilla_id] for casilla_id in _MODELO_130_COMPUTED_CASILLAS
        }
        assert calculated.values["saldo-negativo-fin-periodo"] == Decimal("0.00")

    def test_submitted_file_coverage_scores_fully_extracted_modelo_130_filing(self) -> None:
        # The extracted coverage helper resolves the export layout and scores the
        # observed casillas against the registry-expected set. The M130 redacted
        # submitted file yields every expected result casilla, so coverage is 1.0.
        snapshot = _modelo_130_snapshot()
        body = _submitted_file_payload()
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period="1T",
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
        casillas = _observed_casillas_from_submitted_file(
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
            period="1T",
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

        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observed_values = {item.casilla_id: Decimal(item.value) for item in observed}
        calculated = calculate_registry_snapshot(
            snapshot,
            inputs={
                casilla_id: value for casilla_id, value in observed_values.items() if casilla_id not in {"28", "30"}
            },
            date_context={},
        )
        parsed = parse_export_payload(resolve_export_layout(snapshot).layout, body)
        parsed_fields = {field.field_id: field.value for field in parsed.fields}

        assert set(observed_values) == {t.casilla_id for t in profile.target_casillas}
        assert parsed_fields["modelo-111-tax-id"] == "Y0000001S"
        assert parsed_fields["modelo-111-surnames"] == "SANITIZED SURNAME"
        assert observed_values["28"] == calculated.values["28"]
        assert observed_values["30"] == calculated.values["30"]

    @pytest.mark.parametrize(
        ("filing_year", "period", "profile_id", "expected"),
        (
            (
                2026,
                "1T",
                "modelo-123-export-record",
                {
                    "01": Decimal("2"),
                    "02": Decimal("3"),
                    "03": Decimal("5"),
                    "04": Decimal("1000.25"),
                    "05": Decimal("200.75"),
                    "06": Decimal("1201.00"),
                    "07": Decimal("190.05"),
                    "08": Decimal("38.14"),
                    "09": Decimal("228.19"),
                    "10": Decimal("0.00"),
                    "11": Decimal("7.50"),
                    "12": Decimal("235.69"),
                    "13": Decimal("12.25"),
                    "14": Decimal("223.44"),
                },
            ),
            (
                2023,
                "4T",
                "modelo-123-2019-export-record",
                {
                    "01-legacy": Decimal("5"),
                    "02-legacy": Decimal("1201.00"),
                    "03-legacy": Decimal("228.19"),
                    "04-legacy": Decimal("0.00"),
                    "05-legacy": Decimal("7.50"),
                    "06-legacy": Decimal("235.69"),
                    "07-legacy": Decimal("12.25"),
                    "08-legacy": Decimal("223.44"),
                },
            ),
        ),
    )
    def test_modelo_123_submitted_file_observation_resolves_registry_casillas(
        self,
        tmp_path: Path,
        filing_year: int,
        period: str,
        profile_id: str,
        expected: dict[str, Decimal],
    ) -> None:
        snapshot = _modelo_snapshot("123", filing_year=filing_year, period=period)
        profile = snapshot.extraction_profiles[profile_id]
        body = _exported_modelo_123_payload(tmp_path, filing_year=filing_year, period=period)
        declaration = Declaracion(
            modelo="123",
            ejercicio=filing_year,
            period=period,
            expediente_id=f"{filing_year}12313520436S",
            estado="ALTA",
            presented_at=datetime(filing_year, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
            content_type="application/octet-stream",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 5, 5, 10, 0, 0, tzinfo=UTC),
        )

        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observation = FiledDeclaracionObservation(
            modelo=declaration.modelo,
            ejercicio=declaration.ejercicio,
            period=declaration.period,
            expediente_id=declaration.expediente_id,
            status=declaration.estado,
            presented_at=declaration.presented_at,
            authenticated_identity="12345678Z",
            artefacts=(artefact,),
            casillas=observed,
            extraction_coverage={"submitted_file": 1.0},
        )
        registry_observation = registry_observation_from_filed_declaration(observation)

        assert {item.casilla_id: Decimal(item.value) for item in observed} == expected
        assert set(registry_observation.casilla_values) == {t.casilla_id for t in profile.target_casillas}
        assert registry_observation.casilla_values == expected

    def test_modelo_100_redacted_xml_dictionary_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2023, period="0A")
        body = _submitted_file_payload(_SUBMITTED_FILE_100_2023_0A)
        declaration = Declaracion(
            modelo="100",
            ejercicio=2023,
            period="0A",
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

        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observed_values = {item.casilla_id: item.value for item in observed}
        body_text = body.decode("utf-8")

        assert len(observed) == 77
        assert observed_values["0180"] == "26.26"
        assert observed_values["0224"] == "37.37"
        assert observed_values["0695"] == "87.87"
        assert observed_values["0067"] == "True"
        assert 'nif="Y' not in body_text
        assert 'nif="00000000T"' in body_text
        assert "CL SANITIZADA 0000 LOCALIDAD" in body_text

    def test_modelo_100_redacted_xml_observation_roundtrips_through_encrypted_store(self, tmp_path: Path) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2023, period="0A")
        body = _submitted_file_payload(_SUBMITTED_FILE_100_2023_0A)
        declaration = Declaracion(
            modelo="100",
            ejercicio=2023,
            period="0A",
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
        observed = _observed_casillas_from_submitted_file(
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
    """Verify declaration-copy PDFs are interpreted through registry profiles."""

    def test_sensitive_pdf_temp_path_is_private_and_unlinked(self) -> None:
        body = _declaration_pdf_payload({"03": Decimal("1")})

        with _temporary_sensitive_pdf_path(body) as path:
            captured = path
            assert path.exists()
            assert path.read_bytes() == body
            if os.name == "posix":
                assert path.stat().st_mode & 0o777 == 0o600

        assert not captured.exists()

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
            period="1T",
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
            period="1T",
            expediente_id="EXPEDIENTE-CANARY-123",
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
        assert "EXPEDIENTE-CANARY-123" not in str(err)
        assert "EXPEDIENTE-CANARY-123" not in str(getattr(err, "context", {}))

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
            period="1T",
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
        _assert_read_http(
            "GET",
            _DECLARATIONS_LISTING_URL,
            policy=policy,
        )
        with pytest.raises(RegistryValidationError, match="remote write method"):
            _assert_read_http(
                "POST",
                _DECLARATIONS_LISTING_URL,
                policy=policy,
            )

    def test_cotejo_pdf_get_allowed(self) -> None:
        _assert_read_http(
            "GET",
            f"{_COTEJO_DOCUMENT_URL}?CSV=S3RASL6U73H49Y83",
        )

    def test_declaration_pdf_action_allowed(self) -> None:
        _assert_read_browser_action("open-cotejo-pdf")

    def test_submitted_file_download_action_allowed(self) -> None:
        _assert_read_browser_action("download-filed-data-file")

    def test_unclassified_browser_action_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
            _assert_read_browser_action("new-unreviewed-declarations-click")

    def test_register_download_get_allowed(self) -> None:
        _assert_read_http(
            "GET",
            _REGISTER_DOWNLOAD_URL,
        )

    def test_register_download_external_host_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
            _assert_read_http(
                "GET",
                f"https://example.test{_DECLARATIONS_LISTING_BASE_PATH}/zkau?dtid=z_test&cmd_0=download",
            )

    def test_non_read_method_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="remote write method"):
            _assert_read_http(
                "POST",
                f"{_COTEJO_DOCUMENT_URL}?CSV=S3RASL6U73H49Y83",
            )

    def test_mutating_action_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="browser action token"):
            _assert_read_browser_action("Presentar declaracion")


class TestFiledObservationBindings:
    """Verify filed observations can supply registry previous-filing bindings."""

    def test_previous_filing_binding_resolves_from_filed_observation(self) -> None:
        snapshot = _modelo_130_snapshot()
        selector = next(
            binding.selector
            for binding in snapshot.revision.bindings
            if binding.id == "irpf.previous_year_economic_activity_net_income"
        )
        source_casillas = selector["source_casillas"]
        assert isinstance(source_casillas, tuple)
        casilla_values = {str(casilla_id): Decimal(index + 1) for index, casilla_id in enumerate(source_casillas)}

        resolved = resolve_previous_filing_bindings_from_filed_declarations(
            snapshot.revision,
            (
                _filed_observation(
                    modelo=str(selector["source_modelo"]),
                    ejercicio=2025,
                    period=str(selector["period"]),
                    casilla_values=casilla_values,
                ),
            ),
            filing_year=2026,
            period="1T",
        )

        assert resolved == {
            "irpf.previous_year_economic_activity_net_income": sum(casilla_values.values(), Decimal("0")),
        }

    def test_encrypted_filed_observation_roundtrip_supplies_previous_filing_binding(self, tmp_path: Path) -> None:
        snapshot = _modelo_130_snapshot()
        selector = next(
            binding.selector
            for binding in snapshot.revision.bindings
            if binding.id == "irpf.previous_year_economic_activity_net_income"
        )
        source_casillas = selector["source_casillas"]
        assert isinstance(source_casillas, tuple)
        casilla_values = {str(casilla_id): Decimal(index + 1) for index, casilla_id in enumerate(source_casillas)}
        store = FiledDeclaracionObservationStore(
            tmp_path / "observations",
        )
        observation = _filed_observation(
            modelo=str(selector["source_modelo"]),
            ejercicio=2025,
            period=str(selector["period"]),
            casilla_values=casilla_values,
        )

        manifest_path = store.persist_observation(observation)
        loaded = store.load_observation(manifest_path)
        resolved = resolve_previous_filing_bindings_from_filed_declarations(
            snapshot.revision,
            (loaded,),
            filing_year=2026,
            period="1T",
        )

        assert resolved == {
            "irpf.previous_year_economic_activity_net_income": sum(casilla_values.values(), Decimal("0")),
        }

    def test_justificante_values_rejected_for_registry_binding_input(self) -> None:
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={"0224": Decimal("1")},
            source_artefact_kind="justificante_pdf",
        )

        with pytest.raises(SedeParseError, match="justificante metadata"):
            registry_observation_from_filed_declaration(observation)

    def test_missing_previous_filing_observation_rejected(self) -> None:
        snapshot = _modelo_130_snapshot()

        with pytest.raises(RegistryValidationError, match="expected one observed filing"):
            resolve_previous_filing_bindings_from_filed_declarations(
                snapshot.revision,
                (),
                filing_year=2026,
                period="1T",
            )

    def test_non_decimal_observed_value_rejected(self) -> None:
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={"0224": "no-decimal"},
        )

        with pytest.raises(SedeParseError, match="not decimal-valued"):
            registry_observation_from_filed_declaration(observation)

    def test_contradictory_observed_values_rejected(self) -> None:
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={"0224": Decimal("1")},
        ).model_copy(
            update={
                "casillas": (
                    ObservedCasillaValue(
                        casilla_id="0224",
                        value="1",
                        source_artefact_kind="submitted_file",
                        source_locator="field:0224",
                        confidence=1.0,
                    ),
                    ObservedCasillaValue(
                        casilla_id="0224",
                        value="2",
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
            casilla_values={"0224": Decimal("1")},
            extraction_coverage={"submitted_file": 0.5},
        )

        with pytest.raises(SedeParseError, match="incomplete extraction coverage"):
            registry_observation_from_filed_declaration(observation)
