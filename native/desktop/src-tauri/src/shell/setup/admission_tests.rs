//! Admission against the replies of the agent service. The service's administration
//! channel is the only thing stood in for: a script of the replies it gives, which the
//! real readers of the selection, the provider status and the catalogue then parse.
use super::*;
use cadrumo_application::error::application::{ErrorCode, Operation};
use std::{collections::BTreeMap, sync::Mutex};

pub const LOCAL: &str = "synthetic_local_api";
pub const HOSTED: &str = "synthetic_hosted_api";
pub const TEXT: &str = "synthetic-text:test";
pub const VISION: &str = "synthetic-vision:test";
pub const HOSTED_MODEL: &str = "synthetic-hosted-1";
const ROLES: [&str; 4] = [
    "vision_transcription",
    "text_extraction",
    "column_role_mapping",
    "supply_nature_proposal",
];
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

    /// The service when nobody selected a model for any role.
    pub fn without_selection() -> Self {
        Self::default().answering("model_roles", roles(&[]))
    }

    /// The service with `picks` selected, the provider status of the two synthetic
    /// lanes and the served catalogue listing `models` on the local one.
    pub fn selecting(picks: &[(&str, &str, &str)], models: &[Card]) -> Self {
        Self::default()
            .answering("model_roles", roles(picks))
            .answering("status", status())
            .answering("catalog", served(models))
    }

    pub fn asked(&self) -> Vec<String> {
        self.asked
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .clone()
    }
}

