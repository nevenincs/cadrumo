"""The profile overview: what the operator's profile actually contains.

This is the projection behind the profile manager's landing page. It
answers "what do I know about this taxpayer, and what is still blank" by
walking the schema and pairing every declared field with its recorded
value — so a field the operator has not filled in is a visible empty row
rather than an absence they have to infer.

A declaration does not always stand for one row. A repeatable section's
rows and an object field's instances live under an index the schema never
mentions, so the record decides how many there are while the schema
decides what each holds; both are expanded here.

That inversion is the point. The surface this replaces enumerated the
*steps of a setup wizard*: a list of questions with a status glyph, which
told the operator where they were in a process but never what their
profile held. A profile is data, not a process, and the operator should
be looking at the data.

Completeness rides along as a count rather than a gate. Every field is
editable at any time; ``missing_required`` names what filing will
eventually need, so the surface can show progress without ever refusing
to display a profile that is not finished.

Secret-classed values never leave this module in the clear: a field whose
declared :class:`SensitivityClass` is ``SECRET`` carries
:data:`MASKED_PLACEHOLDER` as its value and reports ``masked``, so no
caller can render a secret by accident. The class is read from the
schema's own declaration rather than from a list of field names kept
here, so a newly-declared secret is masked the moment it is declared.

See Also:
    :class:`~cadrumo.application.user_profile.ProfilePreflightService`
        Per-modelo requirements; this module reports schema-level
        completeness, which is the broader "is the profile filled in"
        question rather than "can I file THIS modelo".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from ...core import ClaveMovilRoute
from ...core.classification import SensitivityClass
from ...core.i18n import tr
from ...core.identity import ProfileId
from ...core.json_contract import Notice
from ...core.redaction import ALWAYS_REDACT_KEY_TERMS
from ...core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ...domain.user_profile.labels import profile_field_label, profile_section_title
from ...domain.user_profile.loader import load_user_profile_schema

# ``ProfileSetupState`` is a pydantic FIELD type below, so it must resolve at
# runtime; deferring it to TYPE_CHECKING leaves the model undefined and every
# construction raises. The rest of the domain surface is annotation-only.
from ...domain.user_profile.schema import ProfileFieldType, derived_selector_for_path
from ...domain.user_profile.values import ProfileSetupState
from .completeness import missing_required_field_paths, profile_section_rows, profile_value_is_present
from .projections import record_to_path_values

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ...domain.user_profile.schema import (
        ProfileDerivedSelectorDefinition,
        ProfileFieldDefinition,
        ProfileSchemaDefinition,
        ProfileSectionDefinition,
    )
    from ...domain.user_profile.values import UserProfileRecord


MASKED_PLACEHOLDER: Final[str] = "••••••••"
"""Rendered in place of a secret-classed value.

A fixed-width glyph run rather than the value's own length, so the mask
does not leak how long the secret is.
"""

_MASK_KEYWORDS: Final[frozenset[str]] = ALWAYS_REDACT_KEY_TERMS | frozenset(
    {
        "secreto",
        "contraseña",
        "clave",
        "key",
    },
)
"""Substrings that mark a sensitive fact the schema has NOT classified.

Defence in depth for exactly that case: a fact reaching a
surface under a path no schema field declares still masks if it is named
like a credential.

They are not consulted for a field the schema HAS classified. Reading
them over a declared field let authored prose override an explicit
declaration, which is how ``auth.provider`` came to mask: its
description mentions a password only to say that no password is stored
there, and the heuristic could not tell the difference. A heuristic
pointed at text this project writes is answerable to an editorial
change nobody would review as a security change -- in both directions,
since deleting a word would equally have unmasked a real credential.

Both English and Spanish stems are carried because an undeclared fact's
path may be authored in either language, and a surface that only knew
one of them would leave the other's facts in the clear.

