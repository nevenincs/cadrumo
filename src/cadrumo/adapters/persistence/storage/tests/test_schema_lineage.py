"""Schema-lineage policy: version ceilings and the upgrade-chain gate.

The completeness gate here is the anti-stranding tripwire: every registered secure-object
namespace must carry a complete upgrade chain from the durability floor to
its current declared ``schema_version``. Today every namespace sits at
version 1 and the chain is vacuously complete; the moment a namespace bumps
its version without landing the one-hop upgrader in the same change, this
gate goes red instead of years-old rows going silently unreadable.
"""

from __future__ import annotations

import ast

import annotated_types
import pytest

from .....core import COMPATIBILITY_REGIME, RELEASED_FORMAT_FLOORS, expected_floor
from .....tests._inventory import production_python_files, repo_relative
from .._namespace_registry import STORAGE_NAMESPACE_REGISTRY
from .._schema_lineage import (
    SECURE_OBJECT_DURABILITY_FLOOR,
    deregister_secure_object_schema_upgrader,
    ensure_schema_version_readable,
    missing_upgrade_hops,
    register_secure_object_schema_upgrader,
    upgrade_secure_object_payload,
)
from ..envelope import Envelope
from ..errors import EnvelopeVersionError, StorageValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo-test.lineage.policy"


def test_floor_matches_the_regime_expected_floor() -> None:
    """The secure-object floor tracks the regime-switched compatibility policy.

    The current secure-object version is the highest declared namespace
    ``schema_version``. While ``PRE_RELEASE`` (today) the expected floor IS
    that current version — the floors-chase-current pre-release posture — so
    every stored row sits at or above the floor with no pre-current shape to
    tolerate. Post-flip the expected floor becomes the frozen released value
    and this assertion demands the floor stay pinned there.
    """
    current = max(
        (definition.schema_version for definition in STORAGE_NAMESPACE_REGISTRY.namespaces),
        default=SECURE_OBJECT_DURABILITY_FLOOR,
    )
    assert (
        expected_floor(
            COMPATIBILITY_REGIME,
            "secure_object",
            current,
            RELEASED_FORMAT_FLOORS,
        )
        == SECURE_OBJECT_DURABILITY_FLOOR
    )


def test_every_registered_namespace_upgrade_chain_is_complete() -> None:
    """A namespace version bump without its registered upgrader fails here."""
    incomplete = {
        definition.namespace: missing_upgrade_hops(
            namespace=definition.namespace,
            from_version=SECURE_OBJECT_DURABILITY_FLOOR,
            to_version=definition.schema_version,
        )
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces
    }
    broken = {namespace: hops for namespace, hops in incomplete.items() if hops}
    assert broken == {}, (
        "secure-object namespaces declare a schema_version without a complete "
        f"durability-floor upgrade chain: {broken}; register the missing one-hop "
        "upgrader(s) in the same change as the version bump"
    )


def test_future_schema_version_is_refused_as_from_future() -> None:
    with pytest.raises(EnvelopeVersionError) as raised:
        ensure_schema_version_readable(
            namespace=_NAMESPACE,
            schema_version=2,
            current_version=1,
        )
    assert raised.value.translated_message == "errors.storage.namespace.schema_version_from_future"
    assert raised.value.context == {
        "namespace": _NAMESPACE,
        "schema_version": 2,
        "expected": 1,
    }


def test_older_version_with_incomplete_chain_names_the_first_missing_hop() -> None:
    upgraders = {(_NAMESPACE, 2): lambda payload: payload}
    with pytest.raises(EnvelopeVersionError) as raised:
        ensure_schema_version_readable(
            namespace=_NAMESPACE,
            schema_version=1,
            current_version=3,
            upgraders=upgraders,
        )
    assert raised.value.translated_message == "errors.storage.namespace.schema_upgrade_path_missing"
    assert raised.value.context == {
        "namespace": _NAMESPACE,
        "schema_version": 1,
        "expected": 3,
        "missing_from_version": 1,
    }


def test_chain_upgrade_applies_registered_hops_in_order() -> None:
    upgraders = {
        (_NAMESPACE, 1): lambda payload: payload + b"|1to2",
        (_NAMESPACE, 2): lambda payload: payload + b"|2to3",
    }
    upgraded = upgrade_secure_object_payload(
        b"written-at-v1",
        namespace=_NAMESPACE,
        from_version=1,
        to_version=3,
        upgraders=upgraders,
    )
    assert upgraded == b"written-at-v1|1to2|2to3"


def test_equal_versions_return_the_payload_unchanged() -> None:
    payload = b"already-current"
    assert (
        upgrade_secure_object_payload(
            payload,
            namespace=_NAMESPACE,
            from_version=1,
            to_version=1,
        )
        is payload
    )


def test_registration_is_single_writer_per_hop_and_reversible() -> None:
    register_secure_object_schema_upgrader(_NAMESPACE, 1, lambda payload: payload)
    try:
        assert (
            missing_upgrade_hops(
                namespace=_NAMESPACE,
                from_version=1,
                to_version=2,
            )
            == ()
        )
        with pytest.raises(StorageValidationError):
            register_secure_object_schema_upgrader(_NAMESPACE, 1, lambda payload: payload)
    finally:
        deregister_secure_object_schema_upgrader(_NAMESPACE, 1)
    assert missing_upgrade_hops(
        namespace=_NAMESPACE,
        from_version=1,
        to_version=2,
    ) == (1,)


