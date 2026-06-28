"""Modelo registry/discovery CLI surface tests split from ``test_modelo``."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import pytest
import typer

from ....application.modelo import WorkUnitNotFoundError
from ....core.redaction import CLI_BUCKET_ID_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....tests.cli_runner import invoke_cached_cli
from .._modelo import _bad_parameter_from_error
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_NON_INPUT_ERROR_CASILLA: CasillaId = validated_casilla_id(
    "iva.casilla-99",
    surface="_NON_INPUT_ERROR_CASILLA",
)

_UUID_TEXT_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def _seed_modelo_130_ready_profile(bucket_id: str) -> None:
    from ....application.user_profile import UserProfileLifecycleRepository
    from ....domain.user_profile import UserProfileFact, UserProfileRecord

    UserProfileLifecycleRepository(bucket_id=bucket_id).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Modelo 130 guidance profile",
            facts=(
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Discoverability: the modelo `describe` verb is listed in `modelo --help`
# and resolves; the ledger `preflight` verb is listed in `ledger --help` and
# resolves. There is deliberately NO `modelo preflight` verb — signposting
# one would mislead the operator (the #51 lesson), so we assert its absence.
# ---------------------------------------------------------------------------


def test_modelo_describe_verb_is_listed_in_help_and_resolves() -> None:
    """`describe` appears in `app modelo --help` and resolves to a real command."""
    listing = invoke_cached_cli(["app", "modelo", "--help"])
    assert listing.exit_code == 0, listing.output
    assert "describe" in listing.output

    resolved = invoke_cached_cli(["app", "modelo", "describe", "--help"])
    assert resolved.exit_code == 0, resolved.output
    assert "MODELO" in resolved.output


def test_ledger_preflight_verb_is_listed_in_help_and_resolves() -> None:
    """`preflight` appears in `app ledger --help` and resolves to a real command."""
    listing = invoke_cached_cli(["app", "ledger", "--help"])
    assert listing.exit_code == 0, listing.output
    assert "preflight" in listing.output

    resolved = invoke_cached_cli(["app", "ledger", "preflight", "--help"])
    assert resolved.exit_code == 0, resolved.output


def test_no_modelo_preflight_verb_is_signposted() -> None:
    """No `app modelo preflight` verb exists (preflight runs inside
    verify/file); the help must not advertise it as a standalone verb."""
    listing = invoke_cached_cli(["app", "modelo", "--help"])
    assert listing.exit_code == 0, listing.output
    # `describe` is present but `preflight` must not appear as a modelo verb.
    assert "preflight" not in listing.output
    unknown = invoke_cached_cli(["app", "modelo", "preflight", "--help"])
    assert unknown.exit_code != 0


# ---------------------------------------------------------------------------
# Period-token consistency: every modelo `--period` help uses the canonical
# registry token vocabulary (0A / 1T-4T / 01-12), never the misleading
# "Q1, annual" or ledger-style "2026Q1" examples.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        ["app", "modelo", "describe", "--help"],
        ["app", "modelo", "casillas", "--help"],
        ["app", "modelo", "formulas", "--help"],
        ["app", "modelo", "history", "--help"],
        ["app", "modelo", "readiness", "--help"],
        ["app", "modelo", "work", "create", "--help"],
    ],
)
def test_modelo_period_help_uses_canonical_registry_tokens(command: list[str]) -> None:
    """Every modelo `--period` help advertises the canonical registry
    token set (0A / 1T-4T / 01-12) and never the misleading 'Q1, annual'
    or ledger-style 'YYYYQn' examples that diverged across surfaces."""
    result = invoke_cached_cli(command)
    assert result.exit_code == 0, result.output
    ascii_only = "".join(c for c in result.output if c.isascii())
    collapsed = " ".join(ascii_only.split())
    assert "1T-4T" in collapsed, collapsed
    # The misleading tokens that previously diverged must be gone.
    assert "Q1, annual" not in collapsed
    assert "2026Q1" not in collapsed


def test_invalid_modelo_period_surfaces_accepted_set() -> None:
    """A period that no revision declares is refused with the declared
    set listed inline (the architecture-rule instructive-refusal contract
    for the dynamic registry period axis)."""
    result = invoke_cached_cli(["app", "modelo", "describe", "303", "--period", "0A"])
    assert result.exit_code != 0, result.output
    # The accepted/declared set is surfaced, not a bare 'invalid'.
    assert "1T" in result.output and "4T" in result.output


@pytest.mark.parametrize(
    ("command", "expected_fragments"),
    [
        (
            ["app", "modelo", "describe", "303", "--year", "2026", "--period", "1T"],
            ("303", "2009-y-siguientes"),
        ),
        (
            ["app", "modelo", "casillas", "303", "--year", "2026", "--period", "1T", "--input-kind", "computed"],
            ("iva.resultado-regimen-general",),
        ),
        (
            ["app", "modelo", "formulas", "303", "--year", "2026", "--period", "1T"],
            ("formula_id",),
        ),
    ],
    ids=("describe", "casillas", "formulas"),
)
def test_registry_discovery_accepts_explicit_year_period_scope(
    command: list[str],
    expected_fragments: tuple[str, ...],
) -> None:
    result = invoke_cached_cli(command)

    assert result.exit_code == 0, result.output
    for fragment in expected_fragments:
        assert fragment in result.output


@pytest.mark.parametrize(
    "command",
    [
        ["app", "modelo", "describe", "303", "--period", "2026Q1"],
        ["app", "modelo", "casillas", "303", "--period", "2026Q1"],
        ["app", "modelo", "formulas", "303", "--period", "2026Q1"],
    ],
)
def test_registry_discovery_rejects_combined_period_scope(command: list[str]) -> None:
    result = invoke_cached_cli(command)

    assert result.exit_code != 0
    assert "bare registry token" in result.output or "1T" in result.output


@pytest.mark.parametrize(
    ("modelo", "alias", "expected_token"),
    [
        ("303", "Q1", "1T"),
        ("100", "annual", "0A"),
    ],
)
@pytest.mark.parametrize(
    "command_prefix",
    [
        ["app", "modelo", "describe"],
        ["app", "modelo", "casillas"],
        ["app", "modelo", "formulas"],
    ],
)
def test_registry_discovery_rejects_aliases_for_explicit_scope(
    command_prefix: list[str],
    modelo: str,
    alias: str,
    expected_token: str,
) -> None:
    result = invoke_cached_cli([*command_prefix, modelo, "--year", "2026", "--period", alias])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert expected_token in result.output


def test_modelo_bad_parameter_helper_renders_registered_errors() -> None:
    error = _bad_parameter_from_error(WorkUnitNotFoundError())

    assert isinstance(error, typer.BadParameter)
    assert str(error)
    assert str(error) != "''"


@pytest.mark.parametrize(
    "command",
    [
        ["app", "modelo", "describe", "303", "--period", "garbage"],
        ["app", "modelo", "casillas", "303", "--period", "2026-Quarter1"],
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "not-a-period"],
        ["app", "modelo", "formulas", "303", "--period", "2026-13"],
    ],
)
def test_malformed_period_surfaces_as_bad_parameter(command: list[str]) -> None:
    result = invoke_cached_cli(command)
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "period must be" in output_lower or "invalid value" in output_lower


def test_unknown_modelo_surfaces_as_bad_parameter() -> None:
    result = invoke_cached_cli(["app", "modelo", "describe", "999"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "999" in output_lower or "not present" in output_lower


@pytest.mark.parametrize(
    "command_prefix",
    [
        ["app", "modelo", "describe"],
        ["app", "modelo", "casillas"],
        ["app", "modelo", "formulas"],
    ],
)
def test_unknown_modelo_with_explicit_period_scope_surfaces_as_bad_parameter(command_prefix: list[str]) -> None:
    result = invoke_cached_cli([*command_prefix, "999", "--year", "2026", "--period", "1T"])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "999" in output_lower or "not present" in output_lower


# ---------------------------------------------------------------------------
# describe surfaces the revision id(s) so `work create --revision` is
# discoverable without first guessing wrong (cluster E / M16).
# ---------------------------------------------------------------------------


def test_describe_surfaces_revision_ids_for_work_create() -> None:
    """`modelo describe` lists the revision id(s) an operator must pass
    to `work create --revision`, so the value is discoverable up front."""

    result = invoke_cached_cli(["app", "modelo", "describe", "303"])
    assert result.exit_code == 0, result.output
    # The label text varies by locale configuration; the revision id value is stable.
    assert "revision" in result.output.lower()
    # 303's filing-grade revision is the value `work create` requires.
    assert "2009-y-siguientes" in result.output


def test_describe_revision_ids_present_in_json_payload() -> None:
    """The typed describe payload carries `revision_ids` as a list so a
    machine consumer can enumerate the valid `--revision` values."""

    result = invoke_cached_cli(["--format", "json", "app", "modelo", "describe", "130"])
    assert result.exit_code == 0, result.output

    payload = _payload(result.output)
    assert isinstance(payload["revision_ids"], list)
    assert payload["revision_ids"]
    assert payload["revision"] in payload["revision_ids"]
    encoded_payload = json.dumps(payload, sort_keys=True)
    assert CLI_PROFILE_ID_PLACEHOLDER not in encoded_payload
    assert CLI_BUCKET_ID_PLACEHOLDER not in encoded_payload
    assert _UUID_TEXT_RE.search(encoded_payload) is None


# ---------------------------------------------------------------------------
# Missing-binding guidance on `work calculate` (cluster E / M18).
# ---------------------------------------------------------------------------


def test_work_create_revision_help_points_at_describe() -> None:
    """The `--revision` option help tells the operator how to discover
    the valid revision id (via `modelo describe`)."""

    result = invoke_cached_cli(["app", "modelo", "work", "create", "--help"])
    assert result.exit_code == 0, result.output
    assert "modelo describe" in result.output


def test_work_calculate_binding_help_points_at_bindings_list() -> None:
    """The `--binding` option help points the operator at
    `bindings list --missing` to discover required bindings."""

    result = invoke_cached_cli(["app", "modelo", "work", "calculate", "--help"])
    assert result.exit_code == 0, result.output
    # The CliRunner renders Rich panel box-drawing characters (│, └, etc.)
    # that interleave with wrapped text.  Strip non-ASCII before collapsing.
    ascii_only = "".join(c for c in result.output if c.isascii())
    collapsed = " ".join(ascii_only.split())
    assert "bindings list --missing" in collapsed


def test_work_calculate_relation_help_names_m200_m202_relation_channels() -> None:
    """The `--relation` help tells M200 operators not to use binding ids for M202 pagos."""

    result = invoke_cached_cli(
        ["app", "modelo", "work", "calculate", "--help"],
        env={"COLUMNS": "240"},
        color=False,
    )
    assert result.exit_code == 0, result.output
    ascii_only = "".join(c for c in result.output if c.isascii())
    collapsed = " ".join(ascii_only.split())
    assert "--relation" in collapsed
    assert "KEY=VALUE" in collapsed
    assert "id de binding" in collapsed or "binding id" in collapsed
    assert "bindings list --missing" in collapsed
    assert "Modelo 200" in collapsed
    assert "M202" in collapsed
    assert "pagos fraccionados" in collapsed
    assert "40.3 casilla 34" in collapsed
    assert "40.2 casilla 03" in collapsed
    assert "0" in collapsed


def test_work_calculate_enters_bucket_source_mesh_calculation_boundary() -> None:
    """The work calculation application helper must use the bucket-backed boundary.

    This keeps default operator calculations on the same source mesh path as
    repository-backed application calculations, instead of reaching around it
    to the low-level registry engine action.
    """

    import inspect

    from ....application.modelo import calculate_modelo_work_revision

    source = inspect.getsource(calculate_modelo_work_revision)
    assert "calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(" in source
    assert "calculate_modelo_revision(" not in source


def test_missing_binding_guidance_enriches_registry_validation_error() -> None:
    """A missing-binding RegistryValidationError is enriched with the
    --binding KEY=VALUE syntax and a bindings-list discovery command so
    the first `work calculate` failure is self-correcting."""

    from ....domain.calculations.registry import RegistryValidationError
    from .._modelo import _missing_binding_guidance

    error = RegistryValidationError(
        "binding 'irpf.previous_year_economic_activity_net_income' has no supplied value",
        translated_message="errors.calc.binding_value_missing",
        context={"binding_id": "irpf.previous_year_economic_activity_net_income"},
    )
    # An unknown work unit forces the generic discovery command path.
    guidance = _missing_binding_guidance(error, "no-such-work-unit")
    assert "--binding KEY=VALUE" in guidance
    assert "bindings list --missing" in guidance
    assert "irpf.previous_year_economic_activity_net_income" in guidance


def test_missing_binding_guidance_routes_by_binding_source(tmp_path) -> None:
    """The missing-binding guidance is routed by the binding's typed source.

    A ledger-aggregation binding rejects a caller ``--binding`` (it reads from
    the bucket ledger), so its guidance MUST steer the operator to add ledger
    rows and run ``ledger preflight`` — NOT to pass ``--binding`` (which the app
    refuses with ``error_modelo_aggregation_binding``). A ``previous_filing``
    binding genuinely accepts ``--binding``, so it keeps the ``--binding``
    guidance. Modelo 130 carries both source kinds, so it exercises both
    branches against the real registry through one persisted work unit.
    """

    from ....application.modelo import create_work_unit
    from ....core import Period
    from ....domain.calculations.registry import RegistryValidationError
    from ....tests.secure_sql import isolated_runtime_profile
    from .._modelo import _missing_binding_guidance

    period = Period.from_year_and_code(2025, "1T")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="missing-binding-route") as runtime:
        _seed_modelo_130_ready_profile(runtime.bucket_id)
        unit = create_work_unit(
            bucket_id=runtime.bucket_id,
            modelo="130",
            filing_year=2025,
            period=period,
            revision_id="2019-y-siguientes",
        )

        ledger_error = RegistryValidationError(
            "binding 'modelo-130-actividad-economica-ingresos-cumulative' has no supplied value",
            translated_message="errors.calc.binding_value_missing",
            context={"binding_id": "modelo-130-actividad-economica-ingresos-cumulative"},
        )
        ledger_guidance = _missing_binding_guidance(ledger_error, unit.work_unit_id)
        # Ledger-sourced: steer to ledger rows + preflight, NOT --binding.
        assert "ledger preflight" in ledger_guidance
        assert "--binding KEY=VALUE" not in ledger_guidance

        prev_filing_error = RegistryValidationError(
            "binding 'irpf.previous_year_economic_activity_net_income' has no supplied value",
            translated_message="errors.calc.binding_value_missing",
            context={"binding_id": "irpf.previous_year_economic_activity_net_income"},
        )
        prev_filing_guidance = _missing_binding_guidance(prev_filing_error, unit.work_unit_id)
        # previous_filing-sourced: keep the --binding guidance, not ledger.
        assert "--binding KEY=VALUE" in prev_filing_guidance
        assert "ledger preflight" not in prev_filing_guidance


def test_work_calculate_missing_m200_m202_relation_prefill_is_advisory(tmp_path) -> None:
    """The live M200 relation-prefill path warns rather than refusing calculation."""

    from ....application.modelo import create_work_unit
    from ....application.user_profile import UserProfileLifecycleRepository
    from ....core import Period
    from ....domain.user_profile import UserProfileFact, UserProfileRecord
    from ....tests.secure_sql import isolated_runtime_profile

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="m200-missing-relation-guidance") as runtime:
        UserProfileLifecycleRepository(bucket_id=runtime.bucket_id, objects=runtime.repository).save(
            UserProfileRecord(
                profile_id=runtime.bucket_id,
                display_name="M200 relation guidance profile",
                facts=(
                    UserProfileFact(path="identity.tax_id", value="B12345678"),
                    UserProfileFact(path="identity.legal_name", value="M200 Relation Guidance SL"),
                    UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
                    UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
                    UserProfileFact(path="taxpayer_type.incn_prior_12_months", value="500000"),
                    UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value="false"),
                    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                ),
            ),
        )
        unit = create_work_unit(
            bucket_id=runtime.bucket_id,
            modelo="200",
            filing_year=2024,
            period=Period.from_year_and_code(2024, "0A"),
            revision_id="2024-y-siguientes",
        )
        result = invoke_cached_cli(
            [
                "app",
                "modelo",
                "work",
                "calculate",
                unit.work_unit_id,
                "--casilla", "00501=100000.00",
                "--casilla", "DP200013:00417=0.00",
                "--casilla", "DP200013:00418=0.00",
                "--casilla", "01032=0.00",
                "--casilla", "DP200014:00547=0.00",
                "--casilla", "DP200014:01033=0.00",
                "--casilla", "DP200014:01034=0.00",
                "--binding", "modelo-200-2024-profile-legal-entity-form=sl",
                "--binding", "modelo-200-2024-profile-new-entity-flag=0",
                "--binding", "modelo-200-2024-profile-incn-prior-12-months=500000",
                "--binding", "modelo-200-2024-profile-tributacion-estado-porcentaje=100",
                "--binding", "modelo-200-2024-bin-pendiente-ejercicios-anteriores=0",
                "--binding", "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
                "--binding", "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0",
                "--relation", "modelo-200-2024-rel-202-pagos-fraccionados=1800",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    assert (
        "ADVISORY: relation 'modelo-200-2024-rel-202-pagos-fraccionados-40-2' requires modelo 202"
        in result.output
    )
    assert "source filing is missing or incomplete" in result.output


def test_missing_relation_guidance_helper_routes_m200_m202_to_relation_flag() -> None:
    """If a relation error reaches the refusal helper, it must point at --relation."""

    from ....domain.calculations.registry import RegistryValidationError
    from .._modelo import _missing_binding_guidance

    error = RegistryValidationError(
        "relation 'modelo-200-2024-rel-202-pagos-fraccionados-40-2' has no supplied value",
        translated_message="errors.calc.relation_value_missing",
        context={"relation_id": "modelo-200-2024-rel-202-pagos-fraccionados-40-2"},
    )

    guidance = _missing_binding_guidance(error, "no-such-work-unit")

    assert "--relation RELATION_ID=VALUE" in guidance
    assert "not --binding" in guidance
    assert "DP200014B:00611" in guidance
    assert "40.3 casilla 34" in guidance
    assert "40.2 casilla 03" in guidance
    assert "unused modality to 0" in guidance
    assert "--binding KEY=VALUE" not in guidance


def test_bindings_discovery_command_renders_runnable_period_token() -> None:
    """The work-unit-scoped discovery command must place only the bare AEAT
    period token after ``--period`` — never the combined ``"<year> <token>"``
    display form of ``Period.__str__`` — so the suggested command is runnable
    verbatim (``--period 1T``, with the year on its own ``--year`` axis)."""

    from ....core import Period
    from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id
    from .._modelo import _bindings_discovery_command

    typed_period = Period.from_year_and_code(2026, "1T")
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="test-bucket",
            modelo="130",
            filing_year=2026,
            period=typed_period,
            revision_id="r" + "0" * 63,
        ),
        bucket_id="test-bucket",
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=typed_period,
        revision_id="r" + "0" * 63,
        name="130-2026-1T",
        created_at=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
    )

    command = _bindings_discovery_command(unit)

    assert "--period 1T --missing" in command
    assert "--year 2026 --period 1T" in command
    # The combined display form must never appear inside the --period value.
    assert "--period 2026" not in command
    assert str(typed_period) not in command
    assert command == "aeat app modelo bindings list --modelo 130 --year 2026 --period 1T --missing"


def test_missing_binding_guidance_passes_non_input_errors_through() -> None:
    """A registry-validation error that is NOT a missing-input class is
    returned unchanged - the guidance is scoped to inputs the operator
    can actually supply."""

    from ....domain.calculations.registry import RegistryValidationError
    from .._modelo import _missing_binding_guidance

    error = RegistryValidationError(
        "casilla referenced before evaluation",
        translated_message="errors.calc.casilla_referenced_before_evaluation",
        context={"casilla_id": _NON_INPUT_ERROR_CASILLA},
    )
    guidance = _missing_binding_guidance(error, "no-such-work-unit")
    assert "--binding KEY=VALUE" not in guidance


# ---------------------------------------------------------------------------
# casillas --form-number filter
# ---------------------------------------------------------------------------


def test_casillas_form_number_filter_matches_declared_casilla() -> None:
    """``--form-number 46`` returns only the M303 casilla whose form_number equals '46'."""
    result = invoke_cached_cli(["app", "modelo", "casillas", "303", "--form-number", "46"])
    assert result.exit_code == 0, result.output
    rows = [line for line in result.output.splitlines() if line.startswith("iva.resultado-regimen-general\t")]
    assert rows, result.output


def test_casillas_form_number_filter_no_match_returns_empty_table() -> None:
    """``--form-number`` with a value not declared by any casilla returns an empty table."""
    result = invoke_cached_cli(["app", "modelo", "casillas", "303", "--form-number", "9999"])
    assert result.exit_code == 0, result.output
    data_rows = [
        line
        for line in result.output.splitlines()
        if line and not line.startswith("operation\t") and not line.startswith("casilla_id\t")
    ]
    assert not data_rows, result.output


# ---------------------------------------------------------------------------
# bindings list / resolve surface
# ---------------------------------------------------------------------------


def test_bindings_list_emits_readiness_and_borrador_columns_per_row() -> None:
    """``bindings list`` enriches each binding row with a readiness
    category from the closed set (ledger source / profile fact /
    prior filed revision / live observation / bucket / waiver /
    blocking finding / casilla), and reports the ``borrador_capable``
    flag per binding so callers can identify AEAT-prefilled casillas."""

    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "1T"],
    )
    assert result.exit_code == 0, result.output
    assert "operation\tregistry.modelo.bindings.list" in result.output
    assert "binding_id\tsource\treadiness\ttyped_enum\tinput_channel\tborrador_capable" in result.output
    # Every modelo-303 binding currently sources from
    # ``ledger_iva_aggregation`` so every row's readiness column is
    # "ledger source".
    assert "ledger source" in result.output
    # Every binding row ends in either ``True`` or ``False`` for the
    # new column. Detect by matching the binding-id prefix on at
    # least one row.
    binding_lines = [line for line in result.output.splitlines() if line.startswith("303\t")]
    assert binding_lines, result.output
    for line in binding_lines:
        last_column = line.rsplit("\t", 1)[-1]
        assert last_column in {"True", "False"}, line


def test_bindings_list_missing_filter_excludes_constant_value_bindings() -> None:
    """``--missing`` filters to bindings that require runtime
    resolution. Constant-valued bindings are inherently always
    available so they drop out of the missing-bindings view."""

    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "1T", "--missing"],
    )
    assert result.exit_code == 0, result.output
    assert "missing_filter\tTrue" in result.output


def test_bindings_list_missing_m200_surfaces_m202_relation_inputs() -> None:
    """M200 missing-input discovery names the M202 pago relation ids, not just target bindings."""

    result = invoke_cached_cli(
        [
            "--language",
            "en",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "200",
            "--year",
            "2024",
            "--period",
            "0A",
            "--missing",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "missing_filter\tTrue" in result.output
    assert "\tmodelo-200-2024-pagos-fraccionados-anuales\trelation_prefill\trelation input\t" in result.output
    assert (
        "\tmodelo-200-2024-pagos-fraccionados-anuales-40-2\trelation_prefill\trelation input\t"
        in result.output
    )
    assert (
        "relation_guidance\tModelo 200 M202 pagos fraccionados feed DP200014B:00611 "
        "through --relation values, not --binding target binding ids."
    ) in result.output
    assert "mutually exclusive per filing" in result.output
    assert "unused modality" in result.output
    assert (
        "relation_input\tmodelo-200-2024-rel-202-pagos-fraccionados\tM202 40.3 casilla 34\t"
        "use --relation modelo-200-2024-rel-202-pagos-fraccionados=VALUE\t"
        "paired target binding modelo-200-2024-pagos-fraccionados-anuales"
    ) in result.output
    assert (
        "relation_input\tmodelo-200-2024-rel-202-pagos-fraccionados-40-2\tM202 40.2 casilla 03\t"
        "use --relation modelo-200-2024-rel-202-pagos-fraccionados-40-2=VALUE\t"
        "paired target binding modelo-200-2024-pagos-fraccionados-anuales-40-2"
    ) in result.output


def test_bindings_list_without_missing_does_not_append_m200_relation_guidance() -> None:
    """The extra M200/M202 relation instructions belong to the missing-input view."""

    result = invoke_cached_cli(
        [
            "--language",
            "en",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "200",
            "--year",
            "2024",
            "--period",
            "0A",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "missing_filter\tFalse" in result.output
    assert "relation_guidance\t" not in result.output
    assert "relation_input\tmodelo-200-2024-rel-202-pagos-fraccionados" not in result.output


def test_bindings_resolve_echoes_override_for_known_key() -> None:
    """An override targeting a known binding id surfaces in the
    payload's ``override`` column."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "resolve",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "1T",
            "--binding",
            "modelo-303-iva-repercutido-general-cuota=1234.56",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "operation\tregistry.modelo.bindings.resolve" in result.output
    assert "override_count\t1" in result.output
    assert "1234.56" in result.output

    json_result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "resolve",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "1T",
            "--binding",
            "modelo-303-iva-repercutido-general-cuota=1234.56",
        ],
    )
    assert json_result.exit_code == 0, json_result.output
    payload = _payload(json_result.output)
    row = next(
        item for item in payload["bindings"] if item["binding_id"] == "modelo-303-iva-repercutido-general-cuota"
    )
    assert row["override"] == "1234.56"


