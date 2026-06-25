"""Focused calculation-registry tests split from the original monolith."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core import Period
from .....core.resources import bundled_path
from .._errors import RegistryValidationError
from .._schema import (
    ConvenioRateRow,
    DeadlineWindowDefinition,
    ExtractionProfileDefinition,
    ExtractionTargetDefinition,
    ModeloRevision,
    ParameterDefinition,
    VerificationPredicateDefinition,
)
from .._validate import RegistryValidator
from ._registry_schema_support import (
    _as_communication_revision,
    _committed_modelo,
    _committed_registry,
    _convenio_row,
    _keyed_bracket,
    _revision,
    _with_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_revision_accepts_strict_continuidad_validation_with_evolution() -> None:
    revision = ModeloRevision.model_validate(
        {
            "id": "2025",
            "valid_from": date(2025, 1, 1),
            "period_selector": {"years": (2025,), "periods": ("0A",)},
            "legal_refs": ("ley-35-2006:art-48",),
            "source_refs": ("aeat-manual",),
            "continuidad_validation": "strict",
            "casilla_continuidad_evolutions": (
                {
                    "id": "renta-2024-2025-base-general-label",
                    "continuidad_id": "renta.base-liquidacion.general",
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
    assert revision.casilla_continuidad_evolutions[0].continuidad_id == "renta.base-liquidacion.general"


def test_extraction_profile_target_casillas_uniqueness_rejects_duplicate_casilla_id() -> None:
    """target_casillas with duplicate casilla_id values raises ValidationError."""
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError):
        ExtractionProfileDefinition(
            id="test.profile",
            surface="declaracion_pdf",
            artefact_kind="declaration_pdf",
            accepted_artefact_kinds=("declaration_pdf",),
            parser="aeat.adapters.inbound.declaracion.parse_declaracion",
            target_casillas=(
                ExtractionTargetDefinition(
                    casilla_id="01",
                    match_strategy="numeric_casilla",
                    value_kind="amount",
                ),
                ExtractionTargetDefinition(
                    casilla_id="01",
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


def test_validator_rejects_extraction_profile_parser_that_does_not_resolve() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    profile = revision.extraction_profiles[0].model_copy(update={"parser": "aeat.missing_registry_parser"})
    mutated = revision.model_copy(update={"extraction_profiles": (profile,)})

    with pytest.raises(RegistryValidationError, match=r"must resolve under one of .*aeat.adapters.inbound.declaracion"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


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


def test_validator_rejects_verification_predicate_with_unknown_operator() -> None:
    """Predicate with an unknown DSL operator must fail at registry-load.

    The runtime DSL evaluator falls through to ``return True`` for any
    unrecognised expression — silent-pass is the documented behaviour
    so unknown DSL extensions don't block. That same behaviour means
    a typo like ``cap_lt_when_positive`` for ``cap_le_when_positive``
    silently passes the predicate gate and the cap rule is lost
    without diagnostic.

    The predicate hardening rejects unknown operators at registry-load
    time. The known set is enumerated in
    ``_validate_surfaces._KNOWN_VERIFICATION_PREDICATE_OPERATORS``:
    ``all_nonzero``, ``any_nonzero``, ``cap_le_when_positive``.
    Typos are caught before any calculation runs.
    """

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    typo_predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-typo-predicate",
        legal_refs=("rd-439-2007:art-110",),
        expression='cap_lt_when_positive(["15", "14"])',  # typo: lt instead of le
        finding_kind="BLOCKING_RULE",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, typo_predicate)},
    )

    with pytest.raises(RegistryValidationError, match="unknown operator 'cap_lt_when_positive'"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_roll_forward_balances_with_wrong_arity() -> None:
    """A roll_forward_balances predicate must name exactly four casilla ids.

    The runtime evaluator's bad-arity branch returns None → treated as holding
    (BLOCKING) / never firing (ADVISORY), so a malformed continuity predicate
    would silently do nothing. The authoring-time validator rejects it at
    registry load. Uses existing M130 casillas (01/02/03) so the failure is the
    arity, not an unknown-casilla reference.
    """

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    bad_arity = VerificationPredicateDefinition(
        predicate_id="modelo-130-bad-roll-forward",
        legal_refs=("rd-439-2007:art-110",),
        expression='roll_forward_balances(["01", "02", "03"])',  # three ids; needs four
        finding_kind="ADVISORY",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, bad_arity)},
    )

    with pytest.raises(RegistryValidationError, match="must name exactly four casilla ids"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_verification_predicate_with_malformed_expression() -> None:
    """Predicate whose expression is not a parseable DSL call fails."""

    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    malformed_predicate = VerificationPredicateDefinition(
        predicate_id="modelo-130-malformed-predicate",
        legal_refs=("rd-439-2007:art-110",),
        expression="just a string with no call shape",
        finding_kind="BLOCKING_RULE",
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, malformed_predicate)},
    )

    with pytest.raises(RegistryValidationError, match="not a recognised DSL call"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_accepts_known_verification_predicate_operators() -> None:
    """The cap_le_when_positive predicate declared by the registry must pass.

    Pins that the committed M130 cap predicate
    (modelo-130-c15-cap-by-c14, expression
    cap_le_when_positive(["15", "14"])) validates cleanly. A
    future operator-set reduction that drops cap_le_when_positive
    from the known set would surface here, not at runtime.
    """

    modelo, catalogues = _committed_modelo("130")
    # No mutation — committed M130 carries the predicate.
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


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
            "consumer": "aeat.application.modelo",
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
        if field.casilla is not None
    )
    casillas = tuple(
        casilla.model_copy(update={"export_refs": tuple(ref for ref in casilla.export_refs if ref != exported.id)})
        if casilla.id == exported.casilla
        else casilla
        for casilla in revision.casillas
    )
    mutated = revision.model_copy(update={"casillas": casillas})

    with pytest.raises(RegistryValidationError, match="is not declared by casilla"):
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
        if field.casilla == target
    }
    export_layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={"fields": tuple(field for field in record.fields if field.casilla != target)},
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
        update={"reconciliation_totals": {"ingresar": "missing"}},
    )
    mutated = revision.model_copy(update={"verification_expectations": (expectation,)})

    with pytest.raises(RegistryValidationError, match="reconciliation total 'ingresar' references unknown casilla"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_requires_reconciliation_total_to_be_computed() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    expectation = revision.verification_expectations[0].model_copy(update={"reconciliation_totals": {"ingresar": "01"}})
    mutated = revision.model_copy(update={"verification_expectations": (expectation,)})

    with pytest.raises(
        RegistryValidationError,
        match="reconciliation total 'ingresar' must be one of computed_casillas",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(_with_revision(modelo, mutated))


def test_validator_rejects_dispatch_table_referencing_unknown_parameter() -> None:
    """The lookup_bracket_by_ccaa dispatch_table leaf must resolve every value
    to a declared parameter; otherwise the registry would only fault at runtime."""
    modelo, catalogues = _committed_modelo("100")
    revision = modelo.revisions["2025"]
    formula = next(item for item in revision.formulas if item.target == "0529")
    dispatch_leaf = formula.expression.args[2]
    assert dispatch_leaf.dispatch_table is not None, "fixture must expose a dispatch_table leaf"

    mutated_dispatch = {**dispatch_leaf.dispatch_table, "madrid": "renta-2025-not-a-declared-parameter"}
    mutated_leaf = dispatch_leaf.model_copy(update={"dispatch_table": mutated_dispatch})
    mutated_args = (formula.expression.args[0], formula.expression.args[1], mutated_leaf)
    mutated_expression = formula.expression.model_copy(update={"args": mutated_args})
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


@pytest.mark.parametrize(
    ("authored_period", "expected_code"),
    (
        ("2026Q1", "1T"),
        ("2026-1T", "1T"),
        ("2026-0A", "0A"),
        ("2026-03", "03"),
        ("2026-1P", "1P"),
        ("2026-EXT-1T", "EXT-1T"),
        ("2026", "0A"),
    ),
)
def test_deadline_window_hydrates_toml_periods_at_schema_boundary(
    authored_period: str,
    expected_code: str,
) -> None:
    window = DeadlineWindowDefinition.model_validate(
        {
            "id": f"test-window-{authored_period.lower()}",
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


def test_keyed_bracket_table_rejects_mixed_brackets_and_keyed_brackets() -> None:
    """A keyed_bracket_table parameter cannot also carry numeric brackets.

    The two shapes are mutually exclusive by design — a parameter
    is either numeric-interval (``bracket_table``) or enum-keyed
    (``keyed_bracket_table``), never both. Mixing produces an
    ambiguous lookup contract; the validator rejects it at
    construction time.
    """
    from .._schema import BracketEntry as _BracketEntry

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


def test_convenio_rate_table_parses_with_mixed_decimal_and_not_yet_authored() -> None:
    """A convenio_rate_table accepts both parseable Decimal rates and NOT_YET_AUTHORED.

    Anti-tautology: the fixture mixes a concrete 0.10 row with a
    NOT_YET_AUTHORED row so the assertion proves both pathways
    persist their declared ``rate`` field literally — i.e. the
    sentinel is not coerced to None or to a Decimal, and the
    concrete Decimal row is not coerced to the sentinel.
    """
    parameter = ParameterDefinition(
        id="test-convenio-rates",
        data_type="convenio_rate_table",
        unit="ratio",
        convenio_rates=(
            _convenio_row("MA", "interest", "0.10", legal_ref_anchor="convenio-es-ma-art-14"),
            _convenio_row("AR", "pension", "NOT_YET_AUTHORED", legal_ref_anchor="convenio-es-ar-pending"),
        ),
        legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
        source_refs=("aeat-modelo-210-procedure",),
    )

    assert parameter.data_type == "convenio_rate_table"
    assert len(parameter.convenio_rates) == 2
    assert parameter.convenio_rates[0].country_code == "MA"
    assert parameter.convenio_rates[0].tipo_renta == "interest"
    assert parameter.convenio_rates[0].rate == "0.10"
    assert parameter.convenio_rates[1].country_code == "AR"
    assert parameter.convenio_rates[1].tipo_renta == "pension"
    assert parameter.convenio_rates[1].rate == "NOT_YET_AUTHORED"


def test_convenio_rate_table_rejects_duplicate_triple() -> None:
    """A convenio_rate_table with two rows sharing (country, tipo_renta, valid_from) is rejected.

    Anti-tautology: the duplicate fixture deliberately reuses the same
    ``(country_code, tipo_renta, valid_from)`` triple across two rows
    with DIFFERENT ``rate`` values. If the validator silently dedup'd
    or kept the first row, the test would pass without surfacing the
    contract violation. The expected outcome is RegistryValidationError
    wrapped in ValidationError because pydantic catches it from the
    after-validator.
    """
    with pytest.raises(ValidationError, match="duplicate"):
        ParameterDefinition(
            id="test-convenio-rates-duplicate",
            data_type="convenio_rate_table",
            unit="ratio",
            convenio_rates=(
                _convenio_row("MA", "interest", "0.10"),
                _convenio_row("MA", "interest", "0.15"),
            ),
            legal_refs=("trlirnr-rdleg-5-2004:art-25.1.a",),
            source_refs=("aeat-modelo-210-procedure",),
        )


def test_convenio_rate_table_rejects_malformed_rate_string() -> None:
    """A ConvenioRateRow with a rate field that is neither a Decimal nor the sentinel is rejected.

    Anti-tautology: the fixture uses a clearly-malformed rate
    (``"not-a-rate"``) that cannot parse as Decimal AND is not the
    NOT_YET_AUTHORED literal. If the row-level validator silently
    accepted any string the test would pass without surfacing the
    parse failure. The expected outcome is ValidationError wrapping
    the row's RegistryValidationError raised from
    ``_validate_convenio_rate_row``.
    """
    with pytest.raises(ValidationError, match="parseable Decimal"):
        ConvenioRateRow(
            country_code="MA",
            tipo_renta="interest",
            rate="not-a-rate",
            legal_ref_anchor="convenio-es-ma-art-14",
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
        )
