//! The native alert a launch shows when it ends before any window exists.
//!
//! The text is the person's output language from the launching environment, the same
//! variable the rest of the earliest startup reads, and the canonical default when it names
//! no carried language. A handoff to an open window shows nothing. The panel is the
//! application's own modal alert; it never reaches for another application's focus.

use crate::{environment::Parent, startup_logging::environment_value, startup_outcome::Outcome};
use cadrumo_application::error::application::ErrorCode;
use cadrumo_manager::{contract::MANAGER_LANGUAGE_ENV, strings::Strings};
use objc2_app_kit::{NSAlert, NSAlertStyle, NSApplication, NSApplicationActivationPolicy};
use objc2_foundation::{MainThreadMarker, NSString};
use std::io::IsTerminal;

/// The payload-free text the person is shown for one ended launch.
#[derive(Debug, PartialEq, Eq)]
pub struct Notice {
    pub title: String,
    pub message: String,
    pub dismiss: String,
}

/// The language the launching environment names, if any.
fn language(parent: &Parent) -> Option<String> {
    environment_value(parent, MANAGER_LANGUAGE_ENV)
        .and_then(|value| value.into_string().ok())
        .map(|value| value.trim().to_owned())
        .filter(|value| !value.is_empty())
}

/// The notice for `outcome` in `language`, or `None` when the launch shows nothing.
pub fn notice(
    language: Option<&str>,
    outcome: Outcome,
    reason: Option<ErrorCode>,
) -> Option<Notice> {
    let strings = Strings::for_language(language).ok()?;
    let (title, message) = match outcome {
        Outcome::HandedOff => return None,
        Outcome::OpenInOtherSession => (
            strings.get("startup_other_session_title").to_owned(),
            strings.get("startup_other_session_message").to_owned(),
        ),
        Outcome::TimedOut => (
            strings.get("startup_closing_title").to_owned(),
            strings.get("startup_closing_message").to_owned(),
        ),
        Outcome::Refused => (
            strings.get("startup_failed_title").to_owned(),
            format!(
                "{}: {}. {}",
                strings.get("startup_failed_reason"),
                reason.map_or_else(|| "unknown".to_owned(), token),
                strings.get("startup_failed_details")
            ),
        ),
    };
    Some(Notice {
        title,
        message,
        dismiss: strings.get("startup_dismiss").to_owned(),
    })
}

/// The protocol token of `code`.
fn token(code: ErrorCode) -> String {
    serde_json::to_value(code)
        .ok()
        .and_then(|value| value.as_str().map(str::to_owned))
        .unwrap_or_else(|| "unknown".to_owned())
}

/// Shows the notice of an ended launch, when there is one and the launch has no terminal of
/// its own. Returns whether an alert was shown.
pub fn show(parent: &Parent, outcome: Outcome, reason: Option<ErrorCode>) -> bool {
    if std::io::stderr().is_terminal() {
        return false;
    }
    let Some(notice) = notice(language(parent).as_deref(), outcome, reason) else {
        return false;
    };
    // AppKit panels belong to the main thread; elsewhere the launch keeps its error report.
    let Some(thread) = MainThreadMarker::new() else {
        return false;
    };
    let application = NSApplication::sharedApplication(thread);
    application.setActivationPolicy(NSApplicationActivationPolicy::Regular);
    let alert = NSAlert::new(thread);
    alert.setAlertStyle(NSAlertStyle::Warning);
    alert.setMessageText(&NSString::from_str(&notice.title));
    alert.setInformativeText(&NSString::from_str(&notice.message));
    alert.addButtonWithTitle(&NSString::from_str(&notice.dismiss));
    alert.runModal();
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    const LANGUAGES: [&str; 4] = ["en", "es", "ca", "hu"];

    #[test]
    fn a_handoff_shows_nothing_and_every_other_outcome_names_itself_in_every_language() {
        for language in LANGUAGES {
            assert!(notice(Some(language), Outcome::HandedOff, None).is_none());
            for (outcome, reason) in [
                (Outcome::OpenInOtherSession, None),
                (Outcome::TimedOut, Some(ErrorCode::TimedOut)),
                (Outcome::Refused, Some(ErrorCode::LogUnavailable)),
            ] {
                let shown = notice(Some(language), outcome, reason).expect("a notice");
                assert!(!shown.title.is_empty() && !shown.message.is_empty());
                assert!(!shown.dismiss.is_empty());
            }
        }
    }

    #[test]
    fn the_titles_differ_by_outcome_and_by_language() {
        let title = |language, outcome| notice(Some(language), outcome, None).unwrap().title;
        assert_ne!(
            title("en", Outcome::TimedOut),
            title("en", Outcome::OpenInOtherSession)
        );
        assert_ne!(title("en", Outcome::Refused), title("hu", Outcome::Refused));
        assert_eq!(
            title("es", Outcome::TimedOut),
            "Cadrumo todavía se está cerrando"
        );
    }

    #[test]
    fn a_refusal_carries_its_reason_token_and_never_more() {
        let shown = notice(
            Some("ca"),
            Outcome::Refused,
            Some(ErrorCode::LogUnavailable),
        )
        .unwrap();
        assert!(
            shown.message.starts_with("Motiu: log_unavailable. "),
            "{}",
            shown.message
        );
        let unknown = notice(Some("en"), Outcome::Refused, None).unwrap();
        assert!(
            unknown.message.starts_with("Reason: unknown. "),
            "{}",
            unknown.message
        );
    }

    #[test]
    fn an_absent_or_uncarried_language_falls_back_to_the_canonical_default() {
        let default = notice(None, Outcome::TimedOut, None).unwrap();
        assert_eq!(
            notice(Some("xx"), Outcome::TimedOut, None).unwrap(),
            default
        );
        let hungarian = notice(Some(" HU "), Outcome::TimedOut, None).unwrap();
        assert_eq!(
            hungarian,
            notice(Some("hu"), Outcome::TimedOut, None).unwrap()
        );
        assert_ne!(hungarian, default);
        let canonical = cadrumo_manager::contract::MANAGER_LANGUAGE_DEFAULT;
        assert_eq!(
            notice(Some(canonical), Outcome::TimedOut, None).unwrap(),
            default
        );
    }

    #[test]
    fn the_language_comes_from_the_launching_environment() {
        let parent = |value: &str| Parent {
            environment: vec![(MANAGER_LANGUAGE_ENV.into(), value.into())],
            working_directory: std::env::temp_dir(),
        };
        assert_eq!(language(&parent(" hu ")).as_deref(), Some("hu"));
        assert_eq!(language(&parent("  ")), None);
        let none = Parent {
            environment: Vec::new(),
            working_directory: std::env::temp_dir(),
        };
        assert_eq!(language(&none), None);
    }
}
