//! The signed-in profile's model providers, as short-lived canonical CLI
//! invocations of the sign-in view's own channel: the digest-verified `aeat`,
//! its projected environment, its lanes, deadline and output bound.
//!
//! A key is written once to the child's standard input, as one JSON object
//! under `--secrets-stdin`, and the input is closed straight after: no retry,
//! no argument, no environment, no copy kept, nothing read back. The shell
//! holds no runtime connection and no session.
mod wire;

use crate::shell::sign_in::{
    REWRITTEN, SignIn,
    process::Children,
    wire::{self as envelope, Outcome},
};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::{fmt, process::Command, sync::Arc};
use tauri::{
    State,
    http::HeaderMap,
    ipc::{InvokeBody, Request},
};
use wire::{CommandFailure, Entry, Refusal, Status};
use zeroize::Zeroizing;

/// The request headers of a change that carries a key. The key is the body
/// and nothing else; the rest are words the product's command line reads as
/// themselves, so none needs encoding.
const PROVIDER_HEADER: &str = "x-cadrumo-provider";
const REVISION_HEADER: &str = "x-cadrumo-revision";
const BASE_URL_HEADER: &str = "x-cadrumo-base-url";
const CLEAR_BASE_URL_HEADER: &str = "x-cadrumo-clear-base-url";
/// The product's bound on the standard-input frame, after JSON encoding.
const FRAME_LIMIT: usize = 8192;
const BASE_URL_LIMIT: usize = 2048;

/// One command under `config provider`: its words, the name its answer must
/// carry, and whether it only reads.
struct Call {
    words: &'static [&'static str],
    leaf: &'static str,
    reads: bool,
}
const STATUS: Call = Call {
    words: &["provider", "status"],
    leaf: "provider.status",
    reads: true,
};
const SET: Call = Call {
    words: &["provider", "set"],
    leaf: "provider.set",
    reads: false,
};
const REMOVE: Call = Call {
    words: &["provider", "remove"],
    leaf: "provider.remove",
    reads: false,
};
const RESET: Call = Call {
    words: &["provider", "reset"],
    leaf: "provider.reset",
    reads: false,
};

fn invalid() -> ApplicationError {
    ApplicationError::new(ErrorCode::InvalidArguments, Operation::Cli)
}

/// The provider a change is for and the revision it read: the guard.
#[derive(Debug, PartialEq)]
struct Target {
    provider: String,
    revision: String,
}

impl Target {
    fn new(provider: &str, revision: &str) -> Result<Self> {
        if !wire::is_provider_id(provider) || !wire::is_revision(revision) {
            return Err(invalid());
        }
        Ok(Self {
            provider: provider.to_owned(),
            revision: revision.to_owned(),
        })
    }
}

/// What a set does to the stored base URL.
#[derive(Debug, PartialEq)]
enum BaseUrl {
    /// Neither flag: the stored URL stays.
    Keep,
    /// `--clear-base-url`: back to the catalogue default.
    Default,
    /// `--base-url`: this one.
    Url(String),
}

impl BaseUrl {
    /// A URL the product's command line would read as written: visible ASCII
    /// within a bound, not led by a hyphen (an option) and free of what the
    /// command line rewrites on Windows. Whether the URL is allowed for the
    /// provider is the product's to decide.
    fn url(text: &str) -> std::result::Result<Self, Refusal> {
        let plain = !text.is_empty()
            && text.len() <= BASE_URL_LIMIT
            && !text.starts_with('-')
            && text.bytes().all(|b| b.is_ascii_graphic())
            && !text.contains(REWRITTEN);
        if plain {
            Ok(Self::Url(text.to_owned()))
        } else {
            Err(Refusal::BaseUrlRejected)
        }
    }
}

/// The one standard-input frame of a key: `{"secret": "<key>"}`, in a buffer
/// that is wiped when it drops. It prints as nothing but its own name, and
/// it can be neither cloned nor serialized.
struct Frame(Zeroizing<Vec<u8>>);

