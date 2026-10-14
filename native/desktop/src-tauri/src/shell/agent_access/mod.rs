//! The keys the signed-in profile has issued to agents outside Cadrumo, as
//! short-lived canonical CLI invocations of the sign-in view's own channel:
//! the digest-verified runtime image, its projected environment, its lanes, deadline
//! and output bound.
//!
//! Listing and revoking are the person's own acts, and the product refuses
//! them to an agent. Neither takes a password, an argument that is not a
//! fixed word or a UUID this module checked, or an environment of its own;
//! no answer carries a key. Revoking is a mutation on the one mutation lane
//! the sign-in view owns, so it never runs beside another and is never
//! retried.
//!
//! Issuing a key is not offered yet: the product does not yet have the form
//! of it that one act of the person can complete, and the host will not
//! stand in for the person's approval with a second process.
pub(crate) mod wire;

use crate::shell::sign_in::{
    SignIn,
    process::Children,
    wire::{self as envelope, Outcome},
};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::{process::Command, sync::Arc};
use tauri::State;
use wire::{Answer, CommandFailure, Refusal, Revoked};

const LIST_LEAF: &str = "profile.automation.list";
const DENY_LEAF: &str = "profile.automation.deny";

/// The arguments of a listing: every word is fixed.
fn list_arguments() -> Vec<String> {
    [
        "--format",
        "json",
        "config",
        "profile",
        "automation",
        "list",
    ]
    .iter()
    .map(|word| (*word).to_owned())
    .collect()
}

/// The arguments of a revoke of one grant, which the product revokes with
/// its keys. The grant is a UUID that was checked, so it is neither an option
/// nor anything the command line rewrites.
fn revoke_arguments(grant: &str) -> Vec<String> {
    [
        "--format",
        "json",
        "config",
        "profile",
        "automation",
        "deny",
        "grant",
        grant,
    ]
    .iter()
    .map(|word| (*word).to_owned())
    .collect()
}

/// A grant a revoke may name, as the product prints it.
fn admitted_grant(text: &str) -> std::result::Result<String, CommandFailure> {
    if wire::is_uuid(text) {
        Ok(text.to_ascii_lowercase())
    } else {
        Err(ApplicationError::new(ErrorCode::InvalidArguments, Operation::Cli).into())
    }
}

/// What a failure of the host itself, once a revoke may have reached the
/// product, tells of the revoke. A call refused before a child existed is
/// plainly not made; any other failure is an outcome the host did not hear.
fn after_revoke(error: ApplicationError) -> CommandFailure {
    match error.code {
        ErrorCode::CliBusy
        | ErrorCode::SpawnFailed
        | ErrorCode::PackageUnavailable
        | ErrorCode::EnvironmentFailed
        | ErrorCode::InvalidArguments
        | ErrorCode::UnsupportedPlatform => error.into(),
        _ => Refusal::OutcomeUnknown.into(),
    }
}

/// Runs a built listing on the read lane and decodes the one envelope it
/// prints. The child is settled on every path.
fn read_list(children: &Children, command: Command) -> std::result::Result<Answer, CommandFailure> {
    let output = children.read(command)?;
    wire::list(envelope::decode(LIST_LEAF, &output)?)
}

/// Runs a built revoke on the mutation lane. Nothing is written to the
/// child's input, and the revoke is attempted once.
fn run_revoke(
    children: &Children,
    command: Command,
    grant: &str,
) -> std::result::Result<Revoked, CommandFailure> {
    let outcome: Outcome = children
        .run(command, None)
        .and_then(|output| envelope::decode(DENY_LEAF, &output))
        .map_err(after_revoke)?;
    wire::revoked(outcome, grant)
}

fn command_of(sign_in: &SignIn, arguments: Vec<String>) -> Result<Command> {
    let mut command = sign_in.runtime()?.command();
    command.args(arguments);
    Ok(command)
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![agent_access_list, agent_access_issue, agent_access_revoke]
}

/// Every key of the signed-in profile, ended ones included: each grant's
/// standing, what it releases and when it last let an agent in. Reading
/// changes nothing.
#[tauri::command]
pub async fn agent_access_list(
    state: State<'_, Arc<SignIn>>,
) -> std::result::Result<Answer, CommandFailure> {
    let state = state.inner().clone();
    super::blocking(move || {
        let command = command_of(&state, list_arguments())?;
        Ok(read_list(&state.children, command))
    })
    .await?
}

