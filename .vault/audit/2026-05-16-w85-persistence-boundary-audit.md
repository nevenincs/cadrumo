---
tags:
  - "#audit"
  - "#w85-persistence-boundary"
date: 2026-05-16
modified: '2026-05-16'
related: []
---

# w85-persistence-boundary audit: W85 persistence-boundary identity audit

## Scope

Persistence-boundary identity audit of the W85 census-sync wave commits
landed up to 2026-05-16: CensusSnapshot (live snapshot service),
CensusSyncService (operator-facing four-verb service), CensusFactSet
(G313 sede adapter envelope), and the new census_stamped_stale_at /
census_stale_reason fields on WorkUnit. Axis question: do the save /
load surfaces in these new types meet the roundtrip-discipline
contract (real adapters, populated-non-default fixtures, anti-
tautology proof), or is there a save-drops-field / load-re-defaults-
field regression latent in the boundary?

## Findings

### CRITICAL - WorkUnit census-stale fields not covered by the canonical roundtrip fixture

src/aeat/domain/modelos/test_secure_storage_roundtrip.py:41-84 - the
_populated_work_unit fixture is the waves only strict roundtrip across
WorkUnitCatalogueRepository, documented as the anti-tautology
safeguard (every defaultable field must carry a non-default value).
The two new defaultable optional fields added in
src/aeat/domain/modelos/_work_unit.py:199-200
(census_stamped_stale_at: datetime | None = None,
census_stale_reason: _StaleReason | None = None) are not set in the
fixture. Because both default to None, a save side that silently
dropped either field would still re-default to None on load and the
strict loaded == original equality on line 109 would pass - the
exact regression aeat-roundtrip-discipline.md prohibits.

Remediation: extend _populated_work_unit to set
census_stamped_stale_at to a real UTC timestamp >= created_at and
census_stale_reason to a non-empty string (the pair must be set or
unset together per the validator at _work_unit.py:256-261). Add
explicit per-field witnesses after reload so a save-drop regression
fails loudly rather than quietly equating None == None.

### HIGH - CensusSnapshot roundtrip suite lacks the anti-tautology proof test

src/aeat/application/live/test_census_snapshot.py:161-203 does
exercise the encrypted-storage cycle with real
EphemeralMasterKeyProvider + real SQLite + a populated fact mapping.
However, the suite carries no mutate-on-disk + reload + assert
ValidationError-or-strict-inequality test (the anti-tautology
proof mandated by aeat-roundtrip-discipline.md). If
_snapshot_from_record ever silently re-defaulted a missing field,
every other roundtrip in the file would still pass.

Additionally the populated fixture leaves five defaultable fields at
their defaults: superseded_by_snapshot_id=None, discarded_at=None,
discarded_by="" (empty), discard_reason="" (empty), and the
implicit ACTIVE state. The SUPERSEDED + DISCARDED metadata triples
are only exercised through the service capture / discard verbs,
never via a fixture-built CensusSnapshot constructed with all
optional metadata pre-set.

Remediation: (a) add a test that saves a populated snapshot, mutates
the on-disk envelope JSON to drop one of census_facts / source_url /
captured_at, and asserts ValidationError (or strict inequality) on
reload; (b) extend the roundtrip fixture set with a DISCARDED
snapshot constructed directly (not via service) with all discard
metadata populated, witnessing each field after reload.

### HIGH - UserProfileFact valid_from / valid_to fields not exercised by census apply roundtrip

src/aeat/application/profile/test_census_sync.py:145-172 correctly
reloads via profiles.load("operator") and asserts both value ==
"propio" and source == CENSUS_SOURCE_TAG after the encrypted-store
cycle - the question-2 provenance-tag concern is genuinely covered.
However, UserProfileFact at src/aeat/domain/user_profile/_values.py:
93-102 carries two additional defaultable fields (valid_from: date |
None = None, valid_to: date | None = None) that census-applied facts
unconditionally leave at None. apply_census_to_profile at
src/aeat/application/profile/_census_sync.py:251-254 constructs each
UserProfileFact without populating either window field - so a save-
drops-window-field regression on the UserProfileRecord boundary is
invisible because the input fixture never carries non-default values
for those fields.

Remediation: add one census-sync roundtrip case where a pre-existing
retained fact (preserved through the stamp call) carries a populated
valid_from (and ideally valid_to), reload, and witness the window
survives the stamp-and-save cycle. Protects the orthogonal window
boundary without requiring census-applied facts themselves to carry
validity windows.

### MEDIUM - CensusFactSet is a transient parse target; future flattener will need its own roundtrip

src/aeat/adapters/outbound/aeat/sede/_census.py:51-104 defines
CensusFactSet as the typed projection of one G313 page parse. Its
only producer is parse_g313_html in the same module; its only
consumer reference site is the parser test
(src/aeat/adapters/outbound/aeat/sede/test_census_parser.py).
CensusSyncService.refresh_census at _census_sync.py:153-178 consumes
a CensusFactSource callable returning Mapping[str, str], not a
CensusFactSet. The fact-set is therefore a strict in-memory adapter
boundary value; no persistence roundtrip is currently required.

Flagged forward-looking gap: the CensusFactSet (typed Decimal, date,
bool) to Mapping[str, str] bridge required for the production
fact_source wiring is not yet implemented. The flattener will be the
silent point where typed fields can be lost on the way to the
snapshot. The _CensusFactValue = str constraint at _census.py:47 is
the boundary that will catch silent Decimal-string coercion, but
only if the wiring test exercises a populated Decimal m2 value end
to end.

Remediation: when the sede driver lands, ship the
CensusFactSet -> Mapping[str, str] flattener alongside a dedicated
test that round-trips every populated typed field through the
flatten-and-snapshot cycle and asserts no value is lost or silently
coerced.

### LOW - CensusSnapshot fixture docstring stale relative to the _CensusFactValue narrowing

src/aeat/application/live/test_census_snapshot.py:3-9 still describes
the fixture as populating census_facts with both Decimal and str
values, but _CensusFactValue = str at _census.py:47 was narrowed
(documented inline at _census.py:38-46) and the fixture itself is
correctly all-string. Cosmetic, but the next reader auditing the
union resolver will be confused.

Remediation: align the test module docstring with the implementation
comment in the next touch of test_census_snapshot.py.

## Recommendations

The CRITICAL WorkUnit finding must land before the W85 wave is
considered persistence-safe - the regression it leaves open is
exactly the save-drops / load-re-defaults pattern the project rule
forbids. The two HIGH findings should land as paired roundtrip
extensions in the same gate. The MEDIUM CensusFactSet flattener gap
is a forward-looking flag; it does not block the current wave but
must be tracked into the step that wires the sede driver into
production. The LOW docstring stale should be folded into the next
touch of test_census_snapshot.py.

Status: REVISION REQUIRED.
