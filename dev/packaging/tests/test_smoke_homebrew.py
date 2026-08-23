"""Direct tests for the real Homebrew source-install harness."""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path

import pytest

from ..smoke_homebrew import (
    CLEANUP_STATE_NAME,
    _assert_oracle_evidence,
    _parser,
    _require_valid_tap_name,
    cleanup_state_document,
    localize_formula,
    main,
    run_deferred_cleanup,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _write_stub_brew(bin_dir: Path, state_dir: Path) -> Path:
    """Write a real executable ``brew`` stub backed by a mutable formula file.

    ``list --formula`` prints ``formulae.txt``; ``uninstall`` removes the
    named formula from it; ``tap`` prints ``taps.txt``; ``untap`` removes the
    tap (or exits 1 when ``fail-untap`` marker exists). Every invocation is a
    real subprocess appending its argv to ``calls.log`` — nothing in the
    module under test is mocked.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "brew_stub.py"
    script.write_text(
        f"""
import json, sys
from pathlib import Path

state = Path({str(state_dir)!r})
formulae_file = state / "formulae.txt"
taps_file = state / "taps.txt"
args = sys.argv[1:]
with (state / "calls.log").open("a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")


def read_lines(path):
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line] if path.is_file() else []


if args[:2] == ["list", "--formula"]:
    sys.stdout.write("\\n".join(read_lines(formulae_file)) + "\\n")
elif args[0] == "uninstall":
    name = args[-1]
    formulae_file.write_text(
        "\\n".join(line for line in read_lines(formulae_file) if line != name) + "\\n",
        encoding="utf-8",
    )
elif args == ["tap"]:
    sys.stdout.write("\\n".join(read_lines(taps_file)) + "\\n")
elif args[0] == "untap":
    if (state / "fail-untap").is_file():
        sys.stderr.write("untap refused by stub")
        raise SystemExit(1)
    name = args[1]
    taps_file.write_text(
        "\\n".join(line for line in read_lines(taps_file) if line != name) + "\\n",
        encoding="utf-8",
    )
else:
    sys.stderr.write("unexpected brew invocation: " + repr(args))
    raise SystemExit(2)