/// Issuing a key is refused until the product offers it as one act of the
/// person's. The choice is admitted as the window made it; nothing is run.
#[tauri::command]
pub async fn agent_access_issue(tax_values: bool) -> std::result::Result<(), CommandFailure> {
    let _admitted: bool = tax_values;
    Err(Refusal::IssueUnavailable.into())
}

/// Revokes one grant, and so its keys. It answers once access is denied;
/// `cleanup_pending` says the stored key is still to be removed from this
/// computer. One attempt: nothing is retried, whatever the outcome.
#[tauri::command]
pub async fn agent_access_revoke(
    state: State<'_, Arc<SignIn>>,
    grant_id: String,
) -> std::result::Result<Revoked, CommandFailure> {
    let grant = admitted_grant(&grant_id)?;
    let state = state.inner().clone();
    super::blocking(move || {
        let command = command_of(&state, revoke_arguments(&grant))?;
        Ok(run_revoke(&state.children, command, &grant))
    })
    .await?
}

#[cfg(test)]
mod tests {
    use super::*;

    const GRANT: &str = "6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5b";

    fn refused(failure: CommandFailure) -> serde_json::Value {
        serde_json::to_value(failure).unwrap()
    }

    #[test]
    fn each_call_is_the_contracts_command_line_with_no_secret_channel() {
        assert_eq!(
            list_arguments(),
            [
                "--format",
                "json",
                "config",
                "profile",
                "automation",
                "list"
            ]
        );
        assert_eq!(
            revoke_arguments(GRANT),
            [
                "--format",
                "json",
                "config",
                "profile",
                "automation",
                "deny",
                "grant",
                GRANT
            ]
        );
        // Nothing is read from standard input: no call asks for a channel.
        for word in list_arguments().iter().chain(&revoke_arguments(GRANT)) {
            assert!(
                !word.contains("secrets") && !word.contains("password"),
                "{word}"
            );
        }
    }

    #[test]
    fn a_revoke_names_a_uuid_the_command_line_reads_as_itself() {
        assert_eq!(admitted_grant(GRANT).unwrap(), GRANT);
        assert_eq!(admitted_grant(&GRANT.to_uppercase()).unwrap(), GRANT);
        for bad in [
            "",
            "all",
            "--help",
            "-6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5",
            "6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5b extra",
            "6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5*",
            "%25USERNAME%25",
        ] {
            assert_eq!(
                refused(admitted_grant(bad).unwrap_err())["code"],
                "invalid_arguments",
                "{bad:?}"
            );
        }
    }

    #[test]
    fn a_host_failure_after_a_revoke_may_have_run_is_an_outcome_unheard() {
        for code in [
            ErrorCode::TimedOut,
            ErrorCode::OutputLimit,
            ErrorCode::ReadFailed,
            ErrorCode::CleanupFailed,
            ErrorCode::WriteFailed,
            ErrorCode::SessionUnavailable,
            ErrorCode::Panic,
        ] {
            assert_eq!(
                refused(after_revoke(ApplicationError::new(code, Operation::Cli))),
                serde_json::json!({"code": "outcome_unknown"}),
                "{code:?}"
            );
        }
        // Refused before any child existed: plainly not made.
        for code in [
            ErrorCode::CliBusy,
            ErrorCode::SpawnFailed,
            ErrorCode::PackageUnavailable,
            ErrorCode::EnvironmentFailed,
        ] {
            let sent = refused(after_revoke(ApplicationError::new(code, Operation::Cli)));
            assert_ne!(sent["code"], "outcome_unknown");
            assert_eq!(sent["operation"], "cli");
        }
    }

    #[tokio::test]
    async fn issuing_is_refused_as_unavailable_whatever_the_choice() {
        for tax_values in [false, true] {
            let failure = agent_access_issue(tax_values).await.unwrap_err();
            assert_eq!(
                refused(failure),
                serde_json::json!({"code": "issue_unavailable"})
            );
        }
    }

    #[cfg(windows)]
    fn powershell(script: &str) -> Command {
        let root = std::env::var_os("SystemRoot").unwrap();
        let mut command = Command::new(
            std::path::Path::new(&root).join("System32/WindowsPowerShell/v1.0/powershell.exe"),
        );
        command.args([
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ]);
        command
    }

