"""Encrypted-SQL persistence-boundary roundtrip for the Art. 81.1 month SET.

``renta_family.descendiente.{n}.meses_madre_trabajo`` records WHICH calendar
months the mother met the Art. 81.1 LIRPF requirements, because Art. 81.2
prorates its guardería increment by the months in which the 81.1 and 81.2
requirements hold "de forma simultánea" — an intersection of two month sets that
a count cannot express.

That makes the persisted shape load-bearing rather than incidental. A month lost
or reordered between save and reload silently changes the proration basis, and
the direction of that error is an OVER-grant of the deducción, which
under-declares tax. So the boundary is pinned here with real adapters only: a
real file-backed storage root, a real per-bucket wrapped DEK minted through the
production create span, and a real :class:`SecureObjectRepository` behind
encrypted SQL.

The anti-tautology proof drives a CORRUPTED serialised value through the same
reload path and asserts it refuses for the right reason, rather than resolving
to an empty set. An empty set is not a safe failure here: it withholds the whole
deducción and the increment that prorates by it, so a silently-emptied value
would make a deduction disappear with nothing said.

See Also:
    :func:`~domain.contribuyente.parse_meses_trabajo`:
        The one grammar this boundary serialises to and parses back.
    :class:`~domain.contribuyente.family.DescendantInfo`:
        Carrier of the month set, whose validator refuses a repeat or an
        unsorted set so the stored form is canonical.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.contribuyente import (
    DescendantInfo,
    descendant_facts_from_list,
    descendant_list_from_facts,
    serialise_meses_trabajo,
)
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import schema_valid_placeholder
from ...workflow import WorkflowState
from .._orchestration import profile_create_storage_span, register_active_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
_MESES_PATH = "renta_family.descendiente.0.meses_madre_trabajo"

#: AEAT's caso a: the mother is entitled May to August. Non-contiguous with the
#: year's start and end on purpose, so a boundary that stored only a COUNT, only
#: the first month, or only the span length would be visibly wrong on reload.
_DECLARED_MONTHS = (5, 6, 7, 8)


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path) -> Iterator[None]:
    """Real file-backed storage root for the production create-span mint path."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def _required_facts(schema: ProfileSchemaDefinition) -> list[UserProfileFact]:
    """Every required non-repeatable schema field with a placeholder value."""
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value=schema_valid_placeholder(field)))
    return facts


def _fully_populated_child() -> DescendantInfo:
    """One descendant with every defaultable field carrying a NON-default value.

    A save-drops-field / load-re-defaults-field regression is invisible when the
    fixture leaves a field at its default, so every field that HAS a default is
    moved off it here.

    Two deliberate exceptions, both forced by the model rather than by
    convenience. ``gastos_guarderia_euros`` stays at its default because the
    record admits exactly one spend authority per child and the monthly map is
    the richer of the two, so setting both is refused at construction. And
    ``death_date`` stays ``None`` because a death date closes the year the other
    fields are being asserted across. Both are stated rather than silently
    skipped, so a later reader can tell a forced omission from a forgotten one.
    """
    return DescendantInfo(
        birth_date=date(2022, 3, 1),
        inscripcion_registro_civil_date=date(2022, 3, 9),
        discapacidad_grado=33,
        convive_con_contribuyente=False,
        dependencia_economica=True,
        custodia_compartida=True,
        rentas_anuales_euros=Decimal("1234.56"),
        presenta_declaracion_propia=True,
        prorrata_minimo=True,
        meses_madre_trabajo=_DECLARED_MONTHS,
        alta_posterior_nacimiento_mes=_DECLARED_MONTHS[0],
        nif="12345678Z",
    )


def _persist_and_reload(facts: tuple[UserProfileFact, ...], schema: ProfileSchemaDefinition) -> UserProfileRecord:
    """Push facts through the real encrypted-SQL boundary and read them back."""
    with profile_create_storage_span(_BUCKET) as routing_profile_id:
        state = register_active_profile(
            WorkflowState(),
            profile_id=_BUCKET,
            display_name="meses madre trabajo roundtrip",
            facts=facts,
            schema=schema,
            routing_profile_id=routing_profile_id,
        )
        record = state.active_profile_record(schema=schema)
    assert record is not None
    return record


def _descendant_facts(record: UserProfileRecord) -> dict[str, str]:
    return {fact.path: str(fact.value) for fact in record.facts if fact.path.startswith("renta_family.descendiente.")}