impl fmt::Debug for Frame {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("Frame(<redacted>)")
    }
}

impl Frame {
    /// The key in the raw body, as UTF-8, within the product's bound once
    /// encoded. The buffer is sized for the longest encoding of the longest
    /// body, so that it never grows and leaves an unwiped copy behind.
    fn new(body: &InvokeBody) -> std::result::Result<Self, CommandFailure> {
        let InvokeBody::Raw(bytes) = body else {
            return Err(invalid().into());
        };
        if bytes.len() > FRAME_LIMIT {
            return Err(Refusal::InvalidKeyFormat.into());
        }
        let key = std::str::from_utf8(bytes)
            .map_err(|_| CommandFailure::from(Refusal::InvalidKeyFormat))?;
        #[derive(serde::Serialize)]
        struct Payload<'a> {
            secret: &'a str,
        }
        let mut frame = Zeroizing::new(Vec::with_capacity(FRAME_LIMIT * 6 + 64));
        serde_json::to_writer(&mut *frame, &Payload { secret: key }).map_err(|_| invalid())?;
        if frame.len() > FRAME_LIMIT {
            return Err(Refusal::InvalidKeyFormat.into());
        }
        Ok(Self(frame))
    }

    fn into_bytes(self) -> Zeroizing<Vec<u8>> {
        self.0
    }
}

/// A set, admitted whole before any child starts.
#[derive(Debug)]
struct SetRequest {
    target: Target,
    base_url: BaseUrl,
    frame: Frame,
}

fn header<'a>(headers: &'a HeaderMap, name: &str) -> Result<Option<&'a str>> {
    headers
        .get(name)
        .map(|value| value.to_str().map_err(|_| invalid()))
        .transpose()
}

fn set_request(
    headers: &HeaderMap,
    body: &InvokeBody,
) -> std::result::Result<SetRequest, CommandFailure> {
    let provider = header(headers, PROVIDER_HEADER)?.ok_or_else(invalid)?;
    let revision = header(headers, REVISION_HEADER)?.ok_or_else(invalid)?;
    let target = Target::new(provider, revision)?;
    // A URL a header cannot carry as text is a URL the command line cannot.
    let url = headers
        .get(BASE_URL_HEADER)
        .map(|value| value.to_str().map_err(|_| Refusal::BaseUrlRejected))
        .transpose()?;
    let base_url = match (url, header(headers, CLEAR_BASE_URL_HEADER)?) {
        (None, None) => BaseUrl::Keep,
        (None, Some("1")) => BaseUrl::Default,
        (Some(url), None) => BaseUrl::url(url)?,
        _ => return Err(invalid().into()),
    };
    // The key is read last: a request refused for anything else never
    // copies it.
    let frame = Frame::new(body)?;
    Ok(SetRequest {
        target,
        base_url,
        frame,
    })
}

/// The arguments of one call. Every word is fixed or was admitted above; a
/// key is never among them.
fn arguments(
    call: &Call,
    target: Option<&Target>,
    base_url: &BaseUrl,
    secret: bool,
) -> Vec<String> {
    let mut arguments: Vec<String> = ["--format", "json", "config"]
        .iter()
        .chain(call.words)
        .map(|word| (*word).to_owned())
        .collect();
    if let Some(target) = target {
        arguments.push(target.provider.clone());
        arguments.push("--expected-revision".to_owned());
        arguments.push(target.revision.clone());
    }
    match base_url {
        BaseUrl::Keep => {}
        BaseUrl::Default => arguments.push("--clear-base-url".to_owned()),
        BaseUrl::Url(url) => {
            arguments.push("--base-url".to_owned());
            arguments.push(url.clone());
        }
    }
    if secret {
        arguments.push("--secrets-stdin".to_owned());
    }
    arguments
}

