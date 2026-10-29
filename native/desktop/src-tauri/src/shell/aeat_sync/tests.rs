use super::admitted::{ADMITTED, Kind};
use super::*;
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};

/// The shipped operation contract manifest, found from the crate upward: the
/// host tests run in a snapshot of the sources under the build tree, which
/// sits inside the repository checkout that owns the manifest.
fn manifest() -> String {
    let relative = std::path::Path::new("src/cadrumo/_data/operations/contract_manifest.json");
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .map(|directory| directory.join(relative))
        .find(|candidate| candidate.is_file())
        .expect("the shipped operation contract manifest is above the crate");
    std::fs::read_to_string(path).unwrap()
}

/// Each shipped definition's contract, by id.
fn contracts() -> BTreeMap<String, Value> {
    let manifest: Value = serde_json::from_str(&manifest()).unwrap();
    manifest["operations"]
        .as_array()
        .unwrap()
        .iter()
        .map(|entry| {
            let contract = entry["contract"].clone();
            (
                contract["definition_id"].as_str().unwrap().to_owned(),
                contract,
            )
        })
        .collect()
}
fn strings(value: &Value) -> BTreeSet<&str> {
    value
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item.as_str().unwrap())
        .collect()
}

#[test]
fn the_admitted_list_is_sorted_and_names_each_definition_once() {
    let ids: Vec<&str> = ADMITTED.iter().map(|(id, _)| *id).collect();
    let mut sorted = ids.clone();
    sorted.sort_unstable();
    sorted.dedup();
    assert_eq!(ids, sorted);
}

#[test]
fn every_admitted_definition_is_a_shipped_contract() {
    let contracts = contracts();
    for (id, _) in ADMITTED {
        assert!(contracts.contains_key(id), "{id} is not in the manifest");
    }
}

#[test]
fn a_read_declares_no_effect_that_changes_records() {
    let contracts = contracts();
    for (id, kind) in ADMITTED {
        let effects = strings(&contracts[id]["permitted_effects"]);
        let changes = effects.iter().any(|e| matches!(*e, "updated" | "partial"));
        assert_eq!(changes, kind != Kind::Read, "{id}: {effects:?}");
    }
}

#[test]
fn no_admitted_definition_pauses_for_the_person_or_can_be_cancelled() {
    let contracts = contracts();
    for (id, _) in ADMITTED {
        assert_eq!(contracts[id]["cancellation"], "unsupported", "{id}");
        assert_eq!(contracts[id]["interaction_kinds"], json!([]), "{id}");
    }
}

#[test]
fn the_list_holds_only_reads_of_aeat_or_the_profile() {
    for (id, _) in ADMITTED {
        assert!(
            id.starts_with("live.") || ["auth.local-read", "auth.session.acquire"].contains(&id),
            "{id} is outside the live reads"
        );
        assert!(
            !["submit", "filing", "present", "write"]
                .iter()
                .any(|word| id.contains(word)),
            "{id}"
        );
    }
}

#[test]
fn the_areas_submit_only_admitted_definitions_and_leave_none_unused() {
    let mut named: BTreeSet<&str> = BTreeSet::from([
        "auth.local-read",
        "auth.session.acquire",
        "live.borrador.100.import",
        "live.notifications.latest",
        "live.notifications.show",
        "live.sync.status",
    ]);
    for area in Area::ORDER {
        named.extend(area.definitions());
    }
    let admitted: BTreeSet<&str> = ADMITTED.iter().map(|(id, _)| *id).collect();
    assert_eq!(named, admitted);
}

#[test]
fn areas_run_in_the_fixed_order() {
    assert_eq!(
        Area::ORDER,
        [
            Area::Census,
            Area::Identity,
            Area::Notifications,
            Area::Vat,
            Area::Filed
        ]
    );
}

fn selection(value: Value) -> Result<Plan> {
    serde_json::from_value::<Selection>(value)
        .map_err(|_| invalid())?
        .admit()
}

#[test]
fn a_selection_runs_each_area_once_in_the_fixed_order() {
    let plan = selection(json!({"areas": ["filed", "census", "filed", "vat"]})).unwrap();
    assert_eq!(plan.areas, [Area::Census, Area::Vat, Area::Filed]);
    for area in ["census", "identity", "notifications", "vat", "filed"] {
        assert!(selection(json!({"areas": [area]})).is_ok(), "{area}");
    }
}

#[test]
fn a_selection_refuses_what_the_window_may_not_name() {
    // Years, forms and a dry run are not the window's to choose: every area
    // reads every year the backend serves, and every read keeps what it read.
    for refused in [
        json!({"areas": []}),
        json!({"areas": ["borrador"]}),
        json!({"areas": ["census"], "output_root": "C:\\"}),
        json!({"areas": ["census"], "nif": "00000000T"}),
        json!({"areas": ["filed"], "years": [2025]}),
        json!({"areas": ["filed"], "forms": ["303"]}),
        json!({"areas": ["filed"], "dry_run": false}),
    ] {
        assert!(selection(refused.clone()).is_err(), "{refused}");
    }
}

