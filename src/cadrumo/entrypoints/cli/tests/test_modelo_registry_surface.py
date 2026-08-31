"""Modelo registry/discovery CLI surface integration tests.

The suite pins the ``aeat app modelo`` discovery and work-calculation ingress
surface: help discoverability, canonical period tokens, describe/casillas/formulas
queries, binding and relation guidance, typed override-key validation, and JSON
payload redaction. It exercises the live Typer tree against the real registry
query and calculation helper paths rather than scanning command source.

See Also:
    :mod:`~entrypoints.cli._modelo_discovery_cli`
        Typer registration for list, describe, casillas, formulas, and bindings
        discovery commands.
    :class:`~domain.calculations.registry.RegistryQueryService`
        Typed registry introspection service behind the discovery surface.
    :func:`~entrypoints.cli._modelo_behavior_support.bare_period_error`
        Factual invalid-token helper that states registry-declared ids without
        making a recovery-action selection.

The bindings discovery surface is locked to the registry as its single
source of truth, and ``work calculate`` reads from that same registry.
"""

from __future__ import annotations

import ast
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
import typer

from ....application.modelo._action_errors import WorkUnitNotFoundError
from ....core.redaction.rules import CLI_BUCKET_ID_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER
from ....domain.user_profile.values import ProfileSetupState
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from .._modelo import _bad_parameter_from_error

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_UUID_TEXT_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
_S91_DECLARED_SOURCE_PATHS = (
    "src/cadrumo/application/modelo/_action_errors.py",
    "src/cadrumo/application/modelo/_export.py",
    "src/cadrumo/application/modelo/_iva_wallet_seed.py",
    "src/cadrumo/application/modelo/_preconditions.py",
    "src/cadrumo/entrypoints/cli/_modelo.py",
    "src/cadrumo/entrypoints/cli/_modelo_behavior_support.py",
    "src/cadrumo/entrypoints/cli/_modelo_payloads.py",
    "src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py",
    "src/cadrumo/entrypoints/cli/_modelo_export_cli.py",
    "src/cadrumo/entrypoints/cli/_modelo_amend_wizard_cli.py",
    "src/cadrumo/entrypoints/cli/_modelo_amend_wizard_payloads.py",
    "src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py",
    "src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py",
    "src/cadrumo/entrypoints/cli/_modelo_iva_wallet_cli.py",
)
_S91_CLI_SOURCE_PATHS = tuple(path for path in _S91_DECLARED_SOURCE_PATHS if "/entrypoints/cli/" in path)
_LOCAL_ACTION_CONSTRUCTORS = {
    "ActionReference",
    "ConditionEvidence",
    "PreconditionVerdict",
    "ResolvedActionReference",
    "ResolvedNoticeAction",
}
_EXECUTABLE_RECOVERY_LITERAL = re.compile(
    r"aeat\s+app\s+modelo\s+(?:filing-record\s+import|bindings\s+list|work\s+(?:calculate|verify|file|revisions)|iva-wallet\s+seed)|calculate\s*->\s*verify\s*->\s*file|set\s+it\s+via\s+config\s+profile",
    re.IGNORECASE,
)


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _s91_cli_census_violations(source: str) -> tuple[str, ...]:
    """Return forbidden local selection or executable-recovery literals in one CLI source."""
    tree = ast.parse(source)
    violations = {
        f"local action constructor: {_call_name(call.func)}"
        for call in ast.walk(tree)
        if isinstance(call, ast.Call) and _call_name(call.func) in _LOCAL_ACTION_CONSTRUCTORS
    }
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        literals = (
            value.value for value in ast.walk(call) if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
        if any(_EXECUTABLE_RECOVERY_LITERAL.search(value) for value in literals):
            violations.add("executable recovery literal")
    return tuple(sorted(violations))


def test_declared_s91_sources_keep_action_selection_in_application_and_recovery_off_prose() -> None:
    """The entire declared Modelo registry surface is fail-closed against action/prose regressions."""
    for relative_path in _S91_DECLARED_SOURCE_PATHS:
        source = (_REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        ast.parse(source)
    for relative_path in _S91_CLI_SOURCE_PATHS:
        source = (_REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert _s91_cli_census_violations(source) == (), relative_path


def test_declared_s91_cli_census_rejects_mutated_local_actions_and_recovery_prose() -> None:
    """Mutation probes prove the Modelo registry census cannot pass after either regression."""
    action_mutation = "ActionReference(action_id='operator.modelo.describe')"
    prose_mutation = "typer.BadParameter(\"Run 'aeat app modelo work calculate' first.\")"
    profile_mutation = 'typer.BadParameter("Set it via config profile.")'

    assert _s91_cli_census_violations(action_mutation) == ("local action constructor: ActionReference",)
    assert _s91_cli_census_violations(prose_mutation) == ("executable recovery literal",)
    assert _s91_cli_census_violations(profile_mutation) == ("executable recovery literal",)


def _seed_modelo_130_ready_profile(bucket_id: str) -> None:
    from ....domain.user_profile.values import UserProfileFact, UserProfileRecord
    from ....tests.profile_capsule import seed_test_profile_record

    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="guidance"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            ),
        ),
        label="Modelo 130 guidance profile",
    )


