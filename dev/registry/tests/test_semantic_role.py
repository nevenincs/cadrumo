"""Roundtrip and validator tests for semantic_role + aliases.

`CasillaDefinition` gained an optional `semantic_role: str | None`
slot and an `aliases: tuple[CasillaAlias, ...]` slot. The
snapshot-build validator now enforces that every casilla sharing a
`semantic_role` declares the same `data_type` and structurally
compatible `constraints`. Single-occurrence role values are reported
as typo-twin diagnostic findings and fail registry-scope validation.

These tests exercise the field shape, the consistency validator,
the typo-twin diagnostic surface, and the alias-preservation
round-trip.
"""

from __future__ import annotations

from typing import Literal, TypedDict

import pytest
from pydantic import ValidationError

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaAlias, CasillaConstraints, CasillaDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.validate_semantic_roles import (
    semantic_role_cardinality_failures,
    semantic_role_consistency_failures,
)
from .semantic_role_support import (
    registry_modelo,
    semantic_role_casilla,
)
from .synthetic_locale_fixtures import (
    synthetic_locale_scope,
    write_test_label,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Three consecutive exercises of the support envelope name the editions of the synthetic one-revision trees.
_EDITIONS = tuple(str(year) for year in filing_year_envelope().years[-3:])
_ED_1, _ED_2, _ED_3 = _EDITIONS


__all__ = ["synthetic_locale_scope"]


class _PartialCasillaUpdate(TypedDict, total=False):
    """Partial kwargs update for _casilla fixture in parametrize tests."""

    semantic_role: str
    semantic_role_cardinality: str
    semantic_role_cardinality_reason: str


class TestSemanticRoleFieldShape:
    def test_default_role_is_none(self) -> None:
        c = semantic_role_casilla()
        assert c.semantic_role is None
        assert c.aliases == ()

    def test_role_round_trips(self) -> None:
        c = semantic_role_casilla(semantic_role="taxpayer_nif", data_type="nif")
        rebuilt = CasillaDefinition.model_validate(
            {**c.model_dump(), "localization_keys": c.localization_keys},
        )
        assert rebuilt.semantic_role == "taxpayer_nif"
        assert rebuilt == c

    def test_invalid_semantic_role_shape_rejected(self) -> None:
        cases: tuple[
            tuple[
                str,
                dict[
                    Literal[
                        "semantic_role",
                        "semantic_role_cardinality",
                        "semantic_role_cardinality_reason",
                    ],
                    str,
                ],
            ],
            ...,
        ] = (
            ("empty-role", {"semantic_role": ""}),
            (
                "singleton-without-role",
                {
                    "semantic_role_cardinality": "intentional_singleton",
                    "semantic_role_cardinality_reason": "2025-only legal slot",
                },
            ),
            (
                "singleton-without-reason",
                {
                    "semantic_role": "is_pf_mod_40_3_b2_base_tipo_3",
                    "semantic_role_cardinality": "intentional_singleton",
                },
            ),
            (
                "reason-without-singleton",
                {
                    "semantic_role": "is_pf_mod_40_3_b2_base_tipo_3",
                    "semantic_role_cardinality_reason": "2025-only legal slot",
                },
            ),
        )

        for case_id, updates in cases:
            try:
                semantic_role_casilla(**updates)
            except ValidationError:
                continue
            raise AssertionError(f"{case_id} accepted an invalid semantic-role shape")

    def test_empty_localization_keys_rejected(self) -> None:
        casilla = semantic_role_casilla()
        with pytest.raises(ValidationError, match="localization_keys"):
            CasillaDefinition.model_validate({**casilla.model_dump(), "localization_keys": ()})

    def test_empty_alias_localization_key_rejected(self) -> None:
        with pytest.raises(ValidationError, match="localization_key"):
            CasillaAlias(
                localization_key="",
                legal_refs=("ley-58-2003:art-29",),
                source_refs=("aeat-manual",),
            )

    def test_intentional_singleton_cardinality_round_trips(self) -> None:
        c = semantic_role_casilla(
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        rebuilt = CasillaDefinition.model_validate(
            {**c.model_dump(), "localization_keys": c.localization_keys},
        )
        assert rebuilt.semantic_role_cardinality == "intentional_singleton"
        assert rebuilt.semantic_role_cardinality_reason == "2025-only legal slot"

    def test_aliases_round_trip(self) -> None:
        alias = CasillaAlias(
            localization_key=write_test_label("NIF declarante"),
            legal_refs=("ley-58-2003:art-29",),
            source_refs=("aeat-manual",),
        )
        c = semantic_role_casilla(semantic_role="taxpayer_nif", data_type="nif", aliases=[alias])
        rebuilt = CasillaDefinition.model_validate(
            {
                **c.model_dump(),
                "localization_keys": c.localization_keys,
                "aliases": ({**alias.model_dump(), "localization_key": alias.localization_key},),
            },
        )
        assert len(rebuilt.aliases) == 1
        assert rebuilt.aliases[0].label == "NIF declarante"
        assert rebuilt.aliases[0].legal_refs == ("ley-58-2003:art-29",)


class TestValidateSemanticRoleConsistency:
    def test_no_role_declarations_passes(self) -> None:
        m = registry_modelo("180", _ED_1, [semantic_role_casilla()])
        assert semantic_role_consistency_failures([m]) == ()

    def test_matching_role_declarations_pass(self) -> None:
        a = semantic_role_casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = semantic_role_casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        m1 = registry_modelo("180", _ED_1, [a])
        m2 = registry_modelo("184", _ED_1, [b])
        assert semantic_role_consistency_failures([m1, m2]) == ()

    def test_diverging_data_type_rejected(self) -> None:
        a = semantic_role_casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = semantic_role_casilla(cid="b", semantic_role="taxpayer_nif", data_type="text")
        m1 = registry_modelo("180", _ED_1, [a])
        m2 = registry_modelo("184", _ED_1, [b])
        failures = semantic_role_consistency_failures([m1, m2])
        assert any("data_type" in f for f in failures)
        assert any("taxpayer_nif" in f for f in failures)

    def test_diverging_constraints_rejected(self) -> None:
        common_legal = ("ley-58-2003:art-29",)
        common_source = ("aeat-manual",)
        constrained = CasillaConstraints(sign="non_negative", legal_refs=common_legal, source_refs=common_source)
        unconstrained = CasillaConstraints(sign="any", legal_refs=common_legal, source_refs=common_source)
        a = semantic_role_casilla(cid="a", semantic_role="retenciones", data_type="money", constraints=constrained)
        b = semantic_role_casilla(cid="b", semantic_role="retenciones", data_type="money", constraints=unconstrained)
        m1 = registry_modelo("180", _ED_1, [a])
        m2 = registry_modelo("184", _ED_1, [b])
        failures = semantic_role_consistency_failures([m1, m2])
        assert any("constraints" in f for f in failures)

    def test_record_design_width_change_must_use_a_distinct_role(self) -> None:
        legal = ("orden-eha-3786-2008:art-1",)
        historical = semantic_role_casilla(
            cid=validated_casilla_id("historical-cnae", surface="semantic-role-width-test"),
            semantic_role="m303_prorrata_actividad_fila_1_cnae",
            data_type="text",
            constraints=CasillaConstraints(
                min_length=3, max_length=3, legal_refs=legal, source_refs=("aeat-dr-303-2025",)
            ),
        )
        widened = semantic_role_casilla(
            cid=validated_casilla_id("widened-cnae", surface="semantic-role-width-test"),
            semantic_role="m303_prorrata_actividad_fila_1_cnae",
            data_type="text",
            constraints=CasillaConstraints(
                min_length=4, max_length=4, legal_refs=legal, source_refs=("aeat-dr-303-2026",)
            ),
        )

        failures = semantic_role_consistency_failures(
            [registry_modelo("303", _ED_2, [historical]), registry_modelo("303", _ED_3, [widened])]
        )

        assert any("constraints incompatible" in failure for failure in failures)

    def test_record_design_enum_widening_preserves_a_stable_role(self) -> None:
        legal = ("orden-eha-3434-2007:art-1",)
        historical = semantic_role_casilla(
            cid=validated_casilla_id("historical-flag", surface="semantic-role-enum-test"),
            semantic_role="m322_identificacion_volumen_anual_no_cero",
            data_type="text",
            constraints=CasillaConstraints(
                max_length=1, enum=("1", "2"), legal_refs=legal, source_refs=("aeat-dr-322-2022",)
            ),
        )
        widened = semantic_role_casilla(
            cid=validated_casilla_id("widened-flag", surface="semantic-role-enum-test"),
            semantic_role="m322_identificacion_volumen_anual_no_cero",
            data_type="text",
            constraints=CasillaConstraints(
                max_length=1, enum=("0", "1", "2"), legal_refs=legal, source_refs=("aeat-dr-322-2026",)
            ),
        )

        assert (
            semantic_role_consistency_failures(
                [registry_modelo("322", _ED_1, [historical]), registry_modelo("322", _ED_3, [widened])]
            )
            == ()
        )

    @pytest.mark.parametrize("scope", ["same_revision", "cross_model"])
    def test_differing_enums_outside_revision_widening_are_rejected(self, scope: str) -> None:
        legal = ("ley-58-2003:art-29",)
        first = semantic_role_casilla(
            cid="first-enum",
            semantic_role="enum_scope_guard",
            constraints=CasillaConstraints(enum=("1",), legal_refs=legal, source_refs=("aeat-manual",)),
        )
        second = semantic_role_casilla(
            cid="second-enum",
            semantic_role="enum_scope_guard",
            constraints=CasillaConstraints(enum=("1", "2"), legal_refs=legal, source_refs=("aeat-manual",)),
        )
        modelos = (
            [registry_modelo("180", _ED_1, [first, second])]
            if scope == "same_revision"
            else [registry_modelo("180", _ED_1, [first]), registry_modelo("184", _ED_2, [second])]
        )

        assert any("constraints incompatible" in failure for failure in semantic_role_consistency_failures(modelos))

    def test_partially_overlapping_enum_recoding_across_revisions_is_rejected(self) -> None:
        legal = ("ley-58-2003:art-29",)
        historical = semantic_role_casilla(
            cid="historical-recoding",
            semantic_role="enum_recoding_guard",
            constraints=CasillaConstraints(enum=("1", "2"), legal_refs=legal, source_refs=("aeat-manual",)),
        )
        recoded = semantic_role_casilla(
            cid="recoded",
            semantic_role="enum_recoding_guard",
            constraints=CasillaConstraints(enum=("2", "3"), legal_refs=legal, source_refs=("aeat-manual",)),
        )

        failures = semantic_role_consistency_failures(
            [registry_modelo("180", _ED_1, [historical]), registry_modelo("180", _ED_2, [recoded])]
        )
        assert any("constraints incompatible" in failure for failure in failures)

    def test_enum_widening_does_not_mask_non_enum_constraint_changes(self) -> None:
        legal = ("ley-58-2003:art-29",)
        historical = semantic_role_casilla(
            cid="historical-width",
            semantic_role="enum_non_enum_guard",
            constraints=CasillaConstraints(max_length=1, enum=("1",), legal_refs=legal, source_refs=("aeat-manual",)),
        )
        widened_and_reshaped = semantic_role_casilla(
            cid="reshaped",
            semantic_role="enum_non_enum_guard",
            constraints=CasillaConstraints(
                max_length=2, enum=("1", "2"), legal_refs=legal, source_refs=("aeat-manual",)
            ),
        )

        failures = semantic_role_consistency_failures(
            [registry_modelo("180", _ED_1, [historical]), registry_modelo("180", _ED_2, [widened_and_reshaped])]
        )
        assert any("constraints incompatible" in failure for failure in failures)

    def test_independent_enum_supersets_across_revisions_are_rejected(self) -> None:
        legal = ("ley-58-2003:art-29",)
        observations = [
            semantic_role_casilla(
                cid=f"enum-observation-{edition}",
                semantic_role="enum_branch_guard",
                constraints=CasillaConstraints(enum=values, legal_refs=legal, source_refs=("aeat-manual",)),
            )
            for edition, values in zip(_EDITIONS, (("1",), ("1", "2"), ("1", "3")), strict=True)
        ]
        modelos = [
            registry_modelo("180", edition, [observation])
            for edition, observation in zip(_EDITIONS, observations, strict=True)
        ]

        assert any("constraints incompatible" in failure for failure in semantic_role_consistency_failures(modelos))


class TestValidateSemanticRoleCardinality:
    def test_intentional_singleton_role_with_single_occurrence_passes(self) -> None:
        c = semantic_role_casilla(
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        m = registry_modelo("202", f"{_ED_2}-y-siguientes", [c])
        assert semantic_role_cardinality_failures([m]) == ()

    def test_intentional_singleton_role_repeated_within_one_revision_fails(self) -> None:
        """POSITIVE CONTROL: the gate must still bite on a real duplicate.

        Two bearers inside ONE revision co-apply in a single filing, which is
        exactly the defect ``intentional_singleton`` exists to catch. If this
        ever passes, the cardinality axis has been removed rather than
        rescoped, which is worse than the artefact the rescoping fixed.
        """
        a = semantic_role_casilla(
            cid="a",
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        b = semantic_role_casilla(cid="b", semantic_role="is_pf_mod_40_3_b2_base_tipo_3")
        m = registry_modelo("202", f"{_ED_2}-y-siguientes", [a, b])
        failures = semantic_role_cardinality_failures([m])
        assert failures == (
            "semantic_role 'is_pf_mod_40_3_b2_base_tipo_3': casilla "
            f"202.{_ED_2}-y-siguientes.a declares semantic_role_cardinality "
            "'intentional_singleton' but role is shared by co-applying casillas "
            "(2 in one revision, 1 modelo(s))",
        )

    def test_intentional_singleton_role_in_a_second_modelo_fails(self) -> None:
        """POSITIVE CONTROL, second axis: two modelos genuinely co-exist.

        Modelo 303 and Modelo 390 are both filed, so a role borne by each is
        shared in the sense the marker denies. Only sibling revisions of ONE
        modelo are mutually exclusive.
        """
        a = semantic_role_casilla(
            cid="a",
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        b = semantic_role_casilla(cid="b", semantic_role="is_pf_mod_40_3_b2_base_tipo_3")
        m1 = registry_modelo("202", f"{_ED_2}-y-siguientes", [a])
        m2 = registry_modelo("303", f"{_ED_2}-y-siguientes", [b])
        failures = semantic_role_cardinality_failures([m1, m2])
        assert failures == (
            "semantic_role 'is_pf_mod_40_3_b2_base_tipo_3': casilla "
            f"202.{_ED_2}-y-siguientes.a declares semantic_role_cardinality "
            "'intentional_singleton' but role is shared by co-applying casillas "
            "(1 in one revision, 2 modelo(s))",
        )

    def test_intentional_singleton_role_across_sibling_revisions_passes(self) -> None:
        """NEGATIVE CONTROL: a revision split must not staleness-fail the marker.

        AEAT binds every ``(modelo, filing_year, period)`` to exactly one
        revision, so these two can never co-apply and the role has not gained a
        sibling -- the revision was cloned. Splitting a revision at a design
        re-layout clones every casilla, so counting raw observations would turn
        correct authoring into a validation failure that gets worse with each
        further split.
        """
        a = semantic_role_casilla(
            cid="a",
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        b = semantic_role_casilla(
            cid="a",
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        m1 = registry_modelo("202", f"{_ED_2}-y-siguientes", [a])
        m2 = registry_modelo("202", f"{_ED_3}-y-siguientes", [b])
        assert semantic_role_cardinality_failures([m1, m2]) == ()
