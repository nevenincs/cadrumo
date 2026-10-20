//! The tracker against a held session that relays like the hold does and
//! answers with documents shaped like the product's.
use super::*;

const PROFILE: &str = "12345678-1234-4234-8234-123456789abc";
const SESSION: &str = "22345678-1234-4234-8234-123456789abc";

fn identity() -> Value {
    json!({"profile_id": PROFILE, "session_id": SESSION, "runtime_boot_id": "b", "connection_id": "c"})
}

fn wording(rows: &[&str]) -> Value {
    json!({
        "names": [
            {"item_id": "browser", "name": "Navegador"},
            {"item_id": "local_ai", "name": "IA local"},
        ],
        "rows": rows.iter().map(|item| json!({
            "item_id": item, "name": format!("Nombre {item}"), "sentence": format!("Frase {item}"),
            "note": null, "action": if *item == "browser" { json!("Configurar") } else { Value::Null },
        })).collect::<Vec<_>>(),
        "failures": [
            {"category": "needs_sign_in", "sentence": "Tienes que iniciar sesión."},
            {"category": "unexpected", "sentence": "Algo ha fallado."},
            {"category": "interrupted", "sentence": "Se interrumpió."},
            {"category": "offline", "sentence": "Sin conexión."},
            {"category": "cancelled", "sentence": "Lo has cancelado."},
        ],
        "retry": "Reintento en {seconds} s (intento {attempt}).",
        "details": format!("Cadrumo setup details\nrows: {}\n", rows.join(",")),
    })
}

fn row(item: &str, state: &str) -> Value {
    json!({
        "item_id": item, "kind": item, "mode": "quick", "state": state,
        "stale_reason": null, "blocked_reason": null, "failure_category": null, "note": null,
        "version": null, "size_estimate_bytes": 100,
        "recovery": if item == "browser" { json!("set_up") } else { Value::Null },
        "recovery_action_id": if item == "browser" {
            json!("operator.provision.browser")
        } else {
            Value::Null
        },
    })
}

fn status(browser: &str) -> Value {
    json!({
        "mode": "quick", "rows": [row("browser", browser), row("local_ai", "ready")],
        "complete": false, "hardware_limited": false, "wording": wording(&["browser", "local_ai"]),
    })
}

fn plan_digest(download: u64) -> String {
    format!("{download:064x}")
}

fn review(download: u64) -> Value {
    json!({
        "identity": {}, "revision": 2, "plan_digest": plan_digest(download),
        "entries": [{
            "entry": {
                "item_id": "browser", "download_bytes": download, "source_hosts": ["cdn.playwright.dev"],
                "destination": "playwright_browsers", "installs_outside_program": false,
                "target_version": null, "advisories": [],
            },
            "destination_path": "C:\\Cadrumo\\components\\playwright", "shares_download_with": null,
            "licence_notice": null, "parts": [],
        }],
        "known_download_bytes": download, "has_unknown_size": false, "installs_outside_program": false,
        "space": {"free_bytes": 10_u64.pow(12), "required_bytes": download + 1},
        "space_sufficient": true, "reviewed_proposal_digest": "e".repeat(64),
        "wording": wording(&[]),
    })
}

fn setup_result(outcome: &str, failure: Option<&str>) -> Value {
    json!({
        "outcome": outcome, "plan_digest": plan_digest(100),
        "items": [{"item_id": "browser", "changed": failure.is_none(), "failure_category": failure,
                   "transferred_bytes": 100}],
        "space": null, "rows": [row("browser", "ready"), row("local_ai", "ready")], "complete": true,
        "wording": wording(&["browser", "local_ai"]),
    })
}

#[derive(Clone, Debug)]
struct FakeOperation {
    id: String,
    definition: String,
    subject: String,
    revision: u64,
    lifecycle: &'static str,
    condition: Option<&'static str>,
    phase: Option<String>,
    events: Vec<Value>,
    review: Option<Value>,
    result: Option<Value>,
    cancellable: bool,
    cancel_requested: bool,
}