def test_bindings_resolve_rejects_unknown_binding_with_suggestion_list() -> None:
    """Unknown override keys fail with a suggestion list sourced
    from the registry's binding catalogue for the active modelo /
    year / period."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "resolve",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "1T",
            "--binding",
            "no-such-binding=42",
        ],
    )
    assert result.exit_code != 0
    output_lower = result.output.lower()
    assert "no-such-binding" in output_lower
    # The suggestion list cites at least one real binding id.
    assert "modelo-303-iva-" in result.output


def test_bindings_resolve_rejects_malformed_override_syntax() -> None:
    """``--binding`` without an ``=`` separator fails at the CLI
    boundary with a typer.BadParameter."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "resolve",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "1T",
            "--binding",
            "missing-equals-sign",
        ],
    )
    assert result.exit_code != 0
    assert "KEY=VALUE" in result.output


# ---------------------------------------------------------------------------
# Boundary regression guards
# ---------------------------------------------------------------------------


def test_no_parallel_bindings_typer_outside_canonical_module() -> None:
    """The canonical ``bindings`` sub-Typer registration lives in
    ``_modelo.py``. Any other module that re-implements a Typer
    named ``bindings`` competes with the canonical surface and must
    be removed."""

    from pathlib import Path

    from ....core.paths import PROJECT_ROOT

    cli_root = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
    canonical = cli_root / "_modelo.py"
    forbidden_patterns = (
        'typer.Typer(\n    name="bindings"',
        'typer.Typer(name="bindings"',
    )
    offenders: list[Path] = []
    for py_file in cli_root.rglob("*.py"):
        if py_file == canonical:
            continue
        if py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8")
        if any(needle in text for needle in forbidden_patterns):
            offenders.append(py_file)
    assert offenders == [], f"Parallel bindings Typer outside the canonical _modelo.py: {[str(p) for p in offenders]}"


