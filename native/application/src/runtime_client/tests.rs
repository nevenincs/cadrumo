use super::connection::{Connection, ExchangeQueue, SessionExchange, Shared, ready_for};
use super::endpoint::Endpoint;
use super::events::{Event, Pushed, event};
use super::framing::{
    DOCUMENT_FRAME, MAXIMUM_FRAME_BYTES, SECRET_FRAME, SUBMISSION_PAYLOAD_CHUNK_BYTES,
    base64_decode, document, frame, frame_header, is_uuid, request_id,
};
use super::handshake::{Cohort, hello_document, server_hello};
use super::refusal::{CUSTODY_RECOVERING, Refusal};
use super::session::{Admitted, Frontend, Standing, access_refusal, admitted, present_login};
use super::stored_proof::{
    KEYSTORE_DIRECTORY, ProofRefusal, RECEIPT_FILENAME, decode_stored_key, receipt_account,
    receipt_locator, receipt_refusal, stored_sign_in_proof,
};
use super::timeout::TimeoutWait;
#[cfg(windows)]
use cadrumo_platform::runtime_pipe;
#[cfg(unix)]
use cadrumo_platform::runtime_socket;
use serde_json::{Map, Value, json};
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Condvar, Mutex, mpsc};
use std::thread;
use std::time::{Duration, Instant};

#[test]
fn an_expired_exchange_does_not_accept_a_buffered_reply() {
    let (sender, receiver) = mpsc::channel();
    sender.send(Map::new()).unwrap();
    assert!(matches!(
        Connection::next_reply(&receiver, Instant::now()),
        Err(Refusal::Timeout)
    ));
    assert!(
        Connection::next_reply(&receiver, Instant::now() + Duration::from_secs(1))
            .unwrap()
            .is_empty()
    );
}

#[test]
fn a_reply_wait_ends_at_its_deadline_without_waiting_for_sender_exit() {
    let (_sender, receiver) = mpsc::channel();
    assert!(matches!(
        Connection::next_reply(&receiver, Instant::now() + Duration::from_millis(20)),
        Err(Refusal::Timeout)
    ));
}

#[test]
fn a_queued_exchange_times_out_without_disturbing_the_owner() {
    let (sender, receiver) = mpsc::channel();
    let queue = Arc::new(ExchangeQueue {
        replies: Mutex::new(Some(receiver)),
        available: Condvar::new(),
        closed: AtomicBool::new(false),
    });
    let owner = queue
        .claim(Instant::now() + Duration::from_secs(2))
        .unwrap();
    let (done, finished) = mpsc::channel();
    let contender = {
        let queue = queue.clone();
        thread::spawn(move || {
            let timed_out = matches!(
                queue.claim(Instant::now() + Duration::from_millis(50)),
                Err(Refusal::Timeout)
            );
            done.send(timed_out).unwrap();
        })
    };
    let timed_out = finished.recv_timeout(Duration::from_secs(2));
    sender.send(Map::new()).unwrap();
    assert!(
        owner
            .recv_timeout(Duration::from_secs(1))
            .unwrap()
            .is_empty()
    );
    drop(owner);
    contender.join().unwrap();
    assert!(timed_out.unwrap());
    assert!(queue.claim(Instant::now() + Duration::from_secs(1)).is_ok());
}

#[test]
fn close_serializes_with_the_claim_check_before_condvar_wait() {
    let (_sender, receiver) = mpsc::channel();
    let queue = Arc::new(ExchangeQueue {
        replies: Mutex::new(Some(receiver)),
        available: Condvar::new(),
        closed: AtomicBool::new(false),
    });
    let owner = queue.claim(TimeoutWait::new().deadline()).unwrap();
    let (at_gap, gap) = mpsc::channel();
    let (resume, resumed) = mpsc::channel();
    let (answer, answered) = mpsc::channel();
    let waiter = {
        let queue = queue.clone();
        thread::spawn(move || {
            let result = queue.claim_observed(TimeoutWait::new().deadline(), || {
                at_gap.send(()).unwrap();
                resumed.recv().unwrap();
            });
            answer
                .send(matches!(result, Err(Refusal::ConnectionClosed)))
                .unwrap();
        })
    };
    gap.recv_timeout(Duration::from_secs(5)).unwrap();
    let (started, starting) = mpsc::channel();
    let (closed, closing) = mpsc::channel();
    let closer = {
        let queue = queue.clone();
        thread::spawn(move || {
            started.send(()).unwrap();
            queue.close();
            closed.send(()).unwrap();
        })
    };
    starting.recv_timeout(Duration::from_secs(5)).unwrap();
    assert!(
        closing.recv_timeout(Duration::from_millis(50)).is_err(),
        "close must serialize with the held reply mutex"
    );
    resume.send(()).unwrap();
    assert!(answered.recv_timeout(Duration::from_secs(5)).unwrap());
    closing.recv_timeout(Duration::from_secs(5)).unwrap();
    waiter.join().unwrap();
    closer.join().unwrap();
    drop(owner);
}

