//! The supervision core against fixture runtimes in isolated synthetic roots.
//!
//! Each case launches real child processes of the fixture image, which speak the runtime's
//! line protocol and follow one plan line per launch. Synthetic roots hold no profiles and
//! are removed afterwards; every fixture process is ended during teardown.
#![cfg(windows)]

use cadrumo_manager::contract::{
    CLEARED_NAMES, CLEARED_PREFIXES, HOST_INHERITED_ENV, NAMESPACE_PREFIX, PINNED_ENV,
    RESERVED_ENV, ROOT_VARIABLE,
};
use cadrumo_manager::session::claim::StartClaim;
use cadrumo_manager::session::ownership::{BootRecordLocator, Role, WaitReason, reserve_restart};
use cadrumo_manager::session::quit::{QuitMarker, record_quit};
use cadrumo_manager::supervision::adoption::{ForeignReason, InstalledVersion, InstalledVersions};
use cadrumo_manager::supervision::exit::{ExitReason, RuntimeExit};
use cadrumo_manager::supervision::launch::LaunchTarget;
use cadrumo_manager::supervision::restart::{RestartClass, RestartPolicy};
use cadrumo_manager::supervision::stop::PlatformStopSignal;
use cadrumo_manager::supervision::supervisor::{
    Collaborators, Effects, Event, Outcome, Request, SessionActivity, StandDownReason, StopCause,
    StopPath, Supervisor, SupervisorConfig, SupervisorHandle, VersionProbe,
};
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::time::{Duration, Instant};
use std::{env, fs, process, thread};

const FIXTURE: &str = env!("CARGO_BIN_EXE_cadrumo-manager-fixture");
const VERSION: &str = "0.5.1";
const CASE_LIMIT: Duration = Duration::from_secs(60);
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const DETACHED_PROCESS: u32 = 0x0000_0008;

fn identity() -> String {
    "ab".repeat(32)
}

/// An isolated synthetic storage root, removed on drop.
struct Root(PathBuf);

impl Root {
    fn new(plan: &[&str]) -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let path = env::temp_dir().join(format!(
            "cadrumo-manager-supervision-{}-{}",
            process::id(),
            NEXT.fetch_add(1, Ordering::SeqCst)
        ));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).expect("create a synthetic root");
        fs::write(path.join("fixture-plan"), plan.join("\n")).expect("write the plan");
        Self(path)
    }

    fn path(&self) -> &Path {
        &self.0
    }

    fn launch_record(&self, index: usize) -> Value {
        let raw = fs::read_to_string(self.0.join(format!("fixture-launch-{index}")))
            .expect("read a launch record");
        serde_json::from_str(&raw).expect("launch record JSON")
    }

    fn launches(&self) -> usize {
        (0..)
            .take_while(|index| self.0.join(format!("fixture-launch-{index}")).exists())
            .count()
    }
}

