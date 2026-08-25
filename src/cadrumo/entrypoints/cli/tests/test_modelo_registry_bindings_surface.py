"""Modelo registry bindings CLI surface tests."""

from __future__ import annotations

import pytest

from ....core.directory_scan import scan_directory
from ....core.resources import resources
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke_in_english(args, **kwargs):
    """Invoke the CLI with the output language pinned to English.

    Several columns rendered by this surface are catalogue text, so asserting an
    English phrase against the Spanish default fails on correct behaviour.
    """
    from ....core.config import override_settings

    with override_settings(cadrumo_output_language="en"):
        return invoke_cached_cli(args, **kwargs)


def test_bindings_list_emits_readiness_and_borrador_columns_per_row() -> None:
    """``bindings list`` enriches each binding row with a readiness
    category from the closed set (ledger source / profile fact /
    prior filed revision / live observation / bucket / waiver /
    blocking finding / casilla), and reports the ``borrador_capable``
    flag per binding so callers can identify AEAT-prefilled casillas."""
    # The readiness column is catalogue text -- the payload field is built with
    # tr() -- and the default output language is Spanish, so the language is
    # pinned rather than assumed.

    result = _invoke_in_english(
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


def test_bindings_list_warns_when_period_scope_filters_are_missing() -> None:
    """Unscoped binding ids are discoverable but unsafe to copy into work calculate."""

    text = invoke_cached_cli(["--language", "en", "app", "modelo", "bindings", "list", "--modelo", "303"])

    assert text.exit_code == 0, text.output
    assert "binding_count\t" in text.output
    assert (
        "notice\twarning\tmodelo.bindings.list.unscoped_revision\tThe binding list is not scoped by --year, --period;"
    ) in text.output
    assert "action_target=modelo.bindings.list\taction_bindings=modelo=303" in text.output

    json_result = invoke_cached_cli(
        ["--language", "en", "--format", "json", "app", "modelo", "bindings", "list", "--modelo", "303"],
    )

    assert json_result.exit_code == 0, json_result.output
    notices = _notices(json_result.output)
    (notice,) = [item for item in notices if item["code"] == "modelo.bindings.list.unscoped_revision"]
    assert notice["severity"] == "warning"
    assert notice["context"]["modelo_filter"] == "303"
    assert notice["context"]["year_filter"] == ""
    assert notice["context"]["period_filter"] == ""
    assert notice["context"]["missing_filters"] == "--year, --period"
    assert "work calculate" in notice["message"]
    assert notice["action"]["action"] == {
        "action_id": "operator.modelo.bindings.list",
        "target_command_key": "modelo.bindings.list",
        "cli_path": ["app", "modelo", "bindings", "list"],
    }
    assert notice["action"]["argument_bindings"] == [
        {
            "argument_name": "modelo",
            "status": "resolved",
            "value": "303",
            "source": "operator_action.verdict_context",
            "source_key": "modelo",
            "source_evidence_id": None,
        },
    ]


def test_bindings_list_warning_names_only_the_missing_scope_filter() -> None:
    """Partially scoped listings keep the same warning but name only the missing filter."""

    result = invoke_cached_cli(
        [
            "--language",
            "en",
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "303",
            "--year",
            "2026",
        ],
    )

    assert result.exit_code == 0, result.output
    notices = _notices(result.output)
    (notice,) = [item for item in notices if item["code"] == "modelo.bindings.list.unscoped_revision"]
    assert notice["context"]["modelo_filter"] == "303"
    assert notice["context"]["year_filter"] == "2026"
    assert notice["context"]["period_filter"] == ""
    assert notice["context"]["missing_filters"] == "--period"
    assert {binding["argument_name"]: binding["value"] for binding in notice["action"]["argument_bindings"]} == {
        "modelo": "303",
        "year": 2026,
    }


def test_bindings_list_omits_scope_warning_when_year_and_period_are_supplied() -> None:
    """The scoped listing already matches the work-unit revision resolver inputs."""

    result = invoke_cached_cli(
        [
            "--language",
            "en",
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "1T",
        ],
    )

    assert result.exit_code == 0, result.output
    scope_notices = [
        notice for notice in _notices(result.output) if notice["code"] == "modelo.bindings.list.unscoped_revision"
    ]
    assert scope_notices == []


def test_bindings_list_missing_m200_surfaces_m202_relation_inputs() -> None:
    """M200 missing-input discovery names the feeding relation id of each relation-fed binding.

    The guidance is registry-derived (each
    :class:`~cadrumo.domain.calculations.registry.RelationDefinition` declares
    its ``target_binding``), so the discovery generalises to any modelo
    rather than enumerating a hardcoded M200 channel table.
    """

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
            "2025",
            "--period",
            "0A",
            "--missing",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "missing_filter\tTrue" in result.output
    assert "\tmodelo-200-2024-pagos-fraccionados-anuales\trelation_prefill\trelation input\t" in result.output
    assert "\tmodelo-200-2024-pagos-fraccionados-anuales-40-2\trelation_prefill\trelation input\t" in result.output
    assert "relation_guidance\tSome bindings below are fed by registry relations" in result.output
    assert "--relation RELATION_ID=VALUE before calculating." in result.output
    assert (
        "relation_input\tmodelo-200-2024-pagos-fraccionados-anuales\t"
        "fed by relation modelo-200-2024-rel-202-pagos-fraccionados\t"
        "use --relation modelo-200-2024-rel-202-pagos-fraccionados=VALUE"
    ) in result.output
    assert (
        "relation_input\tmodelo-200-2024-pagos-fraccionados-anuales-40-2\t"
        "fed by relation modelo-200-2024-rel-202-pagos-fraccionados-40-2\t"
        "use --relation modelo-200-2024-rel-202-pagos-fraccionados-40-2=VALUE"
    ) in result.output


def test_bindings_list_missing_m202_scopes_self_relation_guidance_by_target_period() -> None:
    """M202 previous-installment guidance names only relation ids active for the target period."""

    one_p = invoke_cached_cli(
        [
            "--language",
            "en",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "202",
            "--year",
            "2024",
            "--period",
            "1P",
            "--missing",
        ],
    )
    assert one_p.exit_code == 0, one_p.output
    assert "binding_count\t0" in one_p.output
    assert "modelo-202-2023-2024-pagos-fraccionados-anteriores" not in one_p.output
    assert "modelo-202-2023-2024-rel-self-pagos-2p" not in one_p.output
    assert "modelo-202-2023-2024-rel-self-pagos-3p" not in one_p.output

    two_p = invoke_cached_cli(
        [
            "--language",
            "en",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "202",
            "--year",
            "2024",
            "--period",
            "2P",
            "--missing",
        ],
    )
    assert two_p.exit_code == 0, two_p.output
    assert "modelo-202-2023-2024-rel-self-pagos-2p" in two_p.output
    assert "modelo-202-2023-2024-rel-self-pagos-3p" not in two_p.output

    three_p = invoke_cached_cli(
        [
            "--language",
            "en",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "202",
            "--year",
            "2024",
            "--period",
            "3P",
            "--missing",
        ],
    )
    assert three_p.exit_code == 0, three_p.output
    assert "modelo-202-2023-2024-rel-self-pagos-2p" not in three_p.output
    assert "modelo-202-2023-2024-rel-self-pagos-3p" in three_p.output


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
            "2025",
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
    row = next(item for item in payload["bindings"] if item["binding_id"] == "modelo-303-iva-repercutido-general-cuota")
    assert row["override"] == "1234.56"


def test_bindings_list_and_resolve_localise_distinct_registry_source_semantics() -> None:
    """Real list and resolve leaves preserve distinct source meanings in Spanish."""

    listed = invoke_cached_cli(
        [
            "--language",
            "es",
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "200",
            "--year",
            "2025",
            "--period",
            "0A",
        ],
    )
    assert listed.exit_code == 0, listed.output
    relation_rows = [row for row in _payload(listed.output)["bindings"] if row["source"] == "relation_prefill"]
    assert relation_rows
    assert {row["readiness"] for row in relation_rows} == {"entrada de relación"}

    resolved = invoke_cached_cli(
        [
            "--language",
            "es",
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
        ],
    )
    assert resolved.exit_code == 0, resolved.output
    ledger_rows = [row for row in _payload(resolved.output)["bindings"] if row["source"] == "ledger_iva_aggregation"]
    assert ledger_rows
    assert {row["readiness"] for row in ledger_rows} == {"datos del libro"}


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


def test_no_parallel_bindings_typer_outside_canonical_module() -> None:
    """The canonical ``bindings`` sub-Typer registration lives in
    ``_modelo.py``. Any other module that re-implements a Typer
    named ``bindings`` competes with the canonical surface and must
    be removed."""

    from pathlib import Path

    from ....tests import REPO_ROOT

    cli_root = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli"
    canonical = cli_root / "_modelo.py"
    forbidden_patterns = (
        'typer.Typer(\n    name="bindings"',
        'typer.Typer(name="bindings"',
    )
    offenders: list[Path] = []
    scanned = 0
    for py_file in scan_directory(cli_root, pattern="*.py", recursive=True):
        if py_file == canonical:
            continue
        if py_file.name.startswith("test_"):
            continue
        scanned += 1
        text = py_file.read_text(encoding="utf-8")
        if any(needle in text for needle in forbidden_patterns):
            offenders.append(py_file)
    assert scanned > 100, (
        f"scanned only {scanned} CLI modules under {cli_root}; the scan corpus collapsed (a "
        "package relocation or rename), so an empty offender list would mean 'nothing was "
        "checked' rather than 'nothing is wrong'"
    )
    assert offenders == [], f"Parallel bindings Typer outside the canonical _modelo.py: {[str(p) for p in offenders]}"


def test_bindings_list_and_resolve_emit_no_bucket_event() -> None:
    """``bindings list`` and ``bindings resolve`` are read-only -
    they must not trigger any bucket event.

    The boundary check inspects the canonical module's source for
    any bucket-event emission call. If a future change wires one
    in by accident, this test fails fast."""

    from ....tests import REPO_ROOT

    canonical_text = (REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli" / "_modelo.py").read_text(encoding="utf-8")
    forbidden_emitters = (
        "emit_bucket_event",
        "emit_modelo_bucket_event",
        "append_bucket_event",
        "bucket_event(",
    )
    for needle in forbidden_emitters:
        assert needle not in canonical_text, (
            f"Forbidden bucket-event emission pattern {needle!r} found in "
            "_modelo.py; bindings list/resolve must remain read-only."
        )


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
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "100",
            "--year",
            "2025",
            "--period",
            "0A",
        ],
    )
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


