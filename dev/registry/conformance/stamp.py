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
:attr:`~cadrumo.core.revision_review.RevisionReviewStatus.OPERATOR_REVIEWED` is not one of them.
This CLI is driven by agents. An agent writing "the operator reviewed this" is
precisely the dishonesty the whole conformance feature exists to detect, and no
flag can fix it: an ``--i-am-the-operator`` switch is as assertable by an agent
as the value itself, so it would add the APPEARANCE of assurance and none of
the substance. The registry schema still accepts the value, so the operator
retains the ability to sign off by editing ``revision.toml`` directly — which
the governing decision explicitly keeps legal. The friction is the feature:
operator signoff stays a human act on the file, and this tool cannot manufacture
one.

The narrowing is ENFORCED, not annotated
----------------------------------------

The paragraph above is a claim about what this module refuses, so it is only
true if something refuses. For a while nothing did: the narrowed vocabulary was
a TYPE HINT on :func:`stamp_revision` and every line downstream read
``.value`` off whatever object it was handed. The core
:class:`~cadrumo.core.revision_review.RevisionReviewStatus` is one import away, carries a
``.value``, and is the enum a caller reaches for first because it lives in
``cadrumo.core`` — so a three-line driver written to spare somebody ninety
manifest edits wrote a completed operator signoff naming an agent, and neither
the schema probe nor the post-write reload could object, because the SCHEMA
legitimately accepts ``operator_reviewed``. Only this CLI refuses it, so this
CLI must refuse it where values actually arrive. :func:`stamp_revision` now
coerces the requested status through :class:`StampableReviewStatus` before any
other work, and the refusal names the value and the path a real signoff takes.
A type hint governs a type checker; the coercion governs the file on disk.

The refusal keys on the EFFECTIVE status, not only the requested one
--------------------------------------------------------------------

Coercing the REQUESTED status closed the CREATION of a false operator claim and
left its ATTRIBUTION writable — and attribution is the whole content of the
claim, because a status alone names nobody. With no status supplied the
coercion never fires, the merge falls through to the status the manifest
already declares, and a lone ``--reviewed-by`` writes the reviewer identity
against a DECLARED ``operator_reviewed``. A manifest then names an agent as the
operator's signatory, and that is worse than the creation case in two ways. It
is SILENT to every gate: the operator ceiling counts revisions LACKING a
signoff, and this revision still has one. And it DESTROYS the real operator's
name and date, which the governing decision calls underivable by construction,
so nothing in the tree can reconstruct what was overwritten.

The vocabulary check is therefore applied to the status the write would RESOLVE
TO. When the revision declares a status outside :class:`StampableReviewStatus`
and the request touches any review-axis field, the write is refused and the
caller is sent to the manifest, which is the same door a real signoff comes
through.

That declared status is read off the COMPILED revision rather than off the
manifest text. The two agree today, and only because the loader refuses
governance keys declared in a section fragment — which is the laundering path
that refusal exists to close, so a guard resting on it is resting on the
mechanism it exists to complement. In the one case the readings could diverge —
a signoff reaching the compiled record from somewhere the manifest does not show
— the manifest reading falls through to "nothing declared" and PERMITS the write.
The compiled record is the authority every consumer of this registry sees, this
module already loads it to prove the revision exists, and reading one field off
it costs nothing.

ERASURE is refused by the same rule, deliberately. Returning a signed revision
to ``pending_review`` does red the ratchet — it raises the operator backlog —
but it reds it AFTER the name and the date are already gone, and a loud alarm
over unrecoverable data is not a substitute for a closed door. The ratchet
catches destruction; only the refusal prevents it.

Authorship stays ORTHOGONAL. ``engineered_by`` on an operator-signed revision
is legal and leaves the signoff untouched: who built a revision is a different
fact from who signed it off, and a blanket "the resolved status must be
stampable" rule would refuse an honest authorship claim for a reason that has
nothing to do with authorship.

A new reviewer must restate the date
------------------------------------

An omitted argument keeps whatever the manifest declares, which is right for
every scalar except the reviewer and the date together. A lone ``reviewed_by``
merged onto the DECLARED ``reviewed_at``, so a new claim was recorded against an
old claim's date — measured as ``agent:second`` inheriting ``2026-01-15`` from
``agent:first`` — and the record then stated that a person reviewed a revision on
a day they did not.

