"""Committed per-sequence golden fingerprints for ``cli-sequence`` runs.

One golden file per sequence at ``docs/_sequences/<page-path>/<sequence-id>.json``,
carrying per executed frame: the argv as executed, the exit code, the capture
bindings and, for reader-facing frames, the stream that carried the JSON
envelope and the SHA-256 and byte size of the frame's compared output. The
output itself is not committed. It is regenerated on every check and refresh
into a record (:mod:`~dev.docs.sequences.record_store`), which is what a page
renders, and the golden is that record's fingerprint. The check therefore fails
on exactly the output changes a full stored copy would catch, while an intended
change moves one digest line per frame in review.

Goldens are CLI-owned and never hand-edited: the ``refresh`` mode re-executes
the sequence in its sandbox and rewrites the file through :func:`write_golden`.
A missing golden, a hand-corrupted one, or one written under an earlier
``golden_schema_version`` (version 2 stored the output itself) reads as an
instructive :class:`~dev.docs.sequences.errors.SequenceGoldenError` naming the
exact refresh invocation.

This module also owns the normalisation that makes a record run-independent,
because a golden digest is only stable across runs and machines once it is:

- **JSON envelopes** are stored pre field-mask, so the central
  ``GOLDEN_MASK_FIELDS`` set and the host-conditional carve-out apply when the
  output is compared or rendered, never baked into a record. Path
  normalisation (:func:`normalise_document_paths`) is baked at record time: a
  per-run sandbox path or the checkout path can surface inside an envelope
  STRING VALUE (``config check``'s ``preflight[...].detail``), where the
  field-level mask never looks.
- **Text** is stored after the declared narrow normalisation
  (:func:`normalise_text_output`): per-run sandbox paths and the checkout root
  become stable tokens and centrally masked surrogate ids become the mask
  sentinel.
- **Setup frames** record their argv, exit code and captures only. They still
  execute, and the check asserts their kind, argv, exit code, captures and any
  ``@expect`` against the live run.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Annotated, Final, Literal, cast

from pydantic import BaseModel, Field, JsonValue, StringConstraints, ValidationError, model_validator

from cadrumo.core.hex import Hex64Str
from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.tests.golden_comparison import GOLDEN_MASK_FIELDS, MASK_SENTINEL
from dev._paths import REPO_ROOT, UTF_8

from .errors import SequenceGoldenError
from .runner import CapturedValue, EnvelopeSource, SequenceTranscript
from .schema import FrameKind, SequenceId

__all__ = [
    "PACKAGE_VERSION_PLACEHOLDER",
    "PLATFORM_CONDITIONAL_PREFLIGHT_CHECKS",
    "REPO_ROOT_PLACEHOLDER",
    "SANDBOX_STORAGE_ROOT_PLACEHOLDER",
    "SANDBOX_WORKDIR_PLACEHOLDER",
    "GoldenFrame",
    "SequenceGolden",
    "default_goldens_root",
    "golden_path",
    "mask_host_conditional_details",
    "masked_envelope_values",
    "normalise_document_paths",
    "normalise_text_output",
    "platform_conditional_details",
    "read_golden",
    "refresh_invocation",
    "write_golden",
]

_UTF_8: Final[str] = UTF_8

#: Stable token replacing the per-run isolated storage root in text frames.
SANDBOX_STORAGE_ROOT_PLACEHOLDER: str = "<sandbox-storage-root>"

#: Stable token replacing the per-run sandbox working directory in text frames.
SANDBOX_WORKDIR_PLACEHOLDER: str = "<sandbox-workdir>"

#: Stable token replacing the per-run sandbox root's OWN parent directory —
#: the outer per-sequence temporary directory that ``storage_root`` and
#: ``workdir`` are siblings under. Catches paths under sibling substrates
#: neither of the two more specific tokens above covers, chiefly the secrets
#: store (deliberately anchored on the sandbox root rather than nested inside
#: ``storage_root`` — the production custody split), which otherwise leaks a
#: run-specific temp path into diagnostic-log text frames.
SANDBOX_ROOT_PLACEHOLDER: str = "<sandbox-root>"

#: Stable token replacing the repository checkout root wherever it surfaces in a
#: frame's output. Corpus and data paths carry the absolute checkout path (stable
#: on one machine, different on CI and every other checkout), so a golden is only
#: machine-portable once the checkout root is tokenised the same value-anchored
#: way as the per-run sandbox paths.
REPO_ROOT_PLACEHOLDER: str = "<repo-root>"

#: Stands in for the running package version in captured output.
#:
#: A golden must not carry a version literal. Docs are rendered FROM the golden,
#: so a captured "CADRUMO 0.2.1" is a hardcoded version in user-facing
#: documentation: it rots at the next release, and it silently disagrees with
#: the version the reader actually has. The version is release-managed in one
#: place, so the golden stores this token and the render substitutes the live
#: value back.
PACKAGE_VERSION_PLACEHOLDER: str = "<version>"

_PATH_TOKENS: tuple[str, ...] = (
    SANDBOX_STORAGE_ROOT_PLACEHOLDER,
    SANDBOX_WORKDIR_PLACEHOLDER,
    SANDBOX_ROOT_PLACEHOLDER,
    REPO_ROOT_PLACEHOLDER,
)


def _repo_root() -> Path:
    """Return the repository checkout root (the golden/fixtures/data anchor).

    Resolved relative to this module, the same anchoring as
    :func:`default_goldens_root`, so it equals the prefix of the absolute corpus
    and data paths the CLI emits from this checkout.
    """
    return REPO_ROOT


def _path_replacements(*, storage_root: str, workdir: str) -> list[tuple[str, str]]:
    """Return the value-anchored ``(path, token)`` pairs, longest needle first.

    Four roots are tokenised — the per-run sandbox storage root, workdir, and
    their own parent sandbox root (all run-specific), plus the repository
    checkout root (machine-specific) — each in native, POSIX-slash, and
    JSON-escaped form. The replacement is value-anchored on the exact known
    root strings (never a wildcard), so it can never over-mask an unrelated
    path; longest-first ordering collapses a nested path before its parent, so
    the sandbox root only catches what the two more specific siblings leave
    behind.

    The JSON-escaped form is load-bearing on Windows, where a backslash path
    serialised INTO a value doubles every separator. ``config check`` renders
    its precondition evidence as a JSON blob inside a text table cell, so the
    per-run sandbox path reaches the golden as ``C:\\\\Users\\\\...`` and the
    native single-separator needle never matches it. Without this form that one
    frame carries a run-specific directory name that reds the very next run on
    the same machine — the same defect the host-conditional fact mask closes one
    layer up. A POSIX path is unaffected (it has no backslash to double), so the
    extra pair is inert off Windows rather than conditional on it.
    """
    replacements: list[tuple[str, str]] = []
    anchored = [
        (workdir, SANDBOX_WORKDIR_PLACEHOLDER),
        (storage_root, SANDBOX_STORAGE_ROOT_PLACEHOLDER),
        (str(_repo_root()), REPO_ROOT_PLACEHOLDER),
    ]
    sandbox_root = _writer_path(storage_root).parent
    # A parent that is only a filesystem root (``/``, ``C:\``) would mask every
    # separator in the frame, so a storage root directly under one adds none.
    if sandbox_root.is_absolute() and sandbox_root.parent != sandbox_root:
        anchored.append((str(sandbox_root), SANDBOX_ROOT_PLACEHOLDER))
    for raw, token in anchored:
        native = str(raw)
        posix = native.replace("\\", "/")
        json_escaped = native.replace("\\", "\\\\")
        replacements.append((native, token))
        if posix != native:
            replacements.append((posix, token))
        if json_escaped != native:
            replacements.append((json_escaped, token))
    return sorted(replacements, key=lambda pair: len(pair[0]), reverse=True)


def _writer_path(root: str) -> PurePath:
    """Parse a captured root in the path flavour of the host that wrote it.

    A golden recorded on Windows carries ``C:\\...`` roots that a POSIX checker
    must still decompose: parsed as a host path there, the whole string is one
    relative component whose parent is ``.``, and masking ``.`` rewrites every
    dot in the frame.
    """
    windows = PureWindowsPath(root)
    return windows if windows.drive or "\\" in root else PurePosixPath(root)


def _normalise_token_path_separators(text: str) -> str:
    """Canonicalise separators only in paths rooted at a known stable token.

    Exact root replacement intentionally leaves the path suffix visible.  A
    Windows writer therefore produces ``<repo-root>\\src\\...`` while a POSIX
    checker produces ``<repo-root>/src/...`` unless that suffix is normalised.
    The token anchor keeps unrelated operator paths byte-exact.
    """
    normalised = text
    for token in _PATH_TOKENS:
        token_path = re.compile(rf"{re.escape(token)}(?:[\\/][^\s\"'<>]*)+")
        normalised = token_path.sub(lambda match: match.group(0).replace("\\", "/"), normalised)
    return normalised


#: A page identifier: the docname-style path of the enrolled docs page relative
#: to ``docs/`` (e.g. ``how-to/irpf-lifecycle`` or ``how-to/modelo-303``),
#: forward slashes, no suffix, no traversal.
PageId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
        pattern=r"^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)*$",
    ),
]

_PAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)*$")


class GoldenFrame(BaseModel):
    """One committed frame fingerprint.

    ``output_sha256`` is the digest of the frame's compared output form and
    ``output_bytes`` the size of its recorded output (the reader-facing output
    advisory reads it without executing anything). ``envelope_source`` names the
    stream that carried the JSON envelope, or ``None`` when the output is text
    only. ``captures`` are the values the frame bound, so an id drift is named
    directly in check failures.

    A setup frame is never shown to a reader and carries no output fingerprint:
    its stream fields are all ``None``. Every other executed frame carries both
    the digest and the size.
    """

    model_config = _STRICT_FROZEN

    kind: FrameKind
    argv: tuple[str, ...] = Field(min_length=1)
    exit_code: int
    captures: tuple[CapturedValue, ...] = Field(default=())
    envelope_source: EnvelopeSource | None = None
    output_sha256: Hex64Str | None = None
    output_bytes: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _fingerprint_matches_kind(self) -> GoldenFrame:
        fingerprint = (self.envelope_source, self.output_sha256, self.output_bytes)
        if self.kind is FrameKind.SETUP:
            if fingerprint != (None, None, None):
                raise ValueError("a setup frame records only its argv, exit code and captures")
        elif self.output_sha256 is None or self.output_bytes is None:
            raise ValueError("a reader-facing frame records its output digest and size")
        return self


class SequenceGolden(BaseModel):
    """The committed golden fingerprint of one sequence, in executed-frame order.

    ``golden_schema_version`` 3 is the fingerprint layout. Versions 1 and 2
    stored the output itself; they are refused, never read, and regenerated by
    refresh.
    """

    model_config = _STRICT_FROZEN

    golden_schema_version: Literal[3] = 3
    sequence_id: SequenceId
    frames: tuple[GoldenFrame, ...] = Field(min_length=1)


def default_goldens_root() -> Path:
    """Return the committed ``docs/_sequences/`` golden tree.

    Resolved relative to this module so the engine finds goldens regardless of
    the process working directory (the same anchoring as seeds and fixtures).
    """
    repo_root = REPO_ROOT
    return repo_root / "docs" / "_sequences"


def refresh_invocation(*, page: str | None = None, sequence_id: str | None = None) -> str:
    """Return the exact CLI invocation that (re)writes the addressed goldens."""
    command = "python -m dev.docs.sequences refresh"
    if sequence_id is not None:
        return f"{command} --sequence {sequence_id}"
    if page is not None:
        return f"{command} --page {page}"
    return command


def _validated_page(page: str) -> str:
    stripped = page.strip().replace("\\", "/")
    if not _PAGE_RE.match(stripped) or ".." in stripped.split("/"):
        raise SequenceGoldenError(
            f"page identifier {page!r} must be the docname-style path of the enrolled "
            "page relative to docs/ (forward slashes, lowercase, no suffix, no traversal), "
            "e.g. 'how-to/irpf-lifecycle'",
        )
    return stripped


def golden_path(page: str, sequence_id: str, *, goldens_root: Path | None = None) -> Path:
    """Return the committed golden file path for ``(page, sequence_id)``."""
    root = goldens_root if goldens_root is not None else default_goldens_root()
    return root / _validated_page(page) / f"{sequence_id}.json"


PLATFORM_CONDITIONAL_PREFLIGHT_CHECKS = frozenset(
    {
        "storage:windows-long-path",
        "model-runtime-hardware-floor",
        "local-inference-hardware",
        "local-inference-contention",
    },
)
"""Health rows whose ``detail`` describes the HOST, not the product.

