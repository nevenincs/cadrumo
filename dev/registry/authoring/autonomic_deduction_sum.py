"""Write or check the Modelo 100 formula of casilla 0564 from the official dictionaries.

Casilla 0564 is the sum of the autonomic deductions of the comunidad of residence.
Each edition's declaration dictionary prints that sum once per comunidad as a
``DEDAUTx`` row; :mod:`.autonomic_deduction_sum_dictionary` reads the operands.

The formula adds one term per comunidad, in the dictionary's order:

- the comunidad of residence contributes its official sum, unless a box that sum names
  but the extraction leaves out holds an amount: then 0564 is left without a value, for
  a typed reason, and the operator states it;
- any other comunidad whose official sum is not zero leaves 0564 without a value,
  for a typed reason, because the return can carry only one comunidad's deductions;
- any other comunidad contributes zero.

The oldest authored edition declares the whole formula. A later edition carries a
delta only for the comunidades whose meaning changes from the edition before it, that
is whose set of signed operands or of left-out guards differs; a reordered list is the
same sum and is inherited. Changed terms are replaced in place, and every other term
is inherited, so each term keeps the dictionary row of the edition that declared it. Each
term cites that row as layout authority: the citation names the edition's dictionary and
quotes the whole row, and a comment gives its line. The formula computes nothing beyond
the rows it cites, which is what lets the compiler admit those citations. Each
edition's calculation-completeness manifest then lists the boxes the formula reads.

``--check`` fails when the committed declarations differ from a fresh extraction,
or when the hydrated formula of any edition disagrees with that edition's dictionary.
Both modes print the inventory of left-out boxes; ``--inventory PATH`` also writes it.

Run ``python -m dev.registry.authoring.autonomic_deduction_sum`` to write and
``python -m dev.registry.authoring.autonomic_deduction_sum --check`` to verify.
"""

from __future__ import annotations

import argparse
import itertools
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.formula_runtime_ops import RegistryUnresolvedOutcomeReason
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues

from ..compiler.design_sum import DesignSumError, SelectedTerm, SignedBox, decode_selected_sum
from ..compiler.loader import load_registry_tree
from .autonomic_deduction_sum_dictionary import (
    SUMMARY_BOX,
    AutonomicSumExtractionError,
    ComunidadOperands,
    extract_comunidad_operands,
)
from .autonomic_deduction_sum_inventory import LeftOutEntry, inventory_header, inventory_lines, left_out_entries
from .autonomic_deduction_sum_manifest import manifest_files

__all__ = [
    "AuthoredTerm",
    "EditionOperands",
    "Meaning",
    "check",
    "inventory_text",
    "main",
    "meaning",
    "registry_operands",
    "render",
    "render_delta",
    "write",
]

MODELO: Final = "100"
FORMULA_ID: Final = "renta-deducciones-autonomicas-suma"
RESIDENCE_BINDING: Final = "renta-profile-tax-residence-ccaa"
OTHER_COMUNIDAD_REASON: Final = RegistryUnresolvedOutcomeReason.AUTONOMIC_DEDUCTION_OTHER_COMUNIDAD.value
UNSUMMED_REASON: Final = RegistryUnresolvedOutcomeReason.AUTONOMIC_DEDUCTION_UNSUMMED_BOX.value
LEGAL_REFS: Final = ("ley-35-2006:art-77",)
#: The guidance-tier citation the formula keeps beside its row citations.
GUIDANCE_REF: Final = "lirpf-cuota-chain-authority"
GUIDANCE_TEXT: Final = (
    "El importe de las deducciones establecidas por la Comunidad Autónoma en el ejercicio de las competencias",
)
SHARD_NAME: Final = "0003-deducciones-autonomicas-suma.toml"
BEGIN_MARK: Final = (
    "# BEGIN casilla 0564 autonomic deduction sum, written by dev.registry.authoring.autonomic_deduction_sum"
)
END_MARK: Final = "# END casilla 0564 autonomic deduction sum"
_PER_LINE: Final = 6