impl FakeOperation {
    fn phase(&mut self, code: &str) {
        self.phase = Some(code.to_owned());
        self.events
            .push(json!({"kind": "phase", "phase_code": code}));
    }

    fn await_review(&mut self, download: u64) {
        self.review = Some(review(download));
        self.lifecycle = "waiting_for_interaction";
        self.revision = 2;
    }

    fn settle(&mut self, condition: &'static str, result: Option<Value>) {
        self.lifecycle = "terminal";
        self.condition = Some(condition);
        self.result = result;
        self.review = None;
        self.cancellable = false;
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
            "phase_code": self.phase, "progress": null, "cancellable_now": self.cancellable,
            "cancellation_requested": self.cancel_requested, "pending_interaction": pending,
        })
    }
}

type OnSubmit = Box<dyn FnMut(&mut FakeOperation)>;

/// The hold's relay, answering from fake operations as the runtime would publish them.
struct FakeHold {
    operations: Vec<FakeOperation>,
    calls: Vec<Value>,
    on_submit: OnSubmit,
    busy_holder: Option<String>,
    stale_cancellations: u32,
    /// How the next read of the stored Google sign-in settles: its condition and outcome.
    account: (&'static str, Value),
}

/// A stored sign-in read: signed in as `email`, or not signed in.
fn account(email: Option<&str>) -> (&'static str, Value) {
    let result = json!({"profile_id": PROFILE, "session_present": email.is_some(),
                        "account_email": email, "granted_scopes": [], "issued_at": null});
    (
        "succeeded",
        json!({"profile_id": PROFILE, "outcome": "succeeded", "result": result, "refusal": null}),
    )
}

/// A stored sign-in read the product refused, with the failure its refusal falls into.
fn account_refused(category: &str) -> (&'static str, Value) {
    ("refused", google_outcome(Some(category)))
}

const GOOGLE: [&str; 3] = [GOOGLE_SIGN_IN, GOOGLE_SIGN_OUT, GOOGLE_STATUS];

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
    } else if operation.definition == GOOGLE_STATUS {
        // The hold settles it from what it was told the stored sign-in is.
    } else if operation.definition != SETUP {
        operation.settle("succeeded", Some(status("absent")));
    }
}

fn awaiting_plan(operation: &mut FakeOperation) {
    settle_status(operation);
    if operation.definition == SETUP {
        operation.phase(PLAN_PHASE);
        operation.await_review(100);
    }
}

