"""Published IVA country-vocabulary indexes.

Private implementation for the canonical establishment resolvers.
"""

from __future__ import annotations

from ...core.text_fold import fold_printed_phrase

_ALPHA2_LENGTH = 2
_ALPHA3_LENGTH = 3


def normalise_printed_country_name(printed: str) -> str:
    """Return the form a printed country name is matched under.

    Three normalisations and no more. Case is folded because a document sets its
    address block in whatever typography it likes. Runs of whitespace collapse to
    one because a name broken across an address line arrives with the break in
    it. Combining accents are folded away because invoicing systems routinely
    print ASCII-only, so ``"Mexico"`` and ``"México"`` are the same printed name.

    Punctuation is deliberately NOT stripped: ``"EE.UU."`` is carried in the
    vocabulary with its stops, and squeezing punctuation generally would start
    matching strings that are not names.
    """
    return fold_printed_phrase(printed)


def country_codes_by_printed_name() -> dict[str, str]:
    """Return every vocabulary name, normalised, mapped to its alpha-2 code.

    Read from the published runtime authority rather than written here, so this
    resolver shares the validated catalogue identity used by other consumers.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read, names a
            malformed code, or maps one normalised name to two different
            countries. The last is the check that makes accent folding safe:
            folding is only sound while no two distinct countries fold together,
            and this refuses the table rather than resolving the collision to
            whichever record happened to be read last.
    """
    from ..calculations.registry.authority import bundled_authority

    resolved: dict[str, str] = {}
    for record in bundled_authority().catalogues.runtime.countries.values():
        for name in record.names:
            _claim_printed_country_name(resolved, name, code=record.code, target="published authority")
    return resolved


def _claim_printed_country_name(
    resolved: dict[str, str],
    name: object,
    *,
    code: str,
    target: str,
) -> None:
    """Bind one printed name to its country, refusing a blank name or a cross-country collision.

    Raises:
        IvaCatalogueError: When the name normalises to nothing, or when two
            DIFFERENT countries claim one normalised name.
    """
    from .errors import IvaCatalogueError

    normalised = normalise_printed_country_name(str(name))
    if not normalised:
        raise IvaCatalogueError(f"{target}: country {code} carries a blank printed name")
    claimed = resolved.get(normalised)
    if claimed is not None and claimed != code:
        raise IvaCatalogueError(
            f"{target}: the printed name {name!r} normalises to {normalised!r}, which both "
            f"{claimed} and {code} claim; a name that cannot name one country cannot establish one",
        )
    resolved[normalised] = code


def country_codes_by_alpha3() -> dict[str, str]:
    """Return every vocabulary record's alpha-3 code mapped to its alpha-2 code.

    Read from the same published country projection as the printed names, and
    deliberately so: the alpha-3 form is a second way of
    STATING the country that record already names, so recording it anywhere else
    would put two authorities on one country.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read or a record
            breaks the one-code-one-country invariant.
    """
    from ..calculations.registry.authority import bundled_authority

    resolved: dict[str, str] = {}
    alpha3_by_code: dict[str, str] = {}
    for record in bundled_authority().catalogues.runtime.countries.values():
        _claim_country_alpha3(
            resolved,
            alpha3_by_code,
            target="published authority",
            code=record.code,
            alpha3=record.alpha3,
        )
    return resolved


def _claim_country_alpha3(
    resolved: dict[str, str],
    alpha3_by_code: dict[str, str],
    *,
    target: str,
    code: str,
    alpha3: str,
) -> None:
    """Bind one country identity, refusing either direction of contradiction."""
    from .errors import IvaCatalogueError

    claimed = resolved.get(alpha3)
    if claimed is not None and claimed != code:
        raise IvaCatalogueError(
            f"{target}: the alpha-3 code {alpha3!r} is claimed by both {claimed} and {code}; "
            f"a code that cannot name one country cannot establish one",
        )
    stated = alpha3_by_code.get(code)
    if stated is not None and stated != alpha3:
        raise IvaCatalogueError(
            f"{target}: country {code} states two different alpha-3 codes, {stated!r} and {alpha3!r}",
        )
    resolved[alpha3] = code
    alpha3_by_code[code] = alpha3
