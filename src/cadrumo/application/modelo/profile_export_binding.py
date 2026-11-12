"""Profile-sourced values addressed on the exported declaration.

The export-shaped counterpart to the calculation-shaped resolution in
:mod:`.profile_binding`. Both read the SAME fact index and the SAME
per-binding resolution -- this module adds only the export-side shaping, so a
profile fact cannot mean one thing to the calculation engine and another to the
filed artefact. It is a family module, not a second authority: the fact index
and single-binding resolution stay owned next door and are imported, never
reimplemented.

Split out when ``profile_binding`` crossed its module size budget. The
calculation and export halves genuinely are two cohesive concerns over one
shared substrate, which is the split the budget forced and the shape the
per-family binding modules elsewhere in the tree already use.

The same export shaping also answers the calculation for a bound TEXT casilla:
a declarant-identity casilla reads its profile fact through
:func:`resolve_profile_text_casilla_inputs`, so the value the calculation holds
for it is the value the filed record addresses.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from pydantic import ValidationError

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.filing_producer_key import FilingProducerKey
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids, revision_bindings_by_id
from ...domain.calculations.registry.binding_value_contract import BindingValueChannel
from ...domain.calculations.registry.casilla_membership import text_family_casilla_ids
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.profile_bindings import ProfileProvider
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.contribuyente.entity_type import entity_type_natural_person_token
from ...domain.deadlines.errors import ProfileError
from ...domain.user_profile.errors import ProfileNotFoundError, UserProfileError
from ...domain.user_profile.registry_contract import profile_binding_selectors
from ...domain.user_profile.schema import (
    ProfileDerivedSelectorDefinition,
    ProfileSchemaDefinition,
    derived_selector_for_path,
)
from ...domain.user_profile.values import UserProfileFactValue, UserProfileRecord, compose_legal_full_name
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..filing.export_producer_m303 import M303ProfileLexicals, m303_profile_lexicals
from ..filing.identity_contact_producer import identity_contact_producer_values
from ..filing.producer_profile_facts import (
    IDENTITY_LEGAL_NAME_PATH,
    IDENTITY_NAME_PATH,
    IDENTITY_SURNAMES_PATH,
    IDENTITY_TAX_ID_PATH,
)
from ..filing.producer_snapshot import DeclarationContactFacts, PresenterIdentity, TaxpayerIdentityFacts

# Reuse the public defining module's canonical fact-index and scalar resolver;
# export shaping must not grow a second profile fact authority.
from ..user_profile.projections import profile_fact_index, projection_for_taxpayer
from ..user_profile.validation import profile_text_too_long_error
from .profile_binding import resolve_profile_binding_value
from .profile_derived_facts import (
    inject_derived_activity_tipo_clave_fact,
    inject_derived_cash_election_fact,
    inject_derived_estimation_modality_fact,
)

_SURNAMES_NAME_FORMAT = "surnames_name"

#: Stored profile fact paths the export reads besides the identity ones, which
#: live beside the producer-fact door that names them.
_ENTITY_TYPE_KEY = "taxpayer_type.entity_type"
_CONTACT_PERSON_PHONE_KEY = "contact.contact_person_phone"
_CONTACT_PERSON_NAME_KEY = "contact.contact_person_name"

#: The stored profile fact to correct when a bounded producer field overruns.
_IDENTITY_TEXT_PROFILE_FACTS: Mapping[str, str] = {
    "legal_name": IDENTITY_LEGAL_NAME_PATH,
    "given_name": IDENTITY_NAME_PATH,
    "surnames": IDENTITY_SURNAMES_PATH,
    "full_name": IDENTITY_SURNAMES_PATH,
}
_CONTACT_TEXT_PROFILE_FACTS: Mapping[str, str] = {
    "phone": _CONTACT_PERSON_PHONE_KEY,
    "full_name": _CONTACT_PERSON_NAME_KEY,
}


@dataclass(frozen=True, slots=True)
class ProfileTextCasillaGap:
    """A required profile-bound text casilla the declarant's profile leaves empty.

    ``profile_fields`` are the profile paths the binding reads, so the operator
    is told which fact to declare rather than which casilla came out blank.
    """

    casilla_id: CasillaId
    binding_id: BindingId
    profile_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProfileTextCasillaInputs:
    """Text inputs a revision's profile-bound text casillas take from the profile.

    ``values`` feeds the calculation's text channel. ``gaps`` names every
    REQUIRED such casilla whose profile facts are absent; it stays absent in the
    calculation and is reported, never filled with a placeholder.
    """

    values: dict[CasillaId, str]
    gaps: tuple[ProfileTextCasillaGap, ...]


def _profile_text_casilla_bindings(
    casilla: CasillaDefinition,
    bindings: Mapping[BindingId, BindingDefinition],
    fact_index: Mapping[str, UserProfileFactValue],
) -> tuple[BindingDefinition, ...]:
    return tuple(
        binding
        for binding_id in bound_casilla_binding_ids(casilla)
        if (binding := bindings.get(binding_id)) is not None
        and isinstance(binding.provider, ProfileProvider)
        and binding.value.channel is BindingValueChannel.TEXT
        and _profile_export_binding_applies(binding, fact_index)
    )


def _first_profile_text_value(declared: tuple[UserProfileFactValue, ...]) -> str | None:
    return next((text for fact in declared if (text := _profile_text_spelling(fact)) is not None), None)


def profile_text_fact_index(
    record: object,
    schema: ProfileSchemaDefinition,
    *,
    operation: PinnedAuthorityOperation,
) -> dict[str, UserProfileFactValue]:
    """Return the fact index a bound text casilla reads, with its engine-derived claves.

    Casilla 0168's modality clave is derived from the declared estimation regime and
    casilla 0166's tipo de actividad clave from the activities' censal tipo under it,
    so the text channel reads the derived values and never ones stored at the paths.
    """
    fact_index = profile_fact_index(record, schema)
    inject_derived_estimation_modality_fact(fact_index, operation=operation)
    inject_derived_activity_tipo_clave_fact(fact_index)
    return fact_index


def resolve_profile_text_casilla_inputs(
    revision: ModeloRevision,
    fact_index: Mapping[str, UserProfileFactValue],
) -> ProfileTextCasillaInputs:
    """Resolve each bound text casilla whose binding reads a text fact of the profile.

    The calculation half of the export resolution above: the same applicability
    gate and the same format-aware value, keyed by casilla instead of by
    dictionary field. A declarant-identity casilla -- a NIF, an "apellidos y
    nombre o razón social" -- therefore holds exactly what the filed record
    states for it, and the calculation stops reporting it as unsupplied.

    Only a binding whose value contract declares the text channel is read: an
    enum, date or numeric profile fact has its own channel and its own spelling,
    and rendering it as text here would give it a second one. A binding gated by
    ``required_when_profile_key`` whose precondition does not hold contributes
    nothing and is not a gap, because the slot does not exist for this filer.

    A text answer made only of digits -- a marital-status or declaration-type
    code -- is stored by the profile as a number, and is spelled here as the
    canonical decimal token, the spelling the bound-value channel gives the same
    casilla. A gap is reported only when the profile declares none of the
    binding's facts; a declared fact with no text spelling (a date) is not a
    missing declaration, and the filing validator still reports the casilla.

    Args:
        revision: The :class:`ModeloRevision` whose bound casillas are resolved.
        fact_index: The declarant's profile fact index.

    Returns:
        The resolved text values and the required casillas left empty.
    """
    bindings = revision_bindings_by_id(revision)
    text_casilla_ids = text_family_casilla_ids(revision.casillas)
    values: dict[CasillaId, str] = {}
    gaps: list[ProfileTextCasillaGap] = []
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND or casilla.id not in text_casilla_ids:
            continue
        profile_bindings = _profile_text_casilla_bindings(casilla, bindings, fact_index)
        if not profile_bindings:
            continue
        declared = tuple(_profile_export_value(binding, fact_index) for binding in profile_bindings)
        value = _first_profile_text_value(declared)
        if value is not None:
            values[casilla.id] = value
        elif casilla.required and all(_profile_fact_is_blank(fact) for fact in declared):
            primary = profile_bindings[0]
            gaps.append(
                ProfileTextCasillaGap(
                    casilla_id=casilla.id,
                    binding_id=primary.id,
                    profile_fields=_profile_value_fields(primary),
                ),
            )
    return ProfileTextCasillaInputs(values=values, gaps=tuple(gaps))


def _profile_text_spelling(value: UserProfileFactValue) -> str | None:
    """Return a text-channel profile fact's spelling, or ``None`` when it has no text form.

    A text fact whose characters form a plain decimal, such as the ``"1"`` of an
    individual ``renta_filing.declaration_type``, comes back from the stored
    record as a :class:`~decimal.Decimal`: the record restores JSON-serialised
    numbers without consulting the field's declared type. ``str`` gives back
    exactly the characters that restore accepted, so the casilla holds what the
    operator declared instead of being reported as unsupplied.
    """
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, Decimal) or (isinstance(value, int) and not isinstance(value, bool)):
        return str(value)
    return None


def _profile_fact_is_blank(value: UserProfileFactValue) -> bool:
    """Whether the profile leaves a binding's fact undeclared."""
    return value is None or (isinstance(value, str) and not value.strip())


