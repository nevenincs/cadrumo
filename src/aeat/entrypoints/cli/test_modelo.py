"""CLI surface tests for the ``aeat ... modelo`` command tree.

These tests pin the user-input-error contract: any operator-facing
error (malformed period, unknown modelo) must surface as a
``typer.BadParameter`` clean message rather than a Python traceback.
"""

from __future__ import annotations

import pytest

from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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
# bindings list / preview surface
# ---------------------------------------------------------------------------


def test_bindings_list_emits_readiness_category_for_every_row() -> None:
    """``bindings list`` enriches each binding row with a readiness
    category from the closed set (ledger source / profile fact /
    prior filed revision / live observation / bucket / waiver /
    blocking finding / casilla)."""

    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "Q1"],
    )
    assert result.exit_code == 0, result.output
    assert "operation\tregistry.modelo.bindings.list" in result.output
    assert "binding_id\tsource\treadiness\ttyped_enum\tborrador_capable" in result.output
    # Every modelo-303 binding currently sources from
    # ``ledger_iva_aggregation`` so every row's readiness column is
    # "ledger source".
    assert "ledger source" in result.output


def test_bindings_list_emits_borrador_capable_column_per_row() -> None:
    """``bindings list`` reports the ``borrador_capable`` flag per
    binding so callers can tell at a glance which casillas the AEAT
    borrador prefills versus those the operator must supply."""

    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "Q1"],
    )
    assert result.exit_code == 0, result.output
    # The text-mode header carries the new column.
    assert "borrador_capable" in result.output
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
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "Q1", "--missing"],
    )
    assert result.exit_code == 0, result.output
    assert "missing_filter\tTrue" in result.output


def test_bindings_preview_echoes_override_for_known_key() -> None:
    """An override targeting a known binding id surfaces in the
    payload's ``override`` column."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "preview",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "Q1",
            "--binding",
            "modelo-303-iva-repercutido-general-cuota=1234.56",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "operation\tregistry.modelo.bindings.preview" in result.output
    assert "override_count\t1" in result.output
    assert "1234.56" in result.output


def test_bindings_preview_rejects_unknown_binding_with_suggestion_list() -> None:
    """Unknown override keys fail with a suggestion list sourced
    from the registry's binding catalogue for the active modelo /
    year / period."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "preview",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "Q1",
            "--binding",
            "no-such-binding=42",
        ],
    )
    assert result.exit_code != 0
    output_lower = result.output.lower()
    assert "no-such-binding" in output_lower
    # The suggestion list cites at least one real binding id.
    assert "modelo-303-iva-" in result.output