The rule is a refusal rather than a defaulted date. Defaulting to today would
close the smear equally, and would silently rewrite the date of a real review
whenever a caller only meant to correct a misspelt name, so the tool would be
trading one false date for another with no way to tell them apart. Refusing makes
the caller say which act they are performing. It fires only on a CHANGE of
reviewer against a declared date: restating the same reviewer inherits a date
that is still that reviewer's own, and a first review has nothing to inherit.

A delta edition's review states its scope
-----------------------------------------

An edition that names a predecessor compiles with casilla rows it inherits and
does not state, so a reviewer reading its file signs off on a delta. Its review
covers the rows it states, judged against that predecessor, and the stamp says so:
``reviewed_against`` names the predecessor. This writer fills that scalar from the
COMPILED record's declared predecessor whenever the resolved stamp claims a
review, and drops it when the stamp returns to ``pending_review``. No caller can
supply it, so the scope is always the one the edition actually declares at the
moment of the review, and the schema refuses a claim whose scope no longer
matches.

Why the stamp is manifest-only
------------------------------

A stamp declared inside a per-section fragment merged silently and won, so a
revision could read unstamped in ``revision.toml`` while the compiled snapshot
claimed a completed review — a laundering path the loader now refuses outright.
This writer must not open a second one. It writes ONLY to the revision's own
``revision.toml`` manifest, only the four governance scalars, and only after the
revision has been confirmed to exist as a COMPILED record rather than as a
directory that happens to be on disk.

The target tree is never implicit
---------------------------------

``registry_root`` has no default. It once defaulted to the bundled AEAT tree,
which made the shipped registry the target of every call that simply forgot to
name one — and that is not a hypothetical. A test mutation that dropped the
root pass-through one caller upstream sent the whole suite's stamp invocations
at the shipped Modelo 130 manifest and wrote a fabricated agent review into it:

.. code-block:: toml

    review_status = "agent_reviewed"
    reviewed_by = "agent:opus-executor"
    reviewed_at = 2026-07-28

It was recoverable only because the write is a three-line append to a file under
version control, and a second reviewer separately reported a fabricated stamp
appearing in the shipped tree without being able to attribute it. A default that
is the most consequential possible value is a default nobody should have to
remember to override.

So the parameter is REQUIRED, and dropping it is now a :exc:`TypeError` at the
call rather than a write to shipped data — the exact mutation that caused the
incident is unconstructible. The shipped tree is still stampable, because
declaring authorship and agent review over it is the whole point of the verb;
it is reachable only by NAMING it, through :func:`bundled_registry_root` and the
CLI flag that calls it. ``importlib.resources`` documents the bundled path as
read-only for callers, so this module is the one place allowed to say otherwise
and it says so out loud.

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

"The original bytes" is meant literally, and for a while it was not true. The
manifest was read with ``read_text`` and restored with ``write_text``, so on
Windows the restore expanded every LF to CRLF: measured on the bundled Modelo
130 manifest, 422 bytes and eight LF terminators came back as 430 bytes and
eight CRLF ones. The only test exercising the real restore compared
``read_text``, which normalises away the very difference the claim is about, and
the two byte-identity assertions guarding it sit on the PRE-WRITE refusal path
where nothing was written and are trivially true there. Reading and writing
through raw bytes makes the sentence true, and the successful write now touches
the governance lines only rather than rewriting the file's every terminator.

See Also:
    :class:`~cadrumo.core.revision_review.RevisionReviewStatus`
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
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.core.toml import TomlDecodeError, parse_toml, to_str_keyed_dict
from cadrumo.core.type_guards import is_object_mapping
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor, NoPredecessor
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from ..compiler.loader import load_modelo_directory
from .manager import reset_conformance_cache
from .stamp_toml import GOVERNANCE_KEYS, StampError, apply_governance, render_toml_value

__all__ = [
    "StampResult",
    "StampableReviewStatus",
    "bundled_registry_root",
    "revision_manifest_path",
    "stamp_revision",
]