// The run model, followed by a scripted driver: the queue is tested without a
// relay, and the relay side is the outcome table tested below.

use super::outcome::{self as table, Counts, Outcome, Reason};
use super::run::{self as queue, ItemState, Run, RunState, Settled, Step};
use std::collections::BTreeSet as Set;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

type Answer = Box<dyn Fn(&Step, usize) -> Settled + Send + Sync>;
type During = Box<dyn Fn(&Step, &Mutex<Run>) + Send + Sync>;

/// Answers each step from `answer`, records what ran, and may act on the run
/// while a step is in flight, as the person would from the window.
struct Scripted {
    ran: Mutex<Vec<Step>>,
    answer: Answer,
    during: During,
    run: Mutex<Option<Arc<Mutex<Run>>>>,
    signed_in: AtomicBool,
    cues: AtomicUsize,
}
impl Scripted {
    fn new(answer: impl Fn(&Step, usize) -> Settled + Send + Sync + 'static) -> Self {
        Self {
            ran: Mutex::new(Vec::new()),
            answer: Box::new(answer),
            during: Box::new(|_, _| {}),
            run: Mutex::new(None),
            signed_in: AtomicBool::new(true),
            cues: AtomicUsize::new(0),
        }
    }
    fn ran(&self) -> Vec<Step> {
        lock(&self.ran).clone()
    }
}
impl queue::Driver for Scripted {
    async fn run(&self, step: Step) -> Settled {
        let times = {
            let mut ran = lock(&self.ran);
            ran.push(step.clone());
            ran.iter().filter(|s| **s == step).count()
        };
        let run = lock(&self.run).clone();
        if let Some(run) = run {
            (self.during)(&step, &run);
        }
        (self.answer)(&step, times)
    }
    async fn current(&self) -> bool {
        self.signed_in.load(Ordering::SeqCst)
    }
    fn changed(&self) {
        self.cues.fetch_add(1, Ordering::SeqCst);
    }
}

fn found(pairs: &[(u16, &[&str])]) -> Settled {
    Settled {
        outcome: Outcome::Brought,
        discovered: Some(
            pairs
                .iter()
                .map(|(year, forms)| (*year, forms.iter().map(|f| (*f).to_owned()).collect()))
                .collect(),
        ),
        ..Settled::default()
    }
}
fn brought(step: &Step, _: usize) -> Settled {
    if matches!(step, Step::Discover) {
        found(&[(2024, &["130", "303"]), (2025, &["303"])])
    } else {
        Settled::of(Outcome::Brought)
    }
}

fn plan(value: Value) -> Plan {
    selection(value).unwrap()
}
fn everything() -> Plan {
    plan(json!({"areas": ["filed", "vat", "notifications", "identity", "census"]}))
}

/// Starts `plan` and follows it with `driver` until the driver loop ends.
async fn follow(plan: &Plan, driver: Scripted) -> (Arc<Mutex<Run>>, Arc<Scripted>) {
    let run = Arc::new(Mutex::new(Run::new(plan)));
    assert!(queue::lock(&run).claim());
    *lock(&driver.run) = Some(run.clone());
    let driver = Arc::new(driver);
    queue::drive(run.clone(), driver.clone()).await;
    (run, driver)
}
async fn again(run: &Arc<Mutex<Run>>, driver: &Arc<Scripted>) {
    queue::drive(run.clone(), driver.clone()).await;
}

fn states(run: &Mutex<Run>) -> Vec<(Area, Option<u16>, ItemState)> {
    queue::lock(run)
        .snapshot()
        .areas
        .into_iter()
        .flat_map(|area| {
            let name = area.area;
            area.items
                .into_iter()
                .map(move |item| (name, item.year, item.state))
        })
        .collect()
}

fn filed(year: u16, forms: &[&str]) -> Step {
    Step::Filed {
        year,
        forms: forms.iter().map(|f| (*f).to_owned()).collect(),
    }
}

#[tokio::test]
async fn a_run_brings_the_areas_in_the_fixed_order_and_filed_declarations_year_by_year() {
    let (run, driver) = follow(&everything(), Scripted::new(brought)).await;
    assert_eq!(
        driver.ran(),
        [
            Step::Census,
            Step::Verify("live.verify.nif-iva"),
            Step::Verify("live.verify.tgvi"),
            Step::Notifications,
            Step::Vat,
            Step::Discover,
            filed(2024, &["130", "303"]),
            filed(2025, &["303"]),
        ]
    );
    assert_eq!(queue::lock(&run).state, RunState::Done);
    assert!(
        states(&run)
            .iter()
            .all(|(_, _, s)| *s == ItemState::Brought)
    );
    let years: Vec<_> = states(&run)
        .into_iter()
        .filter(|(area, _, _)| *area == Area::Filed)
        .map(|(_, year, _)| year)
        .collect();
    assert_eq!(years, [Some(2024), Some(2025)]);
    assert!(driver.cues.load(Ordering::SeqCst) > 0, "the window is cued");
}

