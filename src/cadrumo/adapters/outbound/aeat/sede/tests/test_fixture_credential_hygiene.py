"""Credential hygiene for the captured AEAT sede fixtures.

A capture of an authenticated AEAT page carries more than the operator's
identity. The forms on it hold session and anti-CSRF tokens minted for
that live session, and those are credentials rather than personal data,
so an identity-redaction pass does not remove them and a personal-data
review does not look for them.

This gate scans every fixture for input values whose SHAPE is
credential-like, because the field NAME is not a usable signal: the token
that prompted this gate was named ``CI1_ISLW``, which matches none of
``token``, ``csrf``, ``session`` or ``jsessionid`` and reads as markup
noise. What separates a credential from a structural value is that the
credential is opaque and high-entropy, while a structural value is a
readable censal, navigational, or framework term.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from ......core.directory_scan import scan_directory
from ......tests import FIXTURES_DIR
from ......tests.aeat_literal_fixtures import configured_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"

# A credential-shaped run is an unbroken stretch of token characters.
# Separator punctuation (``.``, ``-``, ``_``, ``:``, whitespace) BREAKS a
# run, because structural values are built from readable segments joined
# by separators while a minted token is one continuous stretch. ``+/=``
# stay inside a run since they are base64 alphabet, not separators.
_RUN = re.compile(r"[A-Za-z0-9+/=]+")
_INPUT_VALUE = re.compile(r"<input\b[^>]*\bvalue=\"([^\"]*)\"", re.IGNORECASE)

# A minted AEAT form token is 30+ characters; the longest readable segment
# observed across the committed captures is ``SvInteresadosQuery`` at 18,
# inside a dotted Java class name. 20 sits above every observed structural
# segment and below every observed token.
_MIN_RUN_LENGTH = 20
# Shannon entropy per character. Readable text over a mixed alphabet sits
# well under 3.0; a random 36-character token sits above 4.0.
_MIN_ENTROPY_BITS = 3.0


def _shannon_bits_per_char(value: str) -> float:
    """Return the Shannon entropy of ``value`` in bits per character."""
    if not value:
        return 0.0
    counts = {char: value.count(char) for char in set(value)}
    length = len(value)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def is_credential_shaped(value: str) -> bool:
    """Return whether ``value`` looks like a minted credential rather than a structural term.

    The test is applied to the longest unbroken token-character run in
    ``value``, so a dotted class name or a slash-separated path is judged
    by its segments rather than its total length. A run qualifies only
    when it is long, mixes all three character classes, and carries real
    entropy - readable identifiers fail at least one of the three.
    """
    for run in sorted(_RUN.findall(value), key=len, reverse=True):
        if len(run) < _MIN_RUN_LENGTH:
            # Runs are sorted longest-first, so nothing shorter can qualify.
            return False
        has_mixed_case = any(c.islower() for c in run) and any(c.isupper() for c in run)
        if has_mixed_case and any(c.isdigit() for c in run) and _shannon_bits_per_char(run) >= _MIN_ENTROPY_BITS:
            return True
    return False


def credential_shaped_input_values(html: str) -> tuple[str, ...]:
    """Return every ``<input>`` value in ``html`` that is credential-shaped."""
    return tuple(value for value in (str(item) for item in _INPUT_VALUE.findall(html)) if is_credential_shaped(value))


def scan_fixture_root(root: Path) -> tuple[str, ...]:
    """Return one finding per credential-shaped input value under ``root``.

    ``root`` is a parameter rather than the module constant so the gate can
    be pointed at a directory carrying a planted credential and proven to
    fail; a scanner that has never been shown failing is not evidence.
    """
    findings: list[str] = []
    for path in scan_directory(root, pattern="*.html", recursive=True):
        for value in credential_shaped_input_values(path.read_text(encoding="utf-8", errors="replace")):
            findings.append(f"{path.relative_to(root)}: {value}")
    return tuple(findings)


def _committed_fixtures() -> Iterator[Path]:
    """Yield the sede fixture files tracked in the repository."""
    yield from scan_directory(_FIXTURE_ROOT, pattern="*.html", recursive=True)


class TestCredentialDiscriminator:
    """Pin the discriminator against the values that provoked it."""

    def test_the_real_aeat_session_token_is_flagged(self) -> None:
        """The token found in a live censal capture must be rejected."""
        assert is_credential_shaped("s0VhO79FzmfL9GIKtTZUvku5bdsfTcFm07pC")

    @pytest.mark.parametrize(
        "value",
        [
            "EJECUTADO EN INTERNET",
            configured_path("sede_paths", "censal_datos"),
            "es.aeat.gnno.jdit.web.punSede.interesados.query.SvInteresadosQuery",
            "20/1/20260424215615255685",
            "CONSIDENIT",
            "Y0000001Z",
            "FIXTURECSV1234X7",
            "NORMAL",
            "false",
            "",
        ],
    )
    def test_structural_values_are_not_flagged(self, value: str) -> None:
        """Readable censal, navigational and framework values must survive.

        Every entry here is a real value from a committed capture or one
        named in the gate's brief. A false positive would push an author
        to corrupt structural markup to appease the gate, which is worse
        than the leak it prevents.
        """
        assert not is_credential_shaped(value)


class TestFixtureCredentialHygiene:
    """No committed sede fixture may carry a credential-shaped input value."""

    def test_committed_fixtures_carry_no_credentials(self) -> None:
        """Scan every tracked sede fixture and refuse credential-shaped values."""
        findings = scan_fixture_root(_FIXTURE_ROOT)
        assert not findings, "Credential-shaped input value in a committed sede fixture:\n" + "\n".join(findings)

    def test_the_scan_covers_a_non_empty_fixture_set(self) -> None:
        """A gate that scanned nothing would pass regardless of the fixtures.

        The clean result above means something only if the scan actually
        read files carrying input elements.
        """
        fixtures = tuple(_committed_fixtures())
        assert fixtures, f"no sede fixtures found under {_FIXTURE_ROOT}"
        assert any(_INPUT_VALUE.search(path.read_text(encoding="utf-8", errors="replace")) for path in fixtures)

    def test_scan_fails_on_a_planted_credential(self, tmp_path: Path) -> None:
        """Prove the scan reports a credential rather than passing over it.

        The planted fixture reproduces the real shape: a hidden input whose
        name carries no credential vocabulary, alongside a structural
        hidden input that must not be reported.
        """
        planted = tmp_path / "planted-capture.html"
        planted.write_text(
            '<form><input type="hidden" id="CI1_ISLW" name="CI1_ISLW" '
            'value="s0VhO79FzmfL9GIKtTZUvku5bdsfTcFm07pC">'
            '<input type="hidden" name="CAB-MOTIVO" value="EJECUTADO EN INTERNET"></form>',
            encoding="utf-8",
        )
        findings = scan_fixture_root(tmp_path)
        assert len(findings) == 1
        assert "s0VhO79FzmfL9GIKtTZUvku5bdsfTcFm07pC" in findings[0]
        assert "EJECUTADO EN INTERNET" not in findings[0]
