//! Binding a view connection to a running view.
//!
//! The window asks on its person connection with `view_attach` for a
//! single-use token. The runtime grants it only to the admitted session that
//! submitted the `live.sede.view` operation named in the request, on the same
//! profile and native peer, and only while that operation's worker holds its
//! view open. The token is bound to the exact session, profile, native peer,
//! runtime boot and operation, is spent by its first presentation, accepted or
//! not, and lapses after [`ATTACH_TOKEN_SECONDS`].
//!
//! The window then opens a new runtime connection from this process, verified
//! as every runtime connection is, and presents the token as `view_connect`,
//! the connection's first request. The reply is `view_connected`, after which
//! the connection carries only the view stream. Any refusal is an
//! `access_refusal` followed by the connection's close.
//!
//! The token is private: it is held in a wiped buffer, never printed, and
//! never leaves this module except in the one `view_connect` frame.

use super::{
    chunks::{KIND_DOCUMENT, encode_frame},
    documents::is_lower_hex,
};
use crate::runtime_client::{
    Admitted, Cohort, Endpoint, Refusal, RuntimeChannel, SessionExchange, document, handshake,
    is_uuid, read_frame, request_id, text,
};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::{
    fmt,
    time::{Duration, Instant},
};
use zeroize::Zeroizing;

/// How long an attach token stays presentable after it is issued.
pub const ATTACH_TOKEN_SECONDS: u64 = 10;

const OPERATION_ID_HEX: usize = 64;
const TOKEN_HEX: usize = 64;

/// A request on the person connection, or the first request of a view connection.
#[derive(Serialize)]
#[serde(tag = "action")]
pub enum ViewRequest<'a> {
    #[serde(rename = "view_attach")]
    Attach(ViewAttachRequest<'a>),
    #[serde(rename = "view_connect")]
    Connect(ViewConnect<'a>),
}

/// Asks, on the window's person connection, to attach a view connection to a running view.
#[derive(Serialize)]
pub struct ViewAttachRequest<'a> {
    pub request_id: &'a str,
    pub profile_id: &'a str,
    pub session_id: &'a str,
    pub operation_id: &'a str,
}

/// The first request on a new runtime connection, turning it into a view connection.
#[derive(Serialize)]
pub struct ViewConnect<'a> {
    pub request_id: &'a str,
    pub operation_id: &'a str,
    pub attach_token: &'a str,
}

fn attach_token_seconds() -> u8 {
    10
}

/// A single-use attach token for one new view connection.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewAttachGranted {
    pub request_id: String,
    pub runtime_boot_id: String,
    pub connection_id: String,
    pub operation_id: String,
    pub attach_token: String,
    #[serde(default = "attach_token_seconds")]
    pub expires_in_seconds: u8,
}

impl ViewAttachGranted {
    fn validate(&self) -> bool {
        is_uuid(&self.request_id)
            && is_uuid(&self.runtime_boot_id)
            && is_uuid(&self.connection_id)
            && is_lower_hex(&self.operation_id, OPERATION_ID_HEX)
            && is_lower_hex(&self.attach_token, TOKEN_HEX)
            && u64::from(self.expires_in_seconds) == ATTACH_TOKEN_SECONDS
    }
}

impl fmt::Debug for ViewAttachGranted {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("ViewAttachGranted(..)")
    }
}

/// The reply to `view_attach`; an `access_refusal` never reaches this type.
#[derive(Debug, Deserialize)]
#[serde(tag = "kind")]
pub enum AttachReply {
    #[serde(rename = "view_attach_granted")]
    Granted(ViewAttachGranted),
}

/// The view connection is bound to its operation; the stream follows with no credit granted.
#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ViewConnected {
    pub request_id: String,
    pub runtime_boot_id: String,
    pub connection_id: String,
    pub operation_id: String,
}

impl ViewConnected {
    fn validate(&self) -> bool {
        is_uuid(&self.request_id)
            && is_uuid(&self.runtime_boot_id)
            && is_uuid(&self.connection_id)
            && is_lower_hex(&self.operation_id, OPERATION_ID_HEX)
    }
}

