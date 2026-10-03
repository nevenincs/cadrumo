"""Project the chosen run, notes and sign-offs against current frame identities."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from ._artifacts import DEFAULT_RUN_NAME
from ._review_catalogue import CatalogueFrame, ElementView, RunView, viewport_grid
from ._review_elements import ElementFamily, state_order
from ._review_network import _first_line
from ._review_state import ReviewState
from ._review_store import (
    Note,
    SignOff,
    image_state,
    sign_off_changes,
)


def state_payload(state: ReviewState, run_name: str | None) -> dict[str, object]:
    """Everything the page renders, for one run."""
    generation = state.generation
    runs = state.catalogue.runs()
    view = _choose_run(runs, run_name)
    frames = _frames_in_run(view)
    elements = _view_elements(view)
    frame_digests = {frame.key: frame.png_sha256 for frame in frames}
    latest = _latest_modified_ns(frames)
    return {
        "generation": generation,
        "runs": [{"name": run.name, "frames": len(run.frames), "elements": len(run.elements)} for run in runs],
        "run": None if view is None else view.name,
        "frames": _view_frame_payloads(view, frames),
        "elements": [_element_payload(element) for element in elements.values()],
        "states": _state_listing(tuple(elements.values())),
        "latest_frame_at": None if latest is None else _iso(latest),
        "manifest": None if view is None else _manifest_payload(view),
        "unrecognised": [] if view is None else list(view.unrecognised),
        "notes": [_note_payload(note, elements, frame_digests) for note in state.store.notes()],
        "sign_offs": {key: _sign_off_payload(mark, elements.get(key)) for key, mark in state.store.sign_offs().items()},
        "store": str(state.store.path),
    }


def _state_listing(elements: tuple[ElementView, ...]) -> list[dict[str, str]]:
    """Every state some element is shown in, by family and then in each family's own order."""
    families = list(ElementFamily)
    seen = {(element.family, state) for element in elements for state in element.states if state is not None}
    ordered = sorted(seen, key=lambda item: (families.index(item[0]), state_order(item[0], item[1])))
    return [{"family": str(family), "state": state} for family, state in ordered]


def _digest_of(element: ElementView | None) -> str | None:
    return None if element is None else element.digest


def _element_payload(element: ElementView) -> dict[str, object]:
    return {
        "key": element.key,
        "family": str(element.family),
        "name": element.name,
        "states": list(element.states),
        "frames": [frame.stem for frame in element.frames],
        "digest": element.digest,
        "modified_at": _iso(element.latest_modified_ns),
    }


def _sign_off_payload(mark: SignOff, element: ElementView | None) -> dict[str, object]:
    """A sign-off, and which of the element's frames have moved since it was given."""
    changes = sign_off_changes(mark, {} if element is None else element.frame_digests)
    return {
        "run": mark.run,
        "reviewed_at": mark.reviewed_at,
        "current": changes.unchanged,
        "changed": list(changes.changed),
        "added": list(changes.added),
        "removed": list(changes.removed),
    }


def _choose_run(runs: tuple[RunView, ...], name: str | None) -> RunView | None:
    by_name = {run.name: run for run in runs}
    if name is not None and name in by_name:
        return by_name[name]
    if DEFAULT_RUN_NAME in by_name:
        return by_name[DEFAULT_RUN_NAME]
    return runs[0] if runs else None


def _frame_payload(view: RunView, frame: CatalogueFrame) -> dict[str, object]:
    columns, rows, orientation = viewport_grid(frame.identity.viewport)
    record = view.recorded(frame)
    parts = frame.identity.parts
    return {
        "stem": frame.stem,
        "key": frame.key,
        "surface": frame.identity.surface,
        "element": parts.element,
        "state": parts.state,
        "viewport": str(frame.identity.viewport),
        "theme": str(frame.identity.theme),
        "columns": columns,
        "rows": rows,
        "orientation": orientation,
        "digest": frame.png_sha256,
        "width": frame.width,
        "height": frame.height,
        "bytes": frame.size,
        "modified_at": _iso(frame.modified_ns),
        "text": frame.stem in view.texts,
        "recorded": None
        if record is None
        else {
            "geometry_findings": list(record.geometry_findings),
            "missing_glyphs": list(record.missing_glyphs),
            "elapsed_ms": record.elapsed_ms,
            "sequence": None if record.sequence is None else record.sequence.model_dump(mode="json"),
        },
    }


def _manifest_payload(view: RunView) -> dict[str, object]:
    if view.manifest_error is not None:
        return {"state": "unreadable", "detail": view.manifest_error}
    manifest = view.manifest
    if manifest is None:
        return {"state": "absent"}
    described = len(view.records)
    coherent = described == len(view.frames) == len(manifest.frames)
    return {
        "state": "current" if coherent else "earlier",
        "generated_at": manifest.generated_at,
        "described": described,
        "recorded_frames": len(manifest.frames),
        "spans_a_source_change": manifest.spans_a_source_change,
        "blocked_surfaces": list(manifest.blocked_surfaces),
        "failures": [
            {
                "key": failure.key,
                "kind": str(failure.kind),
                "attempts": failure.attempts,
                "reason": _first_line(failure.detail),
            }
            for failure in manifest.failures
        ],
        "skipped": [{"key": entry.key, "reason": entry.reason} for entry in manifest.skipped],
    }


def _iso(modified_ns: int) -> str:
    return datetime.fromtimestamp(modified_ns / 1e9, tz=UTC).isoformat(timespec="seconds")


def _view_elements(view: RunView | None) -> dict[str, ElementView]:
    """Index only the chosen run's immutable element projections."""
    return {element.key: element for element in (view.elements if view is not None else ())}


def _frames_in_run(view: RunView | None) -> tuple[CatalogueFrame, ...]:
    """Return the selected run's frames or the empty-run projection."""
    return view.frames if view is not None else ()


def _latest_modified_ns(frames: tuple[CatalogueFrame, ...]) -> int | None:
    """Read the newest frame timestamp before serializing the chosen run."""
    return max((frame.modified_ns for frame in frames), default=None)


def _view_frame_payloads(view: RunView | None, frames: tuple[CatalogueFrame, ...]) -> list[dict[str, object]]:
    """Project each chosen-run frame only when that run exists."""
    return [] if view is None else [_frame_payload(view, frame) for frame in frames]


def _note_payload(note: Note, elements: dict[str, ElementView], frame_digests: dict[str, str]) -> dict[str, object]:
    """Bind each stored note to the current element and optional frame identities."""
    payload = {
        **note.model_dump(mode="json"),
        "element_state": str(
            image_state(note.element_sha256, _digest_of(elements.get(note.element_key))),
        ),
        "frame_state": None
        if note.frame_key is None or note.frame_sha256 is None
        else str(image_state(note.frame_sha256, frame_digests.get(note.frame_key))),
    }
    # Note.model_dump has declared string field names; the extra keys are literals.
    return cast("dict[str, object]", payload)