impl FakeHold {
    fn new(on_submit: fn(&mut FakeOperation)) -> Self {
        Self {
            operations: Vec::new(),
            calls: Vec::new(),
            on_submit: Box::new(on_submit),
            busy_holder: None,
            stale_cancellations: 0,
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

    fn refused(&self, code: &str, holder: Option<&str>) -> Value {
        self.reply(
            "operation_refused",
            json!({"code": code, "holder_operation_id": holder}),
        )
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
            "language_observe" => json!({"kind": "profile_language", "language": "es"}),
            "operation_submit" => {
                if request["definition_id"] == SETUP
                    && let Some(holder) = self.busy_holder.clone()
                {
                    return Ok(self.refused("subject_busy", Some(&holder)));
                }
                if GOOGLE
                    .iter()
                    .any(|google| request["definition_id"] == *google)
                {
                    assert_eq!(request["subject_ref"], format!("profile:{PROFILE}"));
                    assert_eq!(request["payload"], json!({"profile_id": PROFILE}));
                } else {
                    assert_eq!(request["subject_ref"], SUBJECT);
                    assert_eq!(request["payload"]["locale"], "es");
                }
                let mut operation = FakeOperation {
                    id: format!("{:064x}", self.operations.len() + 1),
                    definition: request["definition_id"].as_str().unwrap().to_owned(),
                    subject: request["subject_ref"].as_str().unwrap().to_owned(),
                    revision: 1,
                    lifecycle: "running",
                    condition: None,
                    phase: None,
                    events: Vec::new(),
                    review: None,
                    result: None,
                    cancellable: false,
                    cancel_requested: false,
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
                    return Ok(self.refused("operation_denied", None));
                };
                let after = request["after_cursor"].as_u64().unwrap() as usize;
                let events = operation.events[after.min(operation.events.len())..].to_vec();
                let observation = json!({
                    "projection": operation.projection(),
                    "event_page": {
                        "status": if events.is_empty() { "caught_up" } else { "page" },
                        "events": events,
                        "next_cursor": operation.events.len(),
                        "anchor_cursor": operation.events.len(),
                    },
                });
                self.reply("operation_observed", json!({"observation": observation}))
            }
            "operation_result" => {
                let operation = self.operation(&id).clone();
                let Some(result) = operation.result else {
                    return Ok(self.refused("no_result", None));
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
                    return Ok(self.refused("not_pending", None));
                };
                self.reply(
                    "operation_review",
                    json!({
                        "operation_id": id, "interaction_id": "1".repeat(64), "revision": operation.revision,
                        "expires_at": "2026-10-18T10:00:00+00:00",
                        "review_digest": plan["plan_digest"], "document": {"projection": plan},
                    }),
                )
            }
            "operation_respond" => {
                let operation = self.operation(&id);
                let Some(plan) = operation.review.clone() else {
                    return Ok(self.refused("not_pending", None));
                };
                if request["review_digest"] != plan["plan_digest"] {
                    return Ok(self.refused("review_changed", None));
                }
                operation.review = None;
                operation.lifecycle = "running";
                operation.revision += 1;
                operation.cancellable = true;
                self.reply(
                    "operation_responded",
                    json!({"operation_id": id, "decision": request["decision"]}),
                )
            }
            "operation_cancel" => {
                if self.stale_cancellations > 0 {
                    self.stale_cancellations -= 1;
                    self.operation(&id).revision += 1;
                    return Ok(self.refused("stale_operation_revision", None));
                }
                let operation = self.operation(&id);
                assert_eq!(request["expected_revision"], operation.revision);
                operation.cancel_requested = true;
                operation.cancellable = false;
                self.reply("operation_cancel_requested", json!({"operation_id": id}))
            }
            other => panic!("unexpected relay action {other}"),
        })
    }
}

fn tracker() -> Tracker {
    Tracker::new(identity())
}

fn start(resume: bool) -> Action {
    Action::Start {
        items: Some(vec!["browser".into()]),
        model: None,
        resume,
    }
}

fn answer(operation_id: &str, plan_digest: &str, decision: Decision) -> Action {
    Action::Answer {
        operation_id: operation_id.into(),
        plan_digest: plan_digest.into(),
        decision,
    }
}

fn refused(result: std::result::Result<Snapshot, Stop>) -> Refusal {
    match result {
        Err(Stop::Refused(code)) => code,
        other => panic!("expected a refusal, got {other:?}"),
    }
}

fn reviewing(tracker: &mut Tracker, hold: &mut FakeHold, resume: bool) -> (String, String) {
    let snapshot = tracker.handle(hold, start(resume)).unwrap();
    let run = snapshot.setup.expect("a setup");
    assert_eq!(run.stage, RunStage::Review);
    (
        run.operation_id,
        run.review.expect("its review").plan_digest,
    )
}

fn responded(hold: &FakeHold, decision: &str) -> usize {
    hold.actions("operation_respond")
        .iter()
        .filter(|call| call["decision"] == decision)
        .count()
}