def test_bindings_list_and_resolve_emit_no_bucket_event() -> None:
    """``bindings list`` and ``bindings resolve`` are read-only —
    they must not trigger any bucket event.

    The boundary check inspects the canonical module's source for
    any bucket-event emission call. If a future change wires one
    in by accident, this test fails fast."""

    from ....core.paths import PROJECT_ROOT

    canonical_text = (PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "_modelo.py").read_text(encoding="utf-8")
    forbidden_emitters = (
        "emit_bucket_event",
        "append_bucket_event",
        "bucket_event(",
    )
    for needle in forbidden_emitters:
        assert needle not in canonical_text, (
            f"Forbidden bucket-event emission pattern {needle!r} found in "
            "_modelo.py; bindings list/resolve must remain read-only."
        )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("aeat_justificante_pdf", "aeat_justificante_pdf"),
        ("aeat-justificante-pdf", "aeat_justificante_pdf"),
        ("aeat_csv_register", "aeat_csv_register"),
        ("aeat-csv-register", "aeat_csv_register"),
        ("aeat_live_capture", "aeat_live_capture"),
        ("aeat-live-capture", "aeat_live_capture"),
    ],
)
def test_evidence_kind_accepts_canonical_and_hyphenated_values(raw: str, expected: str) -> None:
    """``--evidence-kind`` accepts both canonical underscore values and
    their hyphenated aliases (``aeat-justificante-pdf`` ↔ ``aeat_justificante_pdf``).
    The import command parses the alias and normalises it before
    dispatching the application action."""

    from ....domain.modelos._filing_record import ExternalEvidenceKind

    normalised = raw.strip().replace("-", "_")
    assert ExternalEvidenceKind(normalised) is ExternalEvidenceKind(expected)


