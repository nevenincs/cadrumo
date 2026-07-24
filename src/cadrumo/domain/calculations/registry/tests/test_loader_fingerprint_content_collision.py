"""Same-size, same-mtime content edits must invalidate the loader caches.

The loader keys its in-memory caches on per-file fingerprints. A stat-only
``(path, size, mtime_ns)`` fingerprint cannot distinguish two successive
writes that produce content of the SAME byte length within the filesystem's
effective mtime resolution -- exactly what a CI overlay/network filesystem
delivers under parallel load -- so the cache would silently serve the stale
compiled registry (the ``aeat-registry-authority-flow`` rule requires the
cache above the loader to invalidate on the complete registry tree
fingerprint). These tests force the real collision condition on a real
mutable tree: rewrite a file with different content of identical byte
length, pin ``st_mtime_ns`` back to the pre-edit value with ``os.utime``,
and require the loader to return the NEW content.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from .._loader import load_modelo_directory, load_modelo_file
from ._loader_directory_mode_support import write_fragmented_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MANIFEST_TEXT = """
[modelo]
id = "130"
title = "Modelo 130"
official_name = "MODELO 130"
tax_domain = "irpf"
cadence = "quarterly"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-35-2006:art-1"]
source_refs = ["aeat-source"]
"""

_REVISION_TEXT = """
[revisions.2019-y-siguientes]
valid_from = 2019-01-01
period_selector = { year_from = 2019, periods = ["1T", "2T", "3T", "4T"] }
legal_refs = ["ley-35-2006:art-1"]
source_refs = ["aeat-source"]

[[revisions.2019-y-siguientes.casillas]]
id = "01"
number = "01"
label = "{label}"
section = ["section"]
input_kind = "manual"
continuidad_id = "cont_01"
legal_refs = ["ley-35-2006:art-1"]
source_refs = ["aeat-source"]
"""


def _rewrite_pinning_stat(path: Path, new_text: str) -> None:
    """Rewrite ``path`` with ``new_text``, forcing the stat-visible collision.

    Asserts the new content has the same byte length as the old, then pins
    ``st_atime_ns``/``st_mtime_ns`` back to their pre-edit values so a
    stat-only fingerprint observes an unchanged file.
    """
    before = path.stat()
    path.write_text(new_text, encoding="utf-8")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = path.stat()
    assert after.st_size == before.st_size, "collision precondition: byte length must be unchanged"
    assert after.st_mtime_ns == before.st_mtime_ns, "collision precondition: mtime_ns must be unchanged"


def test_single_file_modelo_same_size_same_mtime_edit_invalidates(tmp_path: Path) -> None:
    """A colliding rewrite of a single-file modelo must serve the NEW label."""
    modelo_path = tmp_path / "130.toml"
    label_a = "Alpha Label 01"
    label_b = "Bravo Label 01"
    assert len(label_a) == len(label_b)
    modelo_path.write_text(_MANIFEST_TEXT + _REVISION_TEXT.replace("{label}", label_a), encoding="utf-8")

    loaded_a = load_modelo_file(modelo_path)
    casilla_a = next(c for c in loaded_a.revisions["2019-y-siguientes"].casillas if c.id == "01")
    assert casilla_a.label == label_a

    _rewrite_pinning_stat(modelo_path, _MANIFEST_TEXT + _REVISION_TEXT.replace("{label}", label_b))

    loaded_b = load_modelo_file(modelo_path)
    casilla_b = next(c for c in loaded_b.revisions["2019-y-siguientes"].casillas if c.id == "01")
    assert casilla_b.label == label_b, (
        "the loader served stale content after a same-size/same-mtime edit: "
        "the fingerprint must discriminate on file content, not stat alone"
    )


def test_directory_modelo_locale_same_size_same_mtime_edit_invalidates(tmp_path: Path) -> None:
    """The directory-mode fingerprint aggregation must carry content sensitivity.

    Replicates the real flake shape: two schema-local locale bodies of
    identical byte length (``test_locales_file_updates_invalidate_cache``'s
    two labels are coincidentally the same length), with the mtime pinned to
    force the stat collision the CI filesystem produces on its own.
    """
    (tmp_path / "manifest.toml").write_text(_MANIFEST_TEXT, encoding="utf-8")
    rev_dir = tmp_path / "revisions" / "2019-y-siguientes"
    rev_dir.mkdir(parents=True)
    write_fragmented_revision(rev_dir, _REVISION_TEXT.replace("{label}", "Spanish Label 01"))
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    locale_path = locales_dir / "en.toml"
    label_a = "English Concept Label 01"
    label_b = "Updated English Label 01"
    assert len(label_a) == len(label_b)
    locale_template = '\n[labels]\n"cont_01" = "{label}"\n'
    locale_path.write_text(locale_template.replace("{label}", label_a), encoding="utf-8")

    loaded_a = load_modelo_directory(tmp_path)
    casilla_a = next(c for c in loaded_a.revisions["2019-y-siguientes"].casillas if c.id == "01")
    assert casilla_a.get_label("en") == label_a

    _rewrite_pinning_stat(locale_path, locale_template.replace("{label}", label_b))

    loaded_b = load_modelo_directory(tmp_path)
    casilla_b = next(c for c in loaded_b.revisions["2019-y-siguientes"].casillas if c.id == "01")
    assert casilla_b.get_label("en") == label_b, (
        "the directory-mode loader served a stale locale overlay after a "
        "same-size/same-mtime edit: the aggregated fingerprint must include a "
        "content discriminator for every TOML in the modelo directory"
    )