Bare ``key`` deliberately subsumes the compound key names --
``api_key``, ``apikey``, ``private_key``, ``private key`` -- so they are
not listed separately. That subsumption is load-bearing rather than
incidental, and is pinned by a test: trimming ``key`` from this set
would silently unmask every compound key field. It stays a local
addition and must NOT be promoted to the shared base, where it would
match ``header_key``, ``producer_key`` and ``casilla_key`` tree-wide.

The set composes :data:`cadrumo.core.redaction.ALWAYS_REDACT_KEY_TERMS`
rather than redeclaring terms beside it. It previously did not, and was
missing eight base terms -- ``nif``, ``tax_id``, ``nie``, ``bearer``,
``certificate``, ``cookie``, ``authorization``, ``pkcs12`` -- so an
undeclared fact named like a NIF rendered in the clear on this surface
while the logging and live-diagnostic predicates both redacted it. Only
the additions above are declared here; a term that must never diverge
belongs in the base.
"""

_NAMESPACE_FIELD_TYPES: Final[frozenset[ProfileFieldType]] = frozenset(
    {ProfileFieldType.OBJECT, ProfileFieldType.ARRAY},
)
"""Field types whose declared path names a namespace rather than a value.

An ``object`` or ``array`` field is written as indexed instances under its
path -- ``censo.divergencia.{n}.{axis,artefact_value,source}``,
``renta_family.descendiente.{n}.*`` -- and never at the bare path itself.
So the bare path is not a blank waiting to be filled in; it is not a slot
at all, and a row offered for it can only ever be empty. The manager
offered exactly that: one permanently blank ``censo.divergencia`` row,
which counted against the profile's own progress line and accepted a typed
value that no reader in the system ever looks at.

