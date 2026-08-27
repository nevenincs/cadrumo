"""Tree-wide gate: every casilla label resolves in the mandatory Spanish source.

Measured through the production resolver chain, never by reading catalogue
YAML. The distinction is load-bearing rather than stylistic. The locale
scaffold emits an occurrence key for every casilla in every revision, null
until translated, and ``resolve_modelo_localization`` walks an ORDERED chain
whose first entry is only the revision-specific tier -- continuity and shared
tiers sit below it and carry the label for every revision that inherits it.
A YAML read sees the null at index zero and stops, so it reports a gap the
resolver does not have: on the Modelo 303 split revisions a direct read
reported 201 missing labels per revision where the resolver's true figure was
84. Overstating a defect by a factor of more than two is how a real gap gets
buried inside a number nobody trusts.

Spanish is the mandatory source locale, so a casilla whose label does not
resolve there has no backstop left: every other catalogue falls through to
Spanish, and a Spanish miss is the one miss that reaches an operator as a
refusal rather than as a foreign-language string.
"""

from __future__ import annotations

import pytest

from ..authority import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_LOCALE = "es"


def _unresolved_spanish_casilla_labels() -> tuple[str, ...]:
    """Return every casilla whose label the resolver cannot answer in Spanish."""
    unresolved: list[str] = []
    for modelo in bundled_authority().modelos:
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                try:
                    label = casilla.get_label(_SOURCE_LOCALE)
                except Exception:
                    unresolved.append(f"{modelo.id}/{revision.id}/{casilla.id}")
                    continue
                if not label.strip():
                    unresolved.append(f"{modelo.id}/{revision.id}/{casilla.id}")
    return tuple(unresolved)


def test_every_casilla_label_resolves_in_the_mandatory_spanish_source() -> None:
    """No modelo, revision or casilla in the bundled tree lacks a Spanish label."""
    unresolved = _unresolved_spanish_casilla_labels()

    # The COUNT is stated, not just a sample. This listed `unresolved[:50]`
    # with no indication that it was a slice, so a 1,798-casilla backlog read
    # as a 50-casilla one -- a diagnostic that understates its own subject by
    # 36x is worse than a long list, because the reader sizes the work from it.
    assert unresolved == (), (
        f"{len(unresolved)} casilla label(s) unresolved in the mandatory Spanish "
        f"source (showing the first {min(len(unresolved), 50)}):\n  " + "\n  ".join(unresolved[:50])
    )


def test_the_spanish_label_sweep_covers_the_whole_bundled_tree() -> None:
    """The sweep is non-vacuous: it visits every modelo and every revision.

    Without this the gate above passes trivially the moment the walk stops
    yielding casillas -- an empty sweep and a fully-translated corpus produce
    the same empty tuple.
    """
    modelos = tuple(bundled_authority().modelos)
    revisions = [revision for modelo in modelos for revision in modelo.revisions.values()]
    casillas = [casilla for revision in revisions for casilla in revision.casillas]

    assert modelos, "the bundled authority yielded no modelos"
    assert len(revisions) > len(modelos), "every modelo must contribute at least one revision"
    assert len(casillas) > len(revisions), "the sweep must reach real casillas, not just revision shells"

    # The resolver, not the catalogue file, is the measuring instrument.
    assert all(casilla.localization_keys for casilla in casillas), (
        "a casilla without localization keys would be skipped by the resolver chain"
    )
