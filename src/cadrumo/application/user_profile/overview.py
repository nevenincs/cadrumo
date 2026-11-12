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

A profile is data, not a process, and the operator should be looking at
the data.

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
    :class:`~cadrumo.application.user_profile.preflight.ProfilePreflightService`
        Per-modelo requirements; this module reports schema-level
        completeness, which is the broader "is the profile filled in"
        question rather than "can I file THIS modelo".
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from collections.abc import Set as AbstractSet
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core.auth_provider import ClaveMovilRoute
from ...core.classification.policies import SensitivityClass
from ...core.i18n.render import lookup_translation, output_language, tr
from ...core.identity.profile import ProfileId
from ...core.json_contract import Notice
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.redaction.rules import ALWAYS_REDACT_KEY_TERMS
from ...domain.user_profile.labels import (
    profile_choice_label,
    profile_field_label,
    profile_field_label_key,
    profile_section_summary,
    profile_section_title,
)

# ``ProfileSetupState`` is a pydantic FIELD type below, so it must resolve at
# runtime; deferring it to TYPE_CHECKING leaves the model undefined and every
# construction raises. The rest of the domain surface is annotation-only.
from ...domain.user_profile.schema import ProfileFieldCodeList, ProfileFieldType, derived_selector_for_path
from ...domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ...domain.user_profile.values import ProfileSetupState, section_field_key
from ..wizard.models import WizardWidget
from .completeness import (
    conditional_profile_missing_required,
    conditional_profile_required_paths,
    missing_required_field_paths,
    pinned_registry_scope,
    profile_section_rows,
    profile_value_is_present,
    schema_requirement_applies,
)
from .field_help import ProfileFieldEjercicioAnswer, profile_field_ejercicio_answers, profile_field_help
from .projections import profile_schema_for_record, record_to_path_values

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ...domain.user_profile.schema import (
        ProfileDerivedSelectorDefinition,
        ProfileFieldDefinition,
        ProfileSchemaDefinition,
        ProfileSectionDefinition,
    )
    from ...domain.user_profile.values import UserProfileRecord
    from ..wizard.models import WizardFlow


_NO_FIELD_HELP: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType[str, tuple[str, ...]]({})
_NO_EJERCICIO_ANSWERS: Final[Mapping[str, ProfileFieldEjercicioAnswer]] = MappingProxyType[
    str, ProfileFieldEjercicioAnswer
]({})
"""The help of a projection built without a setup flow: no field has any."""

MASKED_PLACEHOLDER: Final[str] = "••••••••"
"""Rendered in place of a secret-classed value.

A fixed-width glyph run rather than the value's own length, so the mask
does not leak how long the secret is.
"""

