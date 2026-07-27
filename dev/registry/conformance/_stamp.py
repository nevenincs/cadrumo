"""Write a modelo revision's DECLARED governance stamp to its ``revision.toml``.

The one conformance axis nothing can derive. Who engineered a revision and how
far its review has progressed are facts about people and agents, so the tree
cannot compute them and a governance surface that only derived would report
ninety revisions with no provenance forever. This module is the write path for
that declaration, and it is deliberately the narrowest and most suspicious code
in the package.

Why an agent may not stamp ``operator_reviewed``
------------------------------------------------

:data:`StampableReviewStatus` carries exactly two members, and
:attr:`~cadrumo.core.RevisionReviewStatus.OPERATOR_REVIEWED` is not one of them.
This CLI is driven by agents. An agent writing "the operator reviewed this" is
precisely the dishonesty the whole conformance feature exists to detect, and no
flag can fix it: an ``--i-am-the-operator`` switch is as assertable by an agent
as the value itself, so it would add the APPEARANCE of assurance and none of
the substance. The registry schema still accepts the value, so the operator
retains the ability to sign off by editing ``revision.toml`` directly — which
the governing decision explicitly keeps legal. The friction is the feature:
operator signoff stays a human act on the file, and this tool cannot manufacture
one.

Why the stamp is manifest-only
------------------------------

A stamp declared inside a per-section fragment merged silently and won, so a
revision could read unstamped in ``revision.toml`` while the compiled snapshot
claimed a completed review — a laundering path the loader now refuses outright.
This writer must not open a second one. It writes ONLY to the revision's own
``revision.toml`` manifest, only the four governance scalars, and only after the
revision has been confirmed to exist as a COMPILED record rather than as a
directory that happens to be on disk.

Refuse before writing, then prove the write
-------------------------------------------

The coherence rule — reviewer identity present exactly when the status is beyond
``pending_review`` — is enforced twice on purpose. Before the write it is
enforced by asking the real :class:`~domain.calculations.registry.ModeloRevision`
validator through a probe revision, never by mirroring its logic here, so this
module cannot drift from the rule registry build actually applies. After the
write the whole modelo is re-loaded through the real loader; if it refuses, the
original bytes are restored and the refusal is raised. A state the loader would
reject is therefore unreachable through this path.

See Also:
    :class:`~cadrumo.core.RevisionReviewStatus`
        Closed review vocabulary this writer narrows for agent use.
    :class:`~domain.calculations.registry.ModeloRevision`
        Schema whose validator adjudicates every stamp before it is written.
    :func:`~domain.calculations.registry.load_modelo_directory`
        Real loader used to prove the written tree still compiles.
    :mod:`~dev.registry.conformance.cli`
        Typer surface exposing this writer as the ``stamp`` verb.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.core import RevisionReviewStatus
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    REVISION_GOVERNANCE_FIELDS,
    ModeloRevision,
    PeriodSelector,
    RegistryError,
    load_modelo_directory,
)

from .manager import reset_conformance_cache

__all__ = [
    "GOVERNANCE_KEYS",
    "StampError",
    "StampResult",
    "StampableReviewStatus",
    "revision_manifest_path",
    "stamp_revision",
]


class StampableReviewStatus(StrEnum):
    """Review statuses this CLI is willing to WRITE.

    A deliberate narrowing of :class:`~cadrumo.core.RevisionReviewStatus`, not a
    second vocabulary: every member's value is byte-identical to its core
    counterpart, and a test pins that correspondence together with the
    deliberate absence of ``operator_reviewed``. The narrowing is what makes the
    CLI's accepted-value list honest at the parse boundary — offering a choice
    the tool would always refuse teaches nothing.
    """

    PENDING_REVIEW = "pending_review"
    AGENT_REVIEWED = "agent_reviewed"


#: Emit order for the governance scalars, chosen so a manifest reads
#: authorship first and the review claim after it.
_EMIT_ORDER: Final[tuple[str, ...]] = ("engineered_by", "review_status", "reviewed_by", "reviewed_at")

GOVERNANCE_KEYS: Final[tuple[str, ...]] = (
    *(key for key in _EMIT_ORDER if key in REVISION_GOVERNANCE_FIELDS),
    *sorted(REVISION_GOVERNANCE_FIELDS - set(_EMIT_ORDER)),
)
"""The governance scalars this writer owns, in the order it emits them.

