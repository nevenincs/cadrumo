"""Prior shard attribute loading for lossless casilla authoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .casilla_shard_types import GenerationRefusedError


def load_prior_attributes(
    directory: Path, segmento: str, glob: str = "c{segmento}+*.toml"
) -> dict[str, dict[str, str]]:
    """Read adjudicated attributes and the transcribed caption from an edition."""
    attributes: dict[str, dict[str, str]] = {}
    for path in sorted(directory.glob(glob.format(segmento=segmento))):
        file_attributes = _read_prior_file(path)
        for number, row_attributes in file_attributes.items():
            attributes[number] = row_attributes
    return attributes


@dataclass(slots=True)
class _PriorFileState:
    attributes: dict[str, dict[str, str]] = field(default_factory=dict)
    current: dict[str, str] = field(default_factory=dict)
    number: str | None = None
    pending: str = ""
    collecting_legal_refs: list[str] | None = None
    collecting_section: list[str] | None = None


def _read_prior_file(path: Path) -> dict[str, dict[str, str]]:
    state = _PriorFileState()
    for raw in path.read_text(encoding="utf-8").split("\n"):
        _read_prior_line(path, raw.strip(), state)
    if state.number:
        state.attributes[state.number] = state.current
    return state.attributes


def _read_prior_line(path: Path, line: str, state: _PriorFileState) -> None:
    if line.startswith("# @"):
        state.pending = line
    elif line.startswith("[[revisions."):
        _begin_prior_row(path, state)
    elif line.startswith("number = "):
        state.number = line.split("=", 1)[1].strip().strip('"')
    elif line.startswith(("id = ", "segmento = ")):
        key, value = line.split("=", 1)
        state.current[key.strip()] = value.strip().strip('"')
    elif line.startswith("legal_refs = "):
        _start_legal_refs(line, state)
    elif _continue_legal_refs(line, state) or _start_section_or_type(line, state):
        return
    elif state.collecting_section is not None:
        _continue_section(line, state)


def _begin_prior_row(path: Path, state: _PriorFileState) -> None:
    open_array = (
        "legal_refs"
        if state.collecting_legal_refs is not None
        else "section"
        if state.collecting_section is not None
        else None
    )
    if open_array is not None:
        # An array that never closed leaves the field unset and the row takes the
        # wave default without a word. Refuse it with the affected prior row.
        raise GenerationRefusedError(f"{path.name}: {open_array} array for casilla {state.number!r} is never closed")
    if state.number:
        state.attributes[state.number] = state.current
    state.current, state.number = {"_caption": state.pending}, None
    state.collecting_legal_refs = None
    state.collecting_section = None


def _start_legal_refs(line: str, state: _PriorFileState) -> None:
    value = line.split("=", 1)[1].strip()
    if value.endswith("]"):
        state.current["legal_refs"] = value
    else:
        state.collecting_legal_refs = [value]


def _continue_legal_refs(line: str, state: _PriorFileState) -> bool:
    if state.collecting_legal_refs is None:
        return False
    state.collecting_legal_refs.append(line.strip())
    if line.rstrip().endswith("]"):
        state.current["legal_refs"] = " ".join(state.collecting_legal_refs)
        state.collecting_legal_refs = None
    return True


def _start_section_or_type(line: str, state: _PriorFileState) -> bool:
    if not line.startswith(("section = ", "data_type = ")):
        return False
    key, value = line.split("=", 1)
    key, value = key.strip(), value.strip()
    if key == "section" and not value.endswith("]"):
        state.collecting_section = [value]
    else:
        state.current[key] = value
    return True


def _continue_section(line: str, state: _PriorFileState) -> None:
    collecting = state.collecting_section
    if collecting is None:
        return
    collecting.append(line.strip())
    if line.rstrip().endswith("]"):
        state.current["section"] = " ".join(collecting)
        state.collecting_section = None