/// The reply to `view_connect`; an `access_refusal` never reaches this type.
#[derive(Debug, Deserialize)]
#[serde(tag = "kind")]
pub enum ConnectReply {
    #[serde(rename = "view_connected")]
    Connected(ViewConnected),
}

/// The right to present one attach token: bound to a running view, used once.
pub struct ViewAttachGrant {
    operation_id: String,
    runtime_boot_id: String,
    person_connection_id: String,
    token: Zeroizing<String>,
    expires_at: Instant,
}

impl ViewAttachGrant {
    /// The operation the token is bound to.
    pub fn operation_id(&self) -> &str {
        &self.operation_id
    }

    /// The instant after which the runtime refuses the token.
    pub fn expires_at(&self) -> Instant {
        self.expires_at
    }

    pub fn expired(&self) -> bool {
        Instant::now() >= self.expires_at
    }
}

impl fmt::Debug for ViewAttachGrant {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("ViewAttachGrant(..)")
    }
}

/// Asks, on the person connection `exchange` carries, for a token to attach to the view
/// that `held`'s session submitted as `operation_id`.
///
/// The runtime's refusal comes back as [`Refusal::Denied`]. A reply the
/// runtime could not have sent closes the connection.
pub fn view_attach(
    exchange: &dyn SessionExchange,
    held: &Admitted,
    operation_id: &str,
    deadline: Instant,
) -> Result<ViewAttachGrant, Refusal> {
    if !is_lower_hex(operation_id, OPERATION_ID_HEX) {
        return Err(Refusal::InvalidFrame);
    }
    let id = request_id();
    let request = serde_json::to_value(ViewRequest::Attach(ViewAttachRequest {
        request_id: &id,
        profile_id: &held.profile_id,
        session_id: &held.session_id,
        operation_id,
    }))
    .map_err(|_| Refusal::InvalidFrame)?;
    // The runtime issues the token between sending and answering, so its
    // lifetime is counted from before the request.
    let requested_at = Instant::now();
    let reply = exchange.exchange(&request, deadline)?;
    match grant_from(reply, &id, held, operation_id, requested_at) {
        Some(grant) => Ok(grant),
        None => {
            exchange.close();
            Err(Refusal::InvalidFrame)
        }
    }
}

/// The grant a `view_attach_granted` reply makes, if it answers this request exactly.
fn grant_from(
    reply: Map<String, Value>,
    request_id: &str,
    held: &Admitted,
    operation_id: &str,
    requested_at: Instant,
) -> Option<ViewAttachGrant> {
    let AttachReply::Granted(granted) = serde_json::from_value(Value::Object(reply)).ok()?;
    let answers = granted.validate()
        && granted.request_id == request_id
        && granted.runtime_boot_id == held.runtime_boot_id
        && granted.connection_id == held.connection_id
        && granted.operation_id == operation_id;
    answers.then(|| ViewAttachGrant {
        operation_id: granted.operation_id,
        runtime_boot_id: granted.runtime_boot_id,
        person_connection_id: granted.connection_id,
        token: Zeroizing::new(granted.attach_token),
        expires_at: requested_at + Duration::from_secs(ATTACH_TOKEN_SECONDS),
    })
}

