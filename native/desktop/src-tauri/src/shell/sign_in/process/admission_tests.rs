use super::{tests::powershell, *};
use std::{
    fs,
    path::PathBuf,
    sync::mpsc,
    time::{SystemTime, UNIX_EPOCH},
};

struct BarrierChild {
    directory: PathBuf,
}
impl BarrierChild {
    fn new() -> Self {
        let directory = std::env::temp_dir().join(format!(
            "cadrumo-sign-in-admission-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&directory).unwrap();
        Self { directory }
    }
    fn command(&self) -> Command {
        let mut command = powershell(
            "[IO.File]::WriteAllText($env:CADRUMO_TEST_READY, ''); $until=[DateTime]::UtcNow.AddSeconds(20); while (-not [IO.File]::Exists($env:CADRUMO_TEST_RELEASE)) { if ([DateTime]::UtcNow -gt $until) { exit 3 }; Start-Sleep -Milliseconds 20 }; [Console]::Out.Write('read')",
        );
        command.env("CADRUMO_TEST_READY", self.directory.join("ready"));
        command.env("CADRUMO_TEST_RELEASE", self.directory.join("release"));
        command
    }
    fn wait_ready(&self) {
        let deadline = Instant::now() + Duration::from_secs(10);
        while !self.directory.join("ready").exists() {
            assert!(
                Instant::now() < deadline,
                "real child did not reach its barrier"
            );
            thread::sleep(Duration::from_millis(10));
        }
    }
    fn release(&self) {
        fs::write(self.directory.join("release"), b"").unwrap();
    }
    fn record(&self, label: &'static str) -> Command {
        let mut command = powershell(&format!(
            "[IO.File]::AppendAllText($env:CADRUMO_TEST_ORDER, '{label}' + [Environment]::NewLine); [Console]::Out.Write('{label}')"
        ));
        command.env("CADRUMO_TEST_ORDER", self.directory.join("order"));
        command
    }
}

fn wait_state(children: &Children, matches: impl Fn(&Active) -> bool) {
    let deadline = Instant::now() + Duration::from_secs(10);
    let mut active = children.active.lock().unwrap();
    while !matches(&active) {
        let remaining = deadline.saturating_duration_since(Instant::now());
        assert!(
            !remaining.is_zero(),
            "helper admission did not reach the expected state"
        );
        active = children.changed.wait_timeout(active, remaining).unwrap().0;
    }
}
impl Drop for BarrierChild {
    fn drop(&mut self) {
        // Delete only this fixture's resolved direct child of the temp root.
        if let (Ok(directory), Ok(temporary)) = (
            fs::canonicalize(&self.directory),
            fs::canonicalize(std::env::temp_dir()),
        ) && directory.parent() == Some(temporary.as_path())
            && directory.file_name().is_some_and(|name| {
                name.to_string_lossy()
                    .starts_with("cadrumo-sign-in-admission-")
            })
        {
            let _ = fs::remove_dir_all(directory);
        }
    }
}

#[test]
fn a_mutation_waits_behind_a_real_read_without_replaying_its_password() {
    let children = Children::default();
    let barrier = BarrierChild::new();
    thread::scope(|scope| {
        let reading = scope.spawn(|| children.read(barrier.command()));
        barrier.wait_ready();
        let (send, receive) = mpsc::channel();
        let shared = &children;
        scope.spawn(move || {
            send.send(shared.run(
                powershell("$value=[Console]::In.ReadToEnd(); [Console]::Out.Write($value)"),
                Some(Zeroizing::new(b"queued-password-once".to_vec())),
            ))
            .unwrap();
        });
        let early = receive.recv_timeout(Duration::from_millis(150));
        barrier.release();
        assert_eq!(&*reading.join().unwrap().unwrap().stdout, b"read");
        let output =
            early.unwrap_or_else(|_| receive.recv_timeout(Duration::from_secs(10)).unwrap());
        assert!(
            output.is_ok(),
            "a mutation behind a read was refused: {:?}",
            output.err()
        );
        let output = output.unwrap();
        assert!(output.success);
        assert_eq!(&*output.stdout, b"queued-password-once");
    });
    let snapshot = children.diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.processes.len(), 2);
    assert!(snapshot.output.is_empty());
    assert!(
        !serde_json::to_string(&snapshot.events)
            .unwrap()
            .contains("queued-password-once")
    );
}

#[test]
fn reserved_mutation_precedes_queued_readers_and_refuses_duplicate_mutations() {
    let children = Children::default();
    let barrier = BarrierChild::new();
    thread::scope(|scope| {
        let reading = scope.spawn(|| children.read(barrier.command()));
        barrier.wait_ready();
        let queued = scope.spawn(|| children.read(barrier.record("already-waiting-read")));
        wait_state(&children, |active| active.pending_readers == 1);
        let mutation = scope.spawn(|| children.run(barrier.record("mutation"), None));
        wait_state(&children, |active| active.pending_mutation);
        let duplicate = children.run(
            barrier.record("duplicate-must-not-run"),
            Some(Zeroizing::new(b"duplicate-password-must-not-run".to_vec())),
        );
        assert_eq!(duplicate.err().unwrap().code, ErrorCode::CliBusy);
        let later = scope.spawn(|| children.read(barrier.record("later-read")));
        wait_state(&children, |active| active.pending_readers == 2);
        barrier.release();
        assert!(reading.join().unwrap().unwrap().success);
        assert_eq!(&*mutation.join().unwrap().unwrap().stdout, b"mutation");
        assert!(queued.join().unwrap().unwrap().success);
        assert!(later.join().unwrap().unwrap().success);
    });
    let order = fs::read_to_string(barrier.directory.join("order")).unwrap();
    assert_eq!(order.lines().next(), Some("mutation"));
    assert_eq!(order.lines().count(), 3);
    assert!(!order.contains("duplicate"));
    let active = children.active.lock().unwrap();
    assert_eq!(active.pending_readers, 0);
    assert!(!active.pending_mutation && active.busy.is_none());
    let snapshot = children.diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.processes.len(), 4);
    let refusal = snapshot
        .events
        .iter()
        .find(|event| {
            event
                .failure
                .as_ref()
                .is_some_and(|error| error.code == ErrorCode::CliBusy)
        })
        .unwrap();
    assert!(refusal.process.is_none() && refusal.status.is_none() && refusal.role.is_none());
    assert_eq!(
        refusal.failure.as_ref().unwrap().message,
        "The sign-in helper is busy"
    );
    assert!(
        !serde_json::to_string(&snapshot.events)
            .unwrap()
            .contains("duplicate-password")
    );
}

