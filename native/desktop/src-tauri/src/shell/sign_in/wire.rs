use super::{failure, process::Output};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Result};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Debug, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Refusal {
    pub code: String,
    pub retry_after_seconds: Option<u64>,
}

#[derive(Serialize)]
#[serde(untagged)]
pub enum CommandFailure {
    Host(ApplicationError),
    Refused(Refusal),
}
impl From<ApplicationError> for CommandFailure {
    fn from(error: ApplicationError) -> Self {
        Self::Host(error)
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum Presence {
    Present,
    Absent,
    Unknown,
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct SignInStatus {
    pub supported: bool,
    pub state: Presence,
    pub active_profile: Option<String>,
    #[serde(rename = "runtimeAvailable")]
    pub runtime_available: bool,
    pub refusal: Option<Refusal>,
}
impl SignInStatus {
    pub fn runtime_ready(&self) -> bool {
        self.supported
            && self.runtime_available
            && self.refusal.is_none()
            && self.state != Presence::Unknown
    }

    pub fn unsupported() -> Self {
        Self {
            supported: false,
            state: Presence::Unknown,
            active_profile: None,
            runtime_available: false,
            refusal: None,
        }
    }
}

#[derive(Debug, Serialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum SignInResult {
    /// Public observation from the canonical persisted-login acknowledgement.
    /// It grants no runtime capability and carries no receipt or identity.
    SignedIn { status: SignInStatus },
    Refused {
        #[serde(flatten)]
        refusal: Refusal,
    },
}

#[derive(Debug, Serialize)]
pub struct Profile {
    pub name: String,
    pub active: bool,
}

/// The profiles on this computer as the product lists them. Only labels and
/// the selection cross: the product keeps identities out of what it prints.
#[derive(Debug, Serialize)]
pub struct ProfileList {
    pub profiles: Vec<Profile>,
    /// False when the product could not read its profiles coherently: its
    /// rows are then no evidence of which profiles exist.
    pub complete: bool,
}

#[derive(Debug, Serialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum ProfileCreateResult {
    Created {
        name: String,
    },
    Refused {
        #[serde(flatten)]
        refusal: Refusal,
    },
}

/// The notice a listing carries when its observation could not be trusted.
const INCOHERENT_LISTING: &str = "config.profile.list.incoherent_observation";

/// What the product reports as still standing after a sign-out.
/// `automation_enabled` is the person's persisted setting, which a sign-out
/// keeps: it is not access. `automation_access_remains` is whether an issued key
/// can still admit; null when the product could not say, because its
/// automation store was unreadable or it had no sign-in to end.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RemainingAccess {
    automation_enabled: Option<bool>,
    automation_access_remains: Option<bool>,
    automation_revoked: bool,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SignOutResult {
    pub remaining_access: RemainingAccess,
}

#[derive(Deserialize)]
struct Envelope {
    schema_version: String,
    /// Absent where the product refused before it knew its command.
    command: Option<String>,
    status: String,
    active_profile: Option<String>,
    result: Option<serde_json::Value>,
    error: Option<ErrorBody>,
}
#[derive(Deserialize)]
struct ErrorBody {
    code: String,
    context: Option<BTreeMap<String, String>>,
}

pub enum Outcome {
    Success {
        result: serde_json::Value,
        active_profile: Option<String>,
    },
    Refused {
        refusal: Refusal,
        active_profile: Option<String>,
    },
}

pub fn decode(leaf: &str, output: &Output) -> Result<Outcome> {
    let envelope: Envelope = if output.success {
        serde_json::from_slice(&output.stdout).map_err(|_| failure(ErrorCode::ReadFailed))?
    } else {
        error_envelope(&output.stderr)?
    };
    if envelope.schema_version != "2" {
        return Err(failure(ErrorCode::ReadFailed));
    }
    // An answer carries the command's own name. A refusal may carry none:
    // the product can refuse at startup, before it has read its command,
    // and its typed code is still the reason to show.
    let named = envelope.command.as_deref() == Some(format!("config.{leaf}").as_str());
    let unnamed = envelope.command.is_none();
    match envelope.status.as_str() {
        "success" | "warning" if named && output.success && envelope.error.is_none() => {
            Ok(Outcome::Success {
                result: envelope
                    .result
                    .ok_or_else(|| failure(ErrorCode::ReadFailed))?,
                active_profile: envelope.active_profile,
            })
        }
        "error" if (named || unnamed) && !output.success && envelope.result.is_none() => {
            let error = envelope
                .error
                .ok_or_else(|| failure(ErrorCode::ReadFailed))?;
            let context = error.context.unwrap_or_default();
            let code = context.get("reason").cloned().unwrap_or(error.code);
            // Only a code crosses IPC; translated error messages and arbitrary
            // CLI context never reach shell logs or the documentation bridge.
            if code.is_empty()
                || code.len() > 160
                || !code.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_')
            {
                return Err(failure(ErrorCode::ReadFailed));
            }
            // The runtime uses lower-case public reasons. Throttling carries
            // authentication_required plus the typed sign-in provenance; do
            // not infer it from an arbitrary message or a seconds field alone.
            let code = match code.as_str() {
                "credential_rejected" => "CREDENTIAL_REJECTED".into(),
                "REFUSED_PROFILE_LOGIN_THROTTLED" => "THROTTLED".into(),
                // A registration refused for its password names a reason. One
                // refused because the label is taken names none: its context
                // is that label and nothing else.
                "REFUSED_PROFILE_REGISTRATION"
                    if context.len() == 1 && context.contains_key("profile") =>
                {
                    "profile_already_exists".into()
                }
                "authentication_required"
                    if context.get("sign_in_reason").map(String::as_str) == Some("throttled") =>
                {
                    "THROTTLED".into()
                }
                _ => code,
            };
            let retry_after_seconds = if code == "THROTTLED" {
                Some(
                    context
                        .get("seconds")
                        .ok_or_else(|| failure(ErrorCode::ReadFailed))?
                        .parse()
                        .map_err(|_| failure(ErrorCode::ReadFailed))?,
                )
            } else {
                None
            };
            Ok(Outcome::Refused {
                refusal: Refusal {
                    code,
                    retry_after_seconds,
                },
                active_profile: envelope.active_profile,
            })
        }
        _ => Err(failure(ErrorCode::ReadFailed)),
    }
}

fn error_envelope(bytes: &[u8]) -> Result<Envelope> {
    if let Ok(envelope) = serde_json::from_slice(bytes) {
        return Ok(envelope);
    }
    // CLI stderr also carries startup diagnostics and operator progress. Its
    // final nonempty line is the compact error envelope; prose never crosses IPC.
    let mut lines = bytes
        .split(|byte| *byte == b'\n')
        .filter(|line| line.iter().any(|byte| !byte.is_ascii_whitespace()));
    let last = lines
        .next_back()
        .ok_or_else(|| failure(ErrorCode::ReadFailed))?;
    let envelope = serde_json::from_slice(last).map_err(|_| failure(ErrorCode::ReadFailed))?;
    if lines.any(|line| serde_json::from_slice::<Envelope>(line).is_ok()) {
        return Err(failure(ErrorCode::ReadFailed));
    }
    Ok(envelope)
}

pub fn activity(outcome: Outcome) -> std::result::Result<(), CommandFailure> {
    match outcome {
        Outcome::Refused { refusal, .. } => Err(CommandFailure::Refused(refusal)),
        Outcome::Success { result, .. } => {
            #[derive(Deserialize)]
            #[serde(deny_unknown_fields)]
            struct Activity {
                activity_recorded: bool,
            }
            let result: Activity =
                serde_json::from_value(result).map_err(|_| failure(ErrorCode::ReadFailed))?;
            if !result.activity_recorded {
                return Err(failure(ErrorCode::ReadFailed).into());
            }
            Ok(())
        }
    }
}

pub fn status(outcome: Outcome) -> Result<SignInStatus> {
    match outcome {
        Outcome::Success {
            result,
            active_profile,
        } => {
            #[derive(Deserialize)]
            struct Status {
                presence: Presence,
            }
            #[derive(Deserialize)]
            struct StatusResult {
                status: Status,
            }
            let result: StatusResult =
                serde_json::from_value(result).map_err(|_| failure(ErrorCode::ReadFailed))?;
            Ok(SignInStatus {
                supported: true,
                state: result.status.presence,
                active_profile,
                runtime_available: true,
                refusal: None,
            })
        }
        Outcome::Refused {
            refusal,
            active_profile,
        } => Ok(SignInStatus {
            supported: true,
            state: Presence::Unknown,
            active_profile,
            runtime_available: refusal.code != "runtime_unavailable",
            refusal: Some(refusal),
        }),
    }
}

pub fn login(outcome: Outcome) -> Result<SignInResult> {
    match outcome {
        Outcome::Refused { refusal, .. } => Ok(SignInResult::Refused { refusal }),
        Outcome::Success {
            result,
            active_profile,
        } => {
            #[derive(Deserialize)]
            struct Login {
                session_persisted: bool,
                active_profile: String,
            }
            let result: Login =
                serde_json::from_value(result).map_err(|_| failure(ErrorCode::ReadFailed))?;
            if result.session_persisted {
                if result.active_profile.is_empty()
                    || result.active_profile.chars().count() > super::LABEL_LIMIT
                    || active_profile
                        .as_ref()
                        .is_some_and(|label| label != &result.active_profile)
                {
                    return Err(failure(ErrorCode::ReadFailed));
                }
                Ok(SignInResult::SignedIn {
                    status: SignInStatus {
                        supported: true,
                        state: Presence::Present,
                        active_profile: Some(result.active_profile),
                        runtime_available: true,
                        refusal: None,
                    },
                })
            } else {
                Ok(SignInResult::Refused {
                    refusal: Refusal {
                        code: "session_not_persisted".into(),
                        retry_after_seconds: None,
                    },
                })
            }
        }
    }
}

/// A boolean that must be present in the document, though it may be null.
fn reported<'de, D>(deserializer: D) -> std::result::Result<Option<bool>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    Option::<bool>::deserialize(deserializer)
}

