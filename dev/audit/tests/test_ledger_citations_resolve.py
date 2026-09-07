"""Gate: a file the ledger cites as a reader must exist and name its subject.

A classification's weight comes from what it can be checked against. "No
runtime caller, but dev/registry/parity/maintenance.py consumes it" is
falsifiable; "used by the design-time tooling" is not. So the ledger names
files, and this refuses a name that no longer holds.

The failure it was built from is the quiet kind. The registry parity cluster
cited ``dev/registry/analysis/load_census_classification.py`` among the readers
of eleven symbols. That file mentions the ``record_design_coverage`` MODULE
while classifying import-time load behaviour and consumes none of the eleven,
so the citation overstated the readership and made a reader-less symbol look
attended. Nothing would have caught it: no gate reads evidence prose.

Deliberately narrow. It does NOT require a cluster to cite anything -- several
legitimate classifications have no file reader at all, naming a legal default,
a documented port, or an implementer class instead, and demanding a path would
red those for being a different honest shape. It checks only the claims
actually made: if evidence names a repository path, that path must resolve and
must mention at least one of the entry's subjects.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any, Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LEDGER: Final[Path] = REPO_ROOT / "dev" / "audit" / "reachability_classification.toml"

#: A repository-relative source path as the evidence prose spells one.
_CITED_PATH: Final[re.Pattern[str]] = re.compile(r"(?:dev|src|tests)/[A-Za-z0-9_./-]+\.(?:py|toml)")

_ENTRY_TABLES: Final[tuple[str, ...]] = ("symbol_cluster", "module", "test_module")


def _subjects(entry: dict[str, Any]) -> list[str]:
    """Return the names an entry is about, for a cited file to mention.

    A cluster carries a ``symbols`` key and is about exactly those names. When
    the list is EMPTY the cluster is a resolved record with no live subject, and
    it has no names for a file to mention -- the falling back to its own title
    below would look for a prose sentence in source, which no file contains and
    which was never a claim about the tree.

    A module entry carries no ``symbols`` key at all and is about its dotted
    path, which a reader spells dotted or as its tail.
    """
    if "symbols" in entry:
        return [str(s) for s in entry.get("symbols") or ()]
    name = str(entry.get("name", ""))
    return [name, name.rsplit(".", 1)[-1]] if name else []


def unresolved_citations(data: dict[str, Any], root: Path) -> list[str]:
    """Return ``entry -> path`` for citations that are missing or wholly off-subject.

    Two rules, and the split between them is what keeps the check both toothed
    and satisfiable.

    EVERY cited file must exist. That half never needs an exception: a path
    naming nothing is a broken locator whatever the entry is about.

    At least ONE cited file must mention a subject -- not every one. The defect
    this was written for is an entry whose citation names a SIBLING rather than
    the symbol it is offered as evidence for, and that is still caught, because
    such an entry has no on-subject citation at all. Requiring every citation to
    name a subject instead forbade two legitimate shapes: evidence that cites
    the CONSUMER of a symbol, which is precisely where "nothing reaches this"
    is proved, and a resolved entry whose symbols list has been emptied because
    the work is done, for which the requirement is unsatisfiable by
    construction -- no file can mention a member of an empty list.
    """
    broken: list[str] = []
    for table in _ENTRY_TABLES:
        for entry in data.get(table, ()):
            subjects = [s for s in _subjects(entry) if s]
            evidence = str(entry.get("evidence", ""))
            cited_paths = sorted(set(_CITED_PATH.findall(evidence)))
            on_subject = False
            for cited in cited_paths:
                path = root / cited
                if not path.is_file():
                    broken.append(f"{entry.get('name')} -> {cited} (no such file)")
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                on_subject = on_subject or any(subject in text for subject in subjects)
            if subjects and cited_paths and not on_subject:
                broken.append(
                    f"{entry.get('name')} -> no cited file names any subject of the entry "
                    f"({', '.join(cited_paths)})",
                )
    return broken


def test_the_ledger_still_cites_files() -> None:
    """A population floor: citing nothing would make the check vacuous."""
    data = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))
    cited = {
        path
        for table in _ENTRY_TABLES
        for entry in data.get(table, ())
        for path in _CITED_PATH.findall(str(entry.get("evidence", "")))
    }

    assert len(cited) >= 8, (
        f"the ledger cites only {len(cited)} file path(s); either the prose has "
        "stopped naming its readers or this reader has drifted, and the gate is "
        "inert rather than satisfied"
    )


def test_every_cited_file_resolves_and_names_its_subject() -> None:
    """The direction the gate exists for."""
    data = tomllib.loads(_LEDGER.read_text(encoding="utf-8"))

    broken = unresolved_citations(data, REPO_ROOT)

    assert broken == [], (
        "the ledger cites these files as evidence, and each either does not exist "
        "or does not mention the symbol it is offered as evidence for; correct the "
        f"prose rather than the file: {broken}"
    )


def test_the_gate_catches_a_citation_that_names_no_subject(tmp_path: Path) -> None:
    """Detector teeth: the exact shape the registry parity cluster carried."""
    reader = tmp_path / "dev" / "tool.py"
    reader.parent.mkdir(parents=True)
    reader.write_text("from x import something_else\n", encoding="utf-8")
    data = {"symbol_cluster": [{"name": "c", "symbols": ["absent_symbol"], "evidence": "read by dev/tool.py"}]}

    assert unresolved_citations(data, tmp_path) == [
        "c -> no cited file names any subject of the entry (dev/tool.py)",
    ]


def test_the_gate_catches_a_citation_to_a_missing_file(tmp_path: Path) -> None:
    """Detector teeth: a reader that was renamed or deleted."""
    data = {"symbol_cluster": [{"name": "c", "symbols": ["thing"], "evidence": "read by dev/gone.py"}]}

    assert unresolved_citations(data, tmp_path) == [
        "c -> dev/gone.py (no such file)",
        "c -> no cited file names any subject of the entry (dev/gone.py)",
    ]


def test_a_citation_that_names_its_subject_is_accepted(tmp_path: Path) -> None:
    """The normal case, so the gate is not merely always-red."""
    reader = tmp_path / "dev" / "tool.py"
    reader.parent.mkdir(parents=True)
    reader.write_text("from x import thing\n\nthing()\n", encoding="utf-8")
    data = {"symbol_cluster": [{"name": "c", "symbols": ["thing"], "evidence": "read by dev/tool.py"}]}

    assert unresolved_citations(data, tmp_path) == []


def test_one_on_subject_citation_admits_a_supporting_consumer_citation(tmp_path: Path) -> None:
    """A citation to a consumer is evidence, not drift.

    Where "nothing reaches this" is proved is precisely in the file that does
    NOT mention the symbol, so requiring every citation to name a subject
    forbade the shape the claim is made of. One on-subject citation is enough.
    """
    owner = tmp_path / "dev" / "owner.py"
    owner.parent.mkdir(parents=True)
    owner.write_text("def thing() -> None:\n    return None\n", encoding="utf-8")
    (tmp_path / "dev" / "consumer.py").write_text("from x import something_else\n", encoding="utf-8")
    data = {
        "symbol_cluster": [
            {
                "name": "c",
                "symbols": ["thing"],
                "evidence": "defined in dev/owner.py and absent from dev/consumer.py",
            },
        ],
    }

    assert unresolved_citations(data, tmp_path) == []


def test_a_resolved_cluster_with_no_symbols_still_needs_its_files_to_exist(tmp_path: Path) -> None:
    """The bound on the exemption: emptying ``symbols`` does not licence a dead path."""
    data = {"symbol_cluster": [{"name": "c", "symbols": [], "evidence": "fixed in dev/gone.py"}]}

    assert unresolved_citations(data, tmp_path) == ["c -> dev/gone.py (no such file)"]


def test_an_entry_citing_no_path_is_left_alone(tmp_path: Path) -> None:
    """A legal default or a named implementer class is a different honest shape."""
    data = {
        "symbol_cluster": [
            {"name": "c", "symbols": ["RATE"], "evidence": "The art. 95.1 default, documented in the BOE."}
        ]
    }

    assert unresolved_citations(data, tmp_path) == []