@dataclass(frozen=True, slots=True)
class EditionOperands:
    """One authored edition, the dictionary it prints, and every comunidad's operands."""

    revision_id: str
    source_ref: str
    comunidades: tuple[ComunidadOperands, ...]
    left_out: tuple[LeftOutEntry, ...] = ()

    def guards(self, residence: str) -> tuple[str, ...]:
        """The left-out boxes that leave the comunidad's term without a value when they hold an amount."""
        return tuple(entry.left_out.box for entry in self.left_out if entry.residence == residence and entry.guarded)

    def term(self, comunidad: ComunidadOperands) -> AuthoredTerm:
        """The comunidad's operands and guards, in the shape the registry formula declares."""
        return comunidad.operands, self.guards(comunidad.residence)


def _modelo(modelos: Sequence[ModeloDefinition]) -> ModeloDefinition:
    return next(modelo for modelo in modelos if modelo.id == MODELO)


def _editions(modelo: ModeloDefinition) -> tuple[ModeloRevision, ...]:
    return tuple(sorted(modelo.revisions.values(), key=lambda revision: revision.valid_from))


def _dictionary_source(revision: ModeloRevision, catalogues: RegistryCatalogues) -> tuple[str, bytes]:
    """The one declaration dictionary among the edition's casilla sources that prints the sum."""
    found: list[tuple[str, bytes]] = []
    for source_ref in revision.casilla_source_refs or ():
        source = catalogues.sources[source_ref]
        if source.kind is not RegistrySourceKind.DICTIONARY or not source.corpus_path:
            continue
        body = bundled_path(*Path(source.corpus_path).parts).read_bytes()
        if f"][{SUMMARY_BOX}][".encode() in body:
            found.append((source_ref, body))
    if len(found) != 1:
        raise AutonomicSumExtractionError(
            f"edition {revision.id}: expected one declaration dictionary printing [{SUMMARY_BOX}], found {len(found)}"
        )
    return found[0]


def extract_editions(
    modelos: Sequence[ModeloDefinition], catalogues: RegistryCatalogues
) -> tuple[EditionOperands, ...]:
    """Extract every authored edition and refuse an operand the edition does not declare."""
    editions: list[EditionOperands] = []
    for revision in _editions(_modelo(modelos)):
        source_ref, body = _dictionary_source(revision, catalogues)
        comunidades = extract_comunidad_operands(body)
        declared = {str(casilla.id) for casilla in revision.casillas}
        for comunidad in comunidades:
            missing = sorted(operand.box for operand in comunidad.operands if operand.box not in declared)
            if missing:
                raise AutonomicSumExtractionError(
                    f"edition {revision.id} {comunidad.row.field}: the registry declares no casilla {missing}"
                )
        editions.append(
            EditionOperands(str(revision.id), source_ref, comunidades, left_out_entries(revision, comunidades))
        )
    return tuple(editions)


def _toml_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _operand_lines(operands: tuple[SignedBox, ...], indent: str) -> list[str]:
    leaves = [
        f'{{ casilla_id = "{operand.box}" }}'
        if operand.sign > 0
        else f'{{ op = "negate", args = [{{ casilla_id = "{operand.box}" }}] }}'
        for operand in operands
    ]
    return [indent + ", ".join(leaves[index : index + _PER_LINE]) + "," for index in range(0, len(leaves), _PER_LINE)]


def _magnitude_lines(guards: tuple[str, ...], indent: str) -> list[str]:
    return [
        f'{indent}{{ op = "max", args = [{{ casilla_id = "{box}" }}, '
        f'{{ op = "negate", args = [{{ casilla_id = "{box}" }}] }}] }},'
        for box in guards
    ]


def _resident_lines(comunidad: ComunidadOperands, guards: tuple[str, ...], indent: str) -> list[str]:
    """The comunidad's sum, refused while any left-out box it names holds an amount."""
    if not guards:
        return [
            f'{indent}{{ op = "sum", args = [',
            *_operand_lines(comunidad.operands, indent + "    "),
            f"{indent}] }},",
        ]
    inner = indent + "    "
    return [
        f'{indent}{{ op = "if_then_else", args = [',
        f'{inner}{{ op = "equal", args = [{{ op = "sum", args = [',
        *_magnitude_lines(guards, inner + "    "),
        f'{inner}] }}, {{ literal = "0" }}] }},',
        *_resident_lines(comunidad, (), inner),
        f'{inner}{{ op = "unresolved_outcome", args = [{{ text_literal = "{UNSUMMED_REASON}" }}] }},',
        f"{indent}] }},",
    ]


