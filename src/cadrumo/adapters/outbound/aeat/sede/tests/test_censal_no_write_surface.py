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
specification for this gate proposed exactly one such check, for a token
that appears in NEITHER of the two real write surfaces - the filing tool
and the domicile-modification sibling both carry different route names.
That gate would have gone green over a reader parked beside a write
surface. It is retained as a second wall and must never be treated as the
proof; if the runtime half is ever removed as redundant, this file has
failed at its job. The paths themselves are not repeated here: they are
declared canaries, so this file names none of them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ......core.config import Settings
from ......tests.aeat_literal_fixtures import (
    CENSAL_M036_FILING_TOOL_PATH_CANARY,
    CENSAL_WRITE_SURFACE_PATH_CANARIES,
    PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE,
    aeat_url,
    configured_path,
)
from ..censal_datos import is_forbidden_censal_landing

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_SEDE_ROOT = Path(__file__).resolve().parent.parent
_CENSAL_MODULE = _SEDE_ROOT / "censal_datos.py"

# Procedure codes reachable from the consulta page's own launcher links.
# G322 is the "Otras Modificaciones Censales" door confirmed live on the
# page the reader lands on; the others are siblings in the same family,
# present so the marker cannot be narrowed back to a single code.
_LAUNCHER_CODES: tuple[str, ...] = ("G322", "G313", "G414")

# Real AEAT write surfaces the reader must never be left sitting on, built
# from declared canaries and configured origins rather than literals. The
# origin is deliberately incidental: the landing rule keys on the path, so
# any AEAT origin serving these paths must be refused.
_WRITE_LANDINGS: tuple[str, ...] = (
    *(aeat_url("www1", path) for path in CENSAL_WRITE_SURFACE_PATH_CANARIES),
    *(aeat_url("sede", f"{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}{code}.shtml") for code in _LAUNCHER_CODES),
)

# The landing the reader legitimately wants, plus the surfaces sibling
# readers use. A rule that rejects these is unusable and would be switched
# off, so they are pinned as must-pass.
_READ_LANDINGS: tuple[str, ...] = (
    aeat_url("www6", configured_path("sede_paths", "censal_datos")),
    aeat_url("www6", configured_path("sede_paths", "expedientes_resumen")),
    aeat_url("www6", configured_path("sede_paths", "notifications_summary")),
    aeat_url("www1", configured_path("sede_paths", "iva_compensation_wallet")),
)


def _filing_path_hits(source: str) -> tuple[str, ...]:
    """Return source lines naming a censal filing-tool path, comments aside.

    Both walls use this, so the check the reader is held to is the same one
    proven to fire on a planted path. The paths come from the declared
    canaries rather than from literals repeated here.
    """
    return tuple(
        line.strip()
        for line in source.splitlines()
        if any(path in line for path in CENSAL_WRITE_SURFACE_PATH_CANARIES)
        and not line.strip().startswith("#")
        and '"""' not in line
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

        A single procedure code catches the door that happened to be found
        and leaves its siblings and every future code open. That is the
        same defect as the token this proof was originally specified
        around: a member standing in for its class.
        """
        markers = _forbidden_landing_markers()
        assert PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE in markers, (
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
        from .. import censal_datos

        forbidden_fragments = ("submit", "fill", "click", "follow", "send", "presentar", "modificar", "guardar")
        offenders: list[str] = []
        for name in dir(censal_datos):
            if name.startswith("_"):
                continue
            attribute = getattr(censal_datos, name)
            if getattr(attribute, "__module__", None) != censal_datos.__name__:
                continue  # imported into the module, not part of its surface
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
        """A clean result above means nothing if the module offered nothing to read.

        This used to count censal names on the sede package facade. That facade
        is retired and exports nothing, so the guard would have gone permanently
        green-by-emptiness -- the exact false pass it exists to prevent. It now
        reads the censal module's own public surface, which is where the reader
        actually lives.
        """
        from .. import censal_datos

        public = [
            name
            for name in dir(censal_datos)
            if not name.startswith("_")
            and getattr(getattr(censal_datos, name), "__module__", None) == censal_datos.__name__
        ]
        assert public, "the censal module defines nothing; the scan above read nothing"


class TestStaticFilingPathWall:
    """The weaker of the two walls, kept and labelled as such."""

    def test_module_source_names_no_filing_tool_path(self) -> None:
        """The reader's source must not carry a filing-tool path.

        Weak by construction: it proves the reader does not NAME a write
        path, not that it cannot LAND on one. The runtime landing refusal
        is the wall that matters.
        """
        offenders = _filing_path_hits(_CENSAL_MODULE.read_text(encoding="utf-8"))
        assert not offenders, f"censal reader source names a filing path: {offenders}"

    def test_the_static_wall_fails_on_a_planted_filing_path(self, tmp_path: Path) -> None:
        """Prove the static scan reports a filing path rather than passing over it."""
        planted = tmp_path / "planted_reader.py"
        planted.write_text(
            f'TARGET = "{aeat_url("www1", CENSAL_M036_FILING_TOOL_PATH_CANARY)}"\n',
            encoding="utf-8",
        )
        offenders = _filing_path_hits(planted.read_text(encoding="utf-8"))
        assert offenders, "the static scan would not have reported a planted filing path"