#[test]
fn closing_wakes_a_queued_slot_without_waiting_for_the_startup_timeout() {
    let (_sender, receiver) = mpsc::channel();
    let queue = Arc::new(ExchangeQueue {
        replies: Mutex::new(Some(receiver)),
        available: Condvar::new(),
        closed: AtomicBool::new(false),
    });
    let owner = queue.claim(TimeoutWait::new().deadline()).unwrap();
    let (started, waiting) = mpsc::channel();
    let contender = {
        let queue = queue.clone();
        thread::spawn(move || {
            started.send(()).unwrap();
            matches!(
                queue.claim(TimeoutWait::new().deadline()),
                Err(Refusal::ConnectionClosed)
            )
        })
    };
    waiting.recv().unwrap();
    queue.close();
    assert!(contender.join().unwrap());
    drop(owner);
}

#[test]
fn subscription_racing_disconnect_always_receives_the_terminal_event() {
    for _ in 0..100 {
        let shared = Arc::new(Shared {
            connection_id: Mutex::new(None),
            subscribers: Mutex::new(Vec::new()),
            scoped: Mutex::new(Vec::new()),
            closed: AtomicBool::new(false),
            timeout: AtomicBool::new(false),
        });
        let barrier = Arc::new(std::sync::Barrier::new(2));
        let subscriber = {
            let shared = shared.clone();
            let barrier = barrier.clone();
            thread::spawn(move || {
                barrier.wait();
                (shared.subscribe(), shared.subscribe_scoped())
            })
        };
        barrier.wait();
        shared.closed.store(true, Ordering::Release);
        shared.dispatch(&Pushed {
            event: Event::Disconnected,
            profile_id: None,
            session_id: None,
        });
        let (plain, scoped) = subscriber.join().unwrap();
        assert_eq!(
            plain.recv_timeout(Duration::from_secs(1)).unwrap(),
            Event::Disconnected
        );
        assert_eq!(
            scoped.recv_timeout(Duration::from_secs(1)).unwrap().event,
            Event::Disconnected
        );
        assert!(plain.try_recv().is_err());
        assert!(scoped.try_recv().is_err());
    }
}

#[test]
fn an_expired_claimant_passes_on_a_release_wake() {
    let (_sender, receiver) = mpsc::channel();
    let queue = Arc::new(ExchangeQueue {
        replies: Mutex::new(None),
        available: Condvar::new(),
        closed: AtomicBool::new(false),
    });
    let (waiting, started) = mpsc::channel();
    let (done, finished) = mpsc::channel();
    let waiter = {
        let queue = queue.clone();
        thread::spawn(move || {
            let held = queue.replies.lock().unwrap();
            waiting.send(()).unwrap();
            let (held, timeout) = queue
                .available
                .wait_timeout(held, Duration::from_secs(3))
                .unwrap();
            done.send(!timeout.timed_out() && held.is_some()).unwrap();
        })
    };
    started.recv_timeout(Duration::from_secs(1)).unwrap();
    // The receiver became available, but the release wake went to an
    // expired claimant rather than the waiter above.
    *queue.replies.lock().unwrap() = Some(receiver);
    assert!(matches!(
        queue.claim(Instant::now() - Duration::from_secs(1)),
        Err(Refusal::Timeout)
    ));
    let woke = finished.recv_timeout(Duration::from_secs(1));
    waiter.join().unwrap();
    assert!(woke.unwrap());
}

