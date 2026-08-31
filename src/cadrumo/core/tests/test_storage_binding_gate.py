"""Every path-valued setting has a declared home, or the gate names it.

A location enrolls in the taxonomy when the application both *chooses* it and
*writes data* there. Failing either question makes it an escape -- but an
escape is a positive declaration carrying its role and its reason, never mere
absence from a frozenset, because absence is indistinguishable from oversight.
This gate is what makes that distinction enforceable: every ``Path``-typed
field on :class:`~core.config.Settings` is a taxonomy member, a declared
escape, or the storage root itself, and the three are total and disjoint.

Three properties, each closing a way the classification could rot:

- **Totality.** A new path field is unclassified on arrival and fails here,
  naming both remedies rather than merely refusing.
- **Disjointness.** A field cannot be a member *and* an escape; the taxonomy
  would then disagree with itself about whether the application writes there.
- **No stale entries.** A member or an escape naming a field that no longer
  exists is inventory claiming coverage nothing backs.

Discovery is anchored to ``Settings.model_fields``, a source independent of the
taxonomy. That independence is the whole reason the gate means anything, and it
has one specific failure mode worth naming: were the field set to come from the
taxonomy instead, both sides of the totality comparison would move together and
an empty discovery would compare empty against empty and pass. The
non-empty-discovery assertion below exists for exactly that, and it matters
most after the lifecycle gate stops hand-maintaining its own list -- the moment
the independent oracle would otherwise disappear with nobody looking for it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from ..config import Settings
from ..storage_taxonomy import (
    EXTERNAL_PATH_SETTINGS_FIELDS,
    STORAGE_FIELD_CATEGORIES,
    STORAGE_ROOT_SETTINGS_FIELD,
    STORAGE_TAXONOMY,
)
from ._settings_path_fields import annotation_mentions_path, path_typed_settings_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def unclassified_path_fields(model: type[BaseModel]) -> tuple[str, ...]:
    """Return ``model``'s path fields that are neither member, escape, nor root.

    A pure function over the model so the discrimination tests below can hand
    it a synthetic model carrying an unbound path field and prove the gate
    fires. A gate that cannot be shown to fail is not a gate, and a transient
    mutation of the real settings model proves that once, at the cost of a
    window in which the defect is shippable; this proves it on every run.
    """
    return tuple(
        sorted(
            path_typed_settings_fields(model)
            - set(STORAGE_FIELD_CATEGORIES)
            - set(EXTERNAL_PATH_SETTINGS_FIELDS)
            - {STORAGE_ROOT_SETTINGS_FIELD}
        )
    )


def _discovered() -> frozenset[str]:
    return path_typed_settings_fields(Settings)


def test_discovery_finds_a_non_empty_field_set() -> None:
    """A structural gate that discovers its own subject must find something.

    Without this, every assertion below is satisfiable by discovering nothing.
    The floor is deliberately a lower bound on an order of magnitude rather
    than today's exact count: a census rots on the next ordinary field, while
    "the model still has dozens of path fields" stays true and still refuses a
    discovery that has collapsed.
    """
    discovered = _discovered()
    assert len(discovered) >= 20, (
        f"path-field discovery found only {len(discovered)} field(s) on Settings: {sorted(discovered)}. "
        "Discovery walks Settings.model_fields, so a collapse here means path fields stopped being "
        "flat introspectable attributes -- and every classification assertion in this module would "
        "then pass vacuously while covering nothing"
    )


def test_every_path_field_is_a_member_an_escape_or_the_root() -> None:
    """An unclassified path field fails here, with both remedies named."""
    unclassified = unclassified_path_fields(Settings)
    assert not unclassified, (
        f"Path-typed Settings field(s) with no declared home: {unclassified}. Enroll each as a "
        "StorageCategory in the storage taxonomy if the application chooses this location and "
        "writes data there; otherwise declare it in EXTERNAL_PATH_SETTINGS_FIELDS with an "
        "ExternalPathRole (bundled resource, operator input, third-party cache, external "
        "executable, operator-directed output, maintainer-tooling output) and a reason saying "
        "which of the two questions it fails"
    )


def test_the_three_dispositions_are_pairwise_disjoint() -> None:
    """A field claimed twice means the taxonomy disagrees with itself."""
    members = set(STORAGE_FIELD_CATEGORIES)
    escapes = set(EXTERNAL_PATH_SETTINGS_FIELDS)
    anchor = {STORAGE_ROOT_SETTINGS_FIELD}

    for left_name, left, right_name, right in (
        ("taxonomy members", members, "declared escapes", escapes),
        ("taxonomy members", members, "the storage root", anchor),
        ("declared escapes", escapes, "the storage root", anchor),
    ):
        overlap = sorted(left & right)
        assert not overlap, (
            f"field(s) {overlap} are declared both as {left_name} and as {right_name}; a field "
            "either names a location the application chooses and writes, or it does not"
        )


def test_no_declaration_names_a_field_that_no_longer_exists() -> None:
    """A member or escape outliving its field is coverage nothing backs."""
    discovered = _discovered()

    stale_members = sorted(set(STORAGE_FIELD_CATEGORIES) - discovered)
    assert not stale_members, (
        f"storage taxonomy members bind settings field(s) {stale_members} that Settings no longer "
        "declares as Path-typed; strike or re-point the binding in the same change that retires "
        "the field"
    )

    stale_escapes = sorted(set(EXTERNAL_PATH_SETTINGS_FIELDS) - discovered)
    assert not stale_escapes, (
        f"EXTERNAL_PATH_SETTINGS_FIELDS declares escape(s) for {stale_escapes}, which Settings no "
        "longer declares as Path-typed; an escape for a field that does not exist reads as a "
        "considered decision and is not one"
    )

    assert STORAGE_ROOT_SETTINGS_FIELD in discovered, (
        f"{STORAGE_ROOT_SETTINGS_FIELD} is the anchor every root-scoped member resolves against "
        "and is no longer a Path-typed Settings field"
    )


def test_every_escape_states_its_role_and_its_reason() -> None:
    """An escape with an empty reason is an absence wearing a declaration's clothes."""
    for field_name, declaration in sorted(EXTERNAL_PATH_SETTINGS_FIELDS.items()):
        assert declaration.settings_field == field_name, (
            f"escape keyed {field_name!r} declares settings_field {declaration.settings_field!r}"
        )
        assert declaration.reason.strip(), f"escape {field_name!r} states no reason"


