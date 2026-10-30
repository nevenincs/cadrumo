//! Admission against the replies of the agent service. The service's administration
//! channel is the only thing stood in for: a script of the replies it gives, which the
//! real readers of the provider status, the catalogue and the list of added models then
//! parse.
use super::*;
use cadrumo_application::error::application::{Cause, ErrorCode, Operation};
use std::{
    collections::{BTreeMap, VecDeque},
    sync::Mutex,
};

pub const LOCAL: &str = "synthetic_local_api";
pub const HOSTED: &str = "synthetic_hosted_api";
pub const TEXT: &str = "synthetic-text:test";
pub const VISION: &str = "synthetic-vision:test";
pub const ADDED: &str = "synthetic-added:test";
pub const HOSTED_MODEL: &str = "synthetic-hosted-1";
pub const GB: u64 = 1_000_000_000;

/// The replies a service gives by action, and the actions it was asked, in order. An
/// action nobody scripted fails as an unreachable service does.
#[derive(Default)]
pub struct Replies {
    answers: BTreeMap<&'static str, Value>,
    asked: Mutex<Vec<String>>,
}

impl Replies {
    pub fn answering(mut self, action: &'static str, reply: Value) -> Self {
        self.answers.insert(action, reply);
        self
    }

    /// The service with the provider status of the two synthetic lanes, a served
    /// catalogue recommending `recommended` and listing `cards` on the local lane, and
    /// `added` on the local lane's list.
    pub fn serving(recommended: &[&str], added: &[&str], cards: &[Card]) -> Self {
        Self::default()
            .answering("status", status())
            .answering("catalog", served(recommended, cards))
            .answering("local_models", list(added))
    }

    pub fn asked(&self) -> Vec<String> {
        self.asked
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .clone()
    }
}

impl Agent for Replies {
    fn generation(&self) -> Result<u64, ApplicationError> {
        Ok(0)
    }
    fn exchange(&self, request: Value) -> Result<Value, ApplicationError> {
        let action = request["action"].as_str().unwrap_or_default().to_owned();
        self.asked
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .push(action.clone());
        self.answers.get(action.as_str()).cloned().ok_or_else(|| {
            ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                .with_reason("agent_admin_unavailable")
        })
    }
}

fn revision() -> String {
    "a".repeat(64)
}

/// The models the person added to the local lane's list.
pub fn list(added: &[&str]) -> Value {
    let models: Vec<Value> = added
        .iter()
        .map(|model| json!({"lane": LOCAL, "model": model}))
        .collect();
    json!({"unreadable": false, "models": models, "reading": null, "local_lanes": [LOCAL], "revision": revision()})
}

fn lane(id: &str, provider: &str, auth_kind: &str, mode: &str, saved: bool) -> Value {
    json!({
        "id": id, "provider": provider, "display_name": provider, "transport": "api",
        "auth_kind": auth_kind, "consumers": [], "mode": mode, "credential_saved": saved,
        "available": true, "source": if saved { "profile" } else { "none" },
        "readiness": "ready", "reason": null, "revision": revision(),
    })
}

/// The provider status: a keyless lane on this computer, and a hosted lane with a key.
pub fn status() -> Value {
    json!({
        "development": false,
        "providers": [
            lane(LOCAL, "synthetic_local", "none", "unset", false),
            lane(HOSTED, "synthetic_hosted", "api_key", "key", true),
        ],
    })
}

/// A model and the download size its catalogue entry states, if it states one.
pub type Card<'a> = (&'a str, Option<u64>);

fn cards(key: &str, models: &[Card]) -> Vec<Value> {
    models
        .iter()
        .map(|(model, size)| json!({key: model, "size_bytes": size}))
        .collect()
}

/// A catalogue's recommendations, one capability per model.
fn recommendations(models: &[&str]) -> Value {
    let capabilities = ["vision", "text"];
    Value::Object(
        models
            .iter()
            .zip(capabilities)
            .map(|(model, capability)| (capability.to_owned(), json!(model)))
            .collect(),
    )
}

/// The catalogue a running agent serves: lane records by provider and transport.
pub fn served(recommended: &[&str], models: &[Card]) -> Value {
    json!({
        "api_version": "v1",
        "providers": [
            {"provider_id": "synthetic_hosted", "transport": "api",
             "catalog": {"recommended": {"text": HOSTED_MODEL},
                         "models": cards("model", &[(HOSTED_MODEL, Some(GB))])}},
            {"provider_id": "synthetic_local", "transport": "api",
             "catalog": {"recommended": recommendations(recommended),
                         "models": cards("model", models)}},
        ],
    })
}