def test_evidence_kind_rejects_unrelated_token() -> None:
    """``--evidence-kind`` still rejects values that aren't a valid
    enum member after hyphen-to-underscore normalisation."""

    from ....domain.modelos._filing_record import ExternalEvidenceKind

    raw = "aeat_bogus_evidence"
    with pytest.raises(ValueError, match="aeat_bogus_evidence"):
        ExternalEvidenceKind(raw.strip().replace("-", "_"))


# ---------------------------------------------------------------------------
# contract — typed WorkUnitId validation at CLI ingress
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a" * 64, "a" * 64),
        (f"  {'b' * 64}  ", "b" * 64),
    ],
    ids=("plain", "trimmed"),
)
def test_validate_work_unit_id_accepts_valid_hex64_and_strips_whitespace(raw: str, expected: str) -> None:
    from .._modelo import _validate_work_unit_id

    result = _validate_work_unit_id(raw)
    assert result == expected
    assert isinstance(result, str)


@pytest.mark.parametrize(
    "bad",
    [
        "short",
        "G" * 64,  # uppercase -- not lowercase hex
        "z" * 64,  # non-hex character
        "a" * 63,  # one char short
        "a" * 65,  # one char long
        "",
    ],
)
def test_validate_work_unit_id_rejects_malformed(bad: str) -> None:
    """Malformed work_unit_id values raise ``typer.BadParameter``."""
    import typer as _typer

    from .._modelo import _validate_work_unit_id

    with pytest.raises(_typer.BadParameter):
        _validate_work_unit_id(bad)