class StampableReviewStatus(StrEnum):
    """Review statuses this CLI is willing to WRITE.

    A deliberate narrowing of :class:`~cadrumo.core.revision_review.RevisionReviewStatus`, not a
    second vocabulary: every member's value is byte-identical to its core
    counterpart, and a test pins that correspondence together with the
    deliberate absence of ``operator_reviewed``. The narrowing is what makes the
    CLI's accepted-value list honest at the parse boundary — offering a choice
    the tool would always refuse teaches nothing.

    Because the values ARE the core values, this class is also the coercion
    :func:`stamp_revision` applies to whatever it is handed: a caller passing
    the core ``AUTOMATION_REVIEWED`` member, or the bare string, resolves to the
    member here and is served, while ``operator_reviewed`` in any spelling
    raises. The refusal therefore keys on the VALUE a manifest would carry, not
    on which enum class the caller happened to import.
    """

    PENDING_REVIEW = "pending_review"
    AGENT_REVIEWED = "agent_reviewed"


type ReviewStatusInput = StampableReviewStatus | RevisionReviewStatus | str


#: The arguments that restate a revision's review CLAIM. A request touching any
#: of them is governed by the effective-status guard; ``engineered_by`` is
#: deliberately absent, because authorship is a different fact from signoff.
_REVIEW_AXIS_ARGUMENTS: Final[tuple[str, ...]] = ("review_status", "reviewed_by", "reviewed_at")

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

#: Minimal localization key for the same probe revision. Never written and never
#: resolved against a catalogue: the probe asks only whether a GOVERNANCE
#: combination is legal, and localization is not part of that question -- but the
#: schema requires the field to exist, so the probe must carry one.
#:
#: Declared here beside the period selector rather than inline at the call site,
#: for the reason the selector states. When the schema made this field required,
#: the probe began failing inside the try block and surfaced as "refused
#: governance stamp" on every revision -- a localization change wearing a
#: governance refusal's clothes, which is precisely the disguise the selector's
#: import-time construction exists to prevent.
_PROBE_LOCALIZATION_KEY: Final = "probe"


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
    reviewed_against: str | None

    def rendered(self) -> dict[str, str]:
        """Return the present scalars in canonical TOML form, in emit order."""
        values = {
            "engineered_by": self.engineered_by,
            "review_status": self.review_status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "reviewed_against": self.reviewed_against,
        }
        return {key: render_toml_value(values[key]) for key in GOVERNANCE_KEYS if values[key] is not None}

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
        """Capture the identity and governance fields changed by one stamp."""
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


def bundled_registry_root() -> Path:
    """Return the shipped AEAT registry tree root, resolved.

    The ONE place in this package that names the shipped tree. Every write path
    takes its root as a required argument, so reaching the bundled data is an act
    a caller performs by calling this function — never something that happens
    because an argument was omitted.

    ``importlib.resources`` hands this path out as read-only by contract, and for
    every other consumer in the project it is. The governance stamp is the single
    sanctioned exception: authorship and agent-review provenance cannot be derived
    from the tree, so somebody has to write it into the tree. Isolating that
    exception behind a named function keeps it greppable and keeps the exception
    from spreading by default.
    """
    return Path(bundled_path("registry", "aeat")).resolve()


