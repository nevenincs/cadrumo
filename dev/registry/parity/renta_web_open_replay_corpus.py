"""Development-only parity fold over the Renta WEB Open replay captures.

This is a DEVELOPMENT QUALITY SIGNAL, not a product capability. Neither this
module nor the captures it reads ship inside the wheel: both live in the
repository-only ``dev`` tree, and an installed Cadrumo has no replay surface at
all.

The captures that exist are
the 2025 Modelo 100 set under ``parity_replays/renta_web_open`` beside this
module -- one per autonomous community whose ``minimo personal y familiar``
diverges from the state scale. That is the whole of the corpus: it covers one
modelo and one filing year because those are the captures that happen to exist,
and it makes no claim about any other modelo, year, or scenario.

The fold is deliberately OFFLINE: every payload is decoded by
:class:`RentaWebOpenReplayDriver`, whose only planned operation is a local
parse, and the remote-state guard authorises that plan before any comparison
happens. No AEAT contact occurs on this path, and none may be added to it.
The live capture driver that produced these payloads no longer exists in the
tree, so the captures are frozen artefacts that cannot currently be re-derived.

What the fold compares -- read this before trusting a verdict
-------------------------------------------------------------

Both sides of the comparison come out of the SAME capture file: the expected
values are read from its ``expected_by_casilla_id`` and matched against its own
``observed_by_casilla_id``. The registry engine is never evaluated here. A
``match`` therefore means the capture is internally self-consistent, and means
nothing whatsoever about whether this registry agrees with AEAT.

That distinction is load-bearing rather than pedantic. Driving the registry
directly over these same scenarios returns casilla 0520 = 5550.00 for every
comunidad autonoma, while the captures record 5606.00 for Canarias, 5789.00 for
Galicia and 5956.65 for Madrid -- three disagreements that this fold reported as
``match`` for as long as it has existed. Do not cite a green report from here as
evidence of external grounding, and do not wire the engine in without also
deciding what a resulting mismatch means: whether the registry is under-modelled
or the captures measure something else is unresolved and needs official AEAT
authority to settle.

Reading the guard policy
------------------------

The policy is not hand-built here. It is derived from the registry's own
``live_cross_references`` declaration through
:func:`remote_state_policy_from_cross_reference`, so the guard this fold runs
under is the guard the registry declares, and a declaration change reaches the
runner without a second edit.

Verdicts stay distinct
----------------------

``match``, ``mismatch``, ``unverifiable`` and ``blocked`` are four outcomes,
not a boolean. A payload whose expected casilla was never observed is
``unverifiable`` -- it is not a pass and not a failure, and the report counts
it separately so an absent observation can never be read as agreement.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import CrossReferenceId, OracleId
from cadrumo.domain.calculations.registry.remote_state_guard import (
    RemoteStateGuardPolicy,
    remote_state_policy_from_cross_reference,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_verification import LiveCrossReferenceDecision

from .external_grounding import RentaWebOpenReplayPayload
from .external_oracle_corpus import ExternalOracleCorpus
from .live_parity import ParityFieldComparison, ParityResult, ParityVerdict, ParityVerdictKind
from .renta_web_open_oracle import RentaWebOpenOracle, RentaWebOpenReplayDriver

#: Repository path of the replay captures, relative to this package directory.
_REPLAY_CORPUS_PARTS: Final[tuple[str, ...]] = ("parity_replays", "renta_web_open")

#: The capture filenames the corpus publishes, matching the grounding inventory's glob.
_REPLAY_PAYLOAD_PATTERN: Final[str] = "modelo-*.json"


class ReplayCorpusModel(BaseModel):
    """Strict frozen base for replay-corpus parity facts."""

    model_config = STRICT_FROZEN_CONFIG


class ReplayPayloadParity(ReplayCorpusModel):
    """One capture's parity outcome, with its per-casilla comparisons."""

    payload_name: str = Field(min_length=1, max_length=255)
    scenario_id: str | None = None
    verdict: ParityVerdict
    narrative: str = Field(min_length=1, max_length=2048)
    raw_evidence_locator: str | None = None
    fields: tuple[ParityFieldComparison, ...] = ()


