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

fn wait_state(children: &Children, kind: HelperKind, matches: impl Fn(&Active) -> bool) {
    let lane = children.lane(kind);
    let deadline = Instant::now() + Duration::from_secs(10);
    let mut active = lane.active.lock().unwrap();
    while !matches(&active) {
        let remaining = deadline.saturating_duration_since(Instant::now());
        assert!(
            !remaining.is_zero(),
            "helper admission did not reach the expected state"
        );
        active = lane.changed.wait_timeout(active, remaining).unwrap().0;
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

fn timing_event(
    children: &Children,
    kind: HelperKind,
    outcome: HelperOutcome,
) -> cadrumo_application::diagnostics::Event {
    children
        .diagnostics
        .snapshot(u64::MAX)
        .events
        .into_iter()
        .find(|event| {
            event
                .helper_timing
                .is_some_and(|timing| timing.helper_kind == kind && timing.outcome == outcome)
        })
        .unwrap()
}

#[test]
fn a_mutation_completes_while_a_read_is_held_without_replaying_its_password() {
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
                Some(Zeroizing::new(b"independent-password-once".to_vec())),
            ))
            .unwrap();
        });
        let completed_before_release = receive.recv_timeout(Duration::from_secs(10));
        let read_still_running = children
            .read
            .active
            .lock()
            .unwrap()
            .child
            .as_mut()
            .unwrap()
            .try_wait()
            .unwrap()
            .is_none();
        barrier.release();
        assert_eq!(&*reading.join().unwrap().unwrap().stdout, b"read");
        let output = completed_before_release
            .expect("mutation waited for the held read")
            .unwrap();
        assert!(read_still_running && output.success);
        assert_eq!(&*output.stdout, b"independent-password-once");
    });
    let event = timing_event(&children, HelperKind::Mutation, HelperOutcome::Completed);
    let timing = event.helper_timing.unwrap();
    assert!(event.process.is_some());
    let measured = timing.admission_wait_ms
        + timing.spawn_ms.unwrap()
        + timing.execution_ms.unwrap()
        + timing.cleanup_ms.unwrap()
        + timing.output_join_ms.unwrap();
    assert!(measured <= timing.total_ms);
    println!(
        "independent mutation admission_wait_ms={} execution_ms={} total_ms={}",
        timing.admission_wait_ms,
        timing.execution_ms.unwrap(),
        timing.total_ms
    );
    let snapshot = children.diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.processes.len(), 2);
    assert!(snapshot.output.is_empty());
    assert!(
        !serde_json::to_string(&snapshot.events)
            .unwrap()
            .contains("independent-password-once")
    );
}

#[test]
fn a_read_completes_while_creation_is_held_and_duplicate_mutations_are_refused() {
    let children = Children::default();
    let barrier = BarrierChild::new();
    thread::scope(|scope| {
        let mutation =
            scope.spawn(|| children.run_within(barrier.command(), None, CREATION_DEADLINE));
        barrier.wait_ready();
        let (send, receive) = mpsc::channel();
        let shared = &children;
        let read_barrier = &barrier;
        scope.spawn(move || {
            send.send(shared.read(read_barrier.record("independent-status")))
                .unwrap()
        });
        let completed_before_release = receive.recv_timeout(Duration::from_secs(10));
        let refused = children.run(
            barrier.record("duplicate-must-not-run"),
            Some(Zeroizing::new(b"duplicate-private-password".to_vec())),
        );
        barrier.release();
        assert!(mutation.join().unwrap().unwrap().success);
        let output = completed_before_release
            .expect("read waited for the held mutation")
            .unwrap();
        assert_eq!(&*output.stdout, b"independent-status");
        assert_eq!(refused.err().unwrap().code, ErrorCode::CliBusy);
    });
    assert_eq!(
        fs::read_to_string(barrier.directory.join("order"))
            .unwrap()
            .lines()
            .collect::<Vec<_>>(),
        ["independent-status"]
    );
    let refusal = timing_event(
        &children,
        HelperKind::Mutation,
        HelperOutcome::AdmissionRefused,
    );
    assert!(refusal.process.is_none() && refusal.status.is_none());
    assert!(refusal.helper_timing.unwrap().spawn_ms.is_none());
    assert!(
        !serde_json::to_string(&children.diagnostics.snapshot(u64::MAX).events)
            .unwrap()
            .contains("duplicate-private-password")
    );
}

