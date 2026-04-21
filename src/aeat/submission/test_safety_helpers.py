"""Unit tests for the private live-submit safety helpers."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from ..config import PROJECT_ROOT
from ..filing import build_draft
from ..filing.testing import SyntheticProfile, default_schema_provider
from . import DraftStatus, FilingDraftLike, FilingFinding, Portal
from ._audit import append_live_submit_audit, build_live_submit_audit_record
from ._confirm import compute_draft_checksum, confirm_live_submission
from ._errors import AeatLiveConfirmationDeclinedError

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


@dataclass(frozen=True)
class _CliDraft(FilingDraftLike):
    draft_id: str
    modelo: str
    period: str
    profile_tax_id: str
    status: DraftStatus
    values: dict[str, str] = field(default_factory=dict)
    findings: tuple[FilingFinding, ...] = ()


def test_draft_checksum_is_stable_across_draft_shapes() -> None:
    draft = build_draft(
        modelo="130",
        period="2026Q1",
        profile=SyntheticProfile(
            tax_id="X1234567L",
            display_name="Checksum subject",
            applicable_modelos=("130",),
        ),
        inputs={"01": 12500, "02": 3500, "05": 400, "06": 0},
        schema_provider=default_schema_provider(),
    )
    cli_draft = _CliDraft(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        status=DraftStatus(draft.status.value),
        values={
            value.casilla_id: format(value.value, "f") if isinstance(value.value, Decimal) else str(value.value or "")
            for value in draft.values
        },
    )
    assert compute_draft_checksum(cast(FilingDraftLike, draft)) == compute_draft_checksum(cli_draft)


def test_confirm_live_submission_requires_exact_phrase() -> None:
    draft = _CliDraft(
        draft_id="draft-1",
        modelo="130",
        period="2026Q1",
        profile_tax_id="X1234567L",
        status=DraftStatus.READY_TO_SUBMIT,
        values={"07": "2150.00"},
    )
    portal = Portal(modelo="130", presentation_url="https://sede.example.test/130")
    checksum = compute_draft_checksum(draft)
    expected_phrase = f"SUBMIT 130 2026Q1 X1234567L 2150.00 {checksum}"

    with pytest.raises(AeatLiveConfirmationDeclinedError):
        confirm_live_submission(draft, portal=portal, input_fn=lambda _prompt: "nope")

    confirmation = confirm_live_submission(draft, portal=portal, input_fn=lambda _prompt: expected_phrase)
    assert confirmation.confirmation_phrase == expected_phrase
    assert confirmation.typed_phrase == expected_phrase


def test_append_live_submit_audit_writes_jsonl_and_marks_file_read_only(tmp_path: Path) -> None:
    record = build_live_submit_audit_record(
        modelo="130",
        period="2026Q1",
        taxpayer_nif="X1234567L",
        draft_checksum="abc123",
        submission_url="https://sede.example.test/130",
        response_status="SUBMITTED",
        justificante_csv="CSV-99",
        confirmation_phrase="SUBMIT 130 2026Q1 X1234567L 2150.00 abc123",
        env_state={"AEAT_LIVE_SUBMIT_ENABLED": "true"},
    )
    target = tmp_path / "live-submit-audit.log"

    append_live_submit_audit(record, target=target)
    append_live_submit_audit(record, target=target)

    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    payload = json.loads(lines[0])
    assert payload["modelo"] == "130"
    assert payload["period"] == "2026Q1"
    assert payload["justificante_csv"] == "CSV-99"
    assert payload["env_state"] == {"AEAT_LIVE_SUBMIT_ENABLED": "true"}
    assert target.stat().st_mode & stat.S_IWRITE == 0


def test_live_transport_failure_still_appends_audit_records(tmp_path: Path) -> None:
    draft = _CliDraft(
        draft_id="draft-1",
        modelo="130",
        period="2026Q1",
        profile_tax_id="X1234567L",
        status=DraftStatus.READY_TO_SUBMIT,
        values={"07": "2150.00"},
    )
    checksum = compute_draft_checksum(draft)
    phrase = f"SUBMIT 130 2026Q1 X1234567L 2150.00 {checksum}"
    submissions_dir = tmp_path / "submissions"
    traces_dir = tmp_path / "traces"
    audit_path = tmp_path / "live-submit-audit.log"
    script = textwrap.dedent(
        """
        import asyncio
        import sys
        from dataclasses import dataclass, field
        from datetime import date
        from pathlib import Path
        from typing import Any

        from aeat.config import Settings
        from aeat.submission import (
            AuthProviderDescription,
            AuthProviderKind,
            CasillaInputKind,
            CasillaRecord,
            DraftStatus,
            FilingDraftLike,
            FilingFinding,
            Portal,
            SubmissionEngine,
            Submitter,
        )

        @dataclass
        class Draft(FilingDraftLike):
            draft_id: str = "draft-1"
            modelo: str = "130"
            period: str = "2026Q1"
            profile_tax_id: str = "X1234567L"
            status: DraftStatus = DraftStatus.READY_TO_SUBMIT
            values: dict[str, str] = field(default_factory=lambda: {"07": "2150.00"})
            findings: tuple[FilingFinding, ...] = ()

        class Session:
            async def navigate(self, url: str) -> None: ...
            async def fill(self, selector: str, value: str) -> None: ...
            async def click(self, selector: str) -> None: ...
            async def screenshot(self, path: Path) -> None: ...
            async def trace_start(self, name: str) -> None: ...
            async def trace_stop(self, path: Path) -> None: ...
            async def snapshot_form_state(self, path: Path) -> None: ...

        class Deadlines:
            def is_window_open(self, modelo: str, period: str, today: date) -> bool:
                return True

        class AuthProvider:
            kind = AuthProviderKind.CERTIFICATE

            def describe(self) -> AuthProviderDescription:
                return AuthProviderDescription(
                    kind=self.kind,
                    label="Subprocess certificate",
                    configured=True,
                    available=True,
                    identity_nif="X1234567L",
                    subject="CN=Subprocess",
                    expires_on=date(2099, 12, 31),
                    health_summary="OK:26800",
                )

        class Portals:
            def portal_for(self, modelo: str) -> Portal:
                return Portal(modelo=modelo, presentation_url="https://sede.example.test/130")

        class Casillas:
            def casillas_for_modelo(self, modelo: str) -> tuple[CasillaRecord, ...]:
                return (
                    CasillaRecord(
                        id="07",
                        label={"en": "total", "es": "total", "hu": "osszeg"},
                        input_kind=CasillaInputKind.NUMBER,
                    ),
                )

            def get(self, casilla_id: str) -> CasillaRecord:
                return self.casillas_for_modelo("130")[0]

        class Drafts:
            def load(self, draft_path: Path) -> Any:
                raise NotImplementedError

        class FailingSubmitter(Submitter):
            @property
            def modelo(self) -> str:
                return "130"

            async def dry_run(self, **kwargs: Any):
                raise AssertionError("dry_run should not be called")

            async def submit(self, **kwargs: Any):
                raise RuntimeError("transport blew up after dispatch")

        settings = Settings(
            aeat_submissions_dir=Path(sys.argv[1]),
            aeat_submission_browser_trace_dir=Path(sys.argv[2]),
            aeat_live_submit_enabled=True,
        )
        engine = SubmissionEngine(
            browser_session_factory=Session,
            auth_provider=AuthProvider(),
            portal_catalogue=Portals(),
            draft_loader=Drafts(),
            deadline_checker=Deadlines(),
            casilla_catalogue=Casillas(),
            justificante_parser=Drafts(),
            submitters={"130": FailingSubmitter()},
            settings=settings,
            # Explicit opt-in — this safety-helper test exercises the
            # post-bypass live path. See 2026-04-18-live-submit-cli-excision-adr.
            live_transport_supported=True,
            live_submit_audit_log_path=Path(sys.argv[3]),
        )
        try:
            asyncio.run(engine.submit_draft(Draft(), dry_run=False))
        except RuntimeError:
            raise SystemExit(0)
        raise SystemExit(1)
        """
    )
    env = os.environ.copy()
    env.pop("PYTEST_CURRENT_TEST", None)
    result = subprocess.run(  # noqa: S603 - fixed interpreter invocation for safety-path coverage
        [sys.executable, "-c", script, str(submissions_dir), str(traces_dir), str(audit_path)],
        input=f"{phrase}\n",
        text=True,
        capture_output=True,
        env=env,
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["response_status"] == "DISPATCH_REQUESTED"
    assert json.loads(lines[1])["response_status"] == "ERROR:RuntimeError"