/// The declared catalogue the service relays while no agent is ready, in its envelope.
pub fn declared(recommended: &[&str], models: &[Card]) -> Value {
    json!({
        "kind": "declared",
        "catalog": {"schema_version": 5, "providers": [
            {"id": HOSTED, "provider": "synthetic_hosted", "transport": "api",
             "recommended": {"text": HOSTED_MODEL},
             "models": cards("id", &[(HOSTED_MODEL, Some(GB))])},
            {"id": LOCAL, "provider": "synthetic_local", "transport": "api",
             "recommended": recommendations(recommended),
             "models": cards("id", models)},
        ]},
    })
}

/// The refusal a stop tells the window, so a result reads as it did before a stop could
/// also be a host failure; a host failure is no refusal and fails the test.
pub fn refusal<T>(result: Result<T, Stop>) -> Result<T, Refusal> {
    result.map_err(|stop| stop.refusal().expect("a refusal, not a host failure"))
}

/// The failure diagnostics keep for a stop the window words by its code alone.
pub fn cause<T: std::fmt::Debug>(result: Result<T, Stop>) -> ApplicationError {
    result
        .expect_err("a stop")
        .cause()
        .cloned()
        .expect("a stop that carries its cause")
}

/// An admission over `replies`, and the replies to ask what it read.
fn watched(replies: Replies) -> (Admission, Arc<Replies>) {
    let replies = Arc::new(replies);
    (Admission::new(replies.clone()), replies)
}

fn admission_of(replies: Replies) -> Admission {
    watched(replies).0
}

/// A download of `model` from `lane`.
pub fn requested(lane: &str, model: &str) -> ModelDownload {
    ModelDownload {
        lane: lane.into(),
        model: model.into(),
    }
}

fn admitted(model: &str, size: Option<u64>) -> LocalModels {
    LocalModels::new(vec![SelectedModel::new("download", model, size).unwrap()]).unwrap()
}

/// Override one read with a sequence, leaving the other service replies intact.
struct ScriptedRead {
    replies: Replies,
    action: &'static str,
    answers: Mutex<VecDeque<Result<Value, ApplicationError>>>,
}

impl Agent for ScriptedRead {
    fn generation(&self) -> Result<u64, ApplicationError> {
        Ok(0)
    }
    fn exchange(&self, request: Value) -> Result<Value, ApplicationError> {
        if request["action"] == self.action {
            self.replies.asked.lock().unwrap().push(self.action.into());
            self.answers
                .lock()
                .unwrap()
                .pop_front()
                .expect("unexpected retry")
        } else {
            self.replies.exchange(request)
        }
    }
}

fn scripted(
    action: &'static str,
    answers: Vec<Result<Value, ApplicationError>>,
) -> (Admission, Arc<ScriptedRead>) {
    let agent = Arc::new(ScriptedRead {
        replies: Replies::serving(&[TEXT], &[ADDED], &[(TEXT, Some(GB))]),
        action,
        answers: Mutex::new(answers.into()),
    });
    (Admission::new(agent.clone()), agent)
}

fn busy() -> Result<Value, ApplicationError> {
    Ok(json!({"kind": "refused", "code": "busy"}))
}

#[test]
fn admission_collects_busy_catalogue_and_local_model_reads() {
    let (admission, service) = scripted(
        "catalog",
        vec![busy(), Ok(served(&[TEXT], &[(TEXT, Some(GB))]))],
    );
    assert_eq!(
        admission.download(&requested(LOCAL, TEXT)).unwrap(),
        admitted(TEXT, Some(GB))
    );
    assert_eq!(service.replies.asked(), ["status", "catalog", "catalog"]);

    let (admission, service) = scripted("local_models", vec![busy(), Ok(list(&[ADDED]))]);
    let listed = admission.listed().unwrap();
    assert!(
        listed
            .as_slice()
            .iter()
            .any(|model| model.name.to_string() == ADDED)
    );
    assert_eq!(
        service.replies.asked(),
        ["status", "catalog", "local_models", "local_models"]
    );
}