# ---------------------------------------------------------------------------
# Discoverability: the modelo `describe` verb is listed in `modelo --help`
# and resolves; the ledger `preflight` verb is listed in `ledger --help` and
# resolves. There is deliberately NO `modelo preflight` verb — signposting
# one would mislead the operator (the #51 lesson), so we assert its absence.
# ---------------------------------------------------------------------------


def test_documented_subverb_is_listed_in_help_and_resolves() -> None:
    """Documented app subverbs appear in help and resolve to real commands."""
    # The resolved-verb hint is the positional-argument metavar as Typer
    # renders it in the usage line: a required positional appears braced
    # (`{modelo}`). Older Typer emitted a bare-uppercase `MODELO`; the
    # capability (a required MODELO positional) is unchanged — only the
    # metavar spelling moved.
    cases = (
        ("modelo-describe", ["app", "modelo"], "describe", "{modelo}"),
        ("ledger-preflight", ["app", "ledger"], "preflight", None),
    )

    for case_id, group_args, verb, resolved_hint in cases:
        listing = invoke_cached_cli([*group_args, "--help"])
        assert listing.exit_code == 0, f"{case_id}: {listing.output}"
        assert verb in listing.output, case_id

        resolved = invoke_cached_cli([*group_args, verb, "--help"])
        assert resolved.exit_code == 0, f"{case_id}: {resolved.output}"
        if resolved_hint is not None:
            assert resolved_hint in resolved.output, case_id


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


def test_modelo_period_help_uses_canonical_registry_tokens() -> None:
    """Every modelo `--period` help advertises the canonical registry
    token set (0A / 1T-4T / 01-12) and never the misleading 'Q1, annual'
    or ledger-style 'YYYYQn' examples that diverged across surfaces."""
    commands = (
        ["app", "modelo", "describe", "--help"],
        ["app", "modelo", "casillas", "--help"],
        ["app", "modelo", "formulas", "--help"],
        ["app", "modelo", "history", "--help"],
        ["app", "modelo", "readiness", "--help"],
        ["app", "modelo", "work", "create", "--help"],
    )

    for command in commands:
        result = invoke_cached_cli(command)
        assert result.exit_code == 0, result.output
        ascii_only = "".join(c for c in result.output if c.isascii())
        collapsed = " ".join(ascii_only.split())
        assert "1T-4T" in collapsed, (command, collapsed)
        # The misleading tokens that previously diverged must be gone.
        assert "Q1, annual" not in collapsed, command
        assert "2026Q1" not in collapsed, command


def test_invalid_modelo_period_surfaces_accepted_set() -> None:
    """A period that no revision declares is refused with the declared
    set listed inline (the architecture-rule instructive-refusal contract
    for the dynamic registry period axis)."""
    result = invoke_cached_cli(["app", "modelo", "describe", "303", "--period", "0A"])
    assert result.exit_code != 0, result.output
    # The accepted/declared set is surfaced, not a bare 'invalid'.
    assert "1T" in result.output and "4T" in result.output


def test_registry_discovery_accepts_explicit_year_period_scope() -> None:
    cases = (
        (
            "describe",
            ["app", "modelo", "describe", "303", "--year", "2026", "--period", "1T"],
            ("303", "2022"),
        ),
        (
            "casillas",
            ["app", "modelo", "casillas", "303", "--year", "2026", "--period", "1T", "--input-kind", "computed"],
            ("iva.resultado-regimen-general",),
        ),
        (
            "formulas",
            ["app", "modelo", "formulas", "303", "--year", "2026", "--period", "1T"],
            ("formula_id",),
        ),
    )

    for case_id, command, expected_fragments in cases:
        result = invoke_cached_cli(command)

        assert result.exit_code == 0, f"{case_id}: {result.output}"
        for fragment in expected_fragments:
            assert fragment in result.output, case_id


