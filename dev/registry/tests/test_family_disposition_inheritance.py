"""Family dispositions follow the predecessor link like every other inherited family.

An edition that omits its predecessor's disposition for a family keeps it, with
the stating edition recorded, because a missing declaration is not a missing
rule. Only an authored replacement or an explicit removal changes the inherited
answer. An authored disposition that states the claim it would inherit is a restatement
and is refused. Every test drives the real directory loader over an on-disk TOML
tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.schema_family_disposition import RegistrySchemaFamilyDisposition
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.loader import load_modelo_directory
from ..compiler.schema_family_coverage import build_revision_coverage_manifest
from ..conformance.loader_directory_mode_support import write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_THIRD_YEAR = filing_year_envelope().horizon
_FIRST, _SECOND, _THIRD = str(_THIRD_YEAR - 2), str(_THIRD_YEAR - 1), str(_THIRD_YEAR)

_MODELO_ID: Final = "999"
_ARTICLE: Final = "ley-58-2003:art-29"
_ORDEN: Final = "orden-hac-200-2024:art-1"
_SOURCE: Final = "aeat-manual"
_FAMILY: Final = "live_cross_references"
_REMOVE_FAMILY: Final = f'family_disposition_removals = ["{_FAMILY}"]\n'

_PORTAL_LINK: Final = (
    'id = "enlace-portal"\n'
    'surface = "portal"\n'
    'consumer = "cadrumo.domain.portals.Portal.PORTAL_M303_IVA_AUTOLIQUIDACION"\n'
    "requires_snapshot = true\n"
    f'legal_refs = ["{_ARTICLE}"]\n'
    f'source_refs = ["{_SOURCE}"]\n'
)

_CROSS_REFERENCE: Final = (
    'id = "referencia-documentacion"\n'
    'evidence_tier = "official_source_guidance"\n'
    'surface = "static_official_documentation"\n'
    'guard_policy_id = "politica-documentacion-estatica"\n'
    "forbidden_actions = [\n"
    '    "server-side-save",\n'
    '    "signing",\n'
    '    "presentation",\n'
    '    "payment",\n'
    '    "amendment",\n'
    '    "cancellation",\n'
    '    "document-submission",\n'
    '    "declaration-submission",\n'
    "]\n"
    "synthetic_data_allowed = false\n"
    "requires_authentication = false\n"
    "requires_aeat_authorization = false\n"
    f'legal_refs = ["{_ARTICLE}"]\n'
    f'source_refs = ["{_SOURCE}"]\n'
)


def _casilla(casilla_id: str) -> str:
    return (
        f'id = "{casilla_id}"\n'
        f'number = "{casilla_id}"\n'
        'section = ["liquidacion"]\n'
        f'continuidad_id = "linaje-{casilla_id}"\n'
    )


def _write_section(revision_dir: Path, revision_id: str, section: str, rows: tuple[str, ...]) -> None:
    directory = revision_dir / section
    directory.mkdir()
    (directory / f"0001-{section.replace('_', '-')}.toml").write_text(
        "".join(f'[[revisions."{revision_id}".{section}]]\n{row}\n' for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _write_edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    cross_references: tuple[str, ...] = (),
    extra: str = "",
) -> None:
    year = int(revision_id)
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        f'source_refs = ["{_SOURCE}"]\n'
        f'orden_aplicabilidad = ["{_ORDEN}"]\n'
        f'casilla_source_refs = ["{_SOURCE}"]\n' + extra,
        encoding="utf-8",
        newline="\n",
    )
    _write_section(revision_dir, revision_id, "casillas", (_casilla("01"),))
    _write_section(revision_dir, revision_id, "application_links", (_PORTAL_LINK,))
    if cross_references:
        _write_section(revision_dir, revision_id, _FAMILY, cross_references)


def _disposition(revision_id: str, reason: str) -> str:
    return (
        f'[revisions."{revision_id}".family_dispositions.{_FAMILY}]\n'
        f'reason = "{reason}"\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        f'source_refs = ["{_SOURCE}"]\n'
    )


def _chain(tmp_path: Path, *editions: tuple[str, str], link: str = "predecessor") -> Path:
    """Write the editions in order; each later one links to the one before it."""
    modelo_dir = tmp_path / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    previous: str | None = None
    for revision_id, extra in editions:
        link_line = "" if previous is None else f'{link} = "{previous}"\n'
        _write_edition(modelo_dir, revision_id, extra=link_line + "\n" + extra)
        previous = revision_id
    return modelo_dir


def test_an_omitted_disposition_is_inherited_along_the_chain(tmp_path: Path) -> None:
    """The edition after the stating one, and the one after that, both keep the claim."""
    definition = load_modelo_directory(
        _chain(tmp_path, (_FIRST, _disposition(_FIRST, "Stated once.")), (_SECOND, ""), (_THIRD, "")),
    )

    stated = definition.revisions[_FIRST].family_dispositions[_FAMILY]
    assert stated.inherited_from is None
    for revision_id in (_SECOND, _THIRD):
        inherited = definition.revisions[revision_id].family_dispositions[_FAMILY]
        assert inherited.reason == "Stated once."
        assert str(inherited.inherited_from) == _FIRST


def test_a_storage_only_edge_inherits_dispositions(tmp_path: Path) -> None:
    """The family storage baseline is the link the keyed families use, so it carries the claim."""
    definition = load_modelo_directory(
        _chain(
            tmp_path,
            (_FIRST, _disposition(_FIRST, "Stated once.")),
            (_SECOND, ""),
            link="family_storage_baseline",
        ),
    )

    assert definition.revisions[_SECOND].family_dispositions[_FAMILY].reason == "Stated once."


def test_an_authored_disposition_replaces_the_inherited_one(tmp_path: Path) -> None:
    definition = load_modelo_directory(
        _chain(tmp_path, (_FIRST, _disposition(_FIRST, "Old.")), (_SECOND, _disposition(_SECOND, "New."))),
    )

    replaced = definition.revisions[_SECOND].family_dispositions[_FAMILY]
    assert replaced.reason == "New."
    assert replaced.inherited_from is None


def test_a_removal_deletes_the_inherited_disposition_for_the_chain_after_it(tmp_path: Path) -> None:
    definition = load_modelo_directory(
        _chain(tmp_path, (_FIRST, _disposition(_FIRST, "Stated once.")), (_SECOND, _REMOVE_FAMILY), (_THIRD, "")),
    )

    assert definition.revisions[_SECOND].family_dispositions == {}
    assert definition.revisions[_THIRD].family_dispositions == {}
    assert definition.revisions[_SECOND].family_disposition_removals == (_FAMILY,)


def _populating_successor(tmp_path: Path, *, removal: bool) -> Path:
    modelo_dir = _chain(tmp_path, (_FIRST, _disposition(_FIRST, "Stated once.")))
    _write_edition(
        modelo_dir,
        _SECOND,
        cross_references=(_CROSS_REFERENCE,),
        extra=f'predecessor = "{_FIRST}"\n' + (_REMOVE_FAMILY if removal else ""),
    )
    return modelo_dir


def test_populating_an_inherited_not_applicable_family_needs_the_removal(tmp_path: Path) -> None:
    """Silence never deletes: content over an inherited claim is a contradiction, not a deletion."""
    with pytest.raises(RegistryLoadError, match="family_disposition_removals"):
        load_modelo_directory(_populating_successor(tmp_path / "refused", removal=False))

    definition = load_modelo_directory(_populating_successor(tmp_path / "accepted", removal=True))

    assert definition.revisions[_SECOND].family_dispositions == {}
    assert len(definition.revisions[_SECOND].live_cross_references) == 1


def test_removing_a_disposition_nothing_inherits_is_refused(tmp_path: Path) -> None:
    modelo_dir = _chain(tmp_path, (_FIRST, ""), (_SECOND, _REMOVE_FAMILY))

    with pytest.raises(RegistryLoadError, match="removed but not inherited"):
        load_modelo_directory(modelo_dir)


def test_removing_a_family_no_edition_could_have_inherited_is_refused(tmp_path: Path) -> None:
    modelo_dir = _chain(
        tmp_path,
        (_FIRST, _disposition(_FIRST, "Stated once.")),
        (_SECOND, 'family_disposition_removals = ["not_a_family"]\n'),
    )

    with pytest.raises(RegistryLoadError, match="removed but not inherited"):
        load_modelo_directory(modelo_dir)


def test_a_removal_in_a_modelo_without_any_predecessor_is_refused(tmp_path: Path) -> None:
    modelo_dir = _chain(tmp_path, (_FIRST, _REMOVE_FAMILY))

    with pytest.raises(RegistryLoadError, match="inherits none"):
        load_modelo_directory(modelo_dir)


def test_a_family_both_removed_and_authored_is_refused(tmp_path: Path) -> None:
    modelo_dir = _chain(
        tmp_path,
        (_FIRST, _disposition(_FIRST, "Stated once.")),
        (_SECOND, _REMOVE_FAMILY + "\n" + _disposition(_SECOND, "Again.")),
    )

    with pytest.raises(RegistryLoadError, match="both removed and authored"):
        load_modelo_directory(modelo_dir)


@pytest.mark.parametrize("with_successor", [True, False], ids=["delta-modelo", "modelo-inheriting-nothing"])
def test_an_authored_inherited_from_is_refused(tmp_path: Path, *, with_successor: bool) -> None:
    """The marker is the loader's; a modelo that inherits nothing refuses it the same way."""
    authored = _disposition(_FIRST, "Stated once.") + f'inherited_from = "{int(_FIRST) - 1}"\n'
    editions = ((_FIRST, authored), (_SECOND, "")) if with_successor else ((_FIRST, authored),)

    with pytest.raises(RegistryLoadError, match="authors inherited_from"):
        load_modelo_directory(_chain(tmp_path, *editions))


