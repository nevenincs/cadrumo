use super::super::connection::SessionExchange;
use super::super::events::{Event, Pushed};
use super::super::refusal::{CUSTODY_RECOVERING, Refusal};
use super::super::session::{Admitted, Standing, access_refusal, admitted};
use super::super::session::{Frontend, present_login};
use super::super::timeout::TimeoutWait;
use serde_json::{Map, Value, json};
use std::sync::{Mutex, mpsc};
use std::time::Instant;

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
