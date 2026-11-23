use super::protocol::{Changed, Gateway, Launch, Observation, Observe, Prepared, State};
use super::{Supervisor, lock, mint_bearer};
use cadrumo_application::diagnostics::Diagnostics;
use cadrumo_application::diagnostics::service::AgentRefusal as Refusal;
use cadrumo_application::diagnostics::service::ServiceFact;
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::ipc::Channel;
use tokio::sync::Notify;
use zeroize::Zeroizing;

#[test]
fn unavailable_supervisor_does_not_observe_or_retry() {
    let calls = Arc::new(AtomicU64::new(0));
    let observed_calls = calls.clone();
    let observe: Observe = Arc::new(move || {
        observed_calls.fetch_add(1, Ordering::Relaxed);
        Box::pin(async { observed(true, true, Some("profile")) })
    });
    let changed_calls = calls.clone();
    let changed: Changed = Arc::new(move || {
        changed_calls.fetch_add(1, Ordering::Relaxed);
        Box::pin(async {})
    });
    for reason in [Refusal::ServiceAbsent, Refusal::UnsupportedPlatform] {
        let supervisor = Supervisor::unavailable(
            observe.clone(),
            changed.clone(),
            reason,
            Arc::new(Diagnostics::default()),
        );
        assert_eq!(supervisor.status().state, State::Refused { code: reason });
        supervisor.retry();
        assert_eq!(supervisor.status().state, State::Refused { code: reason });
        assert!(!supervisor.shared.started.load(Ordering::Acquire));
        assert!(!supervisor.shared.retry_requested.load(Ordering::Acquire));
    }
    assert_eq!(calls.load(Ordering::Relaxed), 0);
    assert_eq!(
        serde_json::to_string(&Refusal::UnsupportedPlatform).unwrap(),
        "\"agent_platform_unsupported\""
    );
}

#[test]
fn the_ready_hook_runs_each_time_the_agent_becomes_ready_and_only_then() {
    let observe: Observe = Arc::new(|| Box::pin(async { observed(false, true, None) }));
    let changed: Changed = Arc::new(|| Box::pin(async {}));
    let supervisor = Supervisor::unavailable(
        observe,
        changed,
        Refusal::ServiceAbsent,
        Arc::new(Diagnostics::default()),
    );
    let calls = Arc::new(AtomicU64::new(0));
    let counted = calls.clone();
    supervisor.on_ready(Arc::new(move || {
        counted.fetch_add(1, Ordering::Relaxed);
    }));
    let ready = |version: &str| State::Ready {
        agent_version: version.to_owned(),
    };
    super::publish(&supervisor.shared, State::Starting);
    assert_eq!(calls.load(Ordering::Relaxed), 0);
    super::publish(&supervisor.shared, ready("1"));
    assert_eq!(calls.load(Ordering::Relaxed), 1);
    // The same status again is no new readiness.
    super::publish(&supervisor.shared, ready("1"));
    assert_eq!(calls.load(Ordering::Relaxed), 1);
    // A restart, or another profile's agent, is ready again.
    super::publish(&supervisor.shared, State::Starting);
    super::publish(&supervisor.shared, ready("1"));
    assert_eq!(calls.load(Ordering::Relaxed), 2);
    super::publish(
        &supervisor.shared,
        State::Refused {
            code: Refusal::ServiceFailed,
        },
    );
    assert_eq!(calls.load(Ordering::Relaxed), 2);
}