def revision_manifest_path(modelo: str, revision: str, *, registry_root: Path) -> Path:
    """Resolve one revision's ``revision.toml`` manifest under the registry root.

    Args:
        modelo: Modelo id, e.g. ``"130"``.
        revision: Revision id, e.g. ``"2019-y-siguientes"``.
        registry_root: Registry tree root to resolve under. REQUIRED: see the
            module's own account of what the bundled-tree default cost. Address
            the shipped registry with :func:`bundled_registry_root`.

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
    root = registry_root.resolve()
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
    review_status: ReviewStatusInput | None = None,
    reviewed_by: str | None = None,
    reviewed_at: date | None = None,
    registry_root: Path,
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
        registry_root: Registry tree root to write under. REQUIRED and
            deliberately undefaulted: it once defaulted to the bundled AEAT tree
            and a caller that dropped the argument wrote a fabricated review into
            shipped data. Omitting it is now a :exc:`TypeError` at the call.
            Address the shipped registry with :func:`bundled_registry_root`.

    Returns:
        The :class:`StampResult` describing what changed.

    Raises:
        StampError: The requested review status is outside the vocabulary this
            CLI may write, the manifest already DECLARES a status outside it and
            the request touches the review axis, nothing was supplied to write,
            an authorship claim was supplied together with its clearing, an
            identity names nobody, a reviewer identity reads as an
            already-qualified attribution, the revision is not a compiled record in the
            tree, the resulting stamp is one the schema refuses, or the written
            tree no longer loads. In the last case the manifest is restored to
            its previous bytes before the error is raised.
    """
    review_status = _stampable_status(review_status)
    if engineered_by is not None and clear_engineered_by:
        raise StampError("engineered_by and clear_engineered_by contradict each other; supply one")
    if not any((engineered_by, clear_engineered_by, review_status, reviewed_by, reviewed_at)):
        raise StampError(
            "nothing to stamp: supply at least one of engineered_by, clear_engineered_by, "
            "review_status, reviewed_by, reviewed_at",
        )
    engineered_by = _named_identity(engineered_by, "engineered_by")
    reviewed_by = _named_identity(reviewed_by, "reviewed_by")
    _assert_reviewer_is_not_tier_shaped(reviewed_by)

    manifest = revision_manifest_path(modelo, revision, registry_root=registry_root)
    modelo_dir = manifest.parent.parent.parent
    compiled = _assert_revision_is_compiled(modelo_dir, modelo=modelo, revision=revision)

    # BYTES, not text. ``read_text`` decodes under universal newlines and
    # ``write_text`` re-encodes under the platform's, so a read/write pair on
    # Windows silently expands every LF to CRLF: the shipped manifests are LF, so
    # a "restore" rewrote all eight lines of one and a successful stamp rewrote
    # every line rather than the governance ones. ``git diff`` reads clean
    # through ``text=auto`` normalisation while the working tree carries a
    # whole-file rewrite, which is how it survived three review rounds.
    original_bytes = manifest.read_bytes()
    original = original_bytes.decode(UTF_8_ENCODING)
    declared = _declared_governance(manifest, original, revision)
    _assert_review_axis_is_writable(
        compiled.review_status,
        manifest=manifest,
        requested=(review_status, reviewed_by, reviewed_at),
    )
    _assert_a_new_reviewer_restates_the_date(declared, reviewed_by=reviewed_by, reviewed_at=reviewed_at)
    resolved = _resolve_stamp(
        declared,
        engineered_by=engineered_by,
        clear_engineered_by=clear_engineered_by,
        review_status=review_status,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        scope=compiled.predecessor.revision_id if isinstance(compiled.predecessor, DeclaredPredecessor) else None,
    )
    _assert_schema_accepts(revision, resolved, predecessor=compiled.predecessor)

    rendered = resolved.rendered()
    dropped = declared.declared_keys() - resolved.declared_keys()
    removed = tuple(key for key in GOVERNANCE_KEYS if key in dropped)
    manifest.write_bytes(apply_governance(original, revision, rendered).encode(UTF_8_ENCODING))

    try:
        _assert_revision_is_compiled(modelo_dir, modelo=modelo, revision=revision)
    except StampError:
        manifest.write_bytes(original_bytes)
        raise

    reset_conformance_cache()
    return StampResult(
        manifest=manifest,
        modelo=modelo,
        revision=revision,
        written=rendered,
        removed=removed,
    )


def _stampable_status(value: ReviewStatusInput | None) -> StampableReviewStatus | None:
    """Coerce a requested review status into the vocabulary this CLI may WRITE.

    The first statement of :func:`stamp_revision`, because it is the one
    argument whose annotation is load-bearing rather than descriptive. Most
    refusals in this module protect the FILE — that it stays valid TOML, that
    the loader still accepts it, that a reviewer is not recorded against a
    review the status denies. This one protects the CLAIM the caller STATES,
    and the schema cannot help: ``operator_reviewed`` is a legal registry value,
    so a manifest carrying it compiles cleanly and the post-write reload passes.
    The refusal exists only here, which is why it must be a statement and not a
    type hint.

    It is HALF the guard, and knowing which half matters. This function fires
    only when a status is supplied; an omitted one falls through to whatever the
    manifest declares, so a lone reviewer write against a declared
    ``operator_reviewed`` never reaches this coercion at all.
    :func:`_assert_review_axis_is_writable` is the other half and reads the
    EFFECTIVE status off the file.

    Coercion rather than an identity check on purpose. The narrowed enum's
    values are byte-identical to the core ones, so the core ``AUTOMATION_REVIEWED``
    member and the bare string both resolve to a served member; only the value
    a manifest would actually carry decides. A check like
    ``isinstance(value, StampableReviewStatus)`` would instead refuse a
    perfectly honest caller for importing the other enum, and teach them to
    reach past this function rather than through it.
    """
    if value is None:
        return None
    try:
        return StampableReviewStatus(value)
    except ValueError as exc:
        accepted = ", ".join(repr(member.value) for member in StampableReviewStatus)
        raise StampError(
            f"refusing to write review_status {value!r}: this CLI writes only {accepted}. "
            f"{RevisionReviewStatus.OPERATOR_REVIEWED.value!r} is absent by decision, not by "
            "omission: this CLI is agent-driven, and an agent recording a human's signoff is the "
            "dishonesty the conformance surface exists to detect. Passing the core "
            "RevisionReviewStatus member does not make the claim true. The operator signs off by "
            "editing the revision's revision.toml directly, which the registry schema accepts.",
        ) from exc


