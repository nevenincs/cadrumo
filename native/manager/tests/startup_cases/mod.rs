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
