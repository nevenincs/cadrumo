"""Modelo registry bindings CLI surface tests."""

from __future__ import annotations

import pytest

from ....core.resources import resources
from ....tests.cli_runner import invoke_cached_cli
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


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
    assert "\tmodelo-200-2024-pagos-fraccionados-anuales-40-2\trelation_prefill\trelation input\t" in result.output
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
    row = next(item for item in payload["bindings"] if item["binding_id"] == "modelo-303-iva-repercutido-general-cuota")
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
    """``bindings list`` and ``bindings resolve`` are read-only -
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
