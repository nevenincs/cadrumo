"""The status page must decide an indexed fact by its declaration, not its spelling.

The status walk is fact-driven, so it sees the indexed paths a repeated
fact is stored under (``socios.0.nif``, ``censo.divergencia.0.axis``)
where the manager's schema-driven walk did not. An indexed path matches no
schema field, so an exact lookup raised and the row fell through to the
keyword net -- a floor meant for facts the schema does not know, not a
second opinion on the ones it declares.

That mattered the moment the manager began rendering the same facts, since
the two surfaces share one masking authority precisely so a value one
protects cannot be exposed by the other. Divergence is the failure this
pins, so the guard is stated on the SENSITIVITY reaching the authority
rather than on a rendered string.

Both directions are asserted, because reducing the path to its declaring
field can only be right if it moves the answer in both: a declared secret
whose leaf the net would not recognise must mask, and a declared
non-secret whose leaf the net WOULD recognise must not.
"""

from __future__ import annotations

import pytest

from ....core.classification import SensitivityClass
from ....domain.user_profile.labels import profile_field_label
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.schema import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord, section_field_key
from ..status_projection import _build_fact_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "33333333-3333-4333-8333-333333333333"


def test_an_indexed_path_resolves_to_the_field_that_declares_it() -> None:
    """The reduction the status walk now performs, against the shipped schema."""
    schema = load_user_profile_schema()

    assert section_field_key("attribution_entity_socios.0.nif") == "attribution_entity_socios.nif"
    assert section_field_key("censo.divergencia.0.axis") == "censo.divergencia"
    assert schema.field(section_field_key("attribution_entity_socios.0.nif")).key == "nif"


def test_an_exact_lookup_still_refuses_an_indexed_path() -> None:
    """The positive control for the reduction above.

    Without it the test could pass on a schema that happened to resolve
    indexed paths already, proving nothing about the reduction.
    """
    from ....domain.user_profile.errors import UserProfileError

    with pytest.raises(UserProfileError):
        load_user_profile_schema().field("attribution_entity_socios.0.nif")


def test_an_indexed_row_of_a_declared_secret_is_masked() -> None:
    """A secret whose leaf the keyword net does not recognise must still mask."""

    (row,) = _rows_for(UserProfileFact(path="vaults.0.recovery_phrase", value="the-actual-phrase"))

    assert row.masked


def test_an_indexed_row_of_a_declared_non_secret_is_not_masked() -> None:
    """The other direction: a declaration is not overridden by a leaf's spelling.

    ``passphrase_hint`` is declared ``IDENTITY`` and carries a keyword the
    net matches, so a surface deciding by spelling would mask a fact the
    schema says is ordinary — hiding data the operator asked to see.
    """

    (row,) = _rows_for(UserProfileFact(path="vaults.0.passphrase_hint", value="the-hint"))

    assert not row.masked


def test_an_undeclared_indexed_path_still_falls_to_the_keyword_net() -> None:
    """The floor stays a floor: a fact no schema field declares is unchanged."""

    (row,) = _rows_for(UserProfileFact(path="unknown_section.0.api_key", value="AKIA-not-a-real-key"))

    assert row.masked


def test_each_instance_of_a_repeated_field_gets_its_own_distinguishable_row() -> None:
    """Repeated instances need distinguishable rows on a surface with one column.

    The label is the field's authored name rather than its raw dotted path, so
    two instances of one field would collide into two identical rows and the
    operator could not tell which value belonged to which. What must hold is
    that the instance is still carried, not that the label spells the path.
    """

    rows = _rows_for(
        UserProfileFact(path="vaults.0.passphrase_hint", value="first"),
        UserProfileFact(path="vaults.1.passphrase_hint", value="second"),
    )

    labels = [row.label for row in rows]
    assert len(labels) == 2
    assert len(set(labels)) == 2, f"repeated instances collapsed onto one label: {labels}"


