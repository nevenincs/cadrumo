//! Real fixture-process coverage of ownership-to-supervisor startup composition.

use super::*;
use cadrumo_manager::session::ManagerSession;
use cadrumo_manager::session::ownership::{Ownership, StartKind};
use cadrumo_manager::startup::{self, Running, Start};

fn start(root: &Root, installed: bool) -> Start {
    let mut ownership = Ownership::new(
        root.path().to_path_buf(),
        ManagerSession::current().expect("the actual test-process session"),
        Box::new(Session(true)),
        Box::new(BootRecordLocator::new(root.path())),
    );
    let target = LaunchTarget::fixture(
        PathBuf::from(FIXTURE),
        root.path().to_path_buf(),
        identity(),
        VERSION.into(),
    )
    .expect("fixture launch target");
    startup::start(
        target,
        Case::default().config,
        Collaborators {
            session: Box::new(Session(true)),
            probe: Box::new(Probe(None)),
            versions: Box::new(Catalogue(installed)),
            stop_signal: Box::new(PlatformStopSignal::default()),
        },
        &mut ownership,
        Some(StartKind::Manual),
    )
    .expect("compose ownership with supervision")
}

/// Stop owned fixture children even when a case assertion unwinds.
struct OwnedRun {
    running: Running,
    finished: bool,
}

impl OwnedRun {
    fn new(started: Start) -> Self {
        let Start::Running(running) = started else {
            panic!("expected an owned supervisor");
        };
        Self {
            running,
            finished: false,
        }
    }

    fn finish(
        &mut self,
        mut script: impl FnMut(&Event, &SupervisorHandle),
    ) -> (Vec<Seen>, Outcome) {
        let started = Instant::now();
        let mut seen = Vec::new();
        loop {
            assert!(started.elapsed() < CASE_LIMIT, "startup case did not end");
            match self.running.events.recv_timeout(Duration::from_millis(10)) {
                Ok(event) => {
                    script(&event, &self.running.handle);
                    seen.push(Seen {
                        event,
                        at: Instant::now(),
                    });
                }
                Err(RecvTimeoutError::Disconnected | RecvTimeoutError::Timeout) => {}
            }
            if let Ok(result) = self.running.ended.try_recv() {
                self.finished = true;
                self.running.join().expect("join the composed supervisor");
                for event in self.running.events.try_iter() {
                    script(&event, &self.running.handle);
                    seen.push(Seen {
                        event,
                        at: Instant::now(),
                    });
                }
                return (
                    seen,
                    result.expect("supervisor completed without an I/O failure"),
                );
            }
        }
    }
}

impl Drop for OwnedRun {
    fn drop(&mut self) {
        if !self.finished {
            self.running.handle.request(Request::SessionEnd);
            if self.running.ended.recv_timeout(CASE_LIMIT).is_ok() {
                let _ = self.running.join();
            }
        }
    }
}

#[test]
fn startup_launches_once_and_session_end_stops_the_ready_runtime() {
    let root = Root::new(&["serve"]);
    let mut running = OwnedRun::new(start(&root, true));
    let (seen, outcome) = running.finish(|event, handle| {
        if matches!(event, Event::Ready { .. }) {
            assert!(handle.request(Request::SessionEnd));
        }
    });
    assert_eq!(
        outcome,
        Outcome::Stopped {
            effects: Effects::Unknown
        }
    );
    assert_eq!(root.launches(), 1);
    assert_eq!(
        count(&seen, |event| matches!(event, Event::Ready { .. })),
        1
    );
    assert!(restarts(&seen).is_empty());
    assert_eq!(
        exits(&seen),
        [RuntimeExit::Reason(ExitReason::SessionEndSettle)]
    );
    assert!(seen.iter().any(|seen| matches!(
        seen.event,
        Event::StopRequested {
            cause: StopCause::SessionEnd,
            path: StopPath::Channel,
            ..
        }
    )));
    assert!(
        StartClaim::take(root.path(), Duration::ZERO)
            .unwrap()
            .is_some()
    );
}

#[test]
fn startup_waits_for_a_competing_claim_without_spawning() {
    let root = Root::new(&["serve"]);
    let claim = StartClaim::take(root.path(), Duration::ZERO)
        .expect("take the competing claim")
        .expect("isolated root claim");
    match start(&root, true) {
        Start::Waiting(Role::Wait(WaitReason::StartingElsewhere)) => {}
        Start::Waiting(other) => panic!("unexpected startup role: {other:?}"),
        Start::Running(running) => {
            let _cleanup = OwnedRun {
                running,
                finished: false,
            };
            panic!("a competing claim must prevent supervisor startup");
        }
    }
    assert_eq!(root.launches(), 0);
    drop(claim);
    assert!(
        StartClaim::take(root.path(), Duration::ZERO)
            .unwrap()
            .is_some()
    );
}