#[test]
fn the_first_observation_reads_status_with_the_words_the_product_returned() {
    let mut hold = FakeHold::new(settle_status);
    let snapshot = tracker().handle(&mut hold, Action::Observe).unwrap();
    assert_eq!(hold.submitted(STATUS), 1);
    assert_eq!(snapshot.check.unwrap().stage, CheckStage::Done);
    assert_eq!(
        (snapshot.rows_mode, snapshot.complete),
        (Some(CheckMode::Quick), Some(false))
    );
    let browser = &snapshot.rows[0];
    assert_eq!(
        (browser.item.as_str(), browser.state, browser.recovery),
        ("browser", State::Absent, Some(Recovery::SetUp))
    );
    assert_eq!(
        browser.recovery_action_id.as_deref(),
        Some("operator.provision.browser")
    );
    assert_eq!(
        (
            browser.name.as_str(),
            browser.sentence.as_str(),
            browser.action_label.as_deref()
        ),
        ("Nombre browser", "Frase browser", Some("Configurar"))
    );
    assert!(snapshot.setup.is_none() && snapshot.google.stage == GoogleStage::Idle);
    assert!(snapshot.details.contains("rows: browser,local_ai"));
    // The profile's Google sign-in is read beside the rows, never as one of them.
    assert_eq!(hold.submitted(GOOGLE_STATUS), 1);
    assert_eq!(
        (snapshot.google.state, snapshot.google.email),
        (Some(GoogleState::SignedOut), None)
    );
    assert!(snapshot.rows.iter().all(|row| row.item != "google"));
}

#[test]
fn an_answer_binds_the_exact_plan_digest_and_a_changed_plan_is_refused_without_a_response() {
    let mut hold = FakeHold::new(awaiting_plan);
    let mut tracker = tracker();
    let (operation, digest) = reviewing(&mut tracker, &mut hold, false);
    assert_eq!(digest, plan_digest(100));
    hold.operation(&operation).review = Some(review(200));
    let changed = tracker.handle(&mut hold, answer(&operation, &digest, Decision::Apply));
    assert_eq!(refused(changed), Refusal::PlanChanged);
    assert!(hold.actions("operation_respond").is_empty());
    let answered = tracker
        .handle(
            &mut hold,
            answer(&operation, &plan_digest(200), Decision::Apply),
        )
        .unwrap();
    assert_eq!(responded(&hold, "apply"), 1);
    let respond = hold.actions("operation_respond")[0].clone();
    assert_eq!(respond["interaction_id"], "1".repeat(64));
    assert_eq!(respond["review_digest"], plan_digest(200));
    let run = answered.setup.unwrap();
    assert!(run.stage == RunStage::Running && run.review.is_none());
}

#[test]
fn a_rejection_answers_the_plan_and_another_operation_is_not_pending() {
    let mut hold = FakeHold::new(awaiting_plan);
    let mut tracker = tracker();
    let (operation, digest) = reviewing(&mut tracker, &mut hold, false);
    let other = tracker.handle(&mut hold, answer(&"9".repeat(64), &digest, Decision::Apply));
    assert_eq!(refused(other), Refusal::NotPending);
    tracker
        .handle(&mut hold, answer(&operation, &digest, Decision::Reject))
        .unwrap();
    assert_eq!(
        (responded(&hold, "apply"), responded(&hold, "reject")),
        (0, 1)
    );
}

#[test]
fn the_review_shows_the_products_names_and_plan() {
    let mut hold = FakeHold::new(awaiting_plan);
    let snapshot = tracker().handle(&mut hold, start(false)).unwrap();
    let review = snapshot.setup.unwrap().review.unwrap();
    let entry = &review.entries[0];
    assert_eq!(
        (entry.item.as_str(), entry.name.as_str()),
        ("browser", "Navegador")
    );
    assert_eq!(entry.source_hosts, vec!["cdn.playwright.dev".to_owned()]);
    assert_eq!(
        (
            review.required_bytes,
            review.free_bytes,
            review.space_sufficient
        ),
        (101, Some(10_u64.pow(12)), true)
    );
    assert_eq!(
        review.expires_at.as_deref(),
        Some("2026-10-18T10:00:00+00:00")
    );
}

