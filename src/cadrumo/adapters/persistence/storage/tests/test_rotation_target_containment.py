"""A rotation plan target cannot name a file outside its declared store_dir.

``RotationPlanEntry.target_filename`` is documented as "an exact filename
inside ``store_dir``", and the enumerator concatenated it straight onto that
directory. Nothing enforced the documentation, so a plan naming
``../outside.envelope.json`` -- or an absolute path, which ``Path.__truediv__``
substitutes wholesale -- pointed the rotation WRITER at ciphertext belonging to
another owner, which it would then decrypt and rewrite under the new key.

Two layers are asserted, because neither subsumes the other: the record refuses
the token's SHAPE at construction, and the enumerator re-resolves the surviving
token against the real filesystem. The second layer is reached here through
``model_construct``, which skips validation on purpose -- a layer that only ever
runs behind a validator that already refused everything is untested by
construction.

Real behaviour throughout: real directories, real files, the real enumerator.
Nothing is mocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from .._rotation import RotationPlanEntry, _iter_envelope_files
from ..errors import PathContainmentError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_LEGIT_NAME = "usage-ratios.json"
_HKDF_CONTEXT = b"cadrumo.rotation.containment.test"


def _layout(tmp_path: Path) -> tuple[Path, Path]:
    """Build a store directory beside a sibling file it must never reach."""
    inside = tmp_path / "inside"
    inside.mkdir()
    (inside / _LEGIT_NAME).write_text("{}", encoding="utf-8")
    outside = tmp_path / "outside.envelope.json"
    outside.write_text("{}", encoding="utf-8")
    return inside, outside


def _entry(store_dir: Path, target_filename: str) -> RotationPlanEntry:
    return RotationPlanEntry(
        store_dir=store_dir,
        hkdf_context=_HKDF_CONTEXT,
        target_filename=target_filename,
    )


@pytest.mark.parametrize(
    "target_filename",
    [
        "../outside.envelope.json",
        "../../outside.envelope.json",
        "sub/../../outside.envelope.json",
        "nested/other.envelope.json",
        "..",
        ".",
        ".hidden.envelope.json",
        "",
    ],
)
def test_record_refuses_a_target_that_is_not_a_bare_filename(tmp_path: Path, target_filename: str) -> None:
    """Construction refuses every shape that is not a plain filename.

    ``../outside.envelope.json`` and the separator variants are the escapes
    that reached a sibling directory's ciphertext; ``nested/other...`` is
    refused too because the field's contract is a filename, not a sub-path.
    """
    inside, _outside = _layout(tmp_path)

    with pytest.raises(ValidationError):
        _entry(inside, target_filename)


def test_record_refuses_an_absolute_target(tmp_path: Path) -> None:
    """An absolute path is the escape ``Path.__truediv__`` performs silently.

    Called out separately from the relative cases: ``store_dir / "/etc/x"``
    does not traverse, it DISCARDS ``store_dir`` entirely, so a plan carrying
    an absolute name never touched the declared directory at all.
    """
    inside, outside = _layout(tmp_path)

    with pytest.raises(ValidationError):
        _entry(inside, outside.as_posix())


def test_a_bare_filename_still_resolves_and_is_yielded(tmp_path: Path) -> None:
    """POSITIVE CONTROL: the legitimate single-file target still rotates.

    Without this, every refusal above is equally satisfied by a validator that
    rejects everything -- which would silently stop rotating the single-file
    consumers this field exists for, leaving their ciphertext under the old
    key. ``usage-ratios.json`` is the real production target name.
    """
    inside, _outside = _layout(tmp_path)

    yielded = [path for path, _ in _iter_envelope_files((_entry(inside, _LEGIT_NAME),))]

    assert yielded == [inside.resolve() / _LEGIT_NAME]


def test_a_missing_bare_filename_yields_nothing(tmp_path: Path) -> None:
    """An absent target is skipped, not refused: rotation stays resumable."""
    inside, _outside = _layout(tmp_path)

    assert list(_iter_envelope_files((_entry(inside, "not-written-yet.json"),))) == []


def test_the_enumerator_refuses_an_escaping_target_the_record_did_not_see(tmp_path: Path) -> None:
    """The second layer holds on its own, for a plan that bypassed validation.

    DISCRIMINATING on the enumerator's own containment: ``model_construct``
    installs the traversal target without running the field validator, which is
    exactly the pre-fix state of the record. The enumerator must still refuse,
    and must refuse with the substrate's typed containment error rather than
    yielding the sibling path for the writer to rewrite.
    """
    inside, outside = _layout(tmp_path)
    unvalidated = RotationPlanEntry.model_construct(
        store_dir=inside,
        hkdf_context=_HKDF_CONTEXT,
        envelope_suffix=".envelope.json",
        target_filename=f"../{outside.name}",
    )

    with pytest.raises(PathContainmentError):
        list(_iter_envelope_files((unvalidated,)))

    # The sibling is untouched: the refusal happened before any yield, so the
    # rotation writer never received a path outside the declared store_dir.
    assert outside.read_text(encoding="utf-8") == "{}"