Docs are rendered FROM these goldens, so a row here becomes a sentence in
user-facing prose. Every member states a fact about the machine that happened
to record the capture:

- ``storage:windows-long-path`` reports ``"not applicable on this platform"``
  off Windows and one of several ``LongPathsEnabled`` verdicts on it.
- ``model-runtime-hardware-floor`` reports the host's total RAM against the
  configured floor -- literally ``"total system memory 63.9 GiB meets ..."``.
- ``local-inference-hardware`` and ``local-inference-contention`` report live
  free system memory, accelerator kind, and free VRAM when an NVML reader is
  installed -- figures that drift between two runs on the SAME machine as
  ordinary system load shifts, not only between machines.

Pinning any of these means the golden can only match the machine (and moment)
that wrote it: a Windows capture reds the Linux docs runner, a Linux capture
reds every Windows developer, a 64 GiB capture publishes that number to every
reader, and a free-VRAM reading reds the very next run on the same box.
Masking the detail keeps the row and its id under exact comparison and drops
only the host-specific sentence.

Keyed on the stable row id, never on the detail text: the long-path check alone
has five detail variants and the memory one is unbounded, so enumerating strings
would rot immediately. The id is matched against either ``check`` (preflight
rows) or ``service`` (dependency rows) -- the two shapes ``config check`` emits.
"""

#: Row keys that carry a host-conditional row's stable identifier.
_ROW_ID_KEYS: tuple[str, ...] = ("check", "service")

#: Exact host-row fact coordinates whose values are volatile between runs.
#:
#: Masking the ``detail`` sentence alone leaves the numbers it was rendered from
#: pinned under ``facts``, which reintroduces the very defect
#: :data:`PLATFORM_CONDITIONAL_PREFLIGHT_CHECKS` documents: the local hardware
#: probe's free system memory and free VRAM are live readings that drift between
#: two runs on the same box as ordinary processes allocate memory. The
#: contention row repeats the selected free-capacity value as
#: ``binding_free_bytes`` and must follow the same comparison policy.
#:
#: This is deliberately a row-id/fact-name coordinate, not a suffix rule.
#: Total RAM, total VRAM, thresholds, shortfalls, and byte-valued facts on every
#: other row remain exact diagnostic evidence. Only free-capacity values mask; the
#: key stays under comparison, so a probe that stops reporting free RAM reds.
_VOLATILE_HOST_FACT_COORDINATES: frozenset[tuple[str, str]] = frozenset(
    {
        ("local-inference-hardware", "free_memory_bytes"),
        ("local-inference-hardware", "free_vram_bytes"),
        ("local-inference-contention", "binding_free_bytes"),
    },
)


def _host_conditional_row_id(node: Mapping[str, object]) -> str | None:
    """Return the row's id when it names a host-conditional row, else ``None``."""
    for key in _ROW_ID_KEYS:
        value = node.get(key)
        if isinstance(value, str) and value in PLATFORM_CONDITIONAL_PREFLIGHT_CHECKS:
            return value
    return None


