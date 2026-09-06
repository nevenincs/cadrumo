#!/usr/bin/env python
"""Tests for the semantic duplication detectors and the dispatch that names them.

``dev.audit.semantic_duplication`` ships seven detectors behind a ``_DETECTORS``
dispatch table and a ``run`` driver, and nothing reached any of them. Its sibling
``dev.audit.duplication`` measures COPY-PASTE through jscpd, is wired to
``just audit-duplication``, and carries two test modules. This one has no justfile
recipe, no workflow lane, and is composed by neither ``advisory`` nor ``report``;
``just check-semantic`` drives ``dev.audit.semantic``, a different module. The only
test references it had were the private ``_load_modules`` helper and the
``Candidate`` type, so every detector and the dispatch keying them were undriven.

The module's own docstring says why it exists: jscpd matches token sequences, so
"a concept implemented twice in different syntax is invisible to it, and that is
exactly the duplication this project's rules treat as a blocker".

These drive the public ``run`` over constructed trees, so a dispatch key that stops
resolving, or a detector that stops firing, is a red test rather than a capability
that quietly reports nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..semantic_duplication import _DETECTORS, run

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SHARED = ("alpha_dep", "beta_dep", "gamma_dep", "delta_dep", "epsilon_dep")
_DISJOINT = ("zeta_dep", "eta_dep", "theta_dep", "iota_dep", "kappa_dep")


def _module(package: Path, name: str, imports: tuple[str, ...]) -> None:
    """Write a module whose only content is its first-party import set."""
    lines = [f"from {target} import thing" for target in imports]
    (package / name).write_text(chr(10).join(lines) + chr(10), encoding="utf-8")


def test_every_dispatch_key_runs_the_detector_it_names(tmp_path: Path) -> None:
    """The dispatch is the only route to the detectors, so it must resolve entire.

    ``run`` looks each requested name up in ``_DETECTORS`` and calls the result. A
    key that lost its callable would raise ``KeyError`` for that name alone, which
    is invisible while nothing asks for every name at once.
    """
    package = tmp_path / "cadrumo"
    package.mkdir()
    _module(package, "solo.py", _SHARED)

    for name in sorted(_DETECTORS):
        assert run(package, [name]) is not None

    assert sorted(_DETECTORS) == [
        "call_fingerprint",
        "duplicated_derivation",
        "enum_subset",
        "field_set",
        "import_overlap",
        "package_overlap",
        "scarce_literal",
    ]


def test_two_modules_reaching_for_the_same_collaborators_are_reported(tmp_path: Path) -> None:
    """The positive case: identical first-party import sets, and no edge between them."""
    package = tmp_path / "cadrumo"
    package.mkdir()
    _module(package, "left.py", _SHARED)
    _module(package, "right.py", _SHARED)

    found = run(package, ["import_overlap"])

    assert [candidate.sites for candidate in found] == [("left.py", "right.py")]
    assert found[0].fingerprint == "jaccard=1.00"


def test_modules_sharing_no_collaborator_are_not_reported(tmp_path: Path) -> None:
    """Sibling blindness: a detector that fired on anything would be worthless.

    Same module count, same import count, same shape -- only the overlap differs, so
    a green here is about the Jaccard floor and not about the corpus being small.
    """
    package = tmp_path / "cadrumo"
    package.mkdir()
    _module(package, "left.py", _SHARED)
    _module(package, "right.py", _DISJOINT)

    assert run(package, ["import_overlap"]) == []
