"""The external-oracle corpus closed value set.

An external oracle is an AEAT-authoritative expected value that a casilla's
engine result can be reconciled against, independently of the application's own
calculation. A grounding claim is only as strong as the corpus behind it, so
the corpus a figure came from travels with it rather than being flattened away
at the fold.

Two corpora exist, and they no longer share a root. The AEAT Manual practico
worked-example figures still ship with the package under
``_data/corpus/manual_oracles/``. The Renta WEB Open replay captures do not
ship at all: they are repository-only development artefacts beside this module.
The axis is declared here rather than in ``cadrumo.core`` because everything
that consumes it is development tooling -- a quality signal over the registry,
not a product capability.

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
    """A corpus that supplies an AEAT-authoritative expected casilla value.

    The two members do not share a root, and the split is deliberate rather
    than incidental: only one of these corpora ships.

    Attributes:
        RENTA_WEB_OPEN_REPLAY: The Renta WEB Open open-simulator replay corpus,
            a repository-only development artefact under
            ``dev/registry/parity/parity_replays/renta_web_open/``, whose
            expected figures were captured from AEAT's own live simulator. The
            captures that exist cover 2025 Modelo 100 only.
        AEAT_MANUAL_WORKED_EXAMPLE: The AEAT Manual practico worked-example
            corpus, packaged under ``_data/corpus/manual_oracles/``, whose
            expected figures are quoted verbatim from a bundled manual's caso
            practico table.
    """

    RENTA_WEB_OPEN_REPLAY = "renta_web_open_replay"
    AEAT_MANUAL_WORKED_EXAMPLE = "aeat_manual_worked_example"


__all__ = ["ExternalOracleCorpus"]