#[test]
fn a_streamed_payload_follows_only_readiness_for_the_declared_upload() {
    let descriptor = json!({"kind": "financial_operand_input", "byte_count": 70_000});
    let request = json!({"action": "operation_submit_payload", "descriptor": descriptor});
    let ready = |kind: &str, descriptor: Value| {
        json!({"kind": kind, "descriptor": descriptor})
            .as_object()
            .unwrap()
            .clone()
    };
    assert!(ready_for(
        &request,
        &ready("operation_payload_ready", descriptor.clone())
    ));
    assert!(!ready_for(
        &request,
        &ready(
            "operation_payload_ready",
            json!({"kind": "financial_operand_input", "byte_count": 69_999})
        )
    ));
    assert!(!ready_for(
        &request,
        &ready("operation_submitted", descriptor.clone())
    ));
    assert!(!ready_for(
        &json!({"action": "operation_submit_payload"}),
        &ready("operation_payload_ready", Value::Null)
    ));
    // Every chunk but the last fills one secret frame within its bound.
    assert!(frame(SECRET_FRAME, &[0; SUBMISSION_PAYLOAD_CHUNK_BYTES]).is_ok());
}

#[test]
fn frames_carry_a_kind_a_big_endian_length_and_bounded_payloads() {
    let framed = frame(DOCUMENT_FRAME, b"{}").unwrap();
    assert_eq!(framed, [b'J', 0, 0, 0, 2, b'{', b'}']);
    assert!(frame(DOCUMENT_FRAME, b"").is_err());
    assert!(frame(DOCUMENT_FRAME, &vec![b'x'; MAXIMUM_FRAME_BYTES]).is_ok());
    assert!(frame(DOCUMENT_FRAME, &vec![b'x'; MAXIMUM_FRAME_BYTES + 1]).is_err());
    assert_eq!(frame_header(&[b'E', 0, 0, 1, 0]).unwrap(), (b'E', 256));
    for header in [
        [b'S', 0, 0, 0, 1],
        [b'J', 0, 0, 0, 0],
        [b'J', 0, 1, 0, 1],
        [b'X', 0, 0, 0, 1],
    ] {
        assert!(frame_header(&header).is_err(), "{header:?}");
    }
}

#[test]
fn a_refused_receipt_reads_as_its_receipt_reason_and_other_refusals_do_not() {
    let named = Refusal::Denied {
        code: "authentication_required".into(),
        sign_in: Some(json!({"reason": "expired_absolute"})),
        holder_operation_id: None,
        recovery_remaining_seconds: None,
    };
    assert_eq!(receipt_refusal(&named), Some("expired_absolute"));
    for (code, reason) in [
        ("authentication_required", "absent"),
        ("session_expired", "expired_idle"),
        ("custody_changed", "custody_changed"),
        ("credential_rejected", "tampered"),
    ] {
        assert_eq!(
            receipt_refusal(&Refusal::denied(code)),
            Some(reason),
            "{code}"
        );
    }
    let throttled = Refusal::Denied {
        code: "credential_rejected".into(),
        sign_in: Some(json!({"reason": "throttled", "remaining_seconds": 30})),
        holder_operation_id: None,
        recovery_remaining_seconds: None,
    };
    assert_eq!(receipt_refusal(&throttled), Some("tampered"));
    assert_eq!(receipt_refusal(&Refusal::denied("profile_locked")), None);
    assert_eq!(receipt_refusal(&Refusal::ConnectionClosed), None);
}

#[test]
fn a_busy_subject_names_its_holder() {
    let busy = Refusal::Denied {
        code: "subject_busy".into(),
        sign_in: None,
        holder_operation_id: Some("0f0f0f0f-0000-4000-8000-000000000000".into()),
        recovery_remaining_seconds: None,
    };
    assert_eq!(
        busy.holder_operation_id(),
        Some("0f0f0f0f-0000-4000-8000-000000000000")
    );
    assert_eq!(Refusal::denied("subject_busy").holder_operation_id(), None);
    assert_eq!(Refusal::InvalidFrame.holder_operation_id(), None);
}

