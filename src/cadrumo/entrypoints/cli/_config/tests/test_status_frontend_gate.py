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

from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401
from .....tests.secure_sql import isolated_profile_storage_root
from ....cli._config import _status_frontend
from ....cli._config._status_frontend import present_status_tui

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


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
    ["auth.dni_nie", "auth.numero_soporte", "auth.fecha_validez"],
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
    """
    from .....application.user_profile import mask_profile_field
    from .....domain.user_profile import load_user_profile_schema

    field_def = load_user_profile_schema().field(path)
    label = field_def.description or path
    assert mask_profile_field(path=path, label=label, sensitivity=field_def.sensitivity), (
        f"credential input {path!r} rendered unmasked"
    )


def test_every_shipped_schema_field_masks_identically_on_both_surfaces() -> None:
    """No shipped field may mask on one surface and not the other.

    SUPPORTING as currently written. Both surfaces now call the same
    function, so this cannot fail while that holds -- it is a structural
    restatement, not an independent measurement, and it passes under the
    keyword-policy mutation. Its value is forward-looking: it fails the
    day someone re-forks the decision, which the mechanism test above
    catches more directly.

    It walks every field the real schema declares rather than a sample,
    so a field added later is covered without touching this test.
    """
    from .....application.user_profile import mask_profile_field
    from .....application.user_profile._overview import mask_profile_field as overview_decision
    from .....domain.user_profile import load_user_profile_schema

    schema = load_user_profile_schema()
    divergent: list[str] = []
    for section in schema.sections:
        for field in section.fields:
            path = f"{section.key}.{field.key}"
            label = field.description or path
            status_masked = mask_profile_field(path=path, label=label, sensitivity=field.sensitivity)
            if status_masked != overview_decision(path=path, label=field.description, sensitivity=field.sensitivity):
                divergent.append(path)
    assert not divergent, f"masking diverges between overview and status for: {divergent}"


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
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--irpf-income-categories",
            "actividad_economica",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--surnames",
            "Status",
            "--activity",
            "design",
        ],
    )
    assert result.exit_code == 0, result.output


@pytest.mark.usefixtures("_isolated_cli_backend")
def test_build_fact_rows_masks_by_the_real_schema() -> None:
    """Every fact row over a really created profile obeys the real schema's masking.

    The profile is created through the real non-interactive CLI walk, the
    record loaded through the real workflow repository, and the rows built
    by the production builder against the shipped schema — so the masking
    decision tested here is byte-for-byte the one the operator's screen
    gets.
    """
    from .....application.user_profile import profile_storage_session
    from .....application.workflow import read_profile_bucket, workflow_state_repository

    _create_profile()
    pointer = read_profile_bucket("operator")
    assert pointer is not None
    with profile_storage_session(pointer.bucket_id):
        record = workflow_state_repository().load().active_profile_record()
        rows = _status_frontend._build_fact_rows(record=record)

    assert rows, "a created profile must project at least one fact row"
    nif_row = next((row for row in rows if row.value == "12345678Z"), None)
    assert nif_row is not None, f"the NIF fact must surface; labels: {sorted(row.label for row in rows)}"
    assert nif_row.masked is False

    # No unmasked row may carry a password/key-like label — the keyword
    # branch of the real masking decision, checked over every real row.
    for row in rows:
        if row.masked:
            continue
        haystack = row.label.casefold()
        assert not any(keyword in haystack for keyword in ("passphrase", "password", "clave", "token", "secret")), (
            f"password/key-like row {row.label!r} rendered unmasked"
        )


# ── independent zone degradation (a damaged read never tracebacks) ──────────


@pytest.fixture
def _empty_storage(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def test_every_zone_degrades_on_an_empty_storage_root(_empty_storage: Path) -> None:
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