pub fn logout(outcome: Outcome) -> std::result::Result<SignOutResult, CommandFailure> {
    match outcome {
        Outcome::Refused { refusal, .. } => Err(CommandFailure::Refused(refusal)),
        Outcome::Success { result, .. } => {
            #[derive(Deserialize)]
            struct Logout {
                automation_enabled: Option<bool>,
                // The product writes every field of a result, null included. Serde
                // would read an absent key as null, which here would make a product
                // that predates the field look like one that reported nothing.
                #[serde(deserialize_with = "reported")]
                automation_access_remains: Option<bool>,
                automation_revoked: bool,
            }
            let result: Logout =
                serde_json::from_value(result).map_err(|_| failure(ErrorCode::ReadFailed))?;
            if result.automation_revoked {
                return Err(failure(ErrorCode::ReadFailed).into());
            }
            Ok(SignOutResult {
                remaining_access: RemainingAccess {
                    automation_enabled: result.automation_enabled,
                    automation_access_remains: result.automation_access_remains,
                    automation_revoked: false,
                },
            })
        }
    }
}

pub fn profiles(output: &Output) -> std::result::Result<ProfileList, CommandFailure> {
    match decode("profile.list", output)? {
        Outcome::Refused { refusal, .. } => Err(CommandFailure::Refused(refusal)),
        Outcome::Success { result, .. } => {
            #[derive(Deserialize)]
            struct Row {
                name: String,
                active: bool,
            }
            #[derive(Deserialize)]
            struct Listing {
                profiles: Vec<Row>,
            }
            #[derive(Deserialize)]
            struct Notice {
                code: String,
            }
            #[derive(Deserialize)]
            struct Notices {
                #[serde(default)]
                notices: Vec<Notice>,
            }
            let listing: Listing =
                serde_json::from_value(result).map_err(|_| failure(ErrorCode::ReadFailed))?;
            let said: Notices = serde_json::from_slice(&output.stdout)
                .map_err(|_| failure(ErrorCode::ReadFailed))?;
            // A label is never empty, and at most one profile is selected.
            if listing.profiles.iter().any(|row| row.name.is_empty())
                || listing.profiles.iter().filter(|row| row.active).count() > 1
            {
                return Err(failure(ErrorCode::ReadFailed).into());
            }
            Ok(ProfileList {
                profiles: listing
                    .profiles
                    .into_iter()
                    .map(|row| Profile {
                        name: row.name,
                        active: row.active,
                    })
                    .collect(),
                complete: !said
                    .notices
                    .iter()
                    .any(|notice| notice.code == INCOHERENT_LISTING),
            })
        }
    }
}