#[test]
fn startup_adopts_its_existing_session_without_a_competing_launch() {
    let root = Root::new(&["serve"]);
    let mut incumbent = Incumbent::start(&root);
    let pid = incumbent.child.id();
    let mut running = OwnedRun::new(start(&root, true));
    let (seen, outcome) = running.finish(|event, handle| {
        if matches!(event, Event::Adopted { .. }) {
            assert!(handle.request(Request::SessionEnd));
        }
    });
    assert_eq!(
        outcome,
        Outcome::Stopped {
            effects: Effects::Unknown
        }
    );
    assert_eq!(root.launches(), 1, "only the incumbent was launched");
    assert_eq!(
        count(&seen, |event| matches!(event, Event::Launched { .. })),
        0
    );
    assert!(seen.iter().any(|seen| seen.event
        == Event::Adopted {
            pid,
            version: VERSION.into()
        }));
    assert!(!incumbent.running());
    assert!(restarts(&seen).is_empty());
}

#[test]
fn startup_reports_a_foreign_incumbent_without_signalling_or_launching() {
    for (plan, installed, reason) in [
        (
            "serve admission=development",
            true,
            ForeignReason::DevelopmentAdmission,
        ),
        ("serve", false, ForeignReason::NotInstalled),
    ] {
        let root = Root::new(&[plan]);
        let mut incumbent = Incumbent::start(&root);
        let mut running = OwnedRun::new(start(&root, installed));
        let (seen, outcome) = running.finish(|_, _| {});
        assert_eq!(outcome, Outcome::Foreign(reason));
        assert_eq!(
            root.launches(),
            1,
            "only the foreign incumbent was launched"
        );
        assert!(incumbent.running(), "foreign incumbent must remain alive");
        assert!(!seen.iter().any(|seen| matches!(
            seen.event,
            Event::Launched { .. } | Event::StopRequested { .. } | Event::Terminated { .. }
        )));
    }
}

fn flooded_runtime(
    root: &Root,
) -> (
    OwnedRun,
    cadrumo_manager::supervision::process::RuntimeProcess,
) {
    use cadrumo_manager::supervision::process::{RuntimeProcess, open_process};
    let owned = OwnedRun::new(start(root, true));
    let pid = loop {
        if let Event::Launched { pid, .. } = owned.running.events.recv_timeout(CASE_LIMIT).unwrap()
        {
            break pid;
        }
    };
    let held = RuntimeProcess::Adopted(open_process(pid).expect("hold the exact flooded child"));
    let deadline = Instant::now() + CASE_LIMIT;
    while !root.path().join("fixture-flood-written").exists() {
        assert!(
            Instant::now() < deadline,
            "announcement flood did not complete"
        );
        thread::sleep(Duration::from_millis(5));
    }
    (owned, held)
}

#[test]
fn a_slow_observer_has_bounded_events_and_does_not_delay_runtime_stop() {
    let root = Root::new(&["serve busy announcement_flood=8192"]);
    let (mut owned, mut held) = flooded_runtime(&root);
    let deadline = Instant::now() + CASE_LIMIT;
    while !owned.running.handle.request(Request::Stop) {
        assert!(
            Instant::now() < deadline,
            "ordinary stop could not be queued"
        );
        thread::yield_now();
    }
    let outcome = owned
        .running
        .ended
        .recv_timeout(CASE_LIMIT)
        .unwrap()
        .unwrap();
    owned.running.join().unwrap();
    owned.finished = true;
    assert_eq!(outcome, SETTLED);
    assert!(
        held.try_exit().unwrap().is_some(),
        "the exact child must be reaped"
    );
    assert!(owned.running.events.try_iter().count() <= EVENT_QUEUE);
    assert!(owned.running.handle.take_dropped_events() > 0);
    assert_eq!(owned.running.handle.take_dropped_events(), 0);
    assert!(
        !owned.running.handle.request(Request::Stop),
        "completed input queue must disconnect"
    );
}