Their instances are therefore discovered from the record. The leaf names
are not declared anywhere -- the writing family chooses them -- which is
what separates these from a repeatable SECTION, whose row fields the
schema does declare and which is why an empty repeatable section can still
show what a row would hold while an empty namespace shows nothing.
"""


class ProfileFieldChoice(BaseModel):
    """One value a field may be answered with: the token stored, the words shown.

    The two halves are separate because they are decided by different
    authorities. The token is the schema's -- it is what gets written and what
    every reader matches on -- while the words are copy, resolved into the
    output language. A surface offering the token as its own label is stating
    that the schema's vocabulary is already readable, which is true of a
    ``régimen`` name and false of ``true``.
    """

    model_config = ConfigDict(frozen=True)

    value: str
    label: str


def profile_field_choices(
    field: ProfileFieldDefinition,
    *,
    path: str | None = None,
) -> tuple[ProfileFieldChoice, ...]:
    """The closed answer set for one field, or empty when it is free text.

    THE authority on "may this field be answered by picking rather than by
    typing", so the manager's edit dialog and the add-row form offer the same
    editor for the same declaration instead of each deciding alone. They did
    decide alone, and disagreed: the add-row form had always offered a boolean
    as Yes/No, while the manager gave it a text box -- so the same field was a
    two-item list on one surface and a guess-the-vocabulary prompt on the
    other, and the manager stored whatever spelling of yes the operator
    happened to reach for.

    A BOOLEAN is a closed set of two, which is why it belongs here rather than
    in a checkbox: a page of mixed fields reads better with two named options
    than with a box whose meaning depends on which row the cursor is on, and
    the same reasoning already governs
    :class:`~cadrumo.core.presentation.FormFieldKind`. The tokens are the
    canonical ``true`` / ``false`` the fact carrier promotes to a real
    :class:`bool`, so picking Yes stores a boolean rather than the word.

    The schema path selects existing canonical copy for choices whose stored
    tokens are dispatch keys rather than operator language. Passing the path
    avoids guessing a field's meaning from an accidentally matching enum set.

    Every other type is free text and returns empty, which is how a caller
    tells "pick one of these" from "type a value".
    """
    if field.type is ProfileFieldType.BOOLEAN:
        return (
            ProfileFieldChoice(value="true", label=tr("flows.confirm.yes")),
            ProfileFieldChoice(value="false", label=tr("flows.confirm.no")),
        )
    if field.type is ProfileFieldType.ENUM:
        if path == PROFILE_OUTPUT_LANGUAGE_PATH:
            return tuple(
                ProfileFieldChoice(
                    value=token,
                    label=tr(f"wizard.setup.profile.output-language.choices.{token}.label"),
                )
                for token in field.enum_values
            )
        if path == "auth.provider":
            return tuple(
                ProfileFieldChoice(value=token, label=tr(f"auth.catalogue.{token}_label"))
                for token in field.enum_values
            )
        if path == "auth.clave_movil_route":
            route_keys = {
                ClaveMovilRoute.QR.value: "flows.manager.action.auth_clave_movil_route_qr",
                ClaveMovilRoute.APP_REQUEST.value: "flows.manager.action.auth_clave_movil_route_app_request",
            }
            return tuple(ProfileFieldChoice(value=token, label=tr(route_keys[token])) for token in field.enum_values)
        return tuple(ProfileFieldChoice(value=token, label=token) for token in field.enum_values)
    return ()


class ProfileFieldView(BaseModel):
    """One schema field paired with whatever the profile records for it."""

    model_config = ConfigDict(frozen=True)

    path: str
    label: str
    value: str | None
    masked: bool
    required: bool
    field_type: ProfileFieldType = Field(default=ProfileFieldType.STRING)
    """What the schema declares this field holds.

    Carried so a surface can offer the editor the value deserves and say what
    shape it accepts. A date, a percentage and a NIF are all "a string you
    type" to a page that does not know the difference, and the operator finds
    out which one they got wrong only after the write door refuses.
    """
    choices: tuple[ProfileFieldChoice, ...] = Field(default=())
    """The closed answer set, or empty for a field that is typed into.

    The manager receives the declaration rather than guessing from the
    current value, so an unanswered enum is still presented as a choice.
    Built by :func:`profile_field_choices`, which is also what the add-row
    form reads, so the two surfaces cannot offer different editors for one
    declaration.
    """
    row_index: str | None = Field(default=None)
    """Which instance of a repeated fact this row belongs to, if any.

    A taxpayer with three socios gets three rows labelled ``NIF``, and
    nothing in the label tells them apart -- the path that does is not a
    column. So the instance is stated here as data and left to the surface
    to present, rather than folded into the label: the label is the
    schema's, translated, and a projection that edited it would be writing
    copy.

    The value is the stored index verbatim, not a display ordinal, because
    it is the identity the fact path itself carries -- what a write to
    ``<section>.<index>.<field>`` addresses, and what row assembly and
    index allocation agree on. Renumbering it for display would leave the
    surface naming a row the store does not have. ``None`` marks a row
    that belongs to no instance -- every ordinary field, and the unindexed
    implicit row the setup wizard writes.
    """

    @property
    def present(self) -> bool:
        """Whether the operator has supplied a value for this field.

        Reads the shared presence rule rather than restating it, so the
        count the operator is shown cannot disagree with the gate that
        decides whether the same profile may file.
        """
        return profile_value_is_present(self.value)


class ProfileSectionView(BaseModel):
    """One schema section and its fields, in declaration order."""

    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    fields: tuple[ProfileFieldView, ...]

    @property
    def present_count(self) -> int:
        return sum(1 for field in self.fields if field.present)

    @property
    def total_count(self) -> int:
        return len(self.fields)


class ProfileOverview(BaseModel):
    """Everything the manager's landing page renders for one profile."""

    model_config = ConfigDict(frozen=True)

    profile_id: ProfileId
    label: str
    setup_state: ProfileSetupState
    sections: tuple[ProfileSectionView, ...]
    missing_required: tuple[str, ...] = Field(default=())
    notices: tuple[Notice, ...] = Field(default=())
    """Typed envelope advisories that apply to this profile projection."""

    @property
    def present_count(self) -> int:
        return sum(section.present_count for section in self.sections)

    @property
    def total_count(self) -> int:
        return sum(section.total_count for section in self.sections)

    @property
    def complete(self) -> bool:
        """Whether every schema-required field now carries a value.

        Deliberately not "every field": optional detail staying blank is a
        finished profile, not an unfinished one.
        """
        return not self.missing_required

    @property
    def missing_required_fields(self) -> tuple[ProfileFieldView, ...]:
        """Schema-labelled field views for every currently missing requirement."""
        missing = frozenset(self.missing_required)
        return tuple(field for section in self.sections for field in section.fields if field.path in missing)