#[test]
fn progress_phases_and_retries_follow_each_item_and_the_result_settles_the_rows() {
    let mut hold = FakeHold::new(awaiting_plan);
    let mut tracker = tracker();
    let (operation, digest) = reviewing(&mut tracker, &mut hold, false);
    tracker
        .handle(&mut hold, answer(&operation, &digest, Decision::Apply))
        .unwrap();
    let running = hold.operation(&operation);
    running.phase("dependencies.setup.browser.download");
    running.events.push(
        json!({"kind": "progress", "subject_code": "browser", "completed": 40, "total": 100}),
    );
    running
        .events
        .push(json!({"kind": "notice", "notice_code": "dependencies.setup.browser.retry.2.4"}));
    let snapshot = tracker.handle(&mut hold, Action::Observe).unwrap();
    let run = snapshot.setup.unwrap();
    assert!(run.cancellable);
    let item = &run.items[0];
    assert_eq!(
        (
            item.item.as_str(),
            item.step,
            item.completed,
            item.total,
            item.name.as_str()
        ),
        (
            "browser",
            Some(Step::Download),
            Some(40),
            Some(100),
            "Navegador"
        )
    );
    let retry = item.retry.as_ref().unwrap();
    assert_eq!(
        (retry.attempt, retry.delay_s, retry.sentence.as_str()),
        (2, 4, "Reintento en 4 s (intento 2).")
    );
    hold.operation(&operation)
        .settle("succeeded", Some(setup_result("completed", None)));
    let settled = tracker.handle(&mut hold, Action::Observe).unwrap();
    let run = settled.setup.unwrap();
    assert_eq!(
        (run.stage, run.outcome),
        (RunStage::Settled, Some(Outcome::Completed))
    );
    let result = run.items[0].result.as_ref().unwrap();
    assert!(result.changed && result.sentence.is_none() && run.items[0].retry.is_none());
    assert_eq!(settled.complete, Some(true));
    assert_eq!(settled.rows[0].state, State::Ready);
}

#[test]
fn a_failed_operation_carries_the_products_unexpected_sentence() {
    let mut hold = FakeHold::new(awaiting_plan);
    let mut tracker = tracker();
    let (operation, _digest) = reviewing(&mut tracker, &mut hold, false);
    hold.operation(&operation).settle("failed", None);
    let run = tracker
        .handle(&mut hold, Action::Observe)
        .unwrap()
        .setup
        .unwrap();
    assert_eq!(
        (run.outcome, run.failure_sentence.as_deref()),
        (Some(Outcome::Failed), Some("Algo ha fallado."))
    );
}

#[test]
fn cancel_retries_a_stale_revision_once_and_refuses_what_cannot_be_cancelled() {
    let mut hold = FakeHold::new(awaiting_plan);
    let mut tracker = tracker();
    let (operation, digest) = reviewing(&mut tracker, &mut hold, false);
    let early = tracker.handle(
        &mut hold,
        Action::Cancel {
            operation_id: operation.clone(),
        },
    );
    assert_eq!(refused(early), Refusal::NotCancellable);
    tracker
        .handle(&mut hold, answer(&operation, &digest, Decision::Apply))
        .unwrap();
    hold.stale_cancellations = 1;
    let cancelled = tracker
        .handle(
            &mut hold,
            Action::Cancel {
                operation_id: operation.clone(),
            },
        )
        .unwrap();
    assert!(cancelled.setup.unwrap().cancel_requested);
    assert_eq!(hold.actions("operation_cancel").len(), 2);
}

#[test]
fn resume_right_after_an_interruption_applies_the_unchanged_plan_without_a_second_dialog() {
    let mut hold = FakeHold::new(awaiting_plan);
    let mut tracker = tracker();
    let (operation, digest) = reviewing(&mut tracker, &mut hold, false);
    tracker
        .handle(&mut hold, answer(&operation, &digest, Decision::Apply))
        .unwrap();
    hold.operation(&operation).settle("interrupted", None);
    tracker.handle(&mut hold, Action::Observe).unwrap();
    let resumed = tracker.handle(&mut hold, start(true)).unwrap();
    assert_eq!(resumed.setup.unwrap().stage, RunStage::Running);
    assert_eq!(responded(&hold, "apply"), 2);
}

