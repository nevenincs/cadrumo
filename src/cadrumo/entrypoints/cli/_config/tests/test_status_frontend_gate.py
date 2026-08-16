"""The status-page presenter must never pre-empt the machine contract.

``present_status_tui`` is the seam that decides whether ``aeat config
profile status`` renders the read-only full-screen surface or falls
through to the unchanged envelope path. These tests pin that gate with
real behaviour only: a ``--format json`` request and this test process's
genuinely non-full-screen host MUST return ``False`` so the JSON / text
envelope callers reach the identical machine output the conformance
suites lock. The full-screen presentation itself is never launched here
(it would take over the controlling terminal); the gate's refusal is what
guards the contract. The masking and degradation contracts run against
the real profile schema, a real created profile, and a real empty
storage root — no patched seams, no stand-in schema objects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import typer
import typer.core

from .....tests.profile_capsule import open_test_profile_session
from .....tests.profile_storage_root_fixture import profile_storage_root_fixture

__all__ = ["profile_storage_root_fixture"]

from .....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401
from .....tests.user_profile import register_cli_profile
from ....cli._config import _status_frontend
from ....cli._config._status_frontend import present_status_tui

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

if TYPE_CHECKING:
    from pathlib import Path

    from .....adapters.inbound.tui import StatusFactRow
    from .....domain.user_profile import UserProfileRecord


def _ctx_with_format(format_name: str) -> typer.Context:
    ctx = typer.Context(typer.core.TyperCommand("status"))
    ctx.ensure_object(dict)["format"] = format_name
    return ctx


def test_json_format_falls_through_to_the_envelope_path() -> None:
    # A JSON caller must never be diverted into the interactive surface,
    # regardless of the host's console capability.
    assert present_status_tui(_ctx_with_format("json")) is False


def test_non_full_screen_host_falls_through() -> None:
    """The real captured test host is not full-screen capable, so text falls through.

    Anti-vacuity first: this process runs under pytest's captured IO, so
    the live capability probe genuinely reports a non-full-screen host.
    The gate must then fall through for a text caller on this real host —
    the same decision a piped / CI invocation gets in production.
    """
    from .....application.flows import detect_frontend_capability
    from .....core.flows import FrontendCapability

    assert detect_frontend_capability() is not FrontendCapability.FULL_SCREEN
    assert present_status_tui(_ctx_with_format("text")) is False


def test_presenter_module_exposes_a_read_only_builder() -> None:
    # The builder assembles a view-model and nothing else; it is the only
    # public surface besides the gate, so the presenter has no write verb.
    assert set(_status_frontend.__all__) == {"build_status_page_data", "present_status_tui"}


# ── masking decision (which facts get masked) ───────────────────────────────


def test_secret_classed_field_is_masked() -> None:
    from .....application.user_profile import mask_profile_field
    from .....core.classification import SensitivityClass

    assert mask_profile_field(
        path="identity.tax_id",
        label="NIF",
        sensitivity=SensitivityClass.SECRET,
    )


@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("auth.certificate_passphrase", "Certificate passphrase"),
        ("secrets.api_token", "Token"),
        ("custody.clave", "Clave de recuperación"),
    ],
)
def test_password_or_key_like_field_is_masked(path: str, label: str) -> None:
    from .....application.user_profile import mask_profile_field

    assert mask_profile_field(path=path, label=label, sensitivity=None)


def test_plain_identity_field_is_not_masked() -> None:
    from .....application.user_profile import mask_profile_field
    from .....core.classification import SensitivityClass

    assert not mask_profile_field(
        path="identity.tax_id",
        label="NIF",
        sensitivity=SensitivityClass.IDENTITY,
    )


# ── one masking authority: status must not diverge from the overview ────────


def test_status_surface_holds_no_private_masking_policy() -> None:
    """The status frontend must own no masking policy of its own.

    DISCRIMINATING, on the mechanism rather than the output. It
    previously carried a private ``_MASK_KEYWORDS`` set and an
    ``_is_masked`` twin of the overview's decision; the two drifted, and
    the drift ran in the unsafe direction -- the status set omitted
    ``credential``, so this surface printed the Cl@ve credential inputs
    in clear while the overview masked them.

    Asserting on the absence of a second policy, rather than on masked
    output, is deliberate: a re-introduced private policy that happened
    to agree with the canonical one today would satisfy any output-shaped
    assertion while restoring the drift hazard tomorrow.
    """
    assert not hasattr(_status_frontend, "_is_masked")
    assert not hasattr(_status_frontend, "_MASK_KEYWORDS")


@pytest.mark.parametrize(
    "path",
    ["auth.numero_soporte", "auth.fecha_validez"],
)
def test_clave_credential_inputs_mask_on_the_real_shipped_schema(path: str) -> None:
    """The Cl@ve credential inputs mask under the schema really shipped.

    DISCRIMINATING. These are encrypted-profile credential inputs whose
    shipped descriptions call them exactly that. Label and sensitivity
    are read from the real schema, not a stand-in, so this fails if
    either the masking policy or the shipped wording stops covering them.

    It asserts the masking DECISION for each named field, not the absence
    of a secret from rendered output: a field simply missing from a
    fixture would satisfy an output-shaped assertion while remaining
    unmasked in production.

    The two named here are the CONTRASTE -- what proves possession of the
    physical document. ``auth.dni_nie`` was named alongside them and is
    not one: it merely names the holder, carries the same identifier
    ``identity.tax_id`` renders in the clear one section above, and
    confers no capability without a contraste and a PIN this profile
    never stores. It is deliberately excluded rather than accommodated by
    a looser assertion: the list is an explicit statement of which fields
    MUST mask, so dropping one has to be a visible decision. Deriving it
    from the schema instead would make the gate read its expectation off
    the thing it checks, and it could then never fail.
    """
    from .....application.user_profile import mask_profile_field
    from .....domain.user_profile import load_user_profile_schema

    field_def = load_user_profile_schema().field(path)
    label = field_def.description or path
    assert mask_profile_field(path=path, label=label, sensitivity=field_def.sensitivity), (
        f"credential input {path!r} rendered unmasked"
    )


def test_every_shipped_schema_field_masks_the_same_under_either_callers_label() -> None:
    """The status and overview call sites build ``label`` differently; masking must agree anyway.

    There is one ``mask_profile_field`` -- the status surface
    (``_status_frontend.py``) and the overview surface (``_overview.py``)
    both call it, so there is no second decision to fork. That singularity
    is enforced, not merely asserted here: ``test_mask_profile_field_singularity.py``
    fails the build if a second masking-verdict function appears anywhere
    in the tree, under any name. This test's own job is narrower and
    different -- given the one authority, do the two call sites' differing
    label construction agree on its answer. What differs between them is
    the ``label`` argument each site constructs:
    ``_status_frontend.py`` falls back to the path when the schema
    description is empty, ``_overview.py`` passes the description as-is
    (possibly ``None``). ``sensitivity`` only defers to the keyword net on
    ``label`` when the schema declares no sensitivity for the field, so
    that fallback difference could in principle flip an unclassified
    field's masking between the two sites.

    It walks every field the real schema declares rather than a sample,
    so a field added later is covered without touching this test.
    """
    from .....application.user_profile import mask_profile_field
    from .....domain.user_profile import load_user_profile_schema

    schema = load_user_profile_schema()
    divergent: list[str] = []
    for section in schema.sections:
        for field in section.fields:
            path = f"{section.key}.{field.key}"
            status_label = field.description or path
            overview_label = field.description
            status_masked = mask_profile_field(path=path, label=status_label, sensitivity=field.sensitivity)
            overview_masked = mask_profile_field(path=path, label=overview_label, sensitivity=field.sensitivity)
            if status_masked != overview_masked:
                divergent.append(path)
    assert not divergent, f"masking diverges between the status and overview label construction for: {divergent}"


def test_unknown_field_falls_back_to_the_keyword_policy() -> None:
    """A path the schema does not know still masks on its name alone.

    DISCRIMINATING on the ``credential`` keyword. The status builder
    passes ``sensitivity=None`` for an unrecognised path, so the keyword
    branch is the only thing standing between a stray credential-shaped
    fact and the screen. The negative case (``unknown.city``) is
    supporting: it pins that the policy is not simply mask-everything.
    """
    from .....application.user_profile import mask_profile_field

    assert mask_profile_field(path="unknown.api_credential", label="unknown.api_credential", sensitivity=None)
    assert mask_profile_field(path="unknown.private_key", label="unknown.private_key", sensitivity=None)
    assert not mask_profile_field(path="unknown.city", label="unknown.city", sensitivity=None)


@pytest.mark.parametrize(
    "fragment",
    ["api_key", "apikey", "private_key", "private key"],
)
def test_bare_key_keyword_still_subsumes_the_compound_key_names(fragment: str) -> None:
    """Trimming bare ``key`` from the policy must not unmask compound keys.

    DISCRIMINATING on the ``key`` keyword. The canonical set lists
    ``key`` and deliberately omits ``api_key`` / ``apikey`` /
    ``private_key`` / ``private key`` because ``key`` already subsumes
    them. That subsumption is load-bearing -- the pre-fix status set
    listed the compounds explicitly, so consolidating onto bare ``key``
    silently relies on it -- and is pinned here rather than assumed.
    """
    from .....application.user_profile import mask_profile_field

    assert mask_profile_field(path=f"vault.{fragment}", label=fragment, sensitivity=None)


# ── fact rows over a real record and the real schema ────────────────────────


def _create_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.regime": "GENERAL",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Status",
            "activities.description": "design",
        },
    )


_AUTH_PROVIDER_PATH = "auth.provider"
_AUTH_SOPORTE_PATH = "auth.numero_soporte"
_AUTH_PROVIDER_VALUE = "clave_movil"
_AUTH_SOPORTE_VALUE = "ABC123456"


def _seed_auth_facts() -> None:
    """Give the credential-label net an ``auth.*`` subject to read.

    ``config profile create`` collects no ``auth.*`` answer, so a fixture
    built from that walk alone projects identity, contact, and activity
    rows and NOT ONE row from the section whose labels name credentials.
    The credential-shaped-label assertion below then ran over a row set
    that could not contain the thing it looks for -- it passed for want
    of a subject, which is indistinguishable from passing because the
    labels are clean.

    The two facts are chosen as a pair to cover both arms of that
    assertion: ``auth.provider`` is declared ``identity``, so its row
    renders UNMASKED and is read by the net, while ``auth.numero_soporte``
    is declared ``secret``, so its row is masked and deliberately skipped.

    They are written through the record repository's compare-and-swap fact
    door -- the same one the manager's authentication action commits through
    -- against the real encrypted record, so the rows projected from them are
    the rows an operator's screen is built from.
    """
    from .....domain.user_profile import UserProfileFact
    from .....tests.profile_capsule import set_active_test_profile_facts

    set_active_test_profile_facts(
        (
            UserProfileFact(path=_AUTH_PROVIDER_PATH, value=_AUTH_PROVIDER_VALUE),
            UserProfileFact(path=_AUTH_SOPORTE_PATH, value=_AUTH_SOPORTE_VALUE),
        )
    )


def _fact_rows_over_a_real_profile() -> tuple[tuple[StatusFactRow, ...], UserProfileRecord]:
    """Build the status fact rows for a really created, auth-bearing profile.

    The record is returned alongside its rows so a caller can project the
    SAME record through another surface and compare the two readings.
    """
    from .....application.workflow import read_profile_bucket, workflow_state_repository

    _create_profile()
    pointer = read_profile_bucket("operator")
    assert pointer is not None
    with open_test_profile_session(pointer.bucket_id):
        _seed_auth_facts()
        record = workflow_state_repository().load().active_profile_record()
        assert record is not None
        return _status_frontend._build_fact_rows(record=record), record


@pytest.mark.usefixtures("_isolated_cli_backend")
def test_build_fact_rows_masks_by_the_real_schema() -> None:
    """Every fact row over a really created profile obeys the real schema's masking.

    The profile is created through the real non-interactive CLI walk, the
    auth section written through the real plural fact door, the record
    loaded through the real workflow repository, and the rows built by the
    production builder against the shipped schema — so the masking
    decision tested here is byte-for-byte the one the operator's screen
    gets.
    """
    from .....application.user_profile import mask_profile_field

    rows, _record = _fact_rows_over_a_real_profile()

    assert rows, "a created profile must project at least one fact row"
    nif_row = next((row for row in rows if row.value == "12345678Z"), None)
    assert nif_row is not None, f"the NIF fact must surface; labels: {sorted(row.label for row in rows)}"
    assert nif_row.masked is False

    # ANTI-VACUITY, and the reason the fixture writes the auth section at
    # all: the loop below is a net over UNMASKED rows, so it measures
    # nothing unless an unmasked auth row is really in the set. Both arms
    # are named, so a fixture that silently stops projecting either one
    # fails here rather than quietly emptying the net.
    provider_row = next((row for row in rows if row.value == _AUTH_PROVIDER_VALUE), None)
    assert provider_row is not None, (
        f"auth.provider must project an unmasked row; labels: {sorted(row.label for row in rows)}"
    )
    assert provider_row.masked is False, "auth.provider is declared identity and must render in the clear"
    soporte_row = next((row for row in rows if row.value == _AUTH_SOPORTE_VALUE), None)
    assert soporte_row is not None, "auth.numero_soporte must project a row"
    assert soporte_row.masked is True, "auth.numero_soporte is declared secret and must render masked"

    # No unmasked row may carry a credential-shaped label. The question is
    # put to the canonical policy rather than restated here: this carried a
    # hand-listed copy of it that had drifted to five of the nine keywords,
    # missing "credential" and "key", so a net named for the policy quietly
    # covered less than the policy did. Passing sensitivity=None is what
    # selects the keyword arm, which is exactly the reading wanted of a
    # label -- the row's own masking has already been decided above.
    for row in rows:
        if row.masked:
            continue
        assert not mask_profile_field(path=row.label, label=row.label, sensitivity=None), (
            f"credential-shaped row {row.label!r} rendered unmasked"
        )


# ── row labels: one name per field, except where an index must show ─────────


@pytest.mark.usefixtures("_isolated_cli_backend")
def test_an_unindexed_row_carries_the_label_the_manager_carries() -> None:
    """One field must not be named two different things on two surfaces.

    DISCRIMINATING, and deliberately measured against the OTHER surface
    rather than against the label function this one now calls: asserting
    that ``_build_fact_rows`` returns what ``profile_field_label`` returns
    would restate the implementation. The manager builds its own rows
    through ``build_profile_overview``, so agreement between the two is an
    independent reading of the property that matters.

    The second assertion is what makes this fail on the old code rather
    than merely on a renamed key: the status page used to render the
    schema's ``description`` verbatim, which for ``auth.provider`` is four
    sentences of authority prose. A row that still equals the description
    is a row that never reached the catalogue.
    """
    from .....application.user_profile import build_profile_overview
    from .....domain.user_profile import load_user_profile_schema

    rows, record = _fact_rows_over_a_real_profile()

    status_label = next(row.label for row in rows if row.value == _AUTH_PROVIDER_VALUE)
    overview = build_profile_overview(record)
    manager_label = next(
        field.label for section in overview.sections for field in section.fields if field.path == _AUTH_PROVIDER_PATH
    )
    assert status_label == manager_label, (
        f"status names auth.provider {status_label!r} while the manager names it {manager_label!r}"
    )
    assert status_label != load_user_profile_schema().field(_AUTH_PROVIDER_PATH).description, (
        "the status row still renders the schema description as its label"
    )


def test_an_indexed_row_uses_the_schema_label_and_a_visible_row_marker() -> None:
    """Two socios stay distinguishable without exposing their stored paths.

    DISCRIMINATING as an inequality: the schema declares
    ``attribution_entity_socios.nif`` once, so naming an indexed row after
    its declaration -- by label or by description, it makes no difference
    -- collapses every socio to the same row name on a surface with no
    other column to tell them apart. The label is therefore the raw path
    and the equality assertion below pins which path.

    The record is built directly rather than through the CLI walk because
    ``config profile create`` collects no socio: the shape under test is
    an indexed fact, and this is a real ``UserProfileRecord`` read by the
    production builder against the real shipped schema.
    """
    from .....domain.user_profile import (
        UserProfileFact,
        load_user_profile_schema,
        profile_field_label,
    )
    from .....domain.user_profile import UserProfileRecord as _Record

    first_path = "attribution_entity_socios.0.nif"
    second_path = "attribution_entity_socios.1.nif"
    record = _Record(
        profile_id="00000000-0000-4000-8000-0000000000a1",
        display_name="Socios status row",
        facts=(
            UserProfileFact(path=first_path, value="B12345678"),
            UserProfileFact(path=second_path, value="B87654321"),
        ),
    )

    rows = _status_frontend._build_fact_rows(record=record)
    labels = {row.value: row.label for row in rows}
    assert labels.keys() >= {"B12345678", "B87654321"}, f"both socios must project a row; got {labels}"
    assert labels["B12345678"] != labels["B87654321"], "two socios rendered under one indistinguishable row name"
    declared = load_user_profile_schema().field("attribution_entity_socios.nif")
    field_label = profile_field_label("attribution_entity_socios", declared)
    assert field_label in labels["B12345678"]
    assert field_label in labels["B87654321"]
    assert first_path not in labels.values()
    assert second_path not in labels.values()


# ── independent zone degradation (a damaged read never tracebacks) ──────────


def test_every_zone_degrades_on_an_empty_storage_root(profile_storage_root: Path) -> None:
    """With no profile, no auth state, and no recovery enrolment, every zone degrades.

    This is the real damaged-host contract: the reads genuinely find
    nothing (or refuse), and the builder still returns a fully typed page
    instead of raising — the crash-safety property the status surface
    promises.
    """
    from .....adapters.inbound.tui import StatusPageData

    data = _status_frontend.build_status_page_data()
    assert isinstance(data, StatusPageData)
    assert data.recovery.enrolled is False
    assert data.recovery.fingerprint is None
    assert _status_frontend._build_profile_rows(active_uuid="no-such-uuid") == ()
