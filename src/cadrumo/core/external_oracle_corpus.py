"""The bundled external-oracle corpus closed value set.

An external oracle is an AEAT-authoritative expected value that a casilla's
engine result can be reconciled against, independently of the application's own
calculation. Two such corpora ship under ``_data/corpus/``, and a grounding
claim is only as strong as the corpus behind it, so the corpus a figure came
from travels with it rather than being flattened away at the fold.

The set is declared as a :class:`enum.StrEnum` in ``core`` per the
core-authority discipline (closed axes live in ``core/``, hydrated at
boundaries, asserted as members in tests). ``core`` is the home both sides can
reach: the registry-domain grounding fold that inventories the corpora and the
contributor-facing governance tooling that renders the inventory both consume
the axis, and neither owns it.

:attr:`ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE` carries a value
byte-identical to the ``source_kind`` token stored in the manual-oracle
payloads. The registry-domain grounding fold parses each payload through a
strict model that hydrates that token to this member, refuses an unrecognised
one, and refuses a recognised one that contradicts the corpus directory the
payload was found in — so the value is load-bearing there, not decorative.
The Renta WEB Open replay payloads declare no ``source_kind`` at all; their
member value names the corpus that holds them and is not a stored token, and
the same cross-check binds one if a replay ever declares it.
"""

from __future__ import annotations

from enum import StrEnum


class ExternalOracleCorpus(StrEnum):
    """Bundled corpus that supplies an AEAT-authoritative expected casilla value.

    Attributes:
        RENTA_WEB_OPEN_REPLAY: The Renta WEB Open open-simulator replay corpus
            (``_data/corpus/parity_replays/renta_web_open/``), whose expected
            figures were captured from AEAT's own live simulator.
        AEAT_MANUAL_WORKED_EXAMPLE: The AEAT Manual practico worked-example
            corpus (``_data/corpus/manual_oracles/``), whose expected figures
            are quoted verbatim from a bundled manual's caso practico table.
    """

    RENTA_WEB_OPEN_REPLAY = "renta_web_open_replay"
    AEAT_MANUAL_WORKED_EXAMPLE = "aeat_manual_worked_example"


__all__ = ["ExternalOracleCorpus"]
