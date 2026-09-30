"""The sequence engine refuses to execute against a registry authority that is not current."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.config import override_settings
from dev.registry.pipeline.authority_publication import (
    AuthorityDatabaseCurrency,
    AuthorityDatabaseCurrencyStatus,
)

from ..authority_currency import (
    PUBLISH_AUTHORITY_REMEDY,
    authority_currency_refusal,
    require_current_authority,
    unavailable_authority_refusal,
)
from ..checks import check_page_coherence_in_subprocess, check_sequences_in_subprocess
from ..cli import main
from ..errors import SequenceEngineError

_DESCRIPTOR = Path("authority-root") / "authority.current.json"
_PAGE = "tutorials/authority-currency-case"
_SEQUENCE_ID = "authority-currency-case"


def _currency(status: AuthorityDatabaseCurrencyStatus, detail: str) -> AuthorityDatabaseCurrency:
    return AuthorityDatabaseCurrency(
        descriptor_path=_DESCRIPTOR,
        status=status,
        candidate_identity_digest="0" * 64,
        recorded_identity_digest=None,
        detail=detail,
    )


@pytest.mark.unit
@pytest.mark.hex_core
@pytest.mark.docs
class TestRefusalDecision:
    def test_current_authority_is_not_refused(self) -> None:
        assert authority_currency_refusal(_currency(AuthorityDatabaseCurrencyStatus.CURRENT, "matches")) is None

    @pytest.mark.parametrize(
        "status",
        [
            AuthorityDatabaseCurrencyStatus.STALE,
            AuthorityDatabaseCurrencyStatus.UNREADABLE,
            AuthorityDatabaseCurrencyStatus.UNSUPPORTED_FORMAT,
        ],
    )
    def test_every_non_current_status_refuses_with_the_remedy(self, status: AuthorityDatabaseCurrencyStatus) -> None:
        refusal = authority_currency_refusal(_currency(status, "why it is not current"))
        assert refusal is not None
        assert f"is {status.value}" in refusal
        assert "why it is not current" in refusal
        assert str(_DESCRIPTOR) in refusal
        assert refusal.endswith(PUBLISH_AUTHORITY_REMEDY)

    def test_stale_refusal_carries_the_currency_detail(self) -> None:
        detail = "the legal sources changed since the indexed generation was published"
        refusal = authority_currency_refusal(_currency(AuthorityDatabaseCurrencyStatus.STALE, detail))
        assert refusal is not None
        assert detail in refusal

    def test_unavailable_descriptor_refusal_names_the_remedy(self) -> None:
        refusal = unavailable_authority_refusal("no descriptor at the configured root")
        assert "no published registry authority resolves" in refusal
        assert "no descriptor at the configured root" in refusal
        assert refusal.endswith(PUBLISH_AUTHORITY_REMEDY)

    def test_remedy_is_the_conditional_republish(self) -> None:
        assert (
            PUBLISH_AUTHORITY_REMEDY == "uv run --no-sync python -m dev.registry.pipeline publish-authority --if-stale"
        )


@pytest.mark.integration
@pytest.mark.hex_core
@pytest.mark.docs
def test_the_published_authority_of_this_checkout_is_current() -> None:
    """The real descriptor the runner reads passes, so the gate is not red by construction."""
    require_current_authority()


def _docs_tree(root: Path) -> Path:
    page = root / f"{_PAGE}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "# Authority currency case\n\n"
        "Create a profile first with `aeat config profile create`.\n\n"
        f"```{{cli-sequence}} {_SEQUENCE_ID}\n"
        ":verify: Verify the profile listing succeeds.\n"
        "```\n",
        encoding="utf-8",
    )
    contract = root / "_sequences" / "contracts" / Path(_PAGE) / f"{_SEQUENCE_ID}.seq"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text("@result aeat --format json config profile list\n@expect exit_code == 0\n", encoding="utf-8")
    return root


def _unreadable_authority_root(root: Path) -> Path:
    root.mkdir()
    (root / "authority.current.json").write_text("not a descriptor", encoding="utf-8")
    return root


@pytest.mark.integration
@pytest.mark.hex_core
@pytest.mark.docs
class TestCliRefusal:
    def test_refresh_refuses_without_writing_a_golden(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        docs_root = _docs_tree(tmp_path / "docs")
        goldens_root = tmp_path / "goldens"
        with override_settings(cadrumo_authority_root=tmp_path / "unpublished"):
            exit_code = main(["refresh", "--docs-root", str(docs_root), "--goldens-root", str(goldens_root)])
        err = capsys.readouterr().err
        assert exit_code == 1
        assert "no published registry authority resolves" in err
        assert PUBLISH_AUTHORITY_REMEDY in err
        assert not goldens_root.exists()

    def test_check_refuses_an_unreadable_authority(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        docs_root = _docs_tree(tmp_path / "docs")
        authority_root = _unreadable_authority_root(tmp_path / "authority")
        with override_settings(cadrumo_authority_root=authority_root):
            exit_code = main(["check", "--docs-root", str(docs_root), "--goldens-root", str(tmp_path / "goldens")])
        err = capsys.readouterr().err
        assert exit_code == 1
        assert "is unreadable" in err
        assert PUBLISH_AUTHORITY_REMEDY in err
        assert "divergence" not in err

    def test_coherence_refuses_an_unreadable_authority(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        docs_root = _docs_tree(tmp_path / "docs")
        authority_root = _unreadable_authority_root(tmp_path / "authority")
        with override_settings(cadrumo_authority_root=authority_root):
            exit_code = main(["check", "--coherence", "--docs-root", str(docs_root)])
        err = capsys.readouterr().err
        assert exit_code == 1
        assert "is unreadable" in err
        assert PUBLISH_AUTHORITY_REMEDY in err

    def test_subprocess_checks_refuse_in_the_parent(self, tmp_path: Path) -> None:
        """The build hook's child-process path refuses once instead of reporting a divergence per child."""
        docs_root = _docs_tree(tmp_path / "docs")
        with override_settings(cadrumo_authority_root=tmp_path / "unpublished"):
            with pytest.raises(SequenceEngineError, match="publish-authority --if-stale"):
                check_sequences_in_subprocess(docs_root=docs_root, goldens_root=tmp_path / "goldens", jobs=4)
            with pytest.raises(SequenceEngineError, match="publish-authority --if-stale"):
                check_page_coherence_in_subprocess(docs_root=docs_root, page=_PAGE)