#[test]
fn saturated_input_preserves_session_end_and_persists_dropped_observations() {
    use cadrumo_application::diagnostics::{DiagnosticSource, Diagnostics};
    let root = Root::new(&["serve busy announcement_flood=8192"]);
    let (mut owned, mut held) = flooded_runtime(&root);
    let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
    let log = root.path().join(cadrumo_manager::contract::MANAGER_LOG);
    diagnostics
        .configure_file(&log, 4 * 1024 * 1024, 1)
        .unwrap();
    let mut saturated = false;
    for _ in 0..INPUT_QUEUE * 1024 {
        if !owned.running.handle.request(Request::StopIfIdle) {
            saturated = true;
            break;
        }
    }
    assert!(
        saturated,
        "control flood must reach the bounded input queue"
    );
    assert!(owned.running.handle.request(Request::SessionEnd));
    assert!(cadrumo_manager::background::settle_session(
        &mut owned.running,
        &diagnostics,
        CASE_LIMIT,
    ));
    owned.finished = true;
    assert!(
        held.try_exit().unwrap().is_some(),
        "session end must settle the exact child"
    );
    assert_eq!(root.launches(), 1, "session end must suppress restart");
    assert_eq!(owned.running.handle.take_dropped_events(), 0);
    let text = fs::read_to_string(log).unwrap();
    let dropped = text
        .lines()
        .map(|line| serde_json::from_str::<Value>(line).unwrap())
        .find(|row| row["lifecycle"]["event"] == "events_dropped")
        .expect("bounded event loss must be visible in the durable manager log");
    assert!(dropped["lifecycle"]["count"].as_u64().unwrap() > 0);
    assert_eq!(dropped["kind"], "failure");
}

#[test]
fn session_end_settles_before_logging_and_preserves_final_facts_with_a_refused_sink() {
    use cadrumo_application::diagnostics::{DiagnosticSource, Diagnostics};
    for writable in [true, false] {
        let root = Root::new(&["serve"]);
        let mut owned = OwnedRun::new(start(&root, true));
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        diagnostics.host_event(
            cadrumo_application::diagnostics::EventKind::HostStarted,
            cadrumo_application::diagnostics::HostStage::Admission,
        );
        let log = if writable {
            root.path().join(cadrumo_manager::contract::MANAGER_LOG)
        } else {
            root.path().join("fixture-plan").join("refused.log")
        };
        let configured = diagnostics.configure_file(&log, 65536, 1);
        if writable {
            configured.unwrap();
        } else {
            diagnostics.failure(configured.unwrap_err());
        }
        loop {
            let event = owned.running.events.recv_timeout(CASE_LIMIT).unwrap();
            cadrumo_manager::diagnostics::supervision_event(&diagnostics, &event);
            if matches!(event, Event::Ready { .. }) {
                break;
            }
        }
        assert!(cadrumo_manager::background::settle_session(
            &mut owned.running,
            &diagnostics,
            CASE_LIMIT
        ));
        owned.finished = true;
        assert_eq!(root.launches(), 1);
        let snapshot = diagnostics.snapshot(0);
        let facts = snapshot
            .events
            .iter()
            .filter_map(|event| event.lifecycle)
            .collect::<Vec<_>>();
        use cadrumo_application::diagnostics::lifecycle::{
            Effects as LogEffects, LifecycleFact, RuntimeExit as LogExit, RuntimeReason,
            SupervisorOutcome,
        };
        let end = facts
            .iter()
            .position(|fact| matches!(fact, LifecycleFact::SessionEndRequested {}))
            .unwrap();
        let exit = facts
            .iter()
            .position(|fact| {
                matches!(
                    fact,
                    LifecycleFact::Exited {
                        exit: LogExit::Reason {
                            reason: RuntimeReason::SessionEndSettle,
                            ..
                        },
                        ..
                    }
                )
            })
            .unwrap();
        let outcome = facts
            .iter()
            .position(|fact| {
                matches!(
                    fact,
                    LifecycleFact::SupervisorEnded {
                        result: SupervisorOutcome::Stopped {
                            effects: LogEffects::Unknown
                        }
                    }
                )
            })
            .unwrap();
        assert!(end < exit && exit < outcome);
        assert!(
            StartClaim::take(root.path(), Duration::ZERO)
                .unwrap()
                .is_some()
        );
        if writable {
            let text = fs::read_to_string(log).unwrap();
            assert!(text.contains("session_end_settle") && text.contains("supervisor_ended"));
        } else {
            assert!(snapshot.log_failure.is_some());
            assert!(snapshot.paths.is_none());
        }
    }
}