def _assert_review_axis_is_writable(
    declared_status: RevisionReviewStatus,
    *,
    manifest: Path,
    requested: tuple[object, ...],
) -> None:
    """Refuse to restate a review claim this CLI could not have written itself.

    The companion to :func:`_stampable_status`, and the half that guards the
    file rather than the argument. That function coerces the REQUESTED status,
    so it fires only when a status is supplied; this one reads the status the
    revision already DECLARES, which is what an omitted argument falls through
    to. A lone reviewer write against a declared ``operator_reviewed`` therefore
    reached disk while the requested-status coercion was the only guard —
    re-attributing a human's signoff to an agent, invisibly to every gate,
    while destroying a name and date nothing in the tree can reconstruct.

    The status comes off the COMPILED revision, not off the manifest text. Both
    readings agree today, and they agree only because the loader refuses
    governance keys declared in a section fragment — which is the laundering path
    that refusal exists to close. A guard whose correctness rests on the
    mechanism it exists to complement is circular: it would fall through to
    "nothing declared" and PERMIT the write in exactly the case the two readings
    diverge, which is the case where a signoff arrived from somewhere the
    manifest does not show. Since :func:`_assert_revision_is_compiled` already
    loads the definition to prove the revision exists, reading the authority's
    own value costs nothing. The manifest text is still parsed, for the merge and
    for the line editor, which are genuinely about the FILE this writer edits.

    Scoped to the REVIEW AXIS on purpose. ``engineered_by`` is absent from
    :data:`_REVIEW_AXIS_ARGUMENTS` because authorship is orthogonal to signoff:
    recording who built an operator-signed revision changes no claim about who
    reviewed it, and a blanket "the resolved status must be stampable" rule
    would refuse that honest write for a reason unrelated to it.

    The predicate is the VOCABULARY, never the single value ``operator_reviewed``,
    so a fourth status added to :class:`~cadrumo.core.revision_review.RevisionReviewStatus`
    without being added here enrols itself in the refusal instead of escaping
    it.

    Args:
        declared_status: The review status the COMPILED revision carries. Never
            absent: the schema fails closed to ``pending_review``, so "declares
            nothing" arrives as the in-vocabulary value it means rather than as a
            :data:`None` this guard would have to interpret.
        manifest: The manifest being stamped, named in the refusal so the caller
            is pointed at the file rather than at a flag.
        requested: The review-axis argument values, in
            :data:`_REVIEW_AXIS_ARGUMENTS` order.

    Raises:
        StampError: The declared status is outside the vocabulary this CLI may
            write and the request touches the review axis. Erasure is refused by
            the same rule as substitution: the ratchet catches destruction only
            after the underivable identity is already gone.
    """
    touched = [name for name, value in zip(_REVIEW_AXIS_ARGUMENTS, requested, strict=True) if value is not None]
    if not touched:
        return
    if declared_status.value in {member.value for member in StampableReviewStatus}:
        return
    raise StampError(
        f"refusing to touch {touched!r}: {manifest} already declares review_status "
        f"{declared_status.value!r}, which is outside the vocabulary this CLI writes "
        f"({', '.join(repr(member.value) for member in StampableReviewStatus)}). Restating the review "
        "axis here would re-attribute a signoff this tool could not have made, and would overwrite a "
        "reviewer identity and date that are underivable by construction, so nothing could restore "
        "them. Both advancing and clearing that claim are edits to the manifest, made by the same hand "
        "that made the claim. engineered_by is unaffected and remains writable.",
    )


