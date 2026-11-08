//! Payload-free observations from the desktop and its presentation libraries.
use super::service::LogLevel;
use crate::error::application::ErrorCode;
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DesktopEvent {
    CommandRejected,
    UncaughtError,
    UnhandledRejection,
    ReactError,
    Console,
    NativeLog,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DiagnosticOrigin {
    Frontend,
    Rust,
    Tauri,
}

/// A host relay's payload-free failure vocabulary, separate from application errors.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RelayFailureCode {
    Unavailable,
    Unknown,
    SavedUnread,
    Refused,
    NotAdmitted,
    NotSignedIn,
    Invalid,
    TooLarge,
    FileUnavailable,
    ReviewChanged,
    Conflict,
}

/// A refusal code of the agent host, such as `agent_service_busy`. The host
/// words these itself, and the gateway's own code is appended to a fixed
/// `agent_gateway_` prefix after the host has checked its characters, so a
/// code is a short snake_case token and never exception or payload text.
#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(transparent)]
pub struct AgentRefusalCode(String);

impl AgentRefusalCode {
    const PREFIX: &'static str = "agent_";
    const MAX_LEN: usize = 96;

    pub fn parse(code: &str) -> Option<Self> {
        let rest = code.strip_prefix(Self::PREFIX)?;
        let token = !rest.is_empty()
            && code.len() <= Self::MAX_LEN
            && rest
                .bytes()
                .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_');
        token.then(|| Self(code.to_owned()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl<'de> Deserialize<'de> for AgentRefusalCode {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let code = String::deserialize(deserializer)?;
        Self::parse(&code)
            .ok_or_else(|| serde::de::Error::custom("not an agent refusal code token"))
    }
}

/// Only closed host codes may be persisted; exception and payload text never qualify.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(untagged)]
pub enum DesktopDiagnosticCode {
    Application(ErrorCode),
    Relay(RelayFailureCode),
    Agent(AgentRefusalCode),
}

impl From<ErrorCode> for DesktopDiagnosticCode {
    fn from(code: ErrorCode) -> Self {
        Self::Application(code)
    }
}

/// A backend's closed refusal or failure code that a relay failure carries
/// beside its own code, such as `ERROR_FINANCIAL_AGGREGATION_VALIDATION` or
/// `unknown_operation`. Only snake_case tokens of words joined by `_`
/// qualify, so a value such as a tax ID, an amount or a sentence never does.
#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(transparent)]
pub struct BackendReason(String);

impl BackendReason {
    const MAX_LEN: usize = 96;

    pub fn parse(reason: &str) -> Option<Self> {
        let word = |part: &str| !part.is_empty() && part.bytes().all(|b| b.is_ascii_alphanumeric());
        let mut parts = reason.split('_');
        let first = parts.next().unwrap_or_default();
        let lower = reason.bytes().all(|b| b.is_ascii_lowercase() || b == b'_');
        let joined = reason.contains('_') && parts.all(word);
        let leads = first.bytes().all(|b| b.is_ascii_alphabetic()) && !first.is_empty();
        (reason.len() <= Self::MAX_LEN && leads && (joined || (lower && word(first))))
            .then(|| Self(reason.to_owned()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// Words a frontend message may keep although they start with a capital:
/// sentence openings and error names of the browser and its libraries.
const KEPT_CAPITALISED: [&str; 40] = [
    "A",
    "AbortError",
    "An",
    "Cannot",
    "Could",
    "DOMException",
    "Defaulting",
    "Each",
    "Encountered",
    "Error",
    "EvalError",
    "Expected",
    "Failed",
    "Function",
    "Functions",
    "If",
    "Invalid",
    "It",
    "Maximum",
    "NetworkError",
    "NotAllowedError",
    "NotFoundError",
    "Objects",
    "RangeError",
    "React",
    "ReferenceError",
    "Rendered",
    "ResizeObserver",
    "Script",
    "SecurityError",
    "SyntaxError",
    "The",
    "This",
    "Too",
    "TypeError",
    "URIError",
    "Uncaught",
    "Unexpected",
    "Warning",
    "When",
];

/// The longest template a record keeps, in characters.
const TEMPLATE_LIMIT: usize = 240;

/// The authored shape of a frontend message with every value taken out. A
/// quoted or backticked span, a number, a capitalised word outside
/// [`KEPT_CAPITALISED`], and any word with a digit, a non-ASCII letter or a
/// symbol become `…`; lowercase ASCII words, `%s`-style placeholders and
/// punctuation stay. The frontend sends what this function would return and
/// the host applies it again, so it is the one rule.
pub fn redact_template(text: &str) -> Option<String> {
    const EDGE: &[char] = &[
        '.', ',', ':', ';', '(', ')', '[', ']', '{', '}', '!', '?', '-', '=',
    ];
    let mut spans = String::with_capacity(text.len().min(4 * TEMPLATE_LIMIT));
    let mut quote: Option<char> = None;
    for c in text.chars() {
        match quote {
            Some(open) if c == open => {
                spans.push('…');
                spans.push(c);
                quote = None;
            }
            Some(_) => {}
            None if c == '`' || c == '"' => {
                spans.push(c);
                quote = Some(c);
            }
            None => spans.push(c),
        }
    }
    if quote.is_some() {
        spans.push('…');
    }
    let kept = |core: &str| {
        core.is_empty()
            || core == "…"
            || core == "`…`"
            || core == "\"…\""
            || KEPT_CAPITALISED.contains(&core)
            || (core.len() == 2
                && core.starts_with('%')
                && matches!(
                    core.as_bytes()[1],
                    b's' | b'd' | b'i' | b'f' | b'o' | b'O' | b'c'
                ))
            || (core.starts_with(|c: char| c.is_ascii_lowercase())
                && core.chars().all(|c| c.is_ascii_alphabetic() || c == '\'')
                && !core.contains("''"))
    };
    let mut words: Vec<String> = Vec::new();
    for token in spans.split_whitespace() {
        let core = token.trim_matches(EDGE);
        let word = if kept(core) {
            token.to_owned()
        } else {
            let start = token.find(core).unwrap_or(0);
            format!("{}…{}", &token[..start], &token[start + core.len()..])
        };
        if word == "…" && words.last().is_some_and(|last| last == "…") {
            continue;
        }
        words.push(word);
    }
    let mut template = String::new();
    for word in words {
        let next =
            template.chars().count() + usize::from(!template.is_empty()) + word.chars().count();
        if next > TEMPLATE_LIMIT {
            template.push_str(" …");
            break;
        }
        if !template.is_empty() {
            template.push(' ');
        }
        template.push_str(&word);
    }
    template
        .chars()
        .any(|c| c.is_ascii_alphabetic())
        .then_some(template)
}

/// A bundle module's file name, as a stack frame or an error event names
/// it: never its origin, folders or query.
pub fn module_name(location: &str) -> Option<String> {
    let path = location.split(['?', '#']).next().unwrap_or_default();
    let name = path.rsplit(['/', '\\']).next().unwrap_or_default();
    let script = [".js", ".mjs", ".jsx", ".ts", ".tsx", ".html"]
        .iter()
        .any(|suffix| name.ends_with(suffix));
    (script
        && name.len() <= 96
        && !name.starts_with('.')
        && name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'-')))
    .then(|| name.to_owned())
}

/// What a frontend record said, without any of its values.
#[derive(Clone, Debug, Default, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DesktopSummary {
    /// The message's authored shape, as [`redact_template`] leaves it.
    pub template: Option<String>,
    /// The bundle module of the first frame, as [`module_name`] leaves it.
    pub module: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DesktopDiagnostic {
    pub origin: DiagnosticOrigin,
    pub logger: Option<String>,
    pub event: DesktopEvent,
    pub level: LogLevel,
    /// Resolved against registered command names by the host.
    pub command: Option<String>,
    pub code: Option<DesktopDiagnosticCode>,
    pub dropped: u32,
    pub line: Option<u32>,
    pub column: Option<u32>,
    /// The backend's own code beside a relay failure's `code`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<BackendReason>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub summary: Option<DesktopSummary>,
}
