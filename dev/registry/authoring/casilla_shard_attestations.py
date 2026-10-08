"""Preservation and refusal checks for authored casilla attestations."""

from __future__ import annotations

from pathlib import Path

from .casilla_shard_toml_text import _KEY_LINE, _NL
from .casilla_shard_types import GenerationRefusedError, GenerationReport


def _source_lines(data: bytes) -> list[str]:
    """Decode a shard and split it, tolerating either line-ending style."""
    return data.decode("utf-8").replace(chr(13) + _NL, _NL).split(_NL)


def harvest_attestations(out_dir: Path, revision_id: str) -> dict[str, tuple[str, list[str]]]:
    """Every key line a later pass added to rows this generator already wrote.

    The generator emits eight fields. Anything else on a row on disk was put there
    by somebody else -- ``continuidad_id`` with its origin and evidence,
    ``semantic_role`` with its cardinality. Those are attestations: a person or a
    seeder asserting something this generator cannot re-derive. A re-run that
    simply re-emits its own eight fields deletes them and reports nothing, because
    from here the output looks exactly as it did the first time. On 2026-09-12 that
    was 423 stamps on modelo 036, 54 on 280 and 6 on 220.

    Harvest is keyed by casilla id and scans the WHOLE directory rather than the
    file a row is expected in, because a shard is named for its first and last
    casilla and a row that gains a neighbour moves file. The file a row was found
    in is returned with it, because whether losing the row matters depends on
    whether this run overwrites that file.
    """
    harvested: dict[str, tuple[str, list[str]]] = {}
    marker = f'[[revisions."{revision_id}".casillas]]'
    if not out_dir.is_dir():
        return harvested
    for path in sorted(out_dir.glob("*.toml")):
        current: list[str] = []
        casilla_id: str | None = None
        for line in _source_lines(path.read_bytes()):
            if line.strip() == marker:
                if casilla_id:
                    harvested[casilla_id] = (path.name, current)
                current = []
                casilla_id = None
                continue
            if line.startswith("id = "):
                casilla_id = line.split("=", 1)[1].strip().strip('"')
                continue
            if _KEY_LINE.match(line):
                current.append(line)
        if casilla_id:
            harvested[casilla_id] = (path.name, current)
    return harvested


def reattach_attestations(body: str, harvested: dict[str, tuple[str, list[str]]], revision_id: str) -> tuple[str, int]:
    """Carry every attested field forward onto the row it was made about.

    A field the emission already produces is never overwritten: the generator is
    the authority for its own eight, the attestation for everything else.
    """
    marker = f'[[revisions."{revision_id}".casillas]]'
    out: list[str] = []
    block: list[str] = []
    casilla_id: str | None = None
    carried = 0
    for line in body.split(_NL):
        if line.strip() == marker:
            restored, count = _restore_attestation_block(block, casilla_id, harvested)
            out.extend(restored)
            carried += count
            block = [line]
            casilla_id = None
            continue
        if block:
            if line.startswith("id = "):
                casilla_id = line.split("=", 1)[1].strip().strip('"')
                block.append(line)
                continue
            if _KEY_LINE.match(line):
                block.append(line)
                continue
            restored, count = _restore_attestation_block(block, casilla_id, harvested)
            out.extend(restored)
            carried += count
            block.clear()
            casilla_id = None
        out.append(line)
    restored, count = _restore_attestation_block(block, casilla_id, harvested)
    out.extend(restored)
    carried += count
    return _NL.join(out), carried


def _restore_attestation_block(
    block: list[str],
    casilla_id: str | None,
    harvested: dict[str, tuple[str, list[str]]],
) -> tuple[list[str], int]:
    if casilla_id is None:
        return block, 0
    emitted = {match.group(1) for line in block if (match := _KEY_LINE.match(line))}
    carried = 0
    for line in harvested.get(casilla_id, ("", []))[1]:
        key_match = _KEY_LINE.match(line)
        if key_match is None:
            raise GenerationRefusedError(f"attestation line is not a key line: {line!r}")
        key = key_match.group(1)
        if key not in emitted:
            block.append(line)
            carried += 1
    return block, carried


def refuse_dropped_attestations(
    harvested: dict[str, tuple[str, list[str]]],
    emitted: set[str],
    overwritten: set[str],
) -> None:
    """Refuse when a shard this run rewrites holds an attested row it will not re-emit.

    Preservation only helps a row the emission still produces. A row that has been
    attested, lives in a file this run overwrites, and is no longer emitted --
    because the scope narrowed, the grammar changed, or a number moved into the
    declined set -- would lose its attestation with nothing to carry it onto.

    A row in a shard this run does not write is NOT at risk and must not refuse:
    modelo 220's two declaration headers live in their own shard that the
    money-closure wave never touches, and refusing on them would have blocked a
    generator that was never going to harm them.
    """
    orphaned = sorted(
        casilla_id
        for casilla_id, (source, lines) in harvested.items()
        if lines and casilla_id not in emitted and source in overwritten
    )
    if not orphaned:
        return
    raise GenerationRefusedError(
        f"{len(orphaned)} attested row(s) sit in a shard this run rewrites and "
        f"would not be re-emitted: {', '.join(orphaned[:5])}"
        f"{' ...' if len(orphaned) > 5 else ''}. They carry fields this generator "
        "does not produce (continuidad or semantic_role), so re-emitting without "
        "them destroys work that cannot be re-derived here. Restore the rows to "
        "scope, or move the attestations, before running again."
    )


def emitted_ids(report: GenerationReport) -> list[str]:
    """Every casilla id this run would write, in emission order."""
    return [
        block.split('id = "')[1].split('"')[0]
        for outcome in report.outcomes
        for block in outcome.body.split("[[revisions.")[1:]
    ]


def _refuse_duplicate_ids(report: GenerationReport) -> None:
    """Refuse before writing when two casillas would share an id."""
    seen: dict[str, int] = {}
    for casilla_id in emitted_ids(report):
        seen[casilla_id] = seen.get(casilla_id, 0) + 1
    duplicates = {key: count for key, count in seen.items() if count > 1}
    if not duplicates:
        return
    worst = sorted(duplicates.items(), key=lambda kv: -kv[1])[:5]
    detail = ", ".join(f"{key} x{count}" for key, count in worst)
    raise GenerationRefusedError(
        f"{len(duplicates)} casilla id(s) would be written more than once "
        f"({sum(duplicates.values())} rows): {detail}. An id must be unique across the "
        "whole edition. A duplicate serialises into valid TOML and is caught only when "
        "the modelo is loaded, which is after the files are on disk -- so it is refused "
        "here, before anything is written."
    )
