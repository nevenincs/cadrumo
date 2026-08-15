"""Structural gate: a dict-shaped locale-key registry is scanner-visible AND named as one.

A fifth concealment shape, distinct from the four :mod:`locales._ast_scanner`
already documents: a dict literal mapping arbitrary runtime tokens to
translation keys, declared under a constant name that carries no
``_LOCALE_KEY``/``_LOCALE_KEYS`` suffix, read through a LOWERCASE local
variable (``local = SOME_DICT.get(token)``; ``tr(local)``) rather than a
literal call site. This is invisible to BOTH existing resolvers at once: the
declaration-side scanner (:func:`locales._ast_scanner._extract_locale_constant_keys`)
only trusted a dict whose OWN NAME carried the suffix, and the call-site
naming gate (:func:`locales._ast_scanner.tr_constant_naming_violations_in_tree`)
explicitly excludes a lowercase argument as a genuinely dynamic runtime value
-- which is exactly what ``local`` looks like at the call site, even though
the dict feeding it is a fully static literal.

A commit that renamed the operation supervisor's lease mechanics
(``5a6fcd09e4``) orphaned exactly this shape in
``adapters/inbound/tui/_status_screen.py``: three ``flows.status.profiles.status.*``
keys were dropped from a renamed, still-unsuffixed dict with no signal from
any gate.

Two mechanisms close this:

* Key DISCOVERY (:func:`locales._ast_scanner._extract_locale_constant_keys`,
  reached through the public :func:`locales._ast_scanner.scan_source_tree` /
  :func:`locales._ast_scanner.scan_source_text`) now also recognizes a dict
  literal SHAPED as a locale-key registry (every value dotted-key-shaped) AND
  actually READ into a recognized translator sink, regardless of what its
  target is named. This is what makes such a dict's keys visible to the
  parity/orphan audit and to the co-landing gate without requiring any
  rename first.
* A naming HAZARD gate (:func:`locales._ast_scanner.find_dict_constant_naming_violations`),
  this module's primary subject, flags a module-level dict that IS
  flow-confirmed as a locale-key registry but still carries no suffix, so a
  human renames it into the exact contract the call-site gate already
  enforces.

Flow confirmation -- not shape alone -- is what keeps this gate honest: this
codebase also carries several same-shaped dicts (every value a dotted-key
string) that are NOT locale-key registries at all -- a casilla-to-casilla
reconciliation map, a ``Notice.code`` machine-routing table keyed by an
enum -- and shape alone would have flagged all of them. Only a dict actually
read into ``tr()``/``t()``, ``ValidationVerdict.failed(...)``, an
``*Error``/``*Exception`` constructor, or a translation-key kwarg, is
treated as a locale-key registry.
"""

from __future__ import annotations

import ast

import pytest

from .._ast_scanner import (
    _extract_locale_constant_keys,
    dict_constant_naming_violations_in_tree,
    find_dict_constant_naming_violations,
    scan_source_tree,
)
from .._paths import SRC_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = SRC_DIR

# The exact historical shape ``5a6fcd09e4`` orphaned: a dict constant without
# the required suffix, read through a lowercase local into ``tr()``.
_HISTORICAL_SHAPE = (
    "from cadrumo.core.i18n import tr\n"
    "\n"
    "_PROFILE_STATUS_KEYS = {\n"
    '    "active": "flows.status.profiles.status.active",\n'
    '    "setup_incomplete": "flows.status.profiles.status.setup_incomplete",\n'
    '    "tombstoned": "flows.status.profiles.status.tombstoned",\n'
    "}\n"
    "\n"
    "\n"
    "def render(row_status: str) -> str:\n"
    "    status_key = _PROFILE_STATUS_KEYS.get(row_status)\n"
    "    if status_key is not None:\n"
    "        return tr(status_key)\n"
    '    return tr("flows.status.profiles.status.unknown")\n'
)


def test_no_dict_constant_naming_violations_repo_wide() -> None:
    """Every production locale-key dict registry is named per the same contract.

    Real-behavior gate: walks the actual ``src/cadrumo`` tree (not a fixture)
    and fails loudly, naming every offending ``path:line: 'CONSTANT'`` site.
    """
    violations = find_dict_constant_naming_violations(_SRC_ROOT)

    assert violations == [], (
        "dict-literal locale-key registr(y/ies) without the required "
        "_LOCALE_KEY/_LOCALE_KEYS suffix, making the key set invisible to the "
        "locale coverage/parity scanners before this change and structurally "
        "unnamed as a registry now:\n" + "\n".join(violations)
    )