""",
        encoding="utf-8",
    )
    if sys.platform.startswith("win"):
        launcher = bin_dir / "brew.bat"
        launcher.write_text(
            f'@echo off\r\n"{sys.executable}" "{script}" %*\r\nexit /b %errorlevel%\r\n',
            encoding="utf-8",
        )
    else:
        launcher = bin_dir / "brew"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return launcher


def _seed_cleanup_state(tmp_path: Path, *, installed: bool = True) -> tuple[Path, Path]:
    """Materialise a retain-install aftermath: stub brew + recorded state."""
    state_dir = tmp_path / "brew-state"
    brew = _write_stub_brew(tmp_path / "bin", state_dir)
    (state_dir / "formulae.txt").write_text("git\ncadrumo\nlibyaml\n", encoding="utf-8")
    (state_dir / "taps.txt").write_text("homebrew/core\ncadrumo-smoke/linux-x86_64\n", encoding="utf-8")
    run_root = tmp_path / "evidence" / "run-20260721T000000000Z"
    run_root.mkdir(parents=True)
    installed_prefix = tmp_path / "cellar" / "cadrumo" / "0.2.1"
    if installed:
        installed_prefix.mkdir(parents=True)
    state_path = run_root / CLEANUP_STATE_NAME
    state_path.write_text(
        json.dumps(
            cleanup_state_document(
                brew=brew,
                tap_name="cadrumo-smoke/linux-x86_64",
                tap_registered=True,
                installed_prefix=installed_prefix if installed else None,
                preexisting_formulae={"git"},
                preexisting_taps={"homebrew/core"},
            ),
        ),
        encoding="utf-8",
    )
    return state_path, state_dir


def test_deferred_cleanup_uninstalls_everything_the_smoke_added(tmp_path: Path) -> None:
    """The recorded state drives uninstall of the formula, new deps, and tap."""
    state_path, state_dir = _seed_cleanup_state(tmp_path)
    exit_code = main(["--cleanup-state", str(state_path)])
    calls = [json.loads(line) for line in (state_dir / "calls.log").read_text(encoding="utf-8").splitlines()]
    assert ["uninstall", "--force", "cadrumo"] in calls
    assert ["uninstall", "--force", "--ignore-dependencies", "libyaml"] in calls
    assert ["untap", "cadrumo-smoke/linux-x86_64"] in calls
    formulae = (state_dir / "formulae.txt").read_text(encoding="utf-8").split()
    assert formulae == ["git"]
    # The stub cannot delete the real keg dir, so the honest retained-prefix
    # check reports it and the cleanup exits non-zero — the fail-loud path.
    assert exit_code == 1
    result = json.loads((state_path.parent / "homebrew-cleanup-result.json").read_text(encoding="utf-8"))
    assert any("retained installed prefix" in error for error in result["errors"])


def test_deferred_cleanup_is_clean_when_nothing_is_retained(tmp_path: Path) -> None:
    """A fully-reversed install (no keg left) exits zero with no errors."""
    state_path, _state_dir = _seed_cleanup_state(tmp_path, installed=False)
    exit_code = run_deferred_cleanup(state_path)
    assert exit_code == 0
    result = json.loads((state_path.parent / "homebrew-cleanup-result.json").read_text(encoding="utf-8"))
    assert result["errors"] == []
    assert result["retained_formulae"] == []
    assert result["retained_taps"] == []


def test_deferred_cleanup_surfaces_a_failed_untap(tmp_path: Path) -> None:
    """A cleanup command failure is accumulated and exits non-zero, never silent."""
    state_path, state_dir = _seed_cleanup_state(tmp_path, installed=False)
    (state_dir / "fail-untap").write_text("", encoding="utf-8")
    exit_code = run_deferred_cleanup(state_path)
    assert exit_code == 1
    result = json.loads((state_path.parent / "homebrew-cleanup-result.json").read_text(encoding="utf-8"))
    assert any("untap" in error or "retained taps" in error for error in result["errors"])


def test_smoke_parser_accepts_retain_install() -> None:
    """The lane flag parses and defaults off (inline cleanup stays the default)."""
    base = [
        "--formula",
        "Formula/cadrumo.rb",
        "--cohort-dir",
        "cohort",
        "--evidence-dir",
        "evidence",
    ]
    assert _parser().parse_args(base).retain_install is False
    assert _parser().parse_args([*base, "--retain-install"]).retain_install is True


def test_tap_name_accepts_the_underscored_architecture_matrix_id() -> None:
    """The linux-x86_64 matrix tap must pass, matching Homebrew's own tap grammar."""
    _require_valid_tap_name("cadrumo-smoke/linux-x86_64")
    _require_valid_tap_name("cadrumo-smoke/macos-arm64")


@pytest.mark.parametrize(
    "tap_name",
    [
        "Cadrumo-Smoke/linux",
        "cadrumo-smoke",
        "cadrumo smoke/linux",
        "/linux-x86_64",
        "cadrumo-smoke/",
    ],
)
def test_tap_name_rejects_a_malformed_pair(tap_name: str) -> None:
    """A non-lowercase or non-``user/repository`` tap name is still refused."""
    with pytest.raises(SystemExit, match="one lowercase user/repository pair"):
        _require_valid_tap_name(tap_name)