pub fn created(outcome: Outcome) -> Result<ProfileCreateResult> {
    match outcome {
        Outcome::Refused { refusal, .. } => Ok(ProfileCreateResult::Refused { refusal }),
        Outcome::Success { result, .. } => {
            #[derive(Deserialize)]
            struct Created {
                profile_name: String,
                status: String,
            }
            let result: Created =
                serde_json::from_value(result).map_err(|_| failure(ErrorCode::ReadFailed))?;
            // Anything but a profile that was created is not a creation.
            if result.status != "created" || result.profile_name.is_empty() {
                return Err(failure(ErrorCode::ReadFailed));
            }
            Ok(ProfileCreateResult::Created {
                name: result.profile_name,
            })
        }
    }
}

#[cfg(test)]
#[path = "wire_contract_tests.rs"]
mod contract_tests;

#[cfg(test)]
mod tests {
    use super::*;
    use zeroize::Zeroizing;

    fn output(success: bool, document: serde_json::Value) -> Output {
        let bytes = Zeroizing::new(serde_json::to_vec(&document).unwrap());
        let empty = Zeroizing::new(Vec::new());
        let (stdout, stderr) = if success {
            (bytes, empty)
        } else {
            (empty, bytes)
        };
        Output {
            success,
            stdout,
            stderr,
        }
    }

