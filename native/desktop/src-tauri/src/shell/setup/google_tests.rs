//! The account tracker against a held session that relays like the hold does
//! and answers with documents shaped like the product's.
use super::*;
use cadrumo_application::error::application::Cause;

const PROFILE: &str = "12345678-1234-4234-8234-123456789abc";
const SESSION: &str = "22345678-1234-4234-8234-123456789abc";

fn identity() -> Value {
    json!({"profile_id": PROFILE, "session_id": SESSION, "runtime_boot_id": "b", "connection_id": "c"})
}

#[derive(Clone, Debug)]
struct FakeOperation {
    id: String,
    definition: String,
    subject: String,
    revision: u64,
    lifecycle: &'static str,
    condition: Option<&'static str>,
    review: Option<Value>,
    result: Option<Value>,
}

impl FakeOperation {
    fn settle(&mut self, condition: &'static str, result: Option<Value>) {
        self.lifecycle = "terminal";
        self.condition = Some(condition);
        self.result = result;
        self.review = None;
        self.revision += 1;
    }

    fn projection(&self) -> Value {
        let pending = match &self.review {
            Some(_) => json!({"disposition": "review_available", "interaction_id": "1".repeat(64),
                              "revision": self.revision}),
            None => json!({"disposition": "none"}),
        };
        json!({
            "operation_id": self.id, "definition_id": self.definition, "subject_ref": self.subject,
            "revision": self.revision, "lifecycle": self.lifecycle, "terminal_condition": self.condition,
            "phase_code": null, "progress": null, "cancellable_now": false,
            "cancellation_requested": false, "pending_interaction": pending,
        })
    }
}

type OnSubmit = Box<dyn FnMut(&mut FakeOperation)>;

/// The hold's relay, answering from fake operations as the runtime would publish them.
struct FakeHold {
    operations: Vec<FakeOperation>,
    calls: Vec<Value>,
    on_submit: OnSubmit,
    /// How the next read of the stored Google sign-in settles: its condition and outcome.
    account: (&'static str, Value),
}

/// A stored sign-in read: signed in as `email`, or not signed in.
fn account(email: Option<&str>) -> (&'static str, Value) {
    let result = json!({"profile_id": PROFILE, "session_present": email.is_some(),
                        "account_email": email, "granted_scopes": ["openid", "email", "https://www.googleapis.com/auth/drive.file"], "issued_at": null});
    (
        "succeeded",
        json!({"profile_id": PROFILE, "outcome": "succeeded", "result": result, "refusal": null}),
    )
}

/// A stored sign-in read the product refused, with the failure its refusal falls into.
fn account_refused(category: &str) -> (&'static str, Value) {
    ("refused", google_outcome(Some(category)))
}

fn google_outcome(failure: Option<&str>) -> Value {
    match failure {
        None => {
            json!({"profile_id": PROFILE, "outcome": "succeeded", "result": {}, "refusal": null})
        }
        Some(category) => json!({
            "profile_id": PROFILE, "outcome": "refused", "result": null,
            "refusal": {"provider_code": "REFUSED_GOOGLE_SIGN_IN_REQUIRED", "failure_category": category},
        }),
    }
}

/// The product's Google consent review: the person's own sign-in, by its digest.
fn google_consent() -> Value {
    json!({"profile_id": PROFILE, "plan_digest": "d".repeat(64)})
}

fn settle_status(operation: &mut FakeOperation) {
    if operation.definition == GOOGLE_SIGN_IN {
        operation.review = Some(google_consent());
        operation.lifecycle = "waiting_for_interaction";
        operation.revision = 2;
    } else if operation.definition == GOOGLE_SIGN_OUT {
        operation.settle("succeeded", Some(google_outcome(None)));
    } else if operation.definition == GOOGLE_FOLDER {
        operation.settle("succeeded", Some(json!({
            "outcome": "succeeded", "result": {"configured": true, "root_folder_id": "profile-folder_123"}
        })));
    }
}

impl FakeHold {
    fn new(on_submit: fn(&mut FakeOperation)) -> Self {
        Self {
            operations: Vec::new(),
            calls: Vec::new(),
            on_submit: Box::new(on_submit),
            account: account(None),
        }
    }