def test_inheriting_a_claim_adds_no_serialised_trace_and_no_stronger_coverage(tmp_path: Path) -> None:
    """Where a claim is stated is not part of its meaning, and inheriting it grants nothing more."""
    definition = load_modelo_directory(
        _chain(tmp_path, (_FIRST, _disposition(_FIRST, "Stated once.")), (_SECOND, "")),
    )

    stated = definition.revisions[_FIRST].family_dispositions[_FAMILY]
    inherited = definition.revisions[_SECOND].family_dispositions[_FAMILY]
    assert inherited.model_dump(mode="json") == stated.model_dump(mode="json")
    assert "inherited_from" not in inherited.model_dump(mode="json")
    rows = {
        row.family: row
        for row in build_revision_coverage_manifest(modelo=_MODELO_ID, revision=definition.revisions[_SECOND]).rows
    }
    assert rows[_FAMILY].disposition is RegistrySchemaFamilyDisposition.NOT_APPLICABLE
    assert rows[_FAMILY].reason == "Stated once."


def test_an_authored_disposition_equal_to_the_inherited_one_is_refused(tmp_path: Path) -> None:
    """Restating the inherited claim adds nothing an omission does not already say."""
    modelo_dir = _chain(
        tmp_path,
        (_FIRST, _disposition(_FIRST, "Stated once.")),
        (_SECOND, _disposition(_SECOND, "Stated once.")),
    )

    with pytest.raises(RegistryLoadError) as refusal:
        load_modelo_directory(modelo_dir)

    message = str(refusal.value)
    assert f"modelo {_MODELO_ID!r}" in message
    assert f"revision '{_SECOND}' inheriting from '{_FIRST}'" in message
    assert f"family disposition {_FAMILY!r} restates" in message
    assert f"stated by edition '{_FIRST}'" in message