def mask_profile_field(*, path: str, label: str, sensitivity: SensitivityClass | None) -> bool:
    """Decide whether a profile field's value must be masked before display.

    This is the single masking authority for every surface that projects
    profile facts -- the overview behind the manager landing page and the
    read-only status page alike. It is deliberately public and shared:
    two surfaces that decide confidentiality independently will diverge,
    and the direction that divergence takes is a surface exposing a value
    its sibling protects.

    A field the schema classifies is decided by its declaration alone: it
    masks when classed ``SECRET`` and not otherwise. Only a fact the
    schema does not declare falls through to :data:`_MASK_KEYWORDS`,
    which is what "defence in depth" means here -- a net under the
    unclassified, not a second opinion on the classified.

    That fall-through used to run for every non-``SECRET`` field, which
    is the opposite of what this docstring promised and let a field's
    own description decide its confidentiality. It masked
    ``auth.provider`` -- a closed enum naming the authentication mode,
    no more secret than a username -- because the description says a
    password is *not* stored there, while no field in the schema
    declared ``SECRET`` at all. Prose documenting the absence of a
    credential is not evidence of one, and a declaration the schema
    makes explicitly must not be silently overridden by wording.

    Args:
        path: Dotted schema path of the field, e.g. ``auth.dni_nie``.
        label: Operator-facing description, or the path when none exists.
            Read only when ``sensitivity`` is ``None``.
        sensitivity: Declared :class:`SensitivityClass`, or ``None`` for a
            fact the schema does not know (masking then rests on the
            keywords).

    Returns:
        Whether the value must be replaced with
        :data:`MASKED_PLACEHOLDER` before it reaches an operator.
    """
    if sensitivity is SensitivityClass.SECRET:
        return True
    if sensitivity is not None:
        return False
    haystack = f"{path} {label}".casefold()
    return any(keyword in haystack for keyword in _MASK_KEYWORDS)


def _field_view(
    *,
    path: str,
    section_key: str,
    field: ProfileFieldDefinition,
    values: Mapping[str, str],
    label_suffix: str = "",
    row_index: str | None = None,
) -> ProfileFieldView:
    """Pair one path with the field declaring it and whatever the record holds there.

    The declaring field is passed in rather than looked up from the path,
    which is what keeps an indexed row as safe as an unindexed one. A path
    carrying an index matches no schema field, so a lookup would hand the
    masking authority ``sensitivity=None`` and drop the row to the keyword
    net -- and a ``SECRET`` field's rows would then render in the clear
    unless their leaf happened to be named like a credential. Here the
    declaration travels with the row, so an instance of a secret field is
    masked for the same reason the field is.

    Masking reads the schema's own description, never the localized label.
    Whether a value is a secret is a property of the field, not of the
    language it is being read in: scanning translated copy would let a field
    whose Spanish label omits "password" render in the clear while its
    English row masked.
    """
    raw = values.get(path)
    masked = mask_profile_field(path=path, label=field.description, sensitivity=field.sensitivity)
    present = profile_value_is_present(raw)
    return ProfileFieldView(
        path=path,
        label=f"{profile_field_label(section_key, field) or tr('flows.manager.field_unavailable')}{label_suffix}",
        # Mask only a value that exists; masking a blank would render dots
        # for a field the operator has not filled in and read as "something
        # is set here".
        value=MASKED_PLACEHOLDER if (masked and present) else raw,
        masked=masked,
        required=field.required,
        field_type=field.type,
        choices=profile_field_choices(field, path=f"{section_key}.{field.key}"),
        row_index=row_index,
    )