    fn operation(&mut self, id: &str) -> &mut FakeOperation {
        self.operations
            .iter_mut()
            .find(|operation| operation.id == id)
            .expect("a known operation")
    }

    fn actions(&self, action: &str) -> Vec<&Value> {
        self.calls
            .iter()
            .filter(|call| call["action"] == action)
            .collect()
    }

    fn submitted(&self, definition: &str) -> usize {
        self.operations
            .iter()
            .filter(|operation| operation.definition == definition)
            .count()
    }

    fn reply(&self, kind: &str, fields: Value) -> Value {
        let mut reply = json!({"kind": kind, "profile_id": PROFILE, "session_id": SESSION});
        for (key, value) in fields.as_object().expect("fields") {
            reply[key] = value.clone();
        }
        reply
    }

    fn refused(&self, code: &str) -> Value {
        self.reply("operation_refused", json!({"code": code}))
    }
}

impl Relay for FakeHold {
    fn call(&mut self, request: Value) -> std::result::Result<Value, ApplicationError> {
        self.calls.push(request.clone());
        let id = request["operation_id"]
            .as_str()
            .unwrap_or_default()
            .to_owned();
        Ok(match request["action"].as_str().expect("an action") {
            "operation_submit" => {
                assert_eq!(request["subject_ref"], format!("profile:{PROFILE}"));
                assert_eq!(request["payload"], json!({"profile_id": PROFILE}));
                let mut operation = FakeOperation {
                    id: format!("{:064x}", self.operations.len() + 1),
                    definition: request["definition_id"].as_str().unwrap().to_owned(),
                    subject: request["subject_ref"].as_str().unwrap().to_owned(),
                    revision: 1,
                    lifecycle: "running",
                    condition: None,
                    review: None,
                    result: None,
                };
                (self.on_submit)(&mut operation);
                if operation.definition == GOOGLE_STATUS {
                    let (condition, outcome) = self.account.clone();
                    operation.settle(condition, Some(outcome));
                }
                let id = operation.id.clone();
                self.operations.push(operation);
                self.reply("operation_submitted", json!({"operation_id": id}))
            }
            "operation_observe" => {
                let Some(operation) = self.operations.iter().find(|operation| operation.id == id)
                else {
                    return Ok(self.refused("operation_denied"));
                };
                let observation = json!({
                    "projection": operation.projection(),
                    "event_page": {"status": "caught_up", "events": [], "next_cursor": 0, "anchor_cursor": 0},
                });
                self.reply("operation_observed", json!({"observation": observation}))
            }
            "operation_result" => {
                let operation = self.operation(&id).clone();
                let Some(result) = operation.result else {
                    return Ok(self.refused("no_result"));
                };
                self.reply(
                    "operation_result",
                    json!({"operation_id": id, "definition_id": operation.definition,
                           "document": {"projection": result}}),
                )
            }
            "operation_review" => {
                let operation = self.operation(&id).clone();
                let Some(plan) = operation.review else {
                    return Ok(self.refused("not_pending"));
                };
                self.reply(
                    "operation_review",
                    json!({
                        "operation_id": id, "interaction_id": "1".repeat(64), "revision": operation.revision,
                        "review_digest": plan["plan_digest"], "document": {"projection": plan},
                    }),
                )
            }
            "operation_respond" => {
                let operation = self.operation(&id);
                let Some(plan) = operation.review.clone() else {
                    return Ok(self.refused("not_pending"));
                };
                if request["review_digest"] != plan["plan_digest"] {
                    return Ok(self.refused("review_changed"));
                }
                operation.review = None;
                operation.lifecycle = "running";
                operation.revision += 1;
                self.reply(
                    "operation_responded",
                    json!({"operation_id": id, "decision": request["decision"]}),
                )
            }
            other => panic!("unexpected relay action {other}"),
        })
    }
}

fn tracker() -> Tracker {
    Tracker::new(identity())
}

fn last_sign_in(hold: &FakeHold) -> String {
    hold.operations
        .iter()
        .rev()
        .find(|operation| operation.definition == GOOGLE_SIGN_IN)
        .expect("a submitted sign-in")
        .id
        .clone()
}

#[test]
fn google_sign_in_is_the_registered_operation_answered_once_and_read_back_after_its_cue() {
    let mut hold = FakeHold::new(settle_status);
    let mut tracker = tracker();
    tracker.handle(&mut hold, Act::Observe).unwrap();
    let started = tracker.handle(&mut hold, Act::SignIn).unwrap();
    assert_eq!(started.stage, GoogleStage::SigningIn);
    assert_eq!(hold.submitted(GOOGLE_SIGN_IN), 1);
    // The click is the person's act; the consent review is answered once, by its digest.
    let answers = hold.actions("operation_respond");
    assert_eq!(answers.len(), 1);
    assert_eq!(answers[0]["decision"], "apply");
    assert_eq!(answers[0]["review_digest"], "d".repeat(64));
    let id = answers[0]["operation_id"].as_str().unwrap().to_owned();
    tracker.handle(&mut hold, Act::SignIn).unwrap();
    assert_eq!(
        hold.submitted(GOOGLE_SIGN_IN),
        1,
        "a second click joins the running sign-in"
    );
    assert_eq!(hold.actions("operation_respond").len(), 1);

    hold.operation(&id)
        .settle("refused", Some(google_outcome(Some("needs_sign_in"))));
    let failed = tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(
        (failed.stage, failed.failure),
        (GoogleStage::Failed, Some(Failure::NeedsSignIn))
    );
    // A settled sign-in reads the stored sign-in again.
    assert_eq!(hold.submitted(GOOGLE_STATUS), 2);
    // A settled sign-in is not observed again until the next one starts.
    let observed = hold.actions("operation_observe").len();
    tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(hold.actions("operation_observe").len(), observed);

    tracker.handle(&mut hold, Act::SignIn).unwrap();
    let second = last_sign_in(&hold);
    hold.operation(&second)
        .settle("succeeded", Some(google_outcome(None)));
    hold.account = account(Some("persona@example.com"));
    let signed_in = tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(
        (signed_in.stage, signed_in.state, signed_in.email.as_deref()),
        (
            GoogleStage::Idle,
            Some(GoogleState::SignedIn),
            Some("persona@example.com")
        )
    );
    assert!(signed_in.failure.is_none());
}

#[test]
fn sign_out_is_the_registered_logout_and_the_stored_sign_in_is_read_after_it() {
    let mut hold = FakeHold::new(settle_status);
    hold.account = account(Some("persona@example.com"));
    let mut tracker = tracker();
    let before = tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(before.state, Some(GoogleState::SignedIn));
    hold.account = account(None);
    let after = tracker.handle(&mut hold, Act::SignOut).unwrap();
    assert_eq!(hold.submitted(GOOGLE_SIGN_OUT), 1);
    assert!(
        hold.actions("operation_respond").is_empty(),
        "sign-out asks nothing"
    );
    assert_eq!(
        (after.stage, after.state, after.email),
        (GoogleStage::Idle, Some(GoogleState::SignedOut), None)
    );
}

#[test]
fn a_stored_sign_in_the_build_cannot_read_is_named_and_one_that_cannot_be_read_is_unknown() {
    let mut hold = FakeHold::new(settle_status);
    hold.account = account_refused("not_in_this_build");
    let missing = tracker().handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(missing.state, Some(GoogleState::NotInThisBuild));
    hold.account = account_refused("needs_sign_in");
    let ended = tracker().handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(ended.state, Some(GoogleState::SignedOut));
    hold.account = ("failed", Value::Null);
    let unread = tracker().handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(unread.state, Some(GoogleState::Unknown));
}

#[test]
fn a_sign_in_that_ends_without_a_detailed_refusal_is_unexpected_and_a_cancel_is_cancelled() {
    let mut hold = FakeHold::new(settle_status);
    let mut tracker = tracker();
    tracker.handle(&mut hold, Act::SignIn).unwrap();
    let id = last_sign_in(&hold);
    hold.operation(&id).settle("failed", None);
    let failed = tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(failed.failure, Some(Failure::Unexpected));
    tracker.handle(&mut hold, Act::SignIn).unwrap();
    let id = last_sign_in(&hold);
    hold.operation(&id).settle("cancelled", None);
    let cancelled = tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(cancelled.failure, Some(Failure::Cancelled));
}

#[test]
fn a_tracker_follows_only_the_held_session_it_was_made_for() {
    let tracker = tracker();
    assert!(tracker.follows(&identity()));
    for key in [
        "profile_id",
        "session_id",
        "runtime_boot_id",
        "connection_id",
    ] {
        let mut other = identity();
        other[key] = json!("other");
        assert!(!tracker.follows(&other), "{key}");
    }
}

#[test]
fn drive_folder_requires_a_sign_in_and_grant_and_is_read_once_for_the_profile() {
    let mut hold = FakeHold::new(settle_status);
    let mut tracker = tracker();
    let signed_out = tracker.handle(&mut hold, Act::Observe).unwrap();
    assert!(signed_out.drive_folder_id.is_none());
    assert_eq!(hold.submitted(GOOGLE_FOLDER), 0);
    hold.account = account(Some("person@example.com"));
    let mut tracker = super::Tracker::new(identity());
    let signed_in = tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(
        signed_in.drive_folder_id.as_deref(),
        Some("profile-folder_123")
    );
    tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(hold.submitted(GOOGLE_FOLDER), 1);
    hold.account = account(None);
    let signed_out = tracker.handle(&mut hold, Act::SignOut).unwrap();
    assert!(signed_out.drive_folder_id.is_none());

    hold.account = account(Some("person@example.com"));
    hold.account.1["result"]["granted_scopes"] = json!(["openid", "email"]);
    let mut tracker = super::Tracker::new(identity());
    let no_grant = tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(no_grant.state, Some(GoogleState::SignedIn));
    assert!(no_grant.drive_folder_id.is_none());
    assert_eq!(hold.submitted(GOOGLE_FOLDER), 1);
}

#[test]
fn a_pending_or_refused_folder_does_not_hide_account_status_or_keep_a_stale_link() {
    let mut hold = FakeHold::new(settle_status);
    hold.account = account(Some("person@example.com"));
    hold.on_submit = Box::new(|operation| {
        if operation.definition != GOOGLE_FOLDER {
            settle_status(operation);
        }
    });
    let mut tracker = tracker();
    let pending = tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(pending.state, Some(GoogleState::SignedIn));
    assert!(pending.drive_folder_id.is_none());
    let folder = hold
        .operations
        .iter()
        .find(|op| op.definition == GOOGLE_FOLDER)
        .unwrap()
        .id
        .clone();
    hold.operation(&folder).settle("refused", None);
    let refused = tracker.handle(&mut hold, Act::Observe).unwrap();
    assert!(refused.drive_folder_id.is_none());
    assert_eq!(refused.state, Some(GoogleState::SignedIn));
    tracker.handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(hold.submitted(GOOGLE_FOLDER), 1);
}

#[test]
fn folder_links_reject_unconfigured_missing_and_non_identifier_results() {
    for (configured, id) in [
        (false, Some("folder")),
        (true, None),
        (true, Some("../other?auth=bad")),
        (true, Some("")),
    ] {
        let mut hold = FakeHold::new(settle_status);
        hold.account = account(Some("person@example.com"));
        hold.on_submit = Box::new(move |operation| {
            settle_status(operation);
            if operation.definition == GOOGLE_FOLDER {
                operation.settle("succeeded", Some(json!({
                    "outcome": "succeeded", "result": {"configured": configured, "root_folder_id": id}
                })));
            }
        });
        let google = tracker().handle(&mut hold, Act::Observe).unwrap();
        assert!(google.drive_folder_id.is_none());
        assert_eq!(google.state, Some(GoogleState::SignedIn));
    }
}

#[test]
fn a_reply_outside_the_runtimes_shape_is_a_host_failure() {
    let mut hold = FakeHold::new(|operation| {
        if operation.definition == GOOGLE_STATUS {
            operation.subject = "profile:another".into();
        }
    });
    hold.account = account(None);
    // The read the relay answered is not the one this window submitted: the account stays unknown.
    let google = tracker().handle(&mut hold, Act::Observe).unwrap();
    assert_eq!(google.state, Some(GoogleState::Unknown));
    let mut broken = FakeHold::new(settle_status);
    broken.account = ("succeeded", json!({"outcome": 7}));
    let failed = tracker().handle(&mut broken, Act::Observe).unwrap_err();
    assert!(
        matches!(&failed, Stop::Host(error)
            if error.reason.as_deref() == Some("setup_reply_shape")
                && matches!(error.causes.first(), Some(Cause::Json { .. }))),
        "the host failure names the shape and keeps what the parser found: {failed:?}"
    );
}

/// A relay that answers each call with the next scripted reply.
struct Scripted(std::collections::VecDeque<Value>);

impl Scripted {
    fn of<const N: usize>(replies: [Value; N]) -> Self {
        Self(replies.into())
    }
}

impl Relay for Scripted {
    fn call(&mut self, _: Value) -> std::result::Result<Value, ApplicationError> {
        Ok(self.0.pop_front().expect("a scripted reply"))
    }
}

fn runtime_refused(code: &str) -> Value {
    json!({"kind": "operation_refused", "code": code})
}

fn runtime_submitted() -> Value {
    json!({"kind": "operation_submitted", "operation_id": "1".repeat(64)})
}

/// The `unavailable` an act stopped at: its reason, and the runtime refusal code chained to it.
fn unavailable(result: std::result::Result<Google, Stop>) -> (Option<String>, Option<String>) {
    let Err(Stop::Unavailable(error)) = result else {
        panic!("an unavailable stop, not {result:?}");
    };
    let code = error.causes.iter().find_map(|cause| match cause {
        Cause::Child(refusal) => refusal.code.clone(),
        _ => None,
    });
    (error.reason.as_deref().map(str::to_owned), code)
}

#[test]
fn a_sign_in_the_runtime_will_not_start_is_unavailable_and_names_the_refusal() {
    let mut relay = Scripted::of([runtime_refused("operation_denied")]);
    assert_eq!(
        unavailable(tracker().handle(&mut relay, Act::SignIn)),
        (
            Some("setup_google_submit_refused".into()),
            Some("operation_denied".into())
        )
    );
}

#[test]
fn a_read_the_runtime_refuses_is_unavailable_and_names_the_refusal() {
    let mut relay = Scripted::of([runtime_submitted(), runtime_refused("operation_denied")]);
    assert_eq!(
        unavailable(tracker().handle(&mut relay, Act::SignIn)),
        (
            Some("setup_google_relay_refused".into()),
            Some("operation_denied".into())
        )
    );
}

/// The sign-in the relay submitted, observed while it waits for its consent review.
fn runtime_waiting() -> Value {
    json!({
        "kind": "operation_observed",
        "observation": {"projection": {
            "operation_id": "1".repeat(64), "definition_id": GOOGLE_SIGN_IN,
            "subject_ref": format!("profile:{PROFILE}"), "lifecycle": "waiting_for_interaction",
            "terminal_condition": null,
            "pending_interaction": {"disposition": "review_available",
                                    "interaction_id": "1".repeat(64), "revision": 2},
        }},
    })
}

#[test]
fn a_review_the_runtime_will_not_show_is_unavailable_and_names_the_refusal() {
    let mut relay = Scripted::of([
        runtime_submitted(),
        runtime_waiting(),
        runtime_refused("operation_denied"),
    ]);
    assert_eq!(
        unavailable(tracker().handle(&mut relay, Act::SignIn)),
        (
            Some("setup_google_review_refused".into()),
            Some("operation_denied".into())
        )
    );
}

#[test]
fn an_operation_the_relay_answers_for_another_subject_is_unavailable_and_named() {
    let mut hold = FakeHold::new(|operation| {
        if operation.definition == GOOGLE_SIGN_IN {
            operation.subject = "profile:another".into();
        }
    });
    assert_eq!(
        unavailable(tracker().handle(&mut hold, Act::SignIn)),
        (Some("setup_google_operation_mismatch".into()), None)
    );
}

#[test]
fn a_review_that_moved_on_meanwhile_is_a_refusal_to_word_and_not_an_unavailable_service() {
    let mut relay = Scripted::of([
        runtime_submitted(),
        runtime_waiting(),
        runtime_refused("not_pending"),
    ]);
    assert!(matches!(
        tracker().handle(&mut relay, Act::SignIn),
        Err(Stop::Refused(Refusal::NotPending))
    ));
}
