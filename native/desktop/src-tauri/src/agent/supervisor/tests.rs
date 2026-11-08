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
    // authorization epoch or replenishes an exhausted attempt budget.
    for unavailable in [
        Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)),
        observed(true, false, Some("A")),
    ] {
        *lock(&source) = unavailable;
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
            person: None,
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
            person: None,
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

#[cfg(windows)]
mod live;
