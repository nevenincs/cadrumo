"""Screen: whether cross-revision casilla continuity chains hold together.

A ``continuidad_id`` asserts that a casilla in one revision is the same casilla
as one in another, which is what lets a figure be carried, compared or
explained across years. The assertion is authored, not derived, so it can be
made between casillas that have nothing to do with each other and the registry
will validate.

Four conditions are reported:

- ``chain_crosses_grammar`` - one chain's members use more than one identifier
  grammar. Identity across a grammar change is not automatically wrong, but it
  is the shape a mistaken chain takes, and it is the case an identifier
  contract would have to permit explicitly rather than by silence.
- ``singleton_chain`` - a chain whose members all sit in one revision, so it
  asserts continuity across nothing. Either a sibling is missing or the
  identifier should not be a chain at all.
- ``evolution_without_members`` - an evolution record names a chain no casilla
  carries, so the transition it describes has no endpoints.
- ``modelo_without_continuity`` - a modelo with several revisions where no
  casilla carries a chain at all, reported so that absent continuity is
  distinguishable from broken continuity.

Coverage is reported in the closing census rather than as a finding. A casilla
carrying no chain is not a defect on its own: most casillas are revision-local
and asserting continuity for them would be inventing identity.

The screen exits 0 whatever it finds. It reports; it does not gate. The three
conditions that hold corpus-wide are gated as invariants in the declaration
gate module.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from .casilla_id_grammar import classify_casilla_id

__all__ = [
    "ContinuityFinding",
    "chain_index",
    "continuity_census",
    "definition_findings",
    "screen_authority",
]


@dataclass(frozen=True, slots=True)
class ContinuityFinding:
    """One continuity chain that does not hold together."""

    modelo: str
    kind: str
    detail: str


@dataclass(frozen=True, slots=True)
class ContinuityCensus:
    """Corpus-wide continuity coverage, reported beside the findings."""

    casillas: int
    with_chain: int
    chains: int
    evolutions: int


def chain_index(definition: ModeloDefinition) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    """Return per-chain grammars, per-chain revisions, and per-chain evolution sites.

    Takes the modelo definition rather than the authority because that is all it
    reads, which lets a test hand it a copy of a real definition carrying a
    constructed defect instead of standing something in for the authority.
    """
    grammars: dict[str, set[str]] = collections.defaultdict(set)
    revisions: dict[str, set[str]] = collections.defaultdict(set)
    evolutions: dict[str, set[str]] = collections.defaultdict(set)
    for revision_id, revision in definition.revisions.items():
        for casilla in revision.casillas:
            chain = getattr(casilla, "continuidad_id", None)
            if chain:
                grammars[str(chain)].add(classify_casilla_id(str(casilla.id)))
                revisions[str(chain)].add(str(revision_id))
        for evolution in revision.casilla_continuidad_evolutions:
            evolutions[str(evolution.continuidad_id)].add(str(revision_id))
    return dict(grammars), dict(revisions), dict(evolutions)


def definition_findings(definition: ModeloDefinition, *, modelo_id: str) -> tuple[ContinuityFinding, ...]:
    """Return one modelo definition's continuity findings.

    Takes the definition rather than the authority, as the sibling screens'
    per-unit functions do, so a test can hand it a copy of a real definition
    carrying a constructed defect and assert the KIND the screen would report.
    Without this a detector proof can only reach the index underneath, which
    shows the defect is visible without showing that the screen reports it -
    and two of this screen's conditions were proven exactly that far.
    """
    findings: list[ContinuityFinding] = []
    grammars, revisions, evolutions = chain_index(definition)
    if not grammars and len(definition.revisions) > 1:
        findings.append(
            ContinuityFinding(
                modelo=modelo_id,
                kind="modelo_without_continuity",
                detail=f"{len(definition.revisions)} revisions and no casilla carries a chain",
            )
        )
    for chain, used in sorted(grammars.items()):
        if len(used) > 1:
            findings.append(
                ContinuityFinding(
                    modelo=modelo_id,
                    kind="chain_crosses_grammar",
                    detail=f"chain {chain} spans grammars {sorted(used)}",
                )
            )
    for chain, seen in sorted(revisions.items()):
        if len(seen) == 1:
            findings.append(
                ContinuityFinding(
                    modelo=modelo_id,
                    kind="singleton_chain",
                    detail=f"chain {chain} appears only in revision {next(iter(seen))}",
                )
            )
    findings.extend(
        ContinuityFinding(
            modelo=modelo_id,
            kind="evolution_without_members",
            detail=f"evolution names chain {chain} that no casilla carries",
        )
        for chain in sorted(set(evolutions) - set(grammars))
    )
    return tuple(findings)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[ContinuityFinding, ...]:
    """Screen every modelo's continuity chains through the validated authority."""
    findings: list[ContinuityFinding] = []
    for modelo_id in modelo_ids:
        findings.extend(definition_findings(authority.modelo(modelo_id), modelo_id=modelo_id))
    return tuple(findings)


def continuity_census(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> ContinuityCensus:
    """Return corpus-wide continuity coverage counts."""
    casillas = with_chain = evolutions = 0
    chains: set[tuple[str, str]] = set()
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for revision in definition.revisions.values():
            for casilla in revision.casillas:
                casillas += 1
                chain = getattr(casilla, "continuidad_id", None)
                if chain:
                    with_chain += 1
                    chains.add((modelo_id, str(chain)))
            evolutions += len(revision.casilla_continuidad_evolutions)
    return ContinuityCensus(casillas=casillas, with_chain=with_chain, chains=len(chains), evolutions=evolutions)


def _bundled_modelo_ids() -> tuple[str, ...]:
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    return tuple(sorted(str(code) for code in registry_modelo_codes()))


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    authority = bundled_authority()
    modelo_ids = _bundled_modelo_ids()
    findings = screen_authority(authority, modelo_ids)
    census = continuity_census(authority, modelo_ids)
    tally: collections.Counter[str] = collections.Counter(finding.kind for finding in findings)
    for finding in findings:
        sys.stdout.write(f"continuity modelo={finding.modelo} kind={finding.kind} detail={finding.detail!r}\n")
    kinds = " ".join(f"{kind}={count}" for kind, count in sorted(tally.items()))
    sys.stdout.write(
        f"summary findings={len(findings)} casillas={census.casillas} with_chain={census.with_chain} "
        f"chains={census.chains} evolutions={census.evolutions} {kinds}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
