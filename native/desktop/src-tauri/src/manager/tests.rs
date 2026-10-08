use super::*;

fn fixture(target: Result<Option<PathBuf>>) -> Arc<ManagerStart> {
    Arc::new(ManagerStart {
        package_root: target,
        child: ChildConfiguration::new(
            std::env::current_exe().unwrap(),
            std::env::temp_dir(),
            Default::default(),
        )
        .unwrap(),
        diagnostics: Arc::new(Diagnostics::default()),
        attempt: Arc::new(tokio::sync::Mutex::new(None)),
        generation: AtomicU64::new(0),
        closed: AtomicBool::new(false),
        cancellation: Arc::new(Cancellation::default()),
        spawn_fence: Mutex::new(()),
        closing: tokio::sync::Notify::new(),
    })
}

#[cfg(windows)]
#[tokio::test]
async fn close_cancels_then_joins_the_actual_verifier_and_refuses_late_retries() {
    use cadrumo_application::{error::Error, package::PackageManifest, value::RelativePath};
    use std::{sync::mpsc, time::Instant};
    for abandon_caller in [false, true] {
        let manager = fixture(Ok(None));
        let settled = Arc::new(AtomicBool::new(false));
        let cancellation_observed = Arc::new(AtomicBool::new(false));
        let worker_settled = settled.clone();
        let worker_observed = cancellation_observed.clone();
        let (entered, ready) = tokio::sync::oneshot::channel();
        let (release, waiting) = mpsc::channel();
        let owner = manager.clone();
        let caller = tokio::spawn(async move {
            owner
                .start_with(false, |owner| async move {
                    owner
                        .resolve_with(move |cancellation| {
                            entered.send(()).unwrap();
                            waiting.recv_timeout(Duration::from_secs(5)).unwrap();
                            let owner = RelativePath::new("manifest.json").unwrap();
                            let inspected = PackageManifest::read_cancellable(
                                &std::env::temp_dir().join("unused-cancelled-verifier-fixture"),
                                &owner,
                                &cancellation,
                            );
                            worker_observed.store(
                                matches!(inspected, Err(Error::Cancelled)),
                                Ordering::Release,
                            );
                            worker_settled.store(true, Ordering::Release);
                            // Even a verifier that returns a target after the close fence
                            // must settle without permitting a late helper launch.
                            Ok(PathBuf::from("unused-target"))
                        })
                        .await?;
                    owner
                        .run_dispatch(helper("exit 99"), Duration::from_secs(15))
                        .await
                })
                .await
        });
        tokio::time::timeout(Duration::from_secs(5), ready)
            .await
            .unwrap()
            .unwrap();
        if abandon_caller {
            caller.abort();
        }
        let cancellation_started = Instant::now();
        let closing_owner = manager.clone();
        let closing = tokio::spawn(async move { closing_owner.close().await });
        tokio::time::timeout(Duration::from_secs(5), async {
            while !manager.closed.load(Ordering::Acquire) {
                tokio::task::yield_now().await;
            }
        })
        .await
        .unwrap();
        assert!(
            !closing.is_finished(),
            "close must wait for the actual blocked verifier"
        );
        assert!(!settled.load(Ordering::Acquire));
        for _ in 0..8 {
            assert_eq!(
                tokio::time::timeout(Duration::from_secs(1), manager.start(true))
                    .await
                    .unwrap()
                    .unwrap_err()
                    .code,
                ErrorCode::SessionUnavailable
            );
        }
        assert!(manager.diagnostics.snapshot(0).processes.is_empty());
        let released = Instant::now();
        release.send(()).unwrap();
        tokio::time::timeout(Duration::from_secs(5), closing)
            .await
            .unwrap()
            .unwrap();
        if abandon_caller {
            assert!(caller.await.unwrap_err().is_cancelled());
        } else {
            assert_eq!(
                caller.await.unwrap().unwrap_err().code,
                ErrorCode::SessionUnavailable
            );
        }
        assert!(settled.load(Ordering::Acquire));
        assert!(cancellation_observed.load(Ordering::Acquire));
        assert!(manager.diagnostics.snapshot(0).processes.is_empty());
        assert_eq!(
            manager
                .attempt
                .lock()
                .await
                .as_ref()
                .unwrap()
                .as_ref()
                .unwrap_err()
                .code,
            ErrorCode::SessionUnavailable
        );
        assert_eq!(
            manager
                .run_dispatch(helper("exit 99"), Duration::from_secs(15))
                .await
                .unwrap_err()
                .code,
            ErrorCode::SessionUnavailable
        );
        assert!(manager.diagnostics.snapshot(0).processes.is_empty());
        eprintln!(
            "verifier settlement abandon_caller={abandon_caller} cancellation_to_settlement_us={} test_gate_release_to_settlement_us={}",
            cancellation_started.elapsed().as_micros(),
            released.elapsed().as_micros()
        );
    }
}

