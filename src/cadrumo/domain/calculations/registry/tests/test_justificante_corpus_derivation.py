"""The registry validator never derives the specimen corpus; it is supplied.

The ``declaracion_pdf`` specimen corpus is a checkout-time authoring input.
An earlier revision let the validator DERIVE its location by probing a
repo-shaped path, which forced production code to ask whether it was running
from a source checkout — a question a tax-filing product has no business
asking, and one that let a source-layout guess decide a filesystem read.

The derivation is gone. The corpus root is supplied by the authoring tool that
owns it, or it is absent and the specimen gate does not run. These tests pin
that one-way property: an unsupplied root stays ``None`` regardless of what the
surrounding filesystem looks like, so no later refactor can reintroduce a probe
without reddening a test that names the reason.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .....core.resources._boundary import bundled_path
from .._validate import RegistryValidator
from ..schema import RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

if TYPE_CHECKING:
    from pathlib import Path


def _catalogues() -> RegistryCatalogues:
    """An empty catalogue pair: these cases exercise construction, not validation."""
    return RegistryCatalogues(legal={}, sources={})


def test_an_unsupplied_corpus_root_stays_none(tmp_path: Path) -> None:
    """No ``source_root`` value causes a corpus root to be derived.

    Under the retired behaviour the constructor called a derivation helper
    here and resolved a path from ``source_root``; the field is now exactly
    the constructor argument.
    """
    validator = RegistryValidator(_catalogues(), source_root=tmp_path)

    assert validator.justificante_corpus_root is None


def test_an_unsupplied_root_stays_none_beside_a_real_specimen_tree(tmp_path: Path) -> None:
    """The probe the retired derivation performed is proven absent.

    Lays out the exact shape the old derivation searched for —
    ``<source_root>/../tests/fixtures/justificantes/<modelo>`` holding a real
    file — so a reintroduced probe would find something and populate the root.
    It must still be ``None``: the corpus is supplied, never discovered.
    """
    source_root = tmp_path / "_data"
    source_root.mkdir()
    specimens = tmp_path / "tests" / "fixtures" / "justificantes" / "130"
    specimens.mkdir(parents=True)
    (specimens / "2025-0A.pdf").write_bytes(b"%PDF-1.4 specimen")

    validator = RegistryValidator(_catalogues(), source_root=source_root)

    assert validator.justificante_corpus_root is None, (
        "the validator resolved a corpus root it was never given — a derivation "
        "has been reintroduced, and with it a repo-shaped filesystem probe"
    )


def test_a_supplied_corpus_root_is_honoured_verbatim(tmp_path: Path) -> None:
    """The supplied path is the one used, with no re-derivation."""
    corpus = tmp_path / "specimens"
    corpus.mkdir()

    validator = RegistryValidator(
        _catalogues(),
        source_root=tmp_path / "_data",
        justificante_corpus_root=corpus,
    )

    assert validator.justificante_corpus_root == corpus


def test_the_live_production_path_resolves_no_corpus_root() -> None:
    """The real bundled-data construction yields no corpus root.

    Exercises the production call shape rather than a synthetic one: this is
    what every installed run performs, and it must reach the gate-disabled
    state without consulting the filesystem for a repository.
    """
    validator = RegistryValidator(_catalogues(), source_root=bundled_path())

    assert validator.justificante_corpus_root is None