def test_a_restatement_is_refused_against_the_edition_that_first_stated_the_claim(tmp_path: Path) -> None:
    """Restating over a claim two editions back names the stating edition, not the adjacent one."""
    modelo_dir = _chain(
        tmp_path,
        (_FIRST, _disposition(_FIRST, "Stated once.")),
        (_SECOND, ""),
        (_THIRD, _disposition(_THIRD, "Stated once.")),
    )

    with pytest.raises(RegistryLoadError, match=rf"inheriting from '{_SECOND}'.*stated by edition '{_FIRST}'"):
        load_modelo_directory(modelo_dir)


def test_a_restatement_over_a_storage_only_edge_is_refused(tmp_path: Path) -> None:
    """The family storage baseline carries dispositions, so it cannot be restated either."""
    modelo_dir = _chain(
        tmp_path,
        (_FIRST, _disposition(_FIRST, "Stated once.")),
        (_SECOND, _disposition(_SECOND, "Stated once.")),
        link="family_storage_baseline",
    )

    with pytest.raises(RegistryLoadError, match="restates, unchanged"):
        load_modelo_directory(modelo_dir)


_OTHER_ORDEN: Final = "orden-hac-200-2024:art-2"


@pytest.mark.parametrize(
    ("reason", "legal_refs", "source_refs"),
    [
        ("Changed.", (_ARTICLE,), (_SOURCE,)),
        ("Stated once.", (_ARTICLE, _OTHER_ORDEN), (_SOURCE,)),
        ("Stated once.", (_ARTICLE,), (_SOURCE, "aeat-instructions")),
    ],
    ids=["reason", "legal-refs", "source-refs"],
)
def test_a_changed_claim_is_accepted_as_an_override(
    tmp_path: Path,
    reason: str,
    legal_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
) -> None:
    """A difference in provenance is a difference: the references are part of the claim."""
    legal = ", ".join(f'"{ref}"' for ref in legal_refs)
    sources = ", ".join(f'"{ref}"' for ref in source_refs)
    revised = "\n".join(
        (
            f'[revisions."{_SECOND}".family_dispositions.{_FAMILY}]',
            f'reason = "{reason}"',
            f"legal_refs = [{legal}]",
            f"source_refs = [{sources}]",
            "",
        )
    )
    definition = load_modelo_directory(
        _chain(tmp_path, (_FIRST, _disposition(_FIRST, "Stated once.")), (_SECOND, revised)),
    )

    held = definition.revisions[_SECOND].family_dispositions[_FAMILY]
    assert held.inherited_from is None
    assert held != definition.revisions[_FIRST].family_dispositions[_FAMILY]