def _term_lines(edition: EditionOperands, comunidad: ComunidadOperands, indent: str) -> list[str]:
    inner = indent + "    "
    return [
        f"{indent}# {edition.source_ref}:{comunidad.row.line} {comunidad.row.field}",
        f'{indent}{{ op = "if_then_else", args = [',
        f'{inner}{{ op = "text_equal", args = [{{ binding = "{RESIDENCE_BINDING}" }}, '
        f'{{ text_literal = "{comunidad.residence}" }}] }},',
        *_resident_lines(comunidad, edition.guards(comunidad.residence), inner),
        f'{inner}{{ op = "if_then_else", args = [',
        f'{inner}    {{ op = "equal", args = [{{ op = "sum", args = [',
        *_operand_lines(comunidad.operands, inner + "        "),
        f'{inner}    ] }}, {{ literal = "0" }}] }},',
        f'{inner}    {{ literal = "0" }},',
        f'{inner}    {{ op = "unresolved_outcome", args = [{{ text_literal = "{OTHER_COMUNIDAD_REASON}" }}] }},',
        f"{inner}] }},",
        f"{indent}] }},",
    ]


def _citation(edition: EditionOperands, comunidad: ComunidadOperands) -> str:
    """The layout citation of one term: the edition's dictionary and the whole row it prints."""
    return (
        f"{{ source_ref = {_toml_string(edition.source_ref)}, required_text = [{_toml_string(comunidad.row.text)}] }}"
    )


def _citation_tables(edition: EditionOperands) -> list[str]:
    lines: list[str] = []
    for comunidad in edition.comunidades:
        lines += [
            "",
            f"# {edition.source_ref}:{comunidad.row.line} {comunidad.row.field}",
            f'[[revisions."{edition.revision_id}".formulas.source_citations]]',
            f"source_ref = {_toml_string(edition.source_ref)}",
            f"required_text = [{_toml_string(comunidad.row.text)}]",
        ]
    return lines


def render_baseline(edition: EditionOperands) -> str:
    """The full formula declaration of the oldest authored edition."""
    lines = [
        "# Casilla 0564 (SUMADEDAUT): the autonomic deductions of the comunidad of residence. One term per",
        "# comunidad, each summing the casillas its DEDAUTx row of the official dictionary names. Written by",
        "# `python -m dev.registry.authoring.autonomic_deduction_sum` from the dictionaries; do not edit.",
        f'[[revisions."{edition.revision_id}".formulas]]',
        f'id = "{FORMULA_ID}"',
        f'target_casilla_id = "{SUMMARY_BOX}"',
        'expression = { op = "sum", args = [',
    ]
    for comunidad in edition.comunidades:
        lines.extend(_term_lines(edition, comunidad, "    "))
    lines += [
        "] }",
        'rounding = "money-2"',
        "legal_refs = [" + ", ".join(_toml_string(ref) for ref in LEGAL_REFS) + "]",
        f"source_refs = [{_toml_string(GUIDANCE_REF)}, {_toml_string(edition.source_ref)}]",
        "",
        f'[[revisions."{edition.revision_id}".formulas.source_citations]]',
        f"source_ref = {_toml_string(GUIDANCE_REF)}",
        "required_text = [" + ", ".join(_toml_string(text) for text in GUIDANCE_TEXT) + "]",
        *_citation_tables(edition),
    ]
    return "\n".join(lines) + "\n"


def _changed(previous: EditionOperands, edition: EditionOperands) -> tuple[int, ...]:
    before = [comunidad.residence for comunidad in previous.comunidades]
    after = [comunidad.residence for comunidad in edition.comunidades]
    if before != after:
        raise AutonomicSumExtractionError(
            f"edition {edition.revision_id}: the comunidad rows differ from edition {previous.revision_id}"
        )
    return tuple(
        index
        for index, (old, new) in enumerate(zip(previous.comunidades, edition.comunidades, strict=True))
        if meaning(previous.term(old)) != meaning(edition.term(new))
    )


def _restoring_order(count: int, replaced: tuple[int, ...]) -> list[int]:
    kept = [index for index in range(count) if index not in replaced]
    patched = kept + list(replaced)
    return [patched.index(position) for position in range(count)]