    #[test]
    fn canonical_stderr_refusals_preserve_codes_and_throttle_seconds() {
        for code in [
            "CREDENTIAL_REJECTED",
            "THROTTLED",
            "PROFILE_LOCKED",
            "runtime_unavailable",
        ] {
            let output = output(
                false,
                serde_json::json!({"schema_version":"2","command":"config.login","status":"error","active_profile":"Profile", "error":{"code":"REFUSED_CLI","context":{"reason":code,"seconds":"9"}}}),
            );
            let SignInResult::Refused { refusal } =
                login(decode("login", &output).unwrap()).unwrap()
            else {
                panic!("refusal expected")
            };
            assert_eq!(refusal.code, code);
            assert_eq!(
                refusal.retry_after_seconds,
                if code == "THROTTLED" { Some(9) } else { None }
            );
        }
    }

    #[test]
    fn status_uses_outer_active_profile_and_preserves_unknown() {
        let output = output(
            true,
            serde_json::json!({"schema_version":"2","command":"config.sign-in-status","status":"success","active_profile":"My profile", "result":{"profile_id":"id","status":{"presence":"unknown"}}}),
        );
        let status = status(decode("sign-in-status", &output).unwrap()).unwrap();
        assert_eq!(status.state, Presence::Unknown);
        assert_eq!(status.active_profile.as_deref(), Some("My profile"));
        assert!(status.runtime_available);
        assert!(!status.runtime_ready());
    }

    #[test]
    fn runtime_unavailable_does_not_become_absent() {
        let status = status(Outcome::Refused {
            refusal: Refusal {
                code: "runtime_unavailable".into(),
                retry_after_seconds: None,
            },
            active_profile: None,
        })
        .unwrap();
        assert_eq!(status.state, Presence::Unknown);
        assert!(!status.runtime_available);
        assert!(!status.runtime_ready());
    }

    #[test]
    fn runtime_readiness_requires_a_successful_settled_status_not_an_error_envelope() {
        for presence in ["present", "absent"] {
            let observed = status(Outcome::Success {
                result: serde_json::json!({"status":{"presence":presence}}),
                active_profile: None,
            })
            .unwrap();
            assert!(observed.runtime_ready());
        }
        let observed = status(Outcome::Refused {
            refusal: Refusal {
                code: "protocol_mismatch".into(),
                retry_after_seconds: None,
            },
            active_profile: None,
        })
        .unwrap();
        assert!(observed.runtime_available);
        assert!(!observed.runtime_ready());
    }