#[test]
fn bound_administration_rejects_replacement_before_and_during_an_exchange() {
    use std::io::{Read, Write};
    use std::net::TcpListener;
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    let (arrived, waiting) = std::sync::mpsc::channel();
    let (release, released) = std::sync::mpsc::channel();
    let server = std::thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        let mut frame = || {
            let mut header = [0; 4];
            stream.read_exact(&mut header).unwrap();
            let mut data = vec![0; u32::from_be_bytes(header) as usize];
            stream.read_exact(&mut data).unwrap();
            data
        };
        let _bearer = frame();
        let request: serde_json::Value = serde_json::from_slice(&frame()).unwrap();
        arrived.send(()).unwrap();
        released.recv().unwrap();
        let reply = serde_json::to_vec(&serde_json::json!({"version":1,"request_id":request["request_id"],"result":{"kind":"refused","code":"busy"}})).unwrap();
        stream
            .write_all(&(reply.len() as u32).to_be_bytes())
            .unwrap();
        stream.write_all(&reply).unwrap();
    });
    let observe: Observe = Arc::new(|| Box::pin(async { observed(false, true, None) }));
    let supervisor = Arc::new(Supervisor::new(
        observe,
        every(Duration::from_secs(60)),
        None,
        Arc::new(Diagnostics::default()),
    ));
    let endpoint = super::super::admin::Endpoint {
        port,
        bearer: Arc::new(Zeroizing::new("test".to_owned())),
        generation: 1,
        gate: Default::default(),
    };
    *lock(&supervisor.shared.admin) = Some(endpoint.clone());
    let error = supervisor
        .administer_generation(serde_json::json!({"action":"catalog"}), 2)
        .unwrap_err();
    assert_eq!(
        error.reason.as_deref(),
        Some("agent_admin_generation_changed")
    );
    let worker = {
        let supervisor = supervisor.clone();
        std::thread::spawn(move || {
            supervisor.administer_generation(serde_json::json!({"action":"catalog"}), 1)
        })
    };
    waiting.recv().unwrap();
    *lock(&supervisor.shared.admin) = Some(super::super::admin::Endpoint {
        generation: 2,
        ..endpoint
    });
    release.send(()).unwrap();
    let error = worker.join().unwrap().unwrap_err();
    assert_eq!(
        error.reason.as_deref(),
        Some("agent_admin_generation_changed")
    );
    server.join().unwrap();
}

#[test]
fn replacing_a_gateway_in_the_same_launcher_invalidates_its_admission() {
    let first = Gateway {
        port: 12345,
        bearer: Arc::new(Zeroizing::new("test-bearer".to_owned())),
        workspace_root: "workspace".to_owned(),
        generation: 1,
        instance: Arc::new(()),
    };
    assert!(first.same_instance(&first.clone()));
    let replacement = Gateway {
        instance: Arc::new(()),
        ..first.clone()
    };
    assert!(!first.same_instance(&replacement));
}

#[test]
fn native_drops_keep_paths_private_and_claim_them_once_for_the_observing_gateway() {
    use crate::agent::dropping::Drops;
    use tauri::{DragDropEvent, PhysicalPosition, ipc::InvokeResponseBody};
    let gateway = Gateway {
        port: 12345,
        bearer: Arc::new(Zeroizing::new("test-bearer".to_owned())),
        workspace_root: "workspace".to_owned(),
        generation: 1,
        instance: Arc::new(()),
    };
    let replacement = Gateway {
        instance: Arc::new(()),
        ..gateway.clone()
    };
    let signals = Arc::new(Mutex::new(Vec::<serde_json::Value>::new()));
    let received = signals.clone();
    let channel = Channel::new(move |body| {
        let InvokeResponseBody::Json(body) = body else {
            panic!("Expected a drop signal");
        };
        lock(&received).push(serde_json::from_str(&body).unwrap());
        Ok(())
    });
    let drops = Drops::default();
    let first = drops.observe(channel.clone(), gateway.clone());
    let paths = vec![std::path::PathBuf::from("private/invoice.pdf")];
    let position = PhysicalPosition::new(240.0, 360.0);
    drops.event(
        &DragDropEvent::Enter {
            paths: paths.clone(),
            position,
        },
        2.0,
    );
    drops.event(
        &DragDropEvent::Drop {
            paths: paths.clone(),
            position,
        },
        2.0,
    );
    let held = lock(&signals);
    assert_eq!(held[0]["x"], 120.0);
    assert_eq!(held[0]["y"], 180.0);
    assert_eq!(held[0]["count"], 1);
    let id = held[1]["drop_id"].as_str().unwrap().to_owned();
    assert!(!serde_json::to_string(&*held).unwrap().contains("private"));
    assert!(
        !serde_json::to_string(&*held)
            .unwrap()
            .contains("invoice.pdf")
    );
    drop(held);
    assert!(drops.take(&id, &replacement).is_err());
    assert!(drops.take("invented", &gateway).is_err());
    assert_eq!(drops.take(&id, &gateway).unwrap(), paths);
    assert!(drops.take(&id, &gateway).is_err());
    let received = signals.clone();
    let second = drops.observe(
        Channel::new(move |body| {
            let InvokeResponseBody::Json(body) = body else {
                panic!("Expected a drop signal");
            };
            lock(&received).push(serde_json::from_str(&body).unwrap());
            Ok(())
        }),
        gateway.clone(),
    );
    drops.clear(Some(first));
    // A retired observer cannot clear its replacement.
    assert_ne!(first, second);
    drops.event(
        &DragDropEvent::Drop {
            paths: paths.clone(),
            position,
        },
        2.0,
    );
    let id = lock(&signals)[2]["drop_id"].as_str().unwrap().to_owned();
    assert_eq!(drops.take(&id, &gateway).unwrap(), paths);
    drops.event(&DragDropEvent::Drop { paths, position }, 2.0);
    let id = lock(&signals)[3]["drop_id"].as_str().unwrap().to_owned();
    drops.clear(Some(second));
    assert!(drops.take(&id, &gateway).is_err());
}

