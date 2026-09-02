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

The narrowing is ENFORCED, not annotated
----------------------------------------

The paragraph above is a claim about what this module refuses, so it is only
true if something refuses. For a while nothing did: the narrowed vocabulary was
a TYPE HINT on :func:`stamp_revision` and every line downstream read
``.value`` off whatever object it was handed. The core
:class:`~cadrumo.core.RevisionReviewStatus` is one import away, carries a
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

from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.core.toml import to_str_keyed_dict
from cadrumo.core.type_guards import is_object_mapping
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.loader import load_modelo_directory
from cadrumo.domain.calculations.registry.schema import REVISION_GOVERNANCE_FIELDS, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from .manager import reset_conformance_cache

__all__ = [
    "GOVERNANCE_KEYS",
    "StampError",
    "StampResult",
    "StampableReviewStatus",
    "bundled_registry_root",
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

    Because the values ARE the core values, this class is also the coercion
    :func:`stamp_revision` applies to whatever it is handed: a caller passing
    the core ``AGENT_REVIEWED`` member, or the bare string, resolves to the
    member here and is served, while ``operator_reviewed`` in any spelling
    raises. The refusal therefore keys on the VALUE a manifest would carry, not
    on which enum class the caller happened to import.
    """

    PENDING_REVIEW = "pending_review"
    AGENT_REVIEWED = "agent_reviewed"


type ReviewStatusInput = StampableReviewStatus | RevisionReviewStatus | str


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
    )
    _assert_schema_accepts(revision, resolved)

    rendered = resolved.rendered()
    dropped = declared.declared_keys() - resolved.declared_keys()
    removed = tuple(key for key in GOVERNANCE_KEYS if key in dropped)
    manifest.write_bytes(_apply_governance(original, revision, rendered).encode(UTF_8_ENCODING))

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
    values are byte-identical to the core ones, so the core ``AGENT_REVIEWED``
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
    so a fourth status added to :class:`~cadrumo.core.RevisionReviewStatus`
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
        raise StampError(f"modelo {modelo}: registry refuses to load the modelo: {exc}") from exc
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
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
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
            localization_key=_PROBE_LOCALIZATION_KEY,
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


_QUOTE = '"'
_TRIPLE_QUOTE = '"""'
_LINE_CONTINUATION = "\\\n"

#: Physical width the wrapped form aims for. Deliberately well under BOTH
#: reviewability caps in the tree (520 and 600) rather than tracking either: this
#: module lives in ``dev/`` and the gates in ``src/``, so importing one constant
#: is the wrong direction, and a value comfortably below every cap needs no
#: coordination.
_WRAPPED_NOTE_WIDTH = 90

#: Above this, a rendered assignment is wrapped. Short notes stay single-line, so
#: the common manifest is untouched and diffs stay small.
_WRAP_ASSIGNMENT_ABOVE = 200


def _render_governance_assignment(key: str, rendered_value: str) -> str:
    """Render one ``key = value`` line, wrapping a long note across lines.

    Reviewer notes are prose and routinely run past 2,000 characters. Emitted on
    one line they break the registry reviewability gates, and the sweep to wrap
    them by hand has had to be repeated after each stamping round -- the churn
    starts here, so it is stopped here.

    The wrapped form is a TOML multi-line basic string whose newlines are all
    eaten by line-ending backslashes, so the VALUE is byte-identical to the
    single-line form. Only a plain quoted string is wrapped, and only when it has
    spaces to break at; anything else is returned unchanged rather than risking a
    value the writer cannot reproduce.

    :func:`_without_governance_assignments` already walks an assignment's full
    span, so a multi-line value written here stays replaceable by a later stamp --
    the defect that once made two revisions permanently unstampable.
    """
    single = f"{key} = {rendered_value}"
    if len(single) <= _WRAP_ASSIGNMENT_ABOVE:
        return single
    if not (rendered_value.startswith(_QUOTE) and rendered_value.endswith(_QUOTE)):
        return single
    if rendered_value.startswith(_TRIPLE_QUOTE) or " " not in rendered_value:
        return single
    inner = rendered_value[1:-1]
    words = inner.split(" ")
    line = ""
    out: list[str] = []
    for word in words:
        if line and len(line) + 1 + len(word) > _WRAPPED_NOTE_WIDTH:
            out.append(line + " ")
            line = word
        else:
            line = f"{line} {word}" if line else word
    out.append(line)
    body = _LINE_CONTINUATION.join(out)
    return f"{key} = {_TRIPLE_QUOTE}{_LINE_CONTINUATION}{body}{_TRIPLE_QUOTE}"


def _apply_governance(text: str, revision: str, rendered: dict[str, str]) -> str:
    """Rewrite the manifest's governance keys inside its single revision table.

    Line-oriented on purpose: a full TOML round-trip would reformat every
    hand-authored multi-line array in the file and bury the one-line stamp in an
    unreviewable diff. Only whole ``key = value`` lines for the four governance
    keys are touched; every other line is passed through byte for byte.

    "Byte for byte" includes the LINE TERMINATOR, which is why the joiner is
    read off the input rather than assumed. ``splitlines`` discards the
    terminator it split on, so re-joining with a fixed LF would silently rewrite
    every line of a CRLF manifest — the same whole-file rewrite, arriving from
    the other direction, that writing through ``write_text`` produced on an LF
    one.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    header = f'[revisions."{revision}"]'
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == header)
    except StopIteration as exc:
        # REACHABLE, and it used to carry a pragma claiming otherwise on the
        # ground that ``_declared_governance`` proves the table exists. That
        # proves the table exists in PARSED TOML, never that any line matches
        # this one exact spelling. Measured: both ``[revisions.'<id>']`` and
        # ``[ revisions."<id>" ]`` parse to the same key, load through the real
        # registry loader, and miss here. The line editor needs a literal line to
        # edit, so the narrow match stays and the message names the requirement
        # instead of leaving the caller with a manifest the loader accepts and
        # this writer cannot address.
        raise StampError(
            f"{header} is not present as a whole line in the revision manifest. This writer edits the "
            f"manifest line by line so a hand-authored file stays reviewable, so it needs the table "
            f"header written in exactly that form; an equivalent TOML spelling such as a single-quoted "
            f"or space-padded header parses to the same table and loads cleanly, but cannot be located "
            f"here. Rewrite the header line in the canonical form and stamp again.",
        ) from exc

    end = _revision_table_end(lines, start)
    body = _without_governance_assignments(lines[start + 1 : end])
    while body and not body[-1].strip():
        body.pop()
    body.extend(_render_governance_assignment(key, rendered[key]) for key in GOVERNANCE_KEYS if key in rendered)

    rebuilt = [*lines[:start], lines[start], *body, "", *lines[end:]]
    while rebuilt and not rebuilt[-1].strip():
        rebuilt.pop()
    return newline.join(rebuilt) + newline


def _revision_table_end(lines: list[str], start: int) -> int:
    """Index of the first line after the revision table that ``start`` opens.

    A table ends at the next line that OPENS a new TOML table, but the scan
    cannot simply look for a leading ``[``: a governance value written as a
    multi-line basic string carries arbitrary prose, and a wrapped continuation
    line may legitimately BEGIN with a bracket. Modelo 840 is the worked case --
    its reviewed_by cites AEAT box numbers, and the wrap put ``[13]. VERIFIED
    -- ...`` at the start of a line, which the naive scan read as a table header
    and used to truncate the table thirty lines early. The rebuild then emitted
    the remaining prose outside any table and the manifest stopped parsing, so
    the revision was unstampable through this writer while its neighbours were
    fine.

    Skipping each governance assignment's full span keeps the scan on real
    structure. This is the same span walk :func:`_without_governance_assignments`
    performs; both must agree, or the body slice and the removal disagree about
    where the table ends.
    """
    index = start + 1
    while index < len(lines):
        if _is_governance_line(lines[index]):
            index += _governance_assignment_length(lines, index)
            continue
        if lines[index].startswith("["):
            return index
        index += 1
    return len(lines)


def _without_governance_assignments(body: list[str]) -> list[str]:
    """Return ``body`` with every governance assignment removed, bodies included.

    A governance value is a scalar, but a scalar written as a TOML multi-line
    basic string still occupies several PHYSICAL lines. Dropping only the line
    that carries the key orphans the remaining prose and the closing delimiter
    as bare TOML, and a reviewer note conventionally opening ``agent: ...`` then
    parses as a key with a colon where an equals belongs. That is not
    hypothetical: it refused every attempt to restamp a revision whose
    ``reviewed_by`` had been written in the triple-quoted form, while the
    single-line form beside it stamped cleanly.

    The refusal was the good outcome -- the caller restores the previous bytes
    rather than leaving a broken manifest -- but it made those revisions
    permanently unstampable through this writer.
    """
    kept: list[str] = []
    index = 0
    while index < len(body):
        if _is_governance_line(body[index]):
            index += _governance_assignment_length(body, index)
            continue
        kept.append(body[index])
        index += 1
    return kept


def _governance_assignment_length(body: list[str], index: int) -> int:
    """How many physical lines the governance assignment at ``index`` occupies.

    One, unless its value opens a multi-line basic string that the same line
    does not also close. An unterminated opener runs to the end of the table
    rather than past it, so a malformed manifest cannot make this consume the
    caller's unrelated lines.
    """
    _, _, after = body[index].partition("=")
    if after.count('"""') % 2 == 0:
        return 1
    for offset in range(index + 1, len(body)):
        if '"""' in body[offset]:
            return offset - index + 1
    return len(body) - index


def _is_governance_line(line: str) -> bool:
    """Whether a manifest line OPENS an assignment of one of the four governance scalars.

    Anchored at the start of the line so a governance key name appearing inside
    a continued array element is never mistaken for an assignment. The line is
    the START of the assignment; :func:`_governance_assignment_length` decides
    how far it runs.
    """
    stripped = line.lstrip()
    return any(re.match(rf"{key}\s*=", stripped) for key in GOVERNANCE_KEYS)