#[tokio::test]
async fn filed_declarations_read_every_year_the_discovery_finds_with_its_forms() {
    let (run, driver) = follow(&plan(json!({"areas": ["filed"]})), Scripted::new(brought)).await;
    assert_eq!(
        driver.ran(),
        [
            Step::Discover,
            filed(2024, &["130", "303"]),
            filed(2025, &["303"])
        ]
    );
    assert_eq!(
        states(&run),
        [
            (Area::Filed, Some(2024), ItemState::Brought),
            (Area::Filed, Some(2025), ItemState::Brought),
        ]
    );
}

#[test]
fn the_filed_parts_are_unknown_to_the_window_until_the_discovery_settles() {
    let run = Run::new(&plan(json!({"areas": ["filed"]})));
    let snapshot = run.snapshot();
    assert!(snapshot.areas[0].items.is_empty());
    assert_eq!(snapshot.areas[0].state, queue::AreaState::Waiting);
}

#[tokio::test]
async fn a_failed_discovery_is_one_part_the_person_can_read_again() {
    let driver = Scripted::new(|step, times| match step {
        Step::Discover if times == 1 => Settled::of(Outcome::Failed(Reason::Unavailable)),
        _ => brought(step, times),
    });
    let (run, driver) = follow(&plan(json!({"areas": ["filed"]})), driver).await;
    assert_eq!(states(&run), [(Area::Filed, None, ItemState::Failed)]);
    let item = queue::lock(&run).snapshot().areas[0].items[0].item;
    assert_eq!(
        queue::lock(&run).retry(Area::Filed, Some(item), false),
        Ok(true)
    );
    again(&run, &driver).await;
    assert_eq!(
        states(&run),
        [
            (Area::Filed, Some(2024), ItemState::Brought),
            (Area::Filed, Some(2025), ItemState::Brought)
        ]
    );
}

#[tokio::test]
async fn stop_lets_the_item_in_flight_settle_and_starts_nothing_further() {
    let mut driver = Scripted::new(brought);
    driver.during = Box::new(|step, run| {
        if *step == Step::Notifications {
            queue::lock(run).stop();
            assert_eq!(queue::lock(run).snapshot().state, RunState::Stopping);
        }
    });
    let (run, driver) = follow(&everything(), driver).await;
    assert_eq!(driver.ran().last(), Some(&Step::Notifications));
    assert_eq!(queue::lock(&run).state, RunState::Stopped);
    let shown = states(&run);
    assert!(shown.contains(&(Area::Notifications, None, ItemState::Brought)));
    assert!(shown.contains(&(Area::Vat, None, ItemState::NotStarted)));
    assert!(shown.contains(&(Area::Filed, None, ItemState::NotStarted)));
    let snapshot = queue::lock(&run).snapshot();
    assert_eq!(snapshot.areas[4].state, queue::AreaState::NotStarted);
    assert_eq!(snapshot.areas[0].state, queue::AreaState::Finished);
}

#[tokio::test]
async fn an_ended_session_pauses_and_resume_starts_from_the_first_item_not_brought() {
    let driver = Scripted::new(|step, times| match step {
        Step::Notifications => Settled::of(Outcome::Unknown),
        Step::Vat if times == 1 => Settled::of(Outcome::Failed(Reason::SessionEnded)),
        _ => brought(step, times),
    });
    let (run, driver) = follow(&everything(), driver).await;
    assert_eq!(queue::lock(&run).state, RunState::Paused);
    let shown = states(&run);
    assert!(shown.contains(&(Area::Vat, None, ItemState::Failed)));
    assert!(shown.contains(&(Area::Filed, None, ItemState::NotStarted)));
    let paused = queue::lock(&run).snapshot();
    assert_eq!(paused.areas[3].items[0].reason, Some(Reason::SessionEnded));
    // A paused run is carried on, not read again part by part.
    assert_eq!(
        queue::lock(&run).retry(Area::Vat, None, true),
        Err(queue::Refusal::Refused)
    );
    assert_eq!(queue::lock(&run).resume(), Ok(true));
    again(&run, &driver).await;
    let ran = driver.ran();
    assert_eq!(
        ran[5..],
        [
            Step::Vat,
            Step::Discover,
            filed(2024, &["130", "303"]),
            filed(2025, &["303"]),
        ]
    );
    assert_eq!(ran.iter().filter(|s| **s == Step::Census).count(), 1);
    assert_eq!(
        ran.iter().filter(|s| **s == Step::Notifications).count(),
        1,
        "an unknown item is never run again by itself"
    );
    assert_eq!(queue::lock(&run).state, RunState::Done);
    assert!(states(&run).contains(&(Area::Notifications, None, ItemState::Unknown)));
}