def _repeatable_section_views(
    section: ProfileSectionDefinition,
    values: Mapping[str, str],
    present: frozenset[str],
) -> list[ProfileFieldView]:
    """Expand one repeatable section into a row group per instance it holds.

    A section with three socios yields three groups of the same declared
    fields, addressed at ``section.INDEX.field`` — which is both where the
    values live and where the completeness check already names its missing
    entries, so the two now speak about the same rows.

    A section holding NO rows keeps the single unindexed group, which is
    what the page has always shown. That is the honest answer to "you have
    no socios": the fields a socio would carry, blank. Rendering nothing
    would say the section does not exist, and rendering one blank group
    beside three filled ones — the defect this replaces — says the taxpayer
    has none while they have three.
    """
    rows = tuple(profile_section_rows(section.key, present)) or ("",)
    return [
        _field_view(
            path=f"{section.key}.{row}.{field.key}" if row else f"{section.key}.{field.key}",
            section_key=section.key,
            field=field,
            values=values,
            row_index=row or None,
        )
        for row in rows
        for field in section.fields
    ]


#: Operator-facing suffixes for the ``censo.divergencia`` namespace's three
#: leaves, keyed by the raw stored leaf name. Rendered instead of the bare
#: leaf key (``" (axis)"``, ``" (artefact_value)"``, ``" (source)"``), which
#: leaked the writing family's internal field names onto a localized screen:
#: an operator reading "Divergencias del cotejo censal (artefact_value)" has
#: no way to know that names AEAT's disputed value. Scoped to this one
#: namespace rather than made a generic leaf-translation mechanism, because
#: a leaf name is chosen by whichever family writes the namespace and other
#: namespaces (``renta_family.descendiente`` and siblings) are repeatable
#: SECTIONS with their own declared field labels, not this shape.
_CENSO_DIVERGENCIA_LEAF_LABEL_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "axis": "cli.config.profile.censo.divergencia_leaf_axis",
    "artefact_value": "cli.config.profile.censo.divergencia_leaf_artefact_value",
    "source": "cli.config.profile.censo.divergencia_leaf_source",
}


def resolve_profile_field_label_for_path(schema: ProfileSchemaDefinition, path: str) -> str | None:
    """Return the operator-facing label the schema declares for ``path``, or ``None``.

    Scans every non-repeatable section's own (unindexed) fields for one whose
    ``section.field`` dotted address matches ``path``. A repeatable section's
    row fields and a namespace field's own indexed leaves are deliberately
    not resolved here: a cotejo divergence axis names a plain schema path
    (``contact.fiscal_address``), never an indexed instance.

    Public so both profile-facts surfaces reading a censal cotejo divergence
    — the manager's :func:`build_profile_overview` and the read-only status
    page's fact walk — resolve a divergence axis's raw schema path to the
    SAME operator-facing label, rather than each surface answering "which
    field is this" on its own and risking disagreement.
    """
    for section in schema.sections:
        if section.repeatable:
            continue
        for candidate in section.fields:
            if f"{section.key}.{candidate.key}" == path:
                return profile_field_label(section.key, candidate)
    return None


def _namespace_leaves_by_instance(values: Mapping[str, str], *, prefix: str) -> dict[str, list[str]]:
    """Discover the indexed leaves stored beneath a namespace prefix.

    Both halves of the address are discovered rather than declared: the writing
    family chooses the instance count and the leaf names alike, so the schema can
    say only that the path is a namespace. A path whose index is not a number or
    that carries no leaf at all is not an instance of this namespace and is
    skipped rather than rendered as a malformed row.

    Leaves keep the order the record presents them, which is the order the
    writing family recorded them in, rather than an alphabetisation that would
    scramble a row.
    """
    instances: dict[str, list[str]] = {}
    for path in values:
        if not path.startswith(prefix):
            continue
        index, _, leaf = path[len(prefix) :].partition(".")
        if not leaf or not index.isdigit():
            continue
        leaves = instances.setdefault(index, [])
        if leaf not in leaves:
            leaves.append(leaf)
    return instances


