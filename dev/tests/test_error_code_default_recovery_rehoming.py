from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

import pytest

from dev.quality.error_code_default_recovery_rehoming import (
    DEFAULT_REHOMING_LEDGER_PATH,
    DispositionKind,
    FingerprintOwnership,
    RehomingLedgerError,
    SourceFingerprint,
    _current_plan_steps,
    current_source_fingerprints,
    load_rehoming_ledger,
    validate_rehoming_ledger,
)
from dev.quality.error_code_default_suggestion_preimage_ledger import (
    load_preimage_ledger,
    validate_preimage_ledger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _historical_non_null_identities() -> set[tuple[str, str, str, str, str, int, int]]:
    records = validate_preimage_ledger(load_preimage_ledger())
    return {
        record.source_identity
        for record in records
        if not (
            isinstance((expression := ast.parse(record.old_value_source, mode="eval").body), ast.Constant)
            and expression.value is None
        )
    }


def _write_ledger(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _ownership_line(ownership: FingerprintOwnership) -> str:
    fingerprint = ownership.fingerprint
    return (
        "  { "
        f"path = {json.dumps(fingerprint.path, ensure_ascii=False)}, "
        f"lexical_owner = {json.dumps(fingerprint.lexical_owner, ensure_ascii=False)}, "
        f"role = {json.dumps(fingerprint.role, ensure_ascii=False)}, "
        f"ast_format = {json.dumps(fingerprint.ast_format, ensure_ascii=False)}, "
        f"normalized_ast_sha256 = {json.dumps(fingerprint.normalized_ast_sha256, ensure_ascii=False)}, "
        f"identical_site_ordinal = {fingerprint.identical_site_ordinal}, "
        f"line = {fingerprint.line}, "
        f"column = {fingerprint.column}, "
        f"end_line = {fingerprint.end_line}, "
        f"end_column = {fingerprint.end_column}, "
        f"owner_step = {json.dumps(ownership.owner_step, ensure_ascii=False)} "
        "},\n"
    )


def _live_ownership_with_multiple_row() -> FingerprintOwnership:
    ledger = load_rehoming_ledger()
    row = next(row for row in ledger.rows if len(row.ownerships) > 1)
    return row.ownerships[0]


def test_checked_rehoming_ledger_passes_every_validator_rule() -> None:
    """The packaged ledger satisfies the validator itself, not a partial restatement.

    The sibling test below re-derives part of the join inline. That inline
    restatement can only agree with the validator by coincidence, and every
    rule with no inline counterpart -- owner scope, owner overlap,
    current-unjoined, and the disposition guards -- would be unenforced by this
    suite. Calling the validator is what makes those rules bite here.
    """
    validate_rehoming_ledger(load_rehoming_ledger())


def test_checked_rehoming_ledger_is_an_exact_live_source_join() -> None:
    ledger = load_rehoming_ledger()
    current = current_source_fingerprints()

    assert {row.historical.source_identity for row in ledger.rows} == _historical_non_null_identities()
    assert {row.current_error_qualname for row in ledger.rows if row.current_error_qualname is not None} == set(current)
    assert any(
        any(fingerprint.role == "constructor" for fingerprint in fingerprints) for fingerprints in current.values()
    )
    assert any(
        fingerprints and all(fingerprint.role == "reference" for fingerprint in fingerprints)
        for fingerprints in current.values()
    )

    for row in ledger.rows:
        fingerprints = current.get(row.historical.error_qualname, ())
        if fingerprints:
            assert row.disposition_kind is not DispositionKind.RETIRED_OR_UNREACHABLE
            assert row.current_error_qualname == row.historical.error_qualname
            assert tuple(ownership.fingerprint.identity for ownership in row.ownerships) == tuple(
                fingerprint.identity for fingerprint in fingerprints
            )
            assert all(ownership.owner_step.startswith("S") for ownership in row.ownerships)
        else:
            assert row.disposition_kind is DispositionKind.RETIRED_OR_UNREACHABLE
            assert row.current_error_qualname is None
            assert not row.ownerships


def test_rehoming_ledger_accepts_locator_metadata_drift(tmp_path: Path) -> None:
    ledger = load_rehoming_ledger()
    row = next(row for row in ledger.rows if row.ownerships)
    fingerprint = row.ownerships[0].fingerprint
    source = DEFAULT_REHOMING_LEDGER_PATH.read_text(encoding="utf-8")
    line = _ownership_line(row.ownerships[0])
    assert source.count(line) == 1
    drifted = source.replace(
        line,
        line.replace(
            f"line = {fingerprint.line}, column = {fingerprint.column}, end_line = {fingerprint.end_line}, "
            f"end_column = {fingerprint.end_column}",
            (
                f"line = {fingerprint.line + 1}, column = {fingerprint.column + 1}, "
                f"end_line = {fingerprint.end_line + 1}, end_column = {fingerprint.end_column + 1}"
            ),
        ),
        1,
    )
    drifted_path = _write_ledger(tmp_path, "drifted-rehoming.toml", drifted)

    validate_rehoming_ledger(load_rehoming_ledger(drifted_path))


def test_rehoming_ledger_rejects_forbidden_legacy_current_fields(tmp_path: Path) -> None:
    source = DEFAULT_REHOMING_LEDGER_PATH.read_text(encoding="utf-8")
    legacy = source.replace("ownerships = [", 'current_owner_step = "S999999"\nownerships = [', 1)
    path = _write_ledger(tmp_path, "legacy-field.toml", legacy)

    with pytest.raises(RehomingLedgerError) as raised:
        load_rehoming_ledger(path)

    assert "current_owner_step" in raised.value.errors[0]


def test_rehoming_ledger_rejects_missing_extra_and_duplicate_structural_ownerships(tmp_path: Path) -> None:
    ownership = _live_ownership_with_multiple_row()
    source = DEFAULT_REHOMING_LEDGER_PATH.read_text(encoding="utf-8")
    line = _ownership_line(ownership)
    assert source.count(line) == 1
    missing = _write_ledger(tmp_path, "missing-ownership.toml", source.replace(line, "", 1))
    extra_line = line.replace(
        f"identical_site_ordinal = {ownership.fingerprint.identical_site_ordinal}",
        f"identical_site_ordinal = {ownership.fingerprint.identical_site_ordinal + 1}",
    )
    extra = _write_ledger(tmp_path, "extra-ownership.toml", source.replace(line, f"{line}{extra_line}", 1))
    duplicate = _write_ledger(tmp_path, "duplicate-ownership.toml", source.replace(line, f"{line}{line}", 1))

    with pytest.raises(RehomingLedgerError, match="E_REHOMING_FINGERPRINT_MULTISET"):
        validate_rehoming_ledger(load_rehoming_ledger(missing))
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_FINGERPRINT_MULTISET"):
        validate_rehoming_ledger(load_rehoming_ledger(extra))
    with pytest.raises(RehomingLedgerError) as raised:
        load_rehoming_ledger(duplicate)
    assert "ownerships" in raised.value.errors[0]
    assert "duplicates" in raised.value.errors[0]


def test_rehoming_ledger_rejects_structural_role_owner_and_semantic_hash_drift(tmp_path: Path) -> None:
    ownership = _live_ownership_with_multiple_row()
    source = DEFAULT_REHOMING_LEDGER_PATH.read_text(encoding="utf-8")
    line = _ownership_line(ownership)
    role = _write_ledger(
        tmp_path,
        "role-drift.toml",
        source.replace('role = "constructor"', 'role = "reference"', 1),
    )
    owner = _write_ledger(
        tmp_path,
        "lexical-owner-drift.toml",
        source.replace(
            f"lexical_owner = {json.dumps(ownership.fingerprint.lexical_owner)}",
            'lexical_owner = "cadrumo.structural.owner"',
            1,
        ),
    )
    semantic = _write_ledger(
        tmp_path,
        "semantic-hash-drift.toml",
        source.replace(
            f'normalized_ast_sha256 = "{ownership.fingerprint.normalized_ast_sha256}"',
            'normalized_ast_sha256 = "0000000000000000000000000000000000000000000000000000000000000000"',
            1,
        ),
    )
    assert source.count(line) == 1

    for path in (role, owner, semantic):
        with pytest.raises(RehomingLedgerError, match="E_REHOMING_FINGERPRINT_MULTISET"):
            validate_rehoming_ledger(load_rehoming_ledger(path))


def test_rehoming_ledger_rejects_invalid_structural_format_hash_and_duplicate_identity(tmp_path: Path) -> None:
    ownership = _live_ownership_with_multiple_row()
    source = DEFAULT_REHOMING_LEDGER_PATH.read_text(encoding="utf-8")
    line = _ownership_line(ownership)
    invalid_format = _write_ledger(
        tmp_path,
        "invalid-ast-format.toml",
        source.replace('ast_format = "recovery-ast-v1"', 'ast_format = "recovery-ast-v2"', 1),
    )
    invalid_hash = _write_ledger(
        tmp_path,
        "invalid-hash.toml",
        source.replace(
            f'normalized_ast_sha256 = "{ownership.fingerprint.normalized_ast_sha256}"',
            'normalized_ast_sha256 = "not-a-hash"',
            1,
        ),
    )
    duplicate_identity = _write_ledger(
        tmp_path,
        "duplicate-structural-identity.toml",
        source.replace(
            line,
            line.replace(
                f"line = {ownership.fingerprint.line}",
                f"line = {ownership.fingerprint.line + 1}",
            )
            + line,
            1,
        ),
    )

    for path in (invalid_format, invalid_hash, duplicate_identity):
        with pytest.raises(RehomingLedgerError):
            load_rehoming_ledger(path)


def test_rehoming_ledger_rejects_unknown_and_closed_ownerships(tmp_path: Path) -> None:
    ownership = _live_ownership_with_multiple_row()
    source = DEFAULT_REHOMING_LEDGER_PATH.read_text(encoding="utf-8")
    line = _ownership_line(ownership)
    unknown = _write_ledger(
        tmp_path,
        "unknown-owner.toml",
        source.replace(line, line.replace(ownership.owner_step, "S999999"), 1),
    )
    closed_step = next(step.step_id for step in _current_plan_steps() if step.checked)
    closed = _write_ledger(
        tmp_path,
        "closed-owner.toml",
        source.replace(line, line.replace(ownership.owner_step, closed_step), 1),
    )

    with pytest.raises(RehomingLedgerError, match="E_REHOMING_OWNER_UNKNOWN"):
        validate_rehoming_ledger(load_rehoming_ledger(unknown))
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_OWNER_CLOSED"):
        validate_rehoming_ledger(load_rehoming_ledger(closed))


def test_rehoming_ledger_rejects_an_open_owner_outside_the_fingerprint_scope(tmp_path: Path) -> None:
    ledger = load_rehoming_ledger()
    ownership = _live_ownership_with_multiple_row()
    foreign_owner = next(
        candidate.owner_step
        for row in ledger.rows
        for candidate in row.ownerships
        if candidate.owner_step != ownership.owner_step
    )
    source = DEFAULT_REHOMING_LEDGER_PATH.read_text(encoding="utf-8")
    line = _ownership_line(ownership)
    path = _write_ledger(
        tmp_path,
        "out-of-scope-owner.toml",
        source.replace(line, line.replace(ownership.owner_step, foreign_owner), 1),
    )

    with pytest.raises(RehomingLedgerError, match="E_REHOMING_OWNER_SCOPE"):
        validate_rehoming_ledger(load_rehoming_ledger(path))


def test_rehoming_ledger_rejects_retired_current_evidence_and_live_rows_without_ownerships(tmp_path: Path) -> None:
    ledger = load_rehoming_ledger()
    retired = next(row for row in ledger.rows if not row.ownerships)
    ownership = _live_ownership_with_multiple_row()
    source = DEFAULT_REHOMING_LEDGER_PATH.read_text(encoding="utf-8")
    disposition = 'disposition_kind = "retired_or_unreachable"\n'
    retired_evidence = _write_ledger(
        tmp_path,
        "retired-evidence.toml",
        source.replace(
            disposition,
            (
                f"{disposition}current_error_qualname = {json.dumps(retired.historical.error_qualname)}\n"
                f"ownerships = [\n{_ownership_line(ownership)}]\n"
            ),
            1,
        ),
    )
    live = next(row for row in ledger.rows if row.ownerships)
    current_evidence = f"current_error_qualname = {json.dumps(live.current_error_qualname)}\nownerships = [\n"
    ownership_start = source.index(current_evidence)
    ownership_end = source.index("]\n", ownership_start) + len("]\n")
    live_without_ownerships = _write_ledger(
        tmp_path,
        "live-without-ownerships.toml",
        f"{source[:ownership_start]}current_error_qualname = {json.dumps(live.current_error_qualname)}\n"
        f"{source[ownership_end:]}",
    )

    with pytest.raises(RehomingLedgerError):
        load_rehoming_ledger(retired_evidence)
    with pytest.raises(RehomingLedgerError):
        load_rehoming_ledger(live_without_ownerships)


def _scanner_source(tmp_path: Path, relative_path: str, content: str | bytes) -> Path:
    source = tmp_path / "src" / "cadrumo" / relative_path
    source.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        source.write_bytes(content)
    else:
        source.write_text(content, encoding="utf-8")
    return source


_CERTIFICATE_MODULE = "adapters/outbound/aeat/auth/certificate.py"
_CERTIFICATE_QUALNAME = "cadrumo.adapters.outbound.aeat.auth.certificate.CertificateLoadError"


def _certificate_fingerprints(tmp_path: Path, name: str, content: str) -> tuple[SourceFingerprint, ...]:
    root = tmp_path / name
    _scanner_source(root, _CERTIFICATE_MODULE, content)
    return current_source_fingerprints(root).get(_CERTIFICATE_QUALNAME, ())


def test_structural_fingerprints_ignore_comment_and_locator_shifts_but_detect_semantic_call_changes(
    tmp_path: Path,
) -> None:
    source = (
        "class CertificateLoadError(Exception):\n"
        "    pass\n\n"
        "def construct() -> CertificateLoadError:\n"
        '    return CertificateLoadError(Exception, reason="one")\n'
    )
    shifted = "\n# recovery locator drift\n\n" + source
    argument_changed = source.replace("CertificateLoadError(Exception", "CertificateLoadError(RuntimeError")
    keyword_changed = source.replace('reason="one"', 'detail="one"')
    class_changed = source.replace("CertificateLoadError(Exception", "CertificateLoadErrorAlias(Exception").replace(
        "class CertificateLoadError(Exception):", "class CertificateLoadErrorAlias(Exception):"
    )

    baseline = _certificate_fingerprints(tmp_path, "baseline", source)
    assert baseline
    assert tuple(fingerprint.identity for fingerprint in baseline) == tuple(
        fingerprint.identity for fingerprint in _certificate_fingerprints(tmp_path, "shifted", shifted)
    )
    assert tuple(fingerprint.identity for fingerprint in baseline) != tuple(
        fingerprint.identity for fingerprint in _certificate_fingerprints(tmp_path, "argument", argument_changed)
    )
    assert tuple(fingerprint.identity for fingerprint in baseline) != tuple(
        fingerprint.identity for fingerprint in _certificate_fingerprints(tmp_path, "keyword", keyword_changed)
    )
    assert not _certificate_fingerprints(tmp_path, "class", class_changed)


def test_structural_fingerprints_track_named_owner_across_class_nested_lambda_comprehension_annotations_and_decorators(
    tmp_path: Path,
) -> None:
    fingerprints = _certificate_fingerprints(
        tmp_path,
        "owners",
        (
            "class CertificateLoadError(Exception):\n"
            "    pass\n\n"
            "@CertificateLoadError\n"
            "def documented(value: CertificateLoadError) -> CertificateLoadError:\n"
            "    class Nested(CertificateLoadError):\n"
            "        def reference(self) -> CertificateLoadError:\n"
            "            return CertificateLoadError\n"
            "    callback = lambda: CertificateLoadError\n"
            "    values = [CertificateLoadError for _ in range(1)]\n"
            "    return CertificateLoadError\n"
        ),
    )
    owners = {fingerprint.lexical_owner for fingerprint in fingerprints}
    function_owner = "cadrumo.adapters.outbound.aeat.auth.certificate.documented"
    assert function_owner in owners
    assert f"{function_owner}.Nested" in owners
    assert f"{function_owner}.Nested.reference" in owners
    assert all(fingerprint.role == "reference" for fingerprint in fingerprints)
    assert sum(fingerprint.lexical_owner == function_owner for fingerprint in fingerprints) >= 5


def test_structural_ordinals_do_not_renumber_distinct_sites_and_preserve_identical_multiplicity(
    tmp_path: Path,
) -> None:
    prefix = "class CertificateLoadError(Exception):\n    pass\n\ndef construct():\n    return (\n"
    suffix = "    )\n"
    baseline = _certificate_fingerprints(
        tmp_path,
        "ordinal-baseline",
        f'{prefix}        CertificateLoadError("alpha"),\n        CertificateLoadError("beta"),\n{suffix}',
    )
    changed = _certificate_fingerprints(
        tmp_path,
        "ordinal-changed",
        (
            f'{prefix}        CertificateLoadError("gamma"),\n'
            '        CertificateLoadError("beta"),\n'
            '        CertificateLoadError("alpha"),\n'
            f"{suffix}"
        ),
    )
    duplicate = _certificate_fingerprints(
        tmp_path,
        "ordinal-duplicate",
        (
            f'{prefix}        CertificateLoadError("alpha"),\n'
            '        CertificateLoadError("beta"),\n'
            '        CertificateLoadError("alpha"),\n'
            f"{suffix}"
        ),
    )

    baseline_identities = {fingerprint.identity for fingerprint in baseline}
    changed_identities = {fingerprint.identity for fingerprint in changed}
    assert baseline_identities <= changed_identities
    assert len(changed_identities - baseline_identities) == 1
    duplicate_counts = Counter(fingerprint.normalized_ast_sha256 for fingerprint in duplicate)
    duplicated_hash = next(value for value, count in duplicate_counts.items() if count == 2)
    identical = [fingerprint for fingerprint in duplicate if fingerprint.normalized_ast_sha256 == duplicated_hash]
    assert [fingerprint.identical_site_ordinal for fingerprint in identical] == [1, 2]
    assert sorted(duplicate_counts.values()) == [1, 2]


def test_current_source_fingerprints_fail_closed_on_real_read_decode_and_parse_failures(tmp_path: Path) -> None:
    read_root = tmp_path / "read"
    read_path = read_root / "src" / "cadrumo" / "unreadable.py"
    read_path.mkdir(parents=True)
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_SOURCE_READ"):
        current_source_fingerprints(read_root)

    decode_root = tmp_path / "decode"
    _scanner_source(decode_root, "invalid.py", b"\xff")
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_SOURCE_DECODE"):
        current_source_fingerprints(decode_root)

    parse_root = tmp_path / "parse"
    _scanner_source(parse_root, "invalid.py", "not valid python (")
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_SOURCE_PARSE"):
        current_source_fingerprints(parse_root)


def test_current_source_fingerprints_fail_closed_on_dynamic_and_lexical_ambiguity(tmp_path: Path) -> None:
    module = "adapters/outbound/aeat/auth/certificate.py"
    dynamic_root = tmp_path / "dynamic"
    _scanner_source(
        dynamic_root,
        module,
        (
            "class CertificateLoadError(Exception):\n"
            "    pass\n\n"
            '__import__("cadrumo.adapters.outbound.aeat.auth.certificate")\n'
        ),
    )
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_CALL"):
        current_source_fingerprints(dynamic_root)

    lexical_root = tmp_path / "lexical"
    _scanner_source(
        lexical_root,
        module,
        (
            "class CertificateLoadError(Exception):\n"
            "    pass\n\n"
            "def inspect(value: object) -> None:\n"
            "    match value:\n"
            "        case [name] | (name, extra):\n"
            "            raise CertificateLoadError\n"
        ),
    )
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_MATCH_BINDERS"):
        current_source_fingerprints(lexical_root)


def _dynamic_import_root(tmp_path: Path, name: str, caller: str) -> Path:
    root = tmp_path / name
    _scanner_source(root, _CERTIFICATE_MODULE, "class CertificateLoadError(Exception):\n    pass\n")
    _scanner_source(root, "caller.py", caller)
    return root


@pytest.mark.parametrize(
    "name,caller",
    (
        (
            "import-module-direct",
            ('import importlib\n\nimportlib.import_module("cadrumo.adapters.outbound.aeat.auth.certificate")\n'),
        ),
        (
            "import-module-module-alias",
            ('import importlib as loader\n\nloader.import_module("cadrumo.adapters.outbound.aeat.auth.certificate")\n'),
        ),
        (
            "import-module-function-alias",
            (
                "from importlib import import_module as loader\n\n"
                'loader("cadrumo.adapters.outbound.aeat.auth.certificate")\n'
            ),
        ),
        (
            "import-module-nonliteral",
            (
                "from cadrumo.adapters.outbound.aeat.auth.certificate import CertificateLoadError\n"
                "from importlib import import_module\n\n"
                "def load(module_name: str) -> object:\n"
                "    return import_module(module_name)\n"
            ),
        ),
    ),
)
def test_current_source_fingerprints_fail_closed_on_target_relevant_import_module_routes(
    tmp_path: Path, name: str, caller: str
) -> None:
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(_dynamic_import_root(tmp_path, name, caller))


def test_current_source_fingerprints_rejects_nonliteral_import_module_without_target_relevance(tmp_path: Path) -> None:
    root = _dynamic_import_root(
        tmp_path,
        "import-module-unrelated",
        (
            "from importlib import import_module\n\n"
            "def load(module_name: str) -> object:\n"
            "    return import_module(module_name)\n"
        ),
    )

    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(root)


def _static_lazy_facade_root(tmp_path: Path, name: str, side_import: bool) -> Path:
    root = tmp_path / name
    _scanner_source(root, _CERTIFICATE_MODULE, "class CertificateLoadError(Exception):\n    pass\n")
    side_effect = '    import_module("cadrumo.adapters.outbound.aeat.auth.certificate")\n' if side_import else ""
    _scanner_source(
        root,
        "adapters/outbound/aeat/auth/__init__.py",
        (
            "from importlib import import_module\n\n"
            '_LAZY_EXPORTS = {"CertificateLoadError": ".certificate"}\n\n'
            "def __getattr__(name: str) -> object:\n"
            "    selected = _LAZY_EXPORTS.get(name)\n"
            "    module = import_module(selected, __name__)\n"
            f"{side_effect}"
            "    return getattr(module, name)\n"
        ),
    )
    return root


def test_current_source_fingerprints_allows_only_the_proven_static_pep562_import_module_route(tmp_path: Path) -> None:
    assert not current_source_fingerprints(_static_lazy_facade_root(tmp_path, "static-lazy-facade", False))


def test_current_source_fingerprints_rejects_side_import_module_in_otherwise_static_pep562_facade(
    tmp_path: Path,
) -> None:
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(_static_lazy_facade_root(tmp_path, "static-lazy-side-import", True))


def test_current_source_fingerprints_rejects_shadowed_import_module_in_pep562_facade(tmp_path: Path) -> None:
    root = tmp_path / "static-lazy-shadowed-import"
    _scanner_source(root, _CERTIFICATE_MODULE, "class CertificateLoadError(Exception):\n    pass\n")
    _scanner_source(
        root,
        "adapters/outbound/aeat/auth/__init__.py",
        (
            "from importlib import import_module\n\n"
            "def import_module(name: str, package: str) -> object:\n"
            "    return object()\n\n"
            '_LAZY_EXPORTS = {"CertificateLoadError": ".certificate"}\n\n'
            "def __getattr__(name: str) -> object:\n"
            "    selected = _LAZY_EXPORTS.get(name)\n"
            "    module = import_module(selected, __name__)\n"
            "    return getattr(module, name)\n"
        ),
    )

    with pytest.raises(RehomingLedgerError, match="E_REHOMING_LAZY_GETATTR"):
        current_source_fingerprints(root)


@pytest.mark.parametrize(
    "name,taint",
    (
        ("static-lazy-if-taint", "if True:\n    import_module = object()\n\n"),
        ("static-lazy-try-taint", "try:\n    import_module = object()\nexcept Exception:\n    pass\n\n"),
        ("static-lazy-with-taint", "with object() as import_module:\n    pass\n\n"),
    ),
)
def test_current_source_fingerprints_rejects_control_flow_tainted_import_module_in_pep562_facade(
    tmp_path: Path, name: str, taint: str
) -> None:
    root = tmp_path / name
    _scanner_source(root, _CERTIFICATE_MODULE, "class CertificateLoadError(Exception):\n    pass\n")
    _scanner_source(
        root,
        "adapters/outbound/aeat/auth/__init__.py",
        (
            "from importlib import import_module\n\n"
            f"{taint}"
            '_LAZY_EXPORTS = {"CertificateLoadError": ".certificate"}\n\n'
            "def __getattr__(name: str) -> object:\n"
            "    selected = _LAZY_EXPORTS.get(name)\n"
            "    module = import_module(selected, __name__)\n"
            "    return getattr(module, name)\n"
        ),
    )

    with pytest.raises(RehomingLedgerError, match="E_REHOMING_LAZY_GETATTR"):
        current_source_fingerprints(root)


def _local_lazy_facade_root(tmp_path: Path, name: str, *, taint: str = "", side_import: bool = False) -> Path:
    root = tmp_path / name
    _scanner_source(root, _CERTIFICATE_MODULE, "class CertificateLoadError(Exception):\n    pass\n")
    side_effect = '    loader("cadrumo.adapters.outbound.aeat.auth.certificate")\n' if side_import else ""
    _scanner_source(
        root,
        "adapters/outbound/aeat/auth/__init__.py",
        (
            '_LAZY_EXPORTS = {"CertificateLoadError": ".certificate"}\n\n'
            "def __getattr__(name: str) -> object:\n"
            "    selected = _LAZY_EXPORTS.get(name)\n"
            "    from importlib import import_module as loader\n"
            f"{taint}"
            "    module = loader(selected, __name__)\n"
            f"{side_effect}"
            "    return getattr(module, name)\n"
        ),
    )
    return root


def test_current_source_fingerprints_allows_sequential_route_local_pep562_import_module_alias(tmp_path: Path) -> None:
    assert not current_source_fingerprints(_local_lazy_facade_root(tmp_path, "local-lazy-facade"))


def test_current_source_fingerprints_rejects_side_import_outside_exact_local_pep562_route(tmp_path: Path) -> None:
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(_local_lazy_facade_root(tmp_path, "local-lazy-side-import", side_import=True))


@pytest.mark.parametrize(
    "name,taint",
    (
        ("local-sequential-rebind", "    loader = object()\n"),
        ("local-conditional-rebind", "    if True:\n        loader = object()\n"),
        ("local-try-rebind", "    try:\n        loader = object()\n    except Exception:\n        pass\n"),
        ("local-with-rebind", "    with object() as loader:\n        pass\n"),
        ("local-import-shadow", "    from pathlib import Path as loader\n"),
        ("local-nested-binding", "    def loader() -> object:\n        return object()\n"),
    ),
)
def test_current_source_fingerprints_rejects_rebound_route_local_pep562_import_module_alias(
    tmp_path: Path, name: str, taint: str
) -> None:
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_LAZY_GETATTR"):
        current_source_fingerprints(_local_lazy_facade_root(tmp_path, name, taint=taint))


def _target_module_root(tmp_path: Path, name: str, caller: str) -> Path:
    root = tmp_path / name
    _scanner_source(root, _CERTIFICATE_MODULE, "class CertificateLoadError(Exception):\n    pass\n")
    _scanner_source(
        root,
        "adapters/outbound/aeat/auth/__init__.py",
        (
            "from .certificate import CertificateLoadError\n\n"
            "app = object()\n\n"
            "class CCAA:\n"
            "    pass\n\n"
            "def select_provider() -> object:\n"
            "    return object()\n"
        ),
    )
    _scanner_source(root, "caller.py", caller)
    return root


def test_current_source_fingerprints_allows_closed_non_target_literal_import_module_use(tmp_path: Path) -> None:
    root = _target_module_root(
        tmp_path,
        "closed-auth-use",
        (
            "from importlib import import_module\n\n"
            "def select() -> object:\n"
            '    outbound_auth = import_module("cadrumo.adapters.outbound.aeat.auth")\n'
            "    factory = outbound_auth.select_provider\n"
            "    return factory()\n"
        ),
    )

    assert not current_source_fingerprints(root)


@pytest.mark.parametrize(
    "name,consumer",
    (
        ("closed-target-attribute", "    return outbound_auth.CertificateLoadError\n"),
        ("closed-dynamic-getattr", '    return getattr(outbound_auth, "select_provider")\n'),
        ("closed-module-escape", "    return outbound_auth\n"),
        (
            "closed-nested-capture",
            "    def later() -> object:\n        return outbound_auth.select_provider\n    return later()\n",
        ),
    ),
)
def test_current_source_fingerprints_rejects_escaping_or_target_closed_import_module_use(
    tmp_path: Path, name: str, consumer: str
) -> None:
    caller = (
        "from importlib import import_module\n\n"
        "def select() -> object:\n"
        '    outbound_auth = import_module("cadrumo.adapters.outbound.aeat.auth")\n'
        f"{consumer}"
    )
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(_target_module_root(tmp_path, name, caller))


@pytest.mark.parametrize(
    "name,accessor,expects_target_reference",
    (
        (
            "literal-module-accessor",
            (
                "def certificate_module() -> object:\n"
                "    import importlib\n\n"
                '    return importlib.import_module("cadrumo.adapters.outbound.aeat.auth.certificate")\n\n'
                "def inspect() -> object:\n"
                "    return certificate_module().CertificateLoadError\n"
            ),
            True,
        ),
        (
            "literal-attribute-accessor",
            (
                "def certificate_error() -> object:\n"
                "    from importlib import import_module\n\n"
                '    return import_module("cadrumo.adapters.outbound.aeat.auth.certificate").CertificateLoadError\n\n'
                "def inspect() -> object:\n"
                "    return certificate_error()\n"
            ),
            True,
        ),
        (
            "non-target-attribute-accessor",
            (
                "def ccaa() -> object:\n"
                "    import importlib\n\n"
                '    return importlib.import_module("cadrumo.adapters.outbound.aeat.auth").CCAA\n\n'
                "def inspect() -> object:\n"
                "    return ccaa()\n"
            ),
            False,
        ),
    ),
)
def test_current_source_fingerprints_allows_closed_zero_argument_literal_import_module_accessor(
    tmp_path: Path, name: str, accessor: str, expects_target_reference: bool
) -> None:
    fingerprints = current_source_fingerprints(_target_module_root(tmp_path, name, accessor))

    assert (_CERTIFICATE_QUALNAME in fingerprints) is expects_target_reference


@pytest.mark.parametrize(
    "name,accessor",
    (
        (
            "parameterized-accessor",
            (
                "def certificate_module(module_name: str) -> object:\n"
                "    import importlib\n"
                "    return importlib."
                "import_module(module_name)\n"
            ),
        ),
        (
            "branched-accessor",
            (
                "def certificate_module() -> object:\n"
                "    import importlib\n"
                "    if True:\n        return importlib."
                'import_module("cadrumo.adapters.outbound.aeat.auth.certificate")\n'
            ),
        ),
        (
            "nonliteral-accessor",
            (
                "def certificate_module() -> object:\n"
                "    import importlib\n"
                '    module_name = "cadrumo.adapters.outbound.aeat.auth.certificate"\n'
                "    return importlib.import_module(module_name)\n"
            ),
        ),
    ),
)
def test_current_source_fingerprints_rejects_nonclosed_import_module_accessor(
    tmp_path: Path, name: str, accessor: str
) -> None:
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(
            _target_module_root(
                tmp_path,
                name,
                "from cadrumo.adapters.outbound.aeat.auth.certificate import CertificateLoadError\n\n" + accessor,
            )
        )


def _bounded_cli_loader_root(tmp_path: Path, name: str, factory_body: str, domain: str | None = None) -> Path:
    registrations = (
        "_REGISTRATIONS: tuple[tuple[str, str, str], ...] = (\n"
        '    ("app", "auth", "cadrumo.adapters.outbound.aeat.auth"),\n)\n'
    )
    modules = domain or "_MODULES: frozenset[str] = frozenset(module for _group, _name, module in _REGISTRATIONS)\n"
    caller = (
        "from cadrumo.adapters.outbound.aeat.auth.certificate import CertificateLoadError\n"
        "from importlib import import_module\n\n"
        f"{registrations}{modules}\n"
        "def loader(module_name: str) -> object:\n"
        "    def factory() -> object:\n"
        f"{factory_body}"
        "    return factory()\n"
    )
    return _target_module_root(tmp_path, name, caller)


def test_current_source_fingerprints_allows_bounded_cli_import_module_loader(tmp_path: Path) -> None:
    root = _bounded_cli_loader_root(
        tmp_path,
        "bounded-cli-loader",
        (
            "        if module_name not in _MODULES:\n"
            "            raise RuntimeError(module_name)\n"
            "        module = import_module(module_name)\n"
            "        return module.app\n"
        ),
    )

    assert not current_source_fingerprints(root)


@pytest.mark.parametrize(
    "name,factory_body,domain",
    (
        (
            "cli-target-attribute",
            (
                "        if module_name not in _MODULES:\n            raise RuntimeError(module_name)\n"
                "        module = import_module(module_name)\n"
                "        return module.CertificateLoadError\n"
            ),
            None,
        ),
        (
            "cli-nested-capture",
            (
                "        if module_name not in _MODULES:\n            raise RuntimeError(module_name)\n"
                "        module = import_module(module_name)\n"
                "        def later() -> object:\n            return module.app\n"
                "        return later()\n"
            ),
            None,
        ),
    ),
)
def test_current_source_fingerprints_rejects_unclosed_cli_import_module_loader(
    tmp_path: Path, name: str, factory_body: str, domain: str | None
) -> None:
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(_bounded_cli_loader_root(tmp_path, name, factory_body, domain))


def test_current_source_fingerprints_rejects_rebound_outer_parameter_captured_by_cli_loader(tmp_path: Path) -> None:
    root = _target_module_root(
        tmp_path,
        "cli-rebound-capture",
        (
            "from importlib import import_module\n\n"
            "_REGISTRATIONS: tuple[tuple[str, str, str], ...] = (\n"
            '    ("app", "auth", "cadrumo.adapters.outbound.aeat.auth"),\n)\n'
            "_MODULES: frozenset[str] = frozenset(module for _group, _name, module in _REGISTRATIONS)\n\n"
            "def loader(module_name: str) -> object:\n"
            "    def factory() -> object:\n"
            "        if module_name not in _MODULES:\n"
            "            raise RuntimeError(module_name)\n"
            "        module = import_module(module_name)\n"
            "        return module.app\n"
            '    module_name = "cadrumo.adapters.outbound.aeat.auth.certificate"\n'
            "    return factory()\n"
        ),
    )

    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(root)


def _bounded_side_effect_import_root(tmp_path: Path, name: str, loop_body: str, domain: str | None = None) -> Path:
    caller = (
        "from importlib import import_module\n\n"
        + (domain or '_MODULES: tuple[str, ...] = ("cadrumo.adapters.outbound.aeat.auth",)\n')
        + "\ndef install() -> None:\n"
        + loop_body
    )
    return _target_module_root(tmp_path, name, caller)


def test_current_source_fingerprints_allows_bounded_side_effect_import_module_loop(tmp_path: Path) -> None:
    root = _bounded_side_effect_import_root(
        tmp_path,
        "bounded-side-effect-loop",
        "    for module_name in _MODULES:\n        import_module(module_name)\n",
    )

    assert not current_source_fingerprints(root)


def _imported_tuple_side_effect_root(
    tmp_path: Path,
    name: str,
    domain_source: str,
    *,
    domain_import: str = "from .domains import _MODULES\n",
    loop_domain: str = "_MODULES",
    extra_sources: tuple[tuple[str, str], ...] = (),
    install_body: str | None = None,
) -> Path:
    root = tmp_path / name
    _scanner_source(root, "domains.py", domain_source)
    for relative_path, content in extra_sources:
        _scanner_source(root, relative_path, content)
    caller = f"from importlib import import_module\n{domain_import}\ndef install() -> None:\n" + (
        install_body
        if install_body is not None
        else f"    for module_name in {loop_domain}:\n        import_module(module_name)\n"
    )
    return _target_module_root(tmp_path, name, caller)


def test_current_source_fingerprints_allows_direct_imported_canonical_literal_tuple_domain(tmp_path: Path) -> None:
    root = _imported_tuple_side_effect_root(
        tmp_path,
        "imported-canonical-literal-tuple",
        '_MODULES: tuple[str, ...] = ("cadrumo.adapters.outbound.aeat.auth",)\n',
    )

    assert not current_source_fingerprints(root)


def test_current_source_fingerprints_allows_imported_literal_tuple_through_isolated_exception_loop(
    tmp_path: Path,
) -> None:
    root = _imported_tuple_side_effect_root(
        tmp_path,
        "imported-literal-tuple-isolated-exception-loop",
        '_MODULES: tuple[str, ...] = ("cadrumo.adapters.outbound.aeat.auth",)\n',
        install_body=(
            "    failures: list[Exception] = []\n"
            "    for module_name in _MODULES:\n"
            "        try:\n"
            "            import_module(module_name)\n"
            "        except Exception as error:\n"
            "            failures.append(error)\n"
        ),
    )

    assert not current_source_fingerprints(root)


def test_current_source_fingerprints_rejects_imported_literal_tuple_exception_loop_rebinding_domain(
    tmp_path: Path,
) -> None:
    root = _imported_tuple_side_effect_root(
        tmp_path,
        "imported-literal-tuple-exception-loop-rebinding-domain",
        '_MODULES: tuple[str, ...] = ("cadrumo.adapters.outbound.aeat.auth",)\n',
        install_body=(
            "    for module_name in _MODULES:\n"
            "        try:\n"
            "            import_module(module_name)\n"
            "        except Exception:\n"
            '            module_name = "cadrumo.adapters.outbound.aeat.auth"\n'
        ),
    )

    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(root)


@pytest.mark.parametrize(
    "name,domain_source,domain_import,loop_domain,extra_sources",
    (
        (
            "imported-list-domain",
            '_MODULES = ["cadrumo.adapters.outbound.aeat.auth"]\n',
            "from .domains import _MODULES\n",
            "_MODULES",
            (),
        ),
        (
            "imported-set-domain",
            '_MODULES = {"cadrumo.adapters.outbound.aeat.auth"}\n',
            "from .domains import _MODULES\n",
            "_MODULES",
            (),
        ),
        (
            "imported-dict-domain",
            '_MODULES = {"cadrumo.adapters.outbound.aeat.auth": None}\n',
            "from .domains import _MODULES\n",
            "_MODULES",
            (),
        ),
        (
            "imported-computed-domain",
            '_MODULES = tuple(("cadrumo.adapters.outbound.aeat.auth",))\n',
            "from .domains import _MODULES\n",
            "_MODULES",
            (),
        ),
        (
            "imported-comprehension-domain",
            '_MODULES = tuple(module for module in ("cadrumo.adapters.outbound.aeat.auth",))\n',
            "from .domains import _MODULES\n",
            "_MODULES",
            (),
        ),
        (
            "imported-concatenated-domain",
            '_MODULES = ("cadrumo.adapters.outbound.aeat.auth",) + ()\n',
            "from .domains import _MODULES\n",
            "_MODULES",
            (),
        ),
        (
            "imported-nonliteral-element",
            '_AUTH = "cadrumo.adapters.outbound.aeat.auth"\n_MODULES = (_AUTH,)\n',
            "from .domains import _MODULES\n",
            "_MODULES",
            (),
        ),
        (
            "imported-source-rebound",
            (
                '_MODULES = ("cadrumo.adapters.outbound.aeat.auth",)\n\n'
                "def replace() -> None:\n"
                "    global _MODULES\n"
                '    _MODULES = ("cadrumo.adapters.outbound.aeat.auth",)\n'
            ),
            "from .domains import _MODULES\n",
            "_MODULES",
            (),
        ),
        (
            "imported-importer-rebound",
            '_MODULES = ("cadrumo.adapters.outbound.aeat.auth",)\n',
            'from .domains import _MODULES\n_MODULES = ("cadrumo.adapters.outbound.aeat.auth",)\n',
            "_MODULES",
            (),
        ),
        (
            "imported-alias",
            '_MODULES = ("cadrumo.adapters.outbound.aeat.auth",)\n',
            "from .domains import _MODULES as MODULES\n",
            "MODULES",
            (),
        ),
        (
            "imported-star",
            '_MODULES = ("cadrumo.adapters.outbound.aeat.auth",)\n',
            "from .domains import *\n",
            "_MODULES",
            (),
        ),
        (
            "imported-multiple-provenance",
            '_MODULES = ("cadrumo.adapters.outbound.aeat.auth",)\n',
            "from .domains import _MODULES\nfrom .other import _MODULES\n",
            "_MODULES",
            (("other.py", '_MODULES = ("cadrumo.adapters.outbound.aeat.auth",)\n'),),
        ),
        (
            "imported-missing-source",
            '_MODULES = ("cadrumo.adapters.outbound.aeat.auth",)\n',
            "from .missing import _MODULES\n",
            "_MODULES",
            (),
        ),
        (
            "imported-out-of-repo-source",
            '_MODULES = ("cadrumo.adapters.outbound.aeat.auth",)\n',
            "from external_domains import _MODULES\n",
            "_MODULES",
            (),
        ),
        (
            "imported-cycle",
            "from .other import _MODULES\n",
            "from .domains import _MODULES\n",
            "_MODULES",
            (("other.py", "from .domains import _MODULES\n"),),
        ),
    ),
)
def test_current_source_fingerprints_rejects_noncanonical_imported_domain_provenance(
    tmp_path: Path,
    name: str,
    domain_source: str,
    domain_import: str,
    loop_domain: str,
    extra_sources: tuple[tuple[str, str], ...],
) -> None:
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(
            _imported_tuple_side_effect_root(
                tmp_path,
                name,
                domain_source,
                domain_import=domain_import,
                loop_domain=loop_domain,
                extra_sources=extra_sources,
            )
        )


def test_current_source_fingerprints_rejects_side_effect_loop_import_result_use(tmp_path: Path) -> None:
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(
            _bounded_side_effect_import_root(
                tmp_path,
                "side-effect-result-use",
                "    for module_name in _MODULES:\n        module = import_module(module_name)\n",
            )
        )


def test_current_source_fingerprints_allows_dynamic_pkgutil_package_path_import_module_use(tmp_path: Path) -> None:
    root = _target_module_root(
        tmp_path,
        "pkgutil-package-path",
        (
            "from importlib import import_module\n"
            "import pkgutil\n\n"
            "def package_modules(package_name: str) -> object:\n"
            "    package = import_module(package_name)\n"
            "    return tuple(pkgutil.iter_modules(package.__path__))\n"
        ),
    )

    assert not current_source_fingerprints(root)


@pytest.mark.parametrize(
    "name,consumer",
    (
        ("dynamic-package-escape", "    return package\n"),
        ("dynamic-package-target-attribute", "    return package.CertificateLoadError\n"),
        ("dynamic-package-getattr", '    return getattr(package, "__path__")\n'),
        (
            "dynamic-package-nested-capture",
            "    def later() -> object:\n        return package.__path__\n    return later()\n",
        ),
    ),
)
def test_current_source_fingerprints_rejects_unclosed_dynamic_package_import_module_use(
    tmp_path: Path, name: str, consumer: str
) -> None:
    caller = (
        "from importlib import import_module\n\n"
        "def package_modules(package_name: str) -> object:\n"
        "    package = import_module(package_name)\n"
        f"{consumer}"
    )
    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(_target_module_root(tmp_path, name, caller))


def test_current_source_fingerprints_rejects_unbounded_discarded_dynamic_import_module_side_effect(
    tmp_path: Path,
) -> None:
    root = _target_module_root(
        tmp_path,
        "discarded-side-effect",
        (
            "from importlib import import_module\n\n"
            "def register(module_name: str) -> None:\n"
            "    import_module(module_name)\n"
        ),
    )

    with pytest.raises(RehomingLedgerError, match="E_REHOMING_DYNAMIC_IMPORT_MODULE"):
        current_source_fingerprints(root)