def platform_conditional_details(document: object) -> frozenset[str]:
    """Collect ``detail`` values belonging to host-conditional health rows.

    Walks any envelope shape looking for mappings that carry both a
    host-conditional row id (under ``check`` or ``service``) and a string
    ``detail``. Matching on the pair is what keeps this narrow: a bare ``detail``
    key elsewhere in the envelope is untouched.
    """
    values: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, Mapping):
            detail = node.get("detail")
            if _host_conditional_row_id(node) is not None and isinstance(detail, str) and detail:
                values.add(detail)
            for item in node.values():
                _walk(item)
            return
        if isinstance(node, list | tuple):
            for item in node:
                _walk(item)

    _walk(document)
    return frozenset(values)


def mask_host_conditional_details(document: object) -> object:
    """Replace host-conditional row details with the mask sentinel.

    The structural-tier counterpart to :func:`platform_conditional_details`,
    which serves the text tier. Both route through the same row-id predicate so
    the two tiers cannot drift into disagreeing about which rows are
    host-conditional.

    Rebuilds the document rather than mutating it, so the caller's envelope is
    untouched and the diff paths reported on a genuine divergence still line up
    with the stored artifact.
    """
    if isinstance(document, Mapping):
        masked: dict[str, object] = {str(key): mask_host_conditional_details(value) for key, value in document.items()}
        row_id = _host_conditional_row_id(document)
        if row_id is not None:
            if isinstance(document.get("detail"), str):
                masked["detail"] = MASK_SENTINEL
            facts = document.get("facts")
            if isinstance(facts, Mapping):
                masked["facts"] = {
                    str(key): (MASK_SENTINEL if (row_id, str(key)) in _VOLATILE_HOST_FACT_COORDINATES else value)
                    for key, value in facts.items()
                }
        return masked
    if isinstance(document, list | tuple):
        return [mask_host_conditional_details(item) for item in document]
    return document


