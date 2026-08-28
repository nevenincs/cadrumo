"""A credential-shaped field must say so in its classification.

Masking is decided by a field's declared :class:`SensitivityClass` and
nothing else. That is the right runtime rule -- authored prose must not
override an explicit declaration -- but it leaves one hole: a field that
IS a credential and is declared ``identity`` by mistake renders in the
clear, and no runtime check would notice.

This gate is that check, moved to build time where it belongs. A
heuristic that guesses at runtime can only silently override a
declaration, which is what the previous masking policy did. A heuristic
that runs here can only refuse, and it refuses loudly, naming the field.
It also reads every declared field on every run, where the runtime arm
only ever saw fields something happened to render.

A field is presumed to be a credential on either of two kinds of
evidence, and the pair is deliberate because each is blind where the
other sees:

* **Structural** -- it sits in a section that exists to hold
  authentication material. Section membership cannot be reworded, so
  this arm is immune to the editorial drift that is the whole subject of
  this module. It is the only arm that catches a real credential given
  an innocuous name.
* **Lexical** -- its path or description reads like a credential. This
  arm is fragile in exactly the way described above, but it reaches
  fields outside the credential sections, where the structural arm has
  nothing to say.

Neither subsumes the other: a ``billing.api_key`` is caught only
lexically, an ``auth.contraste_qr`` only structurally.

Layered with the tests around it, and it is worth being explicit about
which covers what, because no one of them covers all of it:

* The known credential set is pinned by name in the auth schema shape
  tests, as a set equality -- stronger than any heuristic where it
  applies. It catches a downgrade of either contraste field, and a
  spurious upgrade of ``auth.provider`` or ``auth.dni_nie``. It cannot
  catch a field ADDED to the section, because adding one leaves that set
  equal.
* That addition is what this gate catches, on either kind of evidence,
  before it can ship.
* A fact arriving at a surface under a path no schema field declares has
  no declaration to consult, so the runtime keyword arm still covers it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest

from ....core.classification import SensitivityClass
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.schema import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CREDENTIAL_EVIDENCE_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "passphrase",
        "secret",
        "secreto",
        "contraseña",
        "clave",
        "credential",
        "token",
        "key",
    },
)
"""Substrings whose presence in a field's path or description PRESUMES a credential.

This was read off ``_overview._MASK_KEYWORDS`` until that set was recomposed onto
the shared redaction base, and the two must not be the same vocabulary again --
they answer different questions. The masking predicate asks *should this value be
hidden from an operator*, for which a NIF, a tax id and a certificate reference
all qualify. This gate asks the narrower *is this field a misdeclared credential*,
and a NIF is not a credential: it is an identity fact that the schema correctly
declares ``IDENTITY`` rather than ``SECRET``.

Sharing one constant across both questions would have flagged twelve correctly
declared identity and financial fields the moment the masking side widened --
``identity.tax_id``, ``auth.dni_nie``, ``renta_spouse.tax_id``, the representante
NIFs -- and would have re-presumed ``auth.provider`` a credential on the word
``certificate`` in its description, which is precisely the prose-driven
misclassification ``_overview`` documents having already fixed once.

The terms here are the credential-naming ones, in both languages, and deliberately
carry no identity term. Bare ``key`` stays for the same reason it does on the
masking side: it subsumes ``api_key``, ``apikey``, ``private_key``.
"""

if TYPE_CHECKING:
    from collections.abc import Mapping


_CREDENTIAL_SECTIONS: Final[frozenset[str]] = frozenset({"auth"})
"""Sections that exist to hold authentication material.

Every field in one is presumed a credential until its entry in
``_EXEMPT`` says otherwise. The presumption follows the section's own
purpose -- ``auth`` is where an authentication mode's inputs live -- so
it is a stated default rather than a guess about a name, and unlike a
keyword it survives any rewording of the field it guards.

