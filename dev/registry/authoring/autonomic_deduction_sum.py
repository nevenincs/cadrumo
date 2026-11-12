"""Write or check the Modelo 100 formula of casilla 0564 from the official dictionaries.

Casilla 0564 is the sum of the autonomic deductions of the comunidad of residence.
Each edition's declaration dictionary prints that sum once per comunidad as a
``DEDAUTx`` row; :mod:`.autonomic_deduction_sum_dictionary` reads the operands.

The formula adds one term per comunidad, in the dictionary's order:

- the comunidad of residence contributes its official sum;
- any other comunidad whose official sum is not zero leaves 0564 without a value,
  for a typed reason, because the return can carry only one comunidad's deductions;
- any other comunidad contributes zero.

The oldest authored edition declares the whole formula. A later edition carries a
delta only for the comunidades whose operand list differs from the edition before
it: their terms are replaced in place, and every other term is inherited. Each
edition's calculation-completeness manifest then lists the boxes the formula reads.

``--check`` fails when the committed declarations differ from a fresh extraction,
or when the hydrated formula of any edition disagrees with that edition's dictionary.

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
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression

from ..compiler.loader import load_registry_tree
from .autonomic_deduction_sum_dictionary import (
    SUMMARY_BOX,
    AutonomicSumExtractionError,
    ComunidadOperands,
    SignedBox,
    extract_comunidad_operands,
)
from .autonomic_deduction_sum_manifest import manifest_files

__all__ = ["EditionOperands", "check", "main", "registry_operands", "render", "write"]

MODELO: Final = "100"
FORMULA_ID: Final = "renta-deducciones-autonomicas-suma"
RESIDENCE_BINDING: Final = "renta-profile-tax-residence-ccaa"
OTHER_COMUNIDAD_REASON: Final = RegistryUnresolvedOutcomeReason.AUTONOMIC_DEDUCTION_OTHER_COMUNIDAD.value
LEGAL_REFS: Final = ("ley-35-2006:art-77",)
#: Formula citations quote guidance-tier text. The dictionaries are layout authority, so each
#: edition's dictionary is listed in ``source_refs`` and each term names its row by line.
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
        editions.append(EditionOperands(str(revision.id), source_ref, comunidades))
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


def _term_lines(edition: EditionOperands, comunidad: ComunidadOperands, indent: str) -> list[str]:
    inner = indent + "    "
    return [
        f"{indent}# {edition.source_ref}:{comunidad.row.line} {comunidad.row.field}",
        f'{indent}{{ op = "if_then_else", args = [',
        f'{inner}{{ op = "text_equal", args = [{{ binding = "{RESIDENCE_BINDING}" }}, '
        f'{{ text_literal = "{comunidad.residence}" }}] }},',
        f'{inner}{{ op = "sum", args = [',
        *_operand_lines(comunidad.operands, inner + "    "),
        f"{inner}] }},",
        f'{inner}{{ op = "if_then_else", args = [',
        f'{inner}    {{ op = "equal", args = [{{ op = "sum", args = [',
        *_operand_lines(comunidad.operands, inner + "        "),
        f'{inner}    ] }}, {{ literal = "0" }}] }},',
        f'{inner}    {{ literal = "0" }},',
        f'{inner}    {{ op = "unresolved_outcome", args = [{{ text_literal = "{OTHER_COMUNIDAD_REASON}" }}] }},',
        f"{inner}] }},",
        f"{indent}] }},",
    ]


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
        if old.operands != new.operands
    )


def _restoring_order(count: int, replaced: tuple[int, ...]) -> list[int]:
    kept = [index for index in range(count) if index not in replaced]
    patched = kept + list(replaced)
    return [patched.index(position) for position in range(count)]


def render_delta(previous: EditionOperands, edition: EditionOperands, known_refs: frozenset[str]) -> str:
    """The family override replacing the changed comunidad terms, or an empty string."""
    changed = _changed(previous, edition)
    if not changed:
        return ""
    indices = "[" + ", ".join(str(index) for index in changed) + "]"
    order = "[" + ", ".join(str(index) for index in _restoring_order(len(edition.comunidades), changed)) + "]"
    terms: list[str] = []
    for index in changed:
        terms.extend(_term_lines(edition, edition.comunidades[index], "    "))
    refs = "" if edition.source_ref in known_refs else f", source_refs = [{_toml_string(edition.source_ref)}]"
    return "\n".join(
        [
            f'[[revisions."{edition.revision_id}".family_overrides]]',
            'family = "formulas"',
            f'selector = {{ revision = "{previous.revision_id}", id = "{FORMULA_ID}" }}',
            f'sequence_removals = {{ "expression.args" = {indices} }}',
            'sequence_additions = { "expression.args" = [',
            *terms,
            f"]{refs} }}",
            f'sequence_order = {{ "expression.args" = {order} }}',
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


def _signed(expression: FormulaExpression) -> SignedBox:
    if expression.casilla_id is not None:
        return SignedBox(1, str(expression.casilla_id))
    if expression.op == "negate" and len(expression.args) == 1 and expression.args[0].casilla_id is not None:
        return SignedBox(-1, str(expression.args[0].casilla_id))
    raise AutonomicSumExtractionError(f"operand {expression!r} is neither a casilla nor its negation")


def _is_zero_test(test: FormulaExpression) -> bool:
    return test.op == "equal" and len(test.args) == 2 and test.args[0].op == "sum" and test.args[1].literal == 0


def _is_other_comunidad_outcome(unresolved: FormulaExpression) -> bool:
    return unresolved.op == "unresolved_outcome" and unresolved.args[0].text_literal == OTHER_COMUNIDAD_REASON


def _guarded_sum(other: FormulaExpression) -> tuple[SignedBox, ...] | None:
    """The operands of the other-comunidad guard, or ``None`` when its shape is not the writer's."""
    if other.op != "if_then_else" or len(other.args) != 3:
        return None
    test, zero, unresolved = other.args
    if not _is_zero_test(test) or zero.literal != 0 or not _is_other_comunidad_outcome(unresolved):
        return None
    return tuple(_signed(arg) for arg in test.args[0].args)