def test_registry_discovery_rejects_combined_period_scope() -> None:
    commands = (
        ["app", "modelo", "describe", "303", "--period", "2026Q1"],
        ["app", "modelo", "casillas", "303", "--period", "2026Q1"],
        ["app", "modelo", "formulas", "303", "--period", "2026Q1"],
    )

    for command in commands:
        result = invoke_cached_cli(command)

        assert result.exit_code != 0, command
        assert "bare registry token" in result.output or "1T" in result.output


def test_registry_discovery_rejects_aliases_for_explicit_scope() -> None:
    command_prefixes = (
        ["app", "modelo", "describe"],
        ["app", "modelo", "casillas"],
        ["app", "modelo", "formulas"],
    )
    aliases = (
        ("303", "Q1", "1T"),
        ("100", "annual", "0A"),
    )

    for command_prefix in command_prefixes:
        for modelo, alias, expected_token in aliases:
            result = invoke_cached_cli([*command_prefix, modelo, "--year", "2026", "--period", alias])

            assert result.exit_code != 0, (command_prefix, modelo, alias)
            assert "Traceback" not in result.output
            assert expected_token in result.output, (command_prefix, modelo, alias)


def test_modelo_bad_parameter_helper_renders_registered_errors() -> None:
    error = _bad_parameter_from_error(WorkUnitNotFoundError())

    assert isinstance(error, typer.BadParameter)
    assert str(error)
    assert str(error) != "''"


def test_malformed_period_surfaces_as_bad_parameter() -> None:
    commands = (
        ["app", "modelo", "describe", "303", "--period", "garbage"],
        ["app", "modelo", "casillas", "303", "--period", "2026-Quarter1"],
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "not-a-period"],
        ["app", "modelo", "formulas", "303", "--period", "2026-13"],
    )

    for command in commands:
        result = invoke_cached_cli(command)
        assert result.exit_code != 0, command
        assert "Traceback" not in result.output
        output_lower = result.output.lower()
        assert "period must be" in output_lower or "invalid value" in output_lower