The SET is the shipped :data:`REVISION_GOVERNANCE_FIELDS`, never a second copy:
that set is derived from the field declarations themselves and is the sole input
to the loader's fragment refusal, so a fifth governance scalar added to the model
must reach this writer without anybody remembering to update it. Only the ORDER
is chosen here, and a field the emit order does not name is appended rather than
dropped — an unordered field is a cosmetic gap, an unwritable one is a
capability hole.
"""

#: Registry path segment pattern. A segment carrying a separator, a parent
#: reference, or a drive letter would escape the registry root on join, so the
#: shape is checked before any path is built rather than after.
_SAFE_SEGMENT: Final = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")

#: Minimal period selector for the pre-write probe revision. Never written
#: anywhere; it exists only so the real schema validator can be asked whether a
#: governance combination is legal. Built at import so a schema change that
#: breaks the probe fails loudly here rather than surfacing later disguised as a
#: refused governance stamp.
_PROBE_PERIOD_SELECTOR: Final = PeriodSelector(year_from=2000, periods=("1T",))


class StampError(RuntimeError):
    """A governance stamp was refused, or could not be written safely."""


@dataclass(frozen=True, slots=True)
class _Stamp:
    """The four governance scalars, typed, as declared or as intended.

    ``review_status`` stays a plain string until the schema probe hydrates it:
    a manifest can declare any token at all, and coercing it to the enum here
    would raise a bare ``ValueError`` instead of the schema's own instructive
    refusal.
    """

    engineered_by: str | None
    review_status: str | None
    reviewed_by: str | None
    reviewed_at: date | None

    def rendered(self) -> dict[str, str]:
        """Return the present scalars in canonical TOML form, in emit order."""
        values = {
            "engineered_by": self.engineered_by,
            "review_status": self.review_status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
        }
        return {key: _render_toml_value(values[key]) for key in GOVERNANCE_KEYS if values[key] is not None}

    def declared_keys(self) -> frozenset[str]:
        """Return the governance keys this stamp carries a value for."""
        return frozenset(self.rendered())


class StampResult:
    """What one successful stamp changed.

    Attributes:
        manifest: The ``revision.toml`` that was rewritten.
        modelo: The stamped modelo id.
        revision: The stamped revision id.
        written: The governance keys now present, mapped to their rendered TOML
            values.
        removed: The governance keys the stamp dropped, which happens when a
            status returns to ``pending_review`` and the reviewer identity must
            go with it.
    """

    __slots__ = ("manifest", "modelo", "removed", "revision", "written")

    def __init__(
        self,
        *,
        manifest: Path,
        modelo: str,
        revision: str,
        written: dict[str, str],
        removed: tuple[str, ...],
    ) -> None:
        self.manifest = manifest
        self.modelo = modelo
        self.revision = revision
        self.written = written
        self.removed = removed

    def render(self) -> str:
        """Return the stamp as one greppable ``key=value`` record line."""
        parts = [
            "stamped",
            f"modelo={self.modelo}",
            f"revision={self.revision}",
            f"manifest={self.manifest.name}",
        ]
        parts.extend(f"{key}={value}" for key, value in self.written.items())
        parts.append(f"removed={','.join(self.removed) if self.removed else '-'}")
        return " ".join(parts)


def revision_manifest_path(modelo: str, revision: str, *, registry_root: Path | None = None) -> Path:
    """Resolve one revision's ``revision.toml`` manifest under the registry root.

    Args:
        modelo: Modelo id, e.g. ``"130"``.
        revision: Revision id, e.g. ``"2019-y-siguientes"``.
        registry_root: Registry tree root. Defaults to the bundled AEAT tree.

    Returns:
        The resolved manifest path.

    Raises:
        StampError: A segment is not a plain registry identifier, the resolved
            path escapes the registry root, or the manifest does not exist.
            Existence is checked because the fragmented layout makes an absent
            manifest a real authoring state, not an impossible one.
    """
    for label, segment in (("modelo", modelo), ("revision", revision)):
        if not _SAFE_SEGMENT.fullmatch(segment):
            raise StampError(
                f"{label} id {segment!r} is not a plain registry identifier; accepted shape is "
                "letters, digits, dot, dash and underscore, starting with a letter or digit",
            )
    root = (bundled_path("registry", "aeat") if registry_root is None else registry_root).resolve()
    manifest = (root / "modelos" / modelo / "revisions" / revision / "revision.toml").resolve()
    if not manifest.is_relative_to(root):
        raise StampError(f"{manifest}: resolved outside the registry root {root}")
    if not manifest.is_file():
        raise StampError(
            f"{manifest}: no revision manifest to stamp; the governance stamp is manifest-only and "
            "is never written into a per-section fragment",
        )
    return manifest


def stamp_revision(
    modelo: str,
    revision: str,
    *,
    engineered_by: str | None = None,
    clear_engineered_by: bool = False,
    review_status: StampableReviewStatus | None = None,
    reviewed_by: str | None = None,
    reviewed_at: date | None = None,
    registry_root: Path | None = None,
) -> StampResult:
    """Write the declared governance scalars for one modelo revision.

    Only the arguments supplied are changed; an omitted field keeps whatever the
    manifest already declares. Advancing the status requires a reviewer and a
    date. Returning the status to ``pending_review`` DROPS the declared reviewer
    identity, because the schema refuses a reviewer recorded against an
    unreviewed status; but SUPPLYING a reviewer while the status stays
    ``pending_review`` is REFUSED rather than dropped, so a caller who asks to
    record a review is never told the write succeeded while their claim was
    discarded.

    A cleared revision keeps an explicit ``review_status = "pending_review"``
    line rather than reverting to an empty manifest. Absence already reads as
    ``pending_review``, so the line adds no derived fact — it adds a stated one,
    and a manifest that says what it means beats one a reader must know a
    default to interpret.

    Args:
        modelo: Modelo id to stamp.
        revision: Revision id to stamp.
        engineered_by: Who built the revision.
        clear_engineered_by: Drop the authorship claim instead of replacing it.
            Present so a wrong name is correctable: without it the first write
            of an authorship claim would be a one-way door.
        review_status: How far its review has progressed.
        reviewed_by: Who reviewed it.
        reviewed_at: When they reviewed it.
        registry_root: Registry tree root. Defaults to the bundled AEAT tree.

    Returns:
        The :class:`StampResult` describing what changed.

    Raises:
        StampError: Nothing was supplied to write, an authorship claim was
            supplied together with its clearing, an identity names nobody, the
            revision is not a compiled record in the tree, the resulting stamp
            is one the schema refuses, or the written tree no longer loads. In
            the last case the manifest is restored to its previous bytes before
            the error is raised.
    """
    if engineered_by is not None and clear_engineered_by:
        raise StampError("engineered_by and clear_engineered_by contradict each other; supply one")
    if not any((engineered_by, clear_engineered_by, review_status, reviewed_by, reviewed_at)):
        raise StampError(
            "nothing to stamp: supply at least one of engineered_by, clear_engineered_by, "
            "review_status, reviewed_by, reviewed_at",
        )
    engineered_by = _named_identity(engineered_by, "engineered_by")
    reviewed_by = _named_identity(reviewed_by, "reviewed_by")

    manifest = revision_manifest_path(modelo, revision, registry_root=registry_root)
    modelo_dir = manifest.parent.parent.parent
    _assert_revision_is_compiled(modelo_dir, modelo=modelo, revision=revision)

    original = manifest.read_text(encoding=UTF_8_ENCODING)
    declared = _declared_governance(manifest, original, revision)
    resolved = _resolve_stamp(
        declared,
        engineered_by=engineered_by,
        clear_engineered_by=clear_engineered_by,
        review_status=review_status,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
    )
    _assert_schema_accepts(revision, resolved)

    rendered = resolved.rendered()
    dropped = declared.declared_keys() - resolved.declared_keys()
    removed = tuple(key for key in GOVERNANCE_KEYS if key in dropped)
    manifest.write_text(_apply_governance(original, revision, rendered), encoding=UTF_8_ENCODING)

    try:
        _assert_revision_is_compiled(modelo_dir, modelo=modelo, revision=revision)
    except StampError:
        manifest.write_text(original, encoding=UTF_8_ENCODING)
        raise

    reset_conformance_cache()
    return StampResult(
        manifest=manifest,
        modelo=modelo,
        revision=revision,
        written=rendered,
        removed=removed,
    )


def _named_identity(value: str | None, field: str) -> str | None:
    """Return ``value`` trimmed, refusing a provenance claim that names nobody.

    A whitespace-only identity is the shape of a claim with no claimant: the
    manifest asserts a person or an agent built or reviewed the revision while
    naming neither, and a minimum-length check alone accepts it. The schema is
    the deeper gate for what a stored identity may be; this is the CLI boundary
    refusing to WRITE a value it can already see is empty of content, and
    trimming what it does write so a trailing newline never becomes part of a
    name.
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        raise StampError(
            f"{field} names nobody: a provenance claim must identify the person or agent it "
            "attributes the work to, and whitespace identifies neither",
        )
    return trimmed