/// Opens a new verified connection to `endpoint` and presents `grant` as its first request.
///
/// The connection is made from this process to the runtime's pipe and verified
/// as the same-account peer, as every runtime connection is. It asks for no
/// lifecycle notices, so only the view stream ever arrives on it. The token is
/// spent by this call whether or not the runtime accepts it. Returns the pipe,
/// which now carries the stream, and the runtime's `view_connected`.
pub fn connect_view(
    endpoint: &Endpoint,
    cohort: &Cohort,
    grant: ViewAttachGrant,
    deadline: Instant,
) -> Result<(RuntimeChannel, ViewConnected), Refusal> {
    if grant.expired() {
        return Err(Refusal::Timeout);
    }
    let (pipe, hello) = handshake(endpoint, cohort, false, deadline)?;
    if hello.boot_id != grant.runtime_boot_id {
        return Err(Refusal::InvalidFrame);
    }
    if grant.expired() {
        return Err(Refusal::Timeout);
    }
    let id = request_id();
    let payload = Zeroizing::new(
        serde_json::to_vec(&ViewRequest::Connect(ViewConnect {
            request_id: &id,
            operation_id: &grant.operation_id,
            attach_token: &grant.token,
        }))
        .map_err(|_| Refusal::InvalidFrame)?,
    );
    let framed = encode_frame(KIND_DOCUMENT, &payload).map_err(|_| Refusal::InvalidFrame)?;
    pipe.write_all(&framed, deadline)?;
    let (kind, reply) = read_frame(&pipe, deadline)?;
    if kind != KIND_DOCUMENT {
        return Err(Refusal::InvalidFrame);
    }
    let connected = connected_from(document(&reply)?, &id, &hello.boot_id, &grant)?;
    Ok((pipe, connected))
}