def test_every_member_binding_round_trips_to_its_declaration() -> None:
    """The reverse index and the declarations agree in both directions."""
    for field_name, category in sorted(STORAGE_FIELD_CATEGORIES.items()):
        assert STORAGE_TAXONOMY[category].settings_field == field_name


# --------------------------------------------------------------------- #
# Positive controls on the selector itself                              #
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "field_name",
    ["aeat_sede_expedientes_path", "aeat_status_notificaciones_path"],
)
def test_the_selector_ignores_str_fields_named_like_paths(field_name: str) -> None:
    """A ``_path``-named ``str`` is an AEAT URL segment, not a filesystem path.

    The converse control: the selector reads annotations, so these are not
    selected and no storage classification is demanded of a URL.
    """
    assert Settings.model_fields[field_name].annotation is str
    assert field_name not in _discovered()


def test_the_selector_ignores_a_non_path_field() -> None:
    """A closed-enum setting is not a location and is not selected."""
    assert "cadrumo_output_language" not in _discovered()


def test_the_selector_admits_an_optional_path() -> None:
    """``Path | None`` is a path field: unset today, a location when set."""
    assert annotation_mentions_path(Settings.model_fields["cadrumo_certificate_path"].annotation)
    assert not annotation_mentions_path(str)
    assert not annotation_mentions_path(int | None)


# --------------------------------------------------------------------- #
# Discrimination: the detector fires on the defect it exists for         #
# --------------------------------------------------------------------- #


class _ModelWithAnUnboundPathField(BaseModel):
    """A synthetic settings-shaped model carrying one unclassified path field."""

    cadrumo_token_dir: Path = Path("tokens")
    cadrumo_scratch_workspace: Path = Path("scratch")


class _ModelWithOnlyClassifiedPathFields(BaseModel):
    """The control: one bound member, one declared escape, and the anchor."""

    cadrumo_token_dir: Path = Path("tokens")
    cadrumo_certificate_path: Path | None = None
    cadrumo_local_storage_root: Path = Path("root")
    cadrumo_output_language: str | None = None


def test_the_detector_names_an_unbound_path_field() -> None:
    """Adding a path field with no declared home must fail, naming the field.

    This is the mutation the gate exists to catch, run on every pass rather
    than once by hand: a field that is neither enrolled nor escaped comes back
    named, so the failure tells the author which field and not merely that
    something is wrong.
    """
    assert unclassified_path_fields(_ModelWithAnUnboundPathField) == ("cadrumo_scratch_workspace",)


def test_the_detector_stays_silent_on_fully_classified_fields() -> None:
    """The positive control: a member, an escape, and the anchor all pass.

    Without this, a detector that returned every discovered field would satisfy
    the assertion above and still be useless -- it would red on every model,
    including the real one.
    """
    assert unclassified_path_fields(_ModelWithOnlyClassifiedPathFields) == ()
