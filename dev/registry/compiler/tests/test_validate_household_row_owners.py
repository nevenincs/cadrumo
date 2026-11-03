"""A household row object whose named owner does not cap it stops publication."""

from __future__ import annotations

from typing import Any

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.profile_row_limits import RowLimitOwner, row_limit_owners

from ...compiler import validator as registry_validator
from ...compiler.validate_household_row_owners import household_row_owner_failures, validate_household_row_owners

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_DESCENDANTS = "renta_family.descendiente"
_ASCENDANTS = "renta_family.ascendiente"


def _owner(object_path: str) -> RowLimitOwner:
    return row_limit_owners()[object_path]


def _without_limit(modelos: Any, group_id: str) -> tuple[Any, ...]:
    """Return ``modelos`` with the repeat limit of every layout group called ``group_id`` removed."""

    def block(value: Any) -> Any:
        if getattr(value, "kind", None) == "repeating" and value.id == group_id:
            return value.model_copy(update={"max_rows": None})
        return value

    def layout(value: Any) -> Any:
        pages = tuple(
            page.model_copy(
                update={
                    "sections": tuple(
                        section.model_copy(update={"blocks": tuple(block(item) for item in section.blocks)})
                        for section in page.sections
                    ),
                },
            )
            for page in value.pages
        )
        return value.model_copy(update={"pages": pages})

    return tuple(
        modelo.model_copy(
            update={
                "revisions": {
                    revision_id: revision.model_copy(
                        update={"form_layouts": tuple(layout(item) for item in revision.form_layouts)},
                    )
                    for revision_id, revision in modelo.revisions.items()
                },
            },
        )
        for modelo in modelos
    )


def test_the_registry_names_one_capped_group_for_each_household_object(_worker_compiled_authority: Any) -> None:
    modelos = _worker_compiled_authority.modelos

    assert dict(row_limit_owners()) == {
        _DESCENDANTS: RowLimitOwner(form="100", group_id="hijo-rows"),
        _ASCENDANTS: RowLimitOwner(form="100", group_id="ascendiente-rows"),
    }
    assert household_row_owner_failures(modelos, row_limit_owners()) == []
    assert validate_household_row_owners(modelos) == ()


def test_an_owner_that_is_not_a_declared_form_is_refused(_worker_compiled_authority: Any) -> None:
    owners = {_DESCENDANTS: RowLimitOwner(form="999", group_id=_owner(_DESCENDANTS).group_id)}

    [failure] = household_row_owner_failures(_worker_compiled_authority.modelos, owners)

    assert "not a declared form" in failure


def test_an_owner_no_revision_reads_the_object_through_is_refused(_worker_compiled_authority: Any) -> None:
    owners = {"renta_family.not_a_household": _owner(_DESCENDANTS)}

    [failure] = household_row_owner_failures(_worker_compiled_authority.modelos, owners)

    assert "no revision reads it" in failure


def test_a_group_that_does_not_exist_is_refused_in_every_reading_revision(_worker_compiled_authority: Any) -> None:
    owners = {_DESCENDANTS: RowLimitOwner(form="100", group_id="no-such-rows")}

    failures = household_row_owner_failures(_worker_compiled_authority.modelos, owners)

    assert failures
    assert all("no layout has the repeating group 'no-such-rows' reading the object" in item for item in failures)


def test_a_group_over_another_object_is_refused(_worker_compiled_authority: Any) -> None:
    owners = {_DESCENDANTS: _owner(_ASCENDANTS)}

    failures = household_row_owner_failures(_worker_compiled_authority.modelos, owners)

    assert failures
    assert all("reading the object" in item for item in failures)


def test_a_named_group_without_a_repeat_limit_is_refused(_worker_compiled_authority: Any) -> None:
    owner = _owner(_DESCENDANTS)
    uncapped = _without_limit(_worker_compiled_authority.modelos, owner.group_id)

    failures = household_row_owner_failures(uncapped, {_DESCENDANTS: owner})

    assert failures
    assert all("declares no repeat limit" in item for item in failures)
    assert household_row_owner_failures(uncapped, {_ASCENDANTS: _owner(_ASCENDANTS)}) == []


def test_the_registry_build_refuses_an_owner_group_its_layout_does_not_declare(
    _worker_compiled_authority: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalogues = _worker_compiled_authority.catalogues
    original = catalogues.facts.facts["household-row-limit-owners"]
    variant = original.variants[0]
    entries = tuple(
        entry.model_copy(update={"value": "no-such-rows"}) if entry.key == f"group.{_DESCENDANTS}" else entry
        for entry in variant.payload.entries
    )
    changed = original.model_copy(
        update={
            "variants": (
                variant.model_copy(update={"payload": variant.payload.model_copy(update={"entries": entries})}),
            ),
        },
    )
    facts = catalogues.facts.model_copy(update={"facts": {**catalogues.facts.facts, original.fact_id: changed}})
    authority = CandidateFactAuthority(facts, catalogues.require_supported_filing_years())
    validator = registry_validator.RegistryValidator(catalogues.model_copy(update={"facts": facts}))
    monkeypatch.setattr(validator, "_validate_registry_modelos", lambda _modelos: [])
    monkeypatch.setattr(registry_validator, "validate_registry_scope", lambda _modelos: ())
    monkeypatch.setattr(registry_validator, "validate_form_geometry", lambda _modelos: ())

    with validating_governed_facts(authority), pytest.raises(RegistryValidationError, match="no-such-rows"):
        validator.validate_registry(_worker_compiled_authority.modelos)