def test_localization_changes_only_the_three_cohort_acquisition_urls(tmp_path: Path) -> None:
    """Loopback acquisition preserves the generated formula outside cohort URLs."""
    cohort = tmp_path / "cohort"
    cohort.mkdir()
    filenames = (
        "cadrumo-0.2.1.tar.gz",
        "cadrumo_data_manuals-0.2.1.tar.gz",
        "cadrumo_data_official-0.2.1.tar.gz",
    )
    digests: dict[str, str] = {}
    for filename in filenames:
        payload = filename.encode()
        (cohort / filename).write_bytes(payload)
        digests[filename] = hashlib.sha256(payload).hexdigest()
    base = "https://github.com/nevenincs/cadrumo/releases/download/v0.2.1"
    formula = "\n".join(
        (
            "class Cadrumo < Formula",
            f'  url "{base}/{filenames[0]}"',
            f'  sha256 "{digests[filenames[0]]}"',
            '  resource "cadrumo-data-manuals" do',
            f'    url "{base}/{filenames[1]}"',
            f'    sha256 "{digests[filenames[1]]}"',
            "  end",
            '  resource "cadrumo-data-official" do',
            f'    url "{base}/{filenames[2]}"',
            f'    sha256 "{digests[filenames[2]]}"',
            "  end",
            '  resource "unrelated-dependency" do',
            '    url "https://files.pythonhosted.org/packages/unrelated-dependency.tar.gz"',
            "  end",
            "end",
            "",
        ),
    )

    localized, replacements = localize_formula(
        formula,
        cohort_dir=cohort.resolve(),
        server_base_url="http://127.0.0.1:43123",
    )

    assert len(replacements) == 3
    assert "https://files.pythonhosted.org/packages/unrelated-dependency.tar.gz" in localized
    restored = localized
    for original, replacement in replacements.items():
        assert replacement in localized
        restored = restored.replace(replacement, original)
    assert restored == formula


def test_localization_rejects_an_incomplete_cohort_formula(tmp_path: Path) -> None:
    """The harness cannot silently test a formula missing one cohort member."""
    cohort = tmp_path / "cohort"
    cohort.mkdir()
    artifact = cohort / "cadrumo-0.2.1.tar.gz"
    artifact.write_bytes(b"root")
    formula = (
        "class Cadrumo < Formula\n"
        '  url "https://github.com/nevenincs/cadrumo/releases/download/v0.2.1/'
        'cadrumo-0.2.1.tar.gz"\n'
        f'  sha256 "{hashlib.sha256(b"root").hexdigest()}"\n'
        "end\n"
    )

    with pytest.raises(SystemExit, match="expected root and two companion"):
        localize_formula(
            formula,
            cohort_dir=cohort.resolve(),
            server_base_url="http://127.0.0.1:43123",
        )


def test_localization_rejects_a_cohort_archive_not_matching_the_formula_digest(
    tmp_path: Path,
) -> None:
    """The source smoke cannot pass through a stale or substituted cohort archive."""
    cohort = tmp_path / "cohort"
    cohort.mkdir()
    filenames = (
        "cadrumo-0.2.1.tar.gz",
        "cadrumo_data_manuals-0.2.1.tar.gz",
        "cadrumo_data_official-0.2.1.tar.gz",
    )
    expected_payload = b"accepted source archive"
    expected_sha256 = hashlib.sha256(expected_payload).hexdigest()
    for filename in filenames:
        (cohort / filename).write_bytes(expected_payload)
    (cohort / filenames[0]).write_bytes(b"different source archive")
    base = "https://github.com/nevenincs/cadrumo/releases/download/v0.2.1"
    formula = "\n".join(
        (
            "class Cadrumo < Formula",
            f'  url "{base}/{filenames[0]}"',
            f'  sha256 "{expected_sha256}"',
            '  resource "cadrumo-data-manuals" do',
            f'    url "{base}/{filenames[1]}"',
            f'    sha256 "{expected_sha256}"',
            "  end",
            '  resource "cadrumo-data-official" do',
            f'    url "{base}/{filenames[2]}"',
            f'    sha256 "{expected_sha256}"',
            "  end",
            "end",
            "",
        ),
    )

    with pytest.raises(SystemExit, match="cohort artifact digest mismatch"):
        localize_formula(
            formula,
            cohort_dir=cohort.resolve(),
            server_base_url="http://127.0.0.1:43123",
        )


def test_oracle_evidence_refuses_a_keg_whose_cli_misses_the_expected_figure() -> None:
    """The installed CLI must reproduce the oracle figure, not merely run."""
    with pytest.raises(SystemExit, match="installed CLI oracle returned unexpected evidence"):
        _assert_oracle_evidence(tax_document={"target_value": "22999.99"})