#[test]
fn a_refusal_of_a_suspended_session_carries_its_recovery_window() {
    let document = |code: &str, window: Value| {
        json!({
            "kind": "access_refusal", "code": code, "sign_in": null,
            "recovery_remaining_seconds": window,
        })
        .as_object()
        .unwrap()
        .clone()
    };
    let waiting = access_refusal(&document("custody_recovering", json!(87)));
    assert!(waiting.is_custody_recovering());
    assert_eq!(waiting.recovery_remaining_seconds(), Some(87));
    assert_eq!(waiting.code(), CUSTODY_RECOVERING);
    // The window is the runtime's to name: none given is none known, not zero.
    let unnamed = access_refusal(&document("custody_recovering", Value::Null));
    assert!(unnamed.is_custody_recovering());
    assert_eq!(unnamed.recovery_remaining_seconds(), None);
    let ended = access_refusal(&document("custody_unavailable", Value::Null));
    assert!(!ended.is_custody_recovering());
    assert_eq!(ended.code(), "custody_unavailable");
    assert_eq!(Refusal::ConnectionClosed.recovery_remaining_seconds(), None);
    assert!(!Refusal::ConnectionClosed.is_custody_recovering());
    assert!(!waiting.is_unsettled() && !ended.is_unsettled());
}

#[test]
fn a_change_the_lost_worker_was_serving_is_unsettled_while_the_session_recovers() {
    let operation = "3".repeat(64);
    let refused = access_refusal(
        json!({
            "kind": "access_refusal", "code": "custody_recovering", "sign_in": null,
            "recovery_remaining_seconds": 87, "effect": "unknown", "operation_id": operation,
        })
        .as_object()
        .unwrap(),
    );
    assert!(refused.is_unsettled());
    assert!(refused.is_custody_recovering());
    assert_eq!(refused.code(), CUSTODY_RECOVERING);
    assert_eq!(refused.recovery_remaining_seconds(), Some(87));
    assert_eq!(refused.unsettled_operation_id(), Some(operation.as_str()));
    assert_eq!(refused.holder_operation_id(), None);
    // A submission names no operation yet; its effect is unknown all the same.
    let submitted = access_refusal(
        json!({"kind": "access_refusal", "code": "custody_recovering", "effect": "unknown"})
            .as_object()
            .unwrap(),
    );
    assert!(submitted.is_unsettled());
    assert_eq!(submitted.unsettled_operation_id(), None);
    assert_eq!(submitted.recovery_remaining_seconds(), None);
    assert!(!Refusal::denied(CUSTODY_RECOVERING).is_unsettled());
    assert_eq!(
        Refusal::denied(CUSTODY_RECOVERING).unsettled_operation_id(),
        None
    );
}

fn held() -> Admitted {
    Admitted {
        profile_id: "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d".into(),
        session_id: "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d".into(),
        connection_id: "2a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d".into(),
        runtime_boot_id: "3a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d".into(),
        expires_at: None,
        session_persisted: None,
        signed_out_profile_ids: Vec::new(),
    }
}

struct PendingLogin {
    sender: Mutex<Option<mpsc::Sender<Pushed>>>,
    requests: Mutex<Vec<String>>,
    login_id: Mutex<String>,
    deadline: Instant,
}

impl PendingLogin {
    fn pending(&self, request: &Value) -> Map<String, Value> {
        json!({
            "kind": "profile_login_pending", "request_id": request["request_id"],
            "profile_id": held().profile_id, "login_request_id": *self.login_id.lock().unwrap(),
        })
        .as_object()
        .unwrap()
        .clone()
    }
}

impl SessionExchange for PendingLogin {
    fn exchange(&self, request: &Value, deadline: Instant) -> Result<Map<String, Value>, Refusal> {
        assert_eq!(deadline, self.deadline);
        assert_eq!(request["action"], "profile_login_status");
        assert_eq!(request["login_request_id"], *self.login_id.lock().unwrap());
        let mut requests = self.requests.lock().unwrap();
        requests.push("status".into());
        if requests.len() == 2 {
            self.sender
                .lock()
                .unwrap()
                .as_ref()
                .unwrap()
                .send(Pushed {
                    event: Event::ProfileLoginChanged {
                        login_request_id: self.login_id.lock().unwrap().clone(),
                    },
                    profile_id: Some(held().profile_id),
                    session_id: None,
                })
                .unwrap();
            Ok(self.pending(request))
        } else {
            Ok(json!({"kind": "profile_status", "status": {
                "connected": true, "credential_authenticated": true, "profile_bound": true,
                "profile_id": held().profile_id, "session_id": held().session_id,
            }, "connection_id": held().connection_id, "runtime_boot_id": held().runtime_boot_id
            })
            .as_object()
            .unwrap()
            .clone())
        }
    }

