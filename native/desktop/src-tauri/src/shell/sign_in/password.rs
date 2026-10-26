//! The signed-in profile's password change, relayed to the runtime's canonical
//! command line. The passwords pass through, on the helper's standard input
//! only; nothing here keeps or reads them.
use super::{Call, SignIn, failure, supported, wire};
use cadrumo_application::error::application::{ErrorCode, Result};
use serde::{
    Deserialize, Deserializer,
    de::{self, Visitor},
};
use std::sync::Arc;
use tauri::{
    State,
    ipc::{InvokeBody, Request},
};
use zeroize::Zeroizing;

const CHANGE: Call = Call {
    words: &["passphrase", "change"],
    leaf: "passphrase.change",
    command: "config.passphrase.change",
    reads: false,
    runtime: true,
    // The current password is proven and the new one derived: both run the
    // product's key derivation.
    slow: true,
};

/// Three passwords, each JSON-escaped, within the product's own bounds.
const BODY_LIMIT: usize = 16 * 1024;

/// A password field: present, a string, and not empty. Its text is checked
/// where the parser holds it and never copied out.
struct Secret;
impl<'de> Deserialize<'de> for Secret {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> std::result::Result<Self, D::Error> {
        struct Text;
        impl Visitor<'_> for Text {
            type Value = Secret;
            fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
                formatter.write_str("a password")
            }
            fn visit_str<E: de::Error>(self, value: &str) -> std::result::Result<Secret, E> {
                if value.is_empty() {
                    Err(E::custom("empty password"))
                } else {
                    Ok(Secret)
                }
            }
        }
        deserializer.deserialize_str(Text)
    }
}

/// The exact secret document `config passphrase change --secrets-stdin` reads.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Rotation {
    #[serde(rename = "current_passphrase")]
    _current: Secret,
    #[serde(rename = "new_passphrase")]
    _new: Secret,
    #[serde(rename = "new_passphrase_confirmation")]
    _confirmation: Secret,
}

fn rotation(body: &InvokeBody) -> Result<Zeroizing<Vec<u8>>> {
    let InvokeBody::Raw(bytes) = body else {
        return Err(failure(ErrorCode::InvalidArguments));
    };
    rotation_bytes(bytes)
}

fn rotation_bytes(bytes: &[u8]) -> Result<Zeroizing<Vec<u8>>> {
    // A derived struct also reads an array of its fields: only an object is
    // the document the command line reads.
    if bytes.len() > BODY_LIMIT || bytes.trim_ascii_start().first() != Some(&b'{') {
        return Err(failure(ErrorCode::InvalidArguments));
    }
    serde_json::from_slice::<Rotation>(bytes).map_err(|_| failure(ErrorCode::InvalidArguments))?;
    Ok(Zeroizing::new(bytes.to_vec()))
}

/// Changes the signed-in profile's password, with the current password, the
/// new one and its confirmation as one JSON object in the raw body. One
/// attempt: nothing is retried, and an outcome the product did not confirm
/// is answered as unknown.
#[tauri::command]
pub async fn profile_password_change(
    state: State<'_, Arc<SignIn>>,
    request: Request<'_>,
) -> std::result::Result<wire::PasswordChangeResult, wire::CommandFailure> {
    if !supported() {
        return Err(failure(ErrorCode::UnsupportedPlatform).into());
    }
    let secret = rotation(request.body())?;
    let state = state.inner().clone();
    super::super::blocking(move || {
        // The command line changes the selected profile's password: only while
        // the window has that profile signed in.
        if state.watch.latest()?.status.state != wire::Presence::Present {
            return Ok(Err(wire::CommandFailure::Refused(wire::Refusal {
                code: "not_signed_in".into(),
                retry_after_seconds: None,
            })));
        }
        Ok(Ok(wire::password_changed(&state.output(
            &CHANGE,
            None,
            Some(secret),
        )?)?))
    })
    .await?
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_the_exact_rotation_document_passes_to_the_command_line() {
        let valid = br#"{"current_passphrase":"old \"one\"","new_passphrase":"n\u00e9w","new_passphrase_confirmation":"n\u00e9w"}"#;
        assert_eq!(&*rotation_bytes(valid).unwrap(), valid);
        for invalid in [
            &br#"{"current_passphrase":"a","new_passphrase":"b"}"#[..],
            br#"{"current_passphrase":"a","new_passphrase":"b","new_passphrase_confirmation":"b","extra":"c"}"#,
            br#"{"current_passphrase":"","new_passphrase":"b","new_passphrase_confirmation":"b"}"#,
            br#"{"current_passphrase":1,"new_passphrase":"b","new_passphrase_confirmation":"b"}"#,
            br#"["a","b","b"]"#,
            b"not json",
        ] {
            assert!(rotation_bytes(invalid).is_err());
        }
        let long = format!(
            r#"{{"current_passphrase":"{}","new_passphrase":"b","new_passphrase_confirmation":"b"}}"#,
            "a".repeat(BODY_LIMIT)
        );
        assert!(rotation_bytes(long.as_bytes()).is_err());
    }

    #[test]
    fn the_change_runs_the_runtime_command_with_its_secrets_on_standard_input() {
        assert_eq!(
            super::super::arguments(&CHANGE, None, true),
            [
                "--format",
                "json",
                "config",
                "passphrase",
                "change",
                "--secrets-stdin"
            ]
        );
        const { assert!(CHANGE.runtime && !CHANGE.reads) };
    }
}