/// Stands in for new sign-in observations: the test's source is read again every `period`.
fn every(period: Duration) -> Changed {
    Arc::new(move || Box::pin(tokio::time::sleep(period)))
}

pub(super) fn observed(present: bool, runtime: bool, profile: Option<&str>) -> Result<Observation> {
    Ok(Observation {
        supported: true,
        present,
        runtime_available: runtime,
        refused: false,
        active_profile: profile.map(str::to_owned),
    })
}

#[test]
fn the_bearer_is_fresh_hex_each_time() {
    let first = mint_bearer().unwrap();
    let second = mint_bearer().unwrap();
    assert_eq!(first.len(), 64);
    assert!(first.bytes().all(|b| b.is_ascii_hexdigit()));
    assert_ne!(*first, *second);
}

#[tokio::test]
async fn repeated_start_failures_exhaust_retries_and_profile_change_resets_them() {
    let source = Arc::new(Mutex::new(observed(true, true, Some("A"))));
    let current = source.clone();
    let observe: Observe = Arc::new(move || {
        let result = lock(&current).clone();
        Box::pin(async move { result })
    });
    let attempts = Arc::new(AtomicU64::new(0));
    let count = attempts.clone();
    let launch: Launch = Arc::new(move |_, _| {
        count.fetch_add(1, Ordering::SeqCst);
        Err(ApplicationError::new(
            ErrorCode::SpawnFailed,
            Operation::Cli,
        ))
    });
    let diagnostics = Arc::new(Diagnostics::default());
    let supervisor = Supervisor::with_timing(
        observe,
        every(Duration::from_millis(1)),
        Some(launch),
        diagnostics.clone(),
        Duration::from_millis(1),
        Duration::from_millis(2),
    );
    supervisor.status();
    tokio::time::timeout(Duration::from_secs(5), async {
        while attempts.load(Ordering::SeqCst) < 4 {
            tokio::time::sleep(Duration::from_millis(5)).await;
        }
    })
    .await
    .unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;
    assert_eq!(attempts.load(Ordering::SeqCst), 4);
    assert_eq!(
        supervisor.status().state,
        State::Refused {
            code: Refusal::ServiceFailed
        }
    );
    let facts: Vec<_> = diagnostics
        .snapshot(u64::MAX)
        .events
        .into_iter()
        .filter_map(|event| event.service)
        .collect();
    let delays: Vec<_> = facts
        .iter()
        .filter_map(|fact| match fact {
            ServiceFact::AgentRetryScheduled { delay_ms } => Some(*delay_ms),
            _ => None,
        })
        .collect();
    assert_eq!(delays, [2, 4, 8]);
    assert!(
        facts
            .iter()
            .any(|fact| matches!(fact, ServiceFact::AgentRetryExhausted { attempts: 4 }))
    );
    // Neither a failed read nor an unavailable runtime creates a new
    // authorization epoch or replenishes an exhausted attempt budget. Within
    // its readiness bound the runtime is waited for, as Stopped.
    for unavailable in [
        Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)),
        observed(true, false, Some("A")),
    ] {
        *lock(&source) = unavailable;
        tokio::time::timeout(Duration::from_secs(5), async {
            while supervisor.status().state != State::Stopped {
                tokio::time::sleep(Duration::from_millis(2)).await;
            }
        })
        .await
        .unwrap();
        *lock(&source) = observed(true, true, Some("A"));
        tokio::time::timeout(Duration::from_secs(5), async {
            while supervisor.status().state
                != (State::Refused {
                    code: Refusal::ServiceFailed,
                })
            {
                tokio::time::sleep(Duration::from_millis(2)).await;
            }
        })
        .await
        .unwrap();
        tokio::time::sleep(Duration::from_millis(30)).await;
        assert_eq!(attempts.load(Ordering::SeqCst), 4);
    }
    supervisor.retry();
    tokio::time::timeout(Duration::from_secs(5), async {
        while attempts.load(Ordering::SeqCst) < 8 {
            tokio::time::sleep(Duration::from_millis(5)).await;
        }
    })
    .await
    .unwrap();
    tokio::time::sleep(Duration::from_millis(50)).await;
    assert_eq!(attempts.load(Ordering::SeqCst), 8);
    *lock(&source) = observed(true, true, Some("B"));
    tokio::time::timeout(Duration::from_secs(5), async {
        while attempts.load(Ordering::SeqCst) < 12 {
            tokio::time::sleep(Duration::from_millis(5)).await;
        }
    })
    .await
    .unwrap();
    supervisor.close().await.unwrap();
    assert_eq!(attempts.load(Ordering::SeqCst), 12);
}

