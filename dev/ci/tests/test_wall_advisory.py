"""The retained wall advisory fires on a wedge and stays quiet on load.

Converting a perf gate from wall-clock to CPU-time is the right instrument
choice on this co-resident fleet, but it is also the change that silently
deletes the only bound able to see a test blocked on a wedged mount: a blocked
test burns no CPU however long it stalls, so a CPU ceiling can never fire on
it. :func:`~dev.ci.perf_measurement.wall_advisory_message` is what a
converted budget keeps in that gap. One such budget survives; the second
conversion's site was replaced wholesale and its advisory went with it,
which is why the coverage assertion at the foot of this module exists.

This gate exists because the advisory has two ways to be worthless and both
pass a green suite. It can be unfalsifiable -- never fire, so the wedge class
stays as unwatched as a straight conversion would have left it. Or it can be
indiscriminate -- fire whenever the box is busy, which on this machine is most
runs, and an advisory that fires on every run is one every reader learns to
skip, the decorative-guard decay already documented twice in this suite.
So both directions are asserted here, against the site-derived figures the two
consumers actually pass rather than against round numbers chosen to pass.

The advisory is a pure classifier over two measured clocks, so it is driven
directly with the readings the fleet recorded on real runs. Nothing is mocked:
the function under test IS the code the benchmarks call, and the numbers are
this repository's own measurements, quoted in the constants' derivations at
both call sites.
"""

from __future__ import annotations

import ast
import re
import warnings
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT

from ..perf_measurement import WallClockAdvisory, wall_advisory_message

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The in-process ledger benchmark's retained threshold and wedge ratio.
_LEDGER_WALL_S: Final[float] = 3.0
_LEDGER_RATIO: Final[float] = 4.0

#: The subprocess cold-start site's, which runs a far looser ratio because a
#: spawn's wall time is dominated by process creation the SUT does not own.
_COLD_START_WALL_S: Final[float] = 7.0
_COLD_START_RATIO: Final[float] = 12.0


def _ledger_advisory(*, wall_seconds: float, cpu_seconds: float) -> str | None:
    """Run the classifier with the ledger benchmark's own thresholds."""
    return wall_advisory_message(
        "iva_quarterly_partitioned p95",
        wall_seconds=wall_seconds,
        cpu_seconds=cpu_seconds,
        wall_advisory_seconds=_LEDGER_WALL_S,
        hang_wall_to_cpu_ratio=_LEDGER_RATIO,
    )


def test_the_measured_loaded_reading_does_not_fire() -> None:
    """The worst load this path ever measured stays quiet.

    Wall 4.10 s against 1.83 CPU-s is the loaded reading recorded in the
    benchmark's own module docstring -- a real run, on the real fleet, with the
    box saturated. It crosses the 3.0 s threshold and must still not warn: at
    2.24x it is load-shaped, and warning here would make the advisory fire on
    ordinary days and so teach every reader to ignore it.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", WallClockAdvisory)
        assert _ledger_advisory(wall_seconds=4.10, cpu_seconds=1.83) is None


def test_the_measured_quiet_reading_does_not_fire() -> None:
    """The unloaded reading is below the threshold and cannot warn."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", WallClockAdvisory)
        assert _ledger_advisory(wall_seconds=2.07, cpu_seconds=1.83) is None


def test_a_stalled_read_fires_and_names_both_clocks() -> None:
    """A wedge is caught, and the message distinguishes it from a regression.

    The shape is the one CPU-time is blind to: wall runs away while CPU holds
    at the same 1.83 s the healthy runs measured. The message must say so, or a
    reader triaging it re-reads it as the performance regression the asserted
    CPU gate has in fact just confirmed is absent.
    """
    with pytest.warns(WallClockAdvisory) as caught:
        message = _ledger_advisory(wall_seconds=45.0, cpu_seconds=1.83)

    assert message is not None
    assert len(caught) == 1
    assert message == str(caught[0].message)
    assert "45.000s" in message
    assert "1.830 CPU-s" in message
    assert "NOT a performance regression" in message