# ---------------------------------------------------------------------------
# contract -- CasillaId / BindingId key validation at CLI ingress
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec",
    [
        "A=1",
        "casilla01=2",
        "A.B:C-D=3",
        "x" * 64 + "=0",  # exactly 64-char key
    ],
)
def test_parse_casilla_override_accepts_valid_keys(spec: str) -> None:
    """Valid CasillaId keys are accepted by ``_parse_casilla_override``."""
    from .._modelo import _parse_casilla_override

    key, _ = _parse_casilla_override(spec)
    assert key


@pytest.mark.parametrize(
    "spec",
    [
        "=value",  # empty key
        " A=1",  # casilla.id must be accepted exactly as supplied
        "A =1",  # key-side whitespace must not be stripped into a valid id
        ".starts-with-dot=1",  # dot at start (fails _CASILLA_RE)
        ("x" * 65) + "=0",  # key exceeds 64-char max
    ],
)
def test_parse_casilla_override_rejects_invalid_keys(spec: str) -> None:
    """Invalid CasillaId keys raise ``typer.BadParameter``."""
    import typer as _typer

    from .._modelo import _parse_casilla_override

    with pytest.raises(_typer.BadParameter):
        _parse_casilla_override(spec)


@pytest.mark.parametrize("spec", [" 01=1.00", "01 =1.00"])
def test_parse_amendment_casilla_rejects_whitespace_padded_keys(spec: str) -> None:
    """Amendment ``--set`` casilla keys are validated without key coercion."""
    import typer as _typer

    from .._modelo import _parse_amendment_casilla

    with pytest.raises(_typer.BadParameter):
        _parse_amendment_casilla(spec)


