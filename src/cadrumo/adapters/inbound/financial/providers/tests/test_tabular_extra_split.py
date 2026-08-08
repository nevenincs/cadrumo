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
subprocess whose import system genuinely cannot find ``pynvml`` -- the module
the extra's registry record probes -- so the production guard fires for the
production reason. Every case asserts that precondition before asserting
anything else: a run where the extra was quietly present would otherwise report
"nothing refused" indistinguishably from a guard that never fires at all.

The fixtures are producer-shaped, not authored to match the reader. The known
side is a real BBVA export (Spanish headers, ``;`` delimiter, comma decimals,
cp1252); the unknown side is an expenses-app export whose header vocabulary
(``merchant``, ``net``, ``vat_rate``, ``gross``) belongs to no bank layout. Both
are already bundled, and their sides were confirmed by measurement rather than
assumed: detection claims the first with ``CsvProvider`` and claims the second
with nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "financial"
_KNOWN_LAYOUT = _FIXTURES / "bbva-sample.csv"
_UNKNOWN_VOCABULARY = _FIXTURES / "tabular-dialects" / "expenses_app_export_2026.csv"

#: The known-layout fixture's data rows, counted from the file rather than from
#: the reader, so a parser that silently dropped one would fail this.
_KNOWN_LAYOUT_ROWS = 2

_BLOCK_EXTRA = """
import sys
class _AbsentPynvml:
    def find_spec(self, name, path=None, target=None):
        if name == "pynvml" or name.startswith("pynvml."):
            raise ModuleNotFoundError("No module named %r" % name)
        return None
sys.meta_path.insert(0, _AbsentPynvml())
"""


def _run_case(body: str, *, extra_absent: bool, tmp_path: Path) -> dict[str, object]:
    """Run ``body`` in a subprocess and return the JSON object it prints.

    ``extra_absent`` selects whether the child's import system can find the
    extra's probe module, which is the only difference between the two
    environments the split is defined over.
    """
    preamble = textwrap.dedent(f"""
        import json, logging
        logging.disable(logging.CRITICAL)
        from pathlib import Path
        from cadrumo.core import LLM_EXTRA
        from cadrumo.core._optional_extras import optional_extra_available
        result = {{"extra_available": optional_extra_available(LLM_EXTRA)}}
        known = Path({str(_KNOWN_LAYOUT)!r})
        unknown = Path({str(_UNKNOWN_VOCABULARY)!r})
    """)
    # Assembled from flush-left segments rather than one interpolated f-string:
    # embedding a multi-line block inside an indented template makes
    # ``dedent`` compute a common prefix of zero and misalign every other line.
    script = "\n".join(
        (
            _BLOCK_EXTRA if extra_absent else "",
            preamble,
            textwrap.dedent(body),
            'print("__RESULT__" + json.dumps(result))',
        )
    )
    completed = subprocess.run(  # noqa: S603 - resolved interpreter, test-authored script, no shell
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=300,
        env={
            **_child_env(),
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
        },
    )
    marker = [line for line in completed.stdout.splitlines() if line.startswith("__RESULT__")]
    assert marker, f"child produced no result:\nstdout={completed.stdout}\nstderr={completed.stderr}"
    payload = json.loads(marker[0].removeprefix("__RESULT__"))
    assert payload["extra_available"] is (not extra_absent), (
        "the child's environment did not carry the extra state the case is defined over; "
        "every assertion below would be meaningless"
    )
    return payload


def _child_env() -> dict[str, str]:
    """Return the parent environment minus any storage-root override."""
    import os

    return {key: value for key, value in os.environ.items() if key != "CADRUMO_LOCAL_STORAGE_ROOT"}


def test_known_fixed_layout_imports_fully_without_the_extra(tmp_path: Path) -> None:
    """The core side of the split: a recognised layout needs no extra at all."""
    result = _run_case(
        """
        from cadrumo.adapters.inbound.financial.providers._detection import detect_provider
        provider = detect_provider(known)
        result["provider"] = type(provider).__name__ if provider else None
        rows = list(provider.ingest(known))
        result["rows"] = len(rows)
        result["directions"] = [row.direction for row in rows]
        """,
        extra_absent=True,
        tmp_path=tmp_path,
    )

    assert result["provider"] == "CsvProvider", "a known layout must take its exact parser"
    assert result["rows"] == _KNOWN_LAYOUT_ROWS, "every row of a known layout must import on a core install"
    assert all(result["directions"]), "each imported row must carry a direction"


def test_unknown_vocabulary_refuses_at_the_mapping_call_naming_the_extra(tmp_path: Path) -> None:
    """The gated side: the refusal must name the install, not blame the file."""
    result = _run_case(
        """
        from cadrumo.adapters.inbound.financial.providers._mapped_tabular import MappedTabularProvider
        try:
            list(MappedTabularProvider().ingest(unknown))
            result["raised"] = None
        except BaseException as exc:
            result["raised"] = type(exc).__name__
            result["message"] = str(exc)
        """,
        extra_absent=True,
        tmp_path=tmp_path,
    )

    assert result["raised"] == "MissingOptionalExtraError", (
        f"the mapping call must refuse instructively; got {result['raised']!r}"
    )
    message = str(result["message"])
    assert "cadrumo[llm]" in message, f"the refusal must name the install that resolves it; got {message!r}"
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
    result = _run_case(
        """
        from cadrumo.adapters.inbound.financial.providers._mapped_tabular import MappedTabularProvider
        try:
            list(MappedTabularProvider().ingest(unknown))
            result["raised"] = None
        except BaseException as exc:
            result["raised"] = type(exc).__name__
            result["message"] = str(exc)
        """,
        extra_absent=False,
        tmp_path=tmp_path,
    )

    assert result["raised"] != "MissingOptionalExtraError", (
        "with the extra installed the missing-extra refusal must not fire; "
        "it would mean the case above proved nothing about absence"
    )
    assert "cadrumo[llm]" not in str(result.get("message", "")), (
        "the install hint must be specific to the absent install"
    )