#[test]
fn pending_reader_bound_and_close_fence_settle_all_waiters_without_spawning_them() {
    let barrier = BarrierChild::new();
    let diagnostics = Arc::new(Diagnostics::default());
    diagnostics
        .configure(&barrier.directory.join("logs"), 32768, 2)
        .unwrap();
    let children = Children::new(diagnostics.clone());
    thread::scope(|scope| {
        let reading = scope.spawn(|| children.read(barrier.command()));
        barrier.wait_ready();
        let mutation = scope.spawn(|| {
            children.run(
                barrier.record("closed-mutation-must-not-run"),
                Some(Zeroizing::new(b"closed-private-password".to_vec())),
            )
        });
        wait_state(&children, |active| active.pending_mutation);
        let readers: Vec<_> = (0..PENDING_READERS)
            .map(|_| scope.spawn(|| children.read(barrier.record("closed-reader-must-not-run"))))
            .collect();
        wait_state(&children, |active| {
            active.pending_readers == PENDING_READERS
        });
        let mut refused = Command::new(barrier.directory.join("private-path-must-not-spawn"));
        refused.arg("private-profile-must-not-log");
        assert_eq!(
            children.read(refused).err().unwrap().code,
            ErrorCode::CliBusy
        );
        let started = Instant::now();
        children.stop().unwrap();
        assert_eq!(
            mutation.join().unwrap().err().unwrap().code,
            ErrorCode::SessionUnavailable
        );
        for reader in readers {
            assert_eq!(
                reader.join().unwrap().err().unwrap().code,
                ErrorCode::SessionUnavailable
            );
        }
        assert!(reading.join().unwrap().is_err());
        assert!(started.elapsed() < Duration::from_secs(5));
    });
    let active = children.active.lock().unwrap();
    assert!(active.closed && active.child.is_none() && active.busy.is_none());
    assert!(!active.pending_mutation);
    assert_eq!(active.pending_readers, 0);
    drop(active);
    assert!(!barrier.directory.join("order").exists());
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.processes.len(), 1);
    let log = fs::read_to_string(snapshot.paths.unwrap().current).unwrap();
    assert!(log.contains("cli_busy") && log.contains("session_unavailable"));
    assert!(
        !log.contains("private-path")
            && !log.contains("private-profile")
            && !log.contains("closed-private-password")
    );
    assert_eq!(
        children.read(powershell("exit 0")).err().unwrap().code,
        ErrorCode::SessionUnavailable
    );
}