def test_rule_fires_on_the_exact_historical_orphaning_shape() -> None:
    """Non-tautology proof: replays the real ``5a6fcd09e4`` defect shape.

    A dict constant without the suffix, read through a lowercase local
    variable into ``tr(...)`` -- precisely the shape that orphaned three keys
    invisibly in production. The detector must fire on the DECLARATION.
    """
    tree = ast.parse(_HISTORICAL_SHAPE)

    violations = list(dict_constant_naming_violations_in_tree(tree))

    assert violations == [(3, "_PROFILE_STATUS_KEYS")]


def test_discovery_now_resolves_the_historical_shape_without_a_rename() -> None:
    """Non-tautology proof: the concealed keys are discoverable BEFORE any rename.

    Key discovery does not depend on the naming-hazard gate being fixed
    first: :func:`scan_source_tree`'s underlying resolver already recognizes
    the un-suffixed, flow-confirmed dict by shape and usage.
    """
    tree = ast.parse(_HISTORICAL_SHAPE)

    keys = _extract_locale_constant_keys(tree)

    assert {
        "flows.status.profiles.status.active",
        "flows.status.profiles.status.setup_incomplete",
        "flows.status.profiles.status.tombstoned",
    } <= keys


def test_rule_passes_on_a_correctly_suffixed_dict_registry() -> None:
    """Anti-false-positive proof: the compliant shape stays green.

    A dict whose target name ends in the required suffix is exactly the
    shape the pre-existing declaration-side scanner already resolved by
    name, so it must not additionally trip this gate.
    """
    tree = ast.parse(
        "from cadrumo.core.i18n import tr\n"
        "\n"
        "_PROFILE_STATUS_LOCALE_KEYS = {\n"
        '    "active": "flows.status.profiles.status.active",\n'
        '    "tombstoned": "flows.status.profiles.status.tombstoned",\n'
        "}\n"
        "\n"
        "\n"
        "def render(row_status: str) -> str:\n"
        "    key = _PROFILE_STATUS_LOCALE_KEYS.get(row_status)\n"
        '    return tr(key) if key is not None else tr("flows.status.profiles.status.unknown")\n',
    )

    assert list(dict_constant_naming_violations_in_tree(tree)) == []


def test_rule_ignores_a_same_shaped_dict_that_never_reaches_the_translator() -> None:
    """Anti-false-positive proof: shape alone is not enough.

    Mirrors a REAL shape this codebase carries: a dict mapping one
    dotted-namespaced casilla id to another, read via ``.get(...)`` into a
    plain local variable that is returned directly -- never passed to
    ``tr()``/``t()``, ``failed(...)``, an ``*Error`` constructor, or a
    translation-key kwarg. Flagging this for a locale-key rename would be a
    false positive against an unrelated domain that merely shares the
    dict-of-dotted-strings shape.
    """
    tree = ast.parse(
        "_RECONCILIATION_ANNUAL_CASILLA_BY_SOURCE = {\n"
        '    "iva.cuota-devengada-total": "iva.anual.cuota-devengada-total",\n'
        '    "iva.resultado-regimen-general": "iva.anual.resultado-regimen-general",\n'
        "}\n"
        "\n"
        "\n"
        "def annual_casilla_for(source_casilla_id: str) -> str | None:\n"
        "    return _RECONCILIATION_ANNUAL_CASILLA_BY_SOURCE.get(source_casilla_id)\n",
    )

    assert list(dict_constant_naming_violations_in_tree(tree)) == []


def test_discovery_ignores_a_same_shaped_dict_that_never_reaches_the_translator() -> None:
    """Anti-false-positive proof for discovery: the unrelated map contributes no fake keys.

    If shape alone drove discovery, the casilla-reconciliation map's values
    would be reported as "live locale keys" that no catalogue carries,
    corrupting the parity audit with false missing-key findings.
    """
    tree = ast.parse(
        "_RECONCILIATION_ANNUAL_CASILLA_BY_SOURCE = {\n"
        '    "iva.cuota-devengada-total": "iva.anual.cuota-devengada-total",\n'
        '    "iva.resultado-regimen-general": "iva.anual.resultado-regimen-general",\n'
        "}\n"
        "\n"
        "\n"
        "def annual_casilla_for(source_casilla_id: str) -> str | None:\n"
        "    return _RECONCILIATION_ANNUAL_CASILLA_BY_SOURCE.get(source_casilla_id)\n",
    )

    from .._ast_scanner import _extract_locale_constant_keys  # noqa: PLC0415 - internal-only assertion target

    assert _extract_locale_constant_keys(tree) == set()


