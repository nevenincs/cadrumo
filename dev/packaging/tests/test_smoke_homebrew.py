"""Direct tests for the real Homebrew source-install harness."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from dev.packaging.smoke_homebrew import (
    _assert_oracle_evidence,
    _require_valid_tap_name,
    localize_formula,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_tap_name_accepts_the_underscored_architecture_matrix_id() -> None:
    """The linux-x86_64 matrix tap must pass, matching Homebrew's own tap grammar."""
    _require_valid_tap_name("cadrumo-smoke/linux-x86_64")
    _require_valid_tap_name("cadrumo-smoke/macos-intel")


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
            '  resource "mcp" do',
            '    url "https://files.pythonhosted.org/packages/mcp.tar.gz"',
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
    assert "https://files.pythonhosted.org/packages/mcp.tar.gz" in localized
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


def test_oracle_evidence_requires_the_mcp_child_to_be_the_installed_cli() -> None:
    """Compatible MCP output is insufficient when its invoked CLI identity differs."""
    with pytest.raises(SystemExit, match="different CLI identity"):
        _assert_oracle_evidence(
            tax_document={"target_value": "23000.00"},
            mcp_document={
                "target_value": "23000.00",
                "invoked_cli_sha256": "1" * 64,
            },
            aeat_path_sha256="2" * 64,
        )