#[test]
fn only_resume_after_an_interruption_skips_the_dialog_and_only_for_the_same_plan() {
    let mut hold = FakeHold::new(awaiting_plan);
    let mut tracker = tracker();
    let (operation, digest) = reviewing(&mut tracker, &mut hold, false);
    tracker
        .handle(&mut hold, answer(&operation, &digest, Decision::Apply))
        .unwrap();
    hold.operation(&operation).settle(
        "succeeded",
        Some(setup_result("interrupted", Some("interrupted"))),
    );
    let interrupted = tracker.handle(&mut hold, Action::Observe).unwrap();
    let run = interrupted.setup.unwrap();
    assert_eq!(run.outcome, Some(Outcome::Interrupted));
    assert_eq!(
        run.items[0].result.as_ref().unwrap().sentence.as_deref(),
        Some("Se interrumpió.")
    );
    // A plain start shows the same plan again.
    let (shown, _digest) = reviewing(&mut tracker, &mut hold, false);
    assert_eq!(responded(&hold, "apply"), 1);
    hold.operation(&shown).settle("cancelled", None);
    tracker.handle(&mut hold, Action::Observe).unwrap();
    // The interruption is no longer the last ending, so even Resume asks again.
    reviewing(&mut tracker, &mut hold, true);
    assert_eq!(responded(&hold, "apply"), 1);
}

#[test]
fn a_setup_held_by_another_session_is_busy_and_a_running_one_is_joined() {
    let mut hold = FakeHold::new(settle_status);
    hold.busy_holder = Some("7".repeat(64));
    let mut tracker = tracker();
    assert_eq!(
        refused(tracker.handle(&mut hold, start(false))),
        Refusal::Busy
    );
    hold.busy_holder = None;
    hold.on_submit = Box::new(awaiting_plan);
    let (first, _digest) = reviewing(&mut tracker, &mut hold, false);
    let second = tracker.handle(&mut hold, start(false)).unwrap();
    assert_eq!(second.setup.unwrap().operation_id, first);
    assert_eq!(hold.submitted(SETUP), 1);
}