/// The `view_connected` a reply makes, or the runtime's refusal.
fn connected_from(
    reply: Map<String, Value>,
    request_id: &str,
    boot_id: &str,
    grant: &ViewAttachGrant,
) -> Result<ViewConnected, Refusal> {
    if text(&reply, "request_id") != Some(request_id)
        || text(&reply, "runtime_boot_id") != Some(boot_id)
    {
        return Err(Refusal::InvalidFrame);
    }
    if text(&reply, "kind") == Some("access_refusal") {
        return Err(Refusal::denied(text(&reply, "code").unwrap_or_default()));
    }
    let ConnectReply::Connected(connected) =
        serde_json::from_value(Value::Object(reply)).map_err(|_| Refusal::InvalidFrame)?;
    // A view connection is a different connection from the person's.
    let exact = connected.validate()
        && connected.operation_id == grant.operation_id
        && connected.connection_id != grant.person_connection_id;
    if exact {
        Ok(connected)
    } else {
        Err(Refusal::InvalidFrame)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::sync::{
        Mutex,
        atomic::{AtomicBool, Ordering},
        mpsc,
    };

    const PROFILE: &str = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    const SESSION: &str = "1a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    const BOOT: &str = "2a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    const PERSON: &str = "3a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    const VIEW: &str = "4a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";

    fn operation() -> String {
        "ab".repeat(32)
    }

    fn token() -> String {
        "cd".repeat(32)
    }

    fn held() -> Admitted {
        Admitted {
            profile_id: PROFILE.into(),
            session_id: SESSION.into(),
            connection_id: PERSON.into(),
            runtime_boot_id: BOOT.into(),
            expires_at: None,
            session_persisted: None,
            signed_out_profile_ids: Vec::new(),
        }
    }

    fn granted(request_id: &str) -> Map<String, Value> {
        json!({
            "kind": "view_attach_granted", "request_id": request_id, "runtime_boot_id": BOOT,
            "connection_id": PERSON, "operation_id": operation(), "attach_token": token(),
            "expires_in_seconds": 10
        })
        .as_object()
        .unwrap()
        .clone()
    }

    type Answer = Box<dyn Fn(&Value) -> Result<Map<String, Value>, Refusal> + Send + Sync>;

    /// Answers each exchange from its request, noting the request and any close.
    struct Answering {
        answer: Answer,
        asked: Mutex<Vec<Value>>,
        closed: AtomicBool,
    }

    impl Answering {
        fn with(answer: Answer) -> Self {
            Self {
                answer,
                asked: Mutex::new(Vec::new()),
                closed: AtomicBool::new(false),
            }
        }
    }

    impl SessionExchange for Answering {
        fn exchange(
            &self,
            request: &Value,
            _deadline: Instant,
        ) -> Result<Map<String, Value>, Refusal> {
            self.asked.lock().unwrap().push(request.clone());
            (self.answer)(request)
        }

        fn exchange_streamed(
            &self,
            _request: &Value,
            _payload: &[u8],
            _deadline: Instant,
        ) -> Result<Map<String, Value>, Refusal> {
            Err(Refusal::Unavailable)
        }

        fn exchange_with_secret(
            &self,
            _request: &Value,
            _secret: &[u8],
            _deadline: Instant,
        ) -> Result<Map<String, Value>, Refusal> {
            Err(Refusal::Unavailable)
        }

        fn subscribe_scoped(&self) -> mpsc::Receiver<crate::runtime_client::Pushed> {
            mpsc::channel().1
        }

        fn close(&self) {
            self.closed.store(true, Ordering::Release);
        }
    }

    fn soon() -> Instant {
        Instant::now() + Duration::from_secs(5)
    }

    #[test]
    fn the_requests_are_exactly_the_python_documents() {
        let attach = serde_json::to_value(ViewRequest::Attach(ViewAttachRequest {
            request_id: "r",
            profile_id: PROFILE,
            session_id: SESSION,
            operation_id: "o",
        }))
        .unwrap();
        assert_eq!(
            attach,
            json!({"action": "view_attach", "request_id": "r", "profile_id": PROFILE,
                   "session_id": SESSION, "operation_id": "o"})
        );
        let connect = serde_json::to_value(ViewRequest::Connect(ViewConnect {
            request_id: "r",
            operation_id: "o",
            attach_token: "t",
        }))
        .unwrap();
        assert_eq!(
            connect,
            json!({"action": "view_connect", "request_id": "r", "operation_id": "o",
                   "attach_token": "t"})
        );
    }

    #[test]
    fn a_grant_answers_only_its_own_request_session_and_operation() {
        let requested_at = Instant::now();
        let id = request_id();
        let grant = grant_from(granted(&id), &id, &held(), &operation(), requested_at).unwrap();
        assert_eq!(grant.operation_id(), operation());
        assert_eq!(grant.expires_at(), requested_at + Duration::from_secs(10));
        assert_eq!(grant.token.as_str(), token());
        assert!(!grant.expired());
        let refused = |change: &dyn Fn(&mut Map<String, Value>)| {
            let mut reply = granted(&id);
            change(&mut reply);
            grant_from(reply, &id, &held(), &operation(), requested_at).is_none()
        };
        assert!(refused(&|reply| {
            reply.insert("request_id".into(), json!(request_id()));
        }));
        assert!(refused(&|reply| {
            reply.insert("runtime_boot_id".into(), json!(VIEW));
        }));
        assert!(refused(&|reply| {
            reply.insert("connection_id".into(), json!(VIEW));
        }));
        assert!(refused(&|reply| {
            reply.insert("operation_id".into(), json!("cd".repeat(32)));
        }));
        assert!(refused(&|reply| {
            reply.insert("attach_token".into(), json!(token().to_uppercase()));
        }));
        assert!(refused(&|reply| {
            reply.insert("attach_token".into(), json!("cd".repeat(31)));
        }));
        assert!(refused(&|reply| {
            reply.insert("expires_in_seconds".into(), json!(11));
        }));
        assert!(refused(&|reply| {
            reply.insert("url".into(), json!("https://x"));
        }));
        assert!(refused(&|reply| {
            reply.insert("kind".into(), json!("view_connected"));
        }));
        assert!(refused(&|reply| {
            reply.remove("attach_token");
        }));
        // The lifetime member may be left out; the contract's default is the ten seconds.
        let mut bare = granted(&id);
        bare.remove("expires_in_seconds");
        assert!(grant_from(bare, &id, &held(), &operation(), requested_at).is_some());
    }

    #[test]
    fn view_attach_sends_the_session_and_operation_and_returns_the_exact_grant() {
        let exchange = Answering::with(Box::new(|request| {
            Ok(granted(request["request_id"].as_str().unwrap()))
        }));
        let grant = view_attach(&exchange, &held(), &operation(), soon()).unwrap();
        assert_eq!(grant.operation_id(), operation());
        assert_eq!(grant.token.as_str(), token());
        assert!(!exchange.closed.load(Ordering::Acquire));
        let request = exchange.asked.lock().unwrap()[0].clone();
        assert_eq!(request["action"], "view_attach");
        assert_eq!(request["profile_id"], PROFILE);
        assert_eq!(request["session_id"], SESSION);
        assert_eq!(request["operation_id"], operation());
        assert!(is_uuid(request["request_id"].as_str().unwrap()));
        assert_eq!(request.as_object().unwrap().len(), 5);
    }

    #[test]
    fn the_runtimes_refusal_comes_back_without_closing_the_connection() {
        let exchange = Answering::with(Box::new(|_| Err(Refusal::denied("operation_unavailable"))));
        let refusal = view_attach(&exchange, &held(), &operation(), soon()).unwrap_err();
        assert_eq!(refusal.code(), "operation_unavailable");
        assert!(
            !exchange.closed.load(Ordering::Acquire),
            "a refusal is the runtime's answer, not a broken connection"
        );
    }

    #[test]
    fn a_reply_for_another_request_closes_the_connection() {
        let exchange = Answering::with(Box::new(|_| Ok(granted(&request_id()))));
        assert!(matches!(
            view_attach(&exchange, &held(), &operation(), soon()),
            Err(Refusal::InvalidFrame)
        ));
        assert!(exchange.closed.load(Ordering::Acquire));
    }

    #[test]
    fn an_operation_that_is_not_an_identity_is_refused_before_any_request() {
        let exchange = Answering::with(Box::new(|_| Err(Refusal::Unavailable)));
        for operation in ["", "AB", &"ab".repeat(31), &"AB".repeat(32)] {
            assert!(matches!(
                view_attach(&exchange, &held(), operation, soon()),
                Err(Refusal::InvalidFrame)
            ));
        }
        assert!(exchange.asked.lock().unwrap().is_empty());
    }

    #[test]
    fn a_view_connected_reply_binds_the_operation_on_a_connection_that_is_not_the_persons() {
        let id = request_id();
        let grant = grant_from(granted(&id), &id, &held(), &operation(), Instant::now()).unwrap();
        let connect_id = request_id();
        let reply = |change: &dyn Fn(&mut Map<String, Value>)| {
            let mut reply = json!({
                "kind": "view_connected", "request_id": connect_id, "runtime_boot_id": BOOT,
                "connection_id": VIEW, "operation_id": operation()
            })
            .as_object()
            .unwrap()
            .clone();
            change(&mut reply);
            connected_from(reply, &connect_id, BOOT, &grant)
        };
        let connected = reply(&|_| {}).unwrap();
        assert_eq!(connected.connection_id, VIEW);
        assert!(matches!(
            reply(&|reply| {
                reply.insert("request_id".into(), json!(request_id()));
            }),
            Err(Refusal::InvalidFrame)
        ));
        assert!(matches!(
            reply(&|reply| {
                reply.insert("runtime_boot_id".into(), json!(VIEW));
            }),
            Err(Refusal::InvalidFrame)
        ));
        assert!(matches!(
            reply(&|reply| {
                reply.insert("connection_id".into(), json!(PERSON));
            }),
            Err(Refusal::InvalidFrame)
        ));
        assert!(matches!(
            reply(&|reply| {
                reply.insert("operation_id".into(), json!("cd".repeat(32)));
            }),
            Err(Refusal::InvalidFrame)
        ));
        assert!(matches!(
            reply(&|reply| {
                reply.insert("extra".into(), json!(1));
            }),
            Err(Refusal::InvalidFrame)
        ));
        let refusal = reply(&|reply| {
            reply.insert("kind".into(), json!("access_refusal"));
            reply.insert("code".into(), json!("connection_mismatch"));
        })
        .unwrap_err();
        assert_eq!(refusal.code(), "connection_mismatch");
    }

    #[test]
    fn a_grant_and_its_token_print_nothing() {
        let id = request_id();
        let grant = grant_from(granted(&id), &id, &held(), &operation(), Instant::now()).unwrap();
        assert!(!format!("{grant:?}").contains(&token()));
        let reply: AttachReply = serde_json::from_value(Value::Object(granted(&id))).unwrap();
        assert!(!format!("{reply:?}").contains(&token()));
    }
}