#[test]
fn admission_stops_after_bounded_busy_replies_and_keeps_the_cause() {
    for action in ["catalog", "local_models"] {
        let (admission, service) = scripted(action, (0..READ_ATTEMPTS).map(|_| busy()).collect());
        let error = cause(admission.download(&requested(LOCAL, ADDED)));
        assert_eq!(
            error.reason.as_deref(),
            Some(if action == "catalog" {
                "setup_catalogue_refused"
            } else {
                "setup_local_models_refused"
            })
        );
        assert!(
            matches!(first_link(&error), Cause::Child(refusal) if refusal.code.as_deref() == Some("busy"))
        );
        assert_eq!(
            service
                .replies
                .asked()
                .iter()
                .filter(|asked| *asked == action)
                .count(),
            READ_ATTEMPTS
        );
    }
}

#[test]
fn admission_does_not_retry_sign_out_transport_failure_or_an_untyped_busy_code() {
    for action in ["catalog", "local_models"] {
        let (admission, service) = scripted(
            action,
            vec![busy(), Ok(json!({"kind": "refused", "code": "signed_out"}))],
        );
        assert_eq!(
            refusal(admission.download(&requested(LOCAL, ADDED))),
            Err(Refusal::NotSignedIn)
        );
        assert_eq!(
            service
                .replies
                .asked()
                .iter()
                .filter(|asked| *asked == action)
                .count(),
            2
        );

        let (admission, service) = scripted(
            action,
            vec![
                busy(),
                Err(ApplicationError::new(ErrorCode::TimedOut, Operation::Cli)
                    .with_reason("synthetic_timeout")),
            ],
        );
        let error = cause(admission.download(&requested(LOCAL, ADDED)));
        assert!(
            matches!(first_link(&error), Cause::Application { code: ErrorCode::TimedOut, reason: Some(reason), .. } if reason == "synthetic_timeout")
        );
        assert_eq!(
            service
                .replies
                .asked()
                .iter()
                .filter(|asked| *asked == action)
                .count(),
            2
        );
    }

    let (admission, service) = scripted("catalog", vec![Ok(json!({"code": "busy"}))]);
    assert_eq!(
        refusal(admission.download(&requested(LOCAL, TEXT))),
        Err(Refusal::ModelSelectionUnusable)
    );
    assert_eq!(
        service.replies.asked(),
        ["status", "catalog", "local_models"]
    );
}

#[test]
fn pending_download_collects_a_catalogue_after_more_than_four_busy_answers() {
    let mut answers: Vec<_> = (0..5).map(|_| busy()).collect();
    answers.push(Ok(served(&[TEXT], &[(TEXT, Some(GB))])));
    let (admission, service) = scripted("catalog", answers);
    let cancellation = Cancellation::default();
    assert_eq!(
        admission
            .download_with_budget(
                &requested(LOCAL, TEXT),
                &cancellation,
                Duration::from_secs(4)
            )
            .unwrap(),
        admitted(TEXT, Some(GB))
    );
    assert_eq!(
        service
            .replies
            .asked()
            .iter()
            .filter(|asked| *asked == "catalog")
            .count(),
        6
    );
}

#[test]
fn pending_download_stops_at_its_deadline_and_keeps_busy() {
    let (admission, service) = scripted("catalog", vec![busy(), busy()]);
    let cancellation = Cancellation::default();
    let error = cause(admission.download_with_budget(
        &requested(LOCAL, TEXT),
        &cancellation,
        Duration::from_millis(50),
    ));
    assert!(
        matches!(first_link(&error), Cause::Child(refusal) if refusal.code.as_deref() == Some("busy"))
    );
    assert_eq!(service.replies.asked(), ["status", "catalog"]);
}

#[test]
fn pending_download_collects_added_models_and_stops_on_other_answers() {
    let cancellation = Cancellation::default();
    let (admission, service) = scripted("local_models", vec![busy(), Ok(list(&[ADDED]))]);
    assert_eq!(
        admission
            .download_with_budget(
                &requested(LOCAL, ADDED),
                &cancellation,
                Duration::from_secs(4)
            )
            .unwrap(),
        admitted(ADDED, None)
    );
    assert_eq!(
        service.replies.asked(),
        ["status", "catalog", "local_models", "local_models"]
    );

    for action in ["status", "catalog", "local_models"] {
        let (admission, service) = scripted(
            action,
            vec![busy(), Ok(json!({"kind":"refused", "code":"signed_out"}))],
        );
        assert_eq!(
            refusal(admission.download_with_budget(
                &requested(LOCAL, ADDED),
                &cancellation,
                Duration::from_secs(4)
            )),
            Err(Refusal::NotSignedIn)
        );
        assert_eq!(
            service
                .replies
                .asked()
                .iter()
                .filter(|asked| *asked == action)
                .count(),
            2
        );

        let (admission, service) = scripted(
            action,
            vec![
                busy(),
                Err(ApplicationError::new(ErrorCode::TimedOut, Operation::Cli)
                    .with_reason("synthetic_timeout")),
            ],
        );
        let error = cause(admission.download_with_budget(
            &requested(LOCAL, ADDED),
            &cancellation,
            Duration::from_secs(4),
        ));
        assert!(
            matches!(first_link(&error), Cause::Application { code: ErrorCode::TimedOut, reason: Some(reason), .. } if reason == "synthetic_timeout")
        );
        assert_eq!(
            service
                .replies
                .asked()
                .iter()
                .filter(|asked| *asked == action)
                .count(),
            2
        );
    }
    let (admission, service) = scripted("catalog", vec![Ok(json!({"code":"busy"}))]);
    assert_eq!(
        refusal(admission.download_with_budget(
            &requested(LOCAL, TEXT),
            &cancellation,
            Duration::from_secs(4)
        )),
        Err(Refusal::ModelSelectionUnusable)
    );
    assert_eq!(
        service.replies.asked(),
        ["status", "catalog", "local_models"]
    );
}

