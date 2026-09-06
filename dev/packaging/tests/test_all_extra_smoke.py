"""Tests for the all-extras lane's claim list and argument contract.

`dev.quality.module_test_reach` listed `dev/packaging/all_extra_smoke.py` as
unreached. The lane installs the aggregate optional extras into a stdlib venv
and drives the installed console script; that is what the packaging-smoke
workflow runs on every OS leg, and reproducing it here would prove nothing the
live legs do not.

What had no coverage is the part deciding what the run CLAIMS. The smoke
manifest refuses a declared claim whose assertion never ran, so the claim list
and the lane body are one contract - and this lane's distinguishing claim is the
capability-gated optional imports, which is the whole reason it exists apart
from the core lane. That coupling was reachable only by building a wheel, a venv
and every extra.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

from .._smoke_common import optional_extra_registry
from ..all_extra_smoke import COMPANION_MODULES, build_parser, declared_claims, optional_import_probe_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXPORT_CLAIM = "frozen dependency exports"


def test_the_export_claim_is_dropped_when_the_checks_are_skipped() -> None:
    """Leaving the claim while skipping the work is what the manifest refuses."""
    assert _EXPORT_CLAIM not in declared_claims(skip_export_checks=True)


def test_the_export_claim_is_present_when_the_checks_run() -> None:
    """A proof that ran must be claimed, or the evidence goes unrecorded."""
    assert _EXPORT_CLAIM in declared_claims(skip_export_checks=False)


def test_skipping_drops_exactly_one_claim() -> None:
    """Skipping one check must not quietly drop another's evidence."""
    full = declared_claims(skip_export_checks=False)
    reduced = declared_claims(skip_export_checks=True)

    assert set(full) - set(reduced) == {_EXPORT_CLAIM}


def test_the_lane_claims_the_optional_imports_that_distinguish_it() -> None:
    """This lane exists to install the aggregate extras, not merely a wheel.

    Named rather than counted: a count would survive the claim being replaced
    by another, and the optional-import proof is the only thing separating this
    lane from the core one.
    """
    assert "all capability-gated optional imports" in declared_claims(skip_export_checks=False)


def test_every_claim_is_distinct_and_non_empty() -> None:
    """The manifest matches claims by exact text, so a duplicate masks a gap.

    Two identical claims are satisfied by one recorded proof, letting a lane
    declare work it never did.
    """
    claims = declared_claims(skip_export_checks=False)

    assert all(claim.strip() for claim in claims)
    assert len(set(claims)) == len(claims)


def test_the_cohort_directory_is_required() -> None:
    """The lane proves one immutable cohort; defaulting it would prove another."""
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_the_cohort_directory_is_parsed_as_a_path() -> None:
    """It is resolved and joined downstream, where a string would not behave."""
    parsed = build_parser().parse_args(["--cohort-dir", "cohort"])

    assert isinstance(parsed.cohort_dir, pathlib.Path)


def test_the_export_checks_run_unless_asked_otherwise() -> None:
    """Skipping is opt-in; a lane skipping by default would prove less in silence."""
    assert build_parser().parse_args(["--cohort-dir", "c"]).skip_export_checks is False
    assert build_parser().parse_args(["--cohort-dir", "c", "--skip-export-checks"]).skip_export_checks is True


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

_STUB_REGISTRY = """import importlib.util
from dataclasses import dataclass


@dataclass(frozen=True)
class _Extra:
    extra: str
    import_name: str


OPTIONAL_EXTRAS = tuple(_Extra(*row) for row in __RECORDS__)


def require_optional_extra(extra):
    if importlib.util.find_spec(extra.import_name) is None:
        raise SystemExit("missing optional extra " + extra.extra)
"""

_DISPLACED_PROBE = """import importlib

from cadrumo.core.optional_extras import OPTIONAL_EXTRAS, require_optional_extra

for _name in ("googleapiclient", "playwright", "anthropic"):
    importlib.import_module(_name)
    require_optional_extra(next(e for e in OPTIONAL_EXTRAS if e.import_name == _name))

print("all-extra-imports-ok")
"""


def _plant(root: pathlib.Path, records, present) -> None:
    """Lay out a stub product registry plus stub modules for the present supplies."""
    package = root / "cadrumo" / "core"
    package.mkdir(parents=True)
    (root / "cadrumo" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "optional_extras.py").write_text(
        _STUB_REGISTRY.replace("__RECORDS__", repr(tuple(records))), encoding="utf-8"
    )
    for name in present:
        head, _, tail = name.partition(".")
        if tail:
            (root / head).mkdir(exist_ok=True)
            (root / head / "__init__.py").write_text("", encoding="utf-8")
            (root / head / f"{tail}.py").write_text("", encoding="utf-8")
        else:
            (root / f"{name}.py").write_text("", encoding="utf-8")