#[tokio::test]
async fn explicit_retry_still_requires_canonical_sign_in() {
    let calls = Arc::new(AtomicU64::new(0));
    let count = calls.clone();
    let observe: Observe = Arc::new(move || {
        count.fetch_add(1, Ordering::SeqCst);
        Box::pin(async { observed(false, true, Some("A")) })
    });
    let launch: Launch = Arc::new(|_, _| panic!("retry cannot authorize a signed-out profile"));
    let supervisor = Supervisor::with_timing(
        observe,
        every(Duration::from_secs(60)),
        Some(launch),
        Arc::new(Diagnostics::default()),
        Duration::from_millis(1),
        Duration::from_millis(1),
    );
    supervisor.status();
    tokio::time::timeout(Duration::from_secs(5), async {
        while supervisor.status().state
            != (State::Refused {
                code: Refusal::SignedOut,
            })
        {
            tokio::task::yield_now().await;
        }
    })
    .await
    .unwrap();
    let before = calls.load(Ordering::SeqCst);
    supervisor.retry();
    tokio::time::timeout(Duration::from_secs(5), async {
        while calls.load(Ordering::SeqCst) == before {
            tokio::task::yield_now().await;
        }
    })
    .await
    .unwrap();
    assert_eq!(
        supervisor.status().state,
        State::Refused {
            code: Refusal::SignedOut
        }
    );
    supervisor.close().await.unwrap();
}