/// Runs a built command on its lane and decodes the one envelope it prints.
/// The child is settled on every path, and a key is written once and then the
/// input is closed.
fn execute(
    children: &Children,
    command: Command,
    call: &Call,
    secret: Option<Zeroizing<Vec<u8>>>,
) -> Result<Outcome> {
    let output = if call.reads {
        children.read(command)?
    } else {
        children.run(command, secret)?
    };
    envelope::decode(call.leaf, &output)
}

fn launch(
    sign_in: &SignIn,
    call: &Call,
    arguments: Vec<String>,
    secret: Option<Zeroizing<Vec<u8>>>,
) -> Result<Outcome> {
    let mut command = sign_in.cli()?.command();
    command.args(arguments);
    execute(&sign_in.children, command, call, secret)
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        provider_settings_status,
        provider_settings_set,
        provider_settings_remove,
        provider_settings_reset
    ]
}

/// Every provider of the signed-in profile, masked: whether a key is there,
/// never what it is. Reading changes nothing.
#[tauri::command]
pub async fn provider_settings_status(
    state: State<'_, Arc<SignIn>>,
) -> std::result::Result<Status, CommandFailure> {
    let state = state.inner().clone();
    let outcome = super::blocking(move || {
        launch(
            &state,
            &STATUS,
            arguments(&STATUS, None, &BaseUrl::Keep, false),
            None,
        )
    })
    .await?;
    wire::status(outcome)
}

/// Stores a key or token: the raw body is the key and nothing else. One
/// attempt; nothing is retried, whatever the outcome.
#[tauri::command]
pub async fn provider_settings_set(
    state: State<'_, Arc<SignIn>>,
    request: Request<'_>,
) -> std::result::Result<Entry, CommandFailure> {
    let SetRequest {
        target,
        base_url,
        frame,
    } = set_request(request.headers(), request.body())?;
    let provider = target.provider.clone();
    let arguments = arguments(&SET, Some(&target), &base_url, true);
    let state = state.inner().clone();
    let outcome =
        super::blocking(move || launch(&state, &SET, arguments, Some(frame.into_bytes()))).await?;
    wire::changed(outcome, &provider)
}

/// Turns the provider off: nothing, not even the environment, is used.
#[tauri::command]
pub async fn provider_settings_remove(
    state: State<'_, Arc<SignIn>>,
    provider: String,
    revision: String,
) -> std::result::Result<Entry, CommandFailure> {
    change(&state, &REMOVE, &provider, &revision).await
}

/// Back to unset.
#[tauri::command]
pub async fn provider_settings_reset(
    state: State<'_, Arc<SignIn>>,
    provider: String,
    revision: String,
) -> std::result::Result<Entry, CommandFailure> {
    change(&state, &RESET, &provider, &revision).await
}