def test_bindings_list_exposes_m100_salary_certificate_withholding_input() -> None:
    """An operator's suffered salary withholding is discoverable as a public binding."""
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "0A",
        ],
    )
    assert result.exit_code == 0, result.output
    rows = {row["binding_id"]: row for row in _payload(result.output)["bindings"]}
    row = rows["renta-2024-certificado-trabajo-retenciones"]
    assert row["source"] == "manual_input"
    assert row["input_channel"] == "decimal"
    assert "ley-35-2006:art-101" in row["legal_refs"]
    assert "aeat-dr-100-2024-dictionary" in row["source_refs"]


def test_bindings_list_typed_payload_carries_relation_inputs_before_calculate() -> None:
    """The typed M200 list payload names each relation-fed binding's feeding relation.

    Issue #556: the M202 pagos-fraccionados inputs that Modelo 200's
    annual settlement folds in were previously discoverable only by
    triggering a failing ``calculate``. The typed ``bindings list``
    payload now carries ``relation_inputs`` -- the registry relation ids
    whose ``target_binding`` is the row's binding -- so a relation-fed
    binding's source is discoverable in the listing ahead of any
    calculation. The mapping is derived from the resolved revision
    (``RelationDefinition.target_binding``), not a per-form table, so it
    generalises to every modelo.
    """
    # The readiness column is catalogue text -- the payload field is built with
    # tr() -- and the default output language is Spanish, so the language is
    # pinned rather than assumed.
    scope = ["--modelo", "200", "--year", "2025", "--period", "0A"]
    result = _invoke_in_english(["--format", "json", "app", "modelo", "bindings", "list", *scope])
    assert result.exit_code == 0, result.output
    rows = {row["binding_id"]: row for row in _payload(result.output)["bindings"]}

    # Cross-check against the authoritative snapshot: every relation's
    # target_binding must surface that relation id on the listed binding row.
    snapshot = resources().modelos.authority.snapshot("200", filing_year=2025, period="0A")
    expected: dict[str, set[str]] = {}
    for relation in snapshot.revision.relations:
        expected.setdefault(str(relation.target_binding), set()).add(str(relation.id))
    assert expected, "Modelo 200 declares relations feeding bindings; fixture must exercise them"

    for binding_id, relation_ids in expected.items():
        assert binding_id in rows, f"relation target binding {binding_id!r} absent from listing"
        emitted = set(rows[binding_id]["relation_inputs"])
        assert emitted == relation_ids, (binding_id, sorted(emitted), sorted(relation_ids))
        assert rows[binding_id]["source"] == "relation_prefill"
        assert rows[binding_id]["readiness"] == "relation input"

    # The specific M202 pagos-fraccionados fold-ins from the audit are present.
    assert (
        "modelo-200-2024-rel-202-pagos-fraccionados"
        in rows["modelo-200-2024-pagos-fraccionados-anuales"]["relation_inputs"]
    )

    # A non-relation-fed binding carries an empty relation_inputs tuple.
    non_relation = [r for r in rows.values() if r["source"] != "relation_prefill"]
    assert non_relation, "Modelo 200 has non-relation bindings to prove the negative case"
    assert all(r["relation_inputs"] == [] for r in non_relation)