class RentaWebOpenReplayParityReport(ReplayCorpusModel):
    """Every Renta WEB Open capture, replayed through the parity oracle.

    ``registry_validated`` records whether the cross-reference declaration
    behind :attr:`guard_policy_id` came from a fully validated registry or from
    a governance-grade tree read. A report must never be mistaken for validated
    authority when it was not.
    """

    corpus: ExternalOracleCorpus
    oracle_id: OracleId
    cross_reference_id: CrossReferenceId
    guard_policy_id: str
    registry_validated: bool
    payloads: tuple[ReplayPayloadParity, ...]

    @property
    def verdict(self) -> ParityVerdict:
        """Collapse the per-payload verdicts into one, worst outcome first.

        ``blocked`` outranks ``mismatch``, which outranks ``unverifiable``: a
        run the guard refused proved nothing about the figures, and a
        disagreement is a stronger signal than an unobserved field. An empty
        corpus is ``unverifiable`` rather than ``match``, because nothing was
        compared.

        Returns:
            The aggregate :class:`ParityVerdict` across every replayed capture.
        """
        verdicts = {payload.verdict for payload in self.payloads}
        if ParityVerdictKind.BLOCKED in verdicts:
            return ParityVerdictKind.BLOCKED
        if ParityVerdictKind.MISMATCH in verdicts:
            return ParityVerdictKind.MISMATCH
        if not self.payloads or ParityVerdictKind.UNVERIFIABLE in verdicts:
            return ParityVerdictKind.UNVERIFIABLE
        return ParityVerdictKind.MATCH

    def payload_count_of(self, verdict: ParityVerdict) -> int:
        """Count the captures whose overall outcome was ``verdict``.

        Returns:
            How many replayed captures carry exactly ``verdict``.
        """
        return sum(1 for payload in self.payloads if payload.verdict == verdict)

    def compared_field_count(self) -> int:
        """Count every per-casilla comparison the fold actually performed.

        Returns:
            The total number of :class:`ParityFieldComparison` rows across
            every capture, which is the fold's anti-vacuity floor: a report
            with no comparisons proves nothing regardless of its verdict.
        """
        return sum(len(payload.fields) for payload in self.payloads)


def replay_corpus_directory() -> Path:
    """Return the repository directory holding the Renta WEB Open captures.

    The captures are repository artefacts, not packaged data, so the location
    is resolved from this module's own position rather than through the
    bundled-resource loader. An absent directory is raised, never tolerated: an
    empty corpus and a corpus that verified clean produce the same report, so a
    silent fallback would read as "nothing to check" while the parity signal
    had in fact disappeared.

    Returns:
        The ``parity_replays/renta_web_open`` directory beside this module.

    Raises:
        RegistryValidationError: When the capture directory does not exist.
    """
    directory = Path(__file__).resolve().parent.joinpath(*_REPLAY_CORPUS_PARTS)
    if not directory.is_dir():
        raise RegistryValidationError(
            f"Renta WEB Open replay capture directory is missing: {directory}. "
            "The captures are repository-only development artefacts; without them the replay "
            "parity signal cannot be produced and must not be reported as clean."
        )
    return directory


def replay_corpus_payload_paths(directory: Path | None = None) -> tuple[Path, ...]:
    """Discover the replay captures under ``directory``, newest-name-last.

    Args:
        directory: Corpus directory to scan; defaults to the repository corpus.

    Returns:
        The discovered capture paths in deterministic order.
    """
    return scan_directory(directory or replay_corpus_directory(), pattern=_REPLAY_PAYLOAD_PATTERN)


