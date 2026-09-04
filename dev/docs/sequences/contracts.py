"""Private authoring contracts for reader-facing CLI sequence cards.

User documentation declares only the sequence id and its reader-facing
verification sentence.  Execution scaffolding, captures, assertions, static
classification, and optional seed/shell settings live in keyed ``.seq`` files
under ``docs/_sequences/contracts/<page>/<sequence-id>.seq``.
"""

from __future__ import annotations

import ntpath
import re
from pathlib import Path, PurePosixPath

from ..._paths import UTF_8
from .errors import SequenceEngineError

__all__ = ["read_sequence_contract", "sequence_contract_path"]

_UTF_8 = UTF_8
_OPTION_RE = re.compile(r"^:(?P<key>[a-z][a-z0-9-]*):\s*(?P<value>.*)$")
_SEQUENCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PRIVATE_OPTION_KEYS = frozenset({"seed", "shells"})


def sequence_contract_path(
    page: str,
    sequence_id: str,
    *,
    docs_root: Path,
    contracts_root: Path | None = None,
) -> Path:
    """Return the private contract path for one page-keyed sequence.

    The docname is POSIX-shaped and comes from a page, so it is validated
    segment by segment and the result is confirmed to land inside the
    contracts root. Splitting on ``/`` alone was not enough on Windows: a
    backslash kept the whole docname in ONE segment, so ``..`` inside it
    never met the check, and a UNC or drive-qualified segment made
    ``joinpath`` discard the root before it entirely.
    """
    if chr(92) in page:
        raise SequenceEngineError(f"a docname is POSIX-shaped and cannot contain a backslash: {page!r}")
    page_parts = tuple(page.split("/"))
    if not page_parts or any(part in {"", ".", ".."} for part in page_parts):
        raise SequenceEngineError(f"invalid docname for a private sequence contract: {page!r}")
    if any(PurePosixPath(part).is_absolute() or ntpath.splitdrive(part)[0] for part in page_parts):
        raise SequenceEngineError(f"a docname segment cannot be absolute or drive-qualified: {page!r}")
    if _SEQUENCE_ID_RE.fullmatch(sequence_id) is None:
        raise SequenceEngineError(f"invalid sequence id for a private sequence contract: {sequence_id!r}")
    root = contracts_root if contracts_root is not None else docs_root / "_sequences" / "contracts"
    resolved = root.joinpath(*page_parts, f"{sequence_id}.seq")
    # Backstop rather than a second guard: whatever the segments looked like,
    # a contract that resolves outside its own root is not this page's.
    if not resolved.resolve().is_relative_to(root.resolve()):
        raise SequenceEngineError(f"private sequence contract escapes its contracts root: {page!r}")
    return resolved


def read_sequence_contract(
    page: str,
    sequence_id: str,
    *,
    docs_root: Path,
    contracts_root: Path | None = None,
) -> tuple[dict[str, str | None], str]:
    """Read one private contract and split its private options from frame lines.

    Only ``:seed:`` and ``:shells:`` are valid contract options.  The
    reader-facing ``:verify:`` sentence stays beside the directive in the public
    page, where editors can review the promise made to the reader.
    """
    path = sequence_contract_path(
        page,
        sequence_id,
        docs_root=docs_root,
        contracts_root=contracts_root,
    )
    try:
        text = path.read_text(encoding=_UTF_8)
    except FileNotFoundError as exc:
        raise SequenceEngineError(
            f"missing private sequence contract for page {page!r}, sequence {sequence_id!r}: {path}",
        ) from exc
    except OSError as exc:
        raise SequenceEngineError(f"cannot read private sequence contract {path}: {exc}") from exc

    lines = text.splitlines()
    options: dict[str, str | None] = {}
    index = 0
    while index < len(lines):
        match = _OPTION_RE.match(lines[index].strip())
        if match is None:
            break
        key = match.group("key")
        if key not in _PRIVATE_OPTION_KEYS:
            raise SequenceEngineError(
                f"private sequence contract {path} uses unsupported option :{key}:; "
                "only :seed: and :shells: belong in a contract",
            )
        if key in options:
            raise SequenceEngineError(f"private sequence contract {path} repeats option :{key}:")
        options[key] = match.group("value").strip()
        index += 1

    body = "\n".join(lines[index:]).strip()
    if not body:
        raise SequenceEngineError(f"private sequence contract {path} contains no frame grammar")
    return options, body
