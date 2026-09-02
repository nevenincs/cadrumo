"""The tabular lane splits mid-pipeline at the ``cadrumo[llm]`` boundary.

A known fixed-layout export is a deterministic read of a known structure, so it
must import completely on a core install. A file of no recognised layout needs
the semantic column-role mapping call, which lives behind the extra -- and when
the extra is absent the operator must be told that, by name.

The failure this gates is a misdirection rather than a crash. The mapping call
raises :class:`MissingOptionalExtraError`, which is both a ``CadrumoError`` and
an ``ImportError``, so a broad guard swallows it and the lane reports "column
roles could not be established". That sentence describes the operator's FILE,
while what is actually missing is a capability of their INSTALL -- so the
operator edits a CSV that was never wrong, and the one command that would fix it
is never named.

**Absence is real here, not simulated with a stub.** Each case runs in a
fresh spawned interpreter whose import system genuinely cannot find ``pynvml`` -- the module
the extra's registry record probes -- so the production guard fires for the
production reason. Every case asserts that precondition before asserting
anything else: a run where the extra was quietly present would otherwise report
"nothing refused" indistinguishably from a guard that never fires at all.

The fixtures are producer-shaped, not authored to match the reader. The known
side is a real BBVA export (Spanish headers, ``;`` delimiter, comma decimals,
cp1252); the unknown side is an expenses-app export whose header vocabulary
(``merchant``, ``net``, ``iva_rate``, ``gross``) belongs to no bank layout. Both
are already bundled, and their sides were confirmed by measurement rather than
assumed: detection claims the first with ``CsvProvider`` and claims the second
with nothing.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import sys
from collections.abc import Sequence
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from multiprocessing.queues import Queue
from pathlib import Path
from queue import Empty
from types import ModuleType
from typing import Literal, TypedDict, override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "financial"
_KNOWN_LAYOUT = _FIXTURES / "bbva-sample.csv"
_UNKNOWN_VOCABULARY = _FIXTURES / "tabular-dialects" / "expenses_app_export_2026.csv"

#: The known-layout fixture's data rows, counted from the file rather than from
#: the reader, so a parser that silently dropped one would fail this.
_KNOWN_LAYOUT_ROWS = 2


class _AbsentPynvml(MetaPathFinder):
    """Make the child interpreter genuinely unable to discover ``pynvml``."""

    @override
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        del path, target
        if fullname == "pynvml" or fullname.startswith("pynvml."):
            raise ModuleNotFoundError(f"No module named {fullname!r}")
        return None


class _ProbeResult(TypedDict, total=False):
    """Typed payload returned by one fresh optional-extra probe."""

    extra_available: bool
    provider: str | None
    rows: int
    directions: list[str]
    raised: str | None
    message: str
    #: The refusal renders its install command downstream from these facts
    #: rather than embedding one in the message, so the probe carries them.
    refused_extra: str | None


class _ProbeMessage(TypedDict):
    """Typed queue envelope separating a probe payload from worker failure."""

    payload: _ProbeResult | None
    error: str | None


def _probe_worker(
    case: Literal["known", "unknown"],
    *,
    extra_absent: bool,
    storage_root: str,
    results: Queue[_ProbeMessage],
) -> None:
    """Run one probe in a genuinely fresh multiprocessing spawn interpreter."""
    try:
        if extra_absent:
            sys.meta_path.insert(0, _AbsentPynvml())
        logging.disable(logging.CRITICAL)
        os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = storage_root

        from ......core.optional_extras import LLM_EXTRA, optional_extra_available

        result: _ProbeResult = {"extra_available": optional_extra_available(LLM_EXTRA)}
        if case == "known":
            from ..detection import detect_provider

            provider = detect_provider(_KNOWN_LAYOUT)
            result["provider"] = type(provider).__name__ if provider else None
            assert provider is not None, "known layout did not resolve to a provider"
            rows = list(provider.ingest(_KNOWN_LAYOUT))
            result["rows"] = len(rows)
            result["directions"] = [row.direction.value for row in rows]
        else:
            from .._mapped_tabular import MappedTabularProvider

            try:
                list(MappedTabularProvider().ingest(_UNKNOWN_VOCABULARY))
                result["raised"] = None
            except BaseException as exc:
                result["raised"] = type(exc).__name__
                result["message"] = str(exc)
                context = getattr(exc, "context", None) or {}
                refused = context.get("extra")
                result["refused_extra"] = str(refused) if refused is not None else None
        results.put({"payload": result, "error": None})
    except BaseException as exc:
        results.put({"payload": None, "error": f"{type(exc).__name__}: {exc}"})


def _run_case(case: Literal["known", "unknown"], *, extra_absent: bool, tmp_path: Path) -> _ProbeResult:
    """Run one probe in a fresh spawn interpreter and return its typed payload."""
    context = multiprocessing.get_context("spawn")
    results: Queue[_ProbeMessage] = Queue(ctx=context.get_context())
    process = context.Process(
        target=_probe_worker,
        kwargs={
            "case": case,
            "extra_absent": extra_absent,
            "storage_root": str(tmp_path / "storage"),
            "results": results,
        },
    )
    process.start()
    try:
        try:
            message = results.get(timeout=300)
        except Empty as exc:
            process.join(timeout=1)
            raise AssertionError(f"child produced no result; exitcode={process.exitcode}") from exc
        process.join(timeout=300)
        assert not process.is_alive(), "child probe exceeded its timeout"
        assert process.exitcode == 0, f"child probe exited with {process.exitcode}: {message['error']}"
        assert message["error"] is None, message["error"]
        payload = message["payload"]
        assert payload is not None, "child probe returned no payload"
        assert payload["extra_available"] is (not extra_absent), (
            "the child's environment did not carry the extra state the case is defined over; "
            "every assertion below would be meaningless"
        )
        return payload
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        process.close()
        results.close()
        results.join_thread()


def test_known_fixed_layout_imports_fully_without_the_extra(tmp_path: Path) -> None:
    """The core side of the split: a recognised layout needs no extra at all."""
    result = _run_case("known", extra_absent=True, tmp_path=tmp_path)

    assert result["provider"] == "CsvProvider", "a known layout must take its exact parser"
    assert result["rows"] == _KNOWN_LAYOUT_ROWS, "every row of a known layout must import on a core install"
    directions = result["directions"]
    assert isinstance(directions, list)
    assert all(isinstance(direction, str) for direction in directions)
    assert all(directions), "each imported row must carry a direction"


def test_unknown_vocabulary_refuses_at_the_mapping_call_naming_the_extra(tmp_path: Path) -> None:
    """The gated side: the refusal must name the install, not blame the file."""
    result = _run_case("unknown", extra_absent=True, tmp_path=tmp_path)

    assert result["raised"] == "MissingOptionalExtraError", (
        f"the mapping call must refuse instructively; got {result['raised']!r}"
    )
    message = str(result["message"])
    # The refusal names the extra in its context and the install command is
    # rendered downstream from it, so the fact is what this pins.
    assert result["refused_extra"] == "llm", (
        f"the refusal must name the extra that resolves it; got {result['refused_extra']!r}"
    )
    assert "column roles could not be established" not in message, (
        "the refusal must not blame the operator's file for an absent capability"
    )


def test_the_refusal_is_caused_by_absence_and_not_by_the_file(tmp_path: Path) -> None:
    """Positive control: the same file stops refusing once the extra is present.

    Without this, the case above is equally consistent with a fixture that
    refuses for some unrelated reason -- a malformed CSV would satisfy "it
    raised" just as well, and the gate would pass while proving nothing about
    the extra boundary.
    """
    result = _run_case("unknown", extra_absent=False, tmp_path=tmp_path)

    assert result["raised"] != "MissingOptionalExtraError", (
        "with the extra installed the missing-extra refusal must not fire; "
        "it would mean the case above proved nothing about absence"
    )
    assert "cadrumo[llm]" not in str(result.get("message", "")), (
        "the install hint must be specific to the absent install"
    )