def _assert_revision_is_compiled(modelo_dir: Path, *, modelo: str, revision: str) -> None:
    """Confirm the revision exists as a COMPILED record, never as a directory listing.

    A subdirectory-blind read of this registry has twice produced wrong verdicts,
    so the revision must be present in the loaded :class:`ModeloDefinition`.
    Re-used after the write as the proof that the loader still accepts the tree.
    """
    try:
        definition = load_modelo_directory(modelo_dir)
    except RegistryError as exc:
        raise StampError(f"modelo {modelo}: registry refuses to load the modelo: {exc}") from exc
    if revision not in definition.revisions:
        raise StampError(
            f"modelo {modelo}: the loaded tree declares no revision {revision!r}; declared revisions "
            f"are {sorted(definition.revisions)}",
        )


def _declared_governance(manifest: Path, text: str, revision: str) -> _Stamp:
    """Read the governance scalars the manifest already declares."""
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise StampError(f"{manifest}: revision manifest is not valid TOML: {exc}") from exc
    revisions = parsed.get("revisions")
    if not isinstance(revisions, dict) or revision not in revisions:
        raise StampError(f'{manifest}: manifest declares no [revisions."{revision}"] table')
    if len(revisions) != 1:
        raise StampError(
            f"{manifest}: manifest declares {len(revisions)} revision tables; the fragmented layout "
            "requires exactly one so the stamp has a single unambiguous home",
        )
    table = revisions[revision]
    if not isinstance(table, dict):
        raise StampError(f'{manifest}: [revisions."{revision}"] is not a table')
    return _Stamp(
        engineered_by=_declared_text(manifest, table, "engineered_by"),
        review_status=_declared_text(manifest, table, "review_status"),
        reviewed_by=_declared_text(manifest, table, "reviewed_by"),
        reviewed_at=_declared_date(manifest, table),
    )


