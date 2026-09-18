"""Closure pairs and inapplicability claims across one predecessor edge.

A closure rule couples a declaration family to the application surface that
consumes it, and it is evaluated against one already-materialised revision.
That is the right question for a full-copy edition and an incomplete one for a
delta edition: the two sides of a pair reach the successor under separate
enrolments, so an edition can keep the surface and lose the family without any
per-revision rule firing. The same edge hides the neighbouring case, where an
edition claims a family is legally inapplicable while its predecessor declares
members of it.

Every test drives the real directory loader over an on-disk TOML tree and the
real validator function over the definition it produces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_inherited_family_pairing import inherited_family_pairing_failures
from ..conformance.loader_directory_mode_support import write_standard_manifest as _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID: Final = "999"
_ARTICLE: Final = "ley-58-2003:art-29"
_ORDEN: Final = "orden-hac-200-2024:art-1"
_SOURCE: Final = "aeat-manual"
_CROSS_REFERENCE_ID: Final = "referencia-documentacion"

_PORTAL_LINK: Final = (
    'id = "enlace-portal"\n'
    'surface = "portal"\n'
    'consumer = "cadrumo.domain.portals.Portal.PORTAL_M303_IVA_AUTOLIQUIDACION"\n'
    "requires_snapshot = true\n"
    f'legal_refs = ["{_ARTICLE}"]\n'
    f'source_refs = ["{_SOURCE}"]\n'
)

_CROSS_REFERENCE: Final = (
    f'id = "{_CROSS_REFERENCE_ID}"\n'
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

_DISPOSITION: Final = (
    '[revisions."2025".family_dispositions.live_cross_references]\n'
    'reason = "The edition claims the law requires no live cross-reference of any kind."\n'
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
    year: int,
    cross_references: tuple[str, ...] = (),
    extra: str = "",
) -> None:
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
        _write_section(revision_dir, revision_id, "live_cross_references", cross_references)


def _modelo(tmp_path: Path, *, successor_extra: str) -> Path:
    modelo_dir = tmp_path / _MODELO_ID
    modelo_dir.mkdir()
    _write_standard_manifest(modelo_dir, "Test")
    _write_edition(modelo_dir, "2024", year=2024, cross_references=(_CROSS_REFERENCE,))
    _write_edition(modelo_dir, "2025", year=2025, extra='predecessor = "2024"\n' + successor_extra)
    return modelo_dir


def test_an_intact_pair_crosses_the_edge_without_a_finding(tmp_path: Path) -> None:
    """The successor states nothing, inherits both sides, and is reported clean.

    This is the ordinary delta edition, and it is the tooth of every refusal
    below: each of those withdraws exactly one side of this pair.
    """
    definition = load_modelo_directory(_modelo(tmp_path, successor_extra=""))

    successor = definition.revisions["2025"]
    assert [str(reference.id) for reference in successor.live_cross_references] == [_CROSS_REFERENCE_ID]
    assert {link.surface for link in successor.application_links} == {"portal"}
    assert inherited_family_pairing_failures(definition) == ()


def test_a_cleared_family_under_a_surviving_surface_is_refused(tmp_path: Path) -> None:
    """Clearing one side of a pair leaves the edition claiming a capability nothing backs.

    ``cleared_families`` withdraws the family; the ``portal`` link arrives by
    inheritance untouched, because the two families are enrolled separately and
    neither mechanism consults the other. The per-revision closure rule stays
    quiet: it fires on a family without its surface, never on a surface without
    its family.
    """
    definition = load_modelo_directory(
        _modelo(tmp_path, successor_extra='cleared_families = ["live_cross_references"]\n'),
    )

    successor = definition.revisions["2025"]
    assert successor.live_cross_references == ()
    assert {link.surface for link in successor.application_links} == {"portal"}
    (failure,) = inherited_family_pairing_failures(definition)
    assert "live_cross_references" in failure
    assert "'portal'" in failure


def test_an_inapplicability_claim_its_predecessor_contradicts_is_refused(tmp_path: Path) -> None:
    """A disposition says the law requires none of the family; the edition before it declares one.

    The revision's own validator refuses a disposition over content the SAME
    edition declares, which leaves this case: the content was the
    predecessor's, the successor's merge dropped it, and the claim then reads
    as law while the edition before it asserts the opposite. Which edition is
    wrong is a grounded authoring decision, not something a merge may settle
    by arithmetic.
    """
    definition = load_modelo_directory(
        _modelo(
            tmp_path,
            successor_extra='cleared_families = ["live_cross_references"]\n\n' + _DISPOSITION,
        ),
    )

    assert set(definition.revisions["2025"].family_dispositions) == {"live_cross_references"}
    failures = inherited_family_pairing_failures(definition)
    assert any("not applicable" in failure for failure in failures)


def test_a_disposition_over_a_family_no_predecessor_declares_stands(tmp_path: Path) -> None:
    """The tooth of the refusal above: nothing contradicts a claim about an empty family.

    Both editions declare no ``live_cross_references``, so the successor's
    disposition is the only statement about the family on the chain and is
    reported clean. Without this, "a disposition is refused" would be
    satisfiable by refusing every disposition.
    """
    modelo_dir = tmp_path / _MODELO_ID
    modelo_dir.mkdir()
    _write_standard_manifest(modelo_dir, "Test")
    _write_edition(modelo_dir, "2024", year=2024)
    _write_edition(modelo_dir, "2025", year=2025, extra='predecessor = "2024"\n\n' + _DISPOSITION)

    definition = load_modelo_directory(modelo_dir)

    assert set(definition.revisions["2025"].family_dispositions) == {"live_cross_references"}
    assert inherited_family_pairing_failures(definition) == ()


def test_a_scoped_family_the_edition_states_itself_needs_no_assertion(tmp_path: Path) -> None:
    """The bound on the loader's scoped-silence refusal: an omitted assertion over stated content decides nothing.

    The loader refuses an edition that leaves a scoped family undecided, which
    is what keeps the scoped route from emptying one side of a pair in silence.
    The refusal stops there: an edition that states the family in full is
    authoring it as a full copy, which is what the scope is for, and the
    predecessor's members are simply not its. Without this bound the refusal
    would also reject ordinary full-copy authoring, which ten live modelos use.
    """
    modelo_dir = tmp_path / _MODELO_ID
    modelo_dir.mkdir()
    _write_standard_manifest(modelo_dir, "Test")
    for revision_id, year in (("2024", 2024), ("2025", 2025)):
        _write_edition(
            modelo_dir,
            revision_id,
            year=year,
            extra='predecessor = "2024"\n' if revision_id == "2025" else "",
        )
        _write_section(
            modelo_dir / "revisions" / revision_id,
            revision_id,
            "workbook_parity_refs",
            (
                f'id = "referencia-libro-{revision_id}"\n'
                f'workbook_source = "{_SOURCE}"\n'
                f'fixture_id = "modelo-999-{revision_id}-layout"\n'
                'formula_coverage = "record_design_layout"\n'
                "runner_required = false\n"
                f'legal_refs = ["{_ARTICLE}"]\n'
                f'source_refs = ["{_SOURCE}"]\n',
            ),
        )

    successor = load_modelo_directory(modelo_dir).revisions["2025"]

    assert [str(reference.id) for reference in successor.workbook_parity_refs] == ["referencia-libro-2025"]