MASK_KEYWORDS: Final[frozenset[str]] = ALWAYS_REDACT_KEY_TERMS | frozenset(
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
them over a declared field would let authored prose override an explicit
declaration: a description that mentions a password only to say that no
password is stored there would be masked, since the heuristic cannot tell
the difference. A heuristic
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

The set composes :data:`cadrumo.core.redaction.rules.ALWAYS_REDACT_KEY_TERMS`
rather than redeclaring terms beside it. Only the additions above are
declared here; a term that must never diverge
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
at all, and a row offered for it can only ever be empty.

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

    model_config = STRICT_FROZEN_CONFIG

    value: str
    label: str


_NO_CODE_LISTS: Final[Mapping[ProfileFieldCodeList, tuple[str, ...]]] = MappingProxyType[
    ProfileFieldCodeList, tuple[str, ...]
]({})
_NO_WIZARD_CHOICES: Final[Mapping[str, tuple[ProfileFieldChoice, ...]]] = MappingProxyType[
    str, tuple[ProfileFieldChoice, ...]
]({})
_PICK_ONE_WIDGETS: Final[frozenset[WizardWidget]] = frozenset({WizardWidget.SELECT, WizardWidget.TEXT})
"""Wizard widgets whose choices are alternatives for one answer.

A checkbox's choices are members of a comma-joined list, which is not an answer
a field typed as a single string can be picked from.
"""


def profile_wizard_choice_sets(flow: WizardFlow | None) -> Mapping[str, tuple[ProfileFieldChoice, ...]]:
    """Return, per profile path, the pick-one choices the setup wizard asks it with.

    A field the schema declares as plain text can still have a closed answer
    set that only the wizard knows: the Modelo 100 declaration type and the
    disability grades are official codes whose words live in the wizard's
    copy. Joining those choices onto the path serves the words the wizard asks
    with from their one producer, so no surface keeps a vocabulary of its own.

    Args:
        flow: The setup flow built for the caller's pinned authority, so the
            codes are the vocabulary the same generation validates. Without it
            no path has wizard choices.

    Returns:
        One entry per path a pick-one question writes and offers choices for.
    """
    if flow is None:
        return _NO_WIZARD_CHOICES
    return {
        question.profile_key: tuple(
            ProfileFieldChoice(value=choice.value, label=tr(choice.label)) for choice in question.choices
        )
        for section in flow.sections
        for question in section.questions
        if question.profile_key is not None and question.choices and question.widget in _PICK_ONE_WIDGETS
    }


def profile_field_choices(
    field: ProfileFieldDefinition,
    *,
    path: str | None = None,
) -> tuple[ProfileFieldChoice, ...]:
    """The closed answer set for one field, or empty when it is free text.

    THE authority on "may this field be answered by picking rather than by
    typing", so the manager's edit dialog and the add-row form offer the same
    editor for the same declaration instead of each deciding alone.

    A BOOLEAN is a closed set of two, which is why it belongs here rather than
    in a checkbox: a page of mixed fields reads better with two named options
    than with a box whose meaning depends on which row the cursor is on, and
    the same reasoning already governs
    ``FormFieldKind``. The tokens are the
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
    if field.type is not ProfileFieldType.ENUM:
        return ()
    return _enum_field_choices(field.enum_values, path=path)


def _enum_choice_rows(
    enum_values: tuple[str, ...], *, label_for: Callable[[str], str]
) -> tuple[ProfileFieldChoice, ...]:
    return tuple(ProfileFieldChoice(value=token, label=label_for(token)) for token in enum_values)


def _enum_field_choices(enum_values: tuple[str, ...], *, path: str | None) -> tuple[ProfileFieldChoice, ...]:
    """Translate an enum through the one canonical vocabulary selected by its path."""
    if path == PROFILE_OUTPUT_LANGUAGE_PATH:
        return _enum_choice_rows(
            enum_values,
            label_for=lambda token: tr(f"wizard.setup.profile.output-language.choices.{token}.label"),
        )
    if path == "auth.provider":
        return _enum_choice_rows(enum_values, label_for=lambda token: tr(f"auth.catalogue.{token}_label"))
    if path == "auth.clave_movil_route":
        route_keys = {
            ClaveMovilRoute.QR.value: "flows.manager.action.auth_clave_movil_route_qr",
            ClaveMovilRoute.APP_REQUEST.value: "flows.manager.action.auth_clave_movil_route_app_request",
        }
        return _enum_choice_rows(enum_values, label_for=lambda token: tr(route_keys[token]))
    if path is not None and "." in path:
        section_key, field_key = path.split(".", 1)
        return _enum_choice_rows(
            enum_values,
            label_for=lambda token: profile_choice_label(section_key, field_key, token),
        )
    return _enum_choice_rows(enum_values, label_for=lambda token: token)


class ProfileFieldView(BaseModel):
    """One schema field paired with whatever the profile records for it."""

    model_config = STRICT_FROZEN_CONFIG

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
    country_options: tuple[str, ...] = Field(default=())
    """The country codes offered for a field typed as a code; any code of its shape stays allowed."""
    choices: tuple[ProfileFieldChoice, ...] = Field(default=())
    """The closed answer set, or empty for a field that is typed into.

    The manager receives the declaration rather than guessing from the
    current value, so an unanswered enum is still presented as a choice.
    Built by :func:`profile_field_choices`, which is also what the add-row
    form reads, so the two surfaces cannot offer different editors for one
    declaration.
    """
    help: tuple[str, ...] | None = Field(default=None)
    """The setup wizard's copy for this field, one paragraph per entry, or ``None``.

    Its prompt, its help text when it has one, and a ``label: description``
    line for each choice that carries a description, exactly as
    :func:`~cadrumo.application.user_profile.field_help.profile_field_help`
    remaps them. ``None`` for a field no wizard question writes;
    :attr:`about` explains that field instead."""
    about: str = Field(default="")
    """The schema's own description of the field, the explanation of last resort."""
    ejercicio_answer: ProfileFieldEjercicioAnswer | None = Field(default=None)
    """How a field stated per ejercicio is answered, or ``None`` for a field holding one value."""
    references_section: str | None = Field(default=None)
    """The repeatable section one of whose rows this field names, or ``None``.

    Declared by the schema, so a generic editor offers the rows of that section
    to pick from instead of asking for a row key.
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


def relocalize_profile_field(view: ProfileFieldView) -> ProfileFieldView:
    """Reword one held field without reading its record or changing any edit witness.

    Indexed repeatable paths retain their instance identity; the declared
    field is the section's final path component, as the overview writer uses.
    Unknown supplied views keep their original label rather than inventing one.
    The help is the backend's served copy and is replaced when the overview is
    read again; this function holds it rather than re-deriving it, because the
    wizard flow it comes from exists only inside a leased authority operation.
    """
    section, separator, remainder = view.path.partition(".")
    if not separator:
        return view
    field_key = remainder.rsplit(".", 1)[-1]
    label_key = profile_field_label_key(section, field_key)
    label = lookup_translation(label_key, locale=output_language())
    if label is None:
        return view
    choices = view.choices
    if view.field_type is ProfileFieldType.BOOLEAN:
        choices = tuple(
            ProfileFieldChoice(
                value=item.value, label=tr("flows.confirm.yes" if item.value == "true" else "flows.confirm.no")
            )
            for item in choices
        )
    elif view.field_type is ProfileFieldType.ENUM:
        choices = _enum_field_choices(tuple(item.value for item in choices), path=f"{section}.{field_key}")
    return view.model_copy(update={"label": label, "choices": choices})


class ProfileSectionView(BaseModel):
    """One schema section and its fields, in declaration order."""

    model_config = STRICT_FROZEN_CONFIG

    key: str
    title: str
    summary: str
    """What the section is for, in one sentence of the output language."""
    repeatable: bool
    fields: tuple[ProfileFieldView, ...]

    @property
    def present_count(self) -> int:
        """Return the number of fields carrying values in this section."""
        return sum(1 for field in self.fields if field.present)

    @property
    def total_count(self) -> int:
        """Return the number of declared fields in this section."""
        return len(self.fields)


class ProfileOverview(BaseModel):
    """Everything the manager's landing page renders for one profile."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: ProfileId
    record_revision: int
    content_digest: str
    label: str
    setup_state: ProfileSetupState
    sections: tuple[ProfileSectionView, ...]
    missing_required: tuple[str, ...] = Field(default=())
    notices: tuple[Notice, ...] = Field(default=())
    """Typed envelope advisories that apply to this profile projection."""

    @property
    def present_count(self) -> int:
        """Return the total number of fields carrying values across sections."""
        return sum(section.present_count for section in self.sections)

    @property
    def total_count(self) -> int:
        """Return the total number of declared fields across sections."""
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
    schema does not declare falls through to :data:`MASK_KEYWORDS`,
    which is what "defence in depth" means here -- a net under the
    unclassified, not a second opinion on the classified.

    Prose documenting the absence of a credential is not evidence of one,
    and a declaration the schema makes explicitly must not be silently
    overridden by wording.

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
    return any(keyword in haystack for keyword in MASK_KEYWORDS)


def _field_view(
    *,
    path: str,
    section_key: str,
    field: ProfileFieldDefinition,
    values: Mapping[str, str],
    help_lines: tuple[str, ...] | None = None,
    label_suffix: str = "",
    row_index: str | None = None,
    conditionally_required: frozenset[str] = frozenset(),
    code_lists: Mapping[ProfileFieldCodeList, tuple[str, ...]] = _NO_CODE_LISTS,
    wizard_choices: Mapping[str, tuple[ProfileFieldChoice, ...]] = _NO_WIZARD_CHOICES,
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
    # The schema's own closed set wins; the wizard's words fill in only for a
    # field the schema leaves as typed text.
    choices = profile_field_choices(field, path=f"{section_key}.{field.key}") or wizard_choices.get(
        f"{section_key}.{field.key}", ()
    )
    return ProfileFieldView(
        path=path,
        label=f"{profile_field_label(section_key, field) or tr('flows.manager.field_unavailable')}{label_suffix}",
        # Mask only a value that exists; masking a blank would render dots
        # for a field the operator has not filled in and read as "something
        # is set here".
        value=MASKED_PLACEHOLDER if (masked and present) else raw,
        masked=masked,
        required=(field.required and schema_requirement_applies(path, values)) or path in conditionally_required,
        field_type=field.type,
        country_options=() if field.code_list is None else code_lists.get(field.code_list, ()),
        choices=choices,
        help=help_lines,
        about=field.description,
        references_section=field.references_section,
        row_index=row_index,
    )


def _required_row_paths(
    section: ProfileSectionDefinition,
    row: str,
    field: ProfileFieldDefinition,
    conditionally_required: frozenset[str],
) -> frozenset[str]:
    """The row path to mark required, where the section's own field is required."""
    if f"{section.key}.{field.key}" not in conditionally_required:
        return frozenset[str]()
    return frozenset({f"{section.key}.{row}.{field.key}" if row else f"{section.key}.{field.key}"})


def _repeatable_section_views(
    section: ProfileSectionDefinition,
    values: Mapping[str, str],
    present: frozenset[str],
    field_help: Mapping[str, tuple[str, ...]],
    conditionally_required: frozenset[str] = frozenset(),
    code_lists: Mapping[ProfileFieldCodeList, tuple[str, ...]] = _NO_CODE_LISTS,
    wizard_choices: Mapping[str, tuple[ProfileFieldChoice, ...]] = _NO_WIZARD_CHOICES,
) -> list[ProfileFieldView]:
    """Expand one repeatable section into a row group per instance it holds.

    A section with three socios yields three groups of the same declared
    fields, addressed at ``section.INDEX.field`` — which is both where the
    values live and where the completeness check already names its missing
    entries, so the two speak about the same rows.

    A section holding NO rows keeps the single unindexed group. That is the
    honest answer to "you have no socios": the fields a socio would carry,
    blank. Rendering nothing would say the section does not exist, and
    rendering one blank group beside three filled ones says the taxpayer has
    none while they have three.
    """
    rows = tuple(profile_section_rows(section.key, present)) or ("",)
    return [
        _field_view(
            path=f"{section.key}.{row}.{field.key}" if row else f"{section.key}.{field.key}",
            section_key=section.key,
            field=field,
            values=values,
            help_lines=field_help.get(f"{section.key}.{field.key}"),
            # A requirement declared for a repeatable section's field holds for
            # every row of it, the single blank row a section with no rows
            # stands for included -- and that is the row the filer fills in.
            # Reading only the indexed path left it unmarked, so the page
            # offered no required entry while the filing gate demanded one.
            conditionally_required=_required_row_paths(section, row, field, conditionally_required),
            row_index=row or None,
            code_lists=code_lists,
            wizard_choices=wizard_choices,
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
            f" ({tr(_CENSO_DIVERGENCIA_LEAF_LABEL_LOCALE_KEYS[leaf])})"
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
    field_help: Mapping[str, tuple[str, ...]],
    derived_selectors: Iterable[ProfileDerivedSelectorDefinition] = (),
    conditionally_required: frozenset[str] = frozenset(),
    code_lists: Mapping[ProfileFieldCodeList, tuple[str, ...]] = _NO_CODE_LISTS,
    wizard_choices: Mapping[str, tuple[ProfileFieldChoice, ...]] = _NO_WIZARD_CHOICES,
) -> list[ProfileFieldView]:
    """Every row one section contributes, expanding whatever repeats.

    A path the engine derives yields no row at all. The write door refuses it,
    so rendering it would offer the operator a box whose value the record then
    rejects -- the two-surfaces-disagreeing failure the write-door refusal
    exists to prevent, reintroduced at the point of entry.
    """
    if section.repeatable:
        return _repeatable_section_views(
            section,
            values,
            present,
            field_help,
            conditionally_required,
            code_lists,
            wizard_choices,
        )
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
                help_lines=field_help.get(f"{section.key}.{field.key}"),
                conditionally_required=conditionally_required,
                code_lists=code_lists,
                wizard_choices=wizard_choices,
            ),
        )
    return views


def _declared_only(paths: Iterable[str], declared: AbstractSet[str]) -> tuple[str, ...]:
    """Keep the paths whose field key the schema declares."""
    return tuple(path for path in paths if section_field_key(path) in declared)


def _required_field_paths(
    record: UserProfileRecord,
    resolved_schema: ProfileSchemaDefinition,
    values: Mapping[str, str],
) -> tuple[list[str], frozenset[str]]:
    """Return the missing required paths and the conditionally required path set."""
    # Row-aware, and it has to be: a repeatable section's rows live at
    # ``section.INDEX.field``, so testing the unindexed path reported every
    # such required field as missing on every profile forever - the
    # completeness count an operator reads was permanently wrong. Stripping
    # the index would not have fixed it either, because a section with no
    # rows has no facts to strip; the rule that was missing is that an
    # absent row demands nothing.
    missing_required: list[str] = list(missing_required_field_paths(resolved_schema, values))
    # Cross-field requirements come from the same completeness contract the
    # taxpayer projection enforces, so the manager never lists fewer required
    # fields than a filing or the workbench will demand.
    # The profile-status baseline for modelo work is READ from the gate that
    # refuses on it rather than restated here. That gate is the authority on
    # what filing-grade work needs, and while this surface held its own answer
    # the header said every required detail was filled in and creating a
    # declaration was refused for want of one of them. The import is local
    # because the gate reads this package's own completeness and preflight
    # contracts, so a module-level one would close a cycle.
    from ..modelo.profile_readiness_gate import (
        modelo_work_profile_baseline_missing_paths,
        modelo_work_profile_baseline_paths,
    )

    # Only a path this schema declares: a baseline fact the resolved schema has
    # no field for has no row to fill in either, and naming it would report a
    # blank the page cannot show.
    declared = {f"{section.key}.{field.key}" for section in resolved_schema.sections for field in section.fields}
    # One pinned generation for the whole walk: the conditional rules and the
    # baseline read the same governed entity-type and income-category
    # vocabularies, and two scopes could judge them against two generations.
    with pinned_registry_scope():
        baseline_required = _declared_only(modelo_work_profile_baseline_paths(record), declared)
        conditionally_required = frozenset((*conditional_profile_required_paths(values), *baseline_required))
        missing_required.extend(
            path for path in conditional_profile_missing_required(values) if path not in missing_required
        )
        # A baseline path is unindexed, so a blank fact already reported at its
        # own row path is the same unfilled detail, not counted twice.
        reported = {section_field_key(path) for path in missing_required}
        missing_required.extend(
            path
            for path in _declared_only(modelo_work_profile_baseline_missing_paths(record), declared)
            if section_field_key(path) not in reported
        )
    return missing_required, conditionally_required


def build_profile_overview(
    record: UserProfileRecord,
    *,
    label: str = "",
    schema: ProfileSchemaDefinition | None = None,
    flow: WizardFlow | None = None,
    code_lists: Mapping[ProfileFieldCodeList, tuple[str, ...]] = _NO_CODE_LISTS,
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
        flow: The setup flow built for the caller's pinned authority. Its
            question copy becomes each field's help, so a surface shows the
            words the wizard asks with. Without it no field carries help and
            :attr:`ProfileFieldView.about` explains every field.
        code_lists: The code lists the caller's pinned authority holds. Without
            them a field declaring one is simply typed into.

    Returns:
        A :class:`ProfileOverview` covering every declared section and field.

    Note:
        Section titles and field labels are resolved into the output
        language at build time, so the returned view is bound to the
        language that was active when it was built. A surface that lets the
        operator change language must rebuild the overview rather than
        re-render the existing one, or the table keeps the old language.
    """
    resolved_schema = profile_schema_for_record(record, schema=schema)
    values = record_to_path_values(record)
    field_help = _NO_FIELD_HELP if flow is None else profile_field_help(flow)
    wizard_choices = profile_wizard_choice_sets(flow)
    ejercicio_answers = _NO_EJERCICIO_ANSWERS if flow is None else profile_field_ejercicio_answers(flow, record.facts)

    missing_required, conditionally_required = _required_field_paths(record, resolved_schema, values)
    # The same presence rule the completeness check reads, so the rows this
    # renders and the rows it reports missing fields for are one set.
    present = frozenset(path for path, value in values.items() if profile_value_is_present(value))
    sections = [
        ProfileSectionView(
            key=section.key,
            title=profile_section_title(section),
            summary=profile_section_summary(section),
            repeatable=section.repeatable,
            fields=tuple(
                view.model_copy(update={"ejercicio_answer": ejercicio_answers.get(view.path)})
                for view in _section_field_views(
                    section,
                    values,
                    present,
                    resolved_schema,
                    field_help,
                    resolved_schema.derived_selectors,
                    conditionally_required,
                    code_lists,
                    wizard_choices,
                )
            ),
        )
        for section in resolved_schema.sections
    ]

    from .cotejo_apply import censo_divergence_notice

    divergence_notice = censo_divergence_notice(record)
    return ProfileOverview(
        profile_id=record.profile_id,
        record_revision=record.record_revision,
        content_digest=record.content_digest,
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
    "profile_wizard_choice_sets",
    "resolve_profile_field_label_for_path",
]