def test_a_fully_blocked_sample_fires_rather_than_dividing_by_zero() -> None:
    """Zero CPU is the wedge in its purest form, not an input to reject.

    A test blocked for its whole duration measures no CPU at all. That is the
    single reading this advisory most needs to survive, so the ratio treats it
    as unbounded rather than guarding the division and returning early.
    """
    with pytest.warns(WallClockAdvisory):
        message = _ledger_advisory(wall_seconds=45.0, cpu_seconds=0.0)

    assert message is not None
    assert "infx" in message.replace(" ", "")


def test_the_cold_start_ratio_admits_the_spawn_wait_it_must() -> None:
    """A healthy loaded SPAWN stays quiet under the looser subprocess ratio.

    6.75 s of wall against 1.45 CPU-s is the worst healthy cold start recorded
    on this box, and its 4.7x ratio would have tripped the in-process site's
    4.0x threshold. That is the whole reason the ratio is per-site: a spawn
    pays process-creation wait the SUT is not answerable for, so a single
    global ratio would have to be either noisy here or blind there.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", WallClockAdvisory)
        assert (
            wall_advisory_message(
                "aeat --version cold start",
                wall_seconds=6.75,
                cpu_seconds=1.45,
                wall_advisory_seconds=_COLD_START_WALL_S,
                hang_wall_to_cpu_ratio=_COLD_START_RATIO,
            )
            is None
        )

    assert _LEDGER_RATIO < 6.75 / 1.45, "the spawn reading no longer demonstrates why the ratio is per-site"


def test_the_cold_start_ratio_still_catches_a_wedged_spawn() -> None:
    """The looser ratio is loose, not vacuous: a stalled spawn still fires."""
    with pytest.warns(WallClockAdvisory):
        assert (
            wall_advisory_message(
                "aeat --version cold start",
                wall_seconds=30.0,
                cpu_seconds=1.45,
                wall_advisory_seconds=_COLD_START_WALL_S,
                hang_wall_to_cpu_ratio=_COLD_START_RATIO,
            )
            is not None
        )


#: Threshold name -> the value this gate proves the advisory behaviour against.
#: Every declaration of one of these names anywhere under `dev/` must carry the
#: value here, so a consumer cannot relax its own copy to silence a real wedge.
_PINNED_THRESHOLDS: Final = {
    "_P95_WALL_ADVISORY_SECONDS": _LEDGER_WALL_S,
    "_P95_WEDGE_WALL_TO_CPU_RATIO": _LEDGER_RATIO,
    "_COLD_START_WALL_ADVISORY_S": _COLD_START_WALL_S,
    "_COLD_START_WEDGE_WALL_TO_CPU_RATIO": _COLD_START_RATIO,
}


def _threshold_drift(root: Path) -> tuple[list[str], int]:
    """Return every drifted declaration under ``root``, and how many were read.

    The count is what stops the check passing vacuously: a discovery gate that
    finds no consumer at all is indistinguishable from one where every consumer
    agrees, and the first of those is a gate asserting nothing.
    """
    declaration = re.compile(
        rf"^({'|'.join(_PINNED_THRESHOLDS)})\s*(?::[^=]+)?=\s*(.+?)\s*(?:#.*)?$",
        re.MULTILINE,
    )
    drifted: list[str] = []
    checked = 0
    for source in sorted(root.rglob("*.py")):
        # This module is scanned like any other. It once skipped itself, and the
        # skip was dead: the pinned names appear here only as dictionary keys,
        # which the line-anchored pattern above cannot match, so removing it
        # changes nothing that is read today - two declarations either way -
        # and removes a blind spot over the one file most likely to acquire a
        # stale copy of a threshold it defines.
        for name, declared in declaration.findall(source.read_text(encoding="utf-8")):
            checked += 1
            expected = _PINNED_THRESHOLDS[name]
            try:
                value = ast.literal_eval(declared.rstrip(","))
            except (SyntaxError, ValueError):
                drifted.append(f"{source.name}: {name} = {declared}, which is not a bare literal this gate can prove")
                continue
            if value != expected:
                drifted.append(f"{source.name}: {name} = {declared}, this gate proves {expected}")
    return drifted, checked


def test_the_consumers_pass_the_thresholds_this_gate_asserts() -> None:
    """Every declared copy of a threshold carries the value proved above.

    Without this the gate drifts into testing figures no caller uses: a
    consumer could relax its threshold to silence a real wedge and every
    assertion here would keep passing against the stale copy.

    Consumers are discovered rather than named. Naming them made the gate a
    list to maintain: it raised on a consumer that had been removed, which
    reads as a threshold failure and is not one, and it said nothing at all
    about a consumer nobody had added to the list.
    """
    drifted, checked = _threshold_drift(REPO_ROOT / "dev")

    assert checked, "no consumer declares any pinned threshold; this gate is asserting nothing"
    assert not drifted, "a consumer carries a threshold this gate does not prove: " + "; ".join(drifted)


def test_a_relaxed_consumer_threshold_is_caught(tmp_path: Path) -> None:
    """The teeth: a consumer that widens its own copy is reported.

    Written to an isolated tree, so the proof runs in the same suite as the
    clean result that is meant to be meaningful.
    """
    (tmp_path / "consumer.py").write_text(
        f"_P95_WALL_ADVISORY_SECONDS = {_LEDGER_WALL_S + 30.0}\n",
        encoding="utf-8",
    )

    drifted, checked = _threshold_drift(tmp_path)

    assert checked == 1
    assert len(drifted) == 1
    assert "_P95_WALL_ADVISORY_SECONDS" in drifted[0]


def test_a_drifted_copy_is_reported_even_in_a_file_named_like_this_module(tmp_path: Path) -> None:
    """No file is exempt by name, including one sharing this module's name.

    The scan once skipped its own filename. The skip was dead - the pinned names
    appear here only as dictionary keys, which the line-anchored pattern cannot
    match - so it protected nothing and hid the one file most likely to acquire
    a stale copy of a threshold it defines. This pins the removal: a drifted
    declaration is reported wherever it sits, and a name-based exemption
    reintroduced above would fail here rather than silently shrinking the scan.
    """
    (tmp_path / Path(__file__).name).write_text(
        f"_COLD_START_WALL_ADVISORY_S = {_COLD_START_WALL_S + 5.0}\n",
        encoding="utf-8",
    )

    drifted, checked = _threshold_drift(tmp_path)

    assert checked == 1, "the file was skipped by name, so the exemption is back"
    assert len(drifted) == 1
    assert "_COLD_START_WALL_ADVISORY_S" in drifted[0]


#: The pinned names a live consumer must STILL declare: a FLOOR, not a record of
#: the ones that happen to qualify today. The drift check above is
#: one-directional in the wrong axis -- it reports no drift for a threshold
#: nobody declares exactly as it does for one every consumer agrees on, and its
#: census floor is a total across all four names, and both live declarations
#: sit in one consumer, so either can vanish while the other keeps the count
#: non-zero. This floor closes that:
#: losing a declaration drops the scan below it and fails.
#:
#: The two cold-start names sit OUTSIDE the floor rather than being asserted
#: absent -- the budget they were copied from was replaced wholesale by a
#: same-named import gate, taking its advisory with it. An equality here would
#: have reddened the moment that advisory was restored, making the gate's green
#: depend on the hole persisting. Restoring it is free; losing a declaration
#: that exists today is not.
_MINIMUM_CONSUMER_BACKED_THRESHOLDS: Final[frozenset[str]] = frozenset(
    {"_P95_WALL_ADVISORY_SECONDS", "_P95_WEDGE_WALL_TO_CPU_RATIO"}
)


def _declared_threshold_names(root: Path) -> set[str]:
    """Return every pinned threshold name some consumer under ``root`` declares."""
    declaration = re.compile(rf"^({'|'.join(_PINNED_THRESHOLDS)})\s*(?::[^=]+)?=\s*\S+", re.MULTILINE)
    return {
        name
        for source in sorted(root.rglob("*.py"))
        for name in declaration.findall(source.read_text(encoding="utf-8"))
    }


def test_no_pinned_threshold_loses_the_live_consumer_it_still_has() -> None:
    """A threshold no consumer declares is a deleted advisory, not agreement.

    The gate above proves the classifier behaves correctly at all four pinned
    figures and then asserts consumers carry them. For half the vocabulary
    there is no consumer to carry anything: the cold-start pair is validated
    in the abstract while the site that once emitted the advisory is gone,
    and the total-count floor cannot see it because the surviving site keeps
    the count above zero.

    Asserted as a SUPERSET of the recorded floor, deliberately. An equality
    reddened the day someone restored the missing advisory, so its green
    depended on the hole staying open -- the gate punishing the repair it
    exists to motivate. Adding a consumer is free here; dropping one that
    exists today fails.
    """
    declared = _declared_threshold_names(REPO_ROOT / "dev")

    assert declared >= _MINIMUM_CONSUMER_BACKED_THRESHOLDS, (
        f"pinned thresholds that lost their live consumer: {sorted(_MINIMUM_CONSUMER_BACKED_THRESHOLDS - declared)}"
    )


def test_a_threshold_whose_only_consumer_vanishes_is_reported(tmp_path: Path) -> None:
    """The teeth: the scan distinguishes a declared name from an orphaned one.

    Driven over an isolated tree holding one consumer that declares a single
    pinned name, so the clean reading above and this proof of detection run
    in the same suite.
    """
    (tmp_path / "consumer.py").write_text(
        f"_P95_WALL_ADVISORY_SECONDS = {_LEDGER_WALL_S}\n",
        encoding="utf-8",
    )

    declared = _declared_threshold_names(tmp_path)

    assert declared == {"_P95_WALL_ADVISORY_SECONDS"}
    assert not declared >= _MINIMUM_CONSUMER_BACKED_THRESHOLDS, (
        "a consumer that dropped one of its two thresholds must not clear the floor"
    )


def test_restoring_a_missing_advisory_clears_the_floor_rather_than_failing_it(tmp_path: Path) -> None:
    """The repair this file motivates must not redden it.

    The counterpart teeth to the case above, and the reason the assertion is a
    superset: driven over an isolated tree holding every pinned name, which is
    what ``dev/`` looks like once the retired cold-start advisory is restored.
    Under the previous equality this tree failed, so the only way to keep the
    suite green was to leave the advisory deleted.
    """
    declarations = [f"{name} = {value}" for name, value in _PINNED_THRESHOLDS.items()]
    (tmp_path / "consumer.py").write_text("\n".join(declarations) + "\n", encoding="utf-8")

    declared = _declared_threshold_names(tmp_path)

    assert declared == set(_PINNED_THRESHOLDS)
    assert declared >= _MINIMUM_CONSUMER_BACKED_THRESHOLDS, (
        "restoring the missing advisory must clear the floor, not fail it"
    )


def test_a_threshold_relaxed_by_an_expression_is_not_read_as_agreement(tmp_path: Path) -> None:
    """A right-hand side this gate cannot evaluate is drift, not a pass.

    The value capture used to stop at the first whitespace, so a consumer that
    widened its threshold with anything spaced -- ``3.0 if _SLOW else 300.0``,
    ``4.0 * 100`` -- handed the scan the leading ``3.0`` and was read as
    agreeing with the figure proved above. That is precisely the relaxation
    this gate exists to catch, passing it a hundredfold. The capture now runs
    to the end of the declaration and the result is parsed, so a right-hand
    side that is not a bare literal is reported rather than partly read.
    """
    (tmp_path / "conditional.py").write_text(
        f"_P95_WALL_ADVISORY_SECONDS = {_LEDGER_WALL_S} if _SLOW else {_LEDGER_WALL_S * 100}\n",
        encoding="utf-8",
    )
    (tmp_path / "arithmetic.py").write_text(
        f"_P95_WEDGE_WALL_TO_CPU_RATIO = {_LEDGER_RATIO} * 100\n",
        encoding="utf-8",
    )

    drifted, checked = _threshold_drift(tmp_path)

    assert checked == 2
    assert len(drifted) == 2, f"a spaced expression was read as the literal it starts with: {drifted}"


def test_a_threshold_spelled_as_an_equal_number_is_not_reported_as_drift(tmp_path: Path) -> None:
    """Agreement is numeric, not textual.

    The counterpart to the case above, and the reason the comparison parses
    rather than merely tightening the string match: ``7`` and ``7.0`` are the
    same threshold, and reporting the first as drift would be a false alarm
    the reader learns to wave through -- the decay this module already guards
    against in the advisory itself.
    """
    (tmp_path / "consumer.py").write_text(
        f"_COLD_START_WALL_ADVISORY_S = {int(_COLD_START_WALL_S)}\n",
        encoding="utf-8",
    )

    drifted, checked = _threshold_drift(tmp_path)

    assert checked == 1
    assert not drifted, f"an equal value spelled as an int was reported as drift: {drifted}"