def _declared_text(manifest: Path, table: dict[str, object], key: str) -> str | None:
    """Read one declared string scalar, refusing a value of the wrong TOML type."""
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise StampError(f"{manifest}: governance key {key!r} declares {type(value).__name__}, expected a string")
    return value


def _declared_date(manifest: Path, table: dict[str, object]) -> date | None:
    """Read the declared review date, refusing a value of the wrong TOML type."""
    value = table.get("reviewed_at")
    if value is None:
        return None
    if not isinstance(value, date):
        raise StampError(
            f"{manifest}: governance key 'reviewed_at' declares {type(value).__name__}, expected a "
            "bare TOML date such as 2026-07-27",
        )
    return value


def _resolve_stamp(
    declared: _Stamp,
    *,
    engineered_by: str | None,
    clear_engineered_by: bool,
    review_status: StampableReviewStatus | None,
    reviewed_by: str | None,
    reviewed_at: date | None,
) -> _Stamp:
    """Merge the requested changes onto what the manifest already declares."""
    requested_author = engineered_by if engineered_by is not None else declared.engineered_by
    author = None if clear_engineered_by else requested_author
    status = review_status.value if review_status is not None else declared.review_status
    if status in (None, RevisionReviewStatus.PENDING_REVIEW.value):
        # A reviewer identity supplied against an unreviewed status is REFUSED,
        # never quietly dropped: the caller asked to record a review, and
        # discarding that request while reporting success would leave them
        # believing a review is on file that is not. Returning a revision to the
        # backlog with no reviewer supplied is the legitimate case, and there the
        # already-declared identity leaves with the claim it attested to.
        supplied = sorted(
            name for name, value in (("reviewed_by", reviewed_by), ("reviewed_at", reviewed_at)) if value is not None
        )
        if supplied:
            raise StampError(
                f"refusing to record {supplied!r} while review_status is "
                f"{RevisionReviewStatus.PENDING_REVIEW.value!r}: the schema refuses a reviewer "
                f"attached to a review the status denies. Record the review by also passing "
                f"review_status={StampableReviewStatus.AGENT_REVIEWED.value!r}",
            )
        return _Stamp(engineered_by=author, review_status=status, reviewed_by=None, reviewed_at=None)
    return _Stamp(
        engineered_by=author,
        review_status=status,
        reviewed_by=reviewed_by if reviewed_by is not None else declared.reviewed_by,
        reviewed_at=reviewed_at if reviewed_at is not None else declared.reviewed_at,
    )


