"""Scope intersection and narrowing against a pairwise oracle, with their cost pinned."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import product
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessEvaluationContext,
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_policy import intersect_scopes, intersect_scopes_within, scope_is_subset
from cadrumo.application.user_profile.operation_access_policy import evaluate_operation_access, operation_scope_refusal
from cadrumo.application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.period import Period
from cadrumo_client.contracts.access_refusals import AccessAllowed, AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    AuthorityState,
    Availability,
    DisclosureCategory,
    DisclosureCategoryGrant,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)
DESTINATIONS = tuple(UUID(int=index) for index in range(1, 4))
PROJECTIONS = ("profile.values.v1", "tax.values.v1", "operation.status.v1")
OPERATIONS = ("profile.read", "profile.write", "modelo.calculate", "modelo.export", "ledger.read", "ledger.write")
PERIODS = tuple(Period.from_year_and_code(year, code) for year in (2025, 2026) for code in ("1T", "2T", "3T", "4T"))
PERMISSIONS = tuple(
    DisclosurePermission(destination_id=destination, projection_id=projection, category=category)
    for destination, projection, category in product(DESTINATIONS, PROJECTIONS, DisclosureCategory)
)
GRANTS = tuple(
    DisclosureCategoryGrant(destination_id=destination, category=category)
    for destination, category in product(DESTINATIONS, DisclosureCategory)
)


class Draws:
    """Deterministic draws from a seed, so every run checks the same generated cases."""

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._count = 0

    def randint(self, low: int, high: int) -> int:
        self._count += 1
        digest = hashlib.sha256(f"{self._seed}:{self._count}".encode()).digest()
        return low + int.from_bytes(digest[:8]) % (high - low + 1)

    def random(self) -> float:
        return self.randint(0, 999) / 1000

    def choice[T](self, pool: tuple[T, ...]) -> T:
        return pool[self.randint(0, len(pool) - 1)]

    def sample[T](self, pool: tuple[T, ...], count: int) -> list[T]:
        items = list(pool)
        for index in range(count):
            swap = self.randint(index, len(items) - 1)
            items[index], items[swap] = items[swap], items[index]
        return items[:count]


def oracle_intersection(scopes: tuple[AccessScope, ...]) -> AccessScope:
    """Ask every scope about every listed item, as the vocabulary defines consent."""
    if not scopes:
        return AccessScope(
            operations=frozenset(),
            actions=frozenset(),
            disclosures=frozenset(),
            periods=frozenset(),
            allow_period_independent=False,
            allow_delegation=False,
        )
    actions = frozenset(AccessAction)
    categories = frozenset(GRANTS)
    periods: frozenset[Period] | None = None
    for scope in scopes:
        actions &= scope.actions
        categories &= scope.disclosure_categories
        if scope.periods is not None:
            periods = scope.periods if periods is None else periods & scope.periods
    listed = [item for scope in scopes for item in scope.disclosures]
    named = [item for scope in scopes for item in scope.operations]
    return AccessScope(
        operations=frozenset(item for item in named if all(scope.permits(item) for scope in scopes)),
        actions=actions,
        disclosures=frozenset(item for item in listed if all(scope.discloses(item) for scope in scopes)),
        periods=periods,
        allow_period_independent=all(scope.allow_period_independent for scope in scopes),
        allow_delegation=all(scope.allow_delegation for scope in scopes),
        disclosure_categories=categories,
        allow_changes_records=all(scope.allow_changes_records for scope in scopes),
        allow_network=all(scope.allow_network for scope in scopes),
    )


def oracle_subset(child: AccessScope, parent: AccessScope) -> bool:
    """Ask the parent about every item the child holds."""
    return (
        all(parent.permits(item) for item in child.operations)
        and all(item in parent.actions for item in child.actions)
        and all(parent.discloses(item) for item in child.disclosures)
        and all(item in parent.disclosure_categories for item in child.disclosure_categories)
        and (parent.periods is None or (child.periods is not None and all(p in parent.periods for p in child.periods)))
        and (parent.allow_period_independent or not child.allow_period_independent)
        and (parent.allow_delegation or not child.allow_delegation)
        and (parent.allow_changes_records or not child.allow_changes_records)
        and (parent.allow_network or not child.allow_network)
    )


def changed[T: BaseModel](model: T, **updates: object) -> T:
    model_type = model.__class__
    return model_type.model_validate({**{name: getattr(model, name) for name in model_type.model_fields}, **updates})


def equal_copy(scope: AccessScope) -> AccessScope:
    """The same scope built from equal, distinct item instances, as a decoded record holds them."""
    return changed(
        scope,
        disclosures=frozenset(DisclosurePermission(**item.model_dump()) for item in scope.disclosures),
        disclosure_categories=frozenset(
            DisclosureCategoryGrant(**item.model_dump()) for item in scope.disclosure_categories
        ),
    )


def some[T](rng: Draws, pool: tuple[T, ...]) -> frozenset[T]:
    return frozenset(rng.sample(pool, rng.randint(0, len(pool))))


def random_scope(rng: Draws) -> AccessScope:
    return AccessScope(
        operations=some(rng, OPERATIONS),
        actions=some(rng, tuple(AccessAction)),
        disclosures=some(rng, PERMISSIONS),
        periods=None if rng.random() < 0.3 else some(rng, PERIODS),
        allow_period_independent=rng.random() < 0.6,
        allow_delegation=rng.random() < 0.6,
        disclosure_categories=frozenset() if rng.random() < 0.4 else some(rng, GRANTS),
        allow_changes_records=rng.random() < 0.7,
        allow_network=rng.random() < 0.7,
    )


def narrowed(rng: Draws, parent: AccessScope) -> AccessScope:
    """A scope inside ``parent``: listed items it holds plus some its category grants cover."""
    covered = tuple(item for item in PERMISSIONS if parent.discloses(item))
    return AccessScope(
        operations=some(rng, tuple(parent.operations)),
        actions=some(rng, tuple(parent.actions)),
        disclosures=some(rng, covered),
        periods=some(rng, PERIODS if parent.periods is None else tuple(parent.periods)),
        allow_period_independent=parent.allow_period_independent and rng.random() < 0.5,
        allow_delegation=parent.allow_delegation and rng.random() < 0.5,
        disclosure_categories=some(rng, tuple(parent.disclosure_categories)),
        allow_changes_records=parent.allow_changes_records and rng.random() < 0.5,
        allow_network=parent.allow_network and rng.random() < 0.5,
    )


def disjoint_pair(rng: Draws) -> tuple[AccessScope, AccessScope]:
    first, second = random_scope(rng), random_scope(rng)
    return (
        changed(
            first,
            operations=first.operations & frozenset(OPERATIONS[::2]),
            disclosures=first.disclosures & frozenset(PERMISSIONS[::2]),
            disclosure_categories=frozenset(),
        ),
        changed(
            second,
            operations=second.operations & frozenset(OPERATIONS[1::2]),
            disclosures=second.disclosures & frozenset(PERMISSIONS[1::2]),
            disclosure_categories=frozenset(),
        ),
    )


def scope_chains(seed: int) -> Iterator[tuple[AccessScope, ...]]:
    rng = Draws(seed)
    yield ()
    for _ in range(40):
        base = random_scope(rng)
        yield (base,)
        yield (base, base)
        yield (base, equal_copy(base))
        yield disjoint_pair(rng)
        child = narrowed(rng, base)
        yield (base, child)
        yield (child, narrowed(rng, child), base)
        yield tuple(random_scope(rng) for _ in range(rng.randint(2, 5)))
        empty = changed(base, disclosures=frozenset(), disclosure_categories=frozenset(), operations=frozenset())
        yield (empty, base)


@pytest.mark.parametrize("seed", range(4))
def test_intersection_matches_the_pairwise_oracle(seed: int) -> None:
    for scopes in scope_chains(seed):
        assert intersect_scopes(scopes) == oracle_intersection(scopes)


@pytest.mark.parametrize("seed", range(4))
def test_bounded_intersection_keeps_exactly_the_named_part_of_the_whole(seed: int) -> None:
    rng = Draws(seed)
    for scopes in scope_chains(seed):
        operations = some(rng, (*OPERATIONS, "unlisted.operation"))
        disclosures = some(rng, PERMISSIONS)
        whole = oracle_intersection(scopes)
        expected = changed(whole, operations=whole.operations & operations, disclosures=whole.disclosures & disclosures)
        assert intersect_scopes_within(scopes, operations=operations, disclosures=disclosures) == expected


@pytest.mark.parametrize("seed", range(4))
def test_narrowing_matches_the_pairwise_oracle(seed: int) -> None:
    rng = Draws(seed)
    for scopes in scope_chains(seed):
        for child, parent in product(scopes, repeat=2):
            assert scope_is_subset(child, parent) is oracle_subset(child, parent)
        if scopes:
            parent = scopes[0]
            child = narrowed(rng, parent)
            assert scope_is_subset(child, parent)
            assert scope_is_subset(equal_copy(child), parent)


def test_a_category_grant_alone_never_adds_an_unlisted_disclosure() -> None:
    grant = GRANTS[0]
    covered = next(item for item in PERMISSIONS if grant.covers(item))
    only_categories = AccessScope(
        operations=frozenset(),
        actions=frozenset(),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=True,
        disclosure_categories=frozenset({grant}),
    )
    assert intersect_scopes((only_categories, only_categories)).disclosures == frozenset()
    bounded = intersect_scopes_within(
        (only_categories, only_categories), operations=frozenset(), disclosures=frozenset({covered})
    )
    assert bounded.disclosures == frozenset()
    listing = changed(only_categories, disclosures=frozenset({covered}), disclosure_categories=frozenset())
    assert intersect_scopes((only_categories, listing)).disclosures == frozenset({covered})


@pytest.mark.parametrize("seed", range(4))
def test_operation_refusal_reads_the_bounded_scope_as_the_whole_one(seed: int) -> None:
    rng = Draws(seed)
    digest = sha256_hex(b"synthetic operation contract")
    for scopes in scope_chains(seed):
        destination = rng.choice(DESTINATIONS)
        periods = some(rng, PERIODS)
        request = OperationAccessRequest(
            profile_id=uuid4(),
            definition_id=rng.choice(OPERATIONS),
            action=rng.choice(tuple(AccessAction)),
            frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
            periods=periods,
            period_independent=not periods,
            destination_id=destination,
        )
        policy = OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=digest,
            actions=some(rng, tuple(AccessAction)),
            disclosures=frozenset(rng.sample(PERMISSIONS, rng.randint(0, 3))),
            periods=None if rng.random() < 0.5 else some(rng, PERIODS),
            allow_period_independent=rng.random() < 0.7,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_all_periods=rng.random() < 0.2,
        )
        bounded = intersect_scopes_within(
            scopes, operations=frozenset({request.definition_id}), disclosures=policy.disclosures
        )
        whole = oracle_intersection(scopes)
        assert operation_scope_refusal(request=request, policy=policy, scope=bounded) == operation_scope_refusal(
            request=request, policy=policy, scope=whole
        )


@pytest.fixture
def item_work(monkeypatch: pytest.MonkeyPatch) -> Counter[str]:
    """Count the Python-level work done per disclosure item: hashing, equality and category checks."""
    counts: Counter[str] = Counter()

    def counted[**P, R](name: str, original: Callable[P, R]) -> Callable[P, R]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            counts[name] += 1
            return original(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(DisclosurePermission, "__hash__", counted("hash", DisclosurePermission.__hash__))
    monkeypatch.setattr(DisclosurePermission, "__eq__", counted("eq", DisclosurePermission.__eq__))
    monkeypatch.setattr(DisclosureCategoryGrant, "covers", counted("covers", DisclosureCategoryGrant.covers))
    return counts


def listed_scope(size: int, *, categories: frozenset[DisclosureCategoryGrant] = frozenset()) -> AccessScope:
    return AccessScope(
        operations=frozenset({PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID}),
        actions=frozenset(AccessAction),
        disclosures=frozenset(
            DisclosurePermission(
                destination_id=DESTINATIONS[index % len(DESTINATIONS)],
                projection_id=f"projection.n{index}",
                category=DisclosureCategory.PROFILE_VALUES,
            )
            for index in range(size)
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=True,
        disclosure_categories=categories,
    )


def test_intersection_work_per_item_does_not_grow_with_the_number_of_scopes(item_work: Counter[str]) -> None:
    listed = listed_scope(300)
    covering = changed(listed, disclosures=frozenset(), disclosure_categories=frozenset(GRANTS))
    measured = []
    for count in (2, 8):
        item_work.clear()
        result = intersect_scopes((covering, *([listed] * (count - 1))))
        assert result.disclosures == listed.disclosures
        measured.append(dict(item_work))
    # One category check per item for the covering scope and one hash to build the result:
    # asking every scope about every item grew this with the scope count.
    assert measured[0] == measured[1]
    assert measured[0]["hash"] <= len(listed.disclosures)


@dataclass(frozen=True)
class Authority:
    registry: OperationRegistry
    profile: ProfileAccessState
    grant: AutomationGrant
    key: ApiKeyRecord
    session: AccessSession
    context: AccessEvaluationContext

    def evaluate(self, request: OperationAccessRequest, policy: OperationAccessPolicy) -> object:
        return evaluate_operation_access(
            request=request,
            policy=policy,
            registry=self.registry,
            session=self.session,
            ancestors=(),
            grant=self.grant,
            key=self.key,
            profile=self.profile,
            context=self.context,
        )


def access_scenario(size: int) -> Authority:
    definitions = build_user_profile_operation_definitions()
    registry = OperationRegistry(
        definitions=definitions, public_registrations=build_user_profile_operation_registrations(definitions)
    )
    binding = ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )
    scope = listed_scope(size, categories=frozenset(GRANTS))
    profile = ProfileAccessState(
        binding=binding,
        lock_generation=0,
        globally_locked=False,
        automation_enabled=True,
        scope=scope,
        storage=Availability.AVAILABLE,
        automation_custody=Availability.AVAILABLE,
    )
    grant = AutomationGrant(
        grant_id=uuid4(),
        binding=binding,
        client_id=uuid4(),
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=scope,
        valid_from=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=364),
        unattended=True,
        allow_os_lock=True,
    )
    key = ApiKeyRecord(
        key_id=uuid4(),
        grant_id=grant.grant_id,
        binding=binding,
        generation=1,
        state=AuthorityState.ACTIVE,
        valid_from=grant.valid_from,
        expires_at=grant.expires_at,
    )
    session = AccessSession(
        session_id=uuid4(),
        binding=binding,
        profile_lock_generation=0,
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        client_id=grant.client_id,
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=changed(scope, disclosure_categories=frozenset()),
        grant_id=grant.grant_id,
        grant_generation=1,
        key_id=key.key_id,
        key_generation=1,
        issued_at=NOW,
        expires_at=NOW + ACCESS_LEASE_MAXIMUM,
        issued_monotonic=100.0,
    )
    context = AccessEvaluationContext(
        now=NOW,
        monotonic_now=100.0,
        clock_rollback_detected=False,
        runtime_boot_id=session.runtime_boot_id,
        connection_id=session.connection_id,
        authenticated_client_id=grant.client_id,
        login_contexts=(
            OsLoginContext(
                login_id="login-a",
                os_owner_id=binding.os_owner_id,
                active=True,
                lock_state=OsLockState.UNLOCKED,
                unattended=LoginEligibility.ELIGIBLE,
                credential_facilities=Availability.AVAILABLE,
            ),
        ),
        private_work_available=True,
    )
    return Authority(registry, profile, grant, key, session, context)


def access_policy(registry: OperationRegistry, disclosure: DisclosurePermission) -> OperationAccessPolicy:
    return OperationAccessPolicy(
        definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        definition_contract_digest=registry.lookup_public_contract(
            PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID
        ).definition_contract_digest,
        actions=frozenset(AccessAction),
        disclosures=frozenset({disclosure}),
        periods=None,
        allow_period_independent=True,
        backend=Availability.AVAILABLE,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
        transaction_authority_required=False,
    )


def test_operation_access_work_does_not_grow_with_the_listed_scope(item_work: Counter[str]) -> None:
    measured = []
    for size in (12, 600):
        authority = access_scenario(size)
        held = min(authority.session.scope.disclosures, key=lambda item: item.projection_id)
        request = OperationAccessRequest(
            profile_id=authority.profile.binding.profile_id,
            definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
            periods=frozenset(),
            period_independent=True,
            destination_id=held.destination_id,
        )
        unheld = DisclosurePermission(
            destination_id=held.destination_id, projection_id="projection.unheld", category=held.category
        )
        item_work.clear()
        allowed = authority.evaluate(request, access_policy(authority.registry, held))
        denied = authority.evaluate(request, access_policy(authority.registry, unheld))
        measured.append(dict(item_work))
        assert isinstance(allowed, AccessAllowed)
        assert denied == AccessDenied(code=AccessDenialCode.DISCLOSURE_DENIED)
    # Intersecting every listed item on each access grew this with the scope fifty-fold.
    assert measured[0] == measured[1]