def test_the_month_set_survives_the_encrypted_boundary_intact(schema: ProfileSchemaDefinition) -> None:
    """Strict equality on the whole record across a real save and reload.

    Asserted as model equality rather than field-by-field, so a field this test
    never thought to name is still covered.
    """
    child = _fully_populated_child()
    facts = (
        *(
            UserProfileFact(path="iva.regime", value="GENERAL") if f.path == "iva.regime" else f
            for f in _required_facts(schema)
        ),
        *(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list((child,))),
    )

    record = _persist_and_reload(facts, schema)
    reloaded = descendant_list_from_facts(_descendant_facts(record))

    assert reloaded == (child,)
    assert reloaded[0].meses_madre_trabajo == _DECLARED_MONTHS


def test_the_stored_form_is_the_canonical_expanded_month_list(schema: ProfileSchemaDefinition) -> None:
    """The fact holds expanded months, not a count and not the range shorthand.

    Pinned because the reload above would pass equally well against a stored
    ``"4"``. Naming the on-disk text is what distinguishes a boundary that
    carries the months from one that reconstructs a plausible set.
    """
    child = _fully_populated_child()
    facts = (
        *(
            UserProfileFact(path="iva.regime", value="GENERAL") if f.path == "iva.regime" else f
            for f in _required_facts(schema)
        ),
        *(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list((child,))),
    )

    record = _persist_and_reload(facts, schema)

    assert _descendant_facts(record)[_MESES_PATH] == serialise_meses_trabajo(_DECLARED_MONTHS)
    assert _descendant_facts(record)[_MESES_PATH] == "05;06;07;08"


@pytest.mark.parametrize(
    ("corrupted", "reason"),
    [
        ("05;05;07;08", "more than once"),
        ("05;13;07", "outside"),
        ("05;;07", "empty entry"),
        ("mayo", "not a number"),
    ],
    ids=["repeat", "out-of-range", "empty-entry", "not-a-number"],
)
def test_a_corrupted_stored_month_set_refuses_rather_than_emptying(
    schema: ProfileSchemaDefinition,
    corrupted: str,
    reason: str,
) -> None:
    """Anti-tautology: corrupt the persisted text, reload, and demand a refusal.

    Driven through the stored STRING rather than by constructing an invalid
    model, because the model's own validator would reject that before any
    persistence code ran — which would prove the validator works and say nothing
    about the boundary. Here the bytes go in through the real store and the
    refusal has to come from the reload path.

    If this ever passes with the boundary broken, every roundtrip here is
    tautological.
    """
    child = _fully_populated_child()
    facts = (
        *(
            UserProfileFact(path="iva.regime", value="GENERAL") if f.path == "iva.regime" else f
            for f in _required_facts(schema)
        ),
        *(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list((child,))),
    )

    record = _persist_and_reload(facts, schema)
    stored = _descendant_facts(record)
    assert stored[_MESES_PATH] != corrupted, "the corruption must differ from the honest value"
    stored[_MESES_PATH] = corrupted

    with pytest.raises(Exception, match=reason):
        descendant_list_from_facts(stored)


def test_a_bare_number_reads_as_that_MONTH_and_not_as_a_count() -> None:
    """The retired count text is not detectable as corruption, and that is safe here.

    ``"4"`` was what the previous count-based shape stored to mean "four months
    qualified". Under the month grammar the same text is a well-formed
    declaration of APRIL, so the parser cannot tell the two apart — there is no
    refusal to assert, and claiming one would be asserting behaviour the code
    does not have.

    That is safe only because of the compatibility posture: no released version
    of this application ever wrote the count form, so no stored fact anywhere
    carries it. It is recorded rather than defended against, because the
    alternative — a branch that sniffed a bare number and rejected it — would be
    read-tolerance for data that does not exist, and it would also reject the
    legitimate operator who worked in April alone.

    The coherence rule is what catches it in practice on any record that also
    declares the post-birth alta month, since a count and a first month will not
    agree except by accident. That is a side effect worth knowing about, not the
    guarantee.
    """
    from ....domain.contribuyente import parse_meses_trabajo

    assert parse_meses_trabajo("4", field="f") == (4,)
    assert parse_meses_trabajo("4", field="f") != tuple(range(1, 5))