def test_a_censo_divergencia_axis_row_resolves_to_the_disputed_fields_label() -> None:
    """A cotejo divergence names WHICH field disagrees, not its raw schema path.

    Before this, ``censo.divergencia.0.axis`` rendered its stored value
    verbatim -- the dotted schema path AEAT and the operator disagree on
    (``contact.fiscal_address``) -- which no operator reading the status
    page can act on. The axis leaf now resolves through the same
    field-label authority the manager overview reads, against the real
    shipped schema so the assertion is against what an operator actually
    meets.
    """
    rows = _rows_for_schema_free(
        UserProfileFact(path="censo.divergencia.0.axis", value="contact.fiscal_address"),
        UserProfileFact(path="censo.divergencia.0.artefact_value", value="CALLE REAL 2"),
    )

    values = {row.value for row in rows}
    expected_label = profile_field_label("contact", load_user_profile_schema().field("contact.fiscal_address"))
    assert "contact.fiscal_address" not in values, "the raw internal schema path leaked to the operator"
    assert expected_label in values
    assert "CALLE REAL 2" in values, "the sibling artefact_value leaf must render untouched"


def test_a_censo_divergencia_axis_row_falls_back_to_the_raw_path_when_unresolvable() -> None:
    """Anti-tautology: an axis the schema does not declare is not silently invented a label.

    Without this, a resolver that always returned SOME string regardless of
    input would pass the test above by accident.
    """
    rows = _rows_for_schema_free(
        UserProfileFact(path="censo.divergencia.0.axis", value="no.such.schema.path"),
    )

    assert {row.value for row in rows} == {"no.such.schema.path"}


def test_a_censo_divergencia_leaf_label_is_translated_not_raw() -> None:
    """The leaf suffix is operator prose, not the stored internal field name.

    ``(axis)`` / ``(artefact_value)`` / ``(source)`` are the leaf keys the
    writing family chose for the record, not words an operator was ever
    meant to read on a localized Spanish screen.
    """
    rows = _rows_for_schema_free(
        UserProfileFact(path="censo.divergencia.0.axis", value="contact.fiscal_address"),
        UserProfileFact(path="censo.divergencia.0.artefact_value", value="CALLE REAL 2"),
        UserProfileFact(path="censo.divergencia.0.source", value="censo_artefact_g313"),
    )
    field_label = profile_field_label("censo", load_user_profile_schema().field("censo.divergencia"))

    labels = {row.label for row in rows if row.label.startswith(field_label)}
    assert labels, f"no censo.divergencia rows rendered under label {field_label!r}: {[r.label for r in rows]}"
    for raw_leaf in ("(axis)", "(artefact_value)", "(source)"):
        assert not any(raw_leaf in label for label in labels), f"raw leaf key {raw_leaf!r} leaked into a label"


def test_an_unindexed_row_still_reads_its_description() -> None:
    """The labelling of every ordinary fact is untouched."""

    rows = _rows_for(UserProfileFact(path="vaults.0.passphrase_hint", value="x"))
    assert rows, "the projection produced no rows at all"

    unindexed = _rows_for_schema_free(UserProfileFact(path="identity.tax_id", value="12345678Z"))
    row = next(row for row in unindexed if row.value == "12345678Z")
    assert row.label != "identity.tax_id"


def _rows_for(*facts: UserProfileFact):
    """Project facts through the real status builder under a synthetic schema."""
    return _build_fact_rows(_record(*facts), schema=_vault_schema())


def _rows_for_schema_free(*facts: UserProfileFact):
    """Project facts through the real status builder under the shipped schema."""
    return _build_fact_rows(_record(*facts))


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=facts,
    )


def _vault_schema() -> ProfileSchemaDefinition:
    """A repeatable section pairing a secret the net misses with a non-secret it hits.

    ``recovery_phrase`` carries no keyword; ``passphrase_hint`` carries
    one. So the two fields fail in opposite directions under a
    spelling-driven decision, and a single test cannot pass both by
    accident.
    """
    return ProfileSchemaDefinition(
        id="test.status",
        version=1,
        title="Status indexed-fact schema",
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
                        key="recovery_phrase",
                        type=ProfileFieldType.STRING,
                        required=False,
                        sensitivity=SensitivityClass.SECRET,
                        description="Words restoring access to this vault",
                    ),
                    ProfileFieldDefinition(
                        key="passphrase_hint",
                        type=ProfileFieldType.STRING,
                        required=False,
                        sensitivity=SensitivityClass.IDENTITY,
                        description="Reminder the operator chose for themselves",
                    ),
                ),
            ),
        ),
    )