#[test]
fn at_most_two_children_and_eight_pending_reads_are_owned_and_close_wakes_every_waiter() {
    let read_barrier = BarrierChild::new();
    let mutation_barrier = BarrierChild::new();
    let diagnostics = Arc::new(Diagnostics::default());
    diagnostics
        .configure(&read_barrier.directory.join("logs"), 32768, 2)
        .unwrap();
    let children = Children::new(diagnostics.clone());
    thread::scope(|scope| {
        let reading = scope.spawn(|| children.read(read_barrier.command()));
        read_barrier.wait_ready();
        let mutation = scope.spawn(|| children.run(mutation_barrier.command(), None));
        mutation_barrier.wait_ready();
        let readers: Vec<_> = (0..PENDING_READERS)
            .map(|_| {
                scope.spawn(|| children.read(read_barrier.record("closed-reader-must-not-run")))
            })
            .collect();
        wait_state(&children, HelperKind::Read, |active| {
            active.pending_readers == PENDING_READERS
        });
        let mut refused = Command::new(read_barrier.directory.join("private-path-must-not-spawn"));
        refused.arg("private-profile-must-not-log");
        assert_eq!(
            children.read(refused).err().unwrap().code,
            ErrorCode::CliBusy
        );
        assert_eq!(
            children
                .run(
                    mutation_barrier.record("duplicate-must-not-run"),
                    Some(Zeroizing::new(b"private-duplicate-password".to_vec()))
                )
                .err()
                .unwrap()
                .code,
            ErrorCode::CliBusy
        );
        let snapshot = diagnostics.snapshot(u64::MAX);
        assert_eq!(
            snapshot
                .processes
                .iter()
                .filter(|status| status.phase == ProcessPhase::Running)
                .count(),
            2
        );
        let read_pid = children
            .read
            .active
            .lock()
            .unwrap()
            .child
            .as_ref()
            .unwrap()
            .id();
        let mutation_pid = children
            .mutation
            .active
            .lock()
            .unwrap()
            .child
            .as_ref()
            .unwrap()
            .id();
        assert_ne!(read_pid, mutation_pid);
        children.stop().unwrap();
        for reader in readers {
            assert_eq!(
                reader.join().unwrap().err().unwrap().code,
                ErrorCode::SessionUnavailable
            );
        }
        assert!(reading.join().unwrap().is_err() && mutation.join().unwrap().is_err());
    });
    assert!(children.is_closed().unwrap());
    for lane in [&children.read, &children.mutation] {
        let active = lane.active.lock().unwrap();
        assert!(active.child.is_none() && !active.busy && active.pending_readers == 0);
    }
    assert!(
        !read_barrier.directory.join("order").exists()
            && !mutation_barrier.directory.join("order").exists()
    );
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.processes.len(), 2);
    assert!(
        snapshot
            .processes
            .iter()
            .all(|status| status.phase == ProcessPhase::Terminated)
    );
    let log = fs::read_to_string(snapshot.paths.unwrap().current).unwrap();
    assert!(
        !log.contains("private-path")
            && !log.contains("private-profile")
            && !log.contains("private-duplicate-password")
    );
    assert_eq!(
        children.read(powershell("exit 0")).err().unwrap().code,
        ErrorCode::SessionUnavailable
    );
    assert_eq!(
        children.run(powershell("exit 0"), None).err().unwrap().code,
        ErrorCode::SessionUnavailable
    );
}

#[test]
fn queued_read_measurements_and_timeouts_release_all_waiting_slots() {
    let children = Children::default();
    let barrier = BarrierChild::new();
    let mut held_ms = 0;
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
            assert_eq!(children.read.active.lock().unwrap().pending_readers, 0);
        }
        let queued = scope.spawn(|| children.read(barrier.record("queued-read")));
        wait_state(&children, HelperKind::Read, |active| {
            active.pending_readers == 1
        });
        let held = Instant::now();
        thread::sleep(Duration::from_millis(150));
        held_ms = milliseconds(held.elapsed());
        barrier.release();
        assert!(reading.join().unwrap().unwrap().success);
        assert_eq!(&*queued.join().unwrap().unwrap().stdout, b"queued-read");
    });
    let snapshot = children.diagnostics.snapshot(u64::MAX);
    assert_eq!(snapshot.processes.len(), 2);
    let queued = snapshot
        .events
        .iter()
        .filter_map(|event| event.helper_timing)
        .filter(|timing| timing.outcome == HelperOutcome::Completed)
        .max_by_key(|timing| timing.admission_wait_ms)
        .unwrap();
    assert!(queued.admission_wait_ms >= held_ms);
    let refused = timing_event(&children, HelperKind::Read, HelperOutcome::AdmissionRefused);
    let timing = refused.helper_timing.unwrap();
    assert!(refused.process.is_none() && refused.status.is_none());
    assert!(
        timing.admission_wait_ms >= 50
            && timing.spawn_ms.is_none()
            && timing.execution_ms.is_none()
    );
    assert!(timing.cleanup_ms.is_none() && timing.output_join_ms.is_none());
    assert_eq!(
        fs::read_to_string(barrier.directory.join("order"))
            .unwrap()
            .lines()
            .collect::<Vec<_>>(),
        ["queued-read"]
    );
}