def _run(root: pathlib.Path, program: str) -> subprocess.CompletedProcess[str]:
    """Run one probe program in a child interpreter that sees only the stub tree.

    ``-S`` drops site-packages and ``-E`` drops ``PYTHONPATH``, so the only
    importable non-stdlib names are the ones planted under ``root``. Without
    that the dev environment's own ``ofxtools`` would satisfy the import the
    absence test needs to fail, and the teeth would be theatre.
    """
    return subprocess.run(  # noqa: S603 - fixed argv, interpreter is this repo's own
        [sys.executable, "-S", "-E", "-c", program],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _live_registry_records() -> tuple[tuple[str, str], ...]:
    """Return the product's own capability-gated extras, so the teeth track it."""
    registry, _symbols = optional_extra_registry(_REPO_ROOT)
    return tuple(sorted(registry.items()))


def test_the_probe_accepts_an_install_where_every_registered_extra_imports() -> None:
    """The control: with every supply present the probe must pass.

    Without it the refusal below could be the fixture failing rather than the
    probe detecting anything, exactly as a red gate that names nothing proves
    nothing.
    """
    import tempfile

    records = _live_registry_records()
    with tempfile.TemporaryDirectory() as raw:
        root = pathlib.Path(raw)
        _plant(root, records, [name for _extra, name in records])
        result = _run(root, optional_import_probe_source(companions=()))

    assert result.returncode == 0, result.stderr
    assert "all-extra-imports-ok" in result.stdout


def test_the_probe_refuses_a_registered_extra_that_installs_but_does_not_import() -> None:
    """``ofx`` and ``llm`` are the two the displaced hand-kept list never reached.

    A supply that resolves but no longer imports is not hypothetical: the
    ``llm`` extra declares ``nvidia-ml-py`` and the product imports ``pynvml``,
    and the production reader answers ``ImportError`` with an ``UNKNOWN``
    accelerator, so the regression is silent everywhere else.
    """
    import tempfile

    records = _live_registry_records()
    unreached = {"ofxtools", "pynvml"}
    present = [name for _extra, name in records if name not in unreached]
    assert len(present) == len(records) - 2, records

    with tempfile.TemporaryDirectory() as raw:
        root = pathlib.Path(raw)
        _plant(root, records, present)
        result = _run(root, optional_import_probe_source(companions=()))

    assert result.returncode != 0
    assert "ofxtools" in result.stderr or "pynvml" in result.stderr


def test_the_displaced_three_name_probe_passes_the_same_install() -> None:
    """The second control, and the one that makes the refusal above mean something.

    The shape this lane carried enumerated google, browser and anthropic by
    hand. Run against the very fixture the registry-driven probe refuses, it
    exits zero: the gate read as an all-extras proof while two of five extras
    had no invocation site in it at all.
    """
    import tempfile

    records = _live_registry_records()
    present = [name for _extra, name in records if name not in {"ofxtools", "pynvml"}]

    with tempfile.TemporaryDirectory() as raw:
        root = pathlib.Path(raw)
        _plant(root, records, present)
        result = _run(root, _DISPLACED_PROBE)

    assert result.returncode == 0, result.stderr
    assert "all-extra-imports-ok" in result.stdout


def test_the_probe_refuses_an_empty_registry_rather_than_looping_over_nothing() -> None:
    """A vacuous loop is the failure mode a derived proof invites; it must fail closed."""
    import tempfile

    with tempfile.TemporaryDirectory() as raw:
        root = pathlib.Path(raw)
        _plant(root, (), ())
        result = _run(root, optional_import_probe_source(companions=()))

    assert result.returncode != 0
    assert "registry is empty" in result.stderr


def test_the_companion_modules_are_imported_rather_than_merely_listed() -> None:
    """The registry names one module per extra; the companions cover the rest.

    Listing them without importing them would restate the old defect one layer
    down, so an absent companion must fail the probe.
    """
    import tempfile

    records = _live_registry_records()
    with tempfile.TemporaryDirectory() as raw:
        root = pathlib.Path(raw)
        _plant(root, records, [name for _extra, name in records])
        result = _run(root, optional_import_probe_source(companions=("absent_companion_pkg",)))

    assert result.returncode != 0
    assert "absent_companion_pkg" in result.stderr
    assert COMPANION_MODULES, "the shipped lane must name the extra-supplied companions"