#[cfg(windows)]
#[tokio::test]
async fn close_waits_for_the_private_helper_and_fences_later_launches() {
    let manager = fixture(Ok(None));
    let held = manager.attempt.lock().await;
    let running = async {
        let result = manager
            .run_dispatch(helper("Start-Sleep -Seconds 60"), Duration::from_secs(30))
            .await;
        drop(held);
        result
    };
    let (result, ()) = tokio::time::timeout(Duration::from_secs(3), async {
        tokio::join!(running, manager.close())
    })
    .await
    .expect("closing must interrupt the helper instead of waiting its30second deadline");
    assert_eq!(result.unwrap_err().code, ErrorCode::SessionUnavailable);
    assert_eq!(
        manager.diagnostics.snapshot(0).processes[0].phase,
        ProcessPhase::Terminated
    );
    assert_eq!(
        manager.start(true).await.unwrap_err().code,
        ErrorCode::SessionUnavailable
    );
}

#[cfg(windows)]
#[tokio::test]
async fn cancelled_ipc_caller_does_not_abandon_the_owned_helper() {
    let manager = fixture(Ok(None));
    let caller_owner = manager.clone();
    let caller = tokio::spawn(async move {
        caller_owner.start_with(true, |owner| async move {
            owner.run_dispatch(helper(
                "Start-Sleep -Milliseconds 700; [Console]::Out.Write('{\"dispatched\":true,\"os_code\":null}')"
            ), Duration::from_secs(10)).await
        }).await
    });
    tokio::time::timeout(Duration::from_secs(5), async {
        while manager.diagnostics.snapshot(0).processes.is_empty() {
            tokio::task::yield_now().await;
        }
    })
    .await
    .unwrap();
    caller.abort();
    assert!(caller.await.unwrap_err().is_cancelled());
    let settled = tokio::time::timeout(Duration::from_secs(5), manager.attempt.lock())
        .await
        .unwrap();
    assert_eq!(
        settled.as_ref().unwrap().as_ref().unwrap(),
        &StartOutcome::Dispatched
    );
    drop(settled);
    manager.close().await;
    let snapshot = manager.diagnostics.snapshot(0);
    assert_eq!(snapshot.processes.len(), 1);
    assert_eq!(snapshot.processes[0].phase, ProcessPhase::Exited);
    assert_eq!(snapshot.processes[0].exit_code, Some(0));
    assert_eq!(
        manager
            .attempt
            .lock()
            .await
            .as_ref()
            .unwrap()
            .as_ref()
            .unwrap(),
        &StartOutcome::Dispatched
    );
}

#[cfg(windows)]
#[tokio::test]
async fn overlapping_retries_share_one_attempt_instead_of_forming_a_launch_queue() {
    use std::{future::Future, task::Poll};
    let manager = fixture(Ok(None));
    let held = manager.attempt.lock().await;
    let mut requests: Vec<_> = (0..64).map(|_| Box::pin(manager.start(true))).collect();
    std::future::poll_fn(|context| {
        for request in &mut requests {
            assert!(request.as_mut().poll(context).is_pending());
        }
        Poll::Ready(())
    })
    .await;
    drop(held);
    for request in requests {
        assert_eq!(request.await.unwrap(), StartOutcome::Unmanaged);
    }
    let starts = manager
        .diagnostics
        .snapshot(0)
        .events
        .iter()
        .filter(|event| matches!(event.kind, EventKind::StageStarted))
        .count();
    assert_eq!(starts, 1, "overlapping IPC retries must share one dispatch");
}

