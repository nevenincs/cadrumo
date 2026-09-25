"""Every revision's own citations sit inside their windows, checked at registry build.

The runtime already refuses a revision citing a legal reference that was not in
force on its devengo date, or a source whose applicability window does not reach
it. Both checks run inside ``build_registry_snapshot``, which means they are
reached once per ``(modelo, filing year, period)`` somebody actually snapshots.
Authoring reaches no such coordinate: a revision can be compiled, validated and
published carrying a stale citation, and the defect surfaces later wherever an
adapter or entrypoint test happens to build that snapshot -- far from the
authoring change, and only for the coordinates those tests cover.

That gap is not hypothetical. Two 2022/2023 revisions of modelos 190 and 193
were authored citing a record design whose window had closed, and a legal
article that took effect the following year. ``vault check``, the candidate
inspection and the registry gates all passed; the defect appeared as several
dozen failures across ``adapters``, ``application`` and ``entrypoints``.

So the sweep runs here, over every revision the compiler produces, using the
runtime's own two checks rather than a second reading of the same rule. A
revision no snapshot test covers is checked exactly like one that is.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistryCatalogues

# The canonical definitions of both window rules. They are private to the
# snapshot module because runtime reaches them only through snapshot build; this
# gate needs the same rule applied to revisions no snapshot coordinate reaches,
# and reading it a second time here is what would let the two disagree.
from cadrumo.domain.calculations.registry.snapshot import (
    check_revision_scoped_legal_windows,
    check_revision_scoped_source_windows,
)

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _window_failures(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    catalogues: RegistryCatalogues,
) -> list[str]:
    """Return both window checks' refusals for one revision, or an empty list."""
    failures: list[str] = []
    for check in (check_revision_scoped_legal_windows, check_revision_scoped_source_windows):
        try:
            check(modelo, revision, catalogues)
        except RegistryValidationError as refusal:
            failures.append(str(refusal))
    return failures


@pytest.fixture(scope="module")
def authority():
    return compiled_bundled_authority()


def test_no_revision_cites_authority_outside_its_own_window(authority) -> None:
    """Sweep every compiled revision, not only the ones a snapshot test reaches."""
    reported: list[str] = []
    for modelo in sorted(authority.modelos, key=lambda item: str(item.id)):
        for revision_id, revision in sorted(modelo.revisions.items()):
            for failure in _window_failures(modelo, revision, authority.catalogues):
                reported.append(f"{modelo.id}/{revision_id}: {failure}")

    assert not reported, (
        "revision(s) cite authority outside its window. Each would be refused at snapshot build, so the "
        "revision cannot be filed for the years it claims:\n" + "\n".join(reported)
    )


def test_a_source_whose_window_closed_before_the_revision_is_reported(authority) -> None:
    """MUTATION: the exact defect the sweep exists to catch, on a constructed revision.

    The stale citation is introduced on a copy, so the shipped tree is untouched
    and the proof and the normal path pass in the same run.
    """
    modelo = next(item for item in authority.modelos if str(item.id) == "190")
    revision = modelo.revisions["2025-y-siguientes"]
    assert _window_failures(modelo, revision, authority.catalogues) == []

    stale = revision.model_copy(update={"source_refs": (*revision.source_refs, "aeat-dr-190-2020")})
    reported = _window_failures(modelo, stale, authority.catalogues)

    assert reported, "a source whose applicability closed before the revision opened was not reported"
    assert "aeat-dr-190-2020" in reported[0]


def test_a_legal_reference_effective_after_the_revision_is_reported(authority) -> None:
    """MUTATION: the legal-window half, which fails on a different date axis."""
    modelo = next(item for item in authority.modelos if str(item.id) == "190")
    revision = modelo.revisions["2022"]
    assert _window_failures(modelo, revision, authority.catalogues) == []

    stale = revision.model_copy(update={"legal_refs": (*revision.legal_refs, "ley-35-2006:art-32")})
    reported = _window_failures(modelo, stale, authority.catalogues)

    assert reported, "a legal reference effective after the revision's devengo date was not reported"
    assert "ley-35-2006:art-32" in reported[0]