#[test]
fn a_failed_mutation_spawn_does_not_reserve_a_slot_or_affect_a_held_read() {
    let children = Children::default();
    let barrier = BarrierChild::new();
    thread::scope(|scope| {
        let reading = scope.spawn(|| children.read(barrier.command()));
        barrier.wait_ready();
        let mut missing = Command::new(barrier.directory.join("synthetic-private-launch-path"));
        missing.arg("private-profile-argument");
        let failed = children.run(
            missing,
            Some(Zeroizing::new(b"private-spawn-password".to_vec())),
        );
        assert_eq!(failed.err().unwrap().code, ErrorCode::SpawnFailed);
        assert!(!children.mutation.active.lock().unwrap().busy);
        let replacement = children.run(barrier.record("replacement"), None);
        let read_still_running = children
            .read
            .active
            .lock()
            .unwrap()
            .child
            .as_mut()
            .unwrap()
            .try_wait()
            .unwrap()
            .is_none();
        barrier.release();
        assert!(reading.join().unwrap().unwrap().success);
        assert!(read_still_running && replacement.unwrap().success);
    });
    let timed = timing_event(&children, HelperKind::Mutation, HelperOutcome::SpawnFailed);
    let timing = timed.helper_timing.unwrap();
    assert!(timed.process.is_none() && timed.status.is_none() && timing.spawn_ms.is_some());
    assert!(
        timing.execution_ms.is_none()
            && timing.cleanup_ms.is_none()
            && timing.output_join_ms.is_none()
    );
    let encoded = serde_json::to_string(&children.diagnostics.snapshot(u64::MAX).events).unwrap();
    assert!(
        !encoded.contains("synthetic-private-launch-path")
            && !encoded.contains("private-profile-argument")
            && !encoded.contains("private-spawn-password")
    );
}

struct PairedChildren {
    children: Children,
    read: BarrierChild,
    mutation: BarrierChild,
}
impl PairedChildren {
    fn new() -> Self {
        use std::os::windows::process::CommandExt;
        let owned = Self {
            children: Children::default(),
            read: BarrierChild::new(),
            mutation: BarrierChild::new(),
        };
        for (kind, barrier) in [
            (HelperKind::Read, &owned.read),
            (HelperKind::Mutation, &owned.mutation),
        ] {
            let mut command = barrier.command();
            command
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .creation_flags(0x08000000);
            let child = command.spawn().unwrap();
            let pid = child.id();
            let mut active = owned.children.lane(kind).active.lock().unwrap();
            active.child = Some(child);
            active.busy = true;
            active.process = Some(owned.children.diagnostics.start(pid, ProcessRole::SignIn));
        }
        owned.read.wait_ready();
        owned.mutation.wait_ready();
        owned
    }
}
impl Drop for PairedChildren {
    fn drop(&mut self) {
        let _ = self.children.stop();
    }
}

#[test]
fn both_lanes_are_fenced_before_cleanup_and_first_error_does_not_skip_the_second_child() {
    let owned = PairedChildren::new();
    let children = &owned.children;
    let mut settled = 0;
    let result = children.close_with(|active| {
        assert!(children.is_closed().unwrap());
        assert!(children.closed.try_lock().is_ok());
        settled += 1;
        let opposite = if settled == 1 {
            HelperKind::Mutation
        } else {
            HelperKind::Read
        };
        let refused = match opposite {
            HelperKind::Read => children.read(powershell("exit 0")),
            HelperKind::Mutation => children.run(powershell("exit 0"), None),
        };
        assert_eq!(refused.err().unwrap().code, ErrorCode::SessionUnavailable);
        if settled == 1 {
            Err(failure(ErrorCode::CleanupFailed))
        } else {
            children.settle_active(active)
        }
    });
    assert_eq!(settled, 2);
    assert_eq!(result.unwrap_err().code, ErrorCode::CleanupFailed);
    assert!(
        children
            .read
            .active
            .lock()
            .unwrap()
            .child
            .as_mut()
            .unwrap()
            .try_wait()
            .unwrap()
            .is_none()
    );
    assert!(
        children
            .mutation
            .active
            .lock()
            .unwrap()
            .child
            .as_mut()
            .unwrap()
            .try_wait()
            .unwrap()
            .is_some()
    );
    children.stop().unwrap();
    assert!(
        children
            .read
            .active
            .lock()
            .unwrap()
            .child
            .as_mut()
            .unwrap()
            .try_wait()
            .unwrap()
            .is_some()
    );
}

