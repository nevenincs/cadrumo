"""Typed casilla row rendering and shard filename derivation."""

from __future__ import annotations

from collections.abc import Sequence

from dev.registry.compiler.record_design_schema import (
    RecordDesignField,
)

from .casilla_shard_design import group_comment


def _render_row(
    *,
    members: Sequence[RecordDesignField],
    revision_id: str,
    segmento: str | None,
    casilla_id: str,
    number: str,
    row: RecordDesignField,
    caption: str,
    section: str,
    data_type: str,
    legal_refs: str,
) -> str:
    segmento_line = f'segmento = "{segmento}"\n' if segmento else ""
    return (
        f"{group_comment(members, caption)}\n"
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        f"{segmento_line}"
        f"section = {section}\n"
        f"data_type = {data_type}\n"
        f"required = false\n"
        f'input_kind = "manual"\n'
        f"legal_refs = {legal_refs}\n"
    )


def _filename_stem(block: str) -> str:
    """The part of a rendered row's id that names it inside its file.

    Record-oriented ids are ``<SEGMENTO>:<number>`` and the segmento is already
    in the filename, so only the tail is repeated. A slug id -- modelo 036's
    ``pf.identificacion-residencia-indicador`` -- has no colon at all, and
    splitting on one raised IndexError rather than producing a wrong name, which
    is the better of the two failures but still a failure.
    """
    casilla_id = block.split('id = "')[1].split('"')[0]
    _, separator, tail = casilla_id.partition(":")
    return tail if separator else casilla_id