def masked_envelope_values(transcript: SequenceTranscript) -> frozenset[str]:
    """Collect the transcript's centrally-masked surrogate-key values.

    Walks every JSON frame's envelope and gathers the string values stored under
    the :data:`GOLDEN_MASK_FIELDS` keys at any depth. Text normalisation replaces
    these values where they appear inline in text output — the "central masked
    ids where they appear inline" half of the text-normalisation policy.

    Setup frames are walked too, although their own output is never stored: an
    id a setup frame minted can reappear inline in a later frame's text.

    Platform-conditional preflight details ride the same channel. Each side
    collects the values from ITS OWN run, exactly as the sandbox paths do, so
    the writer's Windows sentence and the reader's Linux sentence both reduce to
    the mask sentinel and compare equal without either being declared correct.
    """
    values: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, Mapping):
            for key, item in node.items():
                if str(key) in GOLDEN_MASK_FIELDS and isinstance(item, str):
                    values.add(item)
                else:
                    _walk(item)
            return
        if isinstance(node, list | tuple):
            for item in node:
                _walk(item)

    for frame in transcript.frames:
        if frame.envelope is not None:
            _walk(frame.envelope)
            values |= platform_conditional_details(frame.envelope)
    return frozenset(values)


def _normalise_volatile_host_fact_lines(text: str) -> str:
    """Mask exact config-check text coordinates for volatile free capacity."""
    prefixes = tuple(f"{row_id}.facts.{fact_name}\t" for row_id, fact_name in _VOLATILE_HOST_FACT_COORDINATES)
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        ending = "\n" if line.endswith("\n") else ""
        content = line.removesuffix("\n").removesuffix("\r")
        matched = next((prefix for prefix in prefixes if content.startswith(prefix)), None)
        lines.append(f"{matched}{MASK_SENTINEL}{ending}" if matched is not None else line)
    return "".join(lines)