def _namespace_leaf_view(
    *,
    prefix: str,
    section_key: str,
    field: ProfileFieldDefinition,
    values: Mapping[str, str],
    schema: ProfileSchemaDefinition,
    index: str,
    leaf: str,
    detail_number: int,
    is_censo_divergencia: bool,
) -> ProfileFieldView:
    """Render one indexed namespace leaf as an operator-facing row.

    The leaf is named in the label because it is the only thing telling two rows
    of one instance apart. For the ``censo.divergencia`` namespace it is
    translated through :data:`_CENSO_DIVERGENCIA_LEAF_LABEL_LOCALE_KEYS`; every other
    namespace still shows the stored key itself, since the leaf is not prose
    this layer may invent a translation for.
    """
    view = _field_view(
        path=f"{prefix}{index}.{leaf}",
        section_key=section_key,
        field=field,
        values=values,
        label_suffix=(
            f" ({tr(_CENSO_DIVERGENCIA_LEAF_LABEL_LOCALE_KEYS[leaf], default=leaf)})"
            if is_censo_divergencia and leaf in _CENSO_DIVERGENCIA_LEAF_LABEL_LOCALE_KEYS
            else f" ({tr('flows.manager.namespace_detail', number=detail_number)})"
        ),
        row_index=index,
    )
    if is_censo_divergencia and leaf == "axis" and view.value is not None:
        # The stored value is the raw schema PATH of the field AEAT
        # disagrees on (e.g. "contact.fiscal_address"), which no
        # operator reads. Render the field's own label instead, so
        # this row answers "which field" rather than "which path".
        resolved = resolve_profile_field_label_for_path(schema, view.value)
        if resolved is not None:
            return view.model_copy(update={"value": resolved})
    return view


def _namespace_field_views(
    section_key: str,
    field: ProfileFieldDefinition,
    values: Mapping[str, str],
    schema: ProfileSchemaDefinition,
) -> list[ProfileFieldView]:
    """Expand one object/array field into a row per indexed leaf it holds.

    Both halves of the address are discovered, because neither is declared:
    the writing family chooses the instance count and the leaf names alike,
    so the schema can say only that the path is a namespace. An empty
    namespace yields no rows at all — see :data:`_NAMESPACE_FIELD_TYPES`.

    Instances are ordered numerically; leaves keep the order the record
    presents them, which is the order the writing family recorded them in
    (``axis`` before ``artefact_value`` before ``source``) rather than an
    alphabetisation that would scramble a row into ``artefact_value``,
    ``axis``, ``source``.

    The leaf is named in the label because it is the only thing telling two
    rows of one instance apart. For the ``censo.divergencia`` namespace it is
    translated through :data:`_CENSO_DIVERGENCIA_LEAF_LABEL_LOCALE_KEYS`; every
    other namespace still shows the stored key itself, since the leaf is not
    prose this layer may invent a translation for.
    """
    prefix = f"{section_key}.{field.key}."
    is_censo_divergencia = section_key == "censo" and field.key == "divergencia"
    instances = _namespace_leaves_by_instance(values, prefix=prefix)
    return [
        _namespace_leaf_view(
            prefix=prefix,
            section_key=section_key,
            field=field,
            values=values,
            schema=schema,
            index=index,
            leaf=leaf,
            detail_number=detail_number,
            is_censo_divergencia=is_censo_divergencia,
        )
        for index in sorted(instances, key=int)
        for detail_number, leaf in enumerate(instances[index], start=1)
    ]