def _profile_value_fields(binding: BindingDefinition) -> tuple[str, ...]:
    """Return the profile paths a binding's value is read from, without its gate."""
    provider = binding.provider
    gate = provider.required_when_profile_key if isinstance(provider, ProfileProvider) else None
    return tuple(selector for selector in profile_binding_selectors(provider) if selector != gate)


def profile_text_casilla_gap_diagnostics(
    revision: ModeloRevision,
    fact_index: Mapping[str, UserProfileFactValue],
    *,
    supplied_casilla_ids: Collection[CasillaId],
    derived_selectors: tuple[ProfileDerivedSelectorDefinition, ...],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise on each required profile-bound text casilla the profile leaves empty.

    The casilla stays absent in the calculation; this is what tells the operator
    which profile fact would fill it. A casilla the calculation holds a value
    for through any other channel -- the operator's own text, or a bound value
    -- is not a gap, because that value is what the calculation files for it.
    A binding that reads an engine-derived path names the facts that path is
    derived from, because those are what the operator can declare.

    Args:
        revision: The calculated :class:`ModeloRevision`.
        fact_index: The declarant's profile fact index.
        supplied_casilla_ids: Casillas the calculated revision holds an input
            value for, whichever channel supplied it.
        derived_selectors: The profile schema's engine-derived paths.

    Returns:
        One ``unresolved_binding`` advisory per empty required casilla, carrying
        the casilla's and the binding's own grounding.
    """
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = revision_bindings_by_id(revision)
    diagnostics: list[CalculationSourceDiagnostic] = []
    for gap in resolve_profile_text_casilla_inputs(revision, fact_index).gaps:
        if gap.casilla_id in supplied_casilla_ids:
            continue
        casilla = casillas[gap.casilla_id]
        binding = bindings[gap.binding_id]
        fields = ", ".join(_settable_profile_fields(gap.profile_fields, derived_selectors))
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="unresolved_binding",
                source_kind=BindingSourceKind.PROFILE.value,
                binding_id=gap.binding_id,
                casilla_id=gap.casilla_id,
                message=(
                    f"casilla {gap.casilla_id!r} takes its value from the profile through binding "
                    f"{gap.binding_id!r}, and the active profile declares none of {fields}; the casilla "
                    "stays empty rather than holding a placeholder"
                ),
                # Non-command prose: the remedy is projected into notice context,
                # which reserves executable command identity for Notice.action.
                remedy=f"Declare {fields} on the active profile, then recalculate",
                legal_refs=tuple(dict.fromkeys((*casilla.legal_refs, *binding.legal_refs))),
                source_refs=tuple(dict.fromkeys((*casilla.source_refs, *binding.source_refs))),
            ),
        )
    return tuple(diagnostics)


def _settable_profile_fields(
    fields: tuple[str, ...],
    derived_selectors: tuple[ProfileDerivedSelectorDefinition, ...],
) -> tuple[str, ...]:
    """Replace each engine-derived path by the profile facts it is derived from."""
    settable: list[str] = []
    for field in fields:
        derived = derived_selector_for_path(field, derived_selectors)
        settable.extend(derived.derived_from if derived is not None else (field,))
    return tuple(dict.fromkeys(settable))


def _profile_export_binding_applies(
    binding: BindingDefinition,
    fact_index: Mapping[str, UserProfileFactValue],
) -> bool:
    """Whether a conditional export binding's declared precondition holds.

    A binding carrying ``required_when_profile_key`` addresses a slot that only
    exists for some filers: the spouse identity rows (``DP_APENOM_C``,
    ``DPNIF_C``, ``SEXO_C``, ``DPFNAC_C``) belong on a declaración conjunta and
    nowhere else. Writing one unconditionally would put a spouse's name, NIF,
    sex and birth date onto an INDIVIDUAL filing -- a disclosure the taxpayer
    never made, on an artefact they file under their own signature. That is why
    the gate is part of the minimum correct unit here and not a later
    refinement.

    An ABSENT gate fact is not satisfied: the condition must be affirmatively
    met, so a profile that never answered the question writes nothing rather
    than defaulting into disclosure. The read uses the same
    ``str(...).strip()`` shape this module's marital and autonomic derivations
    already apply to ``renta_filing.declaration_type``, and folds case so a
    stored boolean ``True`` matches a registry-declared ``"true"``.
    """
    provider = binding.provider
    if not isinstance(provider, ProfileProvider):
        return True
    gate_key = provider.required_when_profile_key
    if gate_key is None:
        return True
    expected = (provider.required_when_value or "").strip()
    actual = str(fact_index.get(gate_key, "")).strip()
    return bool(expected) and actual.casefold() == expected.casefold()


def _profile_export_value(
    binding: BindingDefinition,
    fact_index: Mapping[str, UserProfileFactValue],
) -> UserProfileFactValue | None:
    """Resolve one export binding's value, honouring a declared multi-key format.

    :func:`resolve_profile_binding_value` returns the FIRST non-blank selector value, which is
    right for a binding whose keys are fallbacks but wrong for one whose keys
    are PARTS: ``DP_APENOM_D`` declares ``("identity.surnames",
    "identity.name")`` with ``format = "surnames_name"``, and taking the first
    would file the surnames alone as the taxpayer's full legal name.

    Only ``surnames_name`` is handled. A ``format = "date"`` binding
    deliberately falls through to the ordinary path: the value stays a typed
    :class:`~datetime.date` and the renderer formats it from the row's declared
    type, so adding a second date rendering here would put a formatting
    authority beside ``format_xml_dictionary_value`` that could silently
    disagree with it on a filed artefact.
    """
    provider = binding.provider
    if not isinstance(provider, ProfileProvider) or provider.format != _SURNAMES_NAME_FORMAT:
        return resolve_profile_binding_value(binding, fact_index)
    keys = provider.profile_keys
    if len(keys) < 2:
        return resolve_profile_binding_value(binding, fact_index)
    composed = compose_legal_full_name(
        surnames=str(fact_index.get(keys[0]) or ""),
        name=str(fact_index.get(keys[1]) or ""),
    )
    return composed or None


def resolve_profile_export_values(
    bindings: Sequence[BindingDefinition],
    *,
    bucket_id: str,
    filing_year: int,
    operation: PinnedAuthorityOperation,
    profile_record: object | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> dict[str, UserProfileFactValue]:
    """Resolve profile-sourced export values keyed by AEAT's dictionary field id.

    The export-shaped twin of :func:`resolve_profile_sourced_bindings`: same
    owner, same fact index, same per-binding resolution, different output
    shape. The calculation side returns typed channels for the engine; this
    returns the values AEAT's own dictionary field ids address, which is what
    the fichero-BOE writer consumes. Keeping both here is what stops a second
    profile-resolution authority appearing on the export path.

    Values stay their concrete :data:`UserProfileFactValue` type. The renderer
    decides a row's rendering from the Python type it receives, so pre-rendering
    to ``str`` here would destroy the distinction it needs.

    Deliberately does NOT call ``_load_profile_facts``: its family and state
    attribution facts feed formulas, and no export-addressed binding names them.
    The one derived path an export binding does name is the cash election, which
    states one ejercicio and so needs ``filing_year``; it is injected through the
    same function the loader uses, so the two cannot disagree.

    A ``repeating`` binding is skipped. Those name array paths
    (``RentaFamilyProfile.ascendants.*`` / ``.descendants.*``) that nothing in
    production writes -- the real writer is the ``renta_family.descendiente``
    OBJECT, which carries neither ``death_date`` nor ``display_name`` -- and
    the dictionary writer reuses a child element by tag, so N of them would
    overwrite one another rather than producing N rows. They are a known
    structural gap, pinned by test rather than reported at runtime: an advisory
    firing on every export for a gap no operator can act on is the alert
    fatigue that makes the real advisories worth ignoring.

    Args:
        bindings: The revision's export-addressed profile bindings, as
            projected onto the schema subview by ``profile_export_bindings``.
        bucket_id: Active profile bucket whose persisted facts are read.
        filing_year: Ejercicio whose election the derived cash-criterion fact states.
        operation: Authority operation supplying the profile read and schema.
        profile_record: Pre-loaded profile record; loaded from the bucket when
            omitted.
        schema: Pre-loaded profile schema; loaded when omitted.

    Returns:
        Dictionary field id to typed value, omitting every binding that
        resolved to nothing or whose precondition was not met. An absent
        profile yields an empty mapping -- the caller decides whether a missing
        slot is fatal, since the export layout is what declares a field
        required.
    """
    return _resolve_profile_export_values(
        bindings,
        bucket_id=bucket_id,
        filing_year=filing_year,
        operation=operation,
        profile_record=profile_record,
        schema=schema,
    )


def resolve_export_identity(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile_record: object | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> tuple[PresenterIdentity, TaxpayerIdentityFacts] | None:
    """Derive the presenter and taxpayer identity facts from the stored profile.

    :class:`PresenterIdentity` deliberately offers no taxpayer-to-presenter
    fallback of its own, so somebody must decide who is presenting. This is
    that decision, made once: the operator whose profile is filing IS the
    presenter. Cadrumo exposes no representative or gestor identity -- a filing
    prepared here belongs to the profile that prepared it -- so deriving the
    presenter from anything else would invent an actor the product has no way
    to name. When a representative surface does land, it overrides here rather
    than being threaded through every export caller.

    The taxpayer facts are read as the four distinct official meanings the
    producer declares, never as interchangeable aliases. A natural person
    carries ``given_name`` and ``surnames`` and the ``full_name`` composed from
    them through :func:`compose_legal_full_name`, so the surnames-first join
    stays the single authority it already is; ``legal_name`` stays absent
    because a natural person has none. Any other entity type carries its
    registered name as BOTH ``legal_name`` and ``full_name`` and nothing else,
    because an entity has no given name or surnames to split.

    Returns:
        The presenter/taxpayer pair, or ``None`` when the profile is absent or
        declares no usable tax identity. ``None`` means "cannot answer", and
        the export path's own refusal states that far better than a half-built
        identity would.
    """
    record = _load_profile_record(
        bucket_id=bucket_id,
        operation=operation,
        profile_record=profile_record,
    )
    if record is None:
        return None
    resolved_schema = operation.profile_schema() if schema is None else schema
    return identity_from_profile_facts(profile_fact_index(record, resolved_schema), schema=resolved_schema)


def _load_profile_record(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile_record: object | None,
) -> object | None:
    """Load the active profile only when the caller did not provide it."""
    if profile_record is not None:
        return profile_record
    from ..user_profile.profile_record_repository import ProfileRecordRepository

    try:
        return ProfileRecordRepository.for_current_session(
            bucket_id,
            profile_decode_context=operation.profile_decode_context(),
        ).load(bucket_id)
    except ProfileNotFoundError:
        return None


def resolve_declaration_contact(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile_record: object | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> DeclarationContactFacts:
    """Read the "persona con quien relacionarse" the informativa header declares.

    Resolved separately from :func:`resolve_export_identity` rather than folded
    into its tuple: this is a THIRD party in AEAT's model, distinct from both
    the taxpayer and the presenter, and under a gestor it is routinely neither
    of them. Keeping it its own read also leaves both existing callers of the
    identity pair untouched.

    Args:
        bucket_id: Active profile bucket.
        operation: Authority operation supplying the profile read and schema.
        profile_record: Already-loaded record, when the caller holds one.
        schema: Already-loaded schema, when the caller holds one.

    Returns:
        The declared contact. Absent halves stay absent -- AEAT writes an
        unfilled alphanumeric header field to blancos, so a profile that
        declares no contact still produces a legal filing.
    """
    record = _load_profile_record(
        bucket_id=bucket_id,
        operation=operation,
        profile_record=profile_record,
    )
    if record is None:
        return DeclarationContactFacts()
    resolved_schema = operation.profile_schema() if schema is None else schema
    return _declaration_contact_from_profile_facts(profile_fact_index(record, resolved_schema), schema=resolved_schema)


def resolve_profile_identity_producer_values(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile_record: object | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> dict[FilingProducerKey, str | None]:
    """Read current taxpayer/contact context using the export's canonical shaping.

    Unlike export admission, this read needs neither a complete presenter nor
    filing elections: a partial profile still answers each fact it declares.
    It supplies no representative, payment selection or historical evidence.
    """
    record = _load_profile_record(bucket_id=bucket_id, operation=operation, profile_record=profile_record)
    if record is None:
        return {}
    resolved_schema = operation.profile_schema() if schema is None else schema
    facts = profile_fact_index(record, resolved_schema)
    return identity_contact_producer_values(
        taxpayer_tax_id=str(facts.get(IDENTITY_TAX_ID_PATH) or "").strip() or None,
        identity=_taxpayer_identity_from_profile_facts(facts, schema=resolved_schema),
        contact=_declaration_contact_from_profile_facts(facts, schema=resolved_schema),
    )


def resolve_m303_profile_lexicals(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    period: Period | None,
    profile_record: object | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> M303ProfileLexicals:
    """Read the declared Modelo 303 enrolment facts through the export's own lexical projection.

    A profile that is absent, or whose IVA block is unclaimed or incomplete,
    answers nothing: every lexical stays ``None`` and is never read as a no.
    Export admission is what refuses such a profile and names the missing path.
    """
    record = _load_profile_record(bucket_id=bucket_id, operation=operation, profile_record=profile_record)
    if not isinstance(record, UserProfileRecord):
        return M303ProfileLexicals()
    resolved_schema = operation.profile_schema() if schema is None else schema
    try:
        profile = projection_for_taxpayer(record, schema=resolved_schema)
    except (ProfileError, UserProfileError):
        return M303ProfileLexicals()
    return m303_profile_lexicals(profile.iva, period)


def _declaration_contact_from_profile_facts(
    facts: Mapping[str, UserProfileFactValue], *, schema: ProfileSchemaDefinition
) -> DeclarationContactFacts:
    """Shape only the declaration's contact fields, preserving absent components."""
    phone = str(facts.get(_CONTACT_PERSON_PHONE_KEY) or "").strip()
    full_name = str(facts.get(_CONTACT_PERSON_NAME_KEY) or "").strip()
    return _built_within_profile_text_bounds(
        lambda: DeclarationContactFacts(phone=phone or None, full_name=full_name or None),
        _CONTACT_TEXT_PROFILE_FACTS,
        schema=schema,
    )


def identity_from_profile_facts(
    facts: Mapping[str, UserProfileFactValue],
    *,
    schema: ProfileSchemaDefinition,
) -> tuple[PresenterIdentity, TaxpayerIdentityFacts] | None:
    """Build the explicit presenter/taxpayer pair from indexed profile facts."""
    tax_id = str(facts.get(IDENTITY_TAX_ID_PATH) or "").strip()
    if not tax_id:
        return None

    identity = _taxpayer_identity_from_profile_facts(facts, schema=schema)
    if identity.full_name is None:
        return None
    return PresenterIdentity(tax_id=tax_id, full_name=identity.full_name), identity


def _taxpayer_identity_from_profile_facts(
    facts: Mapping[str, UserProfileFactValue], *, schema: ProfileSchemaDefinition
) -> TaxpayerIdentityFacts:
    """Shape each declared name component using the export identity rules."""
    return _taxpayer_identity_facts(
        name=str(facts.get(IDENTITY_NAME_PATH) or "").strip(),
        surnames=str(facts.get(IDENTITY_SURNAMES_PATH) or "").strip(),
        legal_name=str(facts.get(IDENTITY_LEGAL_NAME_PATH) or "").strip(),
        entity_type=str(facts.get(_ENTITY_TYPE_KEY) or "").strip().casefold(),
        schema=schema,
    )


def _taxpayer_identity_facts(
    *,
    name: str,
    surnames: str,
    legal_name: str,
    entity_type: str,
    schema: ProfileSchemaDefinition,
) -> TaxpayerIdentityFacts:
    """Shape natural-person and entity names into the producer's four facts."""

    def shape() -> TaxpayerIdentityFacts:
        if entity_type == entity_type_natural_person_token().value:
            full_name = compose_legal_full_name(surnames=surnames, name=name)
            return TaxpayerIdentityFacts(
                legal_name=None,
                given_name=name or None,
                surnames=surnames or None,
                full_name=full_name or None,
            )
        registered = legal_name or compose_legal_full_name(surnames=surnames, name=name)
        return TaxpayerIdentityFacts(
            legal_name=registered or None,
            given_name=None,
            surnames=None,
            full_name=registered or None,
        )

    return _built_within_profile_text_bounds(shape, _IDENTITY_TEXT_PROFILE_FACTS, schema=schema)


def _built_within_profile_text_bounds[Built](
    build: Callable[[], Built],
    profile_facts: Mapping[str, str],
    *,
    schema: ProfileSchemaDefinition,
) -> Built:
    """Report a stored text that overruns a producer's bound as the profile fact to correct.

    A profile written before its field declared a bound, or a composed name each of
    whose parts fits, reaches the producer here. The operator declares the profile
    fact and never sees the producer record, so the refusal names the fact.

    The refusal is raised once the handler has closed, so the validation error,
    which holds the stored text, is neither its cause nor its context.
    """
    try:
        return build()
    except ValidationError as exc:
        refusal = _overlong_profile_text_refusal(exc, profile_facts, schema=schema)
        if refusal is None:
            raise
    raise refusal


def _overlong_profile_text_refusal(
    exc: ValidationError,
    profile_facts: Mapping[str, str],
    *,
    schema: ProfileSchemaDefinition,
) -> UserProfileError | None:
    for error in exc.errors(include_input=False, include_url=False):
        context = error.get("ctx")
        if error["type"] == "string_too_long" and context is not None:
            return profile_text_too_long_error(
                profile_facts[str(error["loc"][0])],
                limit=context["max_length"],
                schema=schema,
            )
    return None


def _profile_export_values_from_facts(
    bindings: Sequence[BindingDefinition], fact_index: Mapping[str, UserProfileFactValue]
) -> dict[str, UserProfileFactValue]:
    values: dict[str, UserProfileFactValue] = {}
    for binding in bindings:
        provider = binding.provider
        if not isinstance(provider, ProfileProvider):
            continue
        field_id = provider.dictionary_field
        if field_id is None or provider.repeating:
            continue
        if not _profile_export_binding_applies(binding, fact_index):
            continue
        value = _profile_export_value(binding, fact_index)
        if value is not None:
            values[field_id] = value
    return values


def _resolve_profile_export_values(
    bindings: Sequence[BindingDefinition],
    *,
    bucket_id: str,
    filing_year: int,
    operation: PinnedAuthorityOperation,
    profile_record: object | None,
    schema: ProfileSchemaDefinition | None,
) -> dict[str, UserProfileFactValue]:
    """Body of :func:`resolve_profile_export_values`; see its contract."""
    if not bindings:
        # A revision declaring no export-addressed profile binding has nothing
        # to resolve, so there is no reason to open the bucket and decrypt a
        # profile record to answer with an empty mapping.
        return {}
    record = profile_record
    if record is None:
        from ..user_profile.profile_record_repository import ProfileRecordRepository

        try:
            record = ProfileRecordRepository.for_current_session(
                bucket_id,
                profile_decode_context=operation.profile_decode_context(),
            ).load(bucket_id)
        except ProfileNotFoundError:
            return {}
    resolved_schema = operation.profile_schema() if schema is None else schema
    fact_index = profile_fact_index(record, resolved_schema)
    inject_derived_cash_election_fact(fact_index, record, filing_year, operation=operation)
    inject_derived_estimation_modality_fact(fact_index, operation=operation)
    inject_derived_activity_tipo_clave_fact(fact_index)

    return _profile_export_values_from_facts(bindings, fact_index)