    #[cfg(windows)]
    const LISTING: &str = "[Console]::Out.Write('{\"schema_version\":\"2\",\"command\":\"config.profile.automation.list\",\"status\":\"success\",\"result\":{\"profile_id\":\"0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d\",\"operation_id\":\"op\",\"inventory\":{\"grants\":[{\"grant_id\":\"6f1b0c1e-2a3d-4e5f-8a9b-0c1d2e3f4a5b\",\"state\":\"active\",\"scope\":{\"all_agent_operations\":false,\"disclosure_categories\":[{\"category\":\"tax_values\"}]},\"valid_from\":\"2026-10-13T09:30:00Z\",\"expires_at\":\"2027-10-13T09:30:00Z\"}],\"keys\":[],\"requests\":[]}}}')";

    // A real child: what it prints is read through the same decoder as the
    // product's own answer, on the lane the product's call would use.
    #[cfg(windows)]
    #[test]
    fn a_listing_read_through_a_real_child_parses_the_envelope() {
        let children = Children::default();
        let answer = read_list(&children, powershell(LISTING)).unwrap();
        assert_eq!(answer.credentials.len(), 1);
        assert_eq!(answer.credentials[0].id, GRANT);
        assert_eq!(answer.credentials[0].last_used_at, None);
    }

    #[cfg(windows)]
    #[test]
    fn a_revoke_through_a_real_child_is_read_and_the_child_gets_no_input() {
        let children = Children::default();
        // The child reports whether its input was the null device: it reads
        // nothing and so finds the end of input at once.
        let answered = |cleanup: &str| {
            format!(
                "$in=[Console]::In.ReadToEnd(); $pending='{cleanup}'; \
                 if ($in.Length -ne 0) {{ exit 3 }}; \
                 [Console]::Out.Write('{{\"schema_version\":\"2\",\"command\":\"config.profile.automation.deny\",\"status\":\"success\",\"result\":{{\"profile_id\":\"0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d\",\"kind\":\"grant\",\"target_id\":\"{GRANT}\",\"receipt\":{{\"access_denied\":true,\"cleanup_pending\":'+$pending+'}}}}}}')"
            )
        };
        for (cleanup, pending) in [("true", true), ("false", false)] {
            let revoked = run_revoke(&children, powershell(&answered(cleanup)), GRANT).unwrap();
            assert_eq!(revoked.cleanup_pending, pending);
        }
    }

    #[cfg(windows)]
    #[test]
    fn a_revoke_whose_answer_names_another_grant_or_is_no_envelope_is_an_outcome_unheard() {
        let children = Children::default();
        for script in [
            "[Console]::Out.Write('{\"schema_version\":\"2\",\"command\":\"config.profile.automation.list\",\"status\":\"success\",\"result\":{}}')",
            "[Console]::Out.Write('not json')",
            "[Console]::Out.Write('')",
            "[Console]::Out.Write('{\"schema_version\":\"2\",\"command\":\"config.profile.automation.deny\",\"status\":\"success\",\"result\":{\"kind\":\"grant\",\"target_id\":\"0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d\",\"receipt\":{\"access_denied\":true,\"cleanup_pending\":false}}}')",
        ] {
            let failure = run_revoke(&children, powershell(script), GRANT).unwrap_err();
            assert_eq!(
                refused(failure),
                serde_json::json!({"code": "outcome_unknown"}),
                "{script}"
            );
        }
    }

    #[cfg(windows)]
    #[test]
    fn a_refusal_envelope_from_a_real_child_keeps_its_meaning() {
        let children = Children::default();
        let envelope = "[Console]::Error.Write('{\"schema_version\":\"2\",\"status\":\"error\",\"error\":{\"code\":\"REFUSED_CLI_BOUNDARY\",\"context\":{\"reason\":\"profile_locked\"}}}'); exit 1";
        assert_eq!(
            refused(run_revoke(&children, powershell(envelope), GRANT).unwrap_err()),
            serde_json::json!({"code": "profile_locked"})
        );
        assert_eq!(
            refused(read_list(&children, powershell(envelope)).unwrap_err()),
            serde_json::json!({"code": "profile_locked"})
        );
    }

    #[cfg(windows)]
    #[test]
    fn a_child_that_floods_its_output_is_bounded_and_reaped() {
        let children = Children::default();
        let flood = "while ($true) { [Console]::Out.Write(('x' * 8192)) }";
        let listing = read_list(&children, powershell(flood)).unwrap_err();
        assert_eq!(refused(listing)["code"], "output_limit");
        // A revoke that may have run is not reported as a failure to run.
        let revoke = run_revoke(&children, powershell(flood), GRANT).unwrap_err();
        assert_eq!(
            refused(revoke),
            serde_json::json!({"code": "outcome_unknown"})
        );
    }
}