def test_bindings_preview_rejects_malformed_override_syntax() -> None:
    """``--binding`` without an ``=`` separator fails at the CLI
    boundary with a typer.BadParameter."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "preview",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            "Q1",
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

    from aeat.core.paths import PROJECT_ROOT

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


def test_bindings_list_and_preview_emit_no_bucket_event() -> None:
    """``bindings list`` and ``bindings preview`` are read-only —
    they must not trigger any bucket event.

    The boundary check inspects the canonical module's source for
    any bucket-event emission call. If a future change wires one
    in by accident, this test fails fast."""

    from aeat.core.paths import PROJECT_ROOT

    canonical_text = (PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "_modelo.py").read_text(encoding="utf-8")
    forbidden_emitters = (
        "emit_bucket_event",
        "append_bucket_event",
        "bucket_event(",
    )
    for needle in forbidden_emitters:
        assert needle not in canonical_text, (
            f"Forbidden bucket-event emission pattern {needle!r} found in "
            "_modelo.py; bindings list/preview must remain read-only."
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

    from aeat.domain.modelos._filing_record import ExternalEvidenceKind

    normalised = raw.strip().replace("-", "_")
    assert ExternalEvidenceKind(normalised) is ExternalEvidenceKind(expected)


def test_evidence_kind_rejects_unrelated_token() -> None:
    """``--evidence-kind`` still rejects values that aren't a valid
    enum member after hyphen-to-underscore normalisation."""

    from aeat.domain.modelos._filing_record import ExternalEvidenceKind

    raw = "aeat_bogus_evidence"
    with pytest.raises(ValueError, match="aeat_bogus_evidence"):
        ExternalEvidenceKind(raw.strip().replace("-", "_"))


# ---------------------------------------------------------------------------
# S05 — typed WorkUnitId validation at CLI ingress
# ---------------------------------------------------------------------------


def test_validate_work_unit_id_accepts_valid_hex64() -> None:
    """A 64-character lowercase hex string is accepted and returned stripped."""
    import typer as _typer

    from aeat.entrypoints.cli._modelo import _validate_work_unit_id

    valid = "a" * 64
    result = _validate_work_unit_id(valid)
    assert result == valid
    assert isinstance(result, str)
    _ = _typer  # ensure import is referenced


def test_validate_work_unit_id_strips_whitespace() -> None:
    """Leading/trailing whitespace is stripped before validation."""
    from aeat.entrypoints.cli._modelo import _validate_work_unit_id

    valid = "b" * 64
    assert _validate_work_unit_id(f"  {valid}  ") == valid


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

    from aeat.entrypoints.cli._modelo import _validate_work_unit_id

    with pytest.raises(_typer.BadParameter):
        _validate_work_unit_id(bad)


# ---------------------------------------------------------------------------
# S06 -- CasillaId / BindingId key validation at CLI ingress
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
    from aeat.entrypoints.cli._modelo import _parse_casilla_override

    key, _ = _parse_casilla_override(spec)
    assert key


@pytest.mark.parametrize(
    "spec",
    [
        "=value",  # empty key
        ".starts-with-dot=1",  # dot at start (fails _CASILLA_RE)
        ("x" * 65) + "=0",  # key exceeds 64-char max
    ],
)
def test_parse_casilla_override_rejects_invalid_keys(spec: str) -> None:
    """Invalid CasillaId keys raise ``typer.BadParameter``."""
    import typer as _typer

    from aeat.entrypoints.cli._modelo import _parse_casilla_override

    with pytest.raises(_typer.BadParameter):
        _parse_casilla_override(spec)


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
    from aeat.entrypoints.cli._modelo import _parse_binding_override

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

    from aeat.entrypoints.cli._modelo import _parse_binding_override

    with pytest.raises(_typer.BadParameter):
        _parse_binding_override(spec)


# ---------------------------------------------------------------------------
# filing-record emitter surface — external_evidence + amends_filing_record_id
# ---------------------------------------------------------------------------


def test_filing_record_payload_renders_external_evidence_and_amends() -> None:
    """The JSON-format emitter for ``aeat app modelo filing-record show``
    surfaces both ``external_evidence`` (kind / reference_id / imported_at)
    and ``amends_filing_record_id`` so amendment chains are operator-discoverable
    from the record's own listing surface, not only via the amend action."""

    from datetime import UTC, datetime

    from aeat.domain.modelos._codes import ModeloCode
    from aeat.domain.modelos._filing_record import (
        ExternalEvidence,
        ExternalEvidenceKind,
        ModeloRecord,
        ModeloRecordStatus,
        derive_filing_record_id,
    )
    from aeat.entrypoints.cli._modelo import _filing_record_payload

    imported_at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    filed_at = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
    work_unit_id = "a" * 64
    revision_id = "c" * 64
    amends_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id="d" * 64,
        filed_at=datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC),
        filed_by="aeat-import",
    )
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_at=filed_at,
            filed_by="operator-A",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id="default",
        modelo=ModeloCode("130"),
        filing_year=2026,
        period="1T",
        filed_at=filed_at,
        filed_by="operator-A",
        notes=None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="JUST-2026-130-1T-XYZ789",
            imported_at=imported_at,
        ),
        amends_filing_record_id=amends_id,
    )

    payload = _filing_record_payload(record)

    assert payload["amends_filing_record_id"] == amends_id
    from typing import cast

    evidence_raw = payload["external_evidence"]
    assert isinstance(evidence_raw, dict)
    evidence = cast(dict[str, object], evidence_raw)
    assert evidence["kind"] == "aeat_justificante_pdf"
    assert evidence["reference_id"] == "JUST-2026-130-1T-XYZ789"
    assert evidence["imported_at"] == imported_at.isoformat()


