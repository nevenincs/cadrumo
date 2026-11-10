use cadrumo_application::diagnostics::{
    Diagnostics, EventKind,
    delivery_wait::delivered,
    service::{AdmissionRead, AdmissionReadOutcome, ServiceFact},
};
use serde_json::{Value, json};
use std::fs;

fn persisted(fact: ServiceFact) -> Value {
    let directory = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let diagnostics = Diagnostics::default();
    diagnostics.configure(directory.path(), 8192, 2).unwrap();
    diagnostics.service(None, fact);
    delivered(&diagnostics);
    let snapshot = diagnostics.snapshot(u64::MAX);
    let event = snapshot.events.last().unwrap();
    assert!(matches!(event.kind, EventKind::ServiceEvent));
    assert!(event.process.is_none() && event.failure.is_none());
    let log = fs::read_to_string(snapshot.paths.unwrap().current).unwrap();
    let record: Value = serde_json::from_str(log.lines().last().unwrap()).unwrap();
    record["service"].clone()
}

#[test]
fn an_admission_read_persists_only_its_closed_name_outcome_and_milliseconds() {
    let record = persisted(ServiceFact::SetupAdmissionRead {
        read: AdmissionRead::LocalModels,
        outcome: AdmissionReadOutcome::Unanswered,
        elapsed_ms: 21_000,
    });
    assert_eq!(
        record,
        json!({
            "event": "setup_admission_read",
            "read": "local_models",
            "outcome": "unanswered",
            "elapsedMs": 21_000,
        })
    );
}

#[test]
fn every_admission_read_and_outcome_has_its_own_token() {
    for (read, token) in [
        (AdmissionRead::ProviderLanes, "provider_lanes"),
        (AdmissionRead::Catalog, "catalog"),
        (AdmissionRead::LocalModels, "local_models"),
    ] {
        assert_eq!(serde_json::to_value(read).unwrap(), json!(token));
    }
    for (outcome, token) in [
        (AdmissionReadOutcome::Answered, "answered"),
        (AdmissionReadOutcome::Unanswered, "unanswered"),
        (AdmissionReadOutcome::Refused, "refused"),
        (AdmissionReadOutcome::Invalid, "invalid"),
    ] {
        assert_eq!(serde_json::to_value(outcome).unwrap(), json!(token));
    }
}

#[test]
fn an_admission_read_record_admits_no_field_beyond_its_own() {
    let fact = ServiceFact::SetupAdmissionRead {
        read: AdmissionRead::ProviderLanes,
        outcome: AdmissionReadOutcome::Answered,
        elapsed_ms: 5,
    };
    let mut forged = serde_json::to_value(fact).unwrap();
    assert_eq!(
        serde_json::from_value::<ServiceFact>(forged.clone()).unwrap(),
        fact
    );
    forged["model"] = json!("private-canary");
    assert!(serde_json::from_value::<ServiceFact>(forged).is_err());
}