#[test]
fn cleanup_errors_keep_both_real_children_owned_and_diagnose_each_before_retry() {
    let owned = PairedChildren::new();
    let children = &owned.children;
    let mut settled = 0;
    let result = children.close_with(|_| {
        settled += 1;
        Err(failure(if settled == 1 {
            ErrorCode::CleanupFailed
        } else {
            ErrorCode::ReadFailed
        }))
    });
    assert_eq!(settled, 2);
    assert_eq!(result.unwrap_err().code, ErrorCode::CleanupFailed);
    for lane in [&children.read, &children.mutation] {
        let mut active = lane.active.lock().unwrap();
        assert!(active.busy && active.child.as_mut().unwrap().try_wait().unwrap().is_none());
        assert!(active.process.is_some());
    }
    let snapshot = children.diagnostics.snapshot(u64::MAX);
    for code in [ErrorCode::CleanupFailed, ErrorCode::ReadFailed] {
        assert!(snapshot.events.iter().any(|event| {
            event.process.is_some()
                && event
                    .failure
                    .as_ref()
                    .is_some_and(|error| error.code == code)
        }));
    }
    children.stop().unwrap();
    assert!(
        children
            .diagnostics
            .snapshot(u64::MAX)
            .processes
            .iter()
            .all(|status| status.phase == ProcessPhase::Terminated)
    );
}

#[test]
fn a_poisoned_fence_still_fences_and_reaps_both_children() {
    let owned = PairedChildren::new();
    let children = &owned.children;
    let poisoned = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let _fence = children.closed.lock().unwrap();
        panic!("synthetic shared fence panic");
    }));
    assert!(poisoned.is_err());
    assert_eq!(children.stop().unwrap_err().code, ErrorCode::LockPoisoned);
    let fence = children
        .closed
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    assert!(*fence);
    drop(fence);
    for lane in [&children.read, &children.mutation] {
        assert!(
            lane.active
                .lock()
                .unwrap()
                .child
                .as_mut()
                .unwrap()
                .try_wait()
                .unwrap()
                .is_some()
        );
    }
    assert_eq!(
        children.run(powershell("exit 0"), None).err().unwrap().code,
        ErrorCode::LockPoisoned
    );
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
    assert_eq!(
        snapshot
            .events
            .last()
            .unwrap()
            .helper_timing
            .unwrap()
            .outcome,
        HelperOutcome::Completed
    );
}

#[test]
fn failed_timing_sink_does_not_change_native_output_or_retry_the_password() {
    let barrier = BarrierChild::new();
    let unavailable = barrier.directory.join("unavailable-log");
    fs::create_dir(&unavailable).unwrap();
    let diagnostics = Arc::new(Diagnostics::default());
    diagnostics.configure_file(&unavailable, 8192, 2).unwrap();
    let children = Children::new(diagnostics.clone());
    let mut command = powershell(
        "[IO.File]::AppendAllText($env:CADRUMO_TEST_ORDER, 'attempt' + [Environment]::NewLine); $value=[Console]::In.ReadToEnd(); [Console]::Out.Write($value)",
    );
    command.env("CADRUMO_TEST_ORDER", barrier.directory.join("order"));
    let output = children
        .run(
            command,
            Some(Zeroizing::new(b"unlogged-private-password".to_vec())),
        )
        .unwrap();
    assert!(output.success);
    assert_eq!(&*output.stdout, b"unlogged-private-password");
    assert_eq!(
        fs::read_to_string(barrier.directory.join("order"))
            .unwrap()
            .lines()
            .count(),
        1
    );
    let snapshot = diagnostics.snapshot(u64::MAX);
    assert_eq!(
        snapshot.log_failure.as_ref().unwrap().code,
        ErrorCode::LogUnavailable
    );
    assert_eq!(snapshot.processes.len(), 1);
    let timing = snapshot.events.last().unwrap().helper_timing.unwrap();
    assert_eq!(timing.outcome, HelperOutcome::Completed);
    assert!(timing.spawn_ms.is_some() && timing.execution_ms.is_some());
    assert!(snapshot.output.is_empty());
    assert!(
        !serde_json::to_string(&snapshot.events)
            .unwrap()
            .contains("unlogged-private-password")
    );
}
