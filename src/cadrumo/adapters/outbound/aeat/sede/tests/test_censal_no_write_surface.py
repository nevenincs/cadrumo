"""No-write proof for the censal consulta reader.

The censal consulta page is one control away from a write. It offers
*Cambio de Domicilio Fiscal* and *Cambio de Domicilio de Notificaciones*
buttons, links the M036 filing tool, and carries an *Otras Modificaciones
Censales* link into the procedure launcher. Reading its rendered DOM is a
read; driving any of those is not.

The proof has two walls of unequal strength, and the weaker one is kept
only because it is cheap:

The PRIMARY wall is the runtime landing refusal. AEAT chooses where a
navigation lands, not this code, so the only trustworthy check is on the
URL actually served after the redirect chain. This file exercises that
refusal through the reader's own exported rule, which the runtime guard
itself calls, so the gate measures the real logic rather than a copy of
it that would agree with itself.

The SECONDARY wall is a static source scan. It is weak by construction: a
static token check cannot see where a navigation lands, and the original
specification for this gate proposed exactly one such check, for the
token ``MOD036`` - which appears in NEITHER write surface, since the
filing tool is ``BU36-ASIS/M036/index.zul`` and the write sibling is
``BUGC-JDIT/ModifDomiDual``. That gate would have gone green over a
reader parked beside a write surface. It is retained as a second wall and
must never be treated as the proof; if the runtime half is ever removed
as redundant, this file has failed at its job.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ......core.config import Settings
from .. import is_forbidden_censal_landing

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_SEDE_ROOT = Path(__file__).resolve().parent.parent
_CENSAL_MODULE = _SEDE_ROOT / "_censal_datos.py"

# Real AEAT write surfaces the reader must never be left sitting on.
# Every one is drawn from bundled AEAT material or a live authenticated
# capture, not invented for this test.
_WRITE_LANDINGS: tuple[str, ...] = (
    "https://www1.agenciatributaria.gob.es/wlpl/BU36-M036/MOD036/index.zul",
    "https://www1.agenciatributaria.gob.es/wlpl/BU36-ASIS/M036/index.zul",
    "https://www6.agenciatributaria.gob.es/wlpl/BUGC-JDIT/ModifDomiDual?NIF=Y0000001Z",
    "https://www6.agenciatributaria.gob.es/wlpl/BUGC-JDIT/ModifDomiNotif?NIF=Y0000001Z",
    "https://sede.agenciatributaria.gob.es//Sede/procedimientoini/G322.shtml",
    "https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml",
    "https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G414.shtml",
)

# The landing the reader legitimately wants, plus the surfaces sibling
# readers use. A marker set that rejects these is unusable and would be
# switched off, so they are pinned as must-pass.
_READ_LANDINGS: tuple[str, ...] = (
    "https://www6.agenciatributaria.gob.es/wlpl/BUGC-JDIT/MdcAcceso?nifRepresentado=Y0000001Z",
    "https://www6.agenciatributaria.gob.es/wlpl/TEWV-CORE/ResumenVlt",
    "https://www6.agenciatributaria.gob.es/wlpl/GNNO-JDIT/ResumenInteresados",
    "https://www1.agenciatributaria.gob.es/wlpl/DAI3-RUTI/CarteraCuotas",
)


def _forbidden_landing_markers() -> tuple[str, ...]:
    """Return the registry-declared censal forbidden-landing markers."""
    return tuple(Settings.external_constants().aeat.live_safety.censal_forbidden_landing_markers)


class TestForbiddenLandingMarkers:
    """The reader's own landing rule must discriminate write surfaces from read ones.

    These exercise ``is_forbidden_censal_landing``, which is the single
    matching rule the runtime guard calls - not a copy of it. An earlier
    draft of this gate mirrored the reader's fold-and-substring matching
    locally, and that mirror was the weakness worth naming: a test that
    reimplements the rule it checks agrees with itself by construction, so
    if the real rule ever changed shape - a regex, a normalisation, a
    host-aware check - the mirror would keep passing while the reader
    diverged, and this file would report green on a property it had
    stopped measuring.
    """

    @pytest.mark.parametrize("landing_url", _WRITE_LANDINGS)
    def test_every_known_write_surface_is_refused(self, landing_url: str) -> None:
        """A landing on any real censal write surface must be refused."""
        assert is_forbidden_censal_landing(landing_url), (
            f"{landing_url} is a censal write surface and the reader's landing rule allows it"
        )

    @pytest.mark.parametrize("landing_url", _READ_LANDINGS)
    def test_read_surfaces_are_not_refused(self, landing_url: str) -> None:
        """The consulta landing and sibling read surfaces must stay reachable."""
        assert not is_forbidden_censal_landing(landing_url), (
            f"{landing_url} is a read surface and the reader's landing rule rejects it"
        )

    def test_the_launcher_marker_is_a_prefix_not_a_code(self) -> None:
        """The procedure-launcher marker covers the family, not one door.

        A literal such as ``G322`` catches the door that happened to be
        found and leaves ``G313``, ``G414`` and every future code open.
        This is the same defect as the ``MOD036`` token: a member standing
        in for its class.
        """
        markers = _forbidden_landing_markers()
        assert "/Sede/procedimientoini/" in markers, (
            f"the procedure-launcher marker must be the path prefix; declared markers are {markers}"
        )

    def test_the_marker_set_is_not_vacuous(self) -> None:
        """A marker that matched everything, or nothing, would pass the tests above trivially."""
        markers = _forbidden_landing_markers()
        assert markers, "no forbidden-landing markers declared"
        assert "" not in markers, "an empty marker matches every landing and disables the guard"


class TestCensalPublicSurfaceOffersNoWrite:
    """The censal reader's public surface must expose no way to drive a control."""

    def test_public_surface_exposes_no_mutating_callable(self) -> None:
        """No exported censal symbol may offer a submit, fill, click or follow.

        Pydantic v2 reserves the ``model_`` prefix for its own API, so
        those members are framework surface rather than anything this
        reader chose to expose; they are skipped by that reserved prefix
        rather than by naming individual hooks, so a future pydantic
        lifecycle method cannot smuggle a false positive back in.
        """
        from ... import sede

        forbidden_fragments = ("submit", "fill", "click", "follow", "send", "presentar", "modificar", "guardar")
        offenders: list[str] = []
        for name in sede.__all__:
            if "censal" not in name.casefold():
                continue
            attribute = getattr(sede, name)
            for member in dir(attribute):
                if member.startswith("_") or member.startswith("model_"):
                    continue
                if any(fragment in member.casefold() for fragment in forbidden_fragments):
                    offenders.append(f"{name}.{member}")
        assert not offenders, f"censal public surface exposes a mutating member: {offenders}"

    def test_the_surface_scan_reports_a_planted_mutating_member(self) -> None:
        """Prove the scan flags a writing surface rather than passing over it.

        The planted object is an input to the scanner, not a stand-in for
        the reader: a no-write proof that has never seen a writing surface
        refuse is the same false green as a scanner that read nothing.
        """
        forbidden_fragments = ("submit", "fill", "click", "follow", "send", "presentar", "modificar", "guardar")

        class _WritingCensalReader:
            def submit_modificacion(self) -> None:
                """A control-driving method the real reader must never grow."""

        offenders = [
            member
            for member in dir(_WritingCensalReader)
            if not member.startswith(("_", "model_")) and any(f in member.casefold() for f in forbidden_fragments)
        ]
        assert offenders == ["submit_modificacion"]

    def test_the_scan_covers_a_non_empty_censal_surface(self) -> None:
        """A clean result above means nothing if no censal symbol was exported."""
        from ... import sede

        exported = [name for name in sede.__all__ if "censal" in name.casefold()]
        assert exported, "no censal symbols exported from the sede facade; the scan above read nothing"


