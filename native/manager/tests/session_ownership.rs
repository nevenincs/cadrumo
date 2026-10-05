//! Session ownership across simulated sessions sharing one storage root.
//!
//! Each simulated session is its own [`Ownership`] with its own session identity and
//! activity, over a shared stand-in for the running runtime. The start claim and the Quit
//! marker are the real ones on disk, so contention between sessions goes through the
//! kernel-released lock. Crashed holders are helper processes of this test binary that are
//! killed while they hold the claim or the session lock.

use cadrumo_manager::session::ManagerSession;
use cadrumo_manager::session::claim::StartClaim;
use cadrumo_manager::session::instance::claim_session;
use cadrumo_manager::session::ownership::{
    Located, ObservedRuntime, Ownership, Role, RuntimeLocator, StartKind, WaitReason,
    reserve_restart,
};
use cadrumo_manager::session::quit::{QuitMarker, QuitState, read_quit_marker, record_quit};
use cadrumo_manager::supervision::supervisor::SessionActivity;
use std::io::{BufRead, BufReader, Lines};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::{Arc, Barrier, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const USER: &str = "S-1-5-21-1004336348-1177238915-682003330-1001";
const HELPER_ROLE: &str = "CADRUMO_OWNERSHIP_HELPER";
const HELPER_TARGET: &str = "CADRUMO_OWNERSHIP_TARGET";
/// Marks the helper's reports among the test harness's own output.
const REPORT: &str = "@ownership-report ";

/// A storage root no other test uses, removed afterwards.
struct Root(PathBuf);

impl Root {
    fn new(label: &str) -> Self {
        let path = std::env::temp_dir().join(format!(
            "cadrumo-manager-ownership-{label}-{}-{}",
            std::process::id(),
            nanos()
        ));
        std::fs::create_dir_all(&path).expect("storage root");
        Self(path)
    }
}

impl Drop for Root {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn nanos() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("clock")
        .as_nanos()
}

/// The runtime as the simulated sessions see it: its pid and session, if one runs.
#[derive(Clone, Debug, Default)]
struct World(Arc<Mutex<Option<(u32, String)>>>);

impl World {
    fn running(&self) -> Option<(u32, String)> {
        self.0.lock().expect("world").clone()
    }

    fn set(&self, runtime: Option<(u32, &str)>) {
        *self.0.lock().expect("world") = runtime.map(|(pid, session)| (pid, session.to_owned()));
    }
}

#[derive(Debug)]
struct WorldObserved {
    world: World,
    pid: u32,
}

impl ObservedRuntime for WorldObserved {
    fn pid(&self) -> u32 {
        self.pid
    }

    fn has_ended(&mut self) -> bool {
        self.world.running().map(|(pid, _)| pid) != Some(self.pid)
    }
}

/// Acts on the runtime before a numbered location, as another manager would meanwhile.
type Interleaving = Box<dyn FnMut(&World, u32) + Send>;

struct WorldLocator {
    world: World,
    session: String,
    /// Called with the call number before each location.
    before: Option<Interleaving>,
    calls: u32,
}

impl RuntimeLocator for WorldLocator {
    fn locate(&mut self) -> Located {
        self.calls += 1;
        if let Some(before) = self.before.as_mut() {
            before(&self.world, self.calls);
        }
        match self.world.running() {
            None => Located::Nothing,
            Some((pid, session)) if session == self.session => Located::OwnSession { pid },
            Some((pid, _)) => Located::OtherSession(Box::new(WorldObserved {
                world: self.world.clone(),
                pid,
            })),
        }
    }
}

#[derive(Clone)]
struct Activity(Arc<AtomicBool>);

impl SessionActivity for Activity {
    fn is_active(&self) -> bool {
        self.0.load(Ordering::SeqCst)
    }
}

#[test]
fn restart_reservation_observes_a_runtime_that_won_the_handoff() {
    let root = Root::new("restart-takeover");
    let world = World::default();
    world.set(Some((42, "other")));
    let mut locator = WorldLocator {
        world,
        session: "own".into(),
        before: None,
        calls: 0,
    };
    let active = Activity(Arc::new(AtomicBool::new(true)));
    let Role::Observe(observed) = reserve_restart(&root.0, &active, &mut locator) else {
        panic!("another session's runtime must only be observed");
    };
    assert_eq!(observed.pid(), 42);
    assert!(StartClaim::take(&root.0, Duration::ZERO).unwrap().is_some());
}

#[test]
fn restart_reservation_rechecks_activity_after_acquiring_the_claim() {
    struct Disconnecting(AtomicU32);
    impl SessionActivity for Disconnecting {
        fn is_active(&self) -> bool {
            self.0.fetch_add(1, Ordering::SeqCst) == 0
        }
    }
    let root = Root::new("restart-disconnect");
    let mut locator = WorldLocator {
        world: World::default(),
        session: "own".into(),
        before: None,
        calls: 0,
    };
    assert!(matches!(
        reserve_restart(&root.0, &Disconnecting(AtomicU32::new(0)), &mut locator),
        Role::Wait(WaitReason::Inactive)
    ));
    assert_eq!(locator.calls, 0);
    assert!(StartClaim::take(&root.0, Duration::ZERO).unwrap().is_some());
}

#[test]
fn restart_permit_rechecks_activity_after_backoff() {
    let root = Root::new("restart-backoff-disconnect");
    let active = Activity(Arc::new(AtomicBool::new(true)));
    let mut locator = WorldLocator {
        world: World::default(),
        session: "own".into(),
        before: None,
        calls: 0,
    };
    let Role::Start(permit) = reserve_restart(&root.0, &active, &mut locator) else {
        panic!("active session gets the restart permit");
    };
    active.0.store(false, Ordering::SeqCst);
    assert_eq!(permit.refusal(&active), Some(WaitReason::Inactive));
}

/// One simulated session's manager.
struct Session {
    ownership: Ownership,
    active: Arc<AtomicBool>,
}

fn session(root: &Path, world: &World, user: &str, name: &str) -> Session {
    session_with(root, world, user, name, None)
}

fn session_with(
    root: &Path,
    world: &World,
    user: &str,
    name: &str,
    before: Option<Interleaving>,
) -> Session {
    let active = Arc::new(AtomicBool::new(true));
    let ownership = Ownership::new(
        root.to_path_buf(),
        ManagerSession {
            user: user.into(),
            session: name.into(),
        },
        Box::new(Activity(Arc::clone(&active))),
        Box::new(WorldLocator {
            world: world.clone(),
            session: name.into(),
            before,
            calls: 0,
        }),
    );
    Session { ownership, active }
}

fn outcome(role: &Role) -> String {
    match role {
        Role::Start(_) => "start".into(),
        Role::OwnSession { pid } => format!("own {pid}"),
        Role::Observe(observed) => format!("observe {}", observed.pid()),
        Role::Wait(reason) => format!("wait {reason:?}"),
    }
}

#[test]
fn two_sessions_racing_for_one_start_never_both_start() {
    let root = Root::new("race");
    let world = World::default();
    let pids = Arc::new(AtomicU32::new(100));
    for round in 0..40 {
        world.set(None);
        let barrier = Arc::new(Barrier::new(2));
        let outcomes: Vec<String> = ["1", "2"]
            .into_iter()
            .map(|name| {
                let (root, world, barrier, pids) = (
                    root.0.clone(),
                    world.clone(),
                    Arc::clone(&barrier),
                    Arc::clone(&pids),
                );
                thread::spawn(move || {
                    let mut manager = session(&root, &world, USER, name);
                    barrier.wait();
                    let role = manager.ownership.reassess();
                    let result = outcome(&role);
                    if let Role::Start(permit) = role {
                        // Launch, then hold the permit until the runtime is "ready".
                        let pid = pids.fetch_add(1, Ordering::SeqCst);
                        world.set(Some((pid, name)));
                        thread::sleep(Duration::from_millis(5));
                        drop(permit);
                    }
                    result
                })
            })
            .collect::<Vec<_>>()
            .into_iter()
            .map(|handle| handle.join().expect("session thread"))
            .collect();
        let starts = outcomes.iter().filter(|role| *role == "start").count();
        assert_eq!(starts, 1, "round {round}: {outcomes:?}");
        let other = outcomes
            .iter()
            .find(|role| *role != "start")
            .expect("the other session");
        assert!(
            other == "wait StartingElsewhere" || other.starts_with("observe "),
            "round {round}: {outcomes:?}"
        );
    }
}

#[test]
fn a_runtime_started_while_taking_the_claim_is_observed_not_started_again() {
    let root = Root::new("late-runtime");
    let world = World::default();
    // The first look finds nothing; by the look under the claim another session's
    // manager has started a runtime and released its claim.
    let mut manager = session_with(
        &root.0,
        &world,
        USER,
        "2",
        Some(Box::new(|world, call| {
            if call == 2 {
                world.set(Some((77, "1")));
            }
        })),
    );
    let role = manager.ownership.reassess();
    assert_eq!(outcome(&role), "observe 77");
    // The claim was released before the runtime was reported.
    assert!(
        StartClaim::take(&root.0, Duration::ZERO)
            .expect("take")
            .is_some()
    );
}

#[test]
fn an_observer_learns_the_runtime_ended_and_takes_over() {
    let root = Root::new("handoff");
    let world = World::default();
    let mut owner = session(&root.0, &world, USER, "1");
    let mut observer = session(&root.0, &world, USER, "2");
    let Role::Start(permit) = owner.ownership.reassess() else {
        panic!("the first session starts the runtime");
    };
    world.set(Some((42, "1")));
    drop(permit);
    assert_eq!(outcome(&owner.ownership.reassess()), "own 42");
    let Role::Observe(mut observed) = observer.ownership.reassess() else {
        panic!("the other session observes");
    };
    assert!(!observed.has_ended());
    // The owner's session ends and its runtime with it.
    world.set(None);
    assert!(observed.has_ended());
    assert_eq!(outcome(&observer.ownership.reassess()), "start");
}

#[test]
fn an_inactive_session_never_starts_the_runtime() {
    let root = Root::new("inactive");
    let world = World::default();
    let mut disconnected = session(&root.0, &world, USER, "2");
    disconnected.active.store(false, Ordering::SeqCst);
    assert_eq!(outcome(&disconnected.ownership.reassess()), "wait Inactive");
    // It still observes a runtime another session runs.
    world.set(Some((9, "1")));
    assert_eq!(outcome(&disconnected.ownership.reassess()), "observe 9");
    world.set(None);
    disconnected.active.store(true, Ordering::SeqCst);
    assert_eq!(outcome(&disconnected.ownership.reassess()), "start");
}

#[test]
fn quit_suppresses_automatic_starts_until_the_same_user_signs_in() {
    let root = Root::new("quit-sign-in");
    let world = World::default();
    let quitter = session(&root.0, &world, USER, "1");
    quitter.ownership.record_quit().expect("record quit");
    let QuitState::Present(marker) = read_quit_marker(&root.0) else {
        panic!("the marker is published");
    };
    assert_eq!((marker.user.as_str(), marker.session.as_str()), (USER, "1"));
    // Every session, including the quitter's, now leaves the runtime stopped.
    let mut other = session(&root.0, &world, USER, "2");
    assert_eq!(outcome(&other.ownership.reassess()), "wait Quit");
    let mut quitter = quitter;
    assert_eq!(outcome(&quitter.ownership.reassess()), "wait Quit");
    // A sign-in of another user leaves this user's Quit in force.
    let mut stranger = session(&root.0, &world, "S-1-5-21-9-9-9-1002", "3");
    assert_eq!(
        outcome(&stranger.ownership.begin(StartKind::SignIn).expect("begin")),
        "wait Quit"
    );
    // The same user signing in again clears it.
    let mut signed_in = session(&root.0, &world, USER, "4");
    assert_eq!(
        outcome(&signed_in.ownership.begin(StartKind::SignIn).expect("begin")),
        "start"
    );
    assert_eq!(read_quit_marker(&root.0), QuitState::Absent);
}

#[test]
fn a_manual_start_clears_any_quit() {
    let root = Root::new("quit-manual");
    let world = World::default();
    record_quit(
        &root.0,
        &QuitMarker {
            user: "S-1-5-21-9-9-9-1002".into(),
            session: "3".into(),
            set_at_ms: 1,
        },
    )
    .expect("record");
    let mut manager = session(&root.0, &world, USER, "1");
    assert_eq!(
        outcome(&manager.ownership.begin(StartKind::SignIn).expect("begin")),
        "wait Quit"
    );
    let role = manager.ownership.start_manually().expect("manual start");
    assert_eq!(outcome(&role), "start");
    drop(role);
    // A manual launch of the manager clears it as well.
    manager.ownership.record_quit().expect("record quit");
    let mut launched = session(&root.0, &world, USER, "2");
    assert_eq!(
        outcome(&launched.ownership.begin(StartKind::Manual).expect("begin")),
        "start"
    );
}

#[test]
fn an_unreadable_marker_suppresses_until_a_manual_start_replaces_it() {
    let root = Root::new("quit-unreadable");
    let world = World::default();
    std::fs::create_dir(root.0.join(".runtime")).expect("runtime directory");
    std::fs::write(
        root.0.join(".runtime").join("manager-quit.json"),
        b"{\"user\":1,\"user\":2}",
    )
    .expect("corrupt marker");
    let mut manager = session(&root.0, &world, USER, "1");
    assert_eq!(
        outcome(&manager.ownership.begin(StartKind::SignIn).expect("begin")),
        "wait QuitUnreadable"
    );
    assert_eq!(
        outcome(&manager.ownership.start_manually().expect("manual")),
        "start"
    );
}

#[test]
fn a_quit_recorded_while_taking_the_claim_holds() {
    let root = Root::new("quit-race");
    let world = World::default();
    let quit_root = root.0.clone();
    // Between the first look and the look under the claim, another session quits.
    let mut manager = session_with(
        &root.0,
        &world,
        USER,
        "2",
        Some(Box::new(move |_, call| {
            if call == 2 {
                record_quit(
                    &quit_root,
                    &QuitMarker {
                        user: USER.into(),
                        session: "1".into(),
                        set_at_ms: 5,
                    },
                )
                .expect("record");
            }
        })),
    );
    assert_eq!(outcome(&manager.ownership.reassess()), "wait Quit");
    assert!(
        StartClaim::take(&root.0, Duration::ZERO)
            .expect("take")
            .is_some()
    );
}

/// A helper process of this test binary, killed on drop if still running. Its output
/// stays open, so the helper never writes into a closed pipe.
struct Helper {
    child: Child,
    _output: Lines<BufReader<ChildStdout>>,
}

impl Helper {
    fn spawn(role: &str, target: &str) -> (Self, String) {
        let mut child = Command::new(std::env::current_exe().expect("test binary"))
            .args(["--exact", "helper", "--nocapture", "--test-threads=1"])
            .env(HELPER_ROLE, role)
            .env(HELPER_TARGET, target)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .expect("helper");
        let mut lines = BufReader::new(child.stdout.take().expect("helper stdout")).lines();
        let report = lines
            .by_ref()
            .map_while(Result::ok)
            .find_map(|line| {
                line.rsplit_once(REPORT)
                    .map(|(_, report)| report.to_owned())
            })
            .expect("helper report");
        (
            Self {
                child,
                _output: lines,
            },
            report,
        )
    }
}

impl Drop for Helper {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// Runs as a helper when a parent test selects a role: holds what it is told to until
/// its standard input closes or it is killed.
#[test]
fn helper() {
    let Ok(role) = std::env::var(HELPER_ROLE) else {
        return;
    };
    let target = std::env::var(HELPER_TARGET).expect("helper target");
    let report = |text: &str| println!("{REPORT}{text}");
    let held: Box<dyn std::any::Any> = match role.as_str() {
        "claim" => match StartClaim::take(Path::new(&target), Duration::ZERO).expect("take") {
            Some(claim) => Box::new(claim),
            None => {
                report("busy");
                return;
            }
        },
        "session" => match claim_session(&target, Duration::ZERO).expect("claim") {
            Some(lock) => Box::new(lock),
            None => {
                report("busy");
                return;
            }
        },
        "wait" => Box::new(()),
        other => panic!("unknown helper role {other}"),
    };
    report("holding");
    let _ = std::io::stdin().read_line(&mut String::new());
    drop(held);
}

#[test]
fn a_crashed_claim_holder_does_not_block_a_takeover() {
    let root = Root::new("crashed-holder");
    let world = World::default();
    let (holder, report) = Helper::spawn("claim", root.0.to_str().expect("UTF-8 root"));
    assert_eq!(report, "holding");
    let mut manager = session(&root.0, &world, USER, "2");
    assert_eq!(
        outcome(&manager.ownership.reassess()),
        "wait StartingElsewhere"
    );
    // Killed while holding: the claim is released by the kernel, not by the holder.
    drop(holder);
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        let role = manager.ownership.reassess();
        if matches!(role, Role::Start(_)) {
            break;
        }
        assert_eq!(outcome(&role), "wait StartingElsewhere");
        assert!(
            Instant::now() < deadline,
            "the crashed holder's claim stayed held"
        );
        thread::sleep(Duration::from_millis(20));
    }
}

/// Real processes held by handle: the session mutex, the observer and the locator.
#[cfg(windows)]
mod processes {
    use super::*;
    use cadrumo_manager::session::ownership::{BootRecordLocator, HandleObserver};
    use cadrumo_manager::supervision::process::open_process;

    #[test]
    fn a_crashed_session_lock_holder_passes_the_lock_on() {
        let manager_id = format!(
            "test.cadrumo.crashed-{}-{}.manager",
            std::process::id(),
            nanos()
        );
        let (holder, report) = Helper::spawn("session", &manager_id);
        assert_eq!(report, "holding");
        assert!(
            claim_session(&manager_id, Duration::from_millis(80))
                .expect("claim")
                .is_none(),
            "a second manager in the session took the lock"
        );
        drop(holder);
        assert!(
            claim_session(&manager_id, Duration::from_secs(5))
                .expect("claim")
                .is_some(),
            "the abandoned session lock was not taken"
        );
    }

    #[test]
    fn a_handle_observer_learns_the_process_ended() {
        let (mut helper, report) = Helper::spawn("wait", "");
        assert_eq!(report, "holding");
        let mut observer = HandleObserver::open(helper.child.id()).expect("observe");
        assert_eq!(observer.pid(), helper.child.id());
        assert!(!observer.has_ended());
        drop(helper.child.stdin.take());
        let deadline = Instant::now() + Duration::from_secs(10);
        while !observer.has_ended() {
            assert!(Instant::now() < deadline, "the end was not observed");
            thread::sleep(Duration::from_millis(20));
        }
    }

    #[test]
    fn the_boot_record_locator_places_a_live_runtime_in_this_session() {
        let root = Root::new("locator");
        let (mut helper, report) = Helper::spawn("wait", "");
        assert_eq!(report, "holding");
        let pid = helper.child.id();
        let created = open_process(pid).expect("inspect").identity.created;
        let runtime = root.0.join(".runtime");
        std::fs::create_dir(&runtime).expect("runtime directory");
        let write_record = |created: u64| {
            let record = serde_json::json!({
                "admission": "native",
                "boot_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
                "package_directory": null,
                "pid": pid,
                "process_created": created,
                "schema_version": 1,
                "version": "1.2.3",
            });
            std::fs::write(runtime.join("boot.json"), record.to_string()).expect("boot record");
        };
        let mut locator = BootRecordLocator::new(&root.0);
        write_record(created);
        assert!(matches!(locator.locate(), Located::OwnSession { pid: found } if found == pid));
        // A record naming another start of that pid is stale.
        write_record(created + 1);
        assert!(matches!(locator.locate(), Located::Nothing));
        write_record(created);
        drop(helper.child.stdin.take());
        let _ = helper.child.wait();
        assert!(matches!(locator.locate(), Located::Nothing));
    }
}
