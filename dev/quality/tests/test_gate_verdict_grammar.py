"""Gate weak predicates against declared structured gate verdicts."""

from __future__ import annotations

import multiprocessing
import os
from pathlib import Path

import pytest

from dev.audit.report import _verdict_of

from ..._paths import REPO_ROOT
from ..gate_verdict_grammar import (
    gate_verdict_consumers,
    scan_gate_verdict_grammar,
    scan_paths_for_gate_verdict_grammar,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIXTURE = Path("fixture.py")
_FIXTURE_ROOT = Path(__file__).with_name("fixtures")
_PYTHON_ROOTS = (REPO_ROOT / "src" / "cadrumo", REPO_ROOT / "dev")
_REPORT = REPO_ROOT / "dev" / "audit" / "report.py"


def _python_modules() -> tuple[Path, ...]:
    """Return the real Python tree, refusing either declared root collapsing."""
    by_root = {root: tuple(root.rglob("*.py")) for root in _PYTHON_ROOTS}
    starved = {root: len(paths) for root, paths in by_root.items() if len(paths) < 500}
    assert not starved, f"the verdict-grammar sweep lost a declared root: {starved}"
    return tuple(path for paths in by_root.values() for path in paths)


def _source_fixture(name: str) -> str:
    return (_FIXTURE_ROOT / f"{name}.py.fixture").read_text(encoding="utf-8")


def test_detector_catches_the_declared_weak_predicate_shapes() -> None:
    """Positive controls live in an isolated source fixture, not this gate."""
    findings = scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_weak"))

    assert [
        (finding.path, finding.lineno, finding.producer, finding.predicate, finding.verdict) for finding in findings
    ] == [
        (_FIXTURE, 7, "import-linter", "endswith", "KEPT"),
        (_FIXTURE, 22, "import-linter", "endswith", "KEPT"),
        (_FIXTURE, 23, "import-linter", "startswith", "KEPT"),
        (_FIXTURE, 24, "import-linter", "endswith", "BROKEN"),
        (_FIXTURE, 25, "import-linter", "startswith", "BROKEN"),
        (_FIXTURE, 26, "import-linter", "in", "KEPT"),
        (_FIXTURE, 27, "import-linter", "not in", "KEPT"),
        (_FIXTURE, 28, "import-linter", "endswith", "KEPT"),
        (_FIXTURE, 28, "import-linter", "endswith", "BROKEN"),
        (_FIXTURE, 32, "import-linter", "endswith", "KEPT"),
        (_FIXTURE, 35, "import-linter", "startswith", "BROKEN"),
        (_FIXTURE, 41, "import-linter", "startswith", "BROKEN"),
        (_FIXTURE, 30, "import-linter", "endswith", "KEPT"),
        (_FIXTURE, 30, "import-linter", "endswith", "BROKEN"),
    ]


def test_report_parser_reads_a_whole_verdict_token_before_the_optional_context() -> None:
    assert _verdict_of("Contract KEPT") == "KEPT"
    assert _verdict_of("Contract KEPT (3 ignored imports)") == "KEPT"
    assert _verdict_of("Contract BROKEN") == "BROKEN"
    assert _verdict_of("Contract BROKEN (1 import)") == "BROKEN"
    assert _verdict_of("Contract NOTKEPT") is None
    assert _verdict_of("Contract BROKENNESS") is None
    assert _verdict_of("KEPT") is None


def test_positive_control_regresses_the_real_report_parser_in_memory() -> None:
    """A named fixture preserves the former report consumer's dynamic loop."""
    findings = scan_gate_verdict_grammar(
        _FIXTURE,
        _source_fixture("gate_verdict_historical_report"),
    )

    assert [(finding.path, finding.predicate, finding.verdict) for finding in findings] == [
        (_FIXTURE, "endswith", "KEPT"),
        (_FIXTURE, "endswith", "BROKEN"),
    ]


def test_non_name_verdict_assignment_does_not_create_a_binding() -> None:
    assert scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_non_name_binding")) == ()


def test_provenance_honours_overwrites_and_direct_subprocess_output() -> None:
    assert scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_overwritten_output")) == ()
    assert scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_future_output")) == ()
    assert scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_foreign_run")) == ()

    findings = scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_direct_output"))

    assert [(finding.predicate, finding.verdict) for finding in findings] == [
        ("endswith", "KEPT"),
        ("startswith", "BROKEN"),
        ("endswith", "KEPT"),
        ("endswith", "KEPT"),
        ("endswith", "BROKEN"),
    ]


def test_producer_command_provenance_checks_every_composed_name() -> None:
    findings = scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_command_binding"))

    assert [(finding.predicate, finding.verdict) for finding in findings] == [("endswith", "KEPT")]


def test_receiver_writes_and_valid_subprocess_forms_preserve_provenance() -> None:
    findings = scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_provenance_edges"))

    assert [(finding.predicate, finding.verdict) for finding in findings] == [
        ("endswith", "KEPT"),
        ("endswith", "KEPT"),
        ("startswith", "BROKEN"),
        ("endswith", "KEPT"),
        ("startswith", "BROKEN"),
    ]


def test_subprocess_import_identity_obeys_reaching_bindings() -> None:
    findings = scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_import_bindings"))

    assert [(finding.predicate, finding.verdict) for finding in findings] == [
        ("endswith", "KEPT"),
        ("startswith", "BROKEN"),
    ]


def test_binding_edges_preserve_only_proven_output_and_verdict_names() -> None:
    findings = scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_binding_edges"))

    assert [(finding.predicate, finding.verdict) for finding in findings] == [("endswith", "KEPT")]


def test_provenance_refuses_future_loop_and_cyclic_sources() -> None:
    findings = scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_source_order_edges"))

    assert [(finding.predicate, finding.verdict) for finding in findings] == [
        ("in", "KEPT"),
        ("endswith", "KEPT"),
    ]


def test_conditional_writes_and_non_reaching_verdicts_are_not_proven() -> None:
    findings = scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_conditional_edges"))

    assert [(finding.predicate, finding.verdict) for finding in findings] == [
        ("endswith", "KEPT"),
        ("endswith", "KEPT"),
        ("endswith", "KEPT"),
        ("endswith", "KEPT"),
        ("endswith", "KEPT"),
        ("endswith", "KEPT"),
    ]


def test_parsed_dynamic_and_unenrolled_fixtures_are_left_alone() -> None:
    """Only direct weak predicates enrolled by a producer grammar are findings."""
    assert scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_clean")) == ()
    assert scan_gate_verdict_grammar(_FIXTURE, _source_fixture("gate_verdict_unenrolled")) == ()
    path = _FIXTURE_ROOT / "gate_verdict_unenrolled.py.fixture"
    assert gate_verdict_consumers((path,)) == ()


def test_declared_verdict_consumer_population_does_not_collapse() -> None:
    """Anti-vacuity control: at least one real module consumes a declared grammar."""
    consumers = gate_verdict_consumers(_python_modules())

    assert consumers, "no real module consumes any declared gate-output grammar"
    assert any(consumer.path == REPO_ROOT / "dev" / "audit" / "report.py" for consumer in consumers)


def _scan_path_in_child(path: str, operation: str) -> None:
    adapter = gate_verdict_consumers if operation == "gate_verdict_consumers" else scan_paths_for_gate_verdict_grammar
    assert adapter((Path(path),))


def _run_path_adapter_under_legacy_locale(path: Path, operation: str) -> int | None:
    environment = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONCOERCECLOCALE": "0",
        "PYTHONUTF8": "0",
    }
    previous_environment = {
        name: os.environ.get(name)
        for name in environment
        if name not in os.environ or os.environ[name] != environment[name]
    }
    os.environ.update(environment)
    try:
        process = multiprocessing.get_context("spawn").Process(target=_scan_path_in_child, args=(str(path), operation))
        process.start()
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join()
        return process.exitcode
    finally:
        for name, value in previous_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_consumer_attribution_keeps_utf8_second_module_string_and_the_declared_producer(tmp_path: Path) -> None:
    path = tmp_path / "consumer.py"
    path.write_text(_source_fixture("gate_verdict_second_literal"), encoding="utf-8")
    consumers = gate_verdict_consumers((path,))

    assert len(consumers) == 1
    consumer = consumers[0]
    assert consumer.path == path
    assert consumer.producer == "import-linter"
    process = _run_path_adapter_under_legacy_locale(path, "gate_verdict_consumers")
    assert process == 0