struct HeldCatalog {
    generation: std::sync::atomic::AtomicU64,
    started: std::sync::mpsc::Sender<()>,
    release: Mutex<std::sync::mpsc::Receiver<()>>,
    asked: Mutex<Vec<String>>,
}

impl Agent for HeldCatalog {
    fn generation(&self) -> Result<u64, ApplicationError> {
        Ok(self.generation.load(std::sync::atomic::Ordering::Acquire))
    }
    fn exchange(&self, request: Value) -> Result<Value, ApplicationError> {
        let action = request["action"].as_str().unwrap().to_owned();
        self.asked.lock().unwrap().push(action.clone());
        if action == "status" {
            return Ok(status());
        }
        self.started.send(()).unwrap();
        self.release.lock().unwrap().recv().unwrap();
        Ok(served(&[TEXT], &[(TEXT, Some(GB))]))
    }
}

#[test]
fn pending_download_discards_a_reply_after_cancellation_or_service_replacement() {
    for cancel in [true, false] {
        let (started, waiting) = std::sync::mpsc::channel();
        let (release, released) = std::sync::mpsc::channel();
        let service = Arc::new(HeldCatalog {
            generation: std::sync::atomic::AtomicU64::new(1),
            started,
            release: Mutex::new(released),
            asked: Mutex::new(Vec::new()),
        });
        let cancellation = Arc::new(Cancellation::default());
        let worker = {
            let service = service.clone();
            let cancellation = cancellation.clone();
            std::thread::spawn(move || {
                Admission::new(service).download_with_budget(
                    &requested(LOCAL, TEXT),
                    &cancellation,
                    Duration::from_secs(4),
                )
            })
        };
        waiting.recv().unwrap();
        if cancel {
            cancellation.cancel();
        } else {
            service
                .generation
                .store(2, std::sync::atomic::Ordering::Release);
        }
        release.send(()).unwrap();
        let error = cause(worker.join().unwrap());
        assert!(
            matches!(first_link(&error), Cause::Application { reason: Some(reason), .. } if reason == if cancel { "setup_admission_cancelled" } else { "agent_admin_generation_changed" })
        );
        assert_eq!(*service.asked.lock().unwrap(), ["status", "catalog"]);
    }
    let (admission, service) = scripted("catalog", vec![]);
    let cancellation = Cancellation::default();
    cancellation.cancel();
    assert!(
        admission
            .download_with_budget(
                &requested(LOCAL, TEXT),
                &cancellation,
                Duration::from_secs(4)
            )
            .is_err()
    );
    assert!(service.replies.asked().is_empty());
}

#[test]
fn a_recommended_model_is_admitted_with_the_size_its_catalogue_entry_states() {
    let cards = [(TEXT, Some(2 * GB)), (VISION, Some(3 * GB))];
    for catalogue in [
        served(&[VISION, TEXT], &cards),
        declared(&[VISION, TEXT], &cards),
    ] {
        let (admission, replies) =
            watched(Replies::serving(&[VISION, TEXT], &[], &cards).answering("catalog", catalogue));
        assert_eq!(
            admission.download(&requested(LOCAL, VISION)).unwrap(),
            admitted(VISION, Some(3 * GB))
        );
        // A recommended model is on the list without the person adding it.
        assert_eq!(replies.asked(), ["status", "catalog"]);
    }
}

