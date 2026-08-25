"""Profile-sourced values addressed on the exported declaration.

The export-shaped counterpart to the calculation-shaped resolution in
:mod:`._profile_binding`. Both read the SAME fact index and the SAME
per-binding resolution -- this module adds only the export-side shaping, so a
profile fact cannot mean one thing to the calculation engine and another to the
filed artefact. It is a family module, not a second authority: the fact index
and single-binding resolution stay owned next door and are imported, never
reimplemented.

Split out when ``_profile_binding`` crossed its module size budget. The
calculation and export halves genuinely are two cohesive concerns over one
shared substrate, which is the split the budget forced and the shape the
per-family binding modules elsewhere in the tree already use.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ...domain.calculations.registry.schema import DataBindingDefinition
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.loader import load_user_profile_schema
from ...domain.user_profile.schema import ProfileSchemaDefinition
from ...domain.user_profile.values import UserProfileFactValue
from ..filing import DeclarationContactFacts, PresenterIdentity, TaxpayerIdentityFacts

# Intra-package reuse of this package's own resolver internals, which the
# architecture rule permits; the cross-package boundary has its own gate.
from ._profile_binding import _profile_fact_index, _resolve_one  # pyright: ignore[reportPrivateUsage]

_SURNAMES_NAME_FORMAT = "surnames_name"

#: Stored profile fact paths the export identity is read from. Named here
#: rather than inline so the three that must agree stay visibly together.
_IDENTITY_TAX_ID_KEY = "identity.tax_id"
_IDENTITY_NAME_KEY = "identity.name"
_IDENTITY_SURNAMES_KEY = "identity.surnames"
_ENTITY_TYPE_KEY = "taxpayer_type.entity_type"
_CONTACT_PERSON_PHONE_KEY = "contact.contact_person_phone"
_CONTACT_PERSON_NAME_KEY = "contact.contact_person_name"
_NATURAL_PERSON_ENTITY_TYPE = "natural_person"


def compose_legal_full_name(*, surnames: str, name: str) -> str:
    """Compose a Spanish legal full name from its ordered parts.

    AEAT writes an individual's name surnames-first, and a blank part must not
    leave a doubled separator behind. This is the single home for that join:
    the export header path and the dictionary-field resolver below both write
    the operator's name onto the same declaration, so two separate joins could
    disagree on one artefact.
    """
    return " ".join(part for part in (surnames.strip(), name.strip()) if part)


def _profile_export_binding_applies(
    binding: DataBindingDefinition,
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
    gate_key = getattr(binding.selector, "required_when_profile_key", None)
    if gate_key is None:
        return True
    expected = str(getattr(binding.selector, "required_when_value", "") or "").strip()
    actual = str(fact_index.get(gate_key, "")).strip()
    return bool(expected) and actual.casefold() == expected.casefold()


def _profile_export_value(
    binding: DataBindingDefinition,
    fact_index: Mapping[str, UserProfileFactValue],
) -> UserProfileFactValue | None:
    """Resolve one export binding's value, honouring a declared multi-key format.

    :func:`_resolve_one` returns the FIRST non-blank selector value, which is
    right for a binding whose keys are fallbacks but wrong for one whose keys
    are PARTS: ``DP_APENOM_D`` declares ``("identity.surnames",
    "identity.name")`` with ``format = "surnames_name"``, and taking the first
    would file the surnames alone as the taxpayer's full legal name.

    Only ``surnames_name`` is handled. A ``format = "date"`` binding
    deliberately falls through to the ordinary path: the value stays a typed
    :class:`~datetime.date` and the renderer formats it from the row's declared
    type, so adding a second date rendering here would put a formatting
    authority beside ``_format_xml_dictionary_value`` that could silently
    disagree with it on a filed artefact.
    """
    selector = binding.selector
    if getattr(selector, "format", None) != _SURNAMES_NAME_FORMAT:
        return _resolve_one(binding, fact_index)
    keys = tuple(getattr(selector, "profile_keys", ()) or ())
    if len(keys) < 2:
        return _resolve_one(binding, fact_index)
    composed = compose_legal_full_name(
        surnames=str(fact_index.get(keys[0]) or ""),
        name=str(fact_index.get(keys[1]) or ""),
    )
    return composed or None


def resolve_profile_export_values(
    bindings: Sequence[DataBindingDefinition],
    *,
    bucket_id: str,
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

    Deliberately does NOT call ``_load_profile_facts``, and deliberately takes
    no :class:`RegistrySnapshot`. That loader adds the engine-derived facts
    (marriage months, guardería aggregates, mínimo descendientes, anualidades
    eligibility, state attribution) on top of the stored index. Measured
    against the real Modelo 100 2024 revision, ZERO of the 32 selectors named
    by export-addressed bindings is a derived path -- every one is a stored
    fact (identity, spouse, taxpayer, tax residence, declaration type). The
    derived injectors therefore cannot change a single value this function
    reads, so requiring a snapshot would be threading an input that provably
    does not affect the answer. Re-measure before assuming otherwise; if a
    future revision does declare an export binding on a derived path, route
    this through the same loader rather than reproducing any part of it.

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
        profile_record=profile_record,
        schema=schema,
    )


def resolve_export_identity(
    *,
    bucket_id: str,
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
    record = _load_profile_record(bucket_id=bucket_id, profile_record=profile_record)
    if record is None:
        return None
    resolved_schema = schema if schema is not None else load_user_profile_schema()
    return _identity_from_profile_facts(_profile_fact_index(record, resolved_schema))


def _load_profile_record(*, bucket_id: str, profile_record: object | None) -> object | None:
    """Load the active profile only when the caller did not provide it."""
    if profile_record is not None:
        return profile_record
    from ..user_profile.profile_record_repository import ProfileRecordRepository

    try:
        return ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return None


def resolve_declaration_contact(
    *,
    bucket_id: str,
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
        profile_record: Already-loaded record, when the caller holds one.
        schema: Already-loaded schema, when the caller holds one.

    Returns:
        The declared contact. Absent halves stay absent -- AEAT writes an
        unfilled alphanumeric header field to blancos, so a profile that
        declares no contact still produces a legal filing.
    """
    record = _load_profile_record(bucket_id=bucket_id, profile_record=profile_record)
    if record is None:
        return DeclarationContactFacts()
    resolved_schema = schema if schema is not None else load_user_profile_schema()
    facts = _profile_fact_index(record, resolved_schema)
    phone = str(facts.get(_CONTACT_PERSON_PHONE_KEY) or "").strip()
    full_name = str(facts.get(_CONTACT_PERSON_NAME_KEY) or "").strip()
    return DeclarationContactFacts(phone=phone or None, full_name=full_name or None)