def _assert_a_new_reviewer_restates_the_date(
    declared: _Stamp,
    *,
    reviewed_by: str | None,
    reviewed_at: date | None,
) -> None:
    """Refuse a reviewer change that would inherit the previous reviewer's date.

    An omitted field keeps whatever the manifest declares, which is right for
    every scalar except this pair. With a reviewer supplied and no date, the
    merge carried the DECLARED ``reviewed_at`` forward, so a new claim was
    recorded against an old claim's date: ``--reviewed-by agent:second`` over a
    stamp of ``agent:first / 2026-01-15`` produced
    ``agent_reviewed | agent:second | 2026-01-15``. In the one axis that is
    declared rather than derived, that is a record stating a person reviewed a
    revision on a day they did not.

    Ruling: REFUSE, rather than default the date to today. Both close the smear
    and they differ in what they do to a typo correction. Defaulting silently
    rewrites the date whenever the name moves, so correcting a misspelt reviewer
    would move a real review's date to today — trading one false date for
    another, and the tool would be unable to say which. Refusing makes the caller
    state which act they are performing: today for a genuine re-review, the
    original date to correct the name. That is the same shape this module already
    applies to a reviewer supplied against ``pending_review``, which is refused
    rather than quietly dropped, and it follows the standing rule here that
    nothing writes a claim the caller did not make.

    The CLI's today-defaulting is deliberately NOT widened to cover this path.
    It fires when a status is supplied, where "the review is happening now" is
    true by construction; a lone reviewer change carries no such warrant.

    Narrow on purpose. It fires only on a CHANGE of reviewer against a declared
    date: restating the same reviewer inherits a date that is still that
    reviewer's own, moving only the date is an explicit act, and a first review
    has no declared date to inherit.

    Args:
        declared: The stamp the manifest already carries.
        reviewed_by: The requested reviewer, or :data:`None`.
        reviewed_at: The requested review date, or :data:`None`.

    Raises:
        StampError: A different reviewer was supplied with no date while the
            manifest declares one.
    """
    if reviewed_by is None or reviewed_at is not None:
        return
    if declared.reviewed_at is None or declared.reviewed_by is None or reviewed_by == declared.reviewed_by:
        return
    raise StampError(
        f"refusing to record reviewed_by {reviewed_by!r} without a date: the manifest declares the "
        f"review as {declared.reviewed_by!r} on {declared.reviewed_at.isoformat()}, and an omitted date "
        "would carry that date onto the new reviewer, recording them as having reviewed the revision on "
        "a day they did not. State the date the claim belongs to: today's date for a review happening "
        "now, or the declared date when correcting the spelling of the same review's reviewer.",
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


def _assert_reviewer_is_not_tier_shaped(value: str | None) -> None:
    """Refuse a reviewer identity that reads as an already-qualified attribution.

    The governance surfaces render a reviewer joined to the tier that claimed
    them, ``<status>:<name>``, so a scanning reader never meets a bare name. The
    JOINED value is unambiguous whatever the name contains, because no status
    value carries a colon and the join is parsed at the first one — which is why
    a reviewer like ``agent:opus-executor`` is perfectly fine and stays legal.

    The RAW field is the exposed one. It is the datum the manifest declares and
    a payload consumer can read it alone, so a reviewer recorded as
    ``operator_reviewed:<a person's name>`` is, read raw, indistinguishable from
    a genuine operator attribution — an agent-tier stamp that reads as a human
    signoff without ever writing the status this CLI refuses to write. That is
    the same claim the effective-status guard exists to protect, arriving
    through the one field that has no vocabulary.

    So the refusal is exactly that shape and no wider: the leading
    colon-delimited segment may not be a review status. Refusing every colon
    would cost the established ``agent:<name>`` convention and buy nothing, since
    the join was never ambiguous.

    Args:
        value: The trimmed reviewer identity, or :data:`None` when none was
            supplied.

    Raises:
        StampError: The identity's leading segment is a review-status token.
    """
    if value is None:
        return
    leading = value.split(":", 1)[0].strip().casefold()
    if leading not in {member.value.casefold() for member in RevisionReviewStatus}:
        return
    raise StampError(
        f"refusing to record reviewed_by {value!r}: it begins with the review status {leading!r} "
        "followed by the separator this surface uses to join a reviewer to the tier that claimed "
        "them, so the stored value reads on its own as an already-qualified attribution. A stamp "
        "this CLI is willing to write would then be readable as one it is not. Name the reviewer "
        "without a leading status token; a qualifier such as 'agent:<name>' is unaffected.",
    )


def _validation_error_cause(exc: BaseException | None) -> PydanticValidationError | None:
    """Return the nearest :exc:`~pydantic.ValidationError` in ``exc``'s cause chain.

    Every raise site in this module that wraps a registry or schema failure keeps
    the original exception as ``__cause__`` (a bare ``raise ... from exc``), and
    the loader wraps its own :exc:`~pydantic.ValidationError` the same way before
    this module ever sees it. Walking the chain rather than checking ``exc``
    alone is what makes :func:`_safe_exception_detail` work whether the
    validation failure reaches this module directly (the schema probe) or
    nested one layer inside a :class:`~cadrumo.domain.calculations.registry.errors.RegistryError`
    (a loaded revision).
    """
    cause = exc
    while cause is not None:
        if isinstance(cause, PydanticValidationError):
            return cause
        cause = cause.__cause__
    return None


def _safe_exception_detail(exc: BaseException) -> str:
    """Render ``exc`` for a refusal message without echoing an arbitrary literal.

    :exc:`~pydantic.ValidationError` composes its own ``str()`` from
    :meth:`~pydantic.ValidationError.errors`, which appends an ``input_value=``
    fragment holding a length-truncated repr of the WHOLE validated payload —
    including any ``reviewed_by`` or ``engineered_by`` string a caller supplied —
    regardless of what the failing validator's own message says. Measured: a
    short reviewer identity survives that truncation whole and reaches the
    message text; a longer one happens to fall inside the elided middle. Neither
    outcome is something a caller decided, and the module writes registry
    provenance for a domain whose diagnostics must never carry a raw caller
    payload.

    So a message built here never touches ``str(ValidationError)`` or its
    ``input``. When the failure traces back to a :exc:`~pydantic.ValidationError`
    (see :func:`_validation_error_cause`), the message is built only from each
    error's own ``msg`` — the text the failing validator in
    :mod:`~cadrumo.domain.calculations.registry.schema` or
    :mod:`~cadrumo.domain.calculations.registry.schema_governance` composed on
    purpose to be shown, naming the revision, the field, and the shape of the
    refusal. Every other exception this module raises or wraps composes its own
    message the same deliberate way, so ``str(exc)`` is safe for anything that is
    not a validation error.
    """
    validation_error = _validation_error_cause(exc)
    if validation_error is None:
        return str(exc)
    return "; ".join(error["msg"] for error in validation_error.errors(include_url=False, include_input=False))


def _assert_revision_is_compiled(modelo_dir: Path, *, modelo: str, revision: str) -> ModeloRevision:
    """Confirm the revision exists as a COMPILED record, never as a directory listing.

    A subdirectory-blind read of this registry has twice produced wrong verdicts,
    so the revision must be present in the loaded :class:`ModeloDefinition`.
    Re-used after the write as the proof that the loader still accepts the tree.

    The compiled revision is RETURNED rather than discarded. It is the authority
    on what this revision declares, this function already holds it, and the
    effective-status guard needs exactly one field off it — so handing it back
    costs nothing and removes the guard's dependency on a second reading of the
    same facts. See :func:`_assert_review_axis_is_writable`.
    """
    try:
        definition = load_modelo_directory(modelo_dir)
    except RegistryError as exc:
        raise StampError(
            f"modelo {modelo}: registry refuses to load the modelo: {_safe_exception_detail(exc)}",
        ) from exc
    compiled = definition.revisions.get(revision)
    if compiled is None:
        raise StampError(
            f"modelo {modelo}: the loaded tree declares no revision {revision!r}; declared revisions "
            f"are {sorted(definition.revisions)}",
        )
    return compiled


def _declared_governance(manifest: Path, text: str, revision: str) -> _Stamp:
    """Read the governance scalars the manifest already declares."""
    try:
        parsed = parse_toml(text)
    except TomlDecodeError as exc:
        raise StampError(f"{manifest}: revision manifest is not valid TOML: {exc}") from exc
    revisions_raw = parsed.get("revisions")
    if not is_object_mapping(revisions_raw):
        raise StampError(f'{manifest}: manifest declares no [revisions."{revision}"] table')
    revisions = to_str_keyed_dict(
        revisions_raw,
        error_factory=lambda message: StampError(f"{manifest}: {message}"),
    )
    if revision not in revisions:
        raise StampError(f'{manifest}: manifest declares no [revisions."{revision}"] table')
    if len(revisions) != 1:
        raise StampError(
            f"{manifest}: manifest declares {len(revisions)} revision tables; the fragmented layout "
            "requires exactly one so the stamp has a single unambiguous home",
        )
    table_raw = revisions[revision]
    if not is_object_mapping(table_raw):
        raise StampError(f'{manifest}: [revisions."{revision}"] is not a table')
    table = to_str_keyed_dict(
        table_raw,
        error_factory=lambda message: StampError(f"{manifest}: {message}"),
    )
    return _Stamp(
        engineered_by=_declared_text(manifest, table, "engineered_by"),
        review_status=_declared_text(manifest, table, "review_status"),
        reviewed_by=_declared_text(manifest, table, "reviewed_by"),
        reviewed_at=_declared_date(manifest, table),
        reviewed_against=_declared_text(manifest, table, "reviewed_against"),
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
    scope: str | None,
) -> _Stamp:
    """Merge the requested changes onto what the manifest already declares.

    ``scope`` is the predecessor the COMPILED edition declares, or ``None`` when
    it states every row. It is written as ``reviewed_against`` whenever the
    resolved stamp claims a review and dropped otherwise. It is never read off
    the manifest or taken from the caller: a declared scope that disagrees with
    the compiled predecessor never loads, and a caller-supplied one would let the
    stamp name an edition the reviewer did not read against.
    """
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
        return _Stamp(
            engineered_by=author,
            review_status=status,
            reviewed_by=None,
            reviewed_at=None,
            reviewed_against=None,
        )
    return _Stamp(
        engineered_by=author,
        review_status=status,
        reviewed_by=reviewed_by if reviewed_by is not None else declared.reviewed_by,
        reviewed_at=reviewed_at if reviewed_at is not None else declared.reviewed_at,
        reviewed_against=scope,
    )


def _assert_schema_accepts(
    revision: str,
    resolved: _Stamp,
    *,
    predecessor: DeclaredPredecessor | NoPredecessor | None,
) -> None:
    """Ask the real revision schema whether this governance combination is legal.

    A probe revision carrying the intended stamp is validated by
    :class:`ModeloRevision` itself, so the refusal a caller sees here is the same
    refusal registry build would raise. Mirroring the coherence rule in this
    module would let the two drift, and the drift would show up as a manifest
    the loader rejects.

    The probe's own fields carry exactly the reviewer identity and authorship
    string a caller supplied, so the refusal below is built through
    :func:`_safe_exception_detail` rather than a bare ``{exc}`` interpolation —
    see that function for why: pydantic's own ``str(ValidationError)`` echoes a
    length-truncated repr of the WHOLE probe payload, including
    ``reviewed_by``/``engineered_by``, whenever the payload is short enough to
    survive the truncation whole.
    """
    try:
        ModeloRevision(
            id=revision,
            localization_key=_PROBE_LOCALIZATION_KEY,
            valid_from=date(2000, 1, 1),
            period_selector=_PROBE_PERIOD_SELECTOR,
            legal_refs=("probe:art-1",),
            source_refs=("probe-source",),
            engineered_by=resolved.engineered_by,
            review_status=RevisionReviewStatus(resolved.review_status or RevisionReviewStatus.PENDING_REVIEW),
            reviewed_by=resolved.reviewed_by,
            reviewed_at=resolved.reviewed_at,
            reviewed_against=resolved.reviewed_against,
            predecessor=predecessor,
        )
    except (RegistryError, ValueError) as exc:
        raise StampError(
            f"refused governance stamp for revision {revision!r}: {_safe_exception_detail(exc)}",
        ) from exc