#[tokio::test]
async fn closing_does_not_wait_for_a_pending_status_read() {
    let entered = Arc::new(Notify::new());
    let notify = entered.clone();
    let observe: Observe = Arc::new(move || {
        let notify = notify.clone();
        Box::pin(async move {
            notify.notify_one();
            std::future::pending().await
        })
    });
    let launch: Launch = Arc::new(|_, _| panic!("pending status cannot authorize launch"));
    let supervisor = Supervisor::new(
        observe,
        every(Duration::from_millis(1)),
        Some(launch),
        Arc::new(Diagnostics::default()),
    );
    supervisor.status();
    entered.notified().await;
    tokio::time::timeout(Duration::from_secs(1), supervisor.close())
        .await
        .unwrap()
        .unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn startup_timeout_is_observed_while_canonical_status_is_pending() {
    let calls = Arc::new(AtomicU64::new(0));
    let count = calls.clone();
    let observe: Observe = Arc::new(move || {
        let first = count.fetch_add(1, Ordering::SeqCst) == 0;
        Box::pin(async move {
            if first {
                observed(true, true, Some("A"))
            } else {
                std::future::pending().await
            }
        })
    });
    // A dropped sender releases preparation even if an assertion panics.
    let (release, gate) = std::sync::mpsc::channel::<()>();
    let gate = Mutex::new(gate);
    let entered = Arc::new(Notify::new());
    let arriving = entered.clone();
    let launch: Launch = Arc::new(move |_, _| {
        arriving.notify_one();
        let _ = lock(&gate).recv();
        Ok(Prepared {
            command: Command::new("cadrumo-timed-out-preparation-must-never-launch"),
            person: Box::new(|| Ok(None)),
            local_engine_default:
                cadrumo_application::provisioning::local_ai::LocalEngine::LlamaCpp,
        })
    });
    let supervisor = Supervisor::new(
        observe,
        every(Duration::from_millis(1)),
        Some(launch),
        Arc::new(Diagnostics::default()),
    )
    .timeout_within(Duration::from_millis(100));
    supervisor.status();
    entered.notified().await;
    tokio::time::timeout(Duration::from_secs(5), async {
        while supervisor.status().state
            != (State::Refused {
                code: Refusal::Timeout,
            })
        {
            tokio::task::yield_now().await;
        }
    })
    .await
    .unwrap();
    assert!(calls.load(Ordering::SeqCst) > 1);
    assert!(lock(&supervisor.shared.running).is_none());
    drop(release);
    supervisor.close().await.unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn a_profile_change_invalidates_preparation_before_its_result_can_launch() {
    struct Release(Arc<(Mutex<bool>, std::sync::Condvar)>);
    impl Drop for Release {
        fn drop(&mut self) {
            *lock(&self.0.0) = true;
            self.0.1.notify_all();
        }
    }
    let source = Arc::new(Mutex::new(observed(true, true, Some("A"))));
    let current = source.clone();
    let observe: Observe = Arc::new(move || {
        let status = lock(&current).clone();
        Box::pin(async move { status })
    });
    let entered = Arc::new(Notify::new());
    let arriving = entered.clone();
    let release = Release(Arc::new((Mutex::new(false), std::sync::Condvar::new())));
    let gate = release.0.clone();
    let launch: Launch = Arc::new(move |_, _| {
        arriving.notify_one();
        let mut open = lock(&gate.0);
        while !*open {
            open = gate.1.wait(open).unwrap();
        }
        Ok(Prepared {
            command: Command::new("cadrumo-cancelled-preparation-must-never-launch"),
            person: Box::new(|| Ok(None)),
            local_engine_default:
                cadrumo_application::provisioning::local_ai::LocalEngine::LlamaCpp,
        })
    });
    let supervisor = Supervisor::new(
        observe,
        every(Duration::from_millis(1)),
        Some(launch),
        Arc::new(Diagnostics::default()),
    );
    supervisor.status();
    entered.notified().await;
    *lock(&source) = observed(true, true, Some("B"));
    tokio::time::timeout(Duration::from_secs(10), async {
        loop {
            if lock(&supervisor.shared.preparing)
                .as_ref()
                .is_some_and(|pending| pending.cancelled.load(Ordering::Acquire))
            {
                break;
            }
            tokio::task::yield_now().await;
        }
    })
    .await
    .unwrap();
    assert!(lock(&supervisor.shared.running).is_none());
    drop(release);
    supervisor.close().await.unwrap();
    assert!(lock(&supervisor.shared.running).is_none());
    assert!(supervisor.gateway().is_none());
}

/// A supervisor whose service never launches here, so a test drives its
/// status and admission itself, with `limit` as its start bound.
fn starting_supervisor(limit: Duration) -> Arc<Supervisor> {
    let observe: Observe = Arc::new(|| Box::pin(async { observed(false, true, None) }));
    let supervisor = Supervisor::new(
        observe,
        every(Duration::from_secs(60)),
        None,
        Arc::new(Diagnostics::default()),
    )
    .timeout_within(limit);
    super::publish(&supervisor.shared, State::Starting);
    Arc::new(supervisor)
}

/// The provider settings status read the window asks for.
fn provider_settings_status(
    supervisor: &Supervisor,
) -> std::result::Result<
    crate::shell::provider_settings::wire::Status,
    crate::shell::provider_settings::wire::CommandFailure,
> {
    crate::shell::provider_settings::when_admitted(
        || supervisor.admin_now(),
        || {
            crate::shell::provider_settings::read_status(
                || supervisor.administer(serde_json::json!({"action":"status"}), None),
                Duration::ZERO,
                crate::shell::provider_settings::STATUS_BUSY_PATIENCE,
            )
        },
    )
}

fn admin_unavailable(
    result: std::result::Result<
        crate::shell::provider_settings::wire::Status,
        crate::shell::provider_settings::wire::CommandFailure,
    >,
) -> bool {
    matches!(
        result,
        Err(crate::shell::provider_settings::wire::CommandFailure::Host(error))
            if error.code == ErrorCode::ReadFailed
                && error.reason.as_deref() == Some("agent_admin_unavailable")
    )
}

#[test]
fn provider_settings_status_asked_while_starting_answers_busy_at_once_then_reads_once_admitted() {
    use std::io::{Read, Write};
    use std::net::TcpListener;
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    let server = std::thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        let mut frame = || {
            let mut header = [0; 4];
            stream.read_exact(&mut header).unwrap();
            let mut data = vec![0; u32::from_be_bytes(header) as usize];
            stream.read_exact(&mut data).unwrap();
            data
        };
        let _bearer = frame();
        let request: serde_json::Value = serde_json::from_slice(&frame()).unwrap();
        assert_eq!(request["action"], "status");
        let reply = serde_json::to_vec(&serde_json::json!({"version":1,"request_id":request["request_id"],"result":{"providers":[],"reads_pending":false}})).unwrap();
        stream
            .write_all(&(reply.len() as u32).to_be_bytes())
            .unwrap();
        stream.write_all(&reply).unwrap();
    });
    let supervisor = starting_supervisor(Duration::from_secs(60));
    // Asked before the endpoint is admitted, as the window does on its first
    // open, the read answers busy at once instead of waiting for the start.
    let asked = std::time::Instant::now();
    assert!(matches!(
        provider_settings_status(&supervisor),
        Err(crate::shell::provider_settings::wire::CommandFailure::Refused(refused))
            if refused.code == crate::shell::provider_settings::wire::Refusal::Busy
    ));
    assert!(asked.elapsed() < Duration::from_secs(1));
    super::admit(
        &supervisor.shared,
        super::super::admin::Endpoint {
            port,
            bearer: Arc::new(Zeroizing::new("test".to_owned())),
            generation: 1,
            gate: Default::default(),
        },
    );
    let status = provider_settings_status(&supervisor).expect("the read answers once admitted");
    assert!(status.providers.is_empty());
    server.join().unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn provider_settings_status_before_the_first_observation_answers_busy_never_refused() {
    // The window opens the settings as the agent is asked to start: the
    // supervisor has not yet observed the sign-in, so its state is still the
    // initial Stopped, and the read answers busy rather than refusing.
    let entered = Arc::new(Notify::new());
    let notify = entered.clone();
    let observe: Observe = Arc::new(move || {
        let notify = notify.clone();
        Box::pin(async move {
            notify.notify_one();
            std::future::pending().await
        })
    });
    let launch: Launch = Arc::new(|_, _| panic!("an unobserved sign-in cannot authorize launch"));
    let supervisor = Supervisor::new(
        observe,
        every(Duration::from_millis(1)),
        Some(launch),
        Arc::new(Diagnostics::default()),
    );
    let asked = std::time::Instant::now();
    assert!(matches!(
        provider_settings_status(&supervisor),
        Err(crate::shell::provider_settings::wire::CommandFailure::Refused(refused))
            if refused.code == crate::shell::provider_settings::wire::Refusal::Busy
    ));
    assert!(asked.elapsed() < Duration::from_secs(1));
    entered.notified().await;
    assert_eq!(supervisor.status().state, State::Stopped);
    tokio::time::timeout(Duration::from_secs(1), supervisor.close())
        .await
        .unwrap()
        .unwrap();
    assert!(admin_unavailable(provider_settings_status(&supervisor)));
}

#[test]
fn provider_settings_status_without_a_starting_service_is_refused_at_once() {
    let supervisor = starting_supervisor(Duration::from_secs(60));
    super::publish(
        &supervisor.shared,
        State::Refused {
            code: Refusal::SignedOut,
        },
    );
    let asked = std::time::Instant::now();
    assert_eq!(supervisor.await_admin(), super::AdminWait::NotStarting);
    assert!(admin_unavailable(provider_settings_status(&supervisor)));
    assert!(asked.elapsed() < Duration::from_secs(10));
}

#[test]
fn administration_waiting_on_a_start_that_fails_is_released_with_its_refusal() {
    let supervisor = starting_supervisor(Duration::from_secs(60));
    let read = {
        let supervisor = supervisor.clone();
        std::thread::spawn(move || {
            crate::shell::provider_settings::when_admitted(
                || supervisor.await_admin(),
                || {
                    crate::shell::provider_settings::read_status(
                        || supervisor.administer(serde_json::json!({"action":"status"}), None),
                        Duration::ZERO,
                        crate::shell::provider_settings::STATUS_BUSY_PATIENCE,
                    )
                },
            )
        })
    };
    std::thread::sleep(Duration::from_millis(100));
    assert!(!read.is_finished());
    let asked = std::time::Instant::now();
    super::publish(
        &supervisor.shared,
        State::Refused {
            code: Refusal::ServiceFailed,
        },
    );
    assert!(admin_unavailable(read.join().unwrap()));
    assert!(asked.elapsed() < Duration::from_secs(10));
}

#[test]
fn provider_settings_status_past_the_start_bound_answers_busy() {
    let supervisor = starting_supervisor(Duration::from_millis(50));
    let mut called = false;
    let result = crate::shell::provider_settings::when_admitted(
        || supervisor.await_admin(),
        || {
            called = true;
            Ok(())
        },
    );
    assert!(!called);
    let Err(crate::shell::provider_settings::wire::CommandFailure::Refused(refused)) = result
    else {
        panic!("a service still starting past the bound is busy");
    };
    assert_eq!(
        serde_json::to_value(refused).unwrap(),
        serde_json::json!({"code":"busy"})
    );
    assert!(matches!(
        provider_settings_status(&supervisor),
        Err(crate::shell::provider_settings::wire::CommandFailure::Refused(_))
    ));
}

#[cfg(windows)]
mod live;

/// A supervisor whose launcher counts its starts, observing `source` every
/// millisecond, with `bound` for the runtime's readiness.
fn awaiting(
    source: &Arc<Mutex<Result<Observation>>>,
    bound: Duration,
) -> (Supervisor, Arc<AtomicU64>, Arc<Diagnostics>) {
    let current = source.clone();
    let observe: Observe = Arc::new(move || {
        let result = lock(&current).clone();
        Box::pin(async move { result })
    });
    let attempts = Arc::new(AtomicU64::new(0));
    let count = attempts.clone();
    let launch: Launch = Arc::new(move |_, _| {
        count.fetch_add(1, Ordering::SeqCst);
        Err(ApplicationError::new(
            ErrorCode::SpawnFailed,
            Operation::Cli,
        ))
    });
    let diagnostics = Arc::new(Diagnostics::default());
    let supervisor = Supervisor::with_timing(
        observe,
        every(Duration::from_millis(1)),
        Some(launch),
        diagnostics.clone(),
        Duration::from_millis(1),
        Duration::from_secs(60),
    )
    .timeout_within(bound);
    (supervisor, attempts, diagnostics)
}

fn refusals(diagnostics: &Diagnostics) -> Vec<Refusal> {
    diagnostics
        .snapshot(u64::MAX)
        .events
        .into_iter()
        .filter_map(|event| match event.service {
            Some(ServiceFact::AgentRefused { reason }) => Some(reason),
            _ => None,
        })
        .collect()
}

#[tokio::test]
async fn a_runtime_not_ready_yet_is_waited_for_and_the_agent_starts_once_it_is() {
    let source = Arc::new(Mutex::new(observed(true, false, Some("A"))));
    let (supervisor, attempts, diagnostics) = awaiting(&source, Duration::from_secs(60));
    supervisor.status();
    tokio::time::sleep(Duration::from_millis(50)).await;
    // Waiting: nothing refused, nothing started, and a read made now is told
    // the service is still starting.
    assert_eq!(supervisor.status().state, State::Stopped);
    assert_eq!(attempts.load(Ordering::SeqCst), 0);
    assert!(refusals(&diagnostics).is_empty());
    assert!(matches!(
        supervisor.admin_now(),
        super::AdminWait::StillStarting
    ));
    *lock(&source) = observed(true, true, Some("A"));
    tokio::time::timeout(Duration::from_secs(5), async {
        while attempts.load(Ordering::SeqCst) == 0 {
            tokio::time::sleep(Duration::from_millis(2)).await;
        }
    })
    .await
    .unwrap();
    assert!(
        !refusals(&diagnostics).contains(&Refusal::RuntimeUnavailable),
        "a runtime that became ready in time is never refused"
    );
    supervisor.close().await.unwrap();
}

#[tokio::test]
async fn a_runtime_unavailable_past_its_readiness_bound_is_refused() {
    let source = Arc::new(Mutex::new(observed(true, false, Some("A"))));
    let (supervisor, attempts, diagnostics) = awaiting(&source, Duration::from_millis(80));
    supervisor.status();
    tokio::time::timeout(Duration::from_secs(5), async {
        while supervisor.status().state
            != (State::Refused {
                code: Refusal::RuntimeUnavailable,
            })
        {
            tokio::time::sleep(Duration::from_millis(2)).await;
        }
    })
    .await
    .unwrap();
    assert_eq!(refusals(&diagnostics), [Refusal::RuntimeUnavailable]);
    assert_eq!(attempts.load(Ordering::SeqCst), 0);
    supervisor.close().await.unwrap();
}

#[tokio::test]
async fn a_sign_in_after_a_sign_out_is_not_answered_as_signed_out_meanwhile() {
    let source = Arc::new(Mutex::new(observed(false, true, Some("A"))));
    let (supervisor, _, _) = awaiting(&source, Duration::from_secs(60));
    supervisor.status();
    tokio::time::timeout(Duration::from_secs(5), async {
        while supervisor.status().state
            != (State::Refused {
                code: Refusal::SignedOut,
            })
        {
            tokio::time::sleep(Duration::from_millis(2)).await;
        }
    })
    .await
    .unwrap();
    // The next sign-in observation is awaited as Stopped, before it is read.
    tokio::time::timeout(Duration::from_secs(5), async {
        while supervisor.status().state != State::Stopped {
            tokio::time::sleep(Duration::from_millis(1)).await;
        }
    })
    .await
    .unwrap();
    supervisor.close().await.unwrap();
}

fn fenced() -> Result<Observation> {
    Err(
        ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
            .with_reason("sign_in_mutation_in_progress"),
    )
}

async fn until_state(supervisor: &Supervisor, state: State) {
    tokio::time::timeout(Duration::from_secs(5), async {
        while supervisor.status().state != state {
            tokio::time::sleep(Duration::from_millis(2)).await;
        }
    })
    .await
    .unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn an_unanswered_first_sign_in_observation_is_refused_as_timed_out_past_the_start_bound() {
    // A launcher's service is read as starting until the sign-in is observed;
    // an observation that never answers must not keep it starting for ever.
    let observe: Observe = Arc::new(|| Box::pin(std::future::pending()));
    let launch: Launch = Arc::new(|_, _| panic!("an unobserved sign-in cannot authorize launch"));
    let diagnostics = Arc::new(Diagnostics::default());
    let supervisor = Supervisor::new(
        observe,
        every(Duration::from_millis(1)),
        Some(launch),
        diagnostics.clone(),
    )
    .timeout_within(Duration::from_millis(80));
    supervisor.status();
    assert!(matches!(
        supervisor.admin_now(),
        super::AdminWait::StillStarting
    ));
    until_state(
        &supervisor,
        State::Refused {
            code: Refusal::Timeout,
        },
    )
    .await;
    assert!(matches!(
        supervisor.admin_now(),
        super::AdminWait::NotStarting
    ));
    tokio::time::sleep(Duration::from_millis(100)).await;
    assert_eq!(
        refusals(&diagnostics),
        [Refusal::Timeout],
        "refused once, not repeatedly"
    );
    tokio::time::timeout(Duration::from_secs(1), supervisor.close())
        .await
        .unwrap()
        .unwrap();
}

#[tokio::test]
async fn a_sign_in_fenced_past_the_start_bound_is_refused_as_timed_out_and_starts_once_decided() {
    let source = Arc::new(Mutex::new(fenced()));
    let (supervisor, attempts, diagnostics) = awaiting(&source, Duration::from_millis(80));
    supervisor.status();
    tokio::time::sleep(Duration::from_millis(20)).await;
    // Within the bound a fenced sign-in is waited for as starting.
    assert_eq!(supervisor.status().state, State::Stopped);
    assert!(refusals(&diagnostics).is_empty());
    until_state(
        &supervisor,
        State::Refused {
            code: Refusal::Timeout,
        },
    )
    .await;
    // Still fenced: the refusal stands, published once, and nothing is started.
    tokio::time::sleep(Duration::from_millis(100)).await;
    assert_eq!(
        supervisor.status().state,
        State::Refused {
            code: Refusal::Timeout
        }
    );
    assert_eq!(refusals(&diagnostics), [Refusal::Timeout]);
    assert_eq!(attempts.load(Ordering::SeqCst), 0);
    // A decided sign-in starts the agent as usual.
    *lock(&source) = observed(true, true, Some("A"));
    tokio::time::timeout(Duration::from_secs(5), async {
        while attempts.load(Ordering::SeqCst) == 0 {
            tokio::time::sleep(Duration::from_millis(2)).await;
        }
    })
    .await
    .unwrap();
    supervisor.close().await.unwrap();
}

#[tokio::test]
async fn a_sign_in_fenced_within_the_start_bound_is_waited_for_without_a_refusal() {
    let source = Arc::new(Mutex::new(fenced()));
    let (supervisor, attempts, diagnostics) = awaiting(&source, Duration::from_secs(60));
    supervisor.status();
    tokio::time::sleep(Duration::from_millis(100)).await;
    assert_eq!(supervisor.status().state, State::Stopped);
    assert!(matches!(
        supervisor.admin_now(),
        super::AdminWait::StillStarting
    ));
    assert!(refusals(&diagnostics).is_empty());
    *lock(&source) = observed(true, true, Some("A"));
    tokio::time::timeout(Duration::from_secs(5), async {
        while attempts.load(Ordering::SeqCst) == 0 {
            tokio::time::sleep(Duration::from_millis(2)).await;
        }
    })
    .await
    .unwrap();
    supervisor.close().await.unwrap();
}
