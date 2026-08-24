"""Every fully-qualified ``cadrumo.*`` docstring reference must resolve.

This campaign has now been misled by prose three times, each in a different
way, and each time the prose named something:

- ``safe_repository_id`` described a two-layer path contract whose second layer
  had been deleted with the module that needed it;
- two docstrings cited a CLI-side lazy-import gate that nobody had written
  back, each pointing at the other as corroboration;
- ``_section_rows`` named ``ProfileCapsuleLifecycle.edit_fields`` as the write
  door judging a whole fact batch -- a method that does not exist, on a class
  that owns no field-editing method at all.

The shipped firmware already applies this discipline to its own prose: a name
in an always-on mandate must resolve to a real artifact, because a dangling
name degrades every session that reads it. The same argument holds here. A
docstring is the first thing a reader consults about a boundary, and one that
names a function, class or module confidently is trusted more than an absence
would be -- so a stale name is worse than no name.

**Scope is deliberate.** Only FULLY-QUALIFIED ``cadrumo.*`` targets are
checked, and only in the packages this campaign answers for. A bare
``:class:`BucketPaths``` is ambiguous by design -- the docs build's
missing-reference resolver is what turns it into a link, and guessing at its
answer here would fight that decision. A dotted ``cadrumo.`` path is not
ambiguous: it names exactly one thing, so it either resolves or it is wrong.

**Resolution is by import, not by name matching.** An earlier version of this
scan compared leaf names against every symbol defined anywhere in the tree; it
produced both false positives (stdlib and third-party names) and, worse, false
NEGATIVES -- three real dangling references survived it because their leaf name
existed somewhere else entirely. Importing the longest importable prefix and
walking the remainder with ``getattr`` is what makes the answer exact, and it
is also the only method that respects the PEP 562 lazy facades this package
tree uses: a name reached through ``__getattr__`` is absent from the module's
source but present on the module object.
"""

from __future__ import annotations

import importlib
import re

import pytest

from ._inventory import SRC_CADRUMO, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The packages this campaign answers for.
_SCOPED_PACKAGES = (
    "adapters/persistence/storage",
    "application/user_profile",
    "entrypoints/cli/_config",
)

#: A Sphinx role naming a fully-qualified project target.
_QUALIFIED_ROLE = re.compile(r":(?:func|class|meth|data|attr|exc|mod):`~?(cadrumo\.[\w.]+)`")


def _resolves(target: str) -> bool:
    """Report whether ``target`` names something that exists.

    Walks back from the longest dotted prefix because the split between module
    path and attribute path is not knowable from the string alone:
    ``cadrumo.core.Modelo.M303`` is a module, a class and a member.
    """
    parts = target.split(".")
    for cut in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:cut]))
        except ImportError:
            # A shorter prefix of a dotted reference is not always an importable
            # module -- resolving ``pkg.mod.Class.attr`` walks prefixes until one
            # imports. A prefix that does not is the normal case, not an error to
            # report, so the walk continues to the next-shorter candidate.
            continue
        for attr in parts[cut:]:
            resolved = _member(obj, attr)
            if resolved is None:
                return False
            obj = resolved
        return True
    return False


def _member(owner: object, attr: str) -> object | None:
    """Return ``owner.attr``, counting declared fields as present.

    A pydantic v2 field is NOT a class attribute -- it lives in
    ``model_fields`` and ``getattr`` on the class returns nothing -- so a plain
    attribute walk calls every ``:attr:`SomeModel.some_field``` reference
    dangling. That would make this gate fail on correct docstrings, which is a
    worse outcome than the staleness it exists to catch: a gate that cries wolf
    gets its scope narrowed until it stops meaning anything.

    Declared-but-unset annotations are accepted for the same reason.
    """
    found = getattr(owner, attr, None)
    if found is not None:
        return found
    fields = getattr(owner, "model_fields", None)
    if isinstance(fields, dict) and attr in fields:
        return fields[attr]
    annotations = getattr(owner, "__annotations__", None)
    if isinstance(annotations, dict) and attr in annotations:
        return annotations[attr]
    return None


def _references() -> list[tuple[str, int, str]]:
    """Return every ``(path, line, target)`` in the scoped packages."""
    found: list[tuple[str, int, str]] = []
    for package in _SCOPED_PACKAGES:
        for path in (SRC_CADRUMO / package).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in _QUALIFIED_ROLE.finditer(text):
                line = text[: match.start()].count("\n") + 1
                found.append((repo_relative(path), line, match.group(1)))
    return found


def test_no_qualified_reference_names_something_that_does_not_exist() -> None:
    """DISCRIMINATING: a confident name is trusted more than an absence would be."""
    dangling = [f"{path}:{line}: {target}" for path, line, target in _references() if not _resolves(target)]

    assert not dangling, (
        "these docstrings name a fully-qualified target that does not resolve:\n  "
        + "\n  ".join(sorted(dangling))
        + "\n\nEither the artifact moved -- point the reference at where it lives now -- or it "
        "was deleted, in which case say so rather than leaving its name standing. If the "
        "symbol SHOULD be reachable at the cited path, export it there; that is the fix the "
        "citation was already assuming."
    )


def test_the_scan_reaches_a_real_population() -> None:
    """ANTI-VACUITY: an empty reference list would clear every package for free.

    The gate's whole content is that the list resolves. A regex that matched
    nothing -- a role spelling change, a package move -- would report a clean
    tree forever.
    """
    references = _references()

    assert len(references) > 100, f"expected the scoped packages to carry many references, got {len(references)}"
    assert len({path for path, _, _ in references}) > 20


def test_the_resolver_reports_a_missing_target() -> None:
    """ANTI-TAUTOLOGY: the resolver must be able to say no.

    A resolver that returned ``True`` unconditionally -- an over-broad
    ``except``, say -- would satisfy the assertion above against any tree.
    """
    assert _resolves("cadrumo.application.user_profile.ProfileCapsuleLifecycle.edit_fields") is False
    assert _resolves("cadrumo.domain.submission.SubmissionRepository") is False
    assert _resolves("cadrumo.this.module.does.not.exist") is False


def test_the_resolver_counts_a_pydantic_field_as_present() -> None:
    """A model field is declared, not attributed, and must not read as dangling.

    ``getattr(Invoice, "operation_date")`` is nothing in pydantic v2 -- the
    field lives in ``model_fields``. Without this the gate would report every
    correct ``:attr:`Model.field``` reference in the tree as stale, and the
    honest response to that would be to delete the gate.
    """
    assert _resolves("cadrumo.domain.invoices.Invoice.operation_date") is True
    assert _resolves("cadrumo.domain.invoices.Invoice.no_such_field_at_all") is False


def test_the_resolver_accepts_real_targets_including_lazy_ones() -> None:
    """The other direction, and the reason resolution is by import.

    ``CommittedProfileView`` is reached through the package's PEP 562
    ``__getattr__``: it is absent from the facade's own source text, so any
    scan reading source rather than importing would call it dangling and be
    wrong.
    """
    assert _resolves("cadrumo.application.user_profile.CommittedProfileView") is True
    assert _resolves("cadrumo.application.user_profile.apply_profile_fact_changes") is True
    assert _resolves("cadrumo.adapters.persistence.storage.bucket.trash_rename_and_remove") is True
    assert _resolves("cadrumo.core") is True