def resolve_replay_cross_reference(
    modelos: Iterable[ModeloDefinition],
    *,
    oracle_id: OracleId,
) -> LiveCrossReferenceDecision:
    """Find the one registry cross-reference the Renta WEB Open oracle answers for.

    The declaration is the authority for the guard policy, so exactly one must
    match. Zero matches means the oracle has no registry standing; several mean
    the registry is ambiguous about which guard governs it. Both are refusals
    rather than a pick.

    Args:
        modelos: Compiled modelo definitions to search.
        oracle_id: The oracle whose cross-reference is wanted.

    Returns:
        The single matching :class:`LiveCrossReferenceDecision`.

    Raises:
        RegistryValidationError: When no declaration, or more than one, matches.
    """
    matches = [
        decision
        for modelo in modelos
        for revision in modelo.revisions.values()
        for decision in revision.live_cross_references
        if decision.id == oracle_id
    ]
    if len(matches) != 1:
        if not matches:
            detail = "no declaration matches"
        elif len({decision.guard_policy_id for decision in matches}) > 1:
            detail = f"conflicting guard policies {sorted({decision.guard_policy_id for decision in matches})!r}"
        else:
            detail = "duplicate declarations name the same guard policy"
        raise RegistryValidationError(
            f"registry must declare exactly one live_cross_references entry for oracle {oracle_id!r}; "
            f"found {len(matches)}: {detail}",
        )
    return matches[0]


def _expected_values(payload: RentaWebOpenReplayPayload) -> Mapping[CasillaId, str]:
    if not payload.expected_by_casilla_id:
        raise RegistryValidationError(
            "Renta WEB Open replay capture declares no expected_by_casilla_id, so it asserts nothing",
        )
    return payload.expected_by_casilla_id


def _payload_parity(
    oracle: RentaWebOpenOracle,
    policy: RemoteStateGuardPolicy,
    payload_path: Path,
) -> ReplayPayloadParity:
    raw = payload_path.read_bytes()
    capture = RentaWebOpenReplayPayload.model_validate_json(raw)
    result: ParityResult = oracle.verify_payload(policy, raw, expected=dict(_expected_values(capture)))
    return ReplayPayloadParity(
        payload_name=payload_path.name,
        scenario_id=capture.scenario_id,
        verdict=result.verdict,
        narrative=result.narrative,
        raw_evidence_locator=result.raw_evidence_locator,
        fields=result.fields,
    )


def build_renta_web_open_replay_parity(
    modelos: Iterable[ModeloDefinition],
    *,
    payload_paths: Sequence[Path] | None = None,
    registry_validated: bool,
) -> RentaWebOpenReplayParityReport:
    """Replay every capture through the oracle under the declared guard.

    Args:
        modelos: Compiled modelo definitions carrying the cross-reference
            declaration that supplies the guard policy.
        payload_paths: Captures to replay; defaults to the repository corpus.
        registry_validated: Whether ``modelos`` came from a validated authority.
            Stamped onto the report so a governance read is never mistaken for
            validated authority.

    Returns:
        The :class:`RentaWebOpenReplayParityReport` for the replayed captures.
    """
    oracle = RentaWebOpenOracle(driver=RentaWebOpenReplayDriver())
    decision = resolve_replay_cross_reference(modelos, oracle_id=oracle.oracle_id)
    policy = remote_state_policy_from_cross_reference(decision)
    paths = tuple(payload_paths) if payload_paths is not None else replay_corpus_payload_paths()
    return RentaWebOpenReplayParityReport(
        corpus=ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY,
        oracle_id=oracle.oracle_id,
        cross_reference_id=decision.id,
        guard_policy_id=decision.guard_policy_id,
        registry_validated=registry_validated,
        payloads=tuple(_payload_parity(oracle, policy, path) for path in paths),
    )


def verify_bundled_renta_web_open_replays() -> RentaWebOpenReplayParityReport:
    """Replay the repository capture corpus against the bundled registry.

    A development convenience path. It enters through the canonical bundled
    authority and validates its complete registry before examining the
    cross-reference that authorises the replay. The report is offline
    development evidence only: replaying a capture neither contacts AEAT, nor
    certifies a filing result, nor is reachable from an installed Cadrumo.

    Returns:
        The :class:`RentaWebOpenReplayParityReport` for the repository corpus.
    """
    authority = bundled_authority()
    authority.validate_registry()
    return build_renta_web_open_replay_parity(authority.modelos, registry_validated=True)


__all__ = [
    "RentaWebOpenReplayParityReport",
    "ReplayPayloadParity",
    "build_renta_web_open_replay_parity",
    "replay_corpus_directory",
    "replay_corpus_payload_paths",
    "resolve_replay_cross_reference",
    "verify_bundled_renta_web_open_replays",
]