impl Agent for Replies {
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

/// Every role's selection, with none for the roles `picks` leaves out.
pub fn roles(picks: &[(&str, &str, &str)]) -> Value {
    let roles: Vec<Value> = ROLES
        .iter()
        .map(
            |role| match picks.iter().find(|(named, _, _)| named == role) {
                Some((_, lane, model)) => json!({"role": role, "lane": lane, "model": model}),
                None => json!({"role": role, "lane": null, "model": null}),
            },
        )
        .collect();
    json!({"unreadable": false, "roles": roles, "revision": revision()})
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
type Card<'a> = (&'a str, Option<u64>);

fn listed(key: &str, models: &[Card]) -> Vec<Value> {
    models
        .iter()
        .map(|(model, size)| json!({key: model, "size_bytes": size}))
        .collect()
}

/// The catalogue a running agent serves: lane records by provider and transport.
pub fn served(models: &[Card]) -> Value {
    json!({
        "api_version": "v1",
        "providers": [
            {"provider_id": "synthetic_hosted", "transport": "api",
             "catalog": {"models": listed("model", &[(HOSTED_MODEL, None)])}},
            {"provider_id": "synthetic_local", "transport": "api",
             "catalog": {"models": listed("model", models)}},
        ],
    })
}

/// The declared catalogue the service relays while no agent is ready, in its envelope.
pub fn declared(models: &[Card]) -> Value {
    json!({
        "kind": "declared",
        "catalog": {"schema_version": 5, "providers": [
            {"id": HOSTED, "provider": "synthetic_hosted", "transport": "api",
             "models": listed("id", &[(HOSTED_MODEL, None)])},
            {"id": LOCAL, "provider": "synthetic_local", "transport": "api",
             "models": listed("id", models)},
        ]},
    })
}

/// An admission over `replies`, and the replies to ask what it read.
fn watched(replies: Replies) -> (Admission, Arc<Replies>) {
    let replies = Arc::new(replies);
    (Admission::new(replies.clone()), replies)
}

fn admission_of(replies: Replies) -> Admission {
    watched(replies).0
}

fn models(triples: &[(&str, &str, u64)]) -> LocalModels {
    LocalModels::new(
        triples
            .iter()
            .map(|(role, name, size)| SelectedModel::new(role, name, *size).unwrap())
            .collect(),
    )
    .unwrap()
}

#[test]
fn a_local_lane_selection_is_admitted_with_the_size_its_catalogue_entry_states() {
    let (admission, replies) = watched(Replies::selecting(
        &[
            ("vision_transcription", LOCAL, VISION),
            ("text_extraction", LOCAL, TEXT),
            ("column_role_mapping", HOSTED, HOSTED_MODEL),
        ],
        &[(TEXT, Some(2 * GB)), (VISION, Some(3 * GB))],
    ));
    assert_eq!(
        admission.local_models().unwrap(),
        models(&[
            ("text_extraction", TEXT, 2 * GB),
            ("vision_transcription", VISION, 3 * GB),
        ])
    );
    assert_eq!(replies.asked(), ["model_roles", "status", "catalog"]);
}

#[test]
fn the_declared_catalogue_states_the_same_sizes_while_no_agent_is_ready() {
    let replies = Replies::selecting(&[("text_extraction", LOCAL, TEXT)], &[]).answering(
        "catalog",
        declared(&[(VISION, Some(3 * GB)), (TEXT, Some(2 * GB))]),
    );
    let (admission, _) = watched(replies);
    assert_eq!(
        admission.local_models().unwrap(),
        models(&[("text_extraction", TEXT, 2 * GB)])
    );
}

#[test]
fn two_roles_selecting_one_model_are_admitted_under_its_one_size() {
    let (admission, _) = watched(Replies::selecting(
        &[
            ("text_extraction", LOCAL, TEXT),
            ("column_role_mapping", LOCAL, TEXT),
        ],
        &[(TEXT, Some(2 * GB))],
    ));
    assert_eq!(
        admission.local_models().unwrap(),
        models(&[
            ("column_role_mapping", TEXT, 2 * GB),
            ("text_extraction", TEXT, 2 * GB),
        ])
    );
}

#[test]
fn a_hosted_lane_is_not_admitted_and_its_catalogue_is_not_read() {
    let (admission, replies) = watched(Replies::selecting(
        &[("text_extraction", HOSTED, HOSTED_MODEL)],
        &[],
    ));
    assert!(admission.local_models().unwrap().is_empty());
    assert_eq!(replies.asked(), ["model_roles", "status"]);
}

#[test]
fn a_local_lane_the_person_turned_off_is_not_admitted_and_its_catalogue_is_not_read() {
    let turned_off = json!({
        "development": false,
        "providers": [lane(LOCAL, "synthetic_local", "none", "disabled", false)],
    });
    let (admission, replies) = watched(
        Replies::selecting(
            &[("vision_transcription", LOCAL, VISION)],
            &[(VISION, Some(3 * GB))],
        )
        .answering("status", turned_off),
    );
    assert!(admission.local_models().unwrap().is_empty());
    assert_eq!(replies.asked(), ["model_roles", "status"]);
}

#[test]
fn a_lane_the_status_does_not_list_is_not_admitted() {
    let (admission, replies) = watched(Replies::selecting(
        &[("text_extraction", "synthetic_gone_api", TEXT)],
        &[(TEXT, Some(2 * GB))],
    ));
    assert!(admission.local_models().unwrap().is_empty());
    assert_eq!(replies.asked(), ["model_roles", "status"]);
}

#[test]
fn no_selection_admits_the_program_alone_and_reads_nothing_else() {
    let (admission, replies) = watched(Replies::without_selection());
    assert_eq!(admission.local_models().unwrap(), LocalModels::default());
    assert_eq!(replies.asked(), ["model_roles"]);
}

#[test]
fn a_model_whose_entry_states_no_size_is_refused_whole_and_never_dropped() {
    let picks = [
        ("vision_transcription", LOCAL, VISION),
        ("text_extraction", LOCAL, TEXT),
    ];
    let cases: [(&str, &[Card]); 4] = [
        ("size null", &[(VISION, Some(3 * GB)), (TEXT, None)]),
        ("size zero", &[(VISION, Some(3 * GB)), (TEXT, Some(0))]),
        ("model unlisted", &[(VISION, Some(3 * GB))]),
        ("catalogue lists nothing", &[]),
    ];
    for (name, listed) in cases {
        let (admission, _) = watched(Replies::selecting(&picks, listed));
        assert_eq!(
            admission.local_models(),
            Err(Refusal::ModelSizeUnstated),
            "{name}"
        );
    }
    // The declared catalogue is held to the same.
    let replies = Replies::selecting(&picks, &[]).answering(
        "catalog",
        declared(&[(VISION, Some(3 * GB)), (TEXT, Some(0))]),
    );
    assert_eq!(
        admission_of(replies).local_models(),
        Err(Refusal::ModelSizeUnstated)
    );
}

#[test]
fn an_unreadable_record_is_refused_and_never_read_as_no_selection() {
    let replies = Replies::default().answering(
        "model_roles",
        json!({"unreadable": true, "roles": [], "revision": null}),
    );
    assert_eq!(
        admission_of(replies).local_models(),
        Err(Refusal::ModelSelectionUnusable)
    );
}

#[test]
fn a_model_name_the_engine_cannot_pull_is_refused() {
    let replies = Replies::selecting(
        &[("text_extraction", LOCAL, "has space")],
        &[("has space", Some(GB))],
    );
    assert_eq!(
        admission_of(replies).local_models(),
        Err(Refusal::ModelSelectionUnusable)
    );
}

#[test]
fn a_service_that_does_not_answer_is_unavailable_and_no_selection_is_invented() {
    let picks = [("text_extraction", LOCAL, TEXT)];
    let listed = [(TEXT, Some(GB))];
    let reachable = || Replies::selecting(&picks, &listed);
    let cases = [
        ("no selection reply", Replies::default()),
        (
            "no status reply",
            Replies::default().answering("model_roles", roles(&picks)),
        ),
        (
            "no catalogue reply",
            Replies::default()
                .answering("model_roles", roles(&picks))
                .answering("status", status()),
        ),
        (
            "a selection outside the contract",
            reachable().answering("model_roles", json!({"roles": "none"})),
        ),
        (
            "a service stopping",
            reachable().answering(
                "model_roles",
                json!({"kind": "refused", "code": "service_stopping"}),
            ),
        ),
        (
            "a catalogue the service refused",
            reachable().answering(
                "catalog",
                json!({"kind": "refused", "code": "catalog_unavailable"}),
            ),
        ),
    ];
    for (name, replies) in cases {
        assert_eq!(
            admission_of(replies).local_models(),
            Err(Refusal::Unavailable),
            "{name}"
        );
    }
}

#[test]
fn a_profile_that_is_signed_out_is_told_so() {
    let signed_out = || json!({"kind": "refused", "code": "signed_out"});
    let picks = [("text_extraction", LOCAL, TEXT)];
    let cases = [
        (
            "selection",
            Replies::default().answering("model_roles", signed_out()),
        ),
        (
            "status",
            Replies::default()
                .answering("model_roles", roles(&picks))
                .answering("status", signed_out()),
        ),
        (
            "catalogue",
            Replies::selecting(&picks, &[(TEXT, Some(GB))]).answering("catalog", signed_out()),
        ),
    ];
    for (name, replies) in cases {
        assert_eq!(
            admission_of(replies).local_models(),
            Err(Refusal::NotSignedIn),
            "{name}"
        );
    }
}