def _section_field_views(
    section: ProfileSectionDefinition,
    values: Mapping[str, str],
    present: frozenset[str],
    schema: ProfileSchemaDefinition,
    derived_selectors: Iterable[ProfileDerivedSelectorDefinition] = (),
) -> list[ProfileFieldView]:
    """Every row one section contributes, expanding whatever repeats.

    A path the engine derives yields no row at all. The write door refuses it,
    so rendering it would offer the operator a box whose value the record then
    rejects -- the two-surfaces-disagreeing failure the write-door refusal
    exists to prevent, reintroduced at the point of entry. The declarations
    themselves are retired in a later change, at which point this filter
    becomes vacuous rather than wrong.
    """
    if section.repeatable:
        return _repeatable_section_views(section, values, present)
    views: list[ProfileFieldView] = []
    for field in section.fields:
        if derived_selector_for_path(f"{section.key}.{field.key}", derived_selectors) is not None:
            continue
        if field.type in _NAMESPACE_FIELD_TYPES:
            views.extend(_namespace_field_views(section.key, field, values, schema))
            continue
        views.append(
            _field_view(
                path=f"{section.key}.{field.key}",
                section_key=section.key,
                field=field,
                values=values,
            ),
        )
    return views


def build_profile_overview(
    record: UserProfileRecord,
    *,
    label: str = "",
    schema: ProfileSchemaDefinition | None = None,
) -> ProfileOverview:
    """Project ``record`` into the manager's landing-page view.

    The walk is driven by the SCHEMA, not by the record's facts: every
    declared field yields a row whether or not the profile has a value for
    it. A fact-driven walk would render only what is already filled in,
    which is precisely the information the operator does not need — they
    need to see the blanks.

    What the schema cannot say alone is how MANY rows a declaration stands
    for. A repeatable section's rows and an object field's instances both
    live under an index the schema never mentions, so the record decides
    their count and the schema decides their content. Reading only the
    schema meant every such fact was invisible: a taxpayer's socios,
    activities, properties, usage ratios and censal divergences were each
    represented by one blank row whatever they held, on the page whose
    whole purpose is saying what the profile holds.

    Args:
        record: The :class:`UserProfileRecord` whose values populate the view.
        label: Operator-facing display name from the committed capsule projection.
        schema: Optional schema override; the canonical schema when omitted.

    Returns:
        A :class:`ProfileOverview` covering every declared section and field.

    Note:
        Section titles and field labels are resolved into the output
        language at build time, so the returned view is bound to the
        language that was active when it was built. A surface that lets the
        operator change language must rebuild the overview rather than
        re-render the existing one, or the table keeps the old language.
    """
    resolved_schema = schema if schema is not None else load_user_profile_schema()
    values = record_to_path_values(record)

    sections: list[ProfileSectionView] = []
    # Row-aware, and it has to be: a repeatable section's rows live at
    # ``section.INDEX.field``, so testing the unindexed path reported every
    # such required field as missing on every profile forever - the
    # completeness count an operator reads was permanently wrong. Stripping
    # the index would not have fixed it either, because a section with no
    # rows has no facts to strip; the rule that was missing is that an
    # absent row demands nothing.
    missing_required: list[str] = list(missing_required_field_paths(resolved_schema, values))
    # The same presence rule the completeness check reads, so the rows this
    # renders and the rows it reports missing fields for are one set.
    present = frozenset(path for path, value in values.items() if profile_value_is_present(value))
    for section in resolved_schema.sections:
        sections.append(
            ProfileSectionView(
                key=section.key,
                title=profile_section_title(section),
                fields=tuple(
                    _section_field_views(
                        section,
                        values,
                        present,
                        resolved_schema,
                        resolved_schema.derived_selectors,
                    ),
                ),
            ),
        )

    from .cotejo_apply import censo_divergence_notice

    divergence_notice = censo_divergence_notice(record)
    return ProfileOverview(
        profile_id=record.profile_id,
        label=label,
        setup_state=record.setup_state,
        sections=tuple(sections),
        missing_required=tuple(missing_required),
        notices=() if divergence_notice is None else (divergence_notice,),
    )


__all__ = [
    "MASKED_PLACEHOLDER",
    "ProfileFieldChoice",
    "ProfileFieldView",
    "ProfileOverview",
    "ProfileSectionView",
    "build_profile_overview",
    "mask_profile_field",
    "profile_field_choices",
    "resolve_profile_field_label_for_path",
]