#[test]
fn mutation_admission_timeout_clears_its_reservation_and_discards_its_password() {
    let children = Children::default();
    let barrier = BarrierChild::new();
    thread::scope(|scope| {
        let reading = scope.spawn(|| children.read(barrier.command()));
        barrier.wait_ready();
        let timed_out = children.execute(
            barrier.record("timed-out-mutation-must-not-run"),
            Some(Zeroizing::new(b"abandoned-private-password".to_vec())),
            HelperKind::Mutation,
            Duration::from_millis(150),
            DEADLINE,
        );
        assert_eq!(timed_out.err().unwrap().code, ErrorCode::CliWaitTimedOut);
        assert!(!children.active.lock().unwrap().pending_mutation);
        let replacement = scope.spawn(|| children.run(barrier.record("replacement"), None));
        wait_state(&children, |active| active.pending_mutation);
        barrier.release();
        assert!(reading.join().unwrap().unwrap().success);
        assert_eq!(
            &*replacement.join().unwrap().unwrap().stdout,
            b"replacement"
        );
    });
    assert_eq!(
        fs::read_to_string(barrier.directory.join("order"))
            .unwrap()
            .lines()
            .collect::<Vec<_>>(),
        ["replacement"]
    );
    let snapshot = children.diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.processes.len(), 2);
    assert!(
        !serde_json::to_string(&snapshot.events)
            .unwrap()
            .contains("abandoned-private-password")
    );
}

#[test]
fn reader_admission_timeouts_release_all_waiting_slots() {
    let children = Children::default();
    let barrier = BarrierChild::new();
    thread::scope(|scope| {
        let reading = scope.spawn(|| children.read(barrier.command()));
        barrier.wait_ready();
        for _ in 0..PENDING_READERS + 2 {
            let timed_out = children.execute(
                barrier.record("timed-out-reader-must-not-run"),
                None,
                HelperKind::Read,
                Duration::from_millis(50),
                DEADLINE,
            );
            assert_eq!(timed_out.err().unwrap().code, ErrorCode::CliWaitTimedOut);
            assert_eq!(children.active.lock().unwrap().pending_readers, 0);
        }
        barrier.release();
        assert!(reading.join().unwrap().unwrap().success);
    });
    assert_eq!(
        &*children
            .read(barrier.record("reader-after-timeouts"))
            .unwrap()
            .stdout,
        b"reader-after-timeouts"
    );
    assert_eq!(children.diagnostics.snapshot(u64::MAX).processes.len(), 2);
}