#[tokio::test]
async fn an_unknown_item_is_read_again_only_once_the_person_was_told() {
    let driver = Scripted::new(|step, times| match step {
        Step::Notifications if times == 1 => Settled::of(Outcome::Unknown),
        Step::Census if times == 1 => Settled::of(Outcome::Failed(Reason::NoAccess)),
        _ => brought(step, times),
    });
    let (run, driver) = follow(&plan(json!({"areas": ["census", "notifications"]})), driver).await;
    assert_eq!(queue::lock(&run).state, RunState::Done);
    let unknown = queue::lock(&run).snapshot().areas[1].items[0].item;
    for item in [Some(unknown), None] {
        let retried = queue::lock(&run).retry(Area::Notifications, item, false);
        assert_eq!(retried, Err(queue::Refusal::Unknown));
    }
    assert_eq!(states(&run)[1].2, ItemState::Unknown);
    // A failed item needs no warning, and one driver follows the queue.
    assert_eq!(queue::lock(&run).retry(Area::Census, None, false), Ok(true));
    assert_eq!(
        queue::lock(&run).retry(Area::Vat, None, true),
        Err(queue::Refusal::Invalid)
    );
    assert_eq!(
        queue::lock(&run).retry(Area::Notifications, Some(999), true),
        Err(queue::Refusal::Invalid)
    );
    assert_eq!(
        queue::lock(&run).retry(Area::Notifications, Some(unknown), true),
        Ok(false)
    );
    again(&run, &driver).await;
    assert_eq!(
        driver.ran(),
        [
            Step::Census,
            Step::Notifications,
            Step::Census,
            Step::Notifications
        ]
    );
    assert_eq!(states(&run)[1].2, ItemState::Brought);
    // What was brought is not read again.
    assert_eq!(
        queue::lock(&run).retry(Area::Notifications, None, true),
        Err(queue::Refusal::Refused)
    );
}

#[tokio::test]
async fn a_sign_out_ends_the_driver_without_running_anything_further() {
    let driver = Scripted::new(brought);
    driver.signed_in.store(false, Ordering::SeqCst);
    let (run, driver) = follow(&everything(), driver).await;
    assert!(driver.ran().is_empty());
    assert!(queue::lock(&run).claim(), "the queue is released");
}

#[tokio::test]
async fn an_ended_session_that_may_have_kept_something_is_unknown_and_never_resumed() {
    // The VAT capture ended its session after keeping a part: the run does
    // not pause there, and the item is never read again by itself.
    let ended = |effect: &str| {
        table::terminal(&projection("refused", effect, Some(table::SESSION_ENDED))).unwrap()
    };
    let driver = Scripted::new(move |step, times| match step {
        Step::Vat => Settled::of(ended("partial")),
        Step::Discover if times == 1 => Settled::of(ended("none")),
        _ => brought(step, times),
    });
    let (run, driver) = follow(&everything(), driver).await;
    assert_eq!(queue::lock(&run).state, RunState::Paused);
    let paused = states(&run);
    assert!(paused.contains(&(Area::Vat, None, ItemState::Unknown)));
    assert!(paused.contains(&(Area::Filed, None, ItemState::Failed)));
    assert_eq!(queue::lock(&run).resume(), Ok(true));
    again(&run, &driver).await;
    let ran = driver.ran();
    assert_eq!(ran.iter().filter(|s| **s == Step::Vat).count(), 1);
    assert_eq!(ran.iter().filter(|s| **s == Step::Discover).count(), 2);
    assert_eq!(queue::lock(&run).state, RunState::Done);
    assert!(states(&run).contains(&(Area::Vat, None, ItemState::Unknown)));
}

#[test]
fn an_area_is_served_the_worst_of_its_settled_items() {
    let mut run = Run::new(&plan(json!({"areas": ["identity", "notifications"]})));
    let outcome = |run: &Run, index: usize| run.snapshot().areas[index].outcome;
    assert_eq!((outcome(&run, 0), outcome(&run, 1)), (None, None));
    let (first, _) = run.next().unwrap();
    run.settle(first, Settled::of(Outcome::Brought));
    assert_eq!(outcome(&run, 0), Some("brought"));
    let (second, _) = run.next().unwrap();
    run.settle(second, Settled::of(Outcome::Failed(Reason::Unavailable)));
    assert_eq!(outcome(&run, 0), Some("failed"));
    let (third, _) = run.next().unwrap();
    run.settle(third, Settled::of(Outcome::NothingFound));
    assert_eq!(outcome(&run, 1), Some("nothing_found"));
}

#[test]
fn a_start_keeps_a_run_that_still_moves_and_replaces_only_a_settled_one() {
    let sync = SyncHost::default();
    let ours = json!({"profile_id": "a", "session_id": "1"});
    assert!(
        sync.begin(&ours, &everything()),
        "the first start holds a run"
    );
    let first = sync.current(&ours).unwrap();
    // A second start, as from a second click racing the first, reattaches.
    assert!(!sync.begin(&ours, &everything()));
    assert!(Arc::ptr_eq(&sync.current(&ours).unwrap(), &first));
    // A run whose driver still follows it is kept, whatever its state says.
    queue::lock(&first).stop();
    assert!(queue::lock(&first).active(), "its driver has not let go");
    assert!(!sync.begin(&ours, &everything()));
    assert!(Arc::ptr_eq(&sync.current(&ours).unwrap(), &first));
    // Once its driver let go of a stopped run, a start holds a fresh one.
    assert_eq!(queue::lock(&first).next(), None);
    assert!(!queue::lock(&first).active());
    assert!(sync.begin(&ours, &everything()));
    assert!(!Arc::ptr_eq(&sync.current(&ours).unwrap(), &first));
    // Another session's start replaces this session's run.
    let other = json!({"profile_id": "a", "session_id": "2"});
    assert!(sync.begin(&other, &everything()));
    assert!(
        lock(&sync.held)
            .as_ref()
            .is_some_and(|h| h.identity == other)
    );
}