    fn exchange_with_secret(
        &self,
        request: &Value,
        secret: &[u8],
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        assert_eq!(deadline, self.deadline);
        assert_eq!(secret, b"one-proof");
        self.requests.lock().unwrap().push("proof".into());
        *self.login_id.lock().unwrap() = request["request_id"].as_str().unwrap().into();
        Ok(self.pending(request))
    }

    fn exchange_streamed(
        &self,
        _: &Value,
        _: &[u8],
        _: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        panic!("login has no operation payload")
    }

    fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
        let (sender, receiver) = mpsc::channel();
        *self.sender.lock().unwrap() = Some(sender);
        receiver
    }

    fn close(&self) {}
}

#[test]
fn pending_login_sends_one_proof_and_claims_after_its_cue_under_one_deadline() {
    let deadline = TimeoutWait::new().deadline();
    let exchange = PendingLogin {
        sender: Mutex::new(None),
        requests: Mutex::new(Vec::new()),
        login_id: Mutex::new(String::new()),
        deadline,
    };
    let admitted = present_login(
        &exchange,
        &held().profile_id,
        Frontend::Desktop,
        "password",
        b"one-proof",
        false,
        deadline,
    )
    .unwrap();
    assert_eq!(admitted.session_id, held().session_id);
    assert_eq!(
        *exchange.requests.lock().unwrap(),
        ["proof", "status", "status"]
    );
}

#[test]
fn a_status_reads_as_held_recovering_or_refused_for_the_session_it_names() {
    let status = |value: Value| value.as_object().unwrap().clone();
    let session = held();
    assert_eq!(
        Standing::of(
            &status(json!({"session_id": session.session_id, "denial": null})),
            &session
        ),
        Standing::Held
    );
    // Whole seconds, rounded up by the runtime; the session keeps its identity.
    assert_eq!(
        Standing::of(
            &status(json!({
                "session_id": session.session_id, "denial": "custody_recovering",
                "recovery_remaining_seconds": 119, "credential_authenticated": false,
            })),
            &session
        ),
        Standing::Recovering {
            remaining_seconds: Some(119)
        }
    );
    assert_eq!(
        Standing::of(
            &status(json!({"session_id": session.session_id, "denial": "custody_recovering"})),
            &session
        ),
        Standing::Recovering {
            remaining_seconds: None
        }
    );
    assert_eq!(
        Standing::of(
            &status(json!({"session_id": session.session_id, "denial": "custody_unavailable"})),
            &session
        ),
        Standing::Refused("custody_unavailable".into())
    );
    // A status that names another session, or none, is no standing of this one.
    for other in [
        json!({"session_id": "4a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d", "denial": null}),
        json!({"session_id": null, "denial": null}),
    ] {
        assert_eq!(
            Standing::of(&status(other), &session),
            Standing::Refused("profile_mismatch".into())
        );
    }
}

#[test]
fn an_admitted_status_of_a_suspended_session_is_refused_with_its_window() {
    let reply = json!({
        "kind": "profile_status",
        "status": {
            "connected": true, "credential_authenticated": false, "profile_bound": true,
            "profile_id": "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
            "session_id": "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
            "denial": "custody_recovering", "recovery_remaining_seconds": 42,
        },
    });
    let refused = admitted(
        reply.as_object().unwrap(),
        "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
    )
    .unwrap_err();
    assert!(refused.is_custody_recovering());
    assert_eq!(refused.recovery_remaining_seconds(), Some(42));
}