def _positions(values: Sequence[int]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"


def render_delta(previous: EditionOperands, edition: EditionOperands, known_refs: frozenset[str]) -> str:
    """The family override replacing the changed comunidad terms and their row citations, or an empty string.

    The citations list the guidance citation first and then one row citation per term, so a
    term's citation sits one position after the term.
    """
    changed = _changed(previous, edition)
    if not changed:
        return ""
    count = len(edition.comunidades)
    cited = tuple(index + 1 for index in changed)
    terms: list[str] = []
    for index in changed:
        terms.extend(_term_lines(edition, edition.comunidades[index], "    "))
    citations = [
        f"    # {edition.source_ref}:{edition.comunidades[index].row.line} {edition.comunidades[index].row.field}\n"
        f"    {_citation(edition, edition.comunidades[index])},"
        for index in changed
    ]
    refs = "" if edition.source_ref in known_refs else f", source_refs = [{_toml_string(edition.source_ref)}]"
    return "\n".join(
        [
            f'[[revisions."{edition.revision_id}".family_overrides]]',
            'family = "formulas"',
            f'selector = {{ revision = "{previous.revision_id}", id = "{FORMULA_ID}" }}',
            f'sequence_removals = {{ "expression.args" = {_positions(changed)}, '
            f'"source_citations" = {_positions(cited)} }}',
            'sequence_additions = { "expression.args" = [',
            *terms,
            '], "source_citations" = [',
            *citations,
            f"]{refs} }}",
            f'sequence_order = {{ "expression.args" = {_positions(_restoring_order(count, changed))}, '
            f'"source_citations" = {_positions(_restoring_order(count + 1, cited))} }}',
        ]
    )


def render(editions: Sequence[EditionOperands]) -> tuple[str, dict[str, str]]:
    """The baseline shard text and each later edition's delta block (empty when unchanged)."""
    baseline = render_baseline(editions[0])
    deltas: dict[str, str] = {}
    known_refs = {editions[0].source_ref}
    for previous, edition in itertools.pairwise(editions):
        deltas[edition.revision_id] = render_delta(previous, edition, frozenset(known_refs))
        if deltas[edition.revision_id]:
            known_refs.add(edition.source_ref)
    return baseline, deltas


def _revision_dir(revision_id: str) -> Path:
    return bundled_path("registry", "aeat", "modelos", MODELO, "revisions", revision_id)


def _with_block(text: str, block: str) -> str:
    """Replace the marked block of a revision manifest, append it, or remove it when empty."""
    start, end = text.find(BEGIN_MARK), text.find(END_MARK)
    if (start < 0) != (end < 0) or end < start:
        raise AutonomicSumExtractionError("revision manifest carries an unbalanced generated block")
    if start >= 0:
        head, tail = text[:start].rstrip("\n"), text[end + len(END_MARK) :].lstrip("\n")
        text = head + "\n" + (("\n" + tail) if tail else "")
    if not block:
        return text
    return text.rstrip("\n") + f"\n\n{BEGIN_MARK}\n{block}\n{END_MARK}\n"


def _expected_files(editions: Sequence[EditionOperands]) -> dict[Path, str]:
    baseline, deltas = render(editions)
    files = {_revision_dir(editions[0].revision_id) / "formulas" / SHARD_NAME: baseline}
    for revision_id, block in deltas.items():
        manifest = _revision_dir(revision_id) / "revision.toml"
        files[manifest] = _with_block(manifest.read_text(encoding="utf-8"), block)
    return files


def _manifest_files(modelos: Sequence[ModeloDefinition]) -> dict[Path, str]:
    revisions = _editions(_modelo(modelos))
    return manifest_files(revisions, {str(revision.id): _revision_dir(str(revision.id)) for revision in revisions})


def _publish(files: Mapping[Path, str]) -> list[Path]:
    changed: list[Path] = []
    for path, text in files.items():
        if not text:
            if path.exists():
                path.unlink()
                changed.append(path)
        elif not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8", newline="\n")
            changed.append(path)
    return changed


def write(editions: Sequence[EditionOperands]) -> list[Path]:
    """Write the formula declarations, then the manifests their closure needs; return the changed files.

    The manifests are derived from the registry as hydrated after the formula is written,
    because the formula's operands are what enter each edition's calculation closure.
    """
    changed = _publish(_expected_files(editions))
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return changed + _publish(_manifest_files(modelos))


AuthoredTerm = tuple[tuple[SignedBox, ...], tuple[str, ...]]
Meaning = tuple[frozenset[SignedBox], frozenset[str]]


def meaning(term: AuthoredTerm) -> Meaning:
    """What a comunidad term computes: its signed operands and its guards, irrespective of order."""
    operands, guards = term
    return frozenset(operands), frozenset(guards)


def registry_operands(revision: ModeloRevision) -> Mapping[str, AuthoredTerm]:
    """Each comunidad's operands and left-out guards as the hydrated edition declares them, in term order."""
    formulas = [formula for formula in revision.formulas if formula.target_casilla_id == SUMMARY_BOX]
    casilla = next(casilla for casilla in revision.casillas if str(casilla.id) == SUMMARY_BOX)
    if len(formulas) != 1 or formulas[0].id != FORMULA_ID or casilla.formula != FORMULA_ID:
        raise AutonomicSumExtractionError(
            f"edition {revision.id}: casilla {SUMMARY_BOX} is not computed by {FORMULA_ID}"
        )
    terms = decode_selected_sum(formulas[0].expression)
    for term in terms:
        _require_writer_shape(revision, term)
    return {term.selector: (term.operands, term.guards) for term in terms}


def _require_writer_shape(revision: ModeloRevision, term: SelectedTerm) -> None:
    """Refuse a decoded term on another binding or refusing for a reason the writer does not emit."""
    expected_guard_reason = UNSUMMED_REASON if term.guards else None
    if (
        term.binding != RESIDENCE_BINDING
        or term.other_reason != OTHER_COMUNIDAD_REASON
        or term.guard_reason != expected_guard_reason
    ):
        raise AutonomicSumExtractionError(
            f"edition {revision.id}: the {term.selector} term is not the residence term the writer emits"
        )


def _edition_problems(revision: ModeloRevision, edition: EditionOperands) -> list[str]:
    try:
        authored = registry_operands(revision)
    except DesignSumError as exc:
        return [str(exc)]
    extracted = {comunidad.residence: meaning(edition.term(comunidad)) for comunidad in edition.comunidades}
    problems = (
        [f"edition {edition.revision_id}: the comunidad terms differ from the dictionary rows"]
        if list(authored) != list(extracted)
        else []
    )
    return problems + [
        f"edition {edition.revision_id} {residence}: operands or left-out guards differ from the dictionary"
        for residence, term in extracted.items()
        if residence not in authored or meaning(authored[residence]) != term
    ]


def check(modelos: Sequence[ModeloDefinition], editions: Sequence[EditionOperands]) -> list[str]:
    """Return every divergence between the dictionaries and the registry; empty when they agree."""
    problems = [
        f"{path}: differs from a fresh extraction; run the tool to rewrite it"
        for path, text in _expected_files(editions).items()
        if not path.exists() or path.read_text(encoding="utf-8") != text
    ]
    problems += [
        f"{path}: does not list the calculation closure the formula needs; run the tool to rewrite it"
        for path in _manifest_files(modelos)
    ]
    revisions = _modelo(modelos).revisions
    for edition in editions:
        problems += _edition_problems(revisions[edition.revision_id], edition)
    return problems


def inventory_text(editions: Sequence[EditionOperands]) -> str:
    """The inventory of every left-out box, one tab-separated line each, after a header."""
    lines = [inventory_header()]
    for edition in editions:
        lines += inventory_lines(edition.revision_id, edition.source_ref, edition.left_out)
    return "\n".join(lines) + "\n"


def _report_inventory(editions: Sequence[EditionOperands], path: Path | None) -> None:
    text = inventory_text(editions)
    print(text, end="")
    if path is not None:
        path.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    """Write the 0564 declarations, or with ``--check`` fail when they diverge from the dictionaries."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the registry diverges from the dictionaries")
    parser.add_argument("--inventory", type=Path, help="also write the inventory of left-out boxes to this file")
    args = parser.parse_args(argv)
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    try:
        editions = extract_editions(modelos, catalogues)
    except DesignSumError as exc:
        print(f"autonomic-deduction-sum\tfailed\t{exc}", file=sys.stderr)
        return 1
    _report_inventory(editions, args.inventory)
    if args.check:
        problems = check(modelos, editions)
        for problem in problems:
            print(f"autonomic-deduction-sum\tdiverged\t{problem}", file=sys.stderr)
        print(f"autonomic-deduction-sum\t{'failed' if problems else 'current'}\teditions={len(editions)}")
        return 1 if problems else 0
    for path in write(editions):
        print(f"autonomic-deduction-sum\twrote\t{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