#[test]
fn a_run_reattaches_for_its_session_and_is_discarded_for_another() {
    let sync = SyncHost::default();
    let ours = json!({"profile_id": "a", "session_id": "1"});
    let run = Arc::new(Mutex::new(Run::new(&everything())));
    *lock(&sync.held) = Some(Held {
        identity: ours.clone(),
        run: run.clone(),
        task: None,
    });
    // The page may be left and opened again: the same session finds its run.
    for _ in 0..2 {
        assert!(Arc::ptr_eq(&sync.current(&ours).unwrap(), &run));
    }
    assert!(queue::lock(&run).active());
    let other = json!({"profile_id": "a", "session_id": "2"});
    assert!(sync.current(&other).is_none());
    assert!(sync.current(&ours).is_none(), "a signed-out run is gone");
    *lock(&sync.held) = Some(Held {
        identity: ours.clone(),
        run,
        task: None,
    });
    sync.close();
    assert!(sync.current(&ours).is_none());
}

#[test]
fn stop_and_resume_of_a_run_no_driver_follows() {
    let mut run = Run::new(&everything());
    run.stop();
    assert_eq!(run.state, RunState::Stopped);
    assert_eq!(run.resume(), Err(queue::Refusal::Refused));
}

// The closed outcome table.

fn projection(condition: &str, effect: &str, refusal: Option<&str>) -> Value {
    json!({"lifecycle": "terminal", "terminal_condition": condition, "effect": effect,
        "refusal_ref": refusal})
}

#[test]
fn a_terminal_condition_reads_as_one_outcome() {
    assert_eq!(
        table::terminal(&projection("succeeded", "updated", None)),
        None
    );
    for (p, expected) in [
        (
            projection("refused", "none", Some(table::SESSION_ENDED)),
            Outcome::Failed(Reason::SessionEnded),
        ),
        (
            projection("failed", "none", Some(table::SESSION_ENDED)),
            Outcome::Failed(Reason::SessionEnded),
        ),
        // An ended session that may have kept something is never resumed.
        (
            projection("refused", "updated", Some(table::SESSION_ENDED)),
            Outcome::Unknown,
        ),
        (
            projection("refused", "partial", Some(table::SESSION_ENDED)),
            Outcome::Unknown,
        ),
        (
            projection("refused", "unknown", Some(table::SESSION_ENDED)),
            Outcome::Unknown,
        ),
        (
            projection(
                "refused",
                "none",
                Some("REFUSED_AUTH_PROVIDER_NOT_CONFIGURED"),
            ),
            Outcome::Failed(Reason::NoAccess),
        ),
        (
            projection("refused", "none", Some("REFUSED_BROWSER_NOT_READY")),
            Outcome::Failed(Reason::Unavailable),
        ),
        (
            projection("refused", "none", Some("REFUSED_APPLICATION_LIVE_INPUT")),
            Outcome::Failed(Reason::Refused),
        ),
        (
            projection("failed", "none", None),
            Outcome::Failed(Reason::Other),
        ),
        (projection("failed", "updated", None), Outcome::Unknown),
        (projection("failed", "partial", None), Outcome::Unknown),
        (
            projection("refused", "unknown", Some("X")),
            Outcome::Unknown,
        ),
        (
            projection("cancelled", "none", None),
            Outcome::Failed(Reason::Other),
        ),
        (projection("lost", "none", None), Outcome::Unknown),
    ] {
        assert_eq!(table::terminal(&p), Some(expected), "{p}");
    }
}