#[test]
fn base64_accepts_only_the_canonical_spelling() {
    assert_eq!(base64_decode("aGk=").unwrap(), b"hi");
    assert_eq!(base64_decode("aGV5").unwrap(), b"hey");
    assert_eq!(base64_decode("aA==").unwrap(), b"h");
    assert_eq!(
        base64_decode("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
            .unwrap()
            .len(),
        32
    );
    for rejected in ["", "aGk", "aGk=x", "a===", "aGl=", "aB==", "a Gk=", "YQ=="] {
        if rejected == "YQ==" {
            assert_eq!(base64_decode(rejected).unwrap(), b"a");
            continue;
        }
        assert!(base64_decode(rejected).is_none(), "{rejected}");
    }
}

#[test]
fn request_ids_are_distinct_version_four_uuids() {
    let first = request_id();
    let second = request_id();
    assert!(is_uuid(&first), "{first}");
    assert_ne!(first, second);
    assert_eq!(&first[14..15], "4");
    assert!(matches!(&first[19..20], "8" | "9" | "a" | "b"));
    assert!(!is_uuid("0A1B2C3D-4E5F-4A6B-9C7D-8E9F0A1B2C3D"));
}

#[cfg(windows)]
fn endpoint() -> Endpoint {
    Endpoint {
        pipe_name: r"\\.\pipe\cadrumo-runtime-test".into(),
        storage_identity: "f".repeat(64),
        owner_sid: "S-1-5-21-1-2-3-1001".into(),
    }
}

#[cfg(unix)]
fn endpoint() -> Endpoint {
    Endpoint {
        socket_leaf: format!("{}.sock", "f".repeat(32)),
        storage_identity: "f".repeat(64),
        owner_uid: 501,
    }
}

fn cohort(generation: Option<&str>) -> Cohort {
    Cohort {
        product_version: "0.6.0".into(),
        authority_generation: generation.map(str::to_owned),
    }
}

#[test]
fn the_client_hello_names_the_cohort_and_asks_for_lifecycle_notices() {
    let hello = hello_document(&endpoint(), &cohort(Some("a1")), true);
    assert_eq!(
        hello,
        json!({
            "kind": "client_hello", "protocol_version": 4, "product_version": "0.6.0",
            "storage_identity": "f".repeat(64), "authority_generation": "a1", "lifecycle_notices": "v1"
        })
    );
    assert!(hello_document(&endpoint(), &cohort(None), true)["authority_generation"].is_null());
}

#[test]
fn a_hello_that_asks_for_no_lifecycle_notices_omits_the_member() {
    let hello = hello_document(&endpoint(), &cohort(Some("a1")), false);
    assert_eq!(
        hello,
        json!({
            "kind": "client_hello", "protocol_version": 4, "product_version": "0.6.0",
            "storage_identity": "f".repeat(64), "authority_generation": "a1"
        })
    );
}

fn server(version: &str, identity: &str, generation: Option<&str>) -> Map<String, Value> {
    let mut document = json!({
        "kind": "server_hello", "protocol_version": 4, "product_version": version,
        "storage_identity": identity, "boot_id": "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
        "authority_generation": generation,
    });
    document.as_object_mut().unwrap().clone()
}

#[test]
fn the_server_hello_must_match_version_root_and_any_shared_generation() {
    let identity = "f".repeat(64);
    let hello = server_hello(
        &server("0.6.0", &identity, Some("a1")),
        &endpoint(),
        &cohort(Some("a1")),
    )
    .unwrap();
    assert_eq!(hello.boot_id, "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d");
    assert_eq!(hello.authority_generation.as_deref(), Some("a1"));
    // A side that knows no generation does not refuse the other's.
    assert!(
        server_hello(
            &server("0.6.0", &identity, None),
            &endpoint(),
            &cohort(Some("a1"))
        )
        .is_ok()
    );
    assert!(
        server_hello(
            &server("0.6.0", &identity, Some("a1")),
            &endpoint(),
            &cohort(None)
        )
        .is_ok()
    );
    assert!(matches!(
        server_hello(
            &server("0.6.0", &identity, Some("a2")),
            &endpoint(),
            &cohort(Some("a1"))
        ),
        Err(Refusal::VersionMismatch)
    ));
    assert!(matches!(
        server_hello(
            &server("0.6.1", &identity, None),
            &endpoint(),
            &cohort(None)
        ),
        Err(Refusal::VersionMismatch)
    ));
    assert!(matches!(
        server_hello(
            &server("0.6.0", &"e".repeat(64), None),
            &endpoint(),
            &cohort(None)
        ),
        Err(Refusal::RootMismatch)
    ));
    let mut wrong = server("0.6.0", &identity, None);
    wrong.insert("protocol_version".into(), json!(2));
    assert!(matches!(
        server_hello(&wrong, &endpoint(), &cohort(None)),
        Err(Refusal::InvalidFrame)
    ));
}

#[test]
fn events_are_read_by_kind_and_an_unknown_kind_ends_the_connection() {
    let read = |value: Value| event(value.as_object().unwrap());
    assert_eq!(
        read(json!({"kind": "sign_in_changed"})),
        Event::SignInChanged
    );
    assert_eq!(
        read(
            json!({"kind": "session_event", "event": "signed_out", "reason": "authentication_required"})
        ),
        Event::SessionRetired {
            kind: "signed_out".into(),
            reason: "authentication_required".into()
        }
    );
    assert_eq!(read(json!({"kind": "profile_status"})), Event::Disconnected);
}

#[test]
fn an_admitted_status_binds_the_profile_and_a_denial_is_the_runtimes_code() {
    let reply = |status: Value, extra: Value| {
        let mut document = json!({
            "kind": "profile_status", "request_id": "r", "runtime_boot_id": "b", "connection_id": "c",
            "status": status, "signed_out_profile_ids": ["0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3e"],
        });
        if let Some(extra) = extra.as_object() {
            document.as_object_mut().unwrap().extend(extra.clone());
        }
        document.as_object().unwrap().clone()
    };
    let live = json!({
        "connected": true, "credential_authenticated": true, "profile_bound": true,
        "profile_id": "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d", "session_id": "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
        "session_expires_at": "2026-10-22T18:00:00Z", "denial": null,
    });
    let session = admitted(
        &reply(
            live.clone(),
            json!({"human_login": {"session_persisted": true}}),
        ),
        "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d",
    )
    .unwrap();
    assert_eq!(session.session_id, "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d");
    assert_eq!(session.session_persisted, Some(true));
    assert_eq!(
        session.signed_out_profile_ids,
        ["0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3e"]
    );
    assert_eq!(session.expires_at.as_deref(), Some("2026-10-22T18:00:00Z"));
    let other = admitted(
        &reply(live.clone(), Value::Null),
        "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3e",
    )
    .unwrap_err();
    assert_eq!(other.code(), "profile_mismatch");
    let mut denied = live.clone();
    denied["denial"] = json!("profile_locked");
    assert_eq!(
        admitted(
            &reply(denied, Value::Null),
            "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d"
        )
        .unwrap_err()
        .code(),
        "profile_locked"
    );
}

#[test]
fn a_receipt_locator_names_its_profile_and_session_or_is_refused() {
    let profile = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    let session = "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    let payload = format!(
        r#"{{"profile_id":"{profile}","schema_version":3,"session_id":"{session}","wrapped":"x"}}"#
    );
    let locator = receipt_locator(payload.as_bytes(), profile).unwrap();
    assert_eq!(locator.session_id, session);
    assert_eq!(receipt_account(&locator), format!("{profile}:{session}"));
    assert_eq!(
        receipt_locator(payload.as_bytes(), "2a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d").unwrap_err(),
        ProofRefusal::Tampered
    );
    for malformed in [
        "",
        "[]",
        r#"{"profile_id":"x","session_id":"y","schema_version":1}"#,
    ] {
        assert_eq!(
            receipt_locator(malformed.as_bytes(), profile).unwrap_err(),
            ProofRefusal::Malformed
        );
    }
}