def test_path_adapter_propagates_location_and_requires_the_utf8_codec(tmp_path: Path) -> None:
    path = tmp_path / "weak.py"
    path.write_text(_source_fixture("gate_verdict_weak"), encoding="utf-8")
    findings = scan_paths_for_gate_verdict_grammar((path,))

    assert findings
    assert all(finding.path == path for finding in findings)
    process = _run_path_adapter_under_legacy_locale(path, "scan_paths_for_gate_verdict_grammar")
    assert process == 0


def test_no_weak_gate_verdict_predicate_survives_in_the_real_tree() -> None:
    """Sweep every Python module under both declared roots."""
    findings = scan_paths_for_gate_verdict_grammar(_python_modules())

    assert not findings, "gate verdicts are read through weaker token predicates:\n" + "\n".join(
        f"  {finding}" for finding in findings
    )


def test_mutation_controls_cover_provenance_shape_and_reachability() -> None:
    """Keep compact positive and negative controls for survivor-prone paths."""
    source = _source_fixture("gate_verdict_mutation_controls")
    findings = scan_gate_verdict_grammar(_FIXTURE, source)

    def line(marker: str) -> int:
        return next(number for number, text in enumerate(source.splitlines(), 1) if marker in text)

    expected = sorted(
        (
            line(marker),
            predicate,
            verdict,
        )
        for marker, predicate, verdict in (
            ("loop-marker", "endswith", "KEPT"),
            ("starred-marker", "endswith", "KEPT"),
            ("repeated-command", "endswith", "KEPT"),
            ("left-binop", "endswith", "KEPT"),
            ("right-binop", "endswith", "KEPT"),
            ("positive-index", "endswith", "KEPT"),
            ("both-sided-ifexp", "endswith", "KEPT"),
            ("repeated-verdict", "endswith", "KEPT"),
            ("comprehension-verdict", "endswith", "KEPT"),
            ("branch-reachability", "endswith", "KEPT"),
            ("terminating-try", "endswith", "KEPT"),
            ("composed-ambiguous-command", "endswith", "KEPT"),
            ("scalar-command", "endswith", "KEPT"),
            ("gate-gate-bound-command", "endswith", "KEPT"),
            ("gate-gate-bound-helper", "endswith", "KEPT"),
        )
    )
    actual = sorted((finding.lineno, finding.predicate, finding.verdict) for finding in findings)
    assert actual == expected
