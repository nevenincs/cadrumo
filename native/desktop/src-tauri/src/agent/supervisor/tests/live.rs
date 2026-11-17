use super::super::protocol::{Launch, Observation, Observe, Prepared, State};
use super::super::retry::RetryBudget;
use super::super::{STARTUP_TIMEOUT, Supervisor, handle, lock, next_due, retire_failed_person};
use super::{every, observed};
use crate::agent::{launcher::Event, runner::Signal};
use cadrumo_application::diagnostics::Diagnostics;
use cadrumo_application::diagnostics::service::AgentRefusal as Refusal;
use cadrumo_application::diagnostics::service::{AgentStopCause, ServiceFact};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::ipc::Channel;

use crate::agent::runner::tests::{alive, launcher_script, powershell, reported};
use crate::shell::sign_in::process::tests::{Gate, HANG_GUARD};
use tauri::ipc::InvokeResponseBody;
use tokio::sync::watch;

#[tokio::test(flavor = "multi_thread")]
async fn launcher_refusal_is_handled_while_status_read_is_pending() {
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
    let launch: Launch = Arc::new(|_, _| {
        Ok(Prepared {
            person: Box::new(|| Ok(None)),
            local_engine_default:
                cadrumo_application::provisioning::local_ai::LocalEngine::LlamaCpp,
            command: powershell(
                "$null = [Console]::In.ReadLine(); Start-Sleep -Milliseconds 500; [Console]::Out.WriteLine('{\"event\":\"agent_refused\",\"code\":\"agent_service_incompatible\"}'); exit 3",
            ),
        })
    });
    let supervisor = Supervisor::with_timing(
        observe,
        every(Duration::from_millis(5)),
        Some(launch),
        Arc::new(Diagnostics::default()),
        Duration::from_secs(5),
        Duration::from_secs(60),
    );
    supervisor.status();
    tokio::time::timeout(Duration::from_secs(20), async {
        loop {
            if supervisor.status().state
                == (State::Refused {
                    code: Refusal::ServiceIncompatible,
                })
                && lock(&supervisor.shared.running).is_none()
            {
                break;
            }
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
    })
    .await
    .unwrap();
    assert!(
        calls.load(Ordering::SeqCst) >= 2,
        "the second status read is still pending"
    );
    assert!(supervisor.gateway().is_none());
    supervisor.close().await.unwrap();
}

struct Rig {
    supervisor: Supervisor,
    observation: Arc<Mutex<Result<Observation>>>,
    statuses: Arc<Mutex<Vec<serde_json::Value>>>,
    diagnostics: Arc<Diagnostics>,
    holders: Arc<Mutex<Vec<HolderFixture>>>,
    /// Moves on at each published status and each recorded diagnostic.
    recorded: Arc<watch::Sender<u64>>,
    /// Holds a retiring launcher at each step the test inspects.
    gate: Option<Gate>,
}

impl Rig {
    /// Lets the launcher go on once it has reached `point`.
    fn release(&mut self, point: &str) {
        let gate = self.gate.as_mut().expect("this launcher waits at a gate");
        tokio::task::block_in_place(|| {
            gate.reached(point);
            gate.go();
        });
    }
}

struct HolderFixture {
    pid: u32,
    identity: serde_json::Value,
}

/// Controlled holder-protocol evidence over real child pipes, not an
/// installed runtime or a proof of native person authentication.
fn held_protocol_fixture(
    profile: &str,
    ignore_end: bool,
    retire_at_gate: Option<&str>,
    service_at_gate: Option<&str>,
    admission_at_gate: Option<&str>,
) -> (Prepared, HolderFixture) {
    let profile_id = match profile {
        "A" => "11111111-1111-4111-8111-111111111111",
        "B" => "22222222-2222-4222-8222-222222222222",
        _ => panic!("unexpected fixture profile"),
    };
    let identity = serde_json::json!({
        "kind": "session_held",
        "profile_id": profile_id,
        "session_id": super::super::super::person::request_id().unwrap(),
        "runtime_boot_id": super::super::super::person::request_id().unwrap(),
        "connection_id": super::super::super::person::request_id().unwrap(),
    });
    let recipient = super::super::super::person::request_id().unwrap();
    let reply = serde_json::json!({
        "kind": "service_connected",
        "request_id": super::super::super::person::request_id().unwrap(),
        "runtime_boot_id": identity["runtime_boot_id"],
        "connection_id": identity["connection_id"],
        "profile_id": profile_id,
        "service_id": "cadrumo-agent-service",
        "lease": {
            "lease_id": super::super::super::person::request_id().unwrap(),
            "session_id": super::super::super::person::request_id().unwrap(),
            "parent_session_id": identity["session_id"],
            "profile_id": profile_id,
            "runtime_boot_id": identity["runtime_boot_id"],
            "connection_id": recipient,
            "service_id": "cadrumo-agent-service",
            "descriptor_digest": "a".repeat(64),
        },
    });
    let admission_gate = admission_at_gate
        .map(|gate| format!("{gate}Wait-Gate 'admission'; "))
        .unwrap_or_default();
    let holder_script = format!(
        "& {{ [Console]::Out.WriteLine('{identity}'); [Console]::Out.Flush(); \
                 while (($line = [Console]::In.ReadLine()) -ne $null) {{ \
                     $request = $line | ConvertFrom-Json; \
                     if ($request.action -ne 'service_admission' -or \
                         $request.recipient_connection_id -ne '{recipient}' -or \
                         $request.service_id -ne 'cadrumo-agent-service' -or \
                         $request.psobject.Properties.Name.Count -ne 4) {{ exit 7 }}; \
                     {admission_gate}$reply = '{reply}' | ConvertFrom-Json; \
                     $reply.request_id = $request.request_id; \
                     [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress -Depth 8)); \
                     [Console]::Out.Flush(); \
                 }} }}"
    );
    let person = crate::agent::person::Person::hold_answering_within(
        powershell(&holder_script),
        profile_id,
        HANG_GUARD,
    )
    .unwrap();
    assert_eq!(person.identity, identity);
    let witness = HolderFixture {
        pid: person.child_id(),
        identity,
    };
    let ready = serde_json::json!({
        "event": "service_ready",
        "protocol": 1,
        "admin_port": 4001,
        "runtime_boot_id": witness.identity["runtime_boot_id"],
        "connection_id": recipient,
        "profile_id": profile_id,
        "service_id": "cadrumo-agent-service",
    });
    // The existing launcher first reads and checks both independently
    // minted startup credentials. Add only the service readiness frame
    // before its existing agent-ready frame and child-tree behavior.
    let mut script = launcher_script(ignore_end);
    if let Some(gate) = retire_at_gate {
        let normal_exit = r#"$null = [Console]::In.ReadToEnd(); [Console]::Out.WriteLine('{"event":"agent_stopped","reason":"agent_host_closed"}'); exit 0"#;
        assert!(script.contains(normal_exit));
        // Each step waits for the test, never for an amount of time.
        script = script.replace(
            normal_exit,
            &format!(
                r#"{gate}Wait-Gate 'ready'; [Console]::Out.WriteLine('{{"event":"agent_stopped","reason":"agent_retired"}}'); [Console]::Out.Flush(); Wait-Gate 'retired'; exit 3"#
            ),
        );
    }
    let marker = "$grandchild = ";
    assert_eq!(script.matches(marker).count(), 1);
    let service_gate = service_at_gate
        .map(|gate| format!("{gate}Wait-Gate 'service'; "))
        .unwrap_or_default();
    let script = script.replacen(
        marker,
        &format!(
            "{service_gate}[Console]::Out.WriteLine('{ready}'); [Console]::Out.Flush(); {marker}"
        ),
        1,
    );
    (
        Prepared {
            person: Box::new(move || Ok(Some(Arc::new(Mutex::new(person))))),
            command: powershell(&script),
            local_engine_default:
                cadrumo_application::provisioning::local_ai::LocalEngine::LlamaCpp,
        },
        witness,
    )
}

fn rig(ignore_end: bool, retire_after_ready: bool) -> Rig {
    rig_with_service_gate(ignore_end, retire_after_ready, false, false)
}

fn rig_with_service_gate(
    ignore_end: bool,
    retire_after_ready: bool,
    wait_for_service: bool,
    wait_for_admission: bool,
) -> Rig {
    let observation = Arc::new(Mutex::new(observed(true, true, Some("A"))));
    let source = observation.clone();
    let observe: Observe = Arc::new(move || {
        let current = lock(&source).clone();
        Box::pin(async move { current })
    });
    let holders = Arc::new(Mutex::new(Vec::new()));
    let witnesses = holders.clone();
    let gate = (retire_after_ready || wait_for_service || wait_for_admission).then(Gate::new);
    let gate_script = gate
        .as_ref()
        .filter(|_| retire_after_ready)
        .map(Gate::script);
    let service_gate = gate.as_ref().filter(|_| wait_for_service).map(Gate::script);
    let admission_gate = gate
        .as_ref()
        .filter(|_| wait_for_admission)
        .map(Gate::script);
    let launch: Launch = Arc::new(move |_, profile| {
        let (prepared, witness) = held_protocol_fixture(
            profile,
            ignore_end,
            gate_script.as_deref(),
            service_gate.as_deref(),
            admission_gate.as_deref(),
        );
        lock(&witnesses).push(witness);
        Ok(prepared)
    });
    let recorded = Arc::new(watch::Sender::new(0u64));
    let diagnostics = Arc::new(Diagnostics::default());
    let moved = recorded.clone();
    diagnostics.on_recorded(Arc::new(move || moved.send_modify(|count| *count += 1)));
    let supervisor = Supervisor::with_timing(
        observe,
        every(Duration::from_millis(100)),
        Some(launch),
        diagnostics.clone(),
        Duration::from_millis(if ignore_end { 500 } else { 10_000 }),
        Duration::from_secs(60),
    );
    let supervisor = if wait_for_service {
        supervisor
    } else {
        supervisor.timeout_within(HANG_GUARD)
    };
    let statuses = Arc::new(Mutex::new(Vec::new()));
    let sink = statuses.clone();
    let moved = recorded.clone();
    supervisor.subscribe(Channel::new(move |body| {
        let InvokeResponseBody::Json(body) = body else {
            panic!("expected a JSON status")
        };
        sink.lock()
            .unwrap()
            .push(serde_json::from_str(&body).unwrap());
        moved.send_modify(|count| *count += 1);
        Ok(())
    }));
    Rig {
        supervisor,
        observation,
        statuses,
        diagnostics,
        holders,
        recorded,
        gate,
    }
}

#[tokio::test(flavor = "multi_thread")]
async fn cold_service_registration_can_finish_after_the_runtime_exchange_window() {
    let mut rig = rig_with_service_gate(false, false, true, false);
    service_waiting(&mut rig).await;
    // Account for a ten-second handshake and a 120-second registration
    // without spending that time asleep in a process fixture.
    lock(&rig.supervisor.shared.running)
        .as_mut()
        .unwrap()
        .started = Instant::now() - Duration::from_secs(181);
    let due = next_due(&rig.supervisor.shared, &RetryBudget::default()).unwrap();
    assert!(due > Instant::now(), "a valid registration still has time");
    rig.gate.as_mut().unwrap().go();
    until_seen(&rig, "cold service ready", || {
        matches!(rig.supervisor.status().state, State::Ready { .. }).then_some(())
    })
    .await;
    assert_eq!(lock(&rig.holders).len(), 1, "no launch was retried");
    rig.supervisor.close().await.unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn a_service_that_never_registers_still_exhausts_its_start_deadline() {
    let mut rig = rig_with_service_gate(false, false, true, false);
    service_waiting(&mut rig).await;
    lock(&rig.supervisor.shared.running)
        .as_mut()
        .unwrap()
        .started = Instant::now() - (STARTUP_TIMEOUT + Duration::from_secs(1));
    rig.supervisor.shared.wake.notify_one();
    until_seen(&rig, "unregistered service stopped", || {
        (matches!(
            rig.supervisor.status().state,
            State::Refused {
                code: Refusal::Timeout
            }
        ) && lock(&rig.supervisor.shared.running).is_none())
        .then_some(())
    })
    .await;
    assert!(rig.supervisor.gateway().is_none());
    assert!(lock(&rig.supervisor.shared.admin).is_none());
    rig.supervisor.close().await.unwrap();
}

async fn service_waiting(rig: &mut Rig) {
    tokio::task::block_in_place(|| rig.gate.as_mut().unwrap().reached("service"));
    // The child can reach its gate before start_child returns to the
    // supervisor that records ownership of it.
    tokio::time::timeout(HANG_GUARD, async {
        while lock(&rig.supervisor.shared.running).is_none() {
            tokio::task::yield_now().await;
        }
    })
    .await
    .unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn sign_out_fences_an_admission_that_has_not_answered_and_discards_its_late_reply() {
    let mut rig = rig_with_service_gate(false, false, false, true);
    tokio::task::block_in_place(|| rig.gate.as_mut().unwrap().reached("admission"));
    *lock(&rig.observation) = observed(false, true, Some("A"));
    until_seen(&rig, "sign-out while admission waits", || {
        matches!(
            rig.supervisor.status().state,
            State::Refused {
                code: Refusal::SignedOut
            }
        )
        .then_some(())
    })
    .await;
    assert!(lock(&rig.supervisor.shared.admin).is_none());
    assert!(rig.supervisor.gateway().is_none());
    rig.gate.as_mut().unwrap().go();
    rig.supervisor.close().await.unwrap();
    assert!(
        lock(&rig.supervisor.shared.admin).is_none(),
        "late admission cannot publish"
    );
}

/// What `seen` finds once a published status or recorded diagnostic
/// makes it true. The guard bounds only a supervisor that hangs.
async fn until_seen<T>(rig: &Rig, what: &str, mut seen: impl FnMut() -> Option<T>) -> T {
    let mut recorded = rig.recorded.subscribe();
    tokio::time::timeout(HANG_GUARD, async {
        loop {
            if let Some(found) = seen() {
                return found;
            }
            recorded.changed().await.unwrap();
        }
    })
    .await
    .unwrap_or_else(|_| panic!("{what}: {:?}", rig.statuses.lock().unwrap()))
}

/// The first status in `state` published at or after index `from`.
async fn until(rig: &Rig, from: usize, state: &str) -> serde_json::Value {
    until_seen(rig, &format!("never {state}"), || {
        let statuses = rig.statuses.lock().unwrap();
        statuses[from.min(statuses.len())..]
            .iter()
            .find(|status| status["state"] == state)
            .cloned()
    })
    .await
}

/// The launcher, its reported grandchild, and its real held-protocol child.
async fn serving(rig: &Rig, from: usize) -> (u32, u32, u32) {
    let ready = until(rig, from, "ready").await;
    let (grandchild, length) = reported(ready["agent_version"].as_str().unwrap());
    assert_eq!(length, "64", "the launcher read the minted bearer");
    let gateway = rig.supervisor.gateway().unwrap();
    assert_eq!(gateway.port, 4000);
    let admin_bearer = {
        let admin = lock(&rig.supervisor.shared.admin);
        let endpoint = admin
            .as_ref()
            .expect("service admitted before agent readiness");
        assert_eq!(endpoint.port, 4001);
        assert_eq!(endpoint.generation, gateway.generation);
        assert_eq!(endpoint.bearer.len(), 64);
        assert_ne!(endpoint.bearer.as_str(), gateway.bearer.as_str());
        endpoint.bearer.clone()
    };
    let snapshot = rig.diagnostics.snapshot(u64::MAX);
    let ready = snapshot
        .events
        .iter()
        .rev()
        .find(|event| {
            matches!(
                event.service,
                Some(ServiceFact::AgentReady {
                    gateway_port: 4000,
                    ..
                })
            )
        })
        .unwrap();
    let process = ready.status.as_ref().unwrap();
    assert_eq!(
        process.role,
        cadrumo_application::process::status::ProcessRole::AgentLauncher
    );
    assert!(process.pid > 0);
    assert!(
        !serde_json::to_string(&snapshot.events)
            .unwrap()
            .contains(gateway.bearer.as_str())
    );
    assert!(
        !serde_json::to_string(&snapshot.events)
            .unwrap()
            .contains(admin_bearer.as_str())
    );
    assert_eq!(gateway.workspace_root, r"C:\lane\ws");
    assert_eq!(gateway.bearer.len(), 64);
    let (launcher, person) = {
        let running = lock(&rig.supervisor.shared.running);
        let running = running.as_ref().unwrap();
        (running.supervised.id(), running.person.clone().unwrap())
    };
    let person = lock(&person);
    let holders = lock(&rig.holders);
    let witness = holders
        .iter()
        .find(|holder| holder.pid == person.child_id())
        .unwrap();
    assert_eq!(person.identity, witness.identity);
    assert!(
        alive(witness.pid),
        "the original held-protocol child is retained"
    );
    (launcher, grandchild, witness.pid)
}

/// The running processes among `pids`, each as its pid and start time:
/// once a process ends, another process can be given its pid.
fn instances(pids: (u32, u32, u32)) -> Vec<String> {
    let output = powershell(&format!(
        "foreach ($id in {},{},{}) {{ \
                     $p = Get-Process -Id $id -ErrorAction SilentlyContinue; \
                     if ($p) {{ [Console]::Out.WriteLine(\"$id@$($p.StartTime.Ticks)\") }} }}; \
                 exit 0",
        pids.0, pids.1, pids.2
    ))
    .output()
    .unwrap();
    assert!(output.status.success());
    String::from_utf8(output.stdout)
        .unwrap()
        .lines()
        .map(str::to_owned)
        .collect()
}

/// Every one of the launcher's processes, while it serves.
fn started(pids: (u32, u32, u32)) -> Vec<String> {
    let started = instances(pids);
    assert!(
        started.len() == 3 && started.iter().all(|process| !process.ends_with('@')),
        "every started process runs: {started:?}"
    );
    started
}

/// Once the supervisor has finished stopping them, none of the started
/// processes remains: the job is empty and the holder reaped.
fn gone(pids: (u32, u32, u32), started: &[String]) {
    let running = instances(pids);
    assert!(
        started.iter().all(|process| !running.contains(process)),
        "a started process survived: {running:?}"
    );
}

#[tokio::test(flavor = "multi_thread")]
async fn a_shared_person_failure_retires_a_ready_service_and_allows_a_fresh_start() {
    let rig = rig(false, false);
    serving(&rig, 0).await;
    let original = rig.supervisor.gateway().unwrap();
    let person = lock(&rig.supervisor.shared.running)
        .as_ref()
        .unwrap()
        .person
        .clone()
        .unwrap();
    // This holder deliberately cannot answer a background language
    // request. Its launcher stays alive until the supervisor stops it.
    let error = tauri::async_runtime::spawn_blocking(move || {
        lock(&person)
            .exchange(serde_json::json!({"action":"language_read"}))
            .unwrap_err()
    })
    .await
    .unwrap();
    until(&rig, 0, "refused").await;
    until_seen(&rig, "failed service not retired", || {
        let stopped = lock(&rig.supervisor.shared.running).is_none();
        stopped.then_some(())
    })
    .await;
    assert!(rig.supervisor.gateway().is_none());
    assert!(
        rig.diagnostics
            .snapshot(u64::MAX)
            .events
            .iter()
            .any(|event| {
                event
                    .failure
                    .as_ref()
                    .is_some_and(|failure| failure.reason == error.reason)
            })
    );
    // A new start gets its own admitted session. It does not retry
    // the background request that lost the old one.
    let from = lock(&rig.statuses).len();
    rig.supervisor.retry();
    serving(&rig, from).await;
    assert!(!original.same_instance(&rig.supervisor.gateway().unwrap()));
    rig.supervisor.close().await.unwrap();
}

/// The causes of each service stop the rig recorded, stopping and stopped, in order.
fn stop_causes(rig: &Rig) -> Vec<AgentStopCause> {
    rig.diagnostics
        .snapshot(u64::MAX)
        .events
        .iter()
        .filter_map(|event| match event.service {
            Some(ServiceFact::AgentStopping { cause } | ServiceFact::AgentStopped { cause }) => {
                Some(cause)
            }
            _ => None,
        })
        .collect()
}

#[tokio::test(flavor = "multi_thread")]
async fn a_retired_person_stops_the_service_without_a_service_failure_retry() {
    let rig = rig(false, false);
    serving(&rig, 0).await;
    let generation = rig.supervisor.gateway().unwrap().generation;
    // Keep the next authority observation retired as well.
    *rig.observation.lock().unwrap() = observed(false, true, Some("A"));
    let from = lock(&rig.statuses).len();
    let retry = retire_failed_person(
        &rig.supervisor.shared,
        generation,
        ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
            .with_reason("person_session_retired"),
    )
    .await;
    assert!(!retry);
    let refused = until(&rig, from, "refused").await;
    assert_eq!(refused["code"], "agent_signed_out");
    assert_eq!(
        stop_causes(&rig),
        [AgentStopCause::SignedOut, AgentStopCause::SignedOut]
    );
    assert!(rig.supervisor.signed_out());
    assert!(rig.supervisor.gateway().is_none());
    assert!(lock(&rig.supervisor.shared.running).is_none());
    assert!(
        !rig.diagnostics
            .snapshot(u64::MAX)
            .events
            .iter()
            .any(|event| {
                event.failure.is_some()
                    || matches!(event.service, Some(ServiceFact::AgentRetryScheduled { .. }))
            })
    );
    // Signing in again starts a service whose calls are no longer the sign-out's.
    *rig.observation.lock().unwrap() = observed(true, true, Some("A"));
    let from = lock(&rig.statuses).len();
    rig.supervisor.retry();
    serving(&rig, from).await;
    assert!(!rig.supervisor.signed_out());
    rig.supervisor.close().await.unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn each_sign_in_trigger_stops_the_launcher_and_its_tree() {
    for (trigger, observation, published) in [
        (
            "sign-out, lock or expiry",
            observed(false, true, Some("A")),
            "refused",
        ),
        (
            "runtime unavailable",
            observed(true, false, Some("A")),
            "awaiting",
        ),
        (
            "unreadable status",
            Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)),
            "awaiting",
        ),
        (
            "local sign-in mutation in progress",
            Err(
                ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                    .with_reason("sign_in_mutation_in_progress"),
            ),
            "stopped",
        ),
        ("another profile", observed(true, true, Some("B")), "ready"),
    ] {
        let rig = rig(false, false);
        assert_eq!(
            rig.supervisor.status().lane,
            None,
            "the service reports no invented lane"
        );
        let first = serving(&rig, 0).await;
        let processes = started(first);
        let changed = rig.statuses.lock().unwrap().len();
        *rig.observation.lock().unwrap() = observation;
        // Each outcome is published only after the launcher is stopped.
        let settled = if published == "ready" || published == "awaiting" {
            "stopped"
        } else {
            published
        };
        let after = until(&rig, changed, settled).await;
        gone(first, &processes);
        assert!(
            rig.supervisor.gateway().is_none_or(|g| g.generation > 1),
            "{trigger}: the old gateway is forgotten"
        );
        if published == "ready" {
            // The new profile is served by a new launcher with a new bearer.
            let second = serving(&rig, changed).await;
            assert_ne!(second, first);
            let states: Vec<_> = rig
                .statuses
                .lock()
                .unwrap()
                .iter()
                .map(|s| s["state"].clone())
                .collect();
            assert!(
                states
                    .windows(2)
                    .any(|w| w[0] == "stopped" && w[1] == "starting"),
                "{states:?}"
            );
        } else if published == "awaiting" {
            // The runtime is waited for within its readiness bound: the
            // service stops for it and nothing is refused yet.
            assert_eq!(
                stop_causes(&rig),
                [
                    AgentStopCause::RuntimeUnavailable,
                    AgentStopCause::RuntimeUnavailable
                ],
                "{trigger}: stopping and stopped"
            );
            assert!(
                !rig.diagnostics
                    .snapshot(u64::MAX)
                    .events
                    .iter()
                    .any(|event| matches!(event.service, Some(ServiceFact::AgentRefused { .. }))),
                "{trigger}"
            );
        } else if published == "refused" {
            let signed_out = trigger.starts_with("sign-out");
            assert_eq!(
                after["code"],
                if signed_out {
                    "agent_signed_out"
                } else {
                    "agent_runtime_unavailable"
                },
                "{trigger}"
            );
            // A sign-out stops the service with its own cause, never a missing sign-in.
            let cause = if signed_out {
                AgentStopCause::SignedOut
            } else {
                AgentStopCause::RuntimeUnavailable
            };
            assert_eq!(
                stop_causes(&rig),
                [cause, cause],
                "{trigger}: stopping and stopped"
            );
            assert_eq!(rig.supervisor.signed_out(), signed_out, "{trigger}");
        }
        rig.supervisor.close().await.unwrap();
        assert!(lock(&rig.supervisor.shared.running).is_none());
    }
}

#[tokio::test(flavor = "multi_thread")]
async fn window_close_stops_the_launcher_even_when_it_ignores_its_input() {
    let rig = rig(true, false);
    rig.supervisor.status();
    let pids = serving(&rig, 0).await;
    let processes = started(pids);
    let closing = Instant::now();
    rig.supervisor.close().await.unwrap();
    assert!(closing.elapsed() < Duration::from_secs(15));
    gone(pids, &processes);
    assert!(rig.supervisor.gateway().is_none());
    // Closed for good: nothing starts again.
    rig.supervisor.status();
    tokio::time::sleep(Duration::from_millis(400)).await;
    assert!(lock(&rig.supervisor.shared.running).is_none());
}

#[tokio::test(flavor = "multi_thread")]
async fn controller_retirement_is_neutral_but_owned_service_exit_is_failed_and_retried() {
    let mut rig = rig(false, true);
    rig.supervisor.status();
    serving(&rig, 0).await;
    let generation = rig.supervisor.gateway().unwrap().generation;
    let after_ready = rig.statuses.lock().unwrap().len();
    rig.release("ready");

    // The launcher now waits at its gate: its service is still running.
    until(&rig, after_ready, "stopped").await;
    assert!(rig.supervisor.gateway().is_none());
    assert!(
        lock(&rig.supervisor.shared.admin)
            .as_ref()
            .is_some_and(|endpoint| endpoint.generation == generation)
    );
    assert!(
        !rig.diagnostics
            .snapshot(u64::MAX)
            .events
            .iter()
            .any(|event| matches!(event.service, Some(ServiceFact::AgentRefused { .. })))
    );

    let after_retirement = rig.statuses.lock().unwrap().len();
    rig.release("retired");
    let refused = until(&rig, after_retirement, "refused").await;
    assert_eq!(refused["code"], "agent_service_failed");
    // Refusal is published before process cleanup and retry scheduling.
    // Observe the completed transition before inspecting its facts.
    until_seen(
        &rig,
        "service exit must finish cleanup and schedule its retry",
        || {
            rig.diagnostics
                .snapshot(u64::MAX)
                .events
                .iter()
                .any(|event| {
                    matches!(
                        event.service,
                        Some(ServiceFact::AgentRetryScheduled { delay_ms: 60_000 })
                    )
                })
                .then_some(())
        },
    )
    .await;
    assert!(lock(&rig.supervisor.shared.admin).is_none());

    let facts: Vec<_> = rig
        .diagnostics
        .snapshot(u64::MAX)
        .events
        .into_iter()
        .filter_map(|event| event.service)
        .collect();
    assert!(facts.iter().any(|fact| matches!(
        fact,
        ServiceFact::AgentRefused {
            reason: Refusal::ServiceFailed
        }
    )));
    assert!(
        facts
            .iter()
            .any(|fact| matches!(fact, ServiceFact::AgentRetryScheduled { delay_ms: 60_000 }))
    );
    rig.supervisor.close().await.unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn a_retired_agent_is_stopped_until_its_replacement_reports_ready() {
    let rig = rig(false, false);
    rig.supervisor.status();
    serving(&rig, 0).await;
    let generation = rig.supervisor.gateway().unwrap().generation;
    let retired = rig.supervisor.gateway().unwrap();

    // The service retires the superseded tree first: nothing serves.
    assert!(
        !handle(
            &rig.supervisor.shared,
            generation,
            Signal::Event(Event::Stopped {
                reason: "agent_retired".into(),
            }),
        )
        .await
    );
    assert_eq!(rig.supervisor.status().state, State::Stopped);
    assert!(rig.supervisor.gateway().is_none());

    // A start declined as busy changes nothing it serves.
    assert!(
        !handle(
            &rig.supervisor.shared,
            generation,
            Signal::Event(Event::Refused {
                code: "busy".into(),
            }),
        )
        .await
    );
    assert_eq!(rig.supervisor.status().state, State::Stopped);

    // The replacement's ready line serves it, through a new gateway.
    assert!(
        !handle(
            &rig.supervisor.shared,
            generation,
            Signal::Event(Event::Ready {
                gateway_port: 4001,
                agent_version: "replacement".into(),
                workspace_root: r"C:\lane\workspace".into(),
            }),
        )
        .await
    );
    assert_eq!(
        rig.supervisor.status().state,
        State::Ready {
            agent_version: "replacement".into()
        }
    );
    let replacement = rig.supervisor.gateway().unwrap();
    assert_eq!(replacement.port, 4001);
    assert!(!replacement.same_instance(&retired));
    rig.supervisor.close().await.unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn a_busy_start_leaves_the_serving_agent_ready() {
    let rig = rig(false, false);
    rig.supervisor.status();
    serving(&rig, 0).await;
    let generation = rig.supervisor.gateway().unwrap().generation;
    let before = rig.supervisor.status().state;
    assert!(
        !handle(
            &rig.supervisor.shared,
            generation,
            Signal::Event(Event::Refused {
                code: "busy".into(),
            }),
        )
        .await
    );
    assert_eq!(rig.supervisor.status().state, before);
    assert!(rig.supervisor.gateway().is_some());
    rig.supervisor.close().await.unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn stopped_reasons_other_than_controller_retirement_remain_refusals() {
    let rig = rig(false, false);
    rig.supervisor.status();
    serving(&rig, 0).await;
    let generation = rig.supervisor.gateway().unwrap().generation;

    assert!(
        !handle(
            &rig.supervisor.shared,
            generation,
            Signal::Event(Event::Stopped {
                reason: "agent_signed_out".into(),
            }),
        )
        .await
    );
    assert_eq!(
        rig.supervisor.status().state,
        State::Refused {
            code: Refusal::SignedOut
        }
    );
    assert!(rig.supervisor.gateway().is_none());
    assert!(
        lock(&rig.supervisor.shared.admin)
            .as_ref()
            .is_some_and(|endpoint| endpoint.generation == generation)
    );
    rig.supervisor.close().await.unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn a_launcher_that_ends_unasked_is_a_failed_service_and_is_not_restarted_at_once() {
    let observation = Arc::new(Mutex::new(observed(true, true, Some("A"))));
    let source = observation.clone();
    let observe: Observe = Arc::new(move || {
        let current = lock(&source).clone();
        Box::pin(async move { current })
    });
    let starts = Arc::new(AtomicU64::new(0));
    let counted = starts.clone();
    let launch: Launch = Arc::new(move |_, _| {
        counted.fetch_add(1, Ordering::AcqRel);
        Ok(Prepared {
            person: Box::new(|| Ok(None)),
            local_engine_default:
                cadrumo_application::provisioning::local_ai::LocalEngine::LlamaCpp,
            command: powershell(
                "$null = [Console]::In.ReadLine(); [Console]::Out.WriteLine('{\"event\":\"agent_refused\",\"code\":\"agent_service_incompatible\"}'); exit 3",
            ),
        })
    });
    let supervisor = Supervisor::with_timing(
        observe,
        every(Duration::from_millis(100)),
        Some(launch),
        Arc::new(Diagnostics::default()),
        Duration::from_secs(5),
        Duration::from_secs(60),
    );
    supervisor.status();
    let deadline = Instant::now() + Duration::from_secs(30);
    while supervisor.status().state
        != (State::Refused {
            code: Refusal::ServiceIncompatible,
        })
    {
        assert!(Instant::now() < deadline);
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    tokio::time::sleep(Duration::from_millis(800)).await;
    assert_eq!(starts.load(Ordering::Acquire), 1);
    assert!(lock(&supervisor.shared.running).is_none());
    // A changed sign-in is a new start.
    *observation.lock().unwrap() = observed(false, true, Some("A"));
    tokio::time::sleep(Duration::from_millis(400)).await;
    *observation.lock().unwrap() = observed(true, true, Some("A"));
    let deadline = Instant::now() + Duration::from_secs(10);
    while starts.load(Ordering::Acquire) < 2 {
        assert!(Instant::now() < deadline);
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    supervisor.close().await.unwrap();
}

/// A service process that writes its process id to `witness` once it has
/// read its startup, announces itself ready when `ready` is given, and waits
/// to be stopped.
fn witnessed_service(
    witness: &std::path::Path,
    ready: Option<&serde_json::Value>,
) -> std::process::Command {
    let announce = ready.map_or(String::new(), |ready| {
        format!("[Console]::Out.WriteLine('{ready}'); [Console]::Out.Flush(); ")
    });
    powershell(&format!(
        "$null = [Console]::In.ReadLine(); [IO.File]::WriteAllText('{}', \"$PID\"); {announce}Start-Sleep -Seconds 120",
        witness.display()
    ))
}

fn witness_path(case: &str) -> std::path::PathBuf {
    let path = std::env::temp_dir().join(format!(
        "cadrumo-person-alongside-{case}-{}.pid",
        std::process::id()
    ));
    let _ = std::fs::remove_file(&path);
    path
}

/// The process id the service wrote, once it has started.
fn started_service(witness: &std::path::Path, within: Duration) -> Option<u32> {
    let deadline = Instant::now() + within;
    loop {
        if let Ok(text) = std::fs::read_to_string(witness)
            && let Ok(pid) = text.trim().parse()
        {
            return Some(pid);
        }
        if Instant::now() >= deadline {
            return None;
        }
        std::thread::sleep(Duration::from_millis(20));
    }
}

async fn ended(pid: u32, within: Duration) -> bool {
    let deadline = Instant::now() + within;
    while alive(pid) {
        if Instant::now() >= deadline {
            return false;
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    true
}

/// The first start launches `first` with `person`; any later one launches nothing.
fn first_start(
    first: std::process::Command,
    person: super::super::protocol::AcquirePerson,
) -> Launch {
    let pending = Arc::new(Mutex::new(Some((first, person))));
    Arc::new(move |_, _| {
        let (command, person) = lock(&pending).take().unwrap_or_else(|| {
            let none: super::super::protocol::AcquirePerson = Box::new(|| Ok(None));
            (
                std::process::Command::new("cadrumo-no-later-start-in-this-test"),
                none,
            )
        });
        Ok(Prepared {
            command,
            person,
            local_engine_default:
                cadrumo_application::provisioning::local_ai::LocalEngine::LlamaCpp,
        })
    })
}

fn signed_in(profile: Arc<Mutex<&'static str>>) -> Observe {
    Arc::new(move || {
        let profile = *lock(&profile);
        Box::pin(async move { observed(true, true, Some(profile)) })
    })
}

fn supervising(observe: Observe, launch: Launch) -> Supervisor {
    Supervisor::with_timing(
        observe,
        every(Duration::from_millis(5)),
        Some(launch),
        Arc::new(Diagnostics::default()),
        // The stop grace: these services ignore their input, so they are
        // terminated once it runs out.
        Duration::from_secs(1),
        Duration::from_secs(60),
    )
}

#[tokio::test(flavor = "multi_thread")]
async fn the_service_starts_while_the_person_resumes_and_stops_when_that_fails() {
    let witness = witness_path("failed");
    let seen = witness.clone();
    let started_alongside = Arc::new(std::sync::atomic::AtomicBool::new(false));
    let noted = started_alongside.clone();
    let supervisor = supervising(
        signed_in(Arc::new(Mutex::new("A"))),
        first_start(
            witnessed_service(&witness, None),
            Box::new(move || {
                // The service process runs on the profile id alone while the
                // person session is still being acquired.
                noted.store(
                    started_service(&seen, Duration::from_secs(20)).is_some(),
                    Ordering::SeqCst,
                );
                Err(
                    ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                        .with_reason("person_not_signed_in"),
                )
            }),
        ),
    );
    supervisor.status();
    let pid = tokio::task::block_in_place(|| started_service(&witness, Duration::from_secs(30)))
        .expect("the service process started");
    assert!(
        ended(pid, Duration::from_secs(20)).await,
        "the service outlived its failed person"
    );
    assert!(
        started_alongside.load(Ordering::SeqCst),
        "the service did not start while the person resumed"
    );
    assert!(lock(&supervisor.shared.admin).is_none());
    supervisor.close().await.unwrap();
    let _ = std::fs::remove_file(&witness);
}

#[tokio::test(flavor = "multi_thread")]
async fn a_start_cancelled_while_the_person_resumes_stops_its_service() {
    let witness = witness_path("cancelled");
    let (release, gate) = std::sync::mpsc::channel::<()>();
    let profile = Arc::new(Mutex::new("A"));
    let supervisor = supervising(
        signed_in(profile.clone()),
        first_start(
            witnessed_service(&witness, None),
            Box::new(move || {
                let _ = gate.recv();
                Ok(None)
            }),
        ),
    );
    supervisor.status();
    let pid = tokio::task::block_in_place(|| started_service(&witness, Duration::from_secs(30)))
        .expect("the service process started");
    *lock(&profile) = "B";
    tokio::time::timeout(Duration::from_secs(10), async {
        while !lock(&supervisor.shared.preparing)
            .as_ref()
            .is_some_and(|pending| pending.cancelled.load(Ordering::Acquire))
        {
            tokio::time::sleep(Duration::from_millis(5)).await;
        }
    })
    .await
    .expect("the profile change cancelled the start");
    drop(release);
    assert!(
        ended(pid, Duration::from_secs(20)).await,
        "a cancelled start kept its service"
    );
    assert!(lock(&supervisor.shared.admin).is_none());
    supervisor.close().await.unwrap();
    let _ = std::fs::remove_file(&witness);
}

#[tokio::test(flavor = "multi_thread")]
async fn a_ready_service_is_not_admitted_before_its_person_is_held() {
    let witness = witness_path("ready");
    let ready = serde_json::json!({
        "event": "service_ready",
        "protocol": 1,
        "admin_port": 4001,
        "runtime_boot_id": "33333333-3333-4333-8333-333333333333",
        "connection_id": "44444444-4444-4444-8444-444444444444",
        "profile_id": "11111111-1111-4111-8111-111111111111",
        "service_id": "cadrumo-agent-service",
    });
    let (release, gate) = std::sync::mpsc::channel::<()>();
    let supervisor = supervising(
        signed_in(Arc::new(Mutex::new("A"))),
        first_start(
            witnessed_service(&witness, Some(&ready)),
            Box::new(move || {
                let _ = gate.recv();
                // Answered without a person: nothing may be admitted.
                Ok(None)
            }),
        ),
    );
    supervisor.status();
    let pid = tokio::task::block_in_place(|| started_service(&witness, Duration::from_secs(30)))
        .expect("the service process started");
    // The service has announced itself ready while its person still resumes.
    tokio::time::sleep(Duration::from_millis(1500)).await;
    assert!(lock(&supervisor.shared.admitting).is_none());
    assert!(lock(&supervisor.shared.admin).is_none());
    assert!(lock(&supervisor.shared.running).is_none());
    drop(release);
    assert!(
        ended(pid, Duration::from_secs(20)).await,
        "a service without a person kept running"
    );
    assert!(lock(&supervisor.shared.admin).is_none());
    supervisor.close().await.unwrap();
    let _ = std::fs::remove_file(&witness);
}