#[test]
fn a_stored_key_is_base64_text_in_utf16_or_utf8() {
    let encoded = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=";
    let utf16: Vec<u8> = encoded.encode_utf16().flat_map(u16::to_le_bytes).collect();
    assert_eq!(
        decode_stored_key(&utf16).unwrap().as_slice(),
        (0u8..32).collect::<Vec<_>>()
    );
    assert_eq!(decode_stored_key(encoded.as_bytes()).unwrap().len(), 32);
    assert_eq!(
        decode_stored_key(b"aGk=").unwrap_err(),
        ProofRefusal::Malformed
    );
    assert_eq!(
        decode_stored_key(&[0xff, 0xfe, 0xfd]).unwrap_err(),
        ProofRefusal::Malformed
    );
}

#[test]
fn a_profile_without_a_receipt_has_no_proof() {
    let root = std::env::temp_dir().join(format!("cadrumo-runtime-client-{}", std::process::id()));
    let profile = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    std::fs::create_dir_all(root.join(KEYSTORE_DIRECTORY).join(profile)).unwrap();
    assert_eq!(
        stored_sign_in_proof(&root, profile).unwrap_err(),
        ProofRefusal::Absent
    );
    assert_eq!(
        stored_sign_in_proof(&root, "not-a-profile").unwrap_err(),
        ProofRefusal::Malformed
    );
    let receipt = root
        .join(KEYSTORE_DIRECTORY)
        .join(profile)
        .join(RECEIPT_FILENAME);
    std::fs::write(&receipt, b"{}").unwrap();
    assert_eq!(
        stored_sign_in_proof(&root, profile).unwrap_err(),
        ProofRefusal::Malformed
    );
    std::fs::write(
        &receipt,
        format!(r#"{{"profile_id":"{profile}","schema_version":3,"session_id":"1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d"}}"#),
    )
    .unwrap();
    // The locator is read; the entry it names was never stored.
    assert_eq!(
        stored_sign_in_proof(&root, profile).unwrap_err(),
        ProofRefusal::KeychainEntryMissing
    );
    let _ = std::fs::remove_dir_all(&root);
}

#[test]
#[cfg(windows)]
fn an_absent_endpoint_is_not_ready_and_an_unknown_root_names_none() {
    let endpoint = Endpoint {
        pipe_name: format!(r"\\.\pipe\cadrumo-runtime-absent-{}", std::process::id()),
        storage_identity: "f".repeat(64),
        owner_sid: runtime_pipe::current_user_sid().unwrap(),
    };
    let refused = match Connection::open(
        &endpoint,
        &cohort(None),
        Instant::now() + Duration::from_secs(2),
    ) {
        Ok(_) => panic!("an absent pipe must not connect"),
        Err(refused) => refused,
    };
    assert!(matches!(refused, Refusal::EndpointNotReady), "{refused}");
    assert!(matches!(
        Endpoint::of(Path::new(r"C:\cadrumo-no-such-root")),
        Err(Refusal::EndpointUntrusted)
    ));
    let here = Endpoint::of(&std::env::temp_dir()).unwrap();
    assert_eq!(
        here.pipe_name,
        format!(r"\\.\pipe\cadrumo-runtime-{}", here.storage_identity)
    );
    assert_eq!(here.storage_identity.len(), 64);
}

#[test]
#[cfg(target_os = "macos")]
fn an_absent_endpoint_is_not_ready_and_an_unknown_or_foreign_root_names_none() {
    let endpoint = Endpoint {
        socket_leaf: format!("{:032x}.sock", u128::from(std::process::id())),
        storage_identity: "f".repeat(64),
        owner_uid: cadrumo_platform::runtime_socket::current_uid(),
    };
    let refused = match Connection::open(
        &endpoint,
        &cohort(None),
        Instant::now() + Duration::from_secs(2),
    ) {
        Ok(_) => panic!("an absent socket must not connect"),
        Err(refused) => refused,
    };
    assert!(matches!(refused, Refusal::EndpointNotReady), "{refused}");
    assert!(matches!(
        Endpoint::of(Path::new("/cadrumo-no-such-root")),
        Err(Refusal::EndpointUntrusted)
    ));
    // The root directory belongs to the system account, never to this one.
    assert!(matches!(
        Endpoint::of(Path::new("/")),
        Err(Refusal::EndpointUntrusted)
    ));
    let here = Endpoint::of(&std::env::temp_dir()).unwrap();
    assert_eq!(here.storage_identity.len(), 64);
    assert_eq!(
        here.socket_leaf,
        format!("{}.sock", &here.storage_identity[..32])
    );
    assert_eq!(
        here.owner_uid,
        cadrumo_platform::runtime_socket::current_uid()
    );
}