fn last_google(hold: &FakeHold) -> String {
    hold.operations
        .iter()
        .rev()
        .find(|operation| operation.definition == GOOGLE_SIGN_IN)
        .expect("a submitted sign-in")
        .id
        .clone()
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

#[test]
fn google_sign_in_is_the_registered_operation_answered_once_and_read_back_after_its_cue() {
    let mut hold = FakeHold::new(settle_status);
    let mut tracker = tracker();
    tracker.handle(&mut hold, Action::Observe).unwrap();
    let started = tracker.handle(&mut hold, Action::GoogleSignIn).unwrap();
    assert_eq!(started.google.stage, GoogleStage::SigningIn);
    assert_eq!(hold.submitted(GOOGLE_SIGN_IN), 1);
    // The click is the person's act; the consent review is answered once, by its digest.
    let answers = hold.actions("operation_respond");
    assert_eq!(answers.len(), 1);
    assert_eq!(answers[0]["decision"], "apply");
    assert_eq!(answers[0]["review_digest"], "d".repeat(64));
    let id = answers[0]["operation_id"].as_str().unwrap().to_owned();
    tracker.handle(&mut hold, Action::GoogleSignIn).unwrap();
    assert_eq!(
        hold.submitted(GOOGLE_SIGN_IN),
        1,
        "a second click joins the running sign-in"
    );
    assert_eq!(hold.actions("operation_respond").len(), 1);

    hold.operation(&id)
        .settle("refused", Some(google_outcome(Some("needs_sign_in"))));
    let failed = tracker.handle(&mut hold, Action::Observe).unwrap().google;
    assert_eq!(
        (failed.stage, failed.failure, failed.sentence.as_deref()),
        (
            GoogleStage::Failed,
            Some(Failure::NeedsSignIn),
            Some("Tienes que iniciar sesión.")
        )
    );
    // A settled sign-in reads the stored sign-in again, and leaves the setup rows alone.
    assert_eq!(hold.submitted(STATUS), 1);
    assert_eq!(hold.submitted(GOOGLE_STATUS), 2);
    // A settled sign-in is not observed again until the next one starts.
    let observed = hold.actions("operation_observe").len();
    tracker.handle(&mut hold, Action::Observe).unwrap();
    assert_eq!(hold.actions("operation_observe").len(), observed);

    tracker.handle(&mut hold, Action::GoogleSignIn).unwrap();
    let second = last_google(&hold);
    hold.operation(&second)
        .settle("succeeded", Some(google_outcome(None)));
    hold.account = account(Some("persona@example.com"));
    let signed_in = tracker.handle(&mut hold, Action::Observe).unwrap().google;
    assert_eq!(
        (signed_in.stage, signed_in.state, signed_in.email.as_deref()),
        (
            GoogleStage::Idle,
            Some(GoogleState::SignedIn),
            Some("persona@example.com")
        )
    );
    assert!(signed_in.sentence.is_none());
}

#[test]
fn sign_out_is_the_registered_logout_and_the_stored_sign_in_is_read_after_it() {
    let mut hold = FakeHold::new(settle_status);
    hold.account = account(Some("persona@example.com"));
    let mut tracker = tracker();
    let before = tracker.handle(&mut hold, Action::Observe).unwrap().google;
    assert_eq!(before.state, Some(GoogleState::SignedIn));
    hold.account = account(None);
    let after = tracker
        .handle(&mut hold, Action::GoogleSignOut)
        .unwrap()
        .google;
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
    let missing = tracker().handle(&mut hold, Action::Observe).unwrap().google;
    assert_eq!(missing.state, Some(GoogleState::NotInThisBuild));
    hold.account = account_refused("needs_sign_in");
    let ended = tracker().handle(&mut hold, Action::Observe).unwrap().google;
    assert_eq!(ended.state, Some(GoogleState::SignedOut));
    hold.account = ("failed", Value::Null);
    let unread = tracker().handle(&mut hold, Action::Observe).unwrap();
    assert_eq!(unread.google.state, Some(GoogleState::Unknown));
    // The setup rows still arrive when the sign-in cannot be read.
    assert_eq!(unread.rows.len(), 2);
}

#[test]
fn a_sign_in_that_ends_without_a_detailed_refusal_is_unexpected_and_a_cancel_is_cancelled() {
    let mut hold = FakeHold::new(settle_status);
    let mut tracker = tracker();
    tracker.handle(&mut hold, Action::GoogleSignIn).unwrap();
    let id = last_google(&hold);
    hold.operation(&id).settle("failed", None);
    let failed = tracker.handle(&mut hold, Action::Observe).unwrap().google;
    assert_eq!(failed.failure, Some(Failure::Unexpected));
    tracker.handle(&mut hold, Action::GoogleSignIn).unwrap();
    let id = last_google(&hold);
    hold.operation(&id).settle("cancelled", None);
    let cancelled = tracker.handle(&mut hold, Action::Observe).unwrap().google;
    assert_eq!(cancelled.failure, Some(Failure::Cancelled));
}

#[test]
fn a_document_outside_the_products_shape_is_a_host_failure_not_a_snapshot() {
    let mut hold = FakeHold::new(|operation| {
        let mut broken = status("absent");
        broken["rows"][0]["state"] = json!("broken");
        operation.settle("succeeded", Some(broken));
    });
    assert!(matches!(
        tracker().handle(&mut hold, Action::Observe),
        Err(Stop::Host(_))
    ));
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
fn phase_and_retry_codes_parse_only_in_their_closed_forms() {
    assert_eq!(
        setup_phase("dependencies.setup.local_ai.download"),
        Some(("local_ai", Step::Download))
    );
    assert_eq!(
        setup_phase("dependencies.setup.local_model.text_extraction.download"),
        None
    );
    assert_eq!(setup_phase("dependencies.setup.browser.unpack"), None);
    assert_eq!(setup_phase("dependencies.setup.printer.download"), None);
    assert_eq!(
        retry_notice("dependencies.setup.browser.retry.3.0"),
        Some(("browser", 3, 1))
    );
    assert_eq!(retry_notice("dependencies.setup.browser.retry.1.4"), None);
    assert_eq!(retry_notice("dependencies.setup.browser.retry.x.4"), None);
}
