use super::{Allowed, StartReply, State, Status, allowed, start_reply};
use crate::agent::supervisor::tests::observed;
use cadrumo_application::diagnostics::service::AgentRefusal as Refusal;
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};

#[test]
fn only_a_present_sign_in_on_a_working_runtime_with_a_profile_serves() {
    assert_eq!(
        allowed(&observed(true, true, Some("A"))),
        Allowed::Serve("A".into())
    );
    for (status, refusal) in [
        // Sign-out, a lock, idle or absolute expiry: the sign-in is gone.
        (observed(false, true, Some("A")), Refusal::SignedOut),
        (observed(true, true, None), Refusal::SignedOut),
        (
            observed(true, false, Some("A")),
            Refusal::RuntimeUnavailable,
        ),
        (
            Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)),
            Refusal::RuntimeUnavailable,
        ),
        (
            Err(ApplicationError::new(
                ErrorCode::SessionUnavailable,
                Operation::Cli,
            )),
            Refusal::RuntimeUnavailable,
        ),
    ] {
        assert_eq!(allowed(&status), Allowed::Refuse(refusal));
    }
    assert_eq!(
        allowed(&Err(ApplicationError::new(
            ErrorCode::SessionUnavailable,
            Operation::Cli
        )
        .with_reason("sign_in_mutation_in_progress"))),
        Allowed::Pending
    );
    let mut refused = observed(true, true, Some("A")).unwrap();
    refused.refused = true;
    assert_eq!(
        allowed(&Ok(refused.clone())),
        Allowed::Refuse(Refusal::RuntimeUnavailable)
    );
    refused.supported = false;
    assert_eq!(
        allowed(&Ok(refused)),
        Allowed::Refuse(Refusal::ServiceAbsent)
    );
}

#[test]
fn statuses_serialize_as_the_column_reads_them() {
    let lane = Some("development");
    for (state, expected) in [
        (
            State::Stopped,
            serde_json::json!({"state": "stopped", "lane": "development"}),
        ),
        (
            State::Starting,
            serde_json::json!({"state": "starting", "lane": "development"}),
        ),
        (
            State::Ready {
                agent_version: "0.4.1".into(),
            },
            serde_json::json!({"state": "ready", "agent_version": "0.4.1", "lane": "development"}),
        ),
        (
            State::Refused {
                code: Refusal::ProviderCredentialMissing,
            },
            serde_json::json!({"state": "refused", "code": "agent_provider_credential_missing", "lane": "development"}),
        ),
    ] {
        assert_eq!(
            serde_json::to_value(Status { state, lane }).unwrap(),
            expected
        );
    }
    assert_eq!(
        serde_json::to_value(Status {
            state: State::Refused {
                code: Refusal::ServiceAbsent
            },
            lane: None
        })
        .unwrap(),
        serde_json::json!({"state": "refused", "code": "agent_service_absent"})
    );
    assert_eq!(
        Refusal::from_launcher("agent_signed_out"),
        Refusal::SignedOut
    );
}

#[test]
fn a_busy_start_is_not_a_refusal_of_the_agent() {
    use serde_json::json;
    assert_eq!(
        start_reply(&json!({"kind": "starting"})).unwrap(),
        StartReply::Starting
    );
    assert_eq!(
        start_reply(&json!({"kind": "refused", "code": "busy"})).unwrap(),
        StartReply::Busy
    );
    assert_eq!(
        start_reply(&json!({"kind": "refused", "code": "signed_out"})).unwrap(),
        StartReply::Refused(Refusal::SignedOut)
    );
    assert_eq!(
        start_reply(&json!({"kind": "refused"})).unwrap(),
        StartReply::Refused(Refusal::ServiceFailed)
    );
    for reply in [json!({}), json!({"kind": "ready"}), json!({"code": "busy"})] {
        let error = start_reply(&reply).unwrap_err();
        assert_eq!(
            error.reason.as_deref(),
            Some("agent_start_reply_unexpected")
        );
    }
}
