"""Boundary gate: every bundled oracle payload is parsed through a strict model.

The grounding fold assigns each payload's corpus from the directory it was
found in. That assignment travels onto
:attr:`RevisionExternalGroundingRow.evidence_corpora` as the provenance of the
figures, so it has to be checked against what the payload itself declares — a
directory-only read would silently reclassify a payload declaring the other
corpus, and report a provenance the figures do not have.

This module holds two things at once: that every payload actually on disk
satisfies its corpus's strict model (so the boundary is not enforced by
refusing real data), and that each way of breaching it is a loud refusal rather
than a tolerated shape. Every refusal case is built by mutating ONE field of a
real bundled payload and is paired with the unmutated original loading cleanly,
so a refusal can never be produced by a fixture that was broken to begin with.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....core import ExternalOracleCorpus
from .....core.resources import bundled_path
from .._errors import RegistryValidationError
from .._external_grounding import (
    _ORACLE_CORPUS_DIRECTORIES,
    _ORACLE_PAYLOAD_MODELS,
    ExternalOracleEvidence,
    ManualWorkedExamplePayload,
    RentaWebOpenReplayPayload,
    _parse_oracle_payload,
    _read_oracle_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _bundled_payloads(corpus: ExternalOracleCorpus) -> list[Path]:
    """Return every bundled payload of ``corpus``, read the way the fold reads them."""
    return sorted(Path(bundled_path(*_ORACLE_CORPUS_DIRECTORIES[corpus])).glob("modelo-*.json"))


def _stage(tmp_path: Path, corpus: ExternalOracleCorpus, source: Path, payload: object) -> Path:
    """Write ``payload`` into a tmp copy of ``corpus``'s directory, under ``source``'s name.

    The staged directory carries the real corpus subtree's own leaf name, so
    the refusal diagnostics quote the same directory an operator would see.
    """
    directory = tmp_path.joinpath(*_ORACLE_CORPUS_DIRECTORIES[corpus])
    directory.mkdir(parents=True, exist_ok=True)
    staged = directory / source.name
    staged.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return staged


def test_every_bundled_payload_satisfies_its_corpus_strict_model() -> None:
    """The strict boundary accepts the whole shipped corpus, both directories.

    The anti-vacuity floor for every refusal below: a model that refused real
    payloads would make the refusal tests pass for the wrong reason.
    """
    parsed_by_corpus = {
        corpus: [_parse_oracle_payload(corpus, path) for path in _bundled_payloads(corpus)]
        for corpus in _ORACLE_CORPUS_DIRECTORIES
    }

    for corpus, parsed in parsed_by_corpus.items():
        assert parsed, f"no bundled payloads were discovered for the {corpus.value} corpus"
        assert all(isinstance(item, _ORACLE_PAYLOAD_MODELS[corpus]) for item in parsed)
        assert all(item.expected_by_casilla_id for item in parsed), (
            f"a {corpus.value} payload carries no expected_by_casilla_id figures at all"
        )


def test_the_manual_corpus_declares_the_token_the_cross_check_verifies() -> None:
    """The corpus cross-check is not vacuous: the manual payloads all state a token.

    A cross-check against a field nothing populates would pass on an empty
    premise. Every manual worked-example payload declares ``source_kind``, and
    it hydrates to the member of the directory holding it.
    """
    manual = [
        _parse_oracle_payload(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE, path)
        for path in _bundled_payloads(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE)
    ]

    assert manual, "no manual worked-example payloads were discovered"
    assert all(item.source_kind is ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE for item in manual)


def test_the_replay_corpus_declares_no_token_and_is_modelled_as_such() -> None:
    """The replay payloads state no corpus, modelo, or filing year, and are not required to.

    Pinned so the optional axes on :class:`RentaWebOpenReplayPayload` stay an
    honest model of what this corpus stores rather than drifting into a default
    that would answer the cross-check on the payload's behalf.
    """
    replays = [
        _parse_oracle_payload(ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY, path)
        for path in _bundled_payloads(ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY)
    ]

    assert replays, "no Renta WEB Open replay payloads were discovered"
    assert all(item.source_kind is None for item in replays)
    assert all(item.modelo is None and item.filing_year is None for item in replays)


def test_a_declared_corpus_contradicting_its_directory_is_refused(tmp_path: Path) -> None:
    """A manual payload declaring the replay corpus refuses, naming token and directory.

    This is the silent reclassification the directory-keyed read allowed: the
    payload claims one provenance, the directory implies another, and the fold
    used to take the directory's word for it.
    """
    source = _bundled_payloads(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE)[0]
    original = json.loads(source.read_text(encoding="utf-8"))

    control = _stage(tmp_path / "control", ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE, source, original)
    loaded = _read_oracle_payload(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE, control)
    assert isinstance(loaded, ExternalOracleEvidence)
    assert loaded.corpus is ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE

    contradicting = _stage(
        tmp_path / "mutated",
        ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE,
        source,
        {**original, "source_kind": ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY.value},
    )
    with pytest.raises(RegistryValidationError) as caught:
        _read_oracle_payload(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE, contradicting)

    message = str(caught.value)
    assert ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY.value in message
    assert ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE.value in message
    assert contradicting.parent.name in message


def test_a_replay_declaring_the_manual_corpus_is_refused(tmp_path: Path) -> None:
    """The cross-check binds the corpus whose token is optional, too.

    An optional field is where a check quietly stops applying. A replay payload
    that grows a ``source_kind`` naming the other corpus must refuse on the
    same terms as a manual one.
    """
    source = _bundled_payloads(ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY)[0]
    original = json.loads(source.read_text(encoding="utf-8"))

    control = _stage(tmp_path / "control", ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY, source, original)
    assert _parse_oracle_payload(ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY, control).source_kind is None

    contradicting = _stage(
        tmp_path / "mutated",
        ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY,
        source,
        {**original, "source_kind": ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE.value},
    )
    with pytest.raises(RegistryValidationError) as caught:
        _read_oracle_payload(ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY, contradicting)

    assert ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE.value in str(caught.value)
    assert contradicting.parent.name in str(caught.value)


def test_an_unrecognised_source_kind_token_is_refused_with_the_accepted_set(tmp_path: Path) -> None:
    """An unknown token refuses at hydration and the message enumerates what is accepted."""
    source = _bundled_payloads(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE)[0]
    original = json.loads(source.read_text(encoding="utf-8"))

    staged = _stage(
        tmp_path,
        ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE,
        source,
        {**original, "source_kind": "hand_computed_by_the_author"},
    )
    with pytest.raises(RegistryValidationError) as caught:
        _read_oracle_payload(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE, staged)

    message = str(caught.value)
    assert "hand_computed_by_the_author" in message
    for member in ExternalOracleCorpus:
        assert member.value in message


def test_a_manual_payload_omitting_its_source_kind_is_refused(tmp_path: Path) -> None:
    """Omission is not an escape hatch from the corpus cross-check.

    If a missing token were tolerated on the corpus that declares one, every
    payload could opt out of the check by dropping the field.
    """
    source = _bundled_payloads(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE)[0]
    original = json.loads(source.read_text(encoding="utf-8"))
    assert "source_kind" in original

    staged = _stage(
        tmp_path,
        ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE,
        source,
        {key: value for key, value in original.items() if key != "source_kind"},
    )
    with pytest.raises(RegistryValidationError) as caught:
        _read_oracle_payload(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE, staged)

    assert "source_kind" in str(caught.value)


def test_an_undeclared_payload_key_is_refused(tmp_path: Path) -> None:
    """An unmodelled key refuses rather than being read past.

    The failure the untyped mapping read allowed: a key nothing consumes looks
    identical to a key the reader forgot, and both were silently dropped.
    """
    source = _bundled_payloads(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE)[0]
    original = json.loads(source.read_text(encoding="utf-8"))

    staged = _stage(
        tmp_path,
        ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE,
        source,
        {**original, "expected_by_casila_id": {"0226": "58100.00"}},
    )
    with pytest.raises(RegistryValidationError) as caught:
        _read_oracle_payload(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE, staged)

    assert "expected_by_casila_id" in str(caught.value)


def test_a_non_canonical_casilla_key_is_refused(tmp_path: Path) -> None:
    """Expected-value keys are canonical casilla ids, checked at the boundary.

    The keys become :attr:`ExternalOracleEvidence.casilla_ids` and are compared
    against declared registry casillas, so a display label entering here would
    read as an unmatched grounding claim rather than as a malformed payload.
    """
    source = _bundled_payloads(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE)[0]
    original = json.loads(source.read_text(encoding="utf-8"))

    staged = _stage(
        tmp_path,
        ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE,
        source,
        {**original, "expected_by_casilla_id": {"Rendimiento neto reducido": "58100.00"}},
    )
    with pytest.raises(RegistryValidationError) as caught:
        _read_oracle_payload(ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE, staged)

    assert "expected_by_casilla_id" in str(caught.value)


def test_the_payload_models_cover_every_corpus_directory() -> None:
    """Every corpus the fold walks has a strict model, so none is read untyped."""
    assert set(_ORACLE_PAYLOAD_MODELS) == set(_ORACLE_CORPUS_DIRECTORIES) == set(ExternalOracleCorpus)
    assert _ORACLE_PAYLOAD_MODELS[ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE] is ManualWorkedExamplePayload
    assert _ORACLE_PAYLOAD_MODELS[ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY] is RentaWebOpenReplayPayload