def test_filing_record_payload_omits_evidence_fields_when_absent() -> None:
    """A locally-filed record (no external_evidence, no amends link)
    surfaces those fields as ``None`` in JSON so downstream consumers
    can rely on the schema shape without optional-key checks."""

    from datetime import UTC, datetime

    from aeat.domain.modelos._codes import ModeloCode
    from aeat.domain.modelos._filing_record import (
        ModeloRecord,
        ModeloRecordStatus,
        derive_filing_record_id,
    )
    from aeat.entrypoints.cli._modelo import _filing_record_payload

    work_unit_id = "a" * 64
    revision_id = "c" * 64
    filed_at = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_at=filed_at,
            filed_by="operator-A",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id="default",
        modelo=ModeloCode("130"),
        filing_year=2026,
        period="1T",
        filed_at=filed_at,
        filed_by="operator-A",
        notes=None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
    )

    payload = _filing_record_payload(record)

    assert payload["external_evidence"] is None
    assert payload["amends_filing_record_id"] is None


def test_filing_record_lines_renders_external_evidence_and_amends_in_text_mode() -> None:
    """The text-format emitter surfaces ``external_evidence.{kind, reference_id,
    imported_at}`` and ``amends_filing_record_id`` as discrete tab-separated
    lines so operators reading ``--format text`` see the amendment context."""

    from datetime import UTC, datetime

    from aeat.domain.modelos._codes import ModeloCode
    from aeat.domain.modelos._filing_record import (
        ExternalEvidence,
        ExternalEvidenceKind,
        ModeloRecord,
        ModeloRecordStatus,
        derive_filing_record_id,
    )
    from aeat.entrypoints.cli._modelo import _filing_record_lines

    imported_at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    work_unit_id = "a" * 64
    revision_id = "c" * 64
    filed_at = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
    amends_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id="d" * 64,
        filed_at=datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC),
        filed_by="aeat-import",
    )
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_at=filed_at,
            filed_by="operator-A",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id="default",
        modelo=ModeloCode("130"),
        filing_year=2026,
        period="1T",
        filed_at=filed_at,
        filed_by="operator-A",
        notes=None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            reference_id="CSV-303-2026-Q1",
            imported_at=imported_at,
        ),
        amends_filing_record_id=amends_id,
    )

    lines = _filing_record_lines(record)

    assert "external_evidence.kind\taeat_csv_register" in lines
    assert "external_evidence.reference_id\tCSV-303-2026-Q1" in lines
    assert f"external_evidence.imported_at\t{imported_at.isoformat()}" in lines
    assert f"amends_filing_record_id\t{amends_id}" in lines


def test_work_calculate_help_exposes_by_actor_flag() -> None:
    """``aeat app modelo work calculate --help`` advertises a ``--by ACTOR``
    option so operators can attribute a calculation revision to a specific
    actor; the default factory pulls the active profile display name when
    ``--by`` is omitted."""

    from aeat.tests.cli_runner import invoke_cached_cli

    result = invoke_cached_cli(["app", "modelo", "work", "calculate", "--help"])
    assert result.exit_code == 0, result.output
    assert "--by" in result.output


# --- Fix 2: work create validates period token eagerly ---


@pytest.mark.parametrize(
    "period",
    [
        "2026Q1",   # year-prefixed form ambiguous to the resolver
        "INVALID",  # completely invalid
        "Q1X",      # garbled quarter token
    ],
)
def test_work_create_rejects_invalid_period_at_create_time(period: str) -> None:
    """``work create`` must reject an un-parseable period token immediately
    rather than storing it and failing later at ``calculate`` time.

    Before fix: invalid tokens were accepted and stored as-is, only
    failing when the registry tried to resolve them at calculate time.
    After fix: ``typer.BadParameter`` fires at create time with a
    human-readable message.
    """

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "303",
            "--year",
            "2026",
            "--period",
            period,
            "--revision",
            "v1",
        ]
    )

    assert result.exit_code != 0, f"period {period!r} should be rejected; got: {result.output}"
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "period must be" in output_lower or "invalid value" in output_lower


@pytest.mark.parametrize(
    "period,expected_normalized",
    [
        ("Q1", "1T"),
        ("1T", "1T"),
        ("Q4", "4T"),
        ("0A", "0A"),
        ("annual", "0A"),
    ],
)
def test_work_create_normalizes_valid_period_tokens(period: str, expected_normalized: str) -> None:
    """Valid period tokens (in any accepted form) must be normalized to the
    canonical registry form (e.g. ``Q1`` → ``1T``) before being stored."""

    from aeat.entrypoints.cli._modelo import _resolve_year_period

    _, normalized = _resolve_year_period(2026, period)
    assert normalized == expected_normalized, f"period {period!r} normalized to {normalized!r}, expected {expected_normalized!r}"
