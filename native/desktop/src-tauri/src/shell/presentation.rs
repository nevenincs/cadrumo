//! Opens a page of the person's own TUI. The held person session asks the
//! runtime, which passes the page to that person's signed-in TUIs on the
//! same profile; the TUI admits the page itself, as it would a keystroke.
//! Nothing here grants access to anything: a page is only where to look.
use super::sign_in::{Presence, SignIn};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::Serialize;
use serde_json::json;
use std::sync::{Arc, Mutex};
use tauri::State;

/// The pages a link may name, as the runtime's closed vocabulary spells them.
pub(crate) const DESTINATIONS: [&str; 11] = [
    "home",
    "ledger",
    "withholding",
    "declarations",
    "aeat_sync",
    "operations",
    "installation",
    "setup",
    "reference",
    "profile",
    "aeat_auth",
];

fn admitted(profile_id: &str, destination: &str) -> bool {
    crate::shell::agent_access::wire::is_uuid(profile_id)
        && profile_id == profile_id.to_ascii_lowercase()
        && profile_id != "00000000-0000-0000-0000-000000000000"
        && DESTINATIONS.contains(&destination)
}

/// What became of a request to open a page.
#[derive(Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "outcome", rename_all = "snake_case")]
pub enum Outcome {
    /// The runtime passed the page to this many TUIs; none is zero.
    Presented { delivered: u64 },
    /// Nobody is signed in here, so no session can carry the request.
    SignedOut,
    /// The link names a profile other than the one signed in here.
    OtherProfile,
}

fn lock<T>(value: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    value.lock().unwrap_or_else(|error| error.into_inner())
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![desktop_present_destination]
}

#[tauri::command]
async fn desktop_present_destination(
    state: State<'_, Arc<SignIn>>,
    profile_id: String,
    destination: String,
) -> Result<Outcome> {
    if !admitted(&profile_id, &destination) {
        return Err(ApplicationError::new(
            ErrorCode::InvalidArguments,
            Operation::Cli,
        ));
    }
    let sign_in = state.inner().clone();
    let status = sign_in.read_status().await?;
    if status.state != Presence::Present || !status.runtime_ready() {
        return Ok(Outcome::SignedOut);
    }
    let Some(label) = status.active_profile else {
        return Ok(Outcome::SignedOut);
    };
    super::blocking(move || {
        // The window knows its profile by label; only the host can tell
        // whether the link's identity is that profile's.
        let active = sign_in.profile_id(&label)?;
        if active != profile_id {
            return Ok(Outcome::OtherProfile);
        }
        let person = sign_in.person(&active)?;
        let reply = lock(&person)
            .exchange(json!({"action": "present_destination", "destination": destination}))?;
        Ok(Outcome::Presented {
            delivered: reply["delivered"].as_u64().unwrap_or(0),
        })
    })
    .await
}

#[cfg(test)]
mod tests {
    use super::*;

    const PROFILE: &str = "5aa00000-0000-4000-8000-0000000000aa";

    #[test]
    fn only_an_exact_profile_and_a_closed_page_are_admitted() {
        for destination in DESTINATIONS {
            assert!(admitted(PROFILE, destination));
        }
        for (profile, destination) in [
            (PROFILE, "aeat-auth"),
            (PROFILE, "Ledger"),
            (PROFILE, ""),
            (PROFILE, "ledger?x=1"),
            ("5AA00000-0000-4000-8000-0000000000AA", "ledger"),
            ("00000000-0000-0000-0000-000000000000", "ledger"),
            ("../profile", "ledger"),
            ("", "ledger"),
        ] {
            assert!(!admitted(profile, destination), "{profile} {destination}");
        }
    }

    #[test]
    fn outcomes_serialize_as_the_window_reads_them() {
        assert_eq!(
            serde_json::to_value(Outcome::Presented { delivered: 2 }).unwrap(),
            json!({"outcome":"presented","delivered":2})
        );
        assert_eq!(
            serde_json::to_value(Outcome::SignedOut).unwrap(),
            json!({"outcome":"signed_out"})
        );
        assert_eq!(
            serde_json::to_value(Outcome::OtherProfile).unwrap(),
            json!({"outcome":"other_profile"})
        );
    }
}