def test_rule_ignores_a_notice_code_routing_table() -> None:
    """Anti-false-positive proof: a ``Notice.code`` machine-routing table is not a locale-key dict.

    Mirrors a second REAL shape this codebase carries deliberately: a dict
    mapping an enum member to a dotted ``Notice.code`` string, fed to
    ``Notice(code=...)`` -- a JSON-consumer routing key, never a translator
    argument. The operator-facing message for the same notice is resolved
    through a SEPARATE literal ``tr(...)`` call site elsewhere, by design
    (recorded in-repo: table lookups are kept out of ``tr()`` call sites
    specifically because they would be scanner-invisible).
    """
    tree = ast.parse(
        "from dataclasses import dataclass\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class Notice:\n"
        "    code: str\n"
        "    message: str\n"
        "\n"
        "\n"
        "_OUTCOME_NOTICE_CODE = {\n"
        '    "rate_inferred": "ledger.evidence.confirm.category_rate_inferred",\n'
        '    "contradicted": "ledger.evidence.confirm.category_contradicted",\n'
        "}\n"
        "\n"
        "\n"
        "def build_notice(outcome: str, message: str) -> Notice:\n"
        "    code = _OUTCOME_NOTICE_CODE[outcome]\n"
        "    return Notice(code=code, message=message)\n",
    )

    assert list(dict_constant_naming_violations_in_tree(tree)) == []


def test_rule_ignores_a_local_scope_dict_even_when_flow_confirmed() -> None:
    """A dict declared and consumed within one function is out of scope.

    Only a MODULE-LEVEL declaration is flagged: a dict literal declared and
    read into ``tr()`` a few lines later, inside one function, is visibly
    connected to its own use at a glance -- not the "invisible at a
    distance" hazard a module constant referenced from elsewhere in the
    file represents.
    """
    tree = ast.parse(
        "from cadrumo.core.i18n import tr\n"
        "\n"
        "\n"
        "def label_for(token: str) -> str:\n"
        "    route_keys = {\n"
        '        "qr": "flows.manager.action.auth_clave_movil_route_qr",\n'
        '        "app_request": "flows.manager.action.auth_clave_movil_route_app_request",\n'
        "    }\n"
        "    return tr(route_keys[token])\n",
    )

    assert list(dict_constant_naming_violations_in_tree(tree)) == []


def test_rule_ignores_an_unshaped_dict_with_one_non_dotted_value() -> None:
    """A dict with even one non-matching value is not treated as a locale-key mapping.

    Keeps the false-positive rate low against an ordinary lookup table that
    happens to carry one dotted-looking string among otherwise unrelated
    values.
    """
    tree = ast.parse(
        "from cadrumo.core.i18n import tr\n"
        "\n"
        "_MIXED_TABLE = {\n"
        '    "a": "cli.app.some.key",\n'
        '    "b": "not-a-dotted-key",\n'
        "}\n"
        "\n"
        "\n"
        "def render(token: str) -> str:\n"
        "    return tr(_MIXED_TABLE[token])\n",
    )

    assert list(dict_constant_naming_violations_in_tree(tree)) == []


def test_rule_fires_through_the_failed_verdict_factory_indirection() -> None:
    """The rule confirms flow into ``ValidationVerdict.failed(...)``, not only ``tr()``.

    Mirrors a REAL shape this codebase carries: a dict of check-token to
    message-key, read through a lowercase local into the flow substrate's
    verdict factory rather than a direct ``tr()`` call.
    """
    tree = ast.parse(
        "class ValidationVerdict:\n"
        "    @classmethod\n"
        "    def failed(cls, message_key, **kwargs):\n"
        "        return cls()\n"
        "\n"
        "\n"
        "_CHECK_MESSAGE_KEYS = {\n"
        '    "impatriado_requires_start_date": "wizard.setup.verifier.impatriado_requires_start_date",\n'
        "}\n"
        "\n"
        "\n"
        "def verdict_for(check: str):\n"
        '    message_key = _CHECK_MESSAGE_KEYS.get(check, "errors.refused.refused_user_profile_validation")\n'
        "    return ValidationVerdict.failed(message_key, check=check)\n",
    )

    violations = list(dict_constant_naming_violations_in_tree(tree))

    assert violations == [(7, "_CHECK_MESSAGE_KEYS")]


def test_repo_real_historical_site_is_scanner_visible_end_to_end() -> None:
    """Sanity check against the ACTUAL repository: the residual live site round-trips.

    ``adapters/inbound/tui/_status_screen.py`` still carries the
    ``5a6fcd09e4`` shape's direct descendant (``_PROFILE_SETUP_STATE_KEYS``)
    at HEAD. This is not a vacuous "nothing in the tree matches" pass: the
    repo-wide keys this dict declares are genuinely discovered by
    :func:`scan_source_tree`, proving the fix reaches the real file, not
    only synthetic fixtures.
    """
    keys = scan_source_tree(_SRC_ROOT)

    assert "flows.status.profiles.status.complete" in keys
    assert "flows.status.profiles.status.incomplete" in keys