A section named here that the schema does not declare is refused below.
A predicate policing a section that no longer exists covers nothing and
passes silently, which is the failure this module is built to prevent.
"""

_EXEMPT: Final[Mapping[str, str]] = {
    "auth.dni_nie": (
        "In the auth section, and correctly so: every Cl@ve mode reads it. But it NAMES "
        "the taxpayer rather than authenticating them, and the section presumption cannot "
        "tell those apart. It carries the same identifier as identity.tax_id -- the two "
        "are compared at live authentication and the session is refused when they diverge "
        "-- which renders in the clear one section above, so classing this copy secret "
        "concealed a value already on the same screen. What actually authenticates is the "
        "contraste (numero_soporte / fecha_validez, both still secret) plus a Cl@ve PIN or "
        "app this profile never stores; someone holding a DNI/NIE and nothing else gains no "
        "capability. The classes themselves say so: SECRET is declared for 'long-lived "
        "authentication material' while IDENTITY names the NIF explicitly, and classing "
        "this field secret dropped nif-hash -- the one rule that hashes a NIF -- from the "
        "policy resolved for it. This is a permanent member of the section rather than a "
        "case awaiting reclassification."
    ),
    "auth.provider": (
        "In the auth section, and correctly so: it selects the authentication mode and "
        "decides which of the other auth fields are required. But it holds WHICH method "
        "the taxpayer uses, not any material to authenticate with -- a closed enum whose "
        "every possible value the schema publishes anyway, so classing the current one "
        "secret would protect nothing while hiding from the operator how they identify. "
        "Knowing the mode confers no capability. This is a permanent member of the "
        "section rather than a case awaiting reclassification."
    ),
    "auth.clave_movil_route": (
        "The same case as auth.provider one field up, and exempt for the same reason: a "
        "closed enum of 'qr' / 'app_request' holding WHICH way Cl@ve Movil asks for "
        "confirmation, not any material to confirm with. Both values are published in the "
        "schema, so classing the chosen one secret would protect nothing while hiding from "
        "the operator how their own login behaves. "
        "Its lexical evidence is a false positive with a linguistic cause worth naming: it "
        "matches 'clave' because Cl@ve is the PROPER NOUN for Spain's national "
        "authentication system, which necessarily appears in the name and description of "
        "every field about it. The keyword cannot distinguish the brand from the password, "
        "and in Spanish tax software the brand is the commoner reading. What the route "
        "actually needs to authenticate -- the contraste pair its description mentions -- "
        "lives in numero_soporte and fecha_validez, both correctly declared secret. "
        "A permanent member of the section rather than a case awaiting reclassification."
    ),
    "censo.divergencia": (
        "Matches on 'provenance token'. That is this project's own term for the source "
        "marker on a divergence row (PROVENANCE_SOURCE_CENSO_ARTEFACT), not a bearer "
        "token: the row holds a diverging fact's schema path, the certificate value the "
        "operator did not adopt, and that marker. Fiscal profile content, rendered in "
        "the clear beside contact.fiscal_address, and not authentication material. Its "
        "former mask was decorative in any case and must not be restored as a fix: the "
        "row the schema declares is the unindexed path, which never carries a value, "
        "while the indexed censo.divergencia.{n}.* subpaths that do carry the content "
        "resolve to no schema field and render unmasked."
    ),
    "attribution_entity_socios.participe_clave": (
        "Matches on 'clave', which is the keyword's weakest case: in Spanish it means both "
        "PASSWORD and CODE, and AEAT uses the second sense throughout. This is literally the "
        "Modelo 184 record layout's 'CLAVE TIPO DE PARTICIPE' at position 81, a one-digit "
        "enum over residente / no residente sin establecimiento permanente / no residente con "
        "establecimiento permanente. It authenticates nothing and grants no capability; "
        "someone holding it learns only which of three residency classes a declared member "
        "falls into, which the declaration publishes to AEAT by design. Renaming it to dodge "
        "the keyword would drop the official term this codebase requires for AEAT concepts, "
        "so the exemption is the honest resolution rather than a workaround."
    ),
    "attribution_entity_socios.clave": (
        "Matches on 'clave' in its own NAME, in the code sense rather than the password "
        "sense: it is the Modelo 184 record's 'clave' at position 93, a one-letter enum over "
        "A capital mobiliario, C capital inmobiliario, D actividades economicas and the rest. "
        "It classifies a declared row for AEAT and authenticates nothing; someone holding it "
        "learns only how the declaration classifies that row, which the filing publishes to "
        "AEAT by design. Renaming it would drop the official AEAT term this codebase requires "
        "for domain concepts."
    ),
    "attribution_entity_socios.subclave": (
        "Matches on 'clave' in its own NAME, in the code sense rather than the password "
        "sense: it is the same record's numeric subclave at positions 94-95, whose meaning "
        "depends on the clave declared beside it. It classifies a declared row for AEAT and "
        "authenticates nothing; someone holding it learns only how the declaration classifies "
        "that row, which the filing publishes to AEAT by design. Renaming it would drop the "
        "official AEAT term this codebase requires for domain concepts."
    ),
    "attribution_entity_socios.clave_declarado": (
        "Matches on 'clave' in its own NAME, in the code sense rather than the password "
        "sense: it is the clave for the socio's TITULARIDAD of the inmueble, a declared "
        "ownership class rather than a secret. It classifies a declared row for AEAT and "
        "authenticates nothing; someone holding it learns only how the declaration classifies "
        "that row, which the filing publishes to AEAT by design. Renaming it would drop the "
        "official AEAT term this codebase requires for domain concepts."
    ),
    "taxpayer_type.declaration_roles": (
        "Matches on 'clave' only through its DESCRIPTION, which names the clave that governs "
        "whether the field applies: each ThirdPartyDeclarationRole feeds a specific Modelo "
        "347 clave (C, D or E). The field itself is a closed set of institutional roles the "
        "filer already declares to AEAT, not authentication material. Rewording the "
        "description to dodge the keyword would remove exactly the sentence telling a reader "
        "when the field is required."
    ),
    "attribution_entity_socios.naturaleza_inmueble": (
        "Matches on 'clave' only through its DESCRIPTION, which names the clave that governs "
        "whether the field applies: it applies only when clave = C, capital inmobiliario. The "
        "field itself is the nature of the property producing the income, not authentication "
        "material. Rewording the description to dodge the keyword would remove exactly the "
        "sentence telling a reader when the field is required."
    ),
    "attribution_entity_socios.situacion_inmueble": (
        "Matches on 'clave' only through its DESCRIPTION, which names the clave that governs "
        "whether the field applies: it applies only when clave = C. The field itself is the "
        "property's situation code, not authentication material. Rewording the description to "
        "dodge the keyword would remove exactly the sentence telling a reader when the field "
        "is required."
    ),
    "attribution_entity_socios.referencia_catastral": (
        "Matches on 'clave' only through its DESCRIPTION, which names the clave that governs "
        "whether the field applies: it carries the catastral reference of the clave-C "
        "inmueble. The field itself is a public cadastral identifier, not authentication "
        "material. Rewording the description to dodge the keyword would remove exactly the "
        "sentence telling a reader when the field is required."
    ),
    "attribution_entity_socios.porcentaje_titularidad_inmueble": (
        "Matches on 'clave' only through its DESCRIPTION, which names the clave that governs "
        "whether the field applies: it qualifies the clave-C inmueble the socio holds. The "
        "field itself is an ownership percentage, not authentication material. Rewording the "
        "description to dodge the keyword would remove exactly the sentence telling a reader "
        "when the field is required."
    ),
    "attribution_entity_socios.dias_arrendamiento": (
        "Matches on 'clave' only through its DESCRIPTION, which names the clave that governs "
        "whether the field applies: it counts days for the clave-C inmueble. The field itself "
        "is a day count within the ejercicio, not authentication material. Rewording the "
        "description to dodge the keyword would remove exactly the sentence telling a reader "
        "when the field is required."
    ),
    "attribution_entity_socios.reduccion": (
        "Matches on 'clave' only through its DESCRIPTION, which names the clave that governs "
        "whether the field applies: it names the clave whose rendimiento the reduction "
        "applies to. The field itself is a EUR amount, not authentication material. Rewording "
        "the description to dodge the keyword would remove exactly the sentence telling a "
        "reader when the field is required."
    ),
    "attribution_entity_socios.rendimiento_neto_previo_eo": (
        "Matches on 'clave' only through its DESCRIPTION, which names the clave that governs "
        "whether the field applies: it belongs to clave D subclave 03/04, estimacion "
        "objetiva. The field itself is a EUR rendimiento, not authentication material. "
        "Rewording the description to dodge the keyword would remove exactly the sentence "
        "telling a reader when the field is required."
    ),
    "attribution_entity_socios.rendimiento_neto_minorado_agricola_eo": (
        "Matches on 'clave' only through its DESCRIPTION, which names the clave that governs "
        "whether the field applies: it belongs to the agricultural estimacion objetiva "
        "subclave of clave D. The field itself is a EUR rendimiento, not authentication "
        "material. Rewording the description to dodge the keyword would remove exactly the "
        "sentence telling a reader when the field is required."
    ),
    "attribution_entity_socios.country_of_residence": (
        "Matches on 'clave' only through its DESCRIPTION, which names the clave that governs "
        "it -- the field itself is an ISO country code written at positions 79-80 of the same "
        "record. Rewording the description to avoid the keyword would remove exactly the "
        "sentence a reader needs to know the field is conditional, so the reference stays and "
        "the field is exempted here. It is identity-class rather than secret for the same "
        "reason the tax identifier is: it names a party rather than authenticating one."
    ),
}
"""Fields whose credential-shaped wording is a false positive.