#[cfg(windows)]
#[tokio::test]
async fn initial_calls_share_the_failure_but_explicit_retry_records_a_new_attempt() {
    let manager = fixture(Err(failure(ErrorCode::ManagerUnavailable)));
    let (first, second) = tokio::join!(manager.start(false), manager.start(false));
    assert_eq!(first.unwrap_err().code, ErrorCode::ManagerUnavailable);
    assert_eq!(second.unwrap_err().code, ErrorCode::ManagerUnavailable);
    let starts = || {
        manager
            .diagnostics
            .snapshot(0)
            .events
            .iter()
            .filter(|event| matches!(event.kind, EventKind::StageStarted))
            .count()
    };
    assert_eq!(starts(), 1);
    assert_eq!(
        manager.start(true).await.unwrap_err().code,
        ErrorCode::ManagerUnavailable
    );
    assert_eq!(starts(), 2);
    let unmanaged = fixture(Ok(None));
    assert_eq!(
        unmanaged.start(false).await.unwrap(),
        StartOutcome::Unmanaged
    );
    assert!(unmanaged.diagnostics.snapshot(0).processes.is_empty());
}

#[cfg(windows)]
fn helper(script: &str) -> tokio::process::Command {
    let mut command = tokio::process::Command::new(
        PathBuf::from(std::env::var_os("SystemRoot").unwrap())
            .join("System32/WindowsPowerShell/v1.0/powershell.exe"),
    );
    command
        .args([
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .kill_on_drop(true);
    command.creation_flags(0x0800_0000);
    command
}

#[cfg(windows)]
#[tokio::test]
async fn missing_executable_or_working_directory_reports_safe_spawn_failure() {
    for missing_image in [false, true] {
        let manager = fixture(Ok(None));
        let private_path =
            std::env::temp_dir().join(format!("cadrumo-missing-private-{}", std::process::id()));
        assert!(!private_path.exists());
        let mut command = if missing_image {
            tokio::process::Command::new(&private_path)
        } else {
            helper("exit0")
        };
        if !missing_image {
            command.current_dir(&private_path);
        }
        let error = manager
            .run_dispatch(command, Duration::from_secs(2))
            .await
            .unwrap_err();
        assert_eq!(error.code, ErrorCode::ManagerDispatchFailed);
        let snapshot = manager.diagnostics.snapshot(0);
        assert!(snapshot.processes.is_empty());
        assert_eq!(snapshot.events[0].role, Some(ProcessRole::ManagerDispatch));
        assert!(
            !serde_json::to_string(&snapshot.events)
                .unwrap()
                .contains("missing-private")
        );
    }
}

#[cfg(windows)]
#[tokio::test]
async fn repeated_helpers_remain_settled_and_report_measured_latency() {
    let manager = fixture(Ok(None));
    let mut samples = Vec::new();
    for _ in 0..24 {
        let start = std::time::Instant::now();
        let mut command = helper(
            "[Console]::Error.Write(('private-noise' * 65536)); [Console]::Out.Write('{\"dispatched\":true,\"os_code\":null}')",
        );
        // Fixed absolute executable and explicit working directory must not need PATH.
        command
            .env_remove("PATH")
            .env_remove("PYTHONPATH")
            .current_dir(std::env::temp_dir());
        assert_eq!(
            manager
                .run_dispatch(command, Duration::from_secs(10))
                .await
                .unwrap(),
            StartOutcome::Dispatched
        );
        samples.push(start.elapsed());
        let snapshot = manager.diagnostics.snapshot(0);
        assert!(
            snapshot
                .processes
                .iter()
                .all(|process| process.phase == ProcessPhase::Exited)
        );
        assert!(snapshot.output.is_empty());
    }
    samples.sort();
    eprintln!(
        "helper churn samples=24 median_us={} p95_us={} retained_processes={}",
        samples[12].as_micros(),
        samples[22].as_micros(),
        manager.diagnostics.snapshot(0).processes.len()
    );
}

#[cfg(windows)]
#[tokio::test]
async fn helper_success_and_failure_keep_exit_attribution_without_capturing_output() {
    for (script, expected) in [
        (
            "[Console]::Out.Write('{\"dispatched\":true,\"os_code\":null}')",
            None,
        ),
        (
            "[Console]::Out.Write('{\"dispatched\":false,\"os_code\":5}'); exit 1",
            Some(ErrorCode::ManagerDispatchFailed),
        ),
        (
            "[Console]::Out.Write('private-invalid-reply')",
            Some(ErrorCode::ManagerDispatchFailed),
        ),
    ] {
        let manager = fixture(Ok(None));
        let result = manager
            .run_dispatch(helper(script), Duration::from_secs(15))
            .await;
        assert_eq!(result.err().map(|error| error.code), expected);
        let snapshot = manager.diagnostics.snapshot(0);
        assert_eq!(snapshot.processes.len(), 1);
        assert_eq!(snapshot.processes[0].phase, ProcessPhase::Exited);
        assert_eq!(snapshot.processes[0].role, ProcessRole::ManagerDispatch);
        assert!(snapshot.output.is_empty());
        assert!(
            !serde_json::to_string(&snapshot.events)
                .unwrap()
                .contains("private-invalid-reply")
        );
    }
}

#[cfg(windows)]
#[tokio::test]
async fn helper_timeout_and_output_limit_reap_and_attribute_the_child() {
    for (script, deadline, expected) in [
        (
            "Start-Sleep -Seconds 60",
            Duration::from_millis(500),
            ErrorCode::TimedOut,
        ),
        (
            "while ($true) { [Console]::Out.Write(('x' * 8192)) }",
            Duration::from_secs(15),
            ErrorCode::OutputLimit,
        ),
    ] {
        let manager = fixture(Ok(None));
        assert_eq!(
            manager
                .run_dispatch(helper(script), deadline)
                .await
                .unwrap_err()
                .code,
            expected
        );
        let snapshot = manager.diagnostics.snapshot(0);
        let process = &snapshot.processes[0];
        assert_eq!(process.phase, ProcessPhase::Terminated);
        assert!(snapshot.events.iter().any(|event| {
            event.process == Some(process.id)
                && event
                    .failure
                    .as_ref()
                    .is_some_and(|error| error.code == expected)
        }));
        assert!(snapshot.output.is_empty());
    }
}

#[test]
fn dispatch_acknowledges_launch_only_and_rejects_failed_or_malformed_replies() {
    assert_eq!(
        decode(br#"{"dispatched":true,"os_code":null}"#, true).unwrap(),
        StartOutcome::Dispatched
    );
    for (bytes, success) in [
        (br#"{"dispatched":true,"os_code":null}"#.as_slice(), false),
        (br#"{"dispatched":false,"os_code":5}"#.as_slice(), true),
        (
            br#"{"dispatched":true,"os_code":null,"ready":true}"#.as_slice(),
            true,
        ),
        (b"not a control reply".as_slice(), true),
    ] {
        assert!(decode(bytes, success).is_err());
    }
}

#[test]
fn manager_path_is_taken_from_the_package_projection_and_is_unambiguous() {
    use cadrumo_application::installation::Image;
    let mut contract: DiscoveryContract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
    contract.layout.application_images = vec![Image {
        name: "fixture-manager".into(),
        placement: ".".into(),
        target: "rust_manager".into(),
    }];
    assert_eq!(
        contract.manager_member().unwrap().as_str(),
        "fixture-manager.exe"
    );
    contract.layout.application_images[0].name = "../foreign".into();
    assert!(contract.manager_member().is_err());
    contract.layout.application_images[0].name = "fixture-manager".into();
    contract.layout.application_images.push(Image {
        name: "duplicate-manager".into(),
        placement: ".".into(),
        target: "rust_manager".into(),
    });
    assert!(contract.manager_member().is_err());
    contract.layout.application_images.clear();
    assert!(contract.manager_member().is_err());
}