    #[test]
    fn a_refusal_that_names_no_command_keeps_its_code_and_an_answer_must_name_its_own() {
        let startup = serde_json::json!({"schema_version":"2","command":null,"status":"error","active_profile":null,"error":{"code":"ERROR_CALCULATIONS_REGISTRY_AUTHORITY_DESCRIPTOR_UNAVAILABLE","context":null}});
        let Outcome::Refused { refusal, .. } =
            decode("sign-in-status", &output(false, startup)).unwrap()
        else {
            panic!("refusal expected")
        };
        assert_eq!(
            refusal.code,
            "ERROR_CALCULATIONS_REGISTRY_AUTHORITY_DESCRIPTOR_UNAVAILABLE"
        );
        for (success, document) in [
            // An answer with no name, and a refusal with another command's.
            (
                true,
                serde_json::json!({"schema_version":"2","command":null,"status":"success","result":{"session_persisted":true}}),
            ),
            (
                false,
                serde_json::json!({"schema_version":"2","command":"config.logout","status":"error","error":{"code":"REFUSED_CLI","context":null}}),
            ),
        ] {
            assert!(decode("login", &output(success, document)).is_err());
        }
    }

    #[test]
    fn envelopes_require_version_command_exit_status_and_payload() {
        for document in [
            serde_json::json!({"schema_version":"1","command":"config.login","status":"success","result":{"session_persisted":true}}),
            serde_json::json!({"schema_version":"2","command":"config.logout","status":"success","result":{"session_persisted":true}}),
            serde_json::json!({"schema_version":"2","command":"config.login","status":"error","result":{"session_persisted":true}}),
            serde_json::json!({"schema_version":"2","command":"config.login","status":"success"}),
        ] {
            assert!(decode("login", &output(true, document)).is_err());
        }
    }

    #[test]
    fn login_requires_a_persisted_sign_in_and_logout_keeps_automation_unknown() {
        let signed_in = login(Outcome::Success {
            result: serde_json::json!({"session_persisted":true,"active_profile":"Profile"}),
            active_profile: None,
        })
        .unwrap();
        assert!(matches!(signed_in, SignInResult::SignedIn { .. }));
        let refused = login(Outcome::Success {
            result: serde_json::json!({"session_persisted":false,"active_profile":"Profile"}),
            active_profile: None,
        })
        .unwrap();
        assert!(matches!(refused, SignInResult::Refused { .. }));
        let signed_out = logout(Outcome::Success {
            result: serde_json::json!({"automation_enabled":null,"automation_access_remains":null,"automation_revoked":false}),
            active_profile: None,
        })
        .ok()
        .unwrap();
        assert_eq!(
            serde_json::to_value(signed_out).unwrap(),
            serde_json::json!({"remainingAccess":{"automationEnabled":null,"automationAccessRemains":null,"automationRevoked":false}})
        );
    }

    fn logout_with(fields: serde_json::Value) -> Option<serde_json::Value> {
        logout(Outcome::Success {
            result: fields,
            active_profile: None,
        })
        .ok()
        .map(|result| serde_json::to_value(result).unwrap())
    }

    #[test]
    fn logout_reports_whether_an_issued_key_can_still_admit_and_never_guesses_it() {
        // The setting a sign-out keeps and the access it leaves are separate
        // facts: a key may stay configured while admitting nothing, and the
        // other way round.
        for (enabled, remains) in [(true, true), (true, false), (false, true), (false, false)] {
            assert_eq!(
                logout_with(serde_json::json!({
                    "automation_enabled": enabled,
                    "automation_access_remains": remains,
                    "automation_revoked": false
                })),
                Some(serde_json::json!({"remainingAccess":{
                    "automationEnabled": enabled,
                    "automationAccessRemains": remains,
                    "automationRevoked": false
                }}))
            );
        }
        // Null is the product saying it could not tell. It stays null.
        assert_eq!(
            logout_with(serde_json::json!({
                "automation_enabled": null,
                "automation_access_remains": null,
                "automation_revoked": false
            })),
            Some(serde_json::json!({"remainingAccess":{
                "automationEnabled": null,
                "automationAccessRemains": null,
                "automationRevoked": false
            }}))
        );
        // A result without the field is a product that does not know the question,
        // not one that answered no. It is refused, as is any value that is not a
        // boolean or null.
        assert_eq!(
            logout_with(serde_json::json!({
                "automation_enabled": true,
                "automation_revoked": false
            })),
            None
        );
        for value in [
            serde_json::json!("false"),
            serde_json::json!(0),
            serde_json::json!(1),
            serde_json::json!([]),
        ] {
            assert_eq!(
                logout_with(serde_json::json!({
                    "automation_enabled": true,
                    "automation_access_remains": value,
                    "automation_revoked": false
                })),
                None
            );
        }
    }
}