#[test]
fn reserved_mutation_spawn_failure_releases_waiting_reader_without_retrying() {
    let children = Children::default();
    let barrier = BarrierChild::new();
    thread::scope(|scope| {
        let reading = scope.spawn(|| children.read(barrier.command()));
        barrier.wait_ready();
        let mut missing = Command::new(barrier.directory.join("synthetic-private-launch-path"));
        missing.arg("private-profile-argument");
        let shared = &children;
        let mutation = scope.spawn(move || {
            shared.run(
                missing,
                Some(Zeroizing::new(b"private-spawn-password".to_vec())),
            )
        });
        wait_state(&children, |active| active.pending_mutation);
        let queued = scope.spawn(|| children.read(barrier.record("reader-after-spawn-failure")));
        wait_state(&children, |active| active.pending_readers == 1);
        barrier.release();
        assert!(reading.join().unwrap().unwrap().success);
        assert_eq!(
            mutation.join().unwrap().err().unwrap().code,
            ErrorCode::SpawnFailed
        );
        assert!(queued.join().unwrap().unwrap().success);
    });
    let active = children.active.lock().unwrap();
    assert!(!active.pending_mutation && active.busy.is_none());
    assert_eq!(active.pending_readers, 0);
    let snapshot = children.diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.processes.len(), 2);
    let error = snapshot
        .events
        .iter()
        .find(|event| {
            event
                .failure
                .as_ref()
                .is_some_and(|error| error.code == ErrorCode::SpawnFailed)
        })
        .unwrap();
    assert_eq!(error.role, Some(ProcessRole::SignIn));
    assert!(error.process.is_none());
    let encoded = serde_json::to_string(&snapshot.events).unwrap();
    assert!(
        !encoded.contains("synthetic-private-launch-path")
            && !encoded.contains("private-profile-argument")
            && !encoded.contains("private-spawn-password")
    );
}

#[test]
fn cleanup_failure_still_wakes_and_fences_pending_commands() {
    let children = Children::default();
    let barrier = BarrierChild::new();
    thread::scope(|scope| {
        let reading = scope.spawn(|| children.read(barrier.command()));
        barrier.wait_ready();
        let mutation = scope.spawn(|| children.run(barrier.record("must-not-run"), None));
        let queued = scope.spawn(|| children.read(barrier.record("must-not-run")));
        wait_state(&children, |active| {
            active.pending_mutation && active.pending_readers == 1
        });
        let closed = children.close_with(|_| Err(failure(ErrorCode::CleanupFailed)));
        assert_eq!(closed.err().unwrap().code, ErrorCode::CleanupFailed);
        assert_eq!(
            mutation.join().unwrap().err().unwrap().code,
            ErrorCode::SessionUnavailable
        );
        assert_eq!(
            queued.join().unwrap().err().unwrap().code,
            ErrorCode::SessionUnavailable
        );
        assert!(reading.join().unwrap().is_err());
    });
    let active = children.active.lock().unwrap();
    assert!(active.closed && active.child.is_none() && active.busy.is_none());
    assert!(!active.pending_mutation && active.pending_readers == 0);
    assert!(!barrier.directory.join("order").exists());
}

#[test]
fn refused_mutation_runs_once_without_retrying_a_failed_stdin_write() {
    let children = Children::default();
    let barrier = BarrierChild::new();
    let mut command = powershell(
        "[IO.File]::AppendAllText($env:CADRUMO_TEST_ORDER, 'attempt' + [Environment]::NewLine); [Console]::Out.Write('refused'); exit 7",
    );
    command.env("CADRUMO_TEST_ORDER", barrier.directory.join("order"));
    let output = children
        .run(command, Some(Zeroizing::new(vec![b'k'; 1024 * 1024])))
        .unwrap();
    assert!(!output.success);
    assert_eq!(&*output.stdout, b"refused");
    assert_eq!(
        fs::read_to_string(barrier.directory.join("order"))
            .unwrap()
            .lines()
            .collect::<Vec<_>>(),
        ["attempt"]
    );
    let snapshot = children.diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.processes.len(), 1);
    assert_eq!(snapshot.processes[0].exit_code, Some(7));
    assert!(snapshot.output.is_empty());
}