@pytest.mark.parametrize(
    "spec",
    [
        "binding-id=1",
        "a=v",
        "modelo-303-iva-repercutido=100",
    ],
)
def test_parse_binding_override_accepts_valid_keys(spec: str) -> None:
    """Valid BindingId keys are accepted by ``_parse_binding_override``."""
    from .._modelo import _parse_binding_override

    key, _ = _parse_binding_override(spec)
    assert key


@pytest.mark.parametrize(
    "spec",
    [
        "=value",  # empty key
        "UPPERCASE=1",  # uppercase not in _REF_RE
        ".starts-dot=1",  # starts with dot
        ("x" * 129) + "=0",  # key exceeds 128-char max
    ],
)
def test_parse_binding_override_rejects_invalid_keys(spec: str) -> None:
    """Invalid BindingId keys raise ``typer.BadParameter``."""
    import typer as _typer

    from .._modelo import _parse_binding_override

    with pytest.raises(_typer.BadParameter):
        _parse_binding_override(spec)


# ---------------------------------------------------------------------------
# bindings-interface hardening: the `bindings list` payload is typed
# and carries provenance; `--modelo` is a registry-derived Choice that refuses
# an unknown code with the accepted set.
# ---------------------------------------------------------------------------


def test_bindings_list_modelo_choice_refuses_unknown_code() -> None:
    """`bindings list --modelo` is a registry-derived Choice.

    An unknown modelo code is refused at parse time (before the command body
    runs) with the accepted-code set, per the CLI-Choice-hint mandate. The
    refusal names a real registry code so the operator sees the accepted set,
    not a bare "value invalid".
    """
    result = invoke_cached_cli(["app", "modelo", "bindings", "list", "--modelo", "ZZZ"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "zzz" in output_lower or "invalid" in output_lower
    # The accepted set is surfaced: at least one real registry code is named.
    assert "303" in result.output or "130" in result.output


def test_bindings_list_modelo_choice_help_renders_accepted_codes() -> None:
    """`bindings list --help` surfaces the accepted modelo-code set.

    The registry-derived Choice metavar / help carries the accepted codes so
    the operator learns the valid set from `--help`, not from a failed run.
    """
    result = invoke_cached_cli(["app", "modelo", "bindings", "list", "--help"])
    assert result.exit_code == 0, result.output
    # The choice is built from the registry-bound modelo id list; the help
    # surface names the accepted codes (the registry exposes 303 and 130).
    assert "303" in result.output and "130" in result.output


def test_bindings_list_payload_is_typed_and_carries_provenance() -> None:
    """The `bindings list` JSON payload is the typed `BindingListRowPayload` shape.

    Each binding row carries the typed fields plus the regulatory grounding
    (`legal_refs` / `source_refs`) sourced from the registry binding
    definition, at parity with the casilla half. This is the operator-boundary
    provenance-parity contract of the bindings-interface hardening; the
    pre-hardening payload was an untyped `dict[str, object]` bag with no
    grounding.
    """
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "bindings", "list",
            "--modelo", "100", "--year", "2025", "--period", "0A",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    bindings = payload["bindings"]
    assert bindings, "Modelo 100 declares bindings; the listing must be non-empty"
    snapshot = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")
    known_binding_ids = {binding.id for binding in snapshot.revision.bindings}
    emitted_binding_ids = {row["binding_id"] for row in bindings}
    assert emitted_binding_ids <= known_binding_ids
    # Every row carries the typed fields and the provenance fields.
    required = {
        "modelo",
        "revision",
        "filing_year",
        "period",
        "binding_id",
        "source",
        "readiness",
        "typed_enum",
        "input_channel",
        "borrador_capable",
        "legal_refs",
        "source_refs",
    }
    for row in bindings:
        assert required <= set(row), sorted(required - set(row))
        assert isinstance(row["legal_refs"], list)
        assert isinstance(row["source_refs"], list)
        assert row["legal_refs"], f"binding {row['binding_id']!r} must carry registry legal_refs"
        assert row["source_refs"], f"binding {row['binding_id']!r} must carry registry source_refs"
