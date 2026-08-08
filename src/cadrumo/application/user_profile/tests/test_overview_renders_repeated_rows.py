"""Real-behavior proofs that repeated facts reach the manager's page.

The projection walks the schema, which says what a field holds but never
how many of it the taxpayer has. Repeated facts are addressed under an
index the schema does not mention — ``socios.0.nif``, and
``censo.divergencia.0.axis`` for an object field's instances — so reading
the unindexed path found nothing, and five repeatable sections plus the
censal divergence namespace each rendered one permanently blank row
however much the profile held. A page whose stated purpose is answering
"what does my profile hold" answered "nothing" for every socio, activity,
property, usage ratio and deferred divergence on record.

Three claims carry the weight here. Instances must be VISIBLE, with their
values, one row each. An empty repeatable section must still show what a
row would hold, because that is the honest answer to "you have no socios"
and is the one case the old blank row got right. And an instance of a
SECRET-classed field must mask exactly as the field does — an indexed path
matches no schema field, so a projection that resolved sensitivity from
the path would hand every such row to the keyword net and render the ones
it did not recognise in the clear.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.classification import SensitivityClass
from ....domain.user_profile import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
    UserProfileFact,
    UserProfileRecord,
    UserProfileStatus,
    load_user_profile_schema,
    profile_field_label,
)
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...workflow import workflow_state_repository
from .. import (
    MASKED_PLACEHOLDER,
    ProfileRepository,
    build_lifecycle_service,
    build_profile_overview,
    profile_create_storage_span,
)
from .._completeness import missing_required_field_paths
from .._projections import record_to_path_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_TAX_ID = "12345678Z"
_SOCIOS = "attribution_entity_socios"
_DIVERGENCIA = "censo.divergencia"
_SECRET_VALUE = "a-distinctive-row-secret"  # noqa: S105 - synthetic test fixture


def _register_active() -> None:
    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id=_BUCKET_ID,
            display_name="repeated-rows-operator",
            overrides={"identity.tax_id": _TAX_ID},
        ),
    )


def _append_facts(*facts: UserProfileFact) -> None:
    repository = ProfileRepository()
    aggregate = repository.load(_BUCKET_ID)
    record = aggregate.record
    repository.save(
        aggregate.model_copy(
            update={"record": record.model_copy(update={"facts": (*record.facts, *facts)})},
        ),
    )


def _socio_row(index: int, *, nif: str, name: str, base: str) -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path=f"{_SOCIOS}.{index}.nif", value=nif),
        UserProfileFact(path=f"{_SOCIOS}.{index}.name", value=name),
        UserProfileFact(path=f"{_SOCIOS}.{index}.share_pct", value=Decimal("25")),
        UserProfileFact(path=f"{_SOCIOS}.{index}.base_imponible_assigned", value=Decimal(base)),
        UserProfileFact(path=f"{_SOCIOS}.{index}.role", value="socio"),
    )


def _rows_by_path(section_key: str) -> dict[str, str | None]:
    record = build_lifecycle_service(bucket_id=_BUCKET_ID).read(_BUCKET_ID)
    overview = build_profile_overview(record)
    section = next(view for view in overview.sections if view.key == section_key)
    return {field.path: field.value for field in section.fields}


def test_a_taxpayer_with_three_socios_sees_three_rows() -> None:
    """The reported defect: repeatable rows were invisible, values and all.

    Asserted on the VALUES rather than on the row count, because a
    projection that emitted three groups of blanks would satisfy a count
    and still hide everything the taxpayer entered.
    """

    _register_active()
    _append_facts(
        *_socio_row(0, nif="B12345678", name="Socio Uno", base="1000"),
        *_socio_row(1, nif="B87654321", name="Socio Dos", base="2000"),
        *_socio_row(2, nif="B11223344", name="Socio Tres", base="3000"),
    )

    rows = _rows_by_path(_SOCIOS)

    assert rows.get(f"{_SOCIOS}.0.name") == "Socio Uno"
    assert rows.get(f"{_SOCIOS}.1.name") == "Socio Dos"
    assert rows.get(f"{_SOCIOS}.2.name") == "Socio Tres"
    assert rows.get(f"{_SOCIOS}.2.base_imponible_assigned") == "3000"
    assert f"{_SOCIOS}.name" not in rows, (
        "the unindexed blank row survived alongside the real ones, which is the "
        f"answer 'you have no socios' given to a taxpayer who has three; rows={sorted(rows)}"
    )


def test_rows_are_ordered_by_their_stored_index() -> None:
    """Row ten belongs after row two, which a lexicographic ordering denies."""

    _register_active()
    _append_facts(
        *_socio_row(2, nif="B00000002", name="Socio Dos", base="200"),
        *_socio_row(10, nif="B00000010", name="Socio Diez", base="1000"),
    )

    ordered = [path for path in _rows_by_path(_SOCIOS) if path.endswith(".name")]

    assert ordered == [f"{_SOCIOS}.2.name", f"{_SOCIOS}.10.name"]


def test_a_repeatable_section_with_no_rows_still_shows_what_a_row_would_hold() -> None:
    """An empty section still shows what a row would hold, which is a real answer.

    The one case the defect got right, so it must survive the repair:
    replacing the blank row with nothing would say the section does not
    exist rather than that it is empty.
    """

    _register_active()

    rows = _rows_by_path(_SOCIOS)

    declared = load_user_profile_schema().section(_SOCIOS).fields
    assert sorted(rows) == sorted(f"{_SOCIOS}.{field.key}" for field in declared)
    assert set(rows.values()) == {None}


def test_an_object_field_renders_one_row_per_indexed_leaf() -> None:
    """A censal divergence is stored under leaves the schema never declares.

    ``censo.divergencia`` is an object field, not a repeatable section: its
    instances carry ``axis``/``artefact_value``/``source``, none of which
    the schema names, so both the instance count and the leaf set are the
    record's to state.
    """

    _register_active()
    _append_facts(
        UserProfileFact(path=f"{_DIVERGENCIA}.0.axis", value="censo.iae_epigrafe"),
        UserProfileFact(path=f"{_DIVERGENCIA}.0.artefact_value", value="6910"),
        UserProfileFact(path=f"{_DIVERGENCIA}.0.source", value="censo_artefact"),
        UserProfileFact(path=f"{_DIVERGENCIA}.1.axis", value="censo.epigrafe_secundario"),
        UserProfileFact(path=f"{_DIVERGENCIA}.1.artefact_value", value="7220"),
        UserProfileFact(path=f"{_DIVERGENCIA}.1.source", value="censo_artefact"),
    )

    rows = _rows_by_path("censo")

    assert rows.get(f"{_DIVERGENCIA}.0.artefact_value") == "6910"
    assert rows.get(f"{_DIVERGENCIA}.1.axis") == "censo.epigrafe_secundario"
    assert _DIVERGENCIA not in rows, "the namespace path itself was offered as a row"


def test_a_censo_divergencia_axis_row_shows_the_disputed_fields_label() -> None:
    """The manager names WHICH field AEAT disputes, not its raw schema path.

    Before this, the ``axis`` leaf rendered its stored value verbatim -- the
    dotted schema path (``contact.fiscal_address``) no operator reads --
    beside a leaf suffix of the raw stored key (``(axis)``). Both now
    resolve through operator-facing prose: the value through
    :func:`resolve_profile_field_label_for_path`, the leaf suffix through
    the same locale catalogue every other row label reads.
    """

    _register_active()
    _append_facts(
        UserProfileFact(path=f"{_DIVERGENCIA}.0.axis", value="contact.fiscal_address"),
        UserProfileFact(path=f"{_DIVERGENCIA}.0.artefact_value", value="CALLE REAL 2"),
    )

    rows = _rows_by_path("censo")
    section = next(
        view
        for view in build_profile_overview(build_lifecycle_service(bucket_id=_BUCKET_ID).read(_BUCKET_ID)).sections
        if view.key == "censo"
    )
    axis_view = next(field for field in section.fields if field.path == f"{_DIVERGENCIA}.0.axis")
    expected_label = profile_field_label("contact", load_user_profile_schema().field("contact.fiscal_address"))

    assert axis_view.value == expected_label
    assert rows.get(f"{_DIVERGENCIA}.0.artefact_value") == "CALLE REAL 2", "the sibling leaf must render untouched"
    assert "(axis)" not in axis_view.label, "the raw stored leaf key leaked into the row label"


def test_a_censo_divergencia_axis_row_falls_back_when_the_path_is_unresolvable() -> None:
    """Anti-tautology: an axis naming no real schema field is left as-is, not invented a label."""

    _register_active()
    _append_facts(UserProfileFact(path=f"{_DIVERGENCIA}.0.axis", value="no.such.schema.path"))

    rows = _rows_by_path("censo")

    assert rows.get(f"{_DIVERGENCIA}.0.axis") == "no.such.schema.path"


def test_a_namespace_field_with_no_instances_contributes_no_row() -> None:
    """An object field's bare path is not a blank; it is not a slot at all.

    Nothing writes it and nothing reads it, so a row offered for it can
    only ever be empty — while counting against the progress line the
    operator reads, and accepting a typed value that vanishes.
    """

    _register_active()

    censo = _rows_by_path("censo")

    assert not [path for path in censo if path.startswith(_DIVERGENCIA)]


def test_an_instance_of_a_secret_field_is_masked_like_the_field() -> None:
    """The confidentiality guard on the new rows.

    An indexed path matches no schema field, so a projection resolving
    sensitivity from the path would see ``None`` and drop the row to the
    keyword net — which recognises ``token`` and ``clave`` but not the
    field this declares. The declaration has to travel with the row.

    The whole serialised view is searched, so a future edit that carries
    the raw value somewhere else in the model still fails.
    """

    record = UserProfileRecord(
        profile_id=_PROFILE_ID,
        display_name="secret-row-operator",
        status=UserProfileStatus.ACTIVE,
        facts=(UserProfileFact(path="vaults.0.recovery_phrase", value=_SECRET_VALUE),),
    )

    overview = build_profile_overview(record, schema=_secret_row_schema())

    row = next(field for field in overview.sections[0].fields if field.path == "vaults.0.recovery_phrase")
    assert row.masked
    assert row.value == MASKED_PLACEHOLDER
    assert _SECRET_VALUE not in overview.model_dump_json()


def test_a_non_secret_instance_is_not_masked() -> None:
    """The positive control for the masking proof.

    Without it, a projection that masked every indexed row unconditionally
    would pass the guard above while hiding every value this change exists
    to show.
    """

    record = UserProfileRecord(
        profile_id=_PROFILE_ID,
        display_name="secret-row-operator",
        status=UserProfileStatus.ACTIVE,
        facts=(UserProfileFact(path="vaults.0.label", value="Caja fuerte"),),
    )

    overview = build_profile_overview(record, schema=_secret_row_schema())

    row = next(field for field in overview.sections[0].fields if field.path == "vaults.0.label")
    assert not row.masked
    assert row.value == "Caja fuerte"


def test_a_rendered_row_names_the_instance_it_belongs_to() -> None:
    """Three socios yield three identically-labelled rows unless the row says which.

    The path that distinguishes them is not a column, so the instance
    travels as data for the surface to present.
    """

    _register_active()
    _append_facts(
        *_socio_row(0, nif="B12345678", name="Socio Uno", base="1000"),
        *_socio_row(1, nif="B87654321", name="Socio Dos", base="2000"),
    )
    record = build_lifecycle_service(bucket_id=_BUCKET_ID).read(_BUCKET_ID)
    section = next(view for view in build_profile_overview(record).sections if view.key == _SOCIOS)

    indexed = {field.path: field.row_index for field in section.fields}

    assert indexed[f"{_SOCIOS}.0.name"] == "0"
    assert indexed[f"{_SOCIOS}.1.name"] == "1"


def test_an_ordinary_field_belongs_to_no_instance() -> None:
    """The counterpart, so ``row_index`` cannot be set unconditionally."""

    _register_active()
    record = build_lifecycle_service(bucket_id=_BUCKET_ID).read(_BUCKET_ID)
    identity = next(view for view in build_profile_overview(record).sections if view.key == "identity")

    assert {field.row_index for field in identity.fields} == {None}


def test_the_rendered_rows_and_the_reported_missing_paths_address_one_row_set() -> None:
    """They disagreed about repeatable rows, which is the whole defect.

    Completeness was made row-aware and the display was not, so the page
    named ``socios.1.name`` as missing while offering no row at that path
    for the operator to fill. Asserted as containment rather than equality
    because a missing path is by definition one the row does not carry a
    value for, while the row set covers filled fields too.
    """

    _register_active()
    _append_facts(
        *_socio_row(0, nif="B12345678", name="Socio Uno", base="1000"),
        UserProfileFact(path=f"{_SOCIOS}.1.nif", value="B87654321"),
    )
    record = build_lifecycle_service(bucket_id=_BUCKET_ID).read(_BUCKET_ID)
    overview = build_profile_overview(record)

    rendered = {field.path for section in overview.sections for field in section.fields}
    reported = set(missing_required_field_paths(load_user_profile_schema(), record_to_path_values(record)))

    assert f"{_SOCIOS}.1.name" in reported, "the incomplete second row stopped being reported"
    assert reported <= rendered, f"named as missing but offered no row: {sorted(reported - rendered)}"


def _secret_row_schema() -> ProfileSchemaDefinition:
    """A repeatable section whose secret field is named nothing like a credential.

    ``recovery_phrase`` is deliberately outside the keyword net: it carries
    none of ``password``, ``secret``, ``token``, ``key``, ``clave`` or
    their Spanish siblings. So a projection that lost the declaration and
    fell back to the keywords renders it in the clear, and the masking test
    fails rather than passing on the net by accident.
    """
    return ProfileSchemaDefinition(
        id="test.overview",
        version=1,
        title="Repeated row schema",
        snapshot_policy=ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH,
        remove_policy=ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS,
        sections=(
            ProfileSectionDefinition(
                key="vaults",
                title="Vaults",
                sensitivity=SensitivityClass.SECRET,
                repeatable=True,
                fields=(
                    ProfileFieldDefinition(
                        key="label",
                        type=ProfileFieldType.STRING,
                        required=False,
                        sensitivity=SensitivityClass.IDENTITY,
                        description="Operator's name for this vault",
                    ),
                    ProfileFieldDefinition(
                        key="recovery_phrase",
                        type=ProfileFieldType.STRING,
                        required=False,
                        sensitivity=SensitivityClass.SECRET,
                        description="Words restoring access to this vault",
                    ),
                ),
            ),
        ),
    )


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield
