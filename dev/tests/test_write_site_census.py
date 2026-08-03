"""The write-site census must discriminate, not merely match names.

Every assertion here pins a distinction whose absence produced a real wrong
number during the storage campaign: ``.save`` counted 138 secure-object writes
as file writes, and an attribute call named ``replace`` counted ``str.replace``
as ``Path.replace`` and reported 267 sites where roughly 99 existed. A census
that cannot tell those apart returns a confident figure about the wrong set, so
each discrimination is asserted in **both** directions -- the shape that must
count, and the lookalike that must not.
"""

from __future__ import annotations

import ast

import pytest

from dev.write_site_census import WriteSite, classify, write_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _call(source: str) -> ast.Call:
    """Return the first call expression in ``source``."""
    parsed = ast.parse(source)
    for node in ast.walk(parsed):
        if isinstance(node, ast.Call):
            return node
    raise AssertionError(f"no call expression in {source!r}")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("path.write_text('x')", "write_text"),
        ("path.write_bytes(b'x')", "write_bytes"),
        ("path.mkdir(parents=True)", "mkdir"),
        ("open(path, 'w')", "open"),
        ("open(path, mode='a')", "open"),
        ("shutil.copytree(source, destination)", "copytree"),
        ("os.makedirs(path)", "makedirs"),
        ("target.replace(destination)", "replace"),
        ("workbook.save(path)", "save"),
    ],
)
def test_a_real_file_producing_call_is_counted(source: str, expected: str) -> None:
    """Each shape that genuinely creates or replaces a filesystem object is matched."""
    found = write_target(_call(source))
    assert found is not None, f"{source!r} produces a file and must be counted"
    assert found[0] == expected


@pytest.mark.parametrize(
    ("source", "why"),
    [
        ("repository.save(record)", "a secure-object save writes an encrypted SQL row, not a file"),
        ("buffer.save(stream)", "an in-memory buffer save touches no filesystem"),
        ("text.replace('a', 'b')", "str.replace takes two arguments; Path.replace takes one"),
        ("open(path, 'r')", "a read-mode open produces nothing"),
        ("open(path)", "the default mode is read"),
        ("path.exists()", "a predicate is not a write"),
        ("path.read_text()", "a read is not a write"),
    ],
)
def test_a_lookalike_is_not_counted(source: str, why: str) -> None:
    """Each shape that shares a method name with a writer, but writes nothing, is refused."""
    assert write_target(_call(source)) is None, f"{source!r} must not be counted: {why}"


def test_the_two_directions_disagree_on_the_same_method_name() -> None:
    """The discriminations are real, not an artefact of separate name lists.

    ``save`` and ``replace`` each appear in both directions above. If the
    selector keyed on the bare method name, one of the two directions would be
    wrong for each, so asserting them together is what proves the receiver and
    the arity are actually consulted.
    """
    assert write_target(_call("workbook.save(path)")) is not None
    assert write_target(_call("repository.save(record)")) is None
    assert write_target(_call("target.replace(destination)")) is not None
    assert write_target(_call("text.replace('a', 'b')")) is None


@pytest.mark.parametrize(
    ("origin", "local_params", "expected"),
    [
        ("storage_path", set(), "taxonomy"),
        ("cadrumo_audit_dir", set(), "taxonomy"),
        ("destination", {"destination"}, "pass_through"),
        ("self", set(), "pass_through"),
        ("self._root", set(), "pass_through"),
        ("<literal 'buckets'>", set(), "literal"),
        ("tmp_dir", set(), "temporary"),
        ("<Subscript>", set(), "unresolved"),
        ("computed", set(), "local"),
    ],
)
def test_provenance_classification(origin: str, local_params: set[str], expected: str) -> None:
    """Each origin shape lands in the bucket that describes where the path came from."""
    assert classify(origin, local_params=local_params, module_params=set()) == expected


def test_a_caller_supplied_path_is_pass_through_not_unenrolled() -> None:
    """The distinction the whole census exists to make.

    A site handed its path has no enrollment answer of its own -- the answer is
    "wherever the caller said". Classifying it as unenrolled would manufacture a
    finding; classifying it as enrolled would manufacture coverage. It is
    neither, and the third label is what lets the count mean something.
    """
    assert classify("output_dir", local_params={"output_dir"}, module_params=set()) == "pass_through"
    assert classify("output_dir", local_params=set(), module_params={"output_dir"}) == "pass_through"
    assert classify("output_dir", local_params=set(), module_params=set()) == "local"


def test_ambiguity_is_reported_rather_than_silently_trusted() -> None:
    """A site on a duck-typed name must announce that it needs a human read."""
    ambiguous = WriteSite(module="m.py", line=1, primitive="touch", origin="session", provenance="local")
    unambiguous = WriteSite(module="m.py", line=2, primitive="mkdir", origin="target", provenance="local")
    assert ambiguous.ambiguous
    assert not unambiguous.ambiguous