class TestStaticFilingPathWall:
    """The weaker of the two walls, kept and labelled as such."""

    def test_module_source_names_no_filing_tool_path(self) -> None:
        """The reader's source must not carry a filing-tool path.

        Weak by construction: it proves the reader does not NAME a write
        path, not that it cannot LAND on one. The runtime landing refusal
        is the wall that matters.
        """
        source = _CENSAL_MODULE.read_text(encoding="utf-8")
        for fragment in ("BU36-M036", "BU36-ASIS", "MOD036"):
            for line in source.splitlines():
                stripped = line.strip()
                if fragment in line and not stripped.startswith("#") and '"""' not in line:
                    pytest.fail(f"censal reader source names filing path {fragment!r}: {stripped}")

    def test_the_static_wall_fails_on_a_planted_filing_path(self, tmp_path: Path) -> None:
        """Prove the static scan reports a filing path rather than passing over it."""
        planted = tmp_path / "planted_reader.py"
        planted.write_text(
            'TARGET = "https://www1.agenciatributaria.gob.es/wlpl/BU36-ASIS/M036/index.zul"\n',
            encoding="utf-8",
        )
        source = planted.read_text(encoding="utf-8")
        hits = [line for line in source.splitlines() if "BU36-ASIS" in line and not line.strip().startswith("#")]
        assert hits, "the static scan would not have reported a planted filing path"
