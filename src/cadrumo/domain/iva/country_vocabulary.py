"""Bundled IVA country-vocabulary indexes.

Private implementation for the canonical establishment resolvers.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache

from ...core.external_constants import UTF_8_ENCODING
from ...core.resources.bundled_data import bundled_path
from ...core.text_fold import fold_printed_phrase
from . import establishment as _establishment

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


@lru_cache(maxsize=1)
def country_codes_by_printed_name() -> dict[str, str]:
    """Return every vocabulary name, normalised, mapped to its alpha-2 code.

    Read from ``registry/aeat/iva/country_names.toml`` rather than written here,
    for the same reason the territory table is: a name vocabulary inlined in a
    feature module is unreviewable, and reviewability is the whole argument for
    it being data.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read, names a
            malformed code, or maps one normalised name to two different
            countries. The last is the check that makes accent folding safe:
            folding is only sound while no two distinct countries fold together,
            and this refuses the table rather than resolving the collision to
            whichever record happened to be read last.
    """
    return _index_country_names(_country_vocabulary_payload(), source=_country_vocabulary_source())


def _country_vocabulary_source() -> str:
    """Return the bundled vocabulary's path, for diagnostics."""
    return str(bundled_path("registry", "aeat", "iva", "country_names.toml"))


def _country_vocabulary_payload() -> object:
    """Return the parsed vocabulary document, refusing an unreadable one.

    Split from both indexers so the two columns are read from one file once and
    cannot drift onto different copies of it.

    Raises:
        IvaCatalogueError: When the bundled table cannot be read or parsed.
    """
    from .errors import IvaCatalogueError

    target = bundled_path("registry", "aeat", "iva", "country_names.toml")
    try:
        return tomllib.loads(target.read_text(encoding=UTF_8_ENCODING))
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot read the country-name vocabulary: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise IvaCatalogueError(f"{target}: malformed country-name vocabulary: {exc}") from exc


def _index_country_names(payload: object, *, source: str) -> dict[str, str]:
    """Index an already-parsed vocabulary payload, refusing an unusable one.

    Split from the read so the refusals are reachable with a payload rather than
    only with a file: the collision refusal is the one that makes accent folding
    sound, and a check that can only be exercised against the bundled table is a
    check nothing proves.

    Args:
        payload: The parsed TOML document.
        source: What to name in a diagnostic -- the bundled path in production.

    Returns:
        Each normalised printed name mapped to its alpha-2 code.

    Raises:
        IvaCatalogueError: When a record names no alpha-2 code, carries no
            printed name, carries a blank one, when two DIFFERENT countries
            claim one normalised name, or when the vocabulary is empty.
    """
    from .errors import IvaCatalogueError

    target = source
    if not _establishment.is_str_keyed_mapping(payload):
        raise IvaCatalogueError(f"{target}: the country-name vocabulary is not a table")

    countries = payload.get("country", ())
    if not _establishment.is_object_list(countries):
        raise IvaCatalogueError(f"{target}: the country-name vocabulary carries a malformed country table")

    resolved: dict[str, str] = {}
    for record in countries:
        code, names = _country_record_code_and_names(record, target=target)
        for name in names:
            _claim_printed_country_name(resolved, name, code=code, target=target)
    if not resolved:
        raise IvaCatalogueError(f"{target}: the country-name vocabulary is empty")
    return resolved


def _country_record_code_and_names(record: object, *, target: str) -> tuple[str, list[object]]:
    """Return one vocabulary record's alpha-2 code and printed names, refusing an unusable record.

    Raises:
        IvaCatalogueError: When the record is not a table, names no alpha-2
            code, or carries no printed name.
    """
    from .errors import IvaCatalogueError

    if not _establishment.is_str_keyed_mapping(record):
        raise IvaCatalogueError(f"{target}: country record is not a table: {record!r}")
    code = str(record.get("code", "")).strip().upper()
    if len(code) != _ALPHA2_LENGTH or not code.isalpha():
        raise IvaCatalogueError(f"{target}: country record names no alpha-2 code: {record!r}")
    names = record.get("names", ())
    if not _establishment.is_object_list(names) or not names:
        raise IvaCatalogueError(f"{target}: country {code} carries no printed name")
    return code, names


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


@lru_cache(maxsize=1)
def country_codes_by_alpha3() -> dict[str, str]:
    """Return every vocabulary record's alpha-3 code mapped to its alpha-2 code.

    Read from the same ``registry/aeat/iva/country_names.toml`` the printed names
    are read from, and deliberately so: the alpha-3 form is a second way of
    STATING the country that record already names, so recording it anywhere else
    would put two authorities on one country.

    Raises:
        IvaCatalogueError: When the bundled vocabulary cannot be read or a record
            breaks the one-code-one-country invariant.
    """
    return _index_country_alpha3(_country_vocabulary_payload(), source=_country_vocabulary_source())


def _index_country_alpha3(payload: object, *, source: str) -> dict[str, str]:
    """Index the alpha-3 column, refusing a table that cannot mean one thing.

    Split from the read for the same reason the name indexer is: the refusals are
    what make the correspondence trustworthy, and a refusal reachable only
    through the bundled file is a refusal nothing proves.

    Three refusals, and each closes a way the table could load a contradiction:

    * A record carrying NO alpha-3 code. Required rather than optional, because
      an omission is indistinguishable at the call site from a country with no
      alpha-3 form: both yield nothing, and the caller reads that as "the
      document states no country" -- the silent blank this column exists to
      close.
    * Two records claiming ONE alpha-3 code. That code would then name two
      countries, and whichever record was read last would win silently.
    * One alpha-2 code claiming TWO alpha-3 codes, which is the same
      contradiction reached from the other side: a duplicated country record
      disagreeing with itself.

    Args:
        payload: The parsed TOML document.
        source: What to name in a diagnostic -- the bundled path in production.

    Returns:
        Each alpha-3 code mapped to the alpha-2 code naming the same country.

    Raises:
        IvaCatalogueError: On any of the three refusals above, on a malformed
            code in either column, or when the column is empty.
    """
    from .errors import IvaCatalogueError

    target = source
    if not _establishment.is_str_keyed_mapping(payload):
        raise IvaCatalogueError(f"{target}: the country-name vocabulary is not a table")

    countries = payload.get("country", ())
    if not _establishment.is_object_list(countries):
        raise IvaCatalogueError(f"{target}: the country-name vocabulary carries a malformed country table")

    resolved: dict[str, str] = {}
    alpha3_by_code: dict[str, str] = {}
    for record in countries:
        if not _establishment.is_str_keyed_mapping(record):
            raise IvaCatalogueError(f"{target}: country record is not a table: {record!r}")
        code = str(record.get("code", "")).strip().upper()
        if len(code) != _ALPHA2_LENGTH or not code.isalpha():
            raise IvaCatalogueError(f"{target}: country record names no alpha-2 code: {record!r}")
        alpha3 = str(record.get("alpha3", "")).strip().upper()
        if len(alpha3) != _ALPHA3_LENGTH or not alpha3.isalpha():
            raise IvaCatalogueError(
                f"{target}: country {code} names no alpha-3 code; the column is required, because an "
                f"absent correspondence reads downstream as a document stating no country at all",
            )
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
    if not resolved:
        raise IvaCatalogueError(f"{target}: the country-name vocabulary carries no alpha-3 correspondence")
    return resolved