async fn change(
    state: &State<'_, Arc<SignIn>>,
    call: &'static Call,
    provider: &str,
    revision: &str,
) -> std::result::Result<Entry, CommandFailure> {
    let target = Target::new(provider, revision)?;
    let arguments = arguments(call, Some(&target), &BaseUrl::Keep, false);
    let state = state.inner().clone();
    let outcome = super::blocking(move || launch(&state, call, arguments, None)).await?;
    wire::changed(outcome, &target.provider)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tauri::http::HeaderValue;

    const KEY: &str = "sk-live-0123456789-not-a-real-key";

    fn target() -> Target {
        Target::new("anthropic", &"0".repeat(64)).unwrap()
    }

    fn headers(pairs: &[(&str, &str)]) -> HeaderMap {
        let mut headers = HeaderMap::new();
        for (name, value) in pairs {
            headers.insert(
                tauri::http::HeaderName::from_bytes(name.as_bytes()).unwrap(),
                HeaderValue::from_str(value).unwrap(),
            );
        }
        headers
    }

    fn body(text: &str) -> InvokeBody {
        InvokeBody::Raw(text.as_bytes().to_vec())
    }

    fn named() -> [(&'static str, &'static str); 2] {
        [(PROVIDER_HEADER, "anthropic"), (REVISION_HEADER, "absent")]
    }

    fn refused(failure: CommandFailure) -> serde_json::Value {
        serde_json::to_value(failure).unwrap()
    }

    #[test]
    fn each_call_is_the_contracts_command_line_and_a_status_names_no_provider() {
        let revision = "0".repeat(64);
        assert_eq!(
            arguments(&STATUS, None, &BaseUrl::Keep, false),
            ["--format", "json", "config", "provider", "status"]
        );
        assert_eq!(
            arguments(&SET, Some(&target()), &BaseUrl::Keep, true),
            [
                "--format",
                "json",
                "config",
                "provider",
                "set",
                "anthropic",
                "--expected-revision",
                revision.as_str(),
                "--secrets-stdin"
            ]
        );
        for (call, word) in [(&REMOVE, "remove"), (&RESET, "reset")] {
            assert_eq!(
                arguments(call, Some(&target()), &BaseUrl::Keep, false),
                [
                    "--format",
                    "json",
                    "config",
                    "provider",
                    word,
                    "anthropic",
                    "--expected-revision",
                    revision.as_str()
                ]
            );
        }
    }

    #[test]
    fn the_base_url_is_stored_cleared_or_kept_by_its_flag() {
        let tail =
            |base_url: &BaseUrl| arguments(&SET, Some(&target()), base_url, true)[8..].to_vec();
        assert_eq!(tail(&BaseUrl::Keep), ["--secrets-stdin"]);
        assert_eq!(
            tail(&BaseUrl::Default),
            ["--clear-base-url", "--secrets-stdin"]
        );
        assert_eq!(
            tail(&BaseUrl::Url("https://gateway.example/v1".into())),
            [
                "--base-url",
                "https://gateway.example/v1",
                "--secrets-stdin"
            ]
        );
    }

    #[test]
    fn a_base_url_header_means_store_a_clear_flag_means_default_and_neither_means_keep() {
        let take = |extra: &[(&str, &str)]| {
            let mut pairs = named().to_vec();
            pairs.extend_from_slice(extra);
            set_request(&headers(&pairs), &body(KEY)).unwrap().base_url
        };
        assert_eq!(take(&[]), BaseUrl::Keep);
        assert_eq!(take(&[(CLEAR_BASE_URL_HEADER, "1")]), BaseUrl::Default);
        assert_eq!(
            take(&[(BASE_URL_HEADER, "https://gateway.example/v1")]),
            BaseUrl::Url("https://gateway.example/v1".into())
        );
    }

    #[test]
    fn a_request_names_its_provider_and_revision_once_and_one_base_url_instruction() {
        let both = [
            (PROVIDER_HEADER, "anthropic"),
            (REVISION_HEADER, "absent"),
            (BASE_URL_HEADER, "https://gateway.example"),
            (CLEAR_BASE_URL_HEADER, "1"),
        ];
        let bad_clear = [
            (PROVIDER_HEADER, "anthropic"),
            (REVISION_HEADER, "absent"),
            (CLEAR_BASE_URL_HEADER, "0"),
        ];
        let requests: [&[(&str, &str)]; 8] = [
            &[],
            &[(PROVIDER_HEADER, "anthropic")],
            &[(REVISION_HEADER, "absent")],
            &[(PROVIDER_HEADER, "Anthropic"), (REVISION_HEADER, "absent")],
            &[(PROVIDER_HEADER, "-x"), (REVISION_HEADER, "absent")],
            &[(PROVIDER_HEADER, "anthropic"), (REVISION_HEADER, "-1")],
            &both,
            &bad_clear,
        ];
        for pairs in requests {
            let failure = set_request(&headers(pairs), &body(KEY)).unwrap_err();
            assert_eq!(refused(failure)["code"], "invalid_arguments", "{pairs:?}");
        }
    }

    #[test]
    fn a_base_url_the_command_line_would_not_read_as_written_is_refused_as_rejected() {
        let long = format!("https://{}", "a".repeat(BASE_URL_LIMIT));
        for url in [
            "",
            "-https://x",
            "--help",
            "https://x y",
            "https://x\t",
            "https://exámple.test",
            "https://x/%25USERNAME%25",
            "https://x/a?b=c",
            "https://x/$HOME",
            "https://x/*",
            "https://x/[1]",
            long.as_str(),
        ] {
            let mut pairs = named().to_vec();
            pairs.push((BASE_URL_HEADER, url));
            let failure = set_request(&headers(&pairs), &body(KEY)).unwrap_err();
            assert_eq!(
                refused(failure),
                serde_json::json!({"code": "base_url_rejected"}),
                "{url:?}"
            );
        }
        // A well-formed https URL passes: whether the provider allows it is
        // the product's call.
        assert_eq!(
            BaseUrl::url("http://localhost:8080/v1").unwrap(),
            BaseUrl::Url("http://localhost:8080/v1".into())
        );
    }

    #[test]
    fn no_argument_of_any_call_holds_the_key() {
        let mut pairs = named().to_vec();
        pairs.push((BASE_URL_HEADER, "https://gateway.example/v1"));
        let request = set_request(&headers(&pairs), &body(KEY)).unwrap();
        let argv = arguments(&SET, Some(&request.target), &request.base_url, true);
        assert!(
            argv.iter()
                .all(|word| !word.contains(KEY) && !word.contains("sk-"))
        );
        // The key is in the frame and nowhere in what prints.
        assert!(!format!("{request:?}").contains("sk-"));
        assert_eq!(format!("{:?}", request.frame), "Frame(<redacted>)");
        assert!(format!("{request:?}").contains("<redacted>"));
        assert_eq!(
            serde_json::from_slice::<serde_json::Value>(&request.frame.into_bytes()).unwrap(),
            serde_json::json!({"secret": KEY})
        );
    }

    #[test]
    fn the_frame_is_one_json_object_within_the_products_bound() {
        let encoded = |text: &str| Frame::new(&body(text)).unwrap().into_bytes();
        assert_eq!(
            serde_json::from_slice::<serde_json::Value>(&encoded("á\"\n漢\\")).unwrap(),
            serde_json::json!({"secret": "á\"\n漢\\"})
        );
        assert_eq!(&*encoded("k"), br#"{"secret":"k"}"#);
        // Empty is the product's to refuse, with its own word for it.
        assert_eq!(&*encoded(""), br#"{"secret":""}"#);
        // Control characters encode to six bytes each: 1400 of them pass the
        // raw bound and fail the encoded one.
        let frame = Frame::new(&body(&"\u{1}".repeat(1400))).unwrap_err();
        assert_eq!(
            refused(frame),
            serde_json::json!({"code": "invalid_key_format"})
        );
        assert_eq!(encoded(&"k".repeat(FRAME_LIMIT - 13)).len(), FRAME_LIMIT);
        // The buffer is sized for the longest encoding, so it never grows
        // and leaves an unwiped copy of an earlier, smaller buffer behind.
        assert!(encoded("\u{1}").capacity() >= FRAME_LIMIT * 6 + 13);
    }

    #[test]
    fn a_key_that_does_not_fit_or_is_not_text_is_refused_before_any_child_starts() {
        for bad in [
            InvokeBody::Raw(vec![255, 254]),
            InvokeBody::Raw(vec![b'k'; FRAME_LIMIT + 1]),
            InvokeBody::Raw(vec![b'k'; FRAME_LIMIT - 12]),
            InvokeBody::Raw(vec![b'"'; FRAME_LIMIT / 2]),
        ] {
            let failure = Frame::new(&bad).unwrap_err();
            assert_eq!(
                refused(failure),
                serde_json::json!({"code": "invalid_key_format"})
            );
        }
        for bad in [
            InvokeBody::Json(serde_json::json!([107])),
            InvokeBody::Json(serde_json::json!({"secret": KEY})),
        ] {
            let failure = Frame::new(&bad).unwrap_err();
            assert_eq!(refused(failure)["code"], "invalid_arguments");
        }
    }

    #[test]
    fn a_request_refused_for_its_words_never_reads_the_key() {
        // A refusal for the provider comes before one for the key.
        let failure = set_request(
            &headers(&[(PROVIDER_HEADER, "NOPE"), (REVISION_HEADER, "absent")]),
            &InvokeBody::Raw(vec![255]),
        )
        .unwrap_err();
        assert_eq!(refused(failure)["code"], "invalid_arguments");
    }

    #[test]
    fn remove_and_reset_admit_only_a_known_shape_of_provider_and_revision() {
        assert!(Target::new("anthropic", "absent").is_ok());
        for (provider, revision) in [
            ("", "absent"),
            ("anthropic", ""),
            ("--help", "absent"),
            ("anthropic", "--help"),
            ("anthropic", "a b"),
            ("anthropic x", "absent"),
        ] {
            assert_eq!(
                Target::new(provider, revision).unwrap_err().code,
                ErrorCode::InvalidArguments
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

    // A real child: it gets the one frame and then end of input, and what it
    // prints is read through the same decoder as the product's own answer.
    #[cfg(windows)]
    #[test]
    fn a_real_child_receives_the_one_frame_then_end_of_input_and_its_answer_is_read() {
        let children = Children::default();
        let outcome = execute(
            &children,
            powershell(
                "$frame=[Console]::In.ReadToEnd(); \
                 $code=if ($frame -ceq '{\"secret\":\"k\"}') {'revision_conflict'} else {'unknown'}; \
                 [Console]::Out.Write('{\"schema_version\":\"2\",\"command\":\"config.provider.set\",\"status\":\"success\",\"result\":{\"refused\":\"'+$code+'\"}}')",
            ),
            &SET,
            Some(Frame::new(&body("k")).unwrap().into_bytes()),
        )
        .unwrap();
        assert_eq!(
            refused(wire::changed(outcome, "anthropic").unwrap_err()),
            serde_json::json!({"code": "revision_conflict"})
        );
    }

    #[cfg(windows)]
    #[test]
    fn a_child_that_floods_its_output_is_refused_by_the_bound_and_reaped() {
        let children = Children::default();
        for call in [&STATUS, &SET] {
            let secret = (!call.reads).then(|| Frame::new(&body("k")).unwrap().into_bytes());
            let failure = execute(
                &children,
                powershell("while ($true) { [Console]::Out.Write(('x' * 8192)) }"),
                call,
                secret,
            )
            .err()
            .unwrap();
            assert_eq!(failure.code, ErrorCode::OutputLimit);
        }
    }

    #[cfg(windows)]
    #[test]
    fn an_answer_that_names_another_command_or_is_not_an_envelope_is_a_protocol_failure() {
        let children = Children::default();
        for script in [
            "[Console]::Out.Write('{\"schema_version\":\"2\",\"command\":\"config.provider.status\",\"status\":\"success\",\"result\":{}}')",
            "[Console]::Out.Write('not json')",
            "[Console]::Out.Write('')",
        ] {
            let failure = execute(&children, powershell(script), &SET, None)
                .err()
                .unwrap();
            assert_eq!(failure.code, ErrorCode::ReadFailed);
        }
    }

    #[cfg(windows)]
    #[test]
    fn a_status_read_through_a_real_child_parses_the_envelope() {
        let children = Children::default();
        let outcome = execute(
            &children,
            powershell(
                "[Console]::Out.Write('{\"schema_version\":\"2\",\"command\":\"config.provider.status\",\"status\":\"success\",\"result\":{\"development\":false,\"providers\":[]}}')",
            ),
            &STATUS,
            None,
        )
        .unwrap();
        assert!(wire::status(outcome).unwrap().providers.is_empty());
    }
}