def _running_version() -> str:
    """Return the version the running package declares.

    Read from the package's single release-managed declaration rather than from
    installed distribution metadata, which reports whatever wheel happens to be
    in the environment and disagrees with the checkout after a version reset.
    """
    from cadrumo.core.package_version import PACKAGE_VERSION

    return PACKAGE_VERSION


def normalise_text_output(
    text: str,
    *,
    storage_root: str,
    workdir: str,
    masked_values: Iterable[str] = (),
) -> str:
    """Apply the declared narrow text normalisation.

    Exactly three token families are normalised — nothing else: the per-run and
    machine-specific paths (sandbox storage root, workdir, and the repository
    checkout root, in both native and POSIX slash forms, longest first so nested
    paths collapse correctly) become stable tokens, the centrally-masked
    surrogate-id values become the mask sentinel, and the running package
    version becomes :data:`PACKAGE_VERSION_TOKEN`. No regex wildcards, no fuzzy
    matching: the result is compared by exact string equality.

    The version family exists because docs are rendered FROM these goldens, so a
    captured version literal is a hardcoded version in user-facing prose. It is
    value-anchored on the exact declared version like every other replacement,
    never a digit pattern, so it cannot over-match an unrelated number.
    """
    replacements = _path_replacements(storage_root=storage_root, workdir=workdir)
    replacements.append((_running_version(), PACKAGE_VERSION_PLACEHOLDER))
    for value in masked_values:
        if value:
            replacements.append((value, MASK_SENTINEL))

    normalised = _normalise_volatile_host_fact_lines(text)
    for needle, token in sorted(replacements, key=lambda pair: len(pair[0]), reverse=True):
        normalised = normalised.replace(needle, token)
    return _normalise_token_path_separators(normalised)


