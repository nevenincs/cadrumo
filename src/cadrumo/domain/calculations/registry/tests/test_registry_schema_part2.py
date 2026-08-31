"""Registry validation of extraction, linking, export and parameter-table schema.

Focused calculation-registry tests split from the original monolith. The
verification-expectation and verification-predicate cases live in
``test_registry_schema_part3``; what remains here is the schema surface those
never shared -- extraction profiles and their parsers, application and
communication links, casilla/export-field agreement, reconciliation totals,
dispatch tables, deadline windows and keyed-bracket parameter tables.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from .....core.period import Period
from .....core.resources.bundled_data import bundled_path
from .._validate import RegistryValidator
from ..errors import RegistryValidationError
from ..schema import ModeloRevision
from ..schema_deadlines import DeadlineWindowDefinition
from ..schema_extraction import ExtractionProfileDefinition, ExtractionTargetDefinition
from ..schema_formula import KeyedBracketEntry, ParameterDefinition
from ..schema_surfaces import CalculationCompletenessCasilla, CalculationCompletenessManifest
from ._registry_schema_support import (
    _NUMERIC_CASILLA_01,
    _as_communication_revision,
    _committed_modelo,
    _committed_registry,
    _keyed_bracket,
    _revision,
    _with_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_revision_accepts_strict_continuidad_validation_with_evolution() -> None:
    revision = ModeloRevision.model_validate(
        {
            "id": "2025",
            "localization_key": "test.schema.revision.2025.label",
            "valid_from": date(2025, 1, 1),
            "period_selector": {"years": (2025,), "periods": ("0A",)},
            "legal_refs": ("ley-35-2006:art-48",),
            "source_refs": ("aeat-manual",),
            "continuidad_validation": "strict",
            "casilla_continuidad_evolutions": (
                {
                    "id": "renta-2024-2025-base-general-label",
                    "continuidad_id": "renta-base-liquidacion-general",
                    "from_revision": "2024",
                    "to_revision": "2025",
                    "evolution_kind": "label_evolved",
                    "legal_refs": ("ley-35-2006:art-48",),
                    "source_refs": ("aeat-manual",),
                },
            ),
        },
    )

    assert revision.continuidad_validation == "strict"
    assert revision.casilla_continuidad_evolutions[0].continuidad_id == "renta-base-liquidacion-general"


def test_extraction_profile_target_casillas_uniqueness_rejects_duplicate_casilla_id() -> None:
    """target_casillas with duplicate casilla_id values raises ValidationError."""
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError):
        ExtractionProfileDefinition(
            id="test.profile",
            surface="declaracion_pdf",
            artefact_kind="declaration_pdf",
            accepted_artefact_kinds=("declaration_pdf",),
            parser="cadrumo.adapters.inbound.declaracion.parse_declaracion",
            target_casillas=(
                ExtractionTargetDefinition(
                    casilla_id=_NUMERIC_CASILLA_01,
                    match_strategy="numeric_casilla",
                    value_kind="amount",
                ),
                ExtractionTargetDefinition(
                    casilla_id=_NUMERIC_CASILLA_01,
                    match_strategy="numeric_casilla",
                    value_kind="amount",
                ),
            ),
            confidence="strict",
            min_coverage=Decimal("1"),
            failure_semantics="fail_hard",
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-dr-130-2019-v12",),
        )


def test_extraction_profile_rejects_zero_minimum_coverage() -> None:
    """An extraction profile must reject a zero-hit coverage floor."""

    with pytest.raises(ValidationError, match="min_coverage"):
        ExtractionProfileDefinition(
            id="test.profile",
            surface="declaracion_pdf",
            artefact_kind="declaration_pdf",
            accepted_artefact_kinds=("declaration_pdf",),
            parser="cadrumo.adapters.inbound.declaracion.parse_declaracion",
            target_casillas=(
                ExtractionTargetDefinition(
                    casilla_id=_NUMERIC_CASILLA_01,
                    match_strategy="numeric_casilla",
                    value_kind="amount",
                ),
            ),
            confidence="strict",
            min_coverage=Decimal("0"),
            failure_semantics="fail_hard",
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-dr-130-2019-v12",),
        )


def test_calculation_completeness_manifest_rejects_duplicate_casilla_id() -> None:
    """A completeness manifest cannot reuse the same canonical casilla id."""

    with pytest.raises(ValidationError, match="duplicate casilla ids"):
        CalculationCompletenessManifest(
            source_ref="aeat-dr-130-2019-v12",
            casillas=(
                CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="01"),
                CalculationCompletenessCasilla(casilla_id=_NUMERIC_CASILLA_01, number="02"),
            ),
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-dr-130-2019-v12",),
        )


def test_validator_rejects_extraction_profile_parser_that_is_not_a_dotted_callable_path() -> None:
    """The domain registry validator checks structural shape only.

    Since the ports-inversion honesty-review fix (commit 034c9e84e6), the domain
    validator no longer names or imports adapter parser modules to confirm a
    ``parser =`` path resolves — that resolution check (allowed-authority prefix,
    importability, callability) moved to the adapter-legal CI gate
    ``cadrumo.adapters.inbound.tests.test_extraction_parser_paths_resolve``, where
    importing ``cadrumo.adapters.inbound`` parsers is legal. What remains at the
    domain layer is a pure structural-shape check: the string must have the
    ``module.attribute`` dotted-callable shape.
    """
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(update={"parser": "not_a_dotted_path"})
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match=r"must be a dotted callable path"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_extraction_profile_without_layout_authority_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    profile = next(item for item in revision.extraction_profiles if item.source_refs)
    sources = dict(catalogues.sources)
    for source_ref in profile.source_refs:
        sources[source_ref] = sources[source_ref].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated_catalogues = catalogues.model_copy(update={"sources": sources})

    with pytest.raises(
        RegistryValidationError,
        match=r"extraction profile .* requires layout_authority source evidence",
    ):
        RegistryValidator(mutated_catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_validator_requires_application_link_for_extraction_profile() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    links = tuple(link for link in revision.application_links if link.surface != "extractor")
    mutated = revision.model_copy(update={"application_links": links})

    with pytest.raises(RegistryValidationError, match="extraction profiles require an extractor application link"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_application_link_for_formulas() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    links = tuple(link for link in revision.application_links if link.surface != "calculation")
    mutated = revision.model_copy(update={"application_links": links})

    with pytest.raises(RegistryValidationError, match="formulas require a calculation application link"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_allows_modelo_145_communication_link_for_non_filing_casillas() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = next(iter(modelo.revisions.values()))
    communication = _as_communication_revision(revision)
    # A pure communication-only modelo does not file declarations and
    # therefore has no PDF-extraction surface; strip extraction_profiles
    # and their corpus-PDF requirements from the mutated revision.
    extractor_link_ids = frozenset(link.id for link in communication.application_links if link.surface == "extractor")
    constructs_without_extractor = tuple(
        construct.model_copy(
            update={
                "extraction_profiles": (),
                "application_links": tuple(
                    link_id for link_id in construct.application_links if link_id not in extractor_link_ids
                ),
            },
        )
        for construct in communication.constructs
    )
    mutated = communication.model_copy(
        update={
            "constructs": constructs_without_extractor,
            "extraction_profiles": (),
            "application_links": tuple(link for link in communication.application_links if link.surface != "extractor"),
        },
    )
    modelo_145 = modelo.model_copy(update={"id": "145"})

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo_145, mutated))


def test_validator_rejects_non_145_communication_link_for_casillas() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = _as_communication_revision(next(iter(modelo.revisions.values())))

    with pytest.raises(RegistryValidationError, match="communication application links are only valid for Modelo 145"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, revision))


def test_validator_rejects_communication_link_combined_with_filing() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = next(iter(modelo.revisions.values()))
    filing_link = next(link for link in revision.application_links if link.surface == "filing")
    communication_link = filing_link.model_copy(
        update={"id": f"{filing_link.id}-communication", "surface": "communication"},
    )
    mutated = revision.model_copy(update={"application_links": (*revision.application_links, communication_link)})

    with pytest.raises(
        RegistryValidationError,
        match="communication application links must not be combined with filing",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_modelo_145_without_communication_link() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = next(iter(modelo.revisions.values()))
    modelo_145 = modelo.model_copy(update={"id": "145"})

    with pytest.raises(RegistryValidationError, match="Modelo 145 requires a communication application link"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo_145, revision))


def test_validator_rejects_communication_link_with_deadline_surface() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = _as_communication_revision(next(iter(modelo.revisions.values())))
    workflow_link = next(link for link in revision.application_links if link.surface == "workflow")
    deadline_link = workflow_link.model_copy(update={"id": f"{workflow_link.id}-deadline", "surface": "deadline"})
    mutated = revision.model_copy(update={"application_links": (*revision.application_links, deadline_link)})

    with pytest.raises(RegistryValidationError, match="communication application links must not declare deadline"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_communication_link_with_portal_surface() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = _as_communication_revision(next(iter(modelo.revisions.values())))
    workflow_link = next(link for link in revision.application_links if link.surface == "workflow")
    portal_link = workflow_link.model_copy(update={"id": f"{workflow_link.id}-portal", "surface": "portal"})
    mutated = revision.model_copy(update={"application_links": (*revision.application_links, portal_link)})

    with pytest.raises(
        RegistryValidationError,
        match="communication application links must not declare live or portal",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_communication_link_with_filing_schedule() -> None:
    modelo, catalogues = _committed_modelo("036")
    revision = next(iter(modelo.revisions.values()))
    filing_link = next(link for link in revision.application_links if link.surface == "filing")
    communication_link = filing_link.model_copy(
        update={
            "id": f"{filing_link.id}-communication",
            "surface": "communication",
            "consumer": "cadrumo.application.modelo",
        },
    )
    application_links = tuple(
        communication_link if link.id == filing_link.id else link
        for link in revision.application_links
        if link.id == filing_link.id or link.surface != "filing"
    )
    constructs = tuple(
        construct.model_copy(
            update={
                "application_links": tuple(
                    communication_link.id if link_id == filing_link.id else link_id
                    for link_id in construct.application_links
                ),
            },
        )
        for construct in revision.constructs
    )
    mutated = revision.model_copy(update={"application_links": application_links, "constructs": constructs})

    with pytest.raises(
        RegistryValidationError,
        match="communication application links must not declare filing schedules",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_application_link_legal_ref_without_legal_authority() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    link = next(item for item in revision.application_links if item.legal_refs)
    legal = dict(catalogues.legal)
    legal_ref = link.legal_refs[0]
    legal[legal_ref] = legal[legal_ref].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated_catalogues = catalogues.model_copy(update={"legal": legal})

    with pytest.raises(
        RegistryValidationError,
        match=r"application link .* legal ref .* is not legal authority",
    ):
        RegistryValidator(mutated_catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_validator_rejects_application_link_without_required_official_guidance_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    link = next(item for item in revision.application_links if item.id == "modelo-130-calculation")
    mutated_link = link.model_copy(update={"source_refs": ("aeat-dr-130-2019-v12",)})
    mutated = revision.model_copy(
        update={
            "application_links": tuple(
                mutated_link if item.id == link.id else item for item in revision.application_links
            ),
        },
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"application link modelo-130-calculation requires official_source_guidance source evidence",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_export_application_link_without_layout_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    link = next(item for item in revision.application_links if item.id == "modelo-130-export")
    mutated_link = link.model_copy(update={"source_refs": ("aeat-modelo-130-instructions",)})
    mutated = revision.model_copy(
        update={
            "application_links": tuple(
                mutated_link if item.id == link.id else item for item in revision.application_links
            ),
        },
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"application link modelo-130-export requires layout_authority source evidence",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_casilla_export_ref_without_export_field() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    target = next(casilla for casilla in revision.casillas if casilla.export_refs)
    casillas = tuple(
        casilla.model_copy(update={"export_refs": (*casilla.export_refs, "missing-export-field")})
        if casilla.id == target.id
        else casilla
        for casilla in revision.casillas
    )
    mutated = revision.model_copy(update={"casillas": casillas})

    with pytest.raises(RegistryValidationError, match="references unknown export field"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_export_field_not_declared_by_casilla() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    exported = next(
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla_id is not None
    )
    casillas = tuple(
        casilla.model_copy(update={"export_refs": tuple(ref for ref in casilla.export_refs if ref != exported.id)})
        if casilla.id == exported.casilla_id
        else casilla
        for casilla in revision.casillas
    )
    mutated = revision.model_copy(update={"casillas": casillas})

    with pytest.raises(RegistryValidationError, match="is not declared by casilla"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_export_field_without_layout_authority_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    target_layout = next(
        layout for layout in revision.export_layouts if any(record.fields for record in layout.records)
    )
    target_field = next(field for record in target_layout.records for field in record.fields)
    export_layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={
                            "fields": tuple(
                                field.model_copy(update={"source_refs": ("aeat-modelo-130-instructions",)})
                                if field.id == target_field.id
                                else field
                                for field in record.fields
                            ),
                        },
                    )
                    for record in layout.records
                ),
            },
        )
        if layout.id == target_layout.id
        else layout
        for layout in revision.export_layouts
    )
    mutated = revision.model_copy(update={"export_layouts": export_layouts})

    with pytest.raises(RegistryValidationError, match="requires layout_authority source evidence"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_submitted_file_profile_without_exported_casilla() -> None:
    modelo, catalogues = _committed_modelo("131")
    revision = modelo.revisions["2026"]
    profile = next(item for item in revision.extraction_profiles if item.surface == "export_record")
    target = profile.target_casillas[0].casilla_id
    removed_export_fields = {
        field.id
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla_id == target
    }
    export_layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={"fields": tuple(field for field in record.fields if field.casilla_id != target)},
                    )
                    for record in layout.records
                ),
            },
        )
        for layout in revision.export_layouts
    )
    casillas = tuple(
        casilla.model_copy(
            update={"export_refs": tuple(ref for ref in casilla.export_refs if ref not in removed_export_fields)},
        )
        if casilla.id == target
        else casilla
        for casilla in revision.casillas
    )
    mutated = revision.model_copy(update={"casillas": casillas, "export_layouts": export_layouts})

    with pytest.raises(RegistryValidationError, match="targets casillas without export fields"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_reconciliation_total_unknown_casilla() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    expectation = revision.verification_expectations[0].model_copy(
        update={"reconciliation_total_casilla_ids": {"ingresar": "missing"}},
    )
    mutated = revision.model_copy(update={"verification_expectations": (expectation,)})

    with pytest.raises(RegistryValidationError, match="reconciliation total 'ingresar' references unknown casilla"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_reconciliation_total_to_be_computed() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    expectation = revision.verification_expectations[0].model_copy(
        update={"reconciliation_total_casilla_ids": {"ingresar": "01"}},
    )
    mutated = revision.model_copy(update={"verification_expectations": (expectation,)})

    with pytest.raises(
        RegistryValidationError,
        match="reconciliation total 'ingresar' must be one of computed_casilla_ids",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def _corrupt_first_ccaa_dispatch(expression: object, bad_parameter: str) -> tuple[object, bool]:
    """Return a copy of *expression* with the first lookup_bracket_by_ccaa's
    dispatch_table pointing 'madrid' at *bad_parameter*.

    From the 2024/2025 M100 revisions the autonomic escala formula wraps its
    lookup_bracket_by_ccaa operators in the LIRPF art. 64/75 separate-escala
    if_then_else predicate, so the dispatch leaf is no longer at the top
    level; the tree is walked to corrupt the first reachable dispatch table.
    """
    if getattr(expression, "op", None) == "lookup_bracket_by_ccaa":
        expr: Any = expression
        leaf = expr.args[2]
        mutated_dispatch = {**leaf.dispatch_table, "madrid": bad_parameter}
        mutated_leaf = leaf.model_copy(update={"dispatch_table": mutated_dispatch})
        mutated_args = (expr.args[0], expr.args[1], mutated_leaf)
        return expr.model_copy(update={"args": mutated_args}), True
    new_args = []
    changed = False
    for arg in getattr(expression, "args", ()) or ():
        if not changed:
            new_arg, did = _corrupt_first_ccaa_dispatch(arg, bad_parameter)
            new_args.append(new_arg)
            changed = changed or did
        else:
            new_args.append(arg)
    if changed:
        expr_copy: Any = expression
        return expr_copy.model_copy(update={"args": tuple(new_args)}), True
    return expression, False


def test_validator_rejects_dispatch_table_referencing_unknown_parameter() -> None:
    """The lookup_bracket_by_ccaa dispatch_table leaf must resolve every value
    to a declared parameter; otherwise the registry would only fault at runtime."""
    modelo, catalogues = _committed_modelo("100")
    revision = modelo.revisions["2025"]
    formula = next(item for item in revision.formulas if item.target_casilla_id == "0529")
    mutated_expression, corrupted = _corrupt_first_ccaa_dispatch(
        formula.expression,
        "renta-2025-not-a-declared-parameter",
    )
    assert corrupted, "fixture must expose a dispatch_table leaf"

    mutated_formula = formula.model_copy(update={"expression": mutated_expression})
    mutated_formulas = tuple(mutated_formula if item.id == formula.id else item for item in revision.formulas)
    mutated_revision = revision.model_copy(update={"formulas": mutated_formulas})

    with pytest.raises(
        RegistryValidationError,
        match=r"dispatch_table\['madrid'\] references unknown parameter "
        r"'renta-2025-not-a-declared-parameter'",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, mutated_revision),
        )


def test_deadline_window_any_mode_requires_conditions() -> None:
    modelo, _catalogues = _committed_registry()
    revision = _revision(modelo)
    window = revision.deadline_windows[0]
    payload = window.model_dump()
    payload.update(
        {
            "applicability_condition_mode": "any",
            "applicability_conditions": (),
        },
    )

    with pytest.raises(ValueError, match="any-mode requires applicability conditions"):
        type(window).model_validate(payload)


def test_deadline_window_accepts_current_display_periods_at_schema_boundary() -> None:
    cases = (
        ("2026 1T", "1T"),
        ("2026 0A", "0A"),
        ("2026 03", "03"),
        ("2026 1P", "1P"),
        ("2026 EXT-1T", "EXT-1T"),
    )
    for authored_period, expected_code in cases:
        window = DeadlineWindowDefinition.model_validate(
            {
                "id": f"test-window-{authored_period.lower().replace(' ', '-')}",
                "filing_year": 2026,
                "period": authored_period,
                "period_kind": "quarterly",
                "opens_on": date(2026, 4, 1),
                "closes_on": date(2026, 4, 20),
                "legal_refs": ("test-law:art-1",),
                "source_refs": ("test-source",),
            },
        )

        expected_period = Period.from_year_and_code(2026, expected_code)
        assert window.period == expected_period
        assert window.model_dump()["period"] == {"filing_year": 2026, "code": expected_code}
        assert window.model_dump(mode="json")["period"] == {"filing_year": 2026, "code": expected_code}
        assert '"period":"2026' not in window.model_dump_json()
        assert DeadlineWindowDefinition.model_validate(window.model_dump()).period == expected_period


def test_deadline_window_rejects_combined_period_shapes() -> None:
    for combined_period in ("2026Q1", "2026-1T", "2026-0A", "2026-03", "2026"):
        with pytest.raises(ValueError, match="expected 'YYYY <period-code>'"):
            DeadlineWindowDefinition.model_validate(
                {
                    "id": f"test-window-{combined_period.lower()}",
                    "filing_year": 2026,
                    "period": combined_period,
                    "period_kind": "quarterly",
                    "opens_on": date(2026, 4, 1),
                    "closes_on": date(2026, 4, 20),
                    "legal_refs": ("test-law:art-1",),
                    "source_refs": ("test-source",),
                },
            )


def test_deadline_window_identity_year_matches_period_despite_following_year_dates() -> None:
    payload = {
        "id": "test-following-january-window",
        "filing_year": 2024,
        "period": "2024 0A",
        "period_kind": "annual",
        "opens_on": date(2025, 1, 1),
        "closes_on": date(2025, 1, 31),
        "legal_refs": ("test-law:art-1",),
        "source_refs": ("test-source",),
    }

    window = DeadlineWindowDefinition.model_validate(payload)
    assert window.filing_year == window.period.filing_year == 2024
    assert window.closes_on.year == 2025

    with pytest.raises(ValueError, match=r"filing_year 2025 must match period filing_year 2024"):
        DeadlineWindowDefinition.model_validate({**payload, "filing_year": 2025})


def test_keyed_bracket_table_parses_with_distinct_keys() -> None:
    """A keyed_bracket_table with two distinct keys parses cleanly."""
    parameter = ParameterDefinition(
        id="test-keyed-rate-table",
        data_type="keyed_bracket_table",
        unit="percent",
        keyed_brackets=(
            _keyed_bracket("general", "0.24"),
            _keyed_bracket("ue_residente", "0.19"),
        ),
        legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
        source_refs=("aeat-modelo-210-procedure",),
    )

    assert parameter.data_type == "keyed_bracket_table"
    assert len(parameter.keyed_brackets) == 2
    assert parameter.keyed_brackets[0].key == "general"
    assert parameter.keyed_brackets[0].value == Decimal("0.24")
    assert parameter.keyed_brackets[1].key == "ue_residente"
    assert parameter.keyed_brackets[1].value == Decimal("0.19")


def test_keyed_bracket_table_rejects_duplicate_key_within_same_window() -> None:
    """A keyed_bracket_table with two rows sharing (key, valid_from) is rejected.

    Anti-tautology: the duplicate fixture deliberately reuses the
    SAME ``key`` AND the SAME ``valid_from`` across two rows with
    different values. If the validator silently dedup'd or kept the
    first row, the test would pass without surfacing the contract
    violation. The expected outcome is RegistryValidationError —
    the (key, valid_from) pair must be unique because the runtime
    lookup is exact-match and a duplicate would make the result
    non-deterministic.
    """
    # Pydantic wraps the inner RegistryValidationError raised from
    # @model_validator(mode="after") into its ValidationError because
    # RegistryValidationError does not extend ValueError. The substring
    # match still asserts the inner message text reaches the surface.
    with pytest.raises(ValidationError, match="duplicate"):
        ParameterDefinition(
            id="test-keyed-rate-table-duplicate",
            data_type="keyed_bracket_table",
            unit="percent",
            keyed_brackets=(
                _keyed_bracket("general", "0.24"),
                _keyed_bracket("general", "0.30"),
            ),
            legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
            source_refs=("aeat-modelo-210-procedure",),
        )


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param(
            (
                KeyedBracketEntry(
                    key="general",
                    value=Decimal("0.24"),
                    valid_from=date(2020, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
                KeyedBracketEntry(
                    key="general",
                    value=Decimal("0.30"),
                    valid_from=date(2023, 1, 1),
                    valid_to=date(2024, 12, 31),
                ),
            ),
            id="wide-then-narrow",
        ),
        pytest.param(
            (
                KeyedBracketEntry(
                    key="general",
                    value=Decimal("0.30"),
                    valid_from=date(2023, 1, 1),
                    valid_to=date(2024, 12, 31),
                ),
                KeyedBracketEntry(
                    key="general",
                    value=Decimal("0.24"),
                    valid_from=date(2020, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
            ),
            id="narrow-then-wide",
        ),
    ],
)
def test_keyed_bracket_table_rejects_overlapping_windows_in_either_order(
    rows: tuple[KeyedBracketEntry, KeyedBracketEntry],
) -> None:
    """One key cannot select two simultaneous rates, regardless of row order."""
    with pytest.raises(ValidationError, match="overlapping validity windows"):
        ParameterDefinition(
            id="test-keyed-rate-table-overlap",
            data_type="keyed_bracket_table",
            unit="percent",
            keyed_brackets=rows,
            legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
            source_refs=("aeat-modelo-210-procedure",),
        )


def test_keyed_bracket_table_allows_disjoint_windows_for_the_same_key() -> None:
    """Annual replacement rows for the same categorical key remain valid."""
    parameter = ParameterDefinition(
        id="test-keyed-rate-table-disjoint",
        data_type="keyed_bracket_table",
        unit="percent",
        keyed_brackets=(
            KeyedBracketEntry(
                key="general",
                value=Decimal("0.24"),
                valid_from=date(2024, 1, 1),
                valid_to=date(2024, 12, 31),
            ),
            KeyedBracketEntry(
                key="general",
                value=Decimal("0.30"),
                valid_from=date(2025, 1, 1),
                valid_to=date(2025, 12, 31),
            ),
        ),
        legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
        source_refs=("aeat-modelo-210-procedure",),
    )

    assert len(parameter.keyed_brackets) == 2


def test_keyed_bracket_table_rejects_mixed_brackets_and_keyed_brackets() -> None:
    """A keyed_bracket_table parameter cannot also carry numeric brackets.

    The two shapes are mutually exclusive by design — a parameter
    is either numeric-interval (``bracket_table``) or enum-keyed
    (``keyed_bracket_table``), never both. Mixing produces an
    ambiguous lookup contract; the validator rejects it at
    construction time.
    """
    from ..schema_formula import BracketEntry as _BracketEntry

    numeric_bracket = _BracketEntry(
        lower_bound=Decimal("0"),
        upper_bound=Decimal("12450"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.19"),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    with pytest.raises(ValidationError, match="cannot mix"):
        ParameterDefinition(
            id="test-keyed-rate-table-mixed",
            data_type="keyed_bracket_table",
            unit="percent",
            brackets=(numeric_bracket,),
            keyed_brackets=(_keyed_bracket("general", "0.24"),),
            legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
            source_refs=("aeat-modelo-210-procedure",),
        )