def _term_operands(term: FormulaExpression) -> tuple[str, tuple[SignedBox, ...]]:
    """Decode one comunidad term, refusing any shape the writer does not produce."""
    if term.op != "if_then_else" or len(term.args) != 3:
        raise AutonomicSumExtractionError("a 0564 term is not a residence test")
    predicate, resident, other = term.args
    if predicate.op != "text_equal" or len(predicate.args) != 2 or resident.op != "sum":
        raise AutonomicSumExtractionError("a 0564 term is not a residence test")
    binding, literal = predicate.args
    if binding.binding != RESIDENCE_BINDING or literal.text_literal is None:
        raise AutonomicSumExtractionError("a 0564 term does not test the residence binding")
    operands = tuple(_signed(arg) for arg in resident.args)
    if _guarded_sum(other) != operands:
        raise AutonomicSumExtractionError(f"the {literal.text_literal} term does not guard its other-comunidad sum")
    return literal.text_literal, operands


def registry_operands(revision: ModeloRevision) -> Mapping[str, tuple[SignedBox, ...]]:
    """Each comunidad's operands as the hydrated edition declares them, in term order."""
    formulas = [formula for formula in revision.formulas if formula.target_casilla_id == SUMMARY_BOX]
    casilla = next(casilla for casilla in revision.casillas if str(casilla.id) == SUMMARY_BOX)
    if len(formulas) != 1 or formulas[0].id != FORMULA_ID or casilla.formula != FORMULA_ID:
        raise AutonomicSumExtractionError(
            f"edition {revision.id}: casilla {SUMMARY_BOX} is not computed by {FORMULA_ID}"
        )
    expression = formulas[0].expression
    if expression.op != "sum":
        raise AutonomicSumExtractionError(f"edition {revision.id}: the 0564 formula is not a sum of terms")
    decoded = [_term_operands(term) for term in expression.args]
    return dict(decoded)


def _edition_problems(revision: ModeloRevision, edition: EditionOperands) -> list[str]:
    try:
        authored = registry_operands(revision)
    except AutonomicSumExtractionError as exc:
        return [str(exc)]
    extracted = {comunidad.residence: comunidad.operands for comunidad in edition.comunidades}
    problems = (
        [f"edition {edition.revision_id}: the comunidad terms differ from the dictionary rows"]
        if list(authored) != list(extracted)
        else []
    )
    return problems + [
        f"edition {edition.revision_id} {residence}: operands differ from the dictionary"
        for residence, operands in extracted.items()
        if authored.get(residence) != operands
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


def main(argv: list[str] | None = None) -> int:
    """Write the 0564 declarations, or with ``--check`` fail when they diverge from the dictionaries."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the registry diverges from the dictionaries")
    args = parser.parse_args(argv)
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    try:
        editions = extract_editions(modelos, catalogues)
    except AutonomicSumExtractionError as exc:
        print(f"autonomic-deduction-sum\tfailed\t{exc}", file=sys.stderr)
        return 1
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