def normalise_document_paths(
    document: dict[str, JsonValue],
    *,
    storage_root: str,
    workdir: str,
) -> dict[str, JsonValue]:
    """Tokenise the sandbox and checkout paths in every string leaf of an envelope.

    The value-anchored analogue of :func:`normalise_text_output` for JSON frames.
    A per-run sandbox path or the machine's checkout path can surface inside an
    envelope STRING VALUE — e.g. ``config check``'s ``preflight[...].detail``
    ("secure-storage root <path> is reachable"; corpus paths under the checkout) —
    exactly where the field-level ``mask_document`` never looks, because that
    primitive masks whole FIELDS by key, not path substrings inside a text value.
    Applied to the golden at BUILD time (the writer's per-run paths are unknowable
    to a later reader, so they must be baked out, the same necessity the text
    frames already carry) and to the LIVE envelope at COMPARE time with this run's
    paths, so both sides carry the stable tokens before the central field mask
    runs. Only exact known-root strings are replaced, so it cannot over-mask.
    """
    replacements = _path_replacements(storage_root=storage_root, workdir=workdir)

    def _norm(node: object) -> object:
        if isinstance(node, str):
            for needle, token in replacements:
                node = node.replace(needle, token)
            return _normalise_token_path_separators(node)
        if isinstance(node, Mapping):
            return {str(key): _norm(value) for key, value in node.items()}
        if isinstance(node, list):
            return [_norm(item) for item in node]
        return node

    return cast("dict[str, JsonValue]", _norm(document))


def write_golden(golden: SequenceGolden, *, page: str, goldens_root: Path | None = None) -> Path:
    """Write ``golden`` to its committed location.

    This is the ONLY sanctioned writer (the refresh CLI mode drives it). The
    file is canonical JSON — key-sorted, two-space indent, UTF-8, trailing
    newline — so review diffs are stable and minimal.
    """
    target = golden_path(page, golden.sequence_id, goldens_root=goldens_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(golden.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    return target


def read_golden(
    page: str,
    sequence_id: str,
    *,
    goldens_root: Path | None = None,
) -> SequenceGolden:
    """Read and strictly validate a committed golden expectation.

    Raises:
        SequenceGoldenError: When the golden file is missing (naming the exact
            refresh invocation that creates it), is not valid JSON, or does not
            validate against the strict golden schema: a hand edit, or a
            golden written under an earlier layout.
    """
    target = golden_path(page, sequence_id, goldens_root=goldens_root)
    if not target.is_file():
        raise SequenceGoldenError(
            f"no committed golden for sequence {sequence_id!r} on page {page!r} "
            f"(expected {target}); generate it with: "
            f"{refresh_invocation(sequence_id=sequence_id)}",
        )
    try:
        raw = target.read_text(encoding=_UTF_8)
    except OSError as exc:
        raise SequenceGoldenError(f"cannot read golden {target}: {exc}") from exc
    try:
        return SequenceGolden.model_validate_json(raw)
    except ValidationError as exc:
        raise SequenceGoldenError(
            f"golden {target} does not validate against the golden schema (a hand edit, or "
            f"a layout this engine no longer reads) — goldens are CLI-owned and never "
            f"hand-edited; regenerate it with: "
            f"{refresh_invocation(sequence_id=sequence_id)}\n{exc}",
        ) from exc
