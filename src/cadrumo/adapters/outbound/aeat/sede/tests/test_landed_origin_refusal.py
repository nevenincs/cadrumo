"""Every sede reader refuses an origin it cannot establish.

A recorded ``source_url`` is a claim about where a read happened. AEAT
load-balances the authenticated session across its numbered pool, so when
the landing cannot be read there is no evidence the read stayed on the
requested host. Substituting the navigated origin prints a guess into the
same field as a measurement, and no later reader can tell them apart.

The three readers previously disagreed: declarations fell back to a fixed
``www6``, the IVA wallet fell back to the unnumbered wallet URL, and censal
refused. They now all refuse.

Two separable claims live here, and they need different evidence:

* The REFUSAL is a behaviour change. Outcome assertions discriminate: with
  a refusal reverted, a fabricated origin is observably produced. Marked
  ``DISCRIMINATING``.
* The shared ``landed_origin`` EXTRACTION is a pure dedup with no behaviour
  change -- all three readers agreed on it even before consolidation, which
  is why nobody noticed the duplication. An outcome assertion cannot defend
  it, because a re-inlined copy would agree. It is defended by IDENTITY
  instead: the readers resolve to the same function object, and the retired
  inline extraction is absent from the compiled modules. Marked ``IDENTITY``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import pytest

from ......core.config import Settings
from ......tests.aeat_literal_fixtures import LANDED_ORIGIN_CARTERA_CUOTAS_PATH_FIXTURE
from .. import _adapter_utils, _declarations_fetch, iva_compensation_wallet
from .._adapter_utils import landed_origin
from ..errors import SedeNavigationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_DOMAINS = Settings.external_constants().aeat.domains

# Landings that carry no usable scheme + host. Hardcoded rather than derived
# from the production predicate, which would only prove self-consistency.
_UNUSABLE_LANDINGS: tuple[str | None, ...] = (
    "",
    None,
    "not-a-url",
    "/relative/only",
    "about:blank",
    "?query=only",
)

_USABLE_LANDINGS: tuple[str, ...] = (
    f"{_DOMAINS.www1}/x",
    f"{_DOMAINS.www12}{LANDED_ORIGIN_CARTERA_CUOTAS_PATH_FIXTURE}",
)


class _LandedPage:
    """Carries a landed URL, the one attribute these readers read off a page."""

    def __init__(self, url: str) -> None:
        self.url = url


class TestTheSharedExtraction:
    """``landed_origin`` answers only "which host", never "which host probably"."""

    @pytest.mark.parametrize("landed", _UNUSABLE_LANDINGS)
    def test_an_unusable_landing_yields_no_origin(self, landed: str | None) -> None:
        """DISCRIMINATING: absence is reported as absence, not as a default."""
        assert landed_origin(landed) is None

    @pytest.mark.parametrize("landed", _USABLE_LANDINGS)
    def test_a_usable_landing_yields_its_own_origin(self, landed: str) -> None:
        """SUPPORTING: the admit path, and proof the helper is not constant-None."""
        origin = landed_origin(landed)
        assert origin is not None
        assert landed.startswith(origin)


class TestTheWalletRefuses:
    """The IVA wallet no longer records the unnumbered URL as a landing."""

    @pytest.mark.parametrize("landed", _UNUSABLE_LANDINGS)
    def test_an_unusable_landing_is_refused(self, landed: str | None) -> None:
        """DISCRIMINATING: reverting the refusal produces the fabricated URL.

        Pins the specific wrong value the retired fallback returned, so a
        revert reports the fabrication rather than a bare missing exception.
        """
        page = _LandedPage(landed or "")
        produced: str | None = None
        try:
            produced = iva_compensation_wallet._landed_wallet_url(page)
        except SedeNavigationError:
            produced = None
        assert produced != iva_compensation_wallet.IVA_COMPENSATION_WALLET_URL, (
            f"FABRICATED wallet source_url {produced!r} recorded for an unusable landing {landed!r}"
        )
        assert produced is None

    @pytest.mark.parametrize("landed", _USABLE_LANDINGS)
    def test_a_usable_landing_records_the_host_that_answered(self, landed: str) -> None:
        """SUPPORTING: the admit path still names the landed host."""
        recorded = iva_compensation_wallet._landed_wallet_url(_LandedPage(landed))
        assert recorded.startswith(landed_origin(landed) or "")


class TestAllThreeReadersAgreeOnRefusal:
    """The conform: no reader may still invent an origin."""

    @pytest.mark.parametrize("landed", _UNUSABLE_LANDINGS)
    def test_neither_reader_returns_a_value(self, landed: str | None) -> None:
        """DISCRIMINATING: each side asserted absolutely, then compared.

        Two relaxed predicates would agree with each other while admitting
        everything, so each reader is separately required to refuse before
        the agreement is asserted.
        """
        with pytest.raises(SedeNavigationError):
            _declarations_fetch._origin_of(landed)
        with pytest.raises(SedeNavigationError):
            iva_compensation_wallet._landed_wallet_url(_LandedPage(landed or ""))


class TestTheExtractionIsOneSharedPredicate:
    """IDENTITY, not agreement: a re-inlined copy would agree and prove nothing."""

    def test_both_readers_resolve_to_the_same_function_object(self) -> None:
        """IDENTITY: the same object, not merely an equal result.

        A value-equality assertion passes against a re-derived copy that
        happens to agree today, which is precisely the state consolidation
        removes. ``is`` cannot.
        """
        assert _declarations_fetch._landed_origin is _adapter_utils.landed_origin
        assert iva_compensation_wallet.landed_origin is _adapter_utils.landed_origin

    @pytest.mark.parametrize(
        "module",
        [_declarations_fetch, iva_compensation_wallet],
    )
    def test_the_retired_inline_extraction_is_absent(self, module: ModuleType) -> None:
        """IDENTITY: the old two-line urlsplit shape is gone from the module.

        Scans for the retired construction -- reading ``.scheme`` and
        ``.netloc`` off a urlsplit result to build an origin string -- rather
        than trusting that the call sites were the only copies.
        """
        assert module.__file__ is not None
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        offenders = [
            ast.unparse(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.JoinedStr) and "scheme" in ast.unparse(node) and "netloc" in ast.unparse(node)
        ]
        assert not offenders, f"retired inline origin extraction still present: {offenders}"
