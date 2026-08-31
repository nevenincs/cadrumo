"""Generate one result-disposition fragment per filing-grade revision.

Every filing-grade revision must resolve every enrolled schema family, so a new
family cannot land without a declaration for each of them. This program writes
those declarations from evidence rather than assertion: the mapping comes out of
the modelo's own diseño de registro via
:mod:`dev.registry.derive_result_dispositions`, and a modelo whose diseño never
carries the field is declared not applicable with that measured absence as its
reason.

Scope note, deliberate and recorded: the fragment declares the DISPOSITION
SEMANTICS only -- what a negative and a zero result mean for this modelo. It does
not declare which casilla holds the result. That second fact is not derivable:
the registry names casillas by semantic role, and the roles are not consistent
across modelos (Modelo 303 says ``iva_resultado_autoliquidacion``, Modelo 130
``irpf_pf_resultado_final``, while Modelos 111, 115 and 123 carry only
``resultado_anteriores_autoliquidaciones``, which is the PRIOR filing's result).
Deriving it would mean encoding a modelo-to-role map in Python, which is the
transcription this migration exists to remove, so the casilla identification
stays where it is until the registry marks a result casilla as a first-class
fact.

Campaign-owned trees are skipped: Modelos 303 and 390 belong to the
export-fragment campaign while it holds them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .derive_result_dispositions import read_diseno_evidence

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_MODELOS_ROOT = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

#: Modelo trees another campaign owns while it holds them.
CAMPAIGN_OWNED_MODELOS: frozenset[str] = frozenset({"303", "390"})

_FRAGMENT_DIRNAME = "result_dispositions"
_FRAGMENT_FILENAME = "0001-result-dispositions.toml"


@dataclass(frozen=True, slots=True)
class GeneratedFragment:
    """One revision's rendered declaration."""

    modelo: str
    revision: str
    path: Path
    body: str
    applicable: bool


def _render(modelo: str, revision: str, *, negative: str | None, zero: str | None, note: str, scanned: int) -> str:
    header = f"# Modelo {modelo} result disposition, read from its own diseno de registro.\n#\n"
    if negative is None:
        return (
            header + f"# The diseno declares no 'Tipo de declaracion' field anywhere across the\n"
            f"# {scanned} corpus files bundled for this modelo. An informative declaration\n"
            "# settles no cuota, so there is no result to dispose of. The absence is\n"
            "# measured rather than assumed, which is what makes this declaration honest.\n"
            f'[[revisions."{revision}".result_dispositions]]\n'
            f'id = "modelo-{modelo}-result-disposition"\n'
            "applicable = false\n"
            'not_applicable_reason = "El diseno de registro de este modelo no declara campo '
            "'Tipo de declaracion': es una declaracion informativa que no liquida cuota, "
            'por lo que no existe disposicion de resultado."\n'
        )
    quoted = note[:180].replace('"', "'")
    return (
        header + "# The diseno states the admissible letters verbatim; the letters ARE the\n"
        "# disposition. A negative result takes the most specific letter the modelo\n"
        "# admits -- C, else B, else D -- and falls back to N when it admits none.\n"
        f'[[revisions."{revision}".result_dispositions]]\n'
        f'id = "modelo-{modelo}-result-disposition"\n'
        "applicable = true\n"
        f'negative_disposition = "{negative}"\n'
        f'zero_disposition = "{zero}"\n'
        f'diseno_note = "{quoted}"\n'
    )


def plan_fragments(root: Path | None = None) -> tuple[GeneratedFragment, ...]:
    """Render a declaration for every filing-grade revision outside owned trees."""
    from cadrumo.core.authority_grade import RegistryAuthorityGrade
    from cadrumo.core.resources import bundled_path
    from cadrumo.domain.calculations.registry.loader import load_registry_tree

    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelos_root = root if root is not None else REGISTRY_MODELOS_ROOT
    planned: list[GeneratedFragment] = []
    cache: dict[str, object] = {}
    for definition in modelos:
        if definition.id in CAMPAIGN_OWNED_MODELOS:
            continue
        evidence = cache.setdefault(definition.id, read_diseno_evidence(definition.id))
        for revision in definition.revisions.values():
            if revision.authority_grade is not RegistryAuthorityGrade.FILING:
                continue
            negative = evidence.negative_disposition  # type: ignore[attr-defined]
            body = _render(
                definition.id,
                str(revision.id),
                negative=negative,
                zero=evidence.zero_disposition,  # type: ignore[attr-defined]
                note=evidence.note,  # type: ignore[attr-defined]
                scanned=evidence.corpus_files_scanned,  # type: ignore[attr-defined]
            )
            planned.append(
                GeneratedFragment(
                    modelo=definition.id,
                    revision=str(revision.id),
                    path=(
                        modelos_root
                        / definition.id
                        / "revisions"
                        / str(revision.id)
                        / _FRAGMENT_DIRNAME
                        / _FRAGMENT_FILENAME
                    ),
                    body=body,
                    applicable=negative is not None,
                ),
            )
    return tuple(planned)


def write_fragments(root: Path | None = None, *, apply: bool = False) -> tuple[GeneratedFragment, ...]:
    """Write every planned declaration. With ``apply`` false, nothing is touched."""
    planned = plan_fragments(root)
    if apply:
        for fragment in planned:
            fragment.path.parent.mkdir(parents=True, exist_ok=True)
            fragment.path.write_text(fragment.body, encoding="utf-8")
    return planned


def main() -> int:
    """Render the declarations, reporting the applicable/not-applicable split."""
    import sys

    apply = "--apply" in sys.argv
    planned = write_fragments(apply=apply)
    applicable = sum(1 for fragment in planned if fragment.applicable)
    verb = "wrote" if apply else "would write"
    print(
        f"{verb} {len(planned)} declarations: {applicable} with a derived mapping, "
        f"{len(planned) - applicable} not applicable",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CAMPAIGN_OWNED_MODELOS",
    "GeneratedFragment",
    "plan_fragments",
    "write_fragments",
]