type Row = (&'static str, Value, Outcome, Value, Outcome);

/// A succeeded result for each admitted capture an item submits, with what it
/// reads as when it found something and when it found nothing.
fn results() -> Vec<Row> {
    let bulk = |captured: u64, rows: u64| {
        json!({"captured_count": captured, "failed_count": 0,
            "filing_evidence_conflict_count": 0,
            "pair_outcomes": [{"modelo": "303", "year": 2025, "row_count": rows}]})
    };
    let vat = |captured: u64| {
        json!({"captured_count": captured, "calculation_observation_count": 0,
            "failed_declaration_count": 0})
    };
    vec![
        // A check that got no answer brought nothing.
        (
            "live.verify.nif-iva",
            json!({"verdict": "valid"}),
            Outcome::Brought,
            json!({"verdict": "unknown"}),
            Outcome::Failed(Reason::Unavailable),
        ),
        (
            "live.verify.tgvi",
            json!({"verdict": "invalid"}),
            Outcome::Brought,
            json!({"verdict": "unknown"}),
            Outcome::Failed(Reason::Unavailable),
        ),
        (
            "live.notifications.capture",
            json!({"row_count": 3}),
            Outcome::Brought,
            json!({"row_count": 0}),
            Outcome::NothingFound,
        ),
        (
            "live.iva-wallet.history-capture",
            vat(2),
            Outcome::Brought,
            vat(0),
            Outcome::NothingFound,
        ),
        (
            "live.filed-discover",
            json!({"pairs": [{"modelo": "303", "ejercicio": 2025}]}),
            Outcome::Brought,
            json!({"pairs": []}),
            Outcome::NothingFound,
        ),
        (
            "live.filed-capture.bulk",
            bulk(2, 2),
            Outcome::Brought,
            bulk(0, 0),
            Outcome::NothingFound,
        ),
    ]
}

#[test]
fn the_outcome_table_reads_every_capture_an_item_submits() {
    let rows = results();
    let read: Set<&str> = rows.iter().map(|(id, ..)| *id).collect();
    let submitted: Set<&str> = Area::ORDER
        .into_iter()
        .flat_map(|area| area.definitions())
        .copied()
        .collect();
    assert_eq!(read, submitted);
    for (id, some, with_some, none, with_none) in rows {
        assert_eq!(table::succeeded(id, &some).0, with_some, "{id}");
        assert_eq!(table::succeeded(id, &none).0, with_none, "{id}");
        assert_eq!(table::succeeded(id, &json!({})).0, Outcome::Unknown, "{id}");
        assert!(admitted(id).is_some_and(|(_, kind)| kind == Kind::Capture));
    }
    assert_eq!(
        table::succeeded("live.unlisted", &json!({})).0,
        Outcome::Unknown
    );
}

#[test]
fn a_capture_with_failed_parts_is_failed_and_counts_what_it_kept() {
    let (outcome, counts) = table::succeeded(
        "live.filed-capture.bulk",
        &json!({"captured_count": 4, "failed_count": 1, "filing_evidence_conflict_count": 2,
            "pair_outcomes": []}),
    );
    assert_eq!(outcome, Outcome::Failed(Reason::Other));
    assert_eq!(counts, Counts { new: 4, changed: 2 });
    let held = table::succeeded(
        "live.filed-capture.bulk",
        &json!({"captured_count": 0, "failed_count": 0, "filing_evidence_conflict_count": 0,
            "pair_outcomes": [{"row_count": 3}]}),
    );
    assert_eq!(held.0, Outcome::Brought, "rows already held are found");
    let vat = table::succeeded(
        "live.iva-wallet.history-capture",
        &json!({"captured_count": 1, "calculation_observation_count": 0,
            "failed_declaration_count": 1}),
    );
    assert_eq!(vat.0, Outcome::Failed(Reason::Other));
}

#[test]
fn a_discovery_reads_its_forms_by_year_and_refuses_what_is_not_a_form() {
    let found = table::discovered(&json!({"pairs": [
        {"modelo": "303", "ejercicio": 2025}, {"modelo": "130", "ejercicio": 2025},
        {"modelo": "303", "ejercicio": 2024}]}))
    .unwrap();
    assert_eq!(
        found[&2025],
        Set::from(["130".to_owned(), "303".to_owned()])
    );
    assert!(
        table::discovered(&json!({"pairs": [{"modelo": "../x", "ejercicio": 2025}]})).is_none()
    );
}

#[test]
fn an_area_takes_the_worst_of_its_items() {
    use Outcome::{Brought, Failed, NothingFound, Unknown};
    assert_eq!(table::worst([Brought, NothingFound]), Some(Brought));
    assert_eq!(
        table::worst([Brought, Failed(Reason::Other)]),
        Some(Failed(Reason::Other))
    );
    assert_eq!(
        table::worst([Failed(Reason::Other), Unknown, Brought]),
        Some(Unknown)
    );
    assert_eq!(table::worst([]), None);
}

#[test]
fn a_sign_in_reads_as_signed_in_only_when_authenticated() {
    let ok = projection("succeeded", "updated", None);
    assert!(signed_in(&ok, Some(&json!({"result": {"authenticated": true}}))).is_ok());
    let code = |result: Result<()>| result.unwrap_err().code;
    assert_eq!(
        code(signed_in(
            &ok,
            Some(&json!({"result": {"authenticated": false}}))
        )),
        "refused"
    );
    assert_eq!(
        code(signed_in(
            &projection(
                "refused",
                "none",
                Some("REFUSED_CLAVE_CREDENTIALS_INCOMPLETE")
            ),
            None
        )),
        "needs_access"
    );
    assert_eq!(
        code(signed_in(&projection("failed", "updated", None), None)),
        "unavailable"
    );
}

#[test]
fn the_census_session_settles_its_item_once_it_waits_for_review() {
    assert_eq!(census_outcome("reading"), None);
    assert_eq!(census_outcome("device"), None);
    let review = census_outcome("review").unwrap();
    assert_eq!(review.outcome, Outcome::Brought);
    assert!(review.review_pending);
    assert_eq!(census_outcome("unknown").unwrap().outcome, Outcome::Unknown);
    assert_eq!(
        census_outcome("failed").unwrap().outcome,
        Outcome::Failed(Reason::Other)
    );
}

// No identifier, code or path reaches the window.

const OPERATION: &str = "abababababababababababababababababababababababababababababababab";

fn leaks(reply: &str) {
    for secret in [
        OPERATION,
        "REFUSED_",
        "aeat_sync.status",
        "live.",
        "auth.",
        "bucket",
        "snapshot",
        "certificado",
        "CERT-1",
        "https://",
        "11111111-2222",
        "B12345678",
    ] {
        assert!(!reply.contains(secret), "{secret} in {reply}");
    }
}

fn status_area(area: &str, state: &str, brought: Option<&str>) -> Value {
    json!({"area": area, "state": state, "last_brought_at": brought, "stale_after_days": 90,
        "last_attempt_at": null, "last_attempt_succeeded": null, "refusal": null,
        "unread_notification_count": null, "filed_periods": null})
}

#[test]
fn no_identifier_code_or_path_reaches_the_window() {
    let at = Some("2026-10-01T10:00:00Z");
    let mut areas = vec![
        status_area("census", "current", at),
        status_area("identity_checks", "unavailable", None),
        status_area("notifications", "possibly_stale", at),
        status_area("iva_wallet", "never_brought", None),
        status_area("filed_declarations", "current", at),
        status_area("borrador_100", "never_brought", None),
    ];
    areas[1]["refusal"] = json!("aeat_sync.status.profile_tax_id_missing");
    areas[2]["unread_notification_count"] = json!(2);
    areas[4]["last_attempt_at"] = json!("2026-10-02T10:00:00Z");
    areas[4]["last_attempt_succeeded"] = json!(false);
    areas[4]["filed_periods"] =
        json!({"matched": 3, "aeat_only": 1, "local_only": 0, "differing": 1});
    let status = json!({"bucket_id": "11111111-2222-4333-8444-555555555555", "status": {
        "contract_version": 1, "observed_at": "2026-10-29T10:00:00Z",
        "filed_declaration_years": [2025], "iva_wallet_years": [2025], "areas": areas}});
    let served = status_reply("p", &status, std::time::SystemTime::now()).unwrap();
    leaks(&serde_json::to_string(&served).unwrap());
    let names: Vec<&str> = served.areas.iter().map(|a| a.area).collect();
    assert_eq!(
        names,
        [
            "census",
            "identity",
            "notifications",
            "vat",
            "filed",
            "borrador"
        ]
    );
    assert_eq!(served.areas[2].counts[0].value, 2);
    assert_eq!(served.areas[4].counts.len(), 4);
    assert_eq!(
        served.areas[4].last_attempt.as_ref().unwrap().outcome,
        "failed"
    );
    assert_eq!(served.areas[5].update, "import");
    let mut unknown_area = status.clone();
    unknown_area["status"]["areas"][0]["area"] = json!("payroll");
    assert!(status_reply("p", &unknown_area, std::time::SystemTime::now()).is_err());
    assert_eq!(served.borrador_years, [2025]);

    let mut run = Run::new(&everything());
    while let Some((id, step)) = run.next() {
        let settled = match step {
            Step::Discover => found(&[(2025, &["303"])]),
            Step::Vat => Settled::of(Outcome::Failed(Reason::Refused)),
            Step::Census => Settled {
                outcome: Outcome::Brought,
                review_pending: true,
                ..Settled::default()
            },
            _ => Settled::of(Outcome::Unknown),
        };
        run.settle(id, settled);
    }
    let snapshot = serde_json::to_string(&run.snapshot()).unwrap();
    leaks(&snapshot);
    assert!(snapshot.contains(r#""reason":"refused""#));
    let results = results_reply(Some(&run), served, filed_rows(&status).unwrap());
    leaks(&serde_json::to_string(&results).unwrap());
    assert_eq!(results.areas[0].at.as_deref(), at);
    assert!(results.areas[0].review_pending);
    let vat = results.areas.iter().find(|a| a.area == Area::Vat).unwrap();
    assert_eq!((vat.outcome, vat.failed.len()), ("failed", 1));

    let row = |certificate: &str, leida: bool, read_on: Option<&str>| {
        json!({"certificado_id": certificate, "tipo": "notificacion", "concepto": "Requerimiento",
            "titular_nif": "B12345678", "titular_nombre": "X", "destinatario_nif": "B12345678",
            "destinatario_nombre": "X", "fecha_emision": "2026-10-01",
            "fecha_notificacion": read_on, "modo_notificacion": null, "leida": leida,
            "source_url": "https://sede.example/y", "mode": "read"})
    };
    let shown = json!({"bucket_id": "11111111-2222-4333-8444-555555555555",
        "snapshot_id": OPERATION, "source_url": "https://sede.example/x", "row_count": 2,
        "rows": [row("CERT-1", false, None), row("CERT-2", true, Some("2026-09-03"))]});
    let rows = notification_rows(&shown).unwrap();
    leaks(&serde_json::to_string(&rows).unwrap());
    assert_eq!((rows[0].read, rows[0].read_on.as_deref()), (false, None));
    assert_eq!(rows[1].read_on.as_deref(), Some("2026-09-03"));

    let prepared = Prepared {
        browser: browser(None),
        access: "ready",
    };
    assert_eq!(
        serde_json::to_value(&prepared).unwrap(),
        json!({"browser": {"state": "attention"}, "access": "ready"})
    );
}

#[test]
fn the_borrador_years_are_the_served_ones_or_the_last_six_before_this_year() {
    let served = json!({"status": {"filed_declaration_years": [2023, 2025, 2024, 2025]}});
    let now = std::time::SystemTime::now();
    assert_eq!(borrador_years(&served, now), [2025, 2024, 2023]);
    // 2026-10-29T00:00:00Z: the latest Borrador on offer is for 2025.
    let in_2026 = std::time::UNIX_EPOCH + std::time::Duration::from_secs(1_793_232_000);
    for none in [
        json!({"status": {"filed_declaration_years": []}}),
        json!({"status": {}}),
        json!({"status": {"filed_declaration_years": [25]}}),
    ] {
        assert_eq!(
            borrador_years(&none, in_2026),
            [2025, 2024, 2023, 2022, 2021, 2020],
            "{none}"
        );
    }
    // Year boundaries in UTC, from the proleptic calendar's own dates.
    for (seconds, year) in [
        (0, 1970),
        (951_782_400, 2000),   // 2000-02-29
        (978_307_199, 2000),   // 2000-12-31T23:59:59Z
        (978_307_200, 2001),   // 2001-01-01
        (1_767_225_599, 2025), // 2025-12-31T23:59:59Z
        (1_767_225_600, 2026), // 2026-01-01
        (4_107_542_400, 2100), // 2100-03-01
    ] {
        assert_eq!(calendar_year(seconds), year, "{seconds}");
    }
}

#[test]
fn the_preflight_reads_access_readiness_through_the_admitted_local_read() {
    assert_eq!(super::admitted::READINESS, "auth.local-read");
    assert_eq!(
        admitted(super::admitted::READINESS),
        Some(("auth.local-read", Kind::Readiness))
    );
    let contract = &contracts()["auth.local-read"];
    assert_eq!(contract["subject_reference"]["kind"], "profile");
    assert_eq!(contract["sensitive_input"], "none");
}

fn filed_status(row: Value) -> Value {
    let mut area = status_area(
        "filed_declarations",
        "current",
        Some("2026-10-01T10:00:00Z"),
    );
    area["filed_periods"] = json!({"matched": 0, "aeat_only": 0, "local_only": 0, "differing": 0});
    area["filed_rows"] = json!([row]);
    json!({"status": {"areas": [area]}})
}

fn served_row() -> Value {
    json!({"modelo": "303", "filing_year": 2025, "period": "1T", "match": "differing",
        "local_record": "draft", "local_record_at": "2026-09-01T10:00:00Z",
        "aeat_shown_at": "2026-10-01T10:00:00Z", "receipt_confirmed": false,
        "differences": ["status"]})
}

#[test]
fn filed_rows_keep_the_record_the_aeat_observation_and_the_receipt_apart() {
    let rows = filed_rows(&filed_status(served_row())).unwrap();
    leaks(&serde_json::to_string(&rows).unwrap());
    assert_eq!(
        serde_json::to_value(&rows).unwrap(),
        json!([{"form": "303", "year": 2025, "period": "1T", "match": "differing",
            "record": {"status": "draft", "on": "2026-09-01T10:00:00Z"},
            "aeat": {"seen_on": "2026-10-01T10:00:00Z"}, "receipt": "not_confirmed",
            "differences": ["status"]}])
    );
    let mut annual = served_row();
    annual["period"] = Value::Null;
    annual["match"] = json!("aeat_only");
    annual["local_record"] = json!("none");
    annual["local_record_at"] = Value::Null;
    annual["receipt_confirmed"] = json!(true);
    annual["differences"] = json!([]);
    let rows = filed_rows(&filed_status(annual)).unwrap();
    assert_eq!(
        (rows[0].period.as_ref(), rows[0].record.as_ref()),
        (None, None)
    );
    assert_eq!((rows[0].group, rows[0].receipt), ("aeat_only", "confirmed"));
    let never_read =
        json!({"status": {"areas": [status_area("filed_declarations", "never_brought", None)]}});
    assert_eq!(filed_rows(&never_read).unwrap(), Vec::new());
}

#[test]
fn a_filed_row_outside_the_closed_words_is_refused() {
    for (field, value) in [
        ("match", json!("maybe")),
        ("local_record", json!("submitted")),
        ("local_record_at", Value::Null),
        ("differences", json!(["amount"])),
        ("modelo", json!("../303")),
        ("filing_year", json!(20250)),
        ("receipt_confirmed", json!("yes")),
    ] {
        let mut row = served_row();
        row[field] = value;
        assert!(filed_rows(&filed_status(row)).is_err(), "{field}");
    }
    let mut unseen = served_row();
    unseen["aeat_shown_at"] = Value::Null;
    unseen["receipt_confirmed"] = json!(true);
    assert!(filed_rows(&filed_status(unseen)).is_err());
}
