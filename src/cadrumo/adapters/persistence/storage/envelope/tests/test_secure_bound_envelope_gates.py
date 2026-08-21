"""Both secure-bound read paths apply one envelope classification/version gate.

``SecureBoundRepository.load`` and the iterator behind ``iter_ids`` /
``iter_records`` each independently parsed the stored envelope, required the
repository's classification, and required its exact schema version. Only the
row wording differed. These tests pin that both now route through the one
``_validate_envelope`` helper and that each refusal still names its own row.

These assertions are STRUCTURAL, not behavioural, and deliberately so: the
extraction is behaviour-preserving by construction (both paths already ran the
same two checks and raised the same two error types), so no input can
distinguish the before and after. What CAN regress is the wiring -- a re-inlined
copy, a collapsed error type, or a lost row label -- and that is what is pinned
here. Behavioural coverage of the two gates themselves already lives in
``test_secure_bound_repository_contract.py``; this module does not restate it.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from ...errors import ClassificationError, EnvelopeVersionError
from .._secure_repository import SecureBoundRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_both_read_paths_route_through_the_one_envelope_gate() -> None:
    """Neither read path re-implements the classification/version checks.

    DISCRIMINATING, and the only assertion here that survives a re-inlining
    mutation: a byte-identical copy of the two checks pasted back into either
    path produces identical behaviour on every input, so no behavioural test
    can see it. This is what notices.
    """
    load_source = inspect.getsource(SecureBoundRepository.load)
    iter_source = inspect.getsource(SecureBoundRepository._iter_validated_rows)

    for name, source in (("load", load_source), ("_iter_validated_rows", iter_source)):
        assert _calls(source, "_validate_envelope"), f"{name} does not route through the shared envelope gate"
        assert "model_validate_json(" not in source, f"{name} parses the envelope itself instead of delegating"
        assert "classification is not" not in source, f"{name} re-implements the classification gate"
        assert "schema_version !=" not in source, f"{name} re-implements the schema-version gate"

    gate_source = inspect.getsource(SecureBoundRepository._validate_envelope)
    assert _calls(gate_source, "model_validate_json")
    assert "classification is not" in gate_source
    assert "schema_version !=" in gate_source


def test_the_gate_raises_the_two_distinct_typed_failures() -> None:
    """The shared gate keeps classification and version as SEPARATE failures.

    DISCRIMINATING for the collapse hazard: folding the two checks into one
    helper invites folding their error types too, which would make a
    version-skewed row indistinguishable from a mis-classified one at every
    call site. Asserted on the gate's own source because both branches must
    exist regardless of which rows a given store happens to hold.
    """
    gate_source = inspect.getsource(SecureBoundRepository._validate_envelope)

    assert "raise ClassificationError(" in gate_source
    assert "raise EnvelopeVersionError(" in gate_source
    assert ClassificationError is not EnvelopeVersionError
    # Neither is a subclass of the other, so a caller can still distinguish them.
    assert not issubclass(ClassificationError, EnvelopeVersionError)
    assert not issubclass(EnvelopeVersionError, ClassificationError)


def test_each_read_path_labels_its_own_row() -> None:
    """A single load and an iterator row stay distinguishable in diagnostics.

    DISCRIMINATING for the wording-collapse hazard: the point of threading a
    ``subject`` through the shared gate is that de-duplicating the checks must
    not de-duplicate the row identity. A gate that hard-coded one label would
    make an iterator refusal read as a single-load refusal.
    """
    load_source = inspect.getsource(SecureBoundRepository.load)
    iter_source = inspect.getsource(SecureBoundRepository._iter_validated_rows)

    assert "subject=" in load_source, "load does not pass a row label to the gate"
    assert "subject=" in iter_source, "the iterator does not pass a row label to the gate"
    assert "iterator row" in iter_source, "the iterator lost its distinct row wording"
    assert "iterator row" not in load_source, "load adopted the iterator's row wording"

    gate_source = inspect.getsource(SecureBoundRepository._validate_envelope)
    assert "{subject}" in gate_source, "the gate hard-codes a row label instead of using the caller's"


def test_the_gate_is_reachable_from_every_production_subclass() -> None:
    """No subclass overrides the gate or either read path.

    SUPPORTING: green under any re-inlining of the gate body. It forecloses a
    different escape -- a subclass shadowing ``load`` or the iterator and
    bringing its own checks back -- rather than proving the extraction.
    """
    subclasses: list[type] = []
    pending = [SecureBoundRepository]
    while pending:
        current = pending.pop()
        for child in current.__subclasses__():
            subclasses.append(child)
            pending.append(child)

    for subclass in subclasses:
        for attribute in ("_validate_envelope", "load", "_iter_validated_rows"):
            assert attribute not in vars(subclass), (
                f"{subclass.__name__} overrides {attribute}, bypassing the shared envelope gate"
            )


def test_sensitivity_and_schema_version_are_the_gate_inputs() -> None:
    """The gate reads the repository's declared sensitivity and version.

    SUPPORTING: a wiring sanity check on the descriptors the gate consumes, so
    the assertions above are known to be testing a gate that is actually bound
    to the repository's own contract rather than a constant.
    """
    gate_source = inspect.getsource(SecureBoundRepository._validate_envelope)

    assert "self.sensitivity" in gate_source
    assert "self.schema_version" in gate_source


def _calls(source: str, callee: str) -> bool:
    """Whether ``source`` actually CALLS ``callee``, not merely mentions it.

    A membership test on source text passes when the name appears in a
    docstring or a comment, so a surface that stopped delegating while keeping
    its prose reads as compliant. That is the mention-versus-containment hole:
    the check answers "does this code discuss the shared path" when the
    property is "does this code take it".
    """
    tree = ast.parse(textwrap.dedent(source))
    return any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Attribute) and node.func.attr == callee)
            or (isinstance(node.func, ast.Name) and node.func.id == callee)
        )
        for node in ast.walk(tree)
    )


def test_the_delegation_check_rejects_a_docstring_mention() -> None:
    """DISCRIMINATING: the shape the text check waved through.

    A surface that stops calling the shared path but keeps a sentence naming
    it is exactly what this gate exists to catch, and exactly what a
    membership test cannot tell apart from a call.
    """
    calling = "def load(self, key):\n    return self._validate_envelope(self._fetch(key))\n"
    mentioning = (
        "def load(self, key):\n"
        '    """Validation happens in _validate_envelope( ) elsewhere."""\n'
        "    return self._fetch(key)\n"
    )

    assert _calls(calling, "_validate_envelope")
    assert not _calls(mentioning, "_validate_envelope")