def test_unknown_modelo_surfaces_as_bad_parameter() -> None:
    result = invoke_cached_cli(["app", "modelo", "describe", "999"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "999" in output_lower or "not present" in output_lower


def test_unknown_modelo_with_explicit_period_scope_surfaces_as_bad_parameter() -> None:
    command_prefixes = (
        ["app", "modelo", "describe"],
        ["app", "modelo", "casillas"],
        ["app", "modelo", "formulas"],
    )

    for command_prefix in command_prefixes:
        result = invoke_cached_cli([*command_prefix, "999", "--year", "2026", "--period", "1T"])

        assert result.exit_code != 0, command_prefix
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
    assert "2022" in result.output


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
# Factual discovery errors on `work calculate` (cluster E / M18).
# ---------------------------------------------------------------------------


def test_work_create_revision_help_points_at_describe() -> None:
    """The `--revision` option help tells the operator how to discover
    the valid revision id (via `modelo describe`)."""

    result = invoke_cached_cli(["app", "modelo", "work", "create", "--help"])
    assert result.exit_code == 0, result.output
    ascii_only = "".join(c for c in result.output if c.isascii())
    collapsed = " ".join(ascii_only.split())
    assert "modelo describe" in collapsed


def test_work_calculate_binding_help_points_at_bindings_list() -> None:
    """The `--binding` option help points the operator at
    `bindings list --missing` to discover required bindings."""

    result = invoke_cached_cli(["app", "modelo", "work", "calculate", "--help"])
    assert result.exit_code == 0, result.output
    # Rich renders panel box-drawing characters that interleave with wrapped
    # text. Strip non-ASCII before collapsing.
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


def test_discovery_bad_parameter_lists_declared_ids_as_facts_not_an_action() -> None:
    """A discovery refusal may list valid IDs; it does not select a CLI action."""
    from .._modelo_behavior_support import bare_period_error

    rendered = bare_period_error("303", "0A")

    assert "0A" in rendered
    assert "1T" in rendered
    assert "4T" in rendered
    assert "aeat" not in rendered.casefold()


def test_work_calculate_missing_m200_m202_relation_prefill_is_advisory(tmp_path) -> None:
    """The live M200 relation-prefill path warns rather than refusing calculation."""

    from ....application.modelo.work_lifecycle import create_work_unit
    from ....core.period import Period
    from ....domain.user_profile.values import UserProfileFact, UserProfileRecord
    from ....tests.profile_capsule import seed_test_profile_record
    from ....tests.secure_sql import isolated_runtime_profile

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="0c200000-0000-4000-8000-000000000002") as runtime:
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=runtime.bucket_id,
                facts=(
                    UserProfileFact(path="identity.tax_id", value="B12345674"),
                    UserProfileFact(path="identity.legal_name", value="M200 Relation Guidance SL"),
                    UserProfileFact(path="activities.description", value="corporate relation guidance"),
                    UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
                    UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
                    UserProfileFact(path="taxpayer_type.incn_prior_12_months", value="500000"),
                    UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value="false"),
                    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                    UserProfileFact(path="iva.regime", value="GENERAL"),
                    UserProfileFact(path="iva.m303_regime_composition", value="general"),
                    UserProfileFact(path="iva.redeme_enrolled", value=False),
                    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                ),
            ),
            root=runtime.storage_root,
            label="M200 relation guidance profile",
        )
        unit = create_work_unit(
            bucket_id=runtime.bucket_id,
            modelo="200",
            filing_year=2024,
            period=Period.from_year_and_code(2024, "0A"),
            revision_id="2024",
        )
        result = invoke_cached_cli(
            [
                "app",
                "modelo",
                "work",
                "calculate",
                unit.work_unit_id,
                "--casilla",
                "00501=100000.00",
                "--casilla",
                "DP200013:00417=0.00",
                "--casilla",
                "DP200013:00418=0.00",
                "--casilla",
                "01032=0.00",
                "--casilla",
                "DP200014:00547=0.00",
                "--casilla",
                "DP200014:01033=0.00",
                "--casilla",
                "DP200014:01034=0.00",
                "--binding",
                "modelo-200-2024-profile-legal-entity-form=sl",
                "--binding",
                "modelo-200-2024-profile-new-entity-flag=0",
                "--binding",
                "modelo-200-2024-profile-incn-prior-12-months=500000",
                "--binding",
                "modelo-200-2024-profile-tributacion-estado-porcentaje=100",
                "--binding",
                "modelo-200-2024-bin-pendiente-ejercicios-anteriores=0",
                "--binding",
                "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
                "--binding",
                "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0",
                "--relation",
                "modelo-200-2024-rel-202-pagos-fraccionados=1800",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    assert "ADVISORY: relation 'modelo-200-2024-rel-202-pagos-fraccionados-40-2' requires modelo 202" in result.output
    assert "source filing is missing or incomplete" in result.output


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


def test_evidence_kind_accepts_canonical_and_hyphenated_values() -> None:
    """``--evidence-kind`` accepts both canonical underscore values and
    their hyphenated aliases (``aeat-justificante-pdf`` ↔ ``aeat_justificante_pdf``).
    The import command parses the alias and normalises it before
    dispatching the application action."""

    from ....domain.modelos.filing_record import ExternalEvidenceKind

    cases = (
        ("aeat_justificante_pdf", "aeat_justificante_pdf"),
        ("aeat-justificante-pdf", "aeat_justificante_pdf"),
        ("aeat_csv_register", "aeat_csv_register"),
        ("aeat-csv-register", "aeat_csv_register"),
        ("aeat_live_capture", "aeat_live_capture"),
        ("aeat-live-capture", "aeat_live_capture"),
    )

    for raw, expected in cases:
        normalised = raw.strip().replace("-", "_")
        assert ExternalEvidenceKind(normalised) is ExternalEvidenceKind(expected)


def test_evidence_kind_rejects_unrelated_token() -> None:
    """``--evidence-kind`` still rejects values that aren't a valid
    enum member after hyphen-to-underscore normalisation."""

    from ....domain.modelos.filing_record import ExternalEvidenceKind

    raw = "aeat_bogus_evidence"
    with pytest.raises(ValueError, match="aeat_bogus_evidence"):
        ExternalEvidenceKind(raw.strip().replace("-", "_"))


# ---------------------------------------------------------------------------
# contract — typed WorkUnitId validation at CLI ingress
# ---------------------------------------------------------------------------


def test_validate_work_unit_id_accepts_valid_hex64_and_strips_whitespace() -> None:
    from .._modelo_cli_support import validate_work_unit_id

    cases = (
        ("plain", "a" * 64, "a" * 64),
        ("trimmed", f"  {'b' * 64}  ", "b" * 64),
    )

    for case_id, raw, expected in cases:
        result = validate_work_unit_id(raw)
        assert result == expected, case_id
        assert isinstance(result, str), case_id


def test_validate_work_unit_id_rejects_malformed() -> None:
    """Malformed work_unit_id values raise ``typer.BadParameter``."""
    import typer as _typer

    from .._modelo_cli_support import validate_work_unit_id

    malformed = (
        "short",
        "G" * 64,  # uppercase -- not lowercase hex
        "z" * 64,  # non-hex character
        "a" * 63,  # one char short
        "a" * 65,  # one char long
        "",
    )

    for bad in malformed:
        with pytest.raises(_typer.BadParameter):
            validate_work_unit_id(bad)


# ---------------------------------------------------------------------------
# contract -- CasillaId / BindingId key validation at CLI ingress
# ---------------------------------------------------------------------------


def test_parse_casilla_override_accepts_valid_keys() -> None:
    """Valid CasillaId keys are accepted by ``parse_casilla_override``."""
    from .._modelo_cli_support import parse_casilla_override

    specs = (
        "A=1",
        "casilla01=2",
        "A.B:C-D=3",
        "x" * 64 + "=0",  # exactly 64-char key
    )

    for spec in specs:
        key, _ = parse_casilla_override(spec)
        assert key, spec


def test_parse_casilla_override_rejects_invalid_keys() -> None:
    """Invalid CasillaId keys raise ``typer.BadParameter``."""
    import typer as _typer

    from .._modelo_cli_support import parse_casilla_override

    specs = (
        "=value",  # empty key
        " A=1",  # casilla.id must be accepted exactly as supplied
        "A =1",  # key-side whitespace must not be stripped into a valid id
        ".starts-with-dot=1",  # dot at start (fails _CASILLA_RE)
        ("x" * 65) + "=0",  # key exceeds 64-char max
    )

    for spec in specs:
        with pytest.raises(_typer.BadParameter):
            parse_casilla_override(spec)


def test_parse_amendment_casilla_rejects_whitespace_padded_keys() -> None:
    """Amendment ``--set`` casilla keys are validated without key coercion."""
    import typer as _typer

    from .._modelo import _parse_amendment_casilla

    for spec in (" 01=1.00", "01 =1.00"):
        with pytest.raises(_typer.BadParameter):
            _parse_amendment_casilla(spec)


def test_parse_amendment_casilla_refuses_non_canonical_amounts() -> None:
    """Amendment ``--set`` amounts conform to the canonical euro grammar.

    Each form here is one the bare ``Decimal`` constructor this replaced really
    does accept, asserted first so the test proves a genuine tightening rather
    than restating the constructor. An amendment restates a casilla on a filed
    declaration, so admitting ``1e3`` (a 1000x misreading of a typo'd ``1e3``),
    ``1.000`` (the Spanish thousands shape silently becoming one euro), or the
    non-finite ``NaN``/``Infinity`` is a filing-grade defect: a ``NaN`` amount
    compares ``False`` to every threshold, so an under-declaration advisory
    keyed on ``> 0`` would never fire for it.
    """
    import typer as _typer

    from .._modelo import _parse_amendment_casilla

    for raw in ("1e3", "1E3", "+140000", "1_000", ".5", "1.", "NaN", "-NaN", "Infinity", "-Infinity", "1.000"):
        assert isinstance(Decimal(raw), Decimal), raw
        with pytest.raises(_typer.BadParameter):
            _parse_amendment_casilla(f"01={raw}")

    # Forms the constructor also rejects must refuse through the same surface
    # rather than escaping as a raw InvalidOperation.
    for raw in ("1.234,56", "36.500,00", "not-decimal", "1 000"):
        with pytest.raises(_typer.BadParameter):
            _parse_amendment_casilla(f"01={raw}")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("140000", Decimal("140000")),
        ("1234.56", Decimal("1234.56")),
        ("0", Decimal("0")),
        ("-1234.56", Decimal("-1234.56")),
        ("  1234.56  ", Decimal("1234.56")),
    ],
)
def test_parse_amendment_casilla_accepts_canonical_amounts(raw: str, expected: Decimal) -> None:
    """The canonical euro form still parses to the exact declared amount."""
    from .._modelo import _parse_amendment_casilla

    _, value = _parse_amendment_casilla(f"01={raw}")
    assert value == expected


def test_parse_binding_override_accepts_valid_keys() -> None:
    """Valid BindingId keys are accepted by ``parse_binding_override``."""
    from .._modelo_cli_support import parse_binding_override

    for spec in ("binding-id=1", "a=v", "modelo-303-iva-repercutido=100"):
        key, _ = parse_binding_override(spec)
        assert key, spec


def test_parse_binding_override_rejects_invalid_keys() -> None:
    """Invalid BindingId keys raise ``typer.BadParameter``."""
    import typer as _typer

    from .._modelo_cli_support import parse_binding_override

    specs = (
        "=value",  # empty key
        "UPPERCASE=1",  # uppercase not in _REF_RE
        ".starts-dot=1",  # starts with dot
        ("x" * 129) + "=0",  # key exceeds 128-char max
    )

    for spec in specs:
        with pytest.raises(_typer.BadParameter):
            parse_binding_override(spec)
