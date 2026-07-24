"""The status-page presenter must never pre-empt the machine contract.

``present_status_tui`` is the seam that decides whether ``aeat config
profile status`` renders the read-only full-screen surface or falls
through to the unchanged envelope path. These tests pin that gate: a
``--format json`` request and any non-full-screen host MUST return
``False`` so the JSON / text envelope callers reach the identical machine
output the conformance suites lock. The full-screen presentation itself is
never launched here (it would take over the controlling terminal); the
gate's refusal is what guards the contract.
"""

from __future__ import annotations

import click
import pytest
import typer

from ....cli._config import _status_frontend
from ....cli._config._status_frontend import present_status_tui

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _ctx_with_format(format_name: str) -> typer.Context:
    ctx = typer.Context(click.Command("status"))
    ctx.ensure_object(dict)["format"] = format_name
    return ctx


def test_json_format_falls_through_to_the_envelope_path() -> None:
    # A JSON caller must never be diverted into the interactive surface,
    # regardless of the host's console capability.
    assert present_status_tui(_ctx_with_format("json")) is False


def test_non_full_screen_host_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.core.flows import FrontendCapability

    monkeypatch.setattr(
        "cadrumo.application.flows.detect_frontend_capability",
        lambda: FrontendCapability.NON_INTERACTIVE,
    )
    assert present_status_tui(_ctx_with_format("text")) is False


def test_line_capable_host_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.core.flows import FrontendCapability

    monkeypatch.setattr(
        "cadrumo.application.flows.detect_frontend_capability",
        lambda: FrontendCapability.LINE,
    )
    assert present_status_tui(_ctx_with_format("text")) is False


def test_presenter_module_exposes_a_read_only_builder() -> None:
    # The builder assembles a view-model and nothing else; it is the only
    # public surface besides the gate, so the presenter has no write verb.
    assert set(_status_frontend.__all__) == {"build_status_page_data", "present_status_tui"}


# ── masking decision (which facts get masked) ───────────────────────────────


def test_secret_classed_field_is_masked() -> None:
    from cadrumo.core.classification import SensitivityClass

    assert _status_frontend._is_masked(
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
    assert _status_frontend._is_masked(path=path, label=label, sensitivity=None)


def test_plain_identity_field_is_not_masked() -> None:
    from cadrumo.core.classification import SensitivityClass

    assert not _status_frontend._is_masked(
        path="identity.tax_id",
        label="NIF",
        sensitivity=SensitivityClass.IDENTITY,
    )


class _StubField:
    def __init__(self, description: str, sensitivity: object) -> None:
        self.description = description
        self.sensitivity = sensitivity


class _StubSchema:
    def __init__(self, fields: dict[str, _StubField]) -> None:
        self._fields = fields

    def field(self, path: str) -> _StubField:
        from cadrumo.domain.user_profile import UserProfileError

        try:
            return self._fields[path]
        except KeyError as exc:
            raise UserProfileError(f"unknown field {path!r}") from exc


def test_build_fact_rows_masks_secret_classed_and_keyword_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.core.classification import SensitivityClass

    values = {
        "identity.tax_id": "12345678Z",
        "custody.stored_passphrase": "SECRET-PASSPHRASE",
        "auth.material": "SECRET-MATERIAL",
    }
    schema = _StubSchema(
        {
            "identity.tax_id": _StubField("NIF", SensitivityClass.IDENTITY),
            # keyword-tripped via the schema description, not the sensitivity.
            "custody.stored_passphrase": _StubField("Passphrase", SensitivityClass.IDENTITY),
            "auth.material": _StubField("Auth material", SensitivityClass.SECRET),
        },
    )
    monkeypatch.setattr("cadrumo.application.user_profile.record_to_path_values", lambda _record: values)
    monkeypatch.setattr("cadrumo.domain.user_profile.load_user_profile_schema", lambda: schema)

    rows = _status_frontend._build_fact_rows(record=object())
    by_label = {row.label: row for row in rows}
    assert by_label["NIF"].masked is False
    assert by_label["Passphrase"].masked is True
    assert by_label["Auth material"].masked is True


# ── independent zone degradation (a damaged read never tracebacks) ──────────


def _raise_cadrumo(*_args: object, **_kwargs: object) -> object:
    from cadrumo.core.errors import CadrumoError

    raise CadrumoError("simulated damaged read")


def test_recovery_zone_degrades_when_recovery_status_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cadrumo.application.user_profile.inspect_recovery_status", _raise_cadrumo)
    view = _status_frontend._build_recovery_view()
    assert view.enrolled is False
    assert view.fingerprint is None


def test_profiles_zone_degrades_when_bucket_scan_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cadrumo.application.workflow.list_profile_buckets", _raise_cadrumo)
    assert _status_frontend._build_profile_rows(active_uuid="abc") == ()


def test_workflow_state_degrades_when_load_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Repo:
        def load(self) -> object:
            return _raise_cadrumo()

    monkeypatch.setattr("cadrumo.application.workflow.workflow_state_repository", lambda: _Repo())
    assert _status_frontend._load_workflow_state() is None


def test_active_record_read_degrades_when_bucket_locked() -> None:
    class _LockedState:
        def active_profile_record(self) -> object:
            return _raise_cadrumo()

    assert _status_frontend._read_active_record(_LockedState()) is None


def test_auth_view_is_empty_when_state_is_unavailable() -> None:
    view = _status_frontend._build_auth_view(None)
    assert view.provider is None
    assert view.login_ready is False