def _assert_schema_accepts(revision: str, resolved: _Stamp) -> None:
    """Ask the real revision schema whether this governance combination is legal.

    A probe revision carrying the intended stamp is validated by
    :class:`ModeloRevision` itself, so the refusal a caller sees here is the same
    refusal registry build would raise. Mirroring the coherence rule in this
    module would let the two drift, and the drift would show up as a manifest
    the loader rejects.
    """
    try:
        ModeloRevision(
            id=revision,
            valid_from=date(2000, 1, 1),
            period_selector=_PROBE_PERIOD_SELECTOR,
            legal_refs=("probe:art-1",),
            source_refs=("probe-source",),
            engineered_by=resolved.engineered_by,
            review_status=RevisionReviewStatus(resolved.review_status or RevisionReviewStatus.PENDING_REVIEW),
            reviewed_by=resolved.reviewed_by,
            reviewed_at=resolved.reviewed_at,
        )
    except (RegistryError, ValueError) as exc:
        raise StampError(f"refused governance stamp for revision {revision!r}: {exc}") from exc


def _render_toml_value(value: object) -> str:
    """Render one governance scalar in canonical TOML form.

    Dates are emitted bare, matching ``valid_from`` in every shipped manifest;
    strings are emitted with the escaping TOML requires so a reviewer name
    carrying a quote cannot break the table.
    """
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _apply_governance(text: str, revision: str, rendered: dict[str, str]) -> str:
    """Rewrite the manifest's governance keys inside its single revision table.

    Line-oriented on purpose: a full TOML round-trip would reformat every
    hand-authored multi-line array in the file and bury the one-line stamp in an
    unreviewable diff. Only whole ``key = value`` lines for the four governance
    keys are touched; every other line is passed through byte for byte.
    """
    lines = text.splitlines()
    header = f'[revisions."{revision}"]'
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == header)
    except StopIteration as exc:  # pragma: no cover - _declared_governance proves the table exists
        raise StampError(f"revision manifest has no {header} header line") from exc

    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("[")),
        len(lines),
    )
    body = [line for line in lines[start + 1 : end] if not _is_governance_line(line)]
    while body and not body[-1].strip():
        body.pop()
    body.extend(f"{key} = {rendered[key]}" for key in GOVERNANCE_KEYS if key in rendered)

    rebuilt = [*lines[:start], lines[start], *body, "", *lines[end:]]
    while rebuilt and not rebuilt[-1].strip():
        rebuilt.pop()
    return "\n".join(rebuilt) + "\n"


def _is_governance_line(line: str) -> bool:
    """Whether a manifest line assigns one of the four governance scalars.

    Anchored at the start of the line so a governance key name appearing inside
    a continued array element is never mistaken for an assignment; the four keys
    are scalars, so their assignment is always a single whole line.
    """
    stripped = line.lstrip()
    return any(re.match(rf"{key}\s*=", stripped) for key in GOVERNANCE_KEYS)