def _identity_from_profile_facts(
    facts: Mapping[str, UserProfileFactValue],
) -> tuple[PresenterIdentity, TaxpayerIdentityFacts] | None:
    """Build the explicit presenter/taxpayer pair from indexed profile facts."""
    tax_id = str(facts.get(_IDENTITY_TAX_ID_KEY) or "").strip()
    if not tax_id:
        return None

    name = str(facts.get(_IDENTITY_NAME_KEY) or "").strip()
    surnames = str(facts.get(_IDENTITY_SURNAMES_KEY) or "").strip()
    entity_type = str(facts.get(_ENTITY_TYPE_KEY) or "").strip().casefold()
    identity = _taxpayer_identity_facts(name=name, surnames=surnames, entity_type=entity_type)
    if identity.full_name is None:
        return None
    return PresenterIdentity(tax_id=tax_id, full_name=identity.full_name), identity


def _taxpayer_identity_facts(
    *,
    name: str,
    surnames: str,
    entity_type: str,
) -> TaxpayerIdentityFacts:
    """Shape natural-person and entity names into the producer's four facts."""
    if entity_type == _NATURAL_PERSON_ENTITY_TYPE:
        full_name = compose_legal_full_name(surnames=surnames, name=name)
        return TaxpayerIdentityFacts(
            legal_name=None,
            given_name=name or None,
            surnames=surnames or None,
            full_name=full_name or None,
        )
    registered = compose_legal_full_name(surnames=surnames, name=name)
    return TaxpayerIdentityFacts(
        legal_name=registered or None,
        given_name=None,
        surnames=None,
        full_name=registered or None,
    )


def _resolve_profile_export_values(
    bindings: Sequence[DataBindingDefinition],
    *,
    bucket_id: str,
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
            record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
        except ProfileNotFoundError:
            return {}
    resolved_schema = schema if schema is not None else load_user_profile_schema()
    fact_index = _profile_fact_index(record, resolved_schema)

    values: dict[str, UserProfileFactValue] = {}
    for binding in bindings:
        selector = binding.selector
        field_id = getattr(selector, "dictionary_field", None)
        if field_id is None or getattr(selector, "repeating", False):
            continue
        if not _profile_export_binding_applies(binding, fact_index):
            continue
        value = _profile_export_value(binding, fact_index)
        if value is not None:
            values[str(field_id)] = value
    return values
