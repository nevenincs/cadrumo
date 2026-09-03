"""Offline parity fold over the bundled Renta WEB Open replay corpus.

The Renta WEB Open oracle compares a set of expected Modelo 100 figures
against the figures AEAT's own public simulator produced. Five captures ship
inside the wheel under ``corpus/parity_replays/renta_web_open``, one per
autonomous community whose ``minimo personal y familiar`` diverges from the
state scale. Until this module existed the comparison engine had no shipped
consumer at all: the captures shipped, the coverage metric counted them, and
nothing ran them outside the test tree.

This fold is the shipped runner. It is deliberately OFFLINE: every payload is
decoded by :class:`RentaWebOpenReplayDriver`, whose only planned operation is a
local parse, and the remote-state guard authorises that plan before any
comparison happens. No AEAT contact occurs on this path, and none may be added
to it -- the live browser driver is a separate, operator-initiated surface.

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

from ....core.casilla_id import CasillaId
from ....core.directory_scan import scan_directory
from ....core.external_oracle_corpus import ExternalOracleCorpus
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.resources.bundled_data import bundled_path
from .authority import bundled_authority
from .errors import RegistryValidationError
from .external_grounding import RentaWebOpenReplayPayload
from .ids import CrossReferenceId, OracleId
from .live_parity import ParityFieldComparison, ParityResult, ParityVerdict, ParityVerdictKind
from .remote_state_guard import RemoteStateGuardPolicy, remote_state_policy_from_cross_reference
from .renta_web_open_oracle import RentaWebOpenOracle, RentaWebOpenReplayDriver
from .schema import ModeloDefinition
from .schema_verification import LiveCrossReferenceDecision

#: Bundled data subtree holding the Renta WEB Open replay captures.
_REPLAY_CORPUS_PARTS: Final[tuple[str, ...]] = ("corpus", "parity_replays", "renta_web_open")

#: The capture filenames the corpus publishes, matching the grounding inventory's glob.
_REPLAY_PAYLOAD_PATTERN: Final[str] = "modelo-*.json"


class ReplayCorpusModel(BaseModel):
    """Strict frozen base for replay-corpus parity facts."""

    model_config = STRICT_FROZEN_CONFIG


class ReplayPayloadParity(ReplayCorpusModel):
    """One bundled capture's parity outcome, with its per-casilla comparisons."""

    payload_name: str = Field(min_length=1, max_length=255)
    scenario_id: str | None = None
    verdict: ParityVerdict
    narrative: str = Field(min_length=1, max_length=2048)
    raw_evidence_locator: str | None = None
    fields: tuple[ParityFieldComparison, ...] = ()


class RentaWebOpenReplayParityReport(ReplayCorpusModel):
    """Every bundled Renta WEB Open capture, replayed through the parity oracle.

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
    """Return the bundled directory holding the Renta WEB Open captures.

    Returns:
        The packaged ``corpus/parity_replays/renta_web_open`` path.
    """
    return Path(bundled_path(*_REPLAY_CORPUS_PARTS))


def replay_corpus_payload_paths(directory: Path | None = None) -> tuple[Path, ...]:
    """Discover the replay captures under ``directory``, newest-name-last.

    Args:
        directory: Corpus directory to scan; defaults to the bundled corpus.

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
    if not matches:
        raise RegistryValidationError(
            f"no registry live_cross_references declaration matches oracle {oracle_id!r}; "
            "the replay corpus cannot be run without the guard policy it declares",
        )
    if len({decision.guard_policy_id for decision in matches}) > 1:
        raise RegistryValidationError(
            f"registry declares conflicting guard policies for oracle {oracle_id!r}: "
            f"{sorted({decision.guard_policy_id for decision in matches})}",
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
    """Replay every bundled capture through the oracle under the declared guard.

    Args:
        modelos: Compiled modelo definitions carrying the cross-reference
            declaration that supplies the guard policy.
        payload_paths: Captures to replay; defaults to the bundled corpus.
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
    """Replay the bundled Renta WEB Open corpus against the bundled registry.

    This product convenience path enters through the canonical bundled
    authority and validates its complete registry before examining the
    cross-reference that authorises the replay. The report is offline evidence
    only: replaying a bundled capture neither contacts AEAT nor certifies a
    filing result.

    Returns:
        The :class:`RentaWebOpenReplayParityReport` for the bundled corpus.
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