# --- The two facts the inner-envelope vacuity proof rests on -------------------
#
# Tightening the twenty inner-envelope read paths from an inequality to an
# equality was behaviour-identical only because two independent facts happened
# to hold together: every read path compares against its own namespace's
# DECLARED schema_version, and the inner envelope field cannot represent a
# version below the durability floor. With both, the below-current region is
# empty and `> N` and `!= N` are the same predicate. Neither fact was pinned
# anywhere, so both were coincidence rather than invariant. These pin them.
#
# Both are deliberately RELATIONS, not literals. A gate asserting "every
# namespace equals 1" would red on a legitimate per-namespace bump — the wrong
# reason — and a durability floor that moves post-flip must carry the field
# floor with it rather than trip an assertion.

_PREDICATE_NAME = "inner_envelope_version_is_current"


def test_inner_envelope_field_floor_tracks_the_durability_floor() -> None:
    """The inner envelope cannot represent a version below the durability floor.

    This is the second half of the vacuity argument. The floor and the field
    constraint are declared in different modules and could drift apart; if they
    ever do, the below-current region stops being empty and the equality check
    starts refusing shapes the ceiling used to accept. Asserted as a relation to
    :data:`SECURE_OBJECT_DURABILITY_FLOOR` rather than against a bare ``1``.
    """
    constraints = [
        item for item in Envelope.model_fields["schema_version"].metadata if isinstance(item, annotated_types.Ge)
    ]
    assert len(constraints) == 1, (
        f"Envelope.schema_version must carry exactly one lower-bound constraint; found {constraints}"
    )
    assert constraints[0].ge == SECURE_OBJECT_DURABILITY_FLOOR, (
        "Envelope.schema_version's floor and the secure-object durability floor are the same "
        "boundary seen from two sides: the lowest representable inner stamp, and the lowest "
        "version every read path keeps readable. They must move together."
    )


def _module_level_version_constants(tree: ast.AST) -> set[str]:
    """Return module-level names assigned from some ``<...>.schema_version``."""
    derived: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if isinstance(value, ast.Attribute) and value.attr == "schema_version":
            derived.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return derived


def _undelegated_version_arguments(source: str) -> list[int]:
    """Return line numbers of predicate calls whose expected version is not namespace-derived."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    derived = _module_level_version_constants(tree)
    offenders: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name != _PREDICATE_NAME or len(node.args) < 2:
            continue
        expected = node.args[1]
        if isinstance(expected, ast.Attribute) and expected.attr == "schema_version":
            continue
        if isinstance(expected, ast.Name) and expected.id in derived:
            continue
        offenders.append(node.lineno)
    return sorted(offenders)


def test_every_reader_compares_against_its_namespace_declared_version() -> None:
    """Each read path's expected version is derived from a namespace definition.

    This is the first half of the vacuity argument, and it must be pinned
    STRUCTURALLY rather than by value. Every reader currently defines its
    constant as ``<NAMESPACE>.schema_version``, so asserting that the constant
    equals the namespace's version would compare a value against its own
    definition and pass no matter what either held — a tautology. What is
    genuinely assertable is the DERIVATION: a reader that restated a literal
    would decouple from the registry and silently outlive a bump, and that is
    what this refuses.
    """
    offenders: list[str] = []
    for path in production_python_files():
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _PREDICATE_NAME not in source:
            continue
        offenders.extend(f"{repo_relative(path)}:{lineno}" for lineno in _undelegated_version_arguments(source))
    assert offenders == [], (
        "every inner-envelope read path must take its expected version from its own "
        "SecureObjectNamespaceDefinition.schema_version, never a restated literal: a literal "
        f"decouples the reader from the registry and survives a namespace bump silently; offenders: {offenders}"
    )


_LITERAL_EXPECTED_VERSION = """
from ..storage import inner_envelope_version_is_current

def load(envelope):
    return inner_envelope_version_is_current(envelope.schema_version, 1)
"""

_DERIVED_VIA_MODULE_CONSTANT = """
from ..storage import CATALOGUE_NAMESPACE, inner_envelope_version_is_current

_CATALOGUE_VERSION = CATALOGUE_NAMESPACE.schema_version

def load(envelope):
    return inner_envelope_version_is_current(envelope.schema_version, _CATALOGUE_VERSION)
"""

_DERIVED_INLINE = """
from ..storage import CATALOGUE_NAMESPACE, inner_envelope_version_is_current

def load(envelope):
    return inner_envelope_version_is_current(envelope.schema_version, CATALOGUE_NAMESPACE.schema_version)
"""


def test_derivation_check_flags_a_restated_literal() -> None:
    """Positive control: a hardcoded expected version is the drift this refuses."""
    assert _undelegated_version_arguments(_LITERAL_EXPECTED_VERSION) == [5]


def test_derivation_check_accepts_a_namespace_derived_module_constant() -> None:
    """Negative control: the shape every real reader uses."""
    assert _undelegated_version_arguments(_DERIVED_VIA_MODULE_CONSTANT) == []


def test_derivation_check_accepts_an_inline_namespace_attribute() -> None:
    """Negative control: the two readers that pass the namespace attribute directly."""
    assert _undelegated_version_arguments(_DERIVED_INLINE) == []


def test_the_derivation_check_actually_reaches_the_read_paths() -> None:
    """The scan must find the real predicate call sites, not silently zero.

    A clean result from the check above is only evidence if it inspected
    something. Twenty call sites were swept onto the predicate; this pins that
    the scan still sees them, so the gate cannot pass by scanning nothing.
    """
    call_sites = 0
    for path in production_python_files():
        source = path.read_text(encoding="utf-8", errors="replace")
        if _PREDICATE_NAME not in source:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
                if name == _PREDICATE_NAME:
                    call_sites += 1
    assert call_sites >= 20, (
        f"expected the swept inner-envelope read paths to remain on the predicate; found {call_sites} call sites"
    )