#[test]
fn an_added_model_is_admitted_with_its_stated_size_or_an_unknown_one() {
    for catalogue in [served(&[TEXT], &[]), declared(&[TEXT], &[])] {
        let (admission, replies) =
            watched(Replies::serving(&[TEXT], &[ADDED], &[]).answering("catalog", catalogue));
        assert_eq!(
            admission.download(&requested(LOCAL, ADDED)).unwrap(),
            admitted(ADDED, None)
        );
        assert_eq!(replies.asked(), ["status", "catalog", "local_models"]);
    }
    // A size the catalogue states for an added model is used; a zero one says nothing.
    for (stated, expected) in [(Some(GB), Some(GB)), (Some(0), None), (None, None)] {
        let replies = Replies::serving(&[TEXT], &[ADDED], &[(ADDED, stated)]);
        assert_eq!(
            admission_of(replies)
                .download(&requested(LOCAL, ADDED))
                .unwrap(),
            admitted(ADDED, expected),
            "{stated:?}"
        );
    }
}

#[test]
fn a_download_off_a_local_lanes_list_is_refused() {
    let mut disabled = status();
    disabled["providers"][0]["mode"] = json!("disabled");
    let cards = [(TEXT, Some(GB)), (VISION, Some(GB))];
    let elsewhere = "synthetic-elsewhere:test";
    for (name, lanes, lane, model) in [
        ("a hosted lane", status(), HOSTED, HOSTED_MODEL),
        ("a lane turned off", disabled, LOCAL, TEXT),
        ("an unknown lane", status(), "synthetic_gone_api", TEXT),
        ("a catalogue model nobody listed", status(), LOCAL, VISION),
        ("a model added to another lane", status(), LOCAL, elsewhere),
    ] {
        let replies = Replies::serving(&[TEXT], &[ADDED], &cards)
            .answering("status", lanes)
            .answering(
                "local_models",
                json!({"unreadable": false, "models": [
                    {"lane": LOCAL, "model": ADDED},
                    {"lane": HOSTED, "model": elsewhere},
                ], "reading": null, "local_lanes": [LOCAL], "revision": revision()}),
            );
        assert_eq!(
            refusal(admission_of(replies).download(&requested(lane, model))),
            Err(Refusal::ModelSelectionUnusable),
            "{name}"
        );
    }
}

#[test]
fn an_unreadable_list_admits_no_added_model_but_keeps_the_recommended_ones() {
    let unreadable = json!({
        "unreadable": true, "models": [], "reading": null, "local_lanes": [LOCAL], "revision": revision(),
    });
    let replies = || {
        Replies::serving(&[TEXT], &[], &[(TEXT, Some(GB))])
            .answering("local_models", unreadable.clone())
    };
    assert_eq!(
        refusal(admission_of(replies()).download(&requested(LOCAL, ADDED))),
        Err(Refusal::ModelSelectionUnusable)
    );
    assert_eq!(
        admission_of(replies())
            .download(&requested(LOCAL, TEXT))
            .unwrap(),
        admitted(TEXT, Some(GB))
    );
}

#[test]
fn a_removal_selects_every_model_on_a_local_lanes_lists_once() {
    let replies = Replies::serving(&[TEXT, VISION], &[ADDED, TEXT], &[]);
    let listed = admission_of(replies).listed().unwrap();
    let mut names: Vec<_> = listed
        .as_slice()
        .iter()
        .map(|model| model.name.to_string())
        .collect();
    names.sort();
    assert_eq!(names, [ADDED, TEXT, VISION]);
}

#[test]
fn a_removal_selects_nothing_from_a_list_nobody_can_read_or_a_lane_that_is_not_local() {
    let unreadable = json!({
        "unreadable": true, "models": [], "reading": null, "local_lanes": [LOCAL], "revision": revision(),
    });
    let listed =
        admission_of(Replies::serving(&[], &[], &[]).answering("local_models", unreadable))
            .listed()
            .unwrap();
    assert!(listed.is_empty(), "the hosted lane's model is no local one");
}

#[test]
fn a_removal_is_refused_for_a_list_name_the_engine_cannot_pull() {
    let replies = Replies::serving(&[], &["has space"], &[]);
    assert_eq!(
        refusal(admission_of(replies).listed()),
        Err(Refusal::ModelSelectionUnusable)
    );
}

#[test]
fn a_model_name_the_engine_cannot_pull_is_refused() {
    let replies = Replies::serving(&[], &["has space"], &[]);
    assert_eq!(
        refusal(admission_of(replies).download(&requested(LOCAL, "has space"))),
        Err(Refusal::ModelSelectionUnusable)
    );
}