impl Drop for Root {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

struct Session(bool);

impl SessionActivity for Session {
    fn is_active(&self) -> bool {
        self.0
    }
}

struct Probe(Option<&'static str>);

impl VersionProbe for Probe {
    fn reprobe(&mut self) -> Option<String> {
        self.0.map(str::to_owned)
    }
}

/// The fixture image is the runtime of one complete installed version, or of none.
struct Catalogue(bool);

impl InstalledVersions for Catalogue {
    fn containing(&self, image: &Path) -> Option<InstalledVersion> {
        let fixture = PathBuf::from(FIXTURE);
        (self.0 && fs::canonicalize(image).ok()? == fs::canonicalize(&fixture).ok()?).then(|| {
            InstalledVersion {
                version: VERSION.into(),
                package_root: fixture.parent().expect("fixture directory").to_path_buf(),
                runtime_image: fixture,
            }
        })
    }

    fn failed(&self, _version: &str) -> bool {
        false
    }
}

struct Case {
    config: SupervisorConfig,
    session: bool,
    probe: Option<&'static str>,
    installed: bool,
    initial_permit: bool,
}

impl Default for Case {
    fn default() -> Self {
        Self {
            config: SupervisorConfig {
                readiness_ceiling: Duration::from_secs(20),
                heartbeat_interval: Duration::from_millis(30),
                heartbeat_staleness: Duration::from_millis(600),
                accept_tick_ceiling: Duration::from_millis(500),
                drain_bound: Duration::from_millis(1500),
                termination_bound: Duration::from_secs(5),
                poll_interval: Duration::from_millis(10),
                restart: RestartPolicy {
                    initial_backoff: Duration::from_millis(20),
                    maximum_backoff: Duration::from_millis(160),
                    crash_loop_limit: 5,
                    crash_loop_window: Duration::from_secs(60),
                },
            },
            session: true,
            probe: None,
            installed: true,
            initial_permit: false,
        }
    }
}

/// One observed event and when the test thread received it.
struct Seen {
    event: Event,
    at: Instant,
}

impl Case {
    /// Run the core on `root`, letting `script` answer events, until an outcome.
    fn run(
        self,
        root: &Root,
        mut script: impl FnMut(&Event, &SupervisorHandle),
    ) -> (Vec<Seen>, Outcome) {
        let target = LaunchTarget::fixture(
            PathBuf::from(FIXTURE),
            root.path().to_path_buf(),
            identity(),
            VERSION.into(),
        )
        .expect("fixture target");
        let collaborators = Collaborators {
            session: Box::new(Session(self.session)),
            probe: Box::new(Probe(self.probe)),
            versions: Box::new(Catalogue(self.installed)),
            stop_signal: Box::new(PlatformStopSignal::default()),
        };
        let (events, observed) = mpsc::channel();
        let mut supervisor = Supervisor::new(self.config, target, collaborators, events);
        let handle = supervisor.handle();
        let permit = self.initial_permit.then(|| {
            let Role::Start(permit) = reserve_restart(
                root.path(),
                &Session(self.session),
                &mut BootRecordLocator::new(root.path()),
            ) else {
                panic!("initial start permit");
            };
            permit
        });
        let running = thread::spawn(move || match permit {
            Some(permit) => supervisor
                .run_with_permit(permit)
                .expect("matching pinned root"),
            None => supervisor.run(),
        });
        let started = Instant::now();
        let mut seen = Vec::new();
        loop {
            assert!(started.elapsed() < CASE_LIMIT, "the case did not end");
            match observed.recv_timeout(Duration::from_millis(10)) {
                Ok(event) => {
                    script(&event, &handle);
                    seen.push(Seen {
                        event,
                        at: Instant::now(),
                    });
                }
                Err(RecvTimeoutError::Disconnected) => break,
                Err(RecvTimeoutError::Timeout) => {}
            }
        }
        (seen, running.join().expect("the supervisor thread"))
    }
}

fn events(seen: &[Seen]) -> Vec<&Event> {
    seen.iter().map(|seen| &seen.event).collect()
}

fn count(seen: &[Seen], matches: impl Fn(&Event) -> bool) -> usize {
    seen.iter().filter(|seen| matches(&seen.event)).count()
}

fn restarts(seen: &[Seen]) -> Vec<RestartClass> {
    seen.iter()
        .filter_map(|seen| match seen.event {
            Event::RestartScheduled { class, .. } => Some(class),
            _ => None,
        })
        .collect()
}

fn exits(seen: &[Seen]) -> Vec<RuntimeExit> {
    seen.iter()
        .filter_map(|seen| match seen.event {
            Event::Exited { exit, .. } => Some(exit),
            _ => None,
        })
        .collect()
}

/// Stop once the `n`th runtime reports ready.
fn stop_on_ready(n: usize) -> impl FnMut(&Event, &SupervisorHandle) {
    let mut ready = 0;
    move |event, handle| {
        if matches!(event, Event::Ready { .. }) {
            ready += 1;
            if ready == n {
                handle.request(Request::Stop);
            }
        }
    }
}

const SETTLED: Outcome = Outcome::Stopped {
    effects: Effects::Settled,
};

#[test]
fn stop_drains_a_ready_runtime_over_the_channel() {
    let root = Root::new(&["serve"]);
    let (seen, outcome) = Case::default().run(&root, stop_on_ready(1));
    assert_eq!(outcome, SETTLED);
    assert_eq!(
        count(&seen, |event| matches!(
            event,
            Event::BootRecordConfirmed { .. }
        )),
        1
    );
    assert_eq!(
        count(&seen, |event| matches!(
            event,
            Event::StopRequested {
                cause: StopCause::Requested,
                path: StopPath::Channel,
                ..
            }
        )),
        1
    );
    assert!(seen.iter().any(|seen| matches!(
        seen.event,
        Event::Exited {
            exit: RuntimeExit::Reason(ExitReason::SupervisorStop),
            announced: Some(ExitReason::SupervisorStop),
            ..
        }
    )));
    assert!(!seen.iter().any(|seen| matches!(
        seen.event,
        Event::CommandRefused(_) | Event::AnnouncementRefused(_) | Event::HangDetected { .. }
    )));
    assert_eq!(root.launches(), 1);
}

#[test]
fn the_runtime_gets_the_supervised_arguments_and_canonical_strict_environment() {
    let root = Root::new(&["serve"]);
    let (_, outcome) = Case::default().run(&root, stop_on_ready(1));
    assert_eq!(outcome, SETTLED);
    let launch = root.launch_record(0);
    let arguments: Vec<&str> = launch["arguments"]
        .as_array()
        .expect("arguments")
        .iter()
        .map(|argument| argument.as_str().expect("argument"))
        .collect();
    let root_text = root.path().to_string_lossy();
    let identity = identity();
    assert_eq!(
        arguments,
        [
            "--storage-root",
            &root_text,
            "--storage-identity",
            &identity,
            "--expected-version",
            VERSION,
            "--supervised",
        ]
    );
    let environment = launch["environment"].as_array().expect("environment");
    assert_eq!(launch["pinned_root"].as_str(), Some(root_text.as_ref()));
    assert!(!environment.is_empty());
    for name in environment {
        let name = name.as_str().expect("variable name");
        if !PINNED_ENV.contains(&name) {
            assert!(
                !CLEARED_NAMES.contains(&name) && !RESERVED_ENV.contains(&name),
                "{name}"
            );
            assert!(
                !CLEARED_PREFIXES
                    .iter()
                    .any(|prefix| name.starts_with(prefix)),
                "{name}"
            );
            assert!(!name.starts_with(NAMESPACE_PREFIX), "{name}");
        }
        assert!(
            !HOST_INHERITED_ENV.contains(&name),
            "fixtures inherit no authority pin"
        );
    }
    assert!(
        environment
            .iter()
            .any(|name| name.as_str() == Some(ROOT_VARIABLE))
    );
}

#[test]
fn stop_if_idle_stops_an_idle_runtime() {
    let root = Root::new(&["serve"]);
    let (seen, outcome) = Case::default().run(&root, |event, handle| {
        if matches!(event, Event::Ready { .. }) {
            handle.request(Request::StopIfIdle);
        }
    });
    assert_eq!(outcome, SETTLED);
    assert_eq!(
        exits(&seen),
        [RuntimeExit::Reason(ExitReason::SupervisorStop)]
    );
    assert_eq!(count(&seen, |event| matches!(event, Event::Busy { .. })), 0);
}

#[test]
fn stop_if_idle_leaves_a_busy_runtime_serving() {
    let root = Root::new(&["serve busy"]);
    let (seen, outcome) = Case::default().run(&root, |event, handle| match event {
        Event::Ready { .. } => {
            handle.request(Request::StopIfIdle);
        }
        Event::Busy { .. } => {
            // Keep supervising through several heartbeats before the real stop.
            thread::sleep(Duration::from_millis(200));
            handle.request(Request::Stop);
        }
        _ => {}
    });
    assert_eq!(outcome, SETTLED);
    let order: Vec<_> = events(&seen)
        .into_iter()
        .filter(|event| matches!(event, Event::Busy { .. } | Event::StopRequested { .. }))
        .collect();
    assert!(matches!(
        order.as_slice(),
        [Event::Busy { .. }, Event::StopRequested { .. }]
    ));
    assert_eq!(root.launches(), 1);
}

#[test]
fn a_crash_restarts_with_backoff_and_leaves_effects_unknown() {
    let root = Root::new(&["exit code=3221225477 after_ready", "serve"]);
    let (seen, outcome) = Case::default().run(&root, stop_on_ready(2));
    assert_eq!(outcome, SETTLED);
    assert_eq!(restarts(&seen), [RestartClass::Unexpected]);
    assert_eq!(exits(&seen)[0], RuntimeExit::Crash(0xC000_0005));
    assert_eq!(
        count(&seen, |event| matches!(event, Event::EffectsUnknown { .. })),
        1
    );
    assert_eq!(root.launches(), 2);
}

#[test]
fn restart_holds_the_claim_through_backoff_and_releases_it_at_readiness() {
    let root = Root::new(&["exit code=3221225477 after_ready", "serve"]);
    let mut ready = 0;
    let (seen, outcome) = Case::default().run(&root, |event, handle| match event {
        Event::RestartScheduled { .. } => {
            assert!(
                StartClaim::take(root.path(), Duration::ZERO)
                    .unwrap()
                    .is_none()
            );
        }
        Event::Ready { .. } => {
            ready += 1;
            if ready == 2 {
                assert!(
                    StartClaim::take(root.path(), Duration::ZERO)
                        .unwrap()
                        .is_some()
                );
                handle.request(Request::Stop);
            }
        }
        _ => {}
    });
    assert_eq!(outcome, SETTLED);
    assert_eq!(restarts(&seen), [RestartClass::Unexpected]);
    assert_eq!(root.launches(), 2);
}

#[test]
fn a_contended_restart_claim_never_launches_again() {
    let root = Root::new(&["exit code=3221225477 after_ready", "serve"]);
    let held = StartClaim::take(root.path(), Duration::ZERO)
        .unwrap()
        .unwrap();
    let (seen, outcome) = Case::default().run(&root, |_, _| {});
    assert_eq!(
        outcome,
        Outcome::RestartDeferred(WaitReason::StartingElsewhere)
    );
    assert!(restarts(&seen).is_empty());
    assert_eq!(root.launches(), 1);
    drop(held);
}

#[test]
fn quit_during_backoff_suppresses_the_restart_and_releases_the_claim() {
    let root = Root::new(&["exit code=3221225477 after_ready", "serve"]);
    let mut case = Case::default();
    case.config.restart.initial_backoff = Duration::from_millis(500);
    case.config.restart.maximum_backoff = Duration::from_millis(500);
    let (_, outcome) = case.run(&root, |event, _| {
        if matches!(event, Event::RestartScheduled { .. }) {
            record_quit(
                root.path(),
                &QuitMarker {
                    user: "test-user".into(),
                    session: "1".into(),
                    set_at_ms: 1,
                },
            )
            .unwrap();
        }
    });
    assert_eq!(outcome, Outcome::RestartDeferred(WaitReason::Quit));
    assert_eq!(root.launches(), 1);
    assert!(
        StartClaim::take(root.path(), Duration::ZERO)
            .unwrap()
            .is_some()
    );
}

#[test]
fn stopping_during_backoff_releases_the_restart_claim() {
    let root = Root::new(&["exit code=3221225477 after_ready", "serve"]);
    let (_, outcome) = Case::default().run(&root, |event, handle| {
        if matches!(event, Event::RestartScheduled { .. }) {
            handle.request(Request::Stop);
        }
    });
    assert_eq!(outcome, SETTLED);
    assert_eq!(root.launches(), 1);
    assert!(
        StartClaim::take(root.path(), Duration::ZERO)
            .unwrap()
            .is_some()
    );
}

#[test]
fn an_initial_permit_survives_a_pre_ready_failure_without_self_contention() {
    let root = Root::new(&["exit code=1", "serve"]);
    let case = Case {
        initial_permit: true,
        ..Case::default()
    };
    let (seen, outcome) = case.run(&root, |event, handle| match event {
        Event::RestartScheduled { .. } => {
            assert!(
                StartClaim::take(root.path(), Duration::ZERO)
                    .unwrap()
                    .is_none()
            );
        }
        Event::Ready { .. } => {
            handle.request(Request::Stop);
        }
        _ => {}
    });
    assert_eq!(outcome, SETTLED);
    assert_eq!(root.launches(), 2);
    assert_eq!(restarts(&seen), [RestartClass::LaunchFailure]);
    assert!(
        StartClaim::take(root.path(), Duration::ZERO)
            .unwrap()
            .is_some()
    );
}

#[test]
fn a_stale_heartbeat_escalates_to_termination_and_restarts() {
    let root = Root::new(&["serve hang_after=3 hang=hard", "serve"]);
    let (seen, outcome) = Case::default().run(&root, stop_on_ready(2));
    assert_eq!(outcome, SETTLED);
    let order: Vec<_> = events(&seen)
        .into_iter()
        .filter(|event| {
            matches!(
                event,
                Event::HangDetected { .. }
                    | Event::StopRequested { .. }
                    | Event::Terminated { .. }
                    | Event::EffectsUnknown { .. }
                    | Event::RestartScheduled { .. }
            )
        })
        .take(5)
        .collect();
    assert!(
        matches!(
            order.as_slice(),
            [
                Event::HangDetected { ready: true, .. },
                Event::StopRequested {
                    cause: StopCause::Hang,
                    path: StopPath::Channel,
                    ..
                },
                Event::Terminated { .. },
                Event::EffectsUnknown { .. },
                Event::RestartScheduled {
                    class: RestartClass::Hang,
                    ..
                },
            ]
        ),
        "{order:?}"
    );
    assert_eq!(exits(&seen)[0], RuntimeExit::Terminated);
}

#[test]
fn a_hung_runtime_that_still_drains_is_not_terminated() {
    let root = Root::new(&["serve hang_after=2 hang=drain", "serve"]);
    let (seen, outcome) = Case::default().run(&root, stop_on_ready(2));
    assert_eq!(outcome, SETTLED);
    assert_eq!(
        count(&seen, |event| matches!(event, Event::Terminated { .. })),
        0
    );
    assert_eq!(
        exits(&seen)[0],
        RuntimeExit::Reason(ExitReason::DrainWatchdog)
    );
    assert_eq!(restarts(&seen), [RestartClass::Hang]);
    assert_eq!(
        count(&seen, |event| matches!(event, Event::EffectsUnknown { .. })),
        1
    );
}

#[test]
fn an_accept_loop_that_stopped_turning_counts_as_a_hang() {
    let root = Root::new(&["serve tick_age_ms=60000", "serve"]);
    let (seen, outcome) = Case::default().run(&root, stop_on_ready(2));
    assert_eq!(outcome, SETTLED);
    assert_eq!(restarts(&seen), [RestartClass::Hang]);
}

#[test]
fn no_readiness_within_the_ceiling_is_a_hang() {
    let root = Root::new(&["silent", "serve"]);
    let mut case = Case::default();
    case.config.readiness_ceiling = Duration::from_millis(500);
    let (seen, outcome) = case.run(&root, stop_on_ready(1));
    assert_eq!(outcome, SETTLED);
    assert!(
        seen.iter()
            .any(|seen| matches!(seen.event, Event::HangDetected { ready: false, .. }))
    );
    assert_eq!(exits(&seen)[0], RuntimeExit::Terminated);
    assert_eq!(restarts(&seen), [RestartClass::Hang]);
}

#[test]
fn stops_the_manager_did_not_send_restart_as_outside_stops() {
    let root = Root::new(&[
        "exit code=65 after_ready",
        "exit code=0 after_ready",
        "exit code=3221225786 after_ready",
        "serve",
    ]);
    let (seen, outcome) = Case::default().run(&root, stop_on_ready(4));
    assert_eq!(outcome, SETTLED);
    assert_eq!(restarts(&seen), [RestartClass::OutsideStop; 3]);
    assert_eq!(
        exits(&seen)[..3],
        [
            RuntimeExit::Reason(ExitReason::SignalStop),
            RuntimeExit::Zero,
            RuntimeExit::ControlC
        ]
    );
}

#[test]
fn witness_loss_restarts_while_the_session_is_active() {
    let root = Root::new(&["exit code=70 after_ready", "serve"]);
    let (seen, outcome) = Case::default().run(&root, stop_on_ready(2));
    assert_eq!(outcome, SETTLED);
    assert_eq!(restarts(&seen), [RestartClass::WitnessLoss]);
}

#[test]
fn witness_loss_waits_for_an_active_session() {
    let root = Root::new(&["exit code=70 after_ready", "serve"]);
    let case = Case {
        session: false,
        ..Case::default()
    };
    let (seen, outcome) = case.run(&root, |_, _| {});
    assert_eq!(outcome, Outcome::AwaitingActiveSession);
    assert!(restarts(&seen).is_empty());
    assert_eq!(root.launches(), 1);
}

#[test]
fn version_mismatch_reprobes_and_relaunches_once() {
    let root = Root::new(&["serve accept_version=0.9.0"]);
    let case = Case {
        probe: Some("0.9.0"),
        ..Case::default()
    };
    let (seen, outcome) = case.run(&root, stop_on_ready(1));
    assert_eq!(outcome, SETTLED);
    let launched: Vec<_> = seen
        .iter()
        .filter_map(|seen| match &seen.event {
            Event::Launched { version, .. } => Some(version.as_str()),
            _ => None,
        })
        .collect();
    assert_eq!(launched, [VERSION, "0.9.0"]);
    assert!(restarts(&seen).is_empty());
    assert_eq!(
        root.launch_record(1)["arguments"][5].as_str(),
        Some("0.9.0")
    );
}

#[test]
fn a_second_version_mismatch_stands_down() {
    let root = Root::new(&["serve accept_version=0.9.0"]);
    let case = Case {
        probe: Some("0.6.0"),
        ..Case::default()
    };
    let (_, outcome) = case.run(&root, |_, _| {});
    assert_eq!(
        outcome,
        Outcome::StoodDown(StandDownReason::VersionMismatch)
    );
    assert_eq!(root.launches(), 2);
}

#[test]
fn root_and_elevation_refusals_stand_down_without_restarting() {
    for (code, reason) in [
        (68, StandDownReason::RootMismatch),
        (72, StandDownReason::ElevatedTokenRefused),
    ] {
        let plan = format!("exit code={code}");
        let root = Root::new(&[plan.as_str(), "serve"]);
        let (seen, outcome) = Case::default().run(&root, |_, _| {});
        assert_eq!(outcome, Outcome::StoodDown(reason));
        assert!(restarts(&seen).is_empty());
        assert_eq!(root.launches(), 1);
    }
}

#[test]
fn the_crash_loop_ceiling_fails_after_backoff_on_monotonic_time() {
    let root = Root::new(&["exit code=73"]);
    let mut case = Case::default();
    case.config.restart.crash_loop_limit = 3;
    let (seen, outcome) = case.run(&root, |_, _| {});
    assert_eq!(
        outcome,
        Outcome::Failed {
            last: RestartClass::Unexpected
        }
    );
    assert_eq!(root.launches(), 4);
    let mut delays = Vec::new();
    for (index, observed) in seen.iter().enumerate() {
        if let Event::RestartScheduled { delay, .. } = observed.event {
            delays.push(delay);
            let next = seen[index..]
                .iter()
                .find(|later| matches!(later.event, Event::Launched { .. }))
                .expect("a relaunch follows each scheduled restart");
            assert!(next.at.duration_since(observed.at) >= delay.mul_f32(0.9));
        }
    }
    assert_eq!(delays, [20, 40, 80].map(Duration::from_millis));
}

/// A runtime the test starts itself, as another manager or a developer would.
struct Incumbent {
    child: Child,
    commands: Option<ChildStdin>,
}

impl Incumbent {
    /// Start the incumbent on launch line 0 and wait until it has published its boot record.
    fn start(root: &Root) -> Self {
        let identity = identity();
        let mut child = Command::new(FIXTURE)
            .args([
                "--storage-root",
                &root.path().to_string_lossy(),
                "--storage-identity",
                &identity,
                "--expected-version",
                VERSION,
                "--supervised",
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW)
            .spawn()
            .expect("start the incumbent");
        let mut line = String::new();
        BufReader::new(child.stdout.take().expect("incumbent stdout"))
            .read_line(&mut line)
            .expect("read the incumbent's first line");
        assert!(line.contains("\"ready\""), "{line}");
        let commands = child.stdin.take();
        Self { child, commands }
    }

    fn running(&mut self) -> bool {
        self.child.try_wait().expect("poll the incumbent").is_none()
    }

    fn stop(&mut self) {
        if let Some(mut commands) = self.commands.take() {
            commands
                .write_all(b"{\"type\":\"stop\"}\n")
                .expect("ask the incumbent to stop");
        }
    }
}

impl Drop for Incumbent {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

#[test]
fn owner_busy_adopts_a_matching_installed_runtime_and_restarts_after_it_exits() {
    let root = Root::new(&["serve", "exit code=67", "serve"]);
    let mut incumbent = Incumbent::start(&root);
    let incumbent_pid = incumbent.child.id();
    let mut ready = 0;
    let (seen, outcome) = Case::default().run(&root, |event, handle| match event {
        Event::Adopted { .. } => incumbent.stop(),
        Event::Ready { .. } => {
            ready += 1;
            handle.request(Request::Stop);
        }
        _ => {}
    });
    assert_eq!(outcome, SETTLED);
    assert_eq!(ready, 1);
    assert!(seen.iter().any(|seen| seen.event
        == Event::Adopted {
            pid: incumbent_pid,
            version: VERSION.into()
        }));
    assert_eq!(
        exits(&seen)[..2],
        [
            RuntimeExit::Reason(ExitReason::OwnerBusy),
            RuntimeExit::Reason(ExitReason::SupervisorStop)
        ]
    );
    assert_eq!(restarts(&seen), [RestartClass::Unexpected]);
}

/// Run one OWNER_BUSY launch against `incumbent` and return the outcome.
fn owner_busy(root: &Root, installed: bool) -> (Vec<Seen>, Outcome) {
    let case = Case {
        installed,
        ..Case::default()
    };
    case.run(root, |_, _| {})
}

#[test]
fn a_foreign_runtime_is_reported_and_never_stopped() {
    let cases: [(&str, bool, ForeignReason); 3] = [
        (
            "serve admission=development",
            true,
            ForeignReason::DevelopmentAdmission,
        ),
        ("serve forge_created", true, ForeignReason::IdentityMismatch),
        ("serve", false, ForeignReason::NotInstalled),
    ];
    for (incumbent_plan, installed, reason) in cases {
        let root = Root::new(&[incumbent_plan, "exit code=67"]);
        let mut incumbent = Incumbent::start(&root);
        let (seen, outcome) = owner_busy(&root, installed);
        assert_eq!(outcome, Outcome::Foreign(reason), "{incumbent_plan}");
        assert!(seen.iter().any(|seen| seen.event == Event::Foreign(reason)));
        assert!(
            incumbent.running(),
            "{incumbent_plan}: a foreign runtime was stopped"
        );
        assert!(!seen.iter().any(|seen| matches!(
            seen.event,
            Event::StopRequested { .. } | Event::Terminated { .. }
        )));
    }
}

#[test]
fn a_record_whose_process_is_gone_is_stale() {
    let root = Root::new(&["serve", "exit code=67"]);
    let mut incumbent = Incumbent::start(&root);
    incumbent.child.kill().expect("end the incumbent");
    incumbent.child.wait().expect("reap the incumbent");
    let (_, outcome) = owner_busy(&root, true);
    assert_eq!(outcome, Outcome::Foreign(ForeignReason::StaleRecord));
}

#[test]
fn an_absent_or_forged_record_is_foreign() {
    let root = Root::new(&["exit code=67"]);
    let (_, outcome) = owner_busy(&root, true);
    assert_eq!(outcome, Outcome::Foreign(ForeignReason::RecordAbsent));

    let root = Root::new(&["exit code=67"]);
    let runtime_directory = root.path().join(".runtime");
    fs::create_dir_all(&runtime_directory).expect("create .runtime");
    let repeated = format!(
        "{{\"admission\":\"native\",\"boot_id\":\"0f8fad5b-d9cb-469f-a165-70867728950e\",\
         \"package_directory\":null,\"pid\":{pid},\"pid\":{pid},\"process_created\":1,\
         \"schema_version\":1,\"version\":\"{VERSION}\"}}",
        pid = process::id()
    );
    fs::write(runtime_directory.join("boot.json"), repeated).expect("write a forged record");
    let (_, outcome) = owner_busy(&root, true);
    assert_eq!(outcome, Outcome::Foreign(ForeignReason::RecordUnreadable));
}

#[test]
fn a_stop_without_a_channel_reaches_the_runtime_as_console_ctrl_c() {
    // The harness runs the core detached from any console, as the GUI-subsystem manager
    // does, so it can attach to the runtime's own console.
    let root = Root::new(&["serve close_announcements"]);
    let output = Command::new(FIXTURE)
        .args([
            "--harness",
            "stop-without-channel",
            &root.path().to_string_lossy(),
            &identity(),
            VERSION,
        ])
        .stdin(Stdio::null())
        .stderr(Stdio::null())
        .creation_flags(DETACHED_PROCESS)
        .output()
        .expect("run the harness");
    let report = String::from_utf8(output.stdout).expect("UTF-8 report");
    assert!(output.status.success(), "{report}");
    assert!(
        report.contains("cause: Requested, path: Signal"),
        "{report}"
    );
    assert!(report.contains("exit: Reason(SignalStop)"), "{report}");
    assert!(
        report
            .lines()
            .last()
            .is_some_and(|line| line == "outcome Stopped { effects: Settled }"),
        "{report}"
    );
}
