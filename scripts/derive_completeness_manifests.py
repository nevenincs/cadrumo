"""Derive calculation-completeness manifests for every calculation-bearing modelo.

Off-load-path authoring tool. Enumerates each modelo revision's
calculation closure from the registry — keyed on each closure casilla's
own ``(segmento, number)`` registry identity — and emits a
calculation-completeness manifest as registry data.

Three registry layouts are handled:

- a fragment-directory revision (``modelos/<id>/revisions/<rev>/``) gets
  a separate ``completeness-manifest.toml`` fragment;
- a revision-file revision (``modelos/<id>/revisions/<rev>.toml``) gets
  the manifest block appended to the revision file;
- a single-file modelo (``modelos/<id>.toml``) gets the manifest block
  appended to the modelo file.

A modelo revision with an empty calculation closure (no formulas, no
verification expectations) carries no calculation surface and is skipped.
A modelo revision whose closure has an undeclared or ungrounded casilla
is reported as a finding and skipped — a passing-but-wrong manifest is
never authored.
"""

from __future__ import annotations

from pathlib import Path

from aeat.core.resources import bundled_path
from aeat.domain.calculations.registry import load_registry_tree
from aeat.domain.calculations.registry._record_design import (
    calculation_closure_identities,
    derive_calculation_completeness_casillas,
)

_REGISTRY_ROOT = Path("src/aeat/_data/registry/aeat/modelos")


def _manifest_block(
    *,
    revision_id: str,
    source_ref: str,
    legal_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    casillas: tuple[tuple[str | None, str], ...],
    multi_segment: bool,
) -> str:
    rid = revision_id
    legal = ", ".join(f'"{ref}"' for ref in legal_refs)
    sources = ", ".join(f'"{ref}"' for ref in source_refs)
    lines = [
        f'[revisions."{rid}".completeness_manifest]',
        f'source_ref = "{source_ref}"',
        f"legal_refs = [{legal}]",
        f"source_refs = [{sources}]",
        "",
    ]
    for segmento, number in casillas:
        lines.append(f'[[revisions."{rid}".completeness_manifest.casillas]]')
        lines.append(f'number = "{number}"')
        if multi_segment and segmento is not None:
            lines.append(f'segmento = "{segmento}"')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


_FRAGMENT_HEADER = (
    "# Modelo {modelo} calculation-completeness manifest.\n"
    "#\n"
    "# Enumerates the casillas in this revision's calculation closure --\n"
    "# the casilla set the cross-connecting calculation engine traverses:\n"
    "# every formula target, every casilla referenced inside a formula\n"
    "# expression, every formula/binding endpoint casilla, and every\n"
    "# verification-expectation operand. Cross-modelo binding source\n"
    "# casillas belong to foreign modelos and are excluded.\n"
    "#\n"
    "# Derived off-load-path from the modelo's calculation surface, keyed\n"
    "# on each closure casilla's own registry (segmento, number) identity.\n"
    "# A casilla the revision declares but the manifest does not list (a\n"
    "# pure data-entry field that feeds no calculation) is not a gate\n"
    "# failure. The off-load-path drift re-verification test re-derives\n"
    "# this set from the registry calculation surface.\n"
    "\n"
)

_INLINE_HEADER = (
    "\n# Calculation-completeness manifest for revision {revision}: the\n"
    "# casillas in this revision's calculation closure (formula targets,\n"
    "# formula-expression refs, formula/binding endpoints, verification\n"
    "# operands), keyed on each casilla's own registry (segmento, number)\n"
    "# identity. Derived off-load-path from the registry calculation\n"
    "# surface; the drift re-verification test re-derives it.\n"
)


def main() -> None:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    authored: list[str] = []
    findings: list[str] = []
    skipped_empty: list[str] = []

    for modelo in sorted(modelos, key=lambda item: item.id):
        for revision in modelo.revisions.values():
            if revision.completeness_manifest is not None:
                continue
            closure = calculation_closure_identities(revision)
            if not closure:
                skipped_empty.append(f"{modelo.id}/{revision.id}")
                continue
            multi_segment = any(segmento is not None for segmento, _ in closure)
            declared = {(c.segmento, c.number): c for c in revision.casillas}

            missing = sorted(
                identity for identity in closure if identity not in declared
            )
            ungrounded = sorted(
                identity
                for identity in closure
                if identity in declared
                and (
                    not declared[identity].legal_refs
                    or not declared[identity].source_refs
                )
            )
            if missing or ungrounded:
                findings.append(
                    f"{modelo.id}/{revision.id}: missing={missing} ungrounded={ungrounded}"
                )
                continue

            derived = derive_calculation_completeness_casillas(
                revision, multi_segment=multi_segment, diseno_path=None
            )
            casillas = tuple(
                sorted(
                    ((item.segmento, item.number) for item in derived),
                    key=lambda pair: (pair[0] or "", pair[1]),
                )
            )

            record_design_refs = tuple(
                ref
                for ref in revision.source_refs
                if catalogues.sources[ref].kind == "record_design"
            )
            source_ref = (
                record_design_refs[0] if record_design_refs else revision.source_refs[0]
            )
            closure_casillas = [declared[identity] for identity in sorted(closure)]
            legal_refs = tuple(
                sorted({ref for c in closure_casillas for ref in c.legal_refs})
            )
            source_refs_set = {ref for c in closure_casillas for ref in c.source_refs}
            source_refs_set.add(source_ref)
            source_refs = tuple(sorted(source_refs_set))

            block = _manifest_block(
                revision_id=revision.id,
                source_ref=source_ref,
                legal_refs=legal_refs,
                source_refs=source_refs,
                casillas=casillas,
                multi_segment=multi_segment,
            )

            fragment_dir = _REGISTRY_ROOT / modelo.id / "revisions" / revision.id
            revision_file = _REGISTRY_ROOT / modelo.id / "revisions" / f"{revision.id}.toml"
            modelo_file = _REGISTRY_ROOT / f"{modelo.id}.toml"
            if fragment_dir.is_dir():
                out_path = fragment_dir / "completeness-manifest.toml"
                out_path.write_text(
                    _FRAGMENT_HEADER.format(modelo=modelo.id) + block, encoding="utf-8"
                )
            elif revision_file.is_file():
                out_path = revision_file
                existing = revision_file.read_text(encoding="utf-8").rstrip("\n") + "\n"
                revision_file.write_text(
                    existing + _INLINE_HEADER.format(revision=revision.id) + block,
                    encoding="utf-8",
                )
            elif modelo_file.is_file():
                out_path = modelo_file
                existing = modelo_file.read_text(encoding="utf-8").rstrip("\n") + "\n"
                modelo_file.write_text(
                    existing + _INLINE_HEADER.format(revision=revision.id) + block,
                    encoding="utf-8",
                )
            else:
                raise RuntimeError(f"no registry file found for modelo {modelo.id}")
            authored.append(
                f"{modelo.id}/{revision.id} -> {out_path} ({len(casillas)} casillas)"
            )

    print("=== authored manifests ===")
    for line in authored:
        print(f"  {line}")
    print(f"\n=== skipped (empty calculation closure) ({len(skipped_empty)}) ===")
    for line in skipped_empty:
        print(f"  {line}")
    print(f"\n=== FINDINGS (real calculation-correctness gaps) ({len(findings)}) ===")
    for line in findings:
        print(f"  {line}")
    if not findings:
        print("  none")


if __name__ == "__main__":
    main()