/// The first link of a cause chain, as the Logs console shows it.
fn first_link(error: &ApplicationError) -> &Cause {
    error.causes.first().expect("a chained cause")
}

#[test]
fn a_service_that_does_not_answer_or_refuses_is_unavailable_and_names_what_it_did() {
    let reachable = || Replies::serving(&[], &[ADDED], &[]);
    type Chained = Box<dyn Fn(&Cause) -> bool>;
    let unanswered = |reason: &'static str| -> Chained {
        Box::new(move |cause| {
            matches!(cause, Cause::Application { code: ErrorCode::ReadFailed, reason: Some(named), .. }
                if named == reason)
        })
    };
    let refused = |code: &'static str| -> Chained {
        Box::new(
            move |cause| matches!(cause, Cause::Child(refusal) if refusal.code.as_deref() == Some(code)),
        )
    };
    let cases: Vec<(&str, Replies, &str, Chained)> = vec![
        (
            "no status reply",
            Replies::default(),
            "setup_provider_status_unanswered",
            unanswered("agent_admin_unavailable"),
        ),
        (
            "no catalogue reply",
            Replies::default().answering("status", status()),
            "setup_catalogue_unanswered",
            unanswered("agent_admin_unavailable"),
        ),
        (
            "no list reply",
            Replies::default()
                .answering("status", status())
                .answering("catalog", served(&[], &[])),
            "setup_local_models_unanswered",
            unanswered("agent_admin_unavailable"),
        ),
        (
            "a provider status the service refused",
            reachable().answering(
                "status",
                json!({"kind": "refused", "code": "service_stopping"}),
            ),
            "setup_provider_status_refused",
            refused("runtime_unavailable"),
        ),
        (
            "a catalogue the service refused",
            reachable().answering(
                "catalog",
                json!({"kind": "refused", "code": "catalog_unavailable"}),
            ),
            "setup_catalogue_refused",
            refused("catalog_unavailable"),
        ),
        (
            "a list the service refused",
            reachable().answering(
                "local_models",
                json!({"kind": "refused", "code": "service_stopping"}),
            ),
            "setup_local_models_refused",
            refused("service_stopping"),
        ),
    ];
    for (name, replies, reason, chained) in cases {
        let result = admission_of(replies).download(&requested(LOCAL, ADDED));
        assert_eq!(
            result.as_ref().err().and_then(Stop::refusal),
            Some(Refusal::Unavailable),
            "{name}"
        );
        let error = cause(result);
        assert_eq!(error.reason.as_deref(), Some(reason), "{name}");
        assert!(chained(first_link(&error)), "{name}: {error}");
    }
}

#[test]
fn a_list_outside_the_services_contract_is_a_host_failure_and_not_a_silent_service() {
    let mut duplicate = list(&[ADDED]);
    duplicate["models"] = json!([
        duplicate["models"][0].clone(),
        duplicate["models"][0].clone()
    ]);
    let cases = [
        ("models that are no list", json!({"models": "none"})),
        ("a revision of no digest", {
            let mut reply = list(&[ADDED]);
            reply["revision"] = json!("not-a-digest");
            reply
        }),
        ("a model twice", duplicate),
    ];
    for (name, reply) in cases {
        let replies = Replies::serving(&[], &[], &[]).answering("local_models", reply);
        let result = admission_of(replies).download(&requested(LOCAL, ADDED));
        assert!(
            matches!(&result, Err(Stop::Host(error))
                if error.code == ErrorCode::ReadFailed
                    && error.reason.as_deref() == Some("setup_local_models_contract")),
            "{name}: {result:?}"
        );
        assert_eq!(result.unwrap_err().refusal(), None, "{name}");
    }
}

#[test]
fn a_profile_that_is_signed_out_is_told_so() {
    let signed_out = || json!({"kind": "refused", "code": "signed_out"});
    let cases = [
        (
            "status",
            Replies::serving(&[], &[ADDED], &[]).answering("status", signed_out()),
        ),
        (
            "catalogue",
            Replies::serving(&[], &[ADDED], &[]).answering("catalog", signed_out()),
        ),
        (
            "list",
            Replies::serving(&[], &[ADDED], &[]).answering("local_models", signed_out()),
        ),
    ];
    for (name, replies) in cases {
        assert_eq!(
            refusal(admission_of(replies).download(&requested(LOCAL, ADDED))),
            Err(Refusal::NotSignedIn),
            "{name}"
        );
    }
}
