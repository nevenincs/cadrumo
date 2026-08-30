"""Every production request states its evidence posture; none inherits it from a default.

The off-host consent gate's first line reads
``if not request.evidence_derived or not provider_reads_off_host(provider)``,
so ``evidence_derived`` is the whole load-bearing bit: an unmarked request is
dispatched to a hosted provider with no consent token AND -- because the gate
returns before the ledger append -- with no record, leaving it invisible to the
withdrawal survey that tells an operator what left their machine.

The field defaults to ``False``, which is the right default for a model whose
callers are mostly not evidence readers. But a default means a builder that
omits the keyword and a builder that judged the content non-evidential look
identical in source and in a diff. This gate removes that ambiguity: **every
production ``LLMRequest`` construction must pass ``evidence_derived``
explicitly**, and the sites that pass a constant ``False`` must be exactly the
ones enrolled below with a stated reason.

The consequence is the point. A sixth builder is a deliberate decision -- either
it marks its content, or it enrols here and someone reads the reason -- rather
than an omission whose diff does not look like a confidentiality change.

**The enrolled entry carries its own tripwire**, because an allowlist whose
reason silently stops being true is worse than none. The column-role mapper is
enrolled on the ground that it transmits schema labels rather than taxpayer
content, and the structural fact holding that up is that its prompt builder has
no channel for a cell value: it takes headers and nothing else. Widening that
signature reds this module, which is exactly when the enrolment needs
re-deciding.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from ...tests import aeat_relative, production_python_files
from ..column_role_mapping import build_column_role_mapping_prompt

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_REQUEST_MODEL = "LLMRequest"
_MARKER = "evidence_derived"

_BUILDERS_DECLARING_NO_EVIDENCE = {
    "llm/column_role_mapping.py": (
        "Column-role mapping transmits the header row -- the file's schema labels -- and never a "
        "cell value: the prompt builder accepts headers and nothing else, and the instruction it "
        "compiles forbids the model to reproduce data. Marking this request evidence-derived would "
        "put a schema-shaped request behind a taxpayer-evidence consent token and close the gated "
        "hosted lane the tabular measurement runs through."
    ),
}


def _request_construction_sites() -> list[tuple[str, int, ast.Call]]:
    """Return every production ``LLMRequest(...)`` call, located by AST.

    An AST walk rather than a text scan, because the package's own docstrings
    show ``LLMRequest(prompt=...)`` in usage examples and a source slice cannot
    tell an example from a call.
    """
    sites: list[tuple[str, int, ast.Call]] = []
    for path in production_python_files():
        source = path.read_text(encoding="utf-8")
        # A call to the request model needs its name in the source, so a module
        # that never spells it cannot hold a call site. The AST walk below is
        # still what CLASSIFIES a hit -- the package's own docstrings show
        # ``LLMRequest(prompt=...)`` in examples, and only a parse tells an
        # example from a call. The screen decides which modules are worth
        # parsing; it does not decide what counts.
        if _REQUEST_MODEL not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
            if name == _REQUEST_MODEL:
                sites.append((aeat_relative(path), node.lineno, node))
    return sites


def test_the_scan_finds_the_known_request_builders() -> None:
    """The sweep is non-vacuous: it must locate the builders that are known to exist.

    Without this, a walk broken by a rename would report zero sites and every
    assertion below would pass over nothing.
    """
    found = {relative for relative, _, _ in _request_construction_sites()}

    for expected in (
        "llm/column_role_mapping.py",
        "llm/evidence_draft_text.py",
        "llm/evidence_draft_vision.py",
        "llm/text_classifier.py",
        "llm/vision_classifier.py",
    ):
        assert expected in found, f"the request-construction scan did not find the known builder in {expected}"


def test_every_production_request_states_its_evidence_posture() -> None:
    """No production request may inherit the marker from the model default."""
    omitting = [
        f"{relative}:{lineno}"
        for relative, lineno, call in _request_construction_sites()
        if not any(keyword.arg == _MARKER for keyword in call.keywords)
    ]

    assert omitting == [], (
        f"these production LLMRequest constructions do not state {_MARKER}, so whether their content "
        f"derives from taxpayer evidence is a default rather than a judgement: {omitting}. Pass the "
        "keyword explicitly -- and if the value is False, enrol the module in this test's "
        "declared set with the reason."
    )


def test_the_requests_declaring_no_evidence_are_exactly_the_enrolled_ones() -> None:
    """A new non-evidential builder must be enrolled, not merely written."""
    declaring_false = {
        relative
        for relative, _, call in _request_construction_sites()
        for keyword in call.keywords
        if keyword.arg == _MARKER and isinstance(keyword.value, ast.Constant) and keyword.value.value is False
    }

    unenrolled = sorted(declaring_false - _BUILDERS_DECLARING_NO_EVIDENCE.keys())
    assert unenrolled == [], (
        f"these builders declare {_MARKER}=False without an enrolled reason: {unenrolled}. Off-host "
        "dispatch of an unmarked request crosses no consent gate and leaves no ledger entry, so the "
        "judgement that its content is not taxpayer evidence belongs in this file where it is read."
    )

    stale = sorted(_BUILDERS_DECLARING_NO_EVIDENCE.keys() - declaring_false)
    assert stale == [], (
        f"these modules are enrolled as declaring no evidence but no longer do: {stale}. Remove the "
        "enrolment rather than leaving a reason nothing is attached to."
    )


def test_the_column_role_prompt_has_no_channel_for_a_cell_value() -> None:
    """The structural fact the enrolment above rests on.

    The mapper is enrolled because it sends schema labels rather than taxpayer
    content, and what makes that a property rather than call-site discipline at
    the prompt layer is that the compiler accepts headers and nothing else. A
    second parameter carrying rows would make the enrolment false, so it reds
    here.
    """
    parameters = list(inspect.signature(build_column_role_mapping_prompt).parameters)

    assert parameters == ["headers"], (
        f"the column-role prompt builder now accepts {parameters}; it is enrolled as sending no "
        "taxpayer content on the ground that headers are the only thing it can carry, so a new "
        "input channel requires that enrolment to be re-decided rather than inherited"
    )

    prompt = build_column_role_mapping_prompt(("Fecha", "Importe"))
    assert "Do not read, copy or produce any data value." in prompt, (
        "the compiled instruction no longer forbids the model to reproduce data; the enrolment "
        "above claims this lane carries schema labels only"
    )
