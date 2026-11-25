//! What reaches diagnostics when the window is told only a code, and when it does not.
use super::{super::wire::Refusal, *};
use cadrumo_application::error::application::{ChildRefusal, ErrorCode, Operation};

fn reports() -> (Reports, Arc<Diagnostics>) {
    let diagnostics = Arc::new(Diagnostics::default());
    (Reports::new(diagnostics.clone()), diagnostics)
}

fn recorded(diagnostics: &Diagnostics) -> Vec<ApplicationError> {
    diagnostics
        .snapshot(u64::MAX)
        .events
        .into_iter()
        .filter_map(|event| event.failure)
        .collect()
}

fn reasons(diagnostics: &Diagnostics) -> Vec<Option<String>> {
    recorded(diagnostics)
        .iter()
        .map(|error| error.reason.as_deref().map(str::to_owned))
        .collect()
}

fn refused_with(code: &str) -> Stop {
    Stop::unavailable("setup_google_relay_refused").because(ChildRefusal {
        code: Some(code.into()),
        ..ChildRefusal::default()
    })
}

fn host(reason: &'static str) -> Stop {
    Stop::Host(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli).with_reason(reason))
}

#[test]
fn every_failed_command_records_its_cause_and_a_refusal_the_person_can_act_on_records_none() {
    let (reports, diagnostics) = reports();
    reports.command(&Stop::unavailable("setup_runtime_not_ready"));
    reports.command(&Stop::unavailable("setup_runtime_not_ready"));
    reports.command(&host("setup_session_changed"));
    reports.command(&Stop::from(Refusal::NotSignedIn));
    reports.command(&Stop::from(Refusal::PlanChanged));
    assert_eq!(
        reasons(&diagnostics),
        [
            Some("setup_runtime_not_ready".into()),
            Some("setup_runtime_not_ready".into()),
            Some("setup_session_changed".into()),
        ],
        "each command is news to the person who asked, and a refusal is not a failure"
    );
    let recorded = recorded(&diagnostics);
    assert_eq!(recorded[0].code, ErrorCode::SessionUnavailable);
    assert_eq!(recorded[2].code, ErrorCode::ReadFailed);
}

#[test]
fn a_read_that_fails_the_same_way_on_every_cue_records_once() {
    let (reports, diagnostics) = reports();
    for _ in 0..5 {
        reports.read(&Stop::unavailable("setup_runtime_not_ready"));
    }
    assert_eq!(
        reasons(&diagnostics),
        [Some("setup_runtime_not_ready".into())]
    );
}

#[test]
fn a_read_records_again_when_its_cause_changes_even_under_one_reason() {
    let (reports, diagnostics) = reports();
    reports.read(&Stop::unavailable("setup_runtime_not_ready"));
    reports.read(&host("setup_session_changed"));
    reports.read(&refused_with("service_stopping"));
    reports.read(&refused_with("service_stopping"));
    reports.read(&refused_with("catalog_unavailable"));
    reports.read(&Stop::unavailable("setup_runtime_not_ready"));
    assert_eq!(
        reasons(&diagnostics),
        [
            Some("setup_runtime_not_ready".into()),
            Some("setup_session_changed".into()),
            Some("setup_google_relay_refused".into()),
            Some("setup_google_relay_refused".into()),
            Some("setup_runtime_not_ready".into()),
        ]
    );
}

#[test]
fn a_read_that_got_through_makes_the_next_identical_failure_news_again() {
    let (reports, diagnostics) = reports();
    reports.read(&Stop::unavailable("setup_runtime_not_ready"));
    reports.recovered();
    reports.read(&Stop::unavailable("setup_runtime_not_ready"));
    assert_eq!(recorded(&diagnostics).len(), 2);
}

#[test]
fn a_failed_command_keeps_the_read_that_fails_alike_after_it_quiet() {
    let (reports, diagnostics) = reports();
    reports.command(&Stop::unavailable("setup_runtime_not_ready"));
    reports.read(&Stop::unavailable("setup_runtime_not_ready"));
    assert_eq!(recorded(&diagnostics).len(), 1);
}

#[test]
fn a_refusal_the_person_can_act_on_neither_records_nor_ends_a_run_of_failed_reads() {
    let (reports, diagnostics) = reports();
    reports.read(&Stop::unavailable("setup_runtime_not_ready"));
    reports.read(&Stop::from(Refusal::NotSignedIn));
    reports.read(&Stop::unavailable("setup_runtime_not_ready"));
    assert_eq!(recorded(&diagnostics).len(), 1);
}

#[test]
fn a_failure_of_the_host_itself_is_recorded_as_it_is() {
    let (reports, diagnostics) = reports();
    let error = ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
        .with_reason("setup_host_closed");
    reports.error(&error);
    let [kept] = &recorded(&diagnostics)[..] else {
        panic!("one failure");
    };
    assert_eq!(
        (kept.code, kept.reason.as_deref()),
        (ErrorCode::SessionUnavailable, Some("setup_host_closed"))
    );
}

#[test]
fn a_read_or_command_the_closing_window_refused_itself_records_nothing() {
    let (reports, diagnostics) = reports();
    let closing = || {
        Stop::Host(
            ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                .with_reason(cadrumo_application::shutdown::HOST_CLOSING),
        )
    };
    reports.read(&closing());
    reports.command(&closing());
    assert!(recorded(&diagnostics).is_empty());
    // A failure that is not the close's own still records.
    reports.read(&host("setup_session_changed"));
    assert_eq!(
        reasons(&diagnostics),
        [Some("setup_session_changed".into())]
    );
}