def test_a_restatement_in_an_edition_with_no_inherited_claim_is_a_first_statement(tmp_path: Path) -> None:
    """With nothing inherited for the family, the entry is new and is not a restatement."""
    definition = load_modelo_directory(
        _chain(tmp_path, (_FIRST, ""), (_SECOND, _disposition(_SECOND, "Stated once."))),
    )

    assert definition.revisions[_SECOND].family_dispositions[_FAMILY].inherited_from is None


def test_removing_and_restating_the_same_claim_stays_refused_as_removed_and_authored(tmp_path: Path) -> None:
    """The removal-plus-re-author path keeps its existing refusal; the restatement refusal does not replace it."""
    modelo_dir = _chain(
        tmp_path,
        (_FIRST, _disposition(_FIRST, "Stated once.")),
        (_SECOND, _REMOVE_FAMILY + "\n" + _disposition(_SECOND, "Stated once.")),
    )

    with pytest.raises(RegistryLoadError, match="both removed and authored"):
        load_modelo_directory(modelo_dir)


def test_restating_after_a_removal_one_edition_later_is_a_new_claim(tmp_path: Path) -> None:
    """Once an edition removes the claim, a later edition stating it again inherits nothing to duplicate."""
    definition = load_modelo_directory(
        _chain(
            tmp_path,
            (_FIRST, _disposition(_FIRST, "Stated once.")),
            (_SECOND, _REMOVE_FAMILY),
            (_THIRD, _disposition(_THIRD, "Stated once.")),
        ),
    )

    assert definition.revisions[_SECOND].family_dispositions == {}
    assert definition.revisions[_THIRD].family_dispositions[_FAMILY].inherited_from is None