Each entry states why the field is not authentication material. An entry
whose field has stopped matching is removed, not left standing -- the
staleness gate below refuses one, so the list cannot outlive its cause
and quietly pre-approve a future field at the same path.
"""


def _presumed_credential(schema: ProfileSchemaDefinition) -> dict[str, list[str]]:
    """Return every field presumed to be a credential, with the evidence for it.

    Args:
        schema: The schema to walk.

    Returns:
        Mapping of dotted field path to sorted evidence -- ``section:<key>``
        where the field sits in a credential-bearing section, and each
        masking keyword its path or description contains.
    """
    presumed: dict[str, list[str]] = {}
    for section in schema.sections:
        for field in section.fields:
            path = f"{section.key}.{field.key}"
            haystack = f"{path} {field.description}".casefold()
            evidence = [keyword for keyword in _CREDENTIAL_EVIDENCE_KEYWORDS if keyword in haystack]
            if section.key in _CREDENTIAL_SECTIONS:
                evidence.append(f"section:{section.key}")
            if evidence:
                presumed[path] = sorted(evidence)
    return presumed


def _misdeclared(schema: ProfileSchemaDefinition) -> dict[str, list[str]]:
    """Return presumed-credential fields that neither declare ``secret`` nor are exempt."""
    return {
        path: evidence
        for path, evidence in _presumed_credential(schema).items()
        if path not in _EXEMPT and schema.field(path).sensitivity is not SensitivityClass.SECRET
    }


def _schema_with(field: ProfileFieldDefinition, *, section_key: str = "auth") -> ProfileSchemaDefinition:
    """Wrap one field in the smallest valid schema, for the control cases."""
    return ProfileSchemaDefinition(
        id="test.credential_gate",
        version=1,
        title="Credential gate control schema",
        snapshot_policy=ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH,
        remove_policy=ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS,
        sections=(
            ProfileSectionDefinition(
                key=section_key,
                title="Control section",
                sensitivity=SensitivityClass.IDENTITY,
                fields=(field,),
            ),
        ),
    )


def test_the_shipped_schema_declares_every_presumed_credential_secret() -> None:
    """No presumed credential may ship classed as anything but ``secret``.

    DISCRIMINATING, and it is the structural arm that gives it purchase
    on the shipped schema: the lexical arm alone finds exactly one live
    subject across every declared field, and that one is a false
    positive. The controls below prove each arm bites on its own,
    because a predicate matching nothing would pass this just as
    happily.
    """
    misdeclared = _misdeclared(load_user_profile_schema())
    assert not misdeclared, (
        "these fields are presumed credentials but are not declared secret; "
        f"classify them or record why they are not: {misdeclared}"
    )


def test_every_credential_section_is_really_declared_by_the_schema() -> None:
    """A section policed here must exist, or the structural arm is vacuous.

    Renaming or removing the ``auth`` section would leave the structural
    arm walking nothing and the gate above passing in silence -- covering
    zero fields while still reading like protection. The presumption has
    to fail loudly instead.
    """
    declared = {section.key for section in load_user_profile_schema().sections}
    missing = sorted(_CREDENTIAL_SECTIONS - declared)
    assert not missing, f"these sections are policed as credential-bearing but are not declared: {missing}"


def test_the_gate_refuses_an_innocuously_named_field_in_a_credential_section() -> None:
    """The structural arm bites where the lexical arm is blind.

    This is the case that justifies the structural predicate, and the
    one neither other gate reaches: the pinned-by-name test is a set
    equality over the known three, so ADDING a field leaves it equal and
    passing.

    The field is a genuine Cl@ve credential input whose name and
    description read like nothing of the sort. The first assertion pins
    that, so this proof cannot quietly decay into a lexical match. Only
    its membership of the auth section gives it away -- which is also
    the only evidence an editorial change cannot remove.
    """
    field = ProfileFieldDefinition(
        key="contraste_qr",
        type=ProfileFieldType.STRING,
        sensitivity=SensitivityClass.IDENTITY,
        description="Value the QR route asks a holder to confirm.",
    )
    haystack = f"auth.{field.key} {field.description}".casefold()
    assert not [word for word in _CREDENTIAL_EVIDENCE_KEYWORDS if word in haystack], (
        "this proof needs a field the lexical arm would NOT match"
    )

    assert _misdeclared(_schema_with(field)) == {"auth.contraste_qr": ["section:auth"]}


def test_the_gate_refuses_a_credential_named_field_outside_the_credential_sections() -> None:
    """The lexical arm bites where the structural arm is blind.

    A credential-shaped field can land in any section, and the
    structural presumption reaches only those that exist to hold
    authentication material. Placed outside them, wording is the only
    evidence there is -- so this control runs in a section the
    structural arm does not police, keeping the two proofs independent.
    """
    misdeclared = _misdeclared(
        _schema_with(
            ProfileFieldDefinition(
                key="api_key",
                type=ProfileFieldType.STRING,
                sensitivity=SensitivityClass.IDENTITY,
                description="Token for the billing integration.",
            ),
            section_key="billing",
        ),
    )
    assert misdeclared == {"billing.api_key": ["key", "token"]}


@pytest.mark.parametrize(
    ("key", "description", "section_key"),
    [
        ("contraste_qr", "Value the QR route asks a holder to confirm.", "auth"),
        ("api_key", "Token for the billing integration.", "billing"),
    ],
)
def test_the_gate_accepts_the_same_field_declared_secret(key: str, description: str, section_key: str) -> None:
    """The negative half of both controls: classifying it correctly clears it.

    A gate that refused either way would satisfy the two controls above
    while making the declaration meaningless. Run against each arm's
    subject, so neither arm can be left refusing unconditionally.
    """
    assert not _misdeclared(
        _schema_with(
            ProfileFieldDefinition(
                key=key,
                type=ProfileFieldType.STRING,
                sensitivity=SensitivityClass.SECRET,
                description=description,
            ),
            section_key=section_key,
        ),
    )


def test_no_exemption_outlives_the_evidence_that_caused_it() -> None:
    """An exemption must name a field that still exists and is still presumed.

    An allowlist nobody prunes is how a gate rots: a stale entry sits
    there pre-approving whatever later occupies that path, and it reads
    to the next author as a decision rather than as residue. An entry
    survives only while the field it names is still presumed a
    credential -- on either kind of evidence, so moving a field out of
    the auth section retires its exemption just as rewording one does.
    """
    schema = load_user_profile_schema()
    presumed = _presumed_credential(schema)
    stale = sorted(path for path in _EXEMPT if path not in presumed)
    assert not stale, f"these exemptions no longer describe a presumed credential and must be removed: {stale}"
