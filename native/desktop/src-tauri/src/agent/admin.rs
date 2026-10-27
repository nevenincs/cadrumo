//! One authenticated bounded administration exchange; mutations are never replayed.
use super::person;
use cadrumo_application::error::application::{
    ApplicationError, Cause, ChildRefusal, ErrorCode, Operation, Result,
};
use serde_json::{Value, json};
use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    sync::{Arc, Condvar, Mutex},
    time::{Duration, Instant},
};
use zeroize::Zeroizing;

/// How many exchanges the service admits at once. It closes any further
/// connection unanswered, which the desktop read as a reset connection, so
/// the desktop holds the rest back until one ends.
pub const CAPACITY: usize = 4;

/// The exchanges in flight with one service, at most [`CAPACITY`].
#[derive(Default)]
pub struct Gate {
    held: Mutex<usize>,
    freed: Condvar,
}

/// One admitted exchange; leaving frees its place for the next.
pub struct Permit<'a>(&'a Gate);

impl Gate {
    /// A place for one exchange, waiting while every place is taken, until `deadline`.
    pub fn enter(&self, deadline: Instant) -> Result<Permit<'_>> {
        let mut held = self.held.lock().unwrap_or_else(|e| e.into_inner());
        while *held >= CAPACITY {
            let Some(left) = deadline
                .checked_duration_since(Instant::now())
                .filter(|left| !left.is_zero())
            else {
                return Err(ApplicationError::new(ErrorCode::TimedOut, Operation::Cli)
                    .with_reason("admin_queue_elapsed"));
            };
            held = self
                .freed
                .wait_timeout(held, left)
                .unwrap_or_else(|e| e.into_inner())
                .0;
        }
        *held += 1;
        Ok(Permit(self))
    }
}

impl Drop for Permit<'_> {
    fn drop(&mut self) {
        let mut held = self.0.held.lock().unwrap_or_else(|e| e.into_inner());
        *held -= 1;
        self.0.freed.notify_one();
    }
}

#[derive(Clone)]
pub struct Endpoint {
    pub port: u16,
    pub bearer: Arc<Zeroizing<String>>,
    pub generation: u64,
    pub gate: Arc<Gate>,
}

/// The diagnostic name of an administration action, as the service declares them.
fn action_reason(action: &str) -> &'static str {
    match action {
        "catalog" => "admin_catalog",
        "status" => "admin_status",
        "set" => "admin_set",
        "remove" => "admin_remove",
        "turn_on" => "admin_turn_on",
        "reset" => "admin_reset",
        "auth" => "admin_auth",
        "sign_in" => "admin_sign_in",
        "start" => "admin_start",
        "stop" => "admin_stop",
        "connect" => "admin_connect_provider",
        "connect_status" => "admin_connect_status",
        "connect_cancel" => "admin_connect_cancel",
        "connect_submit_code" => "admin_connect_submit_code",
        "model_roles" => "admin_model_roles",
        "model_role_set" => "admin_model_role_set",
        "model_role_clear" => "admin_model_role_clear",
        "model_roles_reset" => "admin_model_roles_reset",
        _ => "admin_undeclared_action",
    }
}

/// `failure` named for the exchange it ended: its action, then its request
/// id, which the service's own records carry, then the check that failed.
fn named(action: &str, request_id: &str, failure: ApplicationError) -> ApplicationError {
    let mut named = ApplicationError::new(failure.code, failure.operation)
        .with_reason(action_reason(action))
        .caused_by(failure);
    named.causes.insert(
        0,
        Cause::Application {
            code: named.code,
            operation: named.operation,
            reason: Some(format!("request_{}", request_id.replace('-', ""))),
        },
    );
    named
}
fn failed(reason: &'static str) -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli).with_reason(reason)
}
fn io_failed(code: ErrorCode, reason: &'static str, error: std::io::Error) -> ApplicationError {
    ApplicationError::new(code, Operation::Cli)
        .with_reason(reason)
        .caused_by(error)
}
fn remaining(deadline: Instant) -> Result<Duration> {
    deadline
        .checked_duration_since(Instant::now())
        .filter(|bound| !bound.is_zero())
        .ok_or_else(|| {
            ApplicationError::new(ErrorCode::TimedOut, Operation::Cli)
                .with_reason("admin_deadline_elapsed")
        })
}
fn write_within(stream: &mut TcpStream, mut bytes: &[u8], deadline: Instant) -> Result<()> {
    while !bytes.is_empty() {
        stream
            .set_write_timeout(Some(remaining(deadline)?))
            .map_err(|e| io_failed(ErrorCode::WriteFailed, "admin_write_timeout_set", e))?;
        let count = stream
            .write(bytes)
            .map_err(|e| io_failed(ErrorCode::WriteFailed, "admin_write", e))?;
        if count == 0 {
            return Err(
                ApplicationError::new(ErrorCode::WriteFailed, Operation::Cli)
                    .with_reason("admin_write_zero"),
            );
        }
        bytes = &bytes[count..];
    }
    Ok(())
}
fn read_within(stream: &mut TcpStream, mut bytes: &mut [u8], deadline: Instant) -> Result<()> {
    while !bytes.is_empty() {
        stream
            .set_read_timeout(Some(remaining(deadline)?))
            .map_err(|e| io_failed(ErrorCode::ReadFailed, "admin_read_timeout_set", e))?;
        let count = stream
            .read(bytes)
            .map_err(|e| io_failed(ErrorCode::ReadFailed, "admin_read", e))?;
        if count == 0 {
            return Err(failed("admin_read_eof"));
        }
        bytes = &mut bytes[count..];
    }
    Ok(())
}
fn write_frame(stream: &mut TcpStream, bytes: &[u8], deadline: Instant) -> Result<()> {
    let size = u32::try_from(bytes.len()).map_err(|_| failed("admin_frame_too_large"))?;
    write_within(stream, &size.to_be_bytes(), deadline)?;
    write_within(stream, bytes, deadline)
}
fn read_document(stream: &mut TcpStream, deadline: Instant) -> Result<Value> {
    let mut header = [0u8; 4];
    read_within(stream, &mut header, deadline)?;
    let size = u32::from_be_bytes(header) as usize;
    if !(1..=256 * 1024).contains(&size) {
        return Err(failed("admin_frame_size"));
    }
    let mut bytes = vec![0u8; size];
    read_within(stream, &mut bytes, deadline)?;
    serde_json::from_slice(&bytes).map_err(|error| failed("admin_document_parse").caused_by(error))
}
/// The service's final busy answer to request `id`, if `reply` is one.
fn busy_reply(reply: &Value, id: &str) -> Option<Value> {
    (reply["version"] == 1
        && reply["request_id"] == id
        && reply["result"]["kind"] == "refused"
        && reply["result"]["code"] == "busy")
        .then(|| reply["result"].clone())
}
/// A reply without a result names the service's own refusal code, if it gave one.
fn refused_reply(reply: &Value) -> ApplicationError {
    let answer = if reply["error"].is_object() {
        &reply["error"]
    } else {
        reply
    };
    failed("admin_reply_without_result").caused_by(ChildRefusal::answered(answer))
}
impl Endpoint {
    /// One exchange, named by its action and request id however it fails.
    pub fn exchange(&self, request: Value, secret: Option<Zeroizing<Vec<u8>>>) -> Result<Value> {
        let action = request["action"].as_str().unwrap_or_default().to_owned();
        let id = person::request_id()?;
        self.exchange_as(&id, request, secret)
            .map_err(|failure| named(&action, &id, failure))
    }

    fn exchange_as(
        &self,
        id: &str,
        mut request: Value,
        secret: Option<Zeroizing<Vec<u8>>>,
    ) -> Result<Value> {
        request["version"] = json!(1);
        request["request_id"] = json!(id);
        if let Some(secret) = &secret {
            if !(1..=16 * 1024).contains(&secret.len()) {
                return Err(failed("admin_secret_size"));
            }
            request["secret_bytes"] = json!(secret.len());
        }
        let bytes = serde_json::to_vec(&request)
            .map_err(|error| failed("admin_request_encode").caused_by(error))?;
        if bytes.len() > 4096 {
            return Err(failed("admin_request_too_large"));
        }
        let address = SocketAddr::from(([127, 0, 0, 1], self.port));
        // Login preparation must first reap the running gateway (up to 20 s).
        // Status also runs a contained supplier check: five seconds of execution,
        // ten for tree cleanup, then output drain and profile-authority reads.
        // Its deadline must encompass that work. Login polling stays short.
        let bound = Duration::from_secs(match request["action"].as_str() {
            Some("connect") => 60,
            Some("status") => 30,
            _ => 6,
        });
        // The wait for a place is bounded like the exchange, and apart from it.
        let _permit = self.gate.enter(Instant::now() + bound)?;
        let deadline = Instant::now() + bound;
        let mut stream = TcpStream::connect_timeout(&address, bound)
            .map_err(|e| io_failed(ErrorCode::ReadFailed, "admin_connect", e))?;
        stream
            .set_read_timeout(Some(bound))
            .map_err(|e| io_failed(ErrorCode::ReadFailed, "admin_read_timeout_set", e))?;
        stream
            .set_write_timeout(Some(bound))
            .map_err(|e| io_failed(ErrorCode::WriteFailed, "admin_write_timeout_set", e))?;
        write_frame(&mut stream, self.bearer.as_bytes(), deadline)?;
        write_frame(&mut stream, &bytes, deadline)?;
        if let Some(secret) = secret {
            let ready = read_document(&mut stream, deadline)?;
            if ready["event"] != "secret_ready" || ready["request_id"] != id {
                // A service with no place for the request answers busy at
                // once, before it asks for the secret, which is then not sent.
                if let Some(busy) = busy_reply(&ready, id) {
                    return Ok(busy);
                }
                return Err(failed("admin_secret_ready_mismatch"));
            }
            write_frame(&mut stream, &secret, deadline)?;
        }
        let reply = read_document(&mut stream, deadline)?;
        if reply["version"] != 1 {
            return Err(failed("admin_reply_version"));
        }
        if reply["request_id"] != id {
            return Err(failed("admin_reply_request_mismatch"));
        }
        reply
            .get("result")
            .cloned()
            .ok_or_else(|| refused_reply(&reply))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{error::Error, net::TcpListener};

    fn endpoint(port: u16) -> Endpoint {
        Endpoint {
            port,
            bearer: Arc::new(Zeroizing::new("b".repeat(64))),
            generation: 1,
            gate: Arc::new(Gate::default()),
        }
    }

    /// The check that failed inside a named exchange failure.
    fn check(error: &ApplicationError) -> Option<&str> {
        match error.causes.get(1) {
            Some(Cause::Application { reason, .. }) => reason.as_deref(),
            _ => None,
        }
    }

    fn serve(answer: impl FnOnce(TcpStream) + Send + 'static) -> u16 {
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        std::thread::spawn(move || {
            let (stream, _) = listener.accept().unwrap();
            answer(stream);
        });
        port
    }

    fn drain_request(stream: &mut TcpStream) {
        for _ in 0..2 {
            let mut header = [0u8; 4];
            stream.read_exact(&mut header).unwrap();
            let mut body = vec![0u8; u32::from_be_bytes(header) as usize];
            stream.read_exact(&mut body).unwrap();
        }
    }

    fn exchange(port: u16) -> ApplicationError {
        endpoint(port)
            .exchange(json!({"action": "catalog"}), None)
            .unwrap_err()
    }

    #[test]
    fn connect_exchange_allows_the_gateway_shutdown_grace_before_reply() {
        let port = serve(|mut stream| {
            let mut header = [0u8; 4];
            stream.read_exact(&mut header).unwrap();
            let mut bearer = vec![0u8; u32::from_be_bytes(header) as usize];
            stream.read_exact(&mut bearer).unwrap();
            assert_eq!(bearer, b"b".repeat(64));

            stream.read_exact(&mut header).unwrap();
            let mut body = vec![0u8; u32::from_be_bytes(header) as usize];
            stream.read_exact(&mut body).unwrap();
            let request: Value = serde_json::from_slice(&body).unwrap();
            assert_eq!(request["action"], "connect");

            // The normal admin bound is six seconds. Login preparation can
            // first spend twenty seconds stopping the hosted gateway.
            std::thread::sleep(Duration::from_secs(7));

            let reply = serde_json::to_vec(&json!({
                "version": 1,
                "request_id": request["request_id"],
                "result": {"kind": "connected"},
            }))
            .unwrap();
            stream
                .write_all(&(reply.len() as u32).to_be_bytes())
                .unwrap();
            stream.write_all(&reply).unwrap();
        });

        let reply = endpoint(port)
            .exchange(json!({"action": "connect"}), None)
            .unwrap();
        assert_eq!(reply["kind"], "connected");
    }

    #[test]
    fn each_admin_failure_names_its_check_and_keeps_its_source() {
        let refused = {
            let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
            let port = listener.local_addr().unwrap().port();
            drop(listener);
            exchange(port)
        };
        assert_eq!(refused.reason.as_deref(), Some("admin_catalog"));
        assert_eq!(check(&refused), Some("admin_connect"));
        assert!(matches!(
            refused.causes.last(),
            Some(Cause::Io { io_kind, .. }) if io_kind == "ConnectionRefused"
        ));
        assert!(refused.source().is_some());

        let closed = exchange(serve(|mut stream| drain_request(&mut stream)));
        assert_eq!(check(&closed), Some("admin_read_eof"));

        let oversized = exchange(serve(|mut stream| {
            drain_request(&mut stream);
            stream.write_all(&u32::MAX.to_be_bytes()).unwrap();
        }));
        assert_eq!(check(&oversized), Some("admin_frame_size"));

        let garbled = exchange(serve(|mut stream| {
            drain_request(&mut stream);
            stream.write_all(&3u32.to_be_bytes()).unwrap();
            stream.write_all(b"{x}").unwrap();
        }));
        assert_eq!(check(&garbled), Some("admin_document_parse"));
        assert!(matches!(
            garbled.causes.last(),
            Some(Cause::Json { category, .. }) if category == "syntax"
        ));

        let mismatched = exchange(serve(|mut stream| {
            drain_request(&mut stream);
            let reply = br#"{"version":1,"request_id":"other"}"#;
            stream
                .write_all(&(reply.len() as u32).to_be_bytes())
                .unwrap();
            stream.write_all(reply).unwrap();
        }));
        assert_eq!(check(&mismatched), Some("admin_reply_request_mismatch"));
    }

    #[test]
    fn a_reply_without_a_result_carries_the_services_refusal_code() {
        let error = exchange(serve(|mut stream| {
            let mut header = [0u8; 4];
            stream.read_exact(&mut header).unwrap();
            let mut bearer = vec![0u8; u32::from_be_bytes(header) as usize];
            stream.read_exact(&mut bearer).unwrap();
            stream.read_exact(&mut header).unwrap();
            let mut body = vec![0u8; u32::from_be_bytes(header) as usize];
            stream.read_exact(&mut body).unwrap();
            let request: Value = serde_json::from_slice(&body).unwrap();
            let reply = serde_json::to_vec(&json!({
                "version": 1,
                "request_id": request["request_id"],
                "error": {"code": "provider_unavailable", "message": "PRIVATE"},
            }))
            .unwrap();
            stream
                .write_all(&(reply.len() as u32).to_be_bytes())
                .unwrap();
            stream.write_all(&reply).unwrap();
        }));
        assert_eq!(check(&error), Some("admin_reply_without_result"));
        let Some(Cause::Child(refusal)) = error.causes.last() else {
            panic!("expected the service refusal, got {:?}", error.causes);
        };
        assert_eq!(refusal.code.as_deref(), Some("provider_unavailable"));
        assert!(!serde_json::to_string(&error).unwrap().contains("PRIVATE"));
    }

    #[test]
    fn a_failure_names_the_action_and_the_request_it_ended() {
        let port = {
            let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
            let port = listener.local_addr().unwrap().port();
            drop(listener);
            port
        };
        for (action, reason) in [
            ("catalog", "admin_catalog"),
            ("status", "admin_status"),
            ("start", "admin_start"),
            ("connect_status", "admin_connect_status"),
            ("model_roles", "admin_model_roles"),
            ("model_role_set", "admin_model_role_set"),
            ("unheard_of", "admin_undeclared_action"),
        ] {
            let error = endpoint(port)
                .exchange(json!({"action": action}), None)
                .unwrap_err();
            assert_eq!(error.reason.as_deref(), Some(reason));
            assert_eq!(error.code, ErrorCode::ReadFailed);
            let Some(Cause::Application {
                reason: Some(request),
                ..
            }) = error.causes.first()
            else {
                panic!("expected the request id first, got {:?}", error.causes);
            };
            let id = request.strip_prefix("request_").unwrap();
            assert!(id.len() == 32 && id.bytes().all(|b| b.is_ascii_hexdigit()));
            assert!(error.causes.iter().all(Cause::admissible));
            let summary = error.chain_summary().unwrap();
            assert!(summary.starts_with(reason) && summary.contains("admin_connect"));
        }
    }

    #[test]
    fn exchanges_beyond_the_services_capacity_wait_for_a_place() {
        let gate = Arc::new(Gate::default());
        let later = Instant::now() + Duration::from_secs(60);
        let held: Vec<_> = (0..CAPACITY).map(|_| gate.enter(later).unwrap()).collect();
        // Every place is taken: one more waits, and a wait that has run out
        // is refused as elapsed rather than sent to be reset.
        let elapsed = gate.enter(Instant::now()).err().unwrap();
        assert_eq!(elapsed.code, ErrorCode::TimedOut);
        assert_eq!(elapsed.reason.as_deref(), Some("admin_queue_elapsed"));
        let (entered, admitted) = std::sync::mpsc::channel();
        let waiting = {
            let gate = gate.clone();
            std::thread::spawn(move || {
                let permit = gate.enter(later).map(|_| ());
                entered.send(permit.is_ok()).unwrap();
            })
        };
        // Leaving one place admits the waiting exchange.
        drop(held);
        assert!(admitted.recv().unwrap());
        waiting.join().unwrap();
        assert_eq!(*gate.held.lock().unwrap(), 0);
    }

    /// Reads the bearer and the request, and returns the request.
    fn read_request(stream: &mut TcpStream) -> Value {
        let mut header = [0u8; 4];
        for _ in 0..2 {
            stream.read_exact(&mut header).unwrap();
            let mut body = vec![0u8; u32::from_be_bytes(header) as usize];
            stream.read_exact(&mut body).unwrap();
            if let Ok(request) = serde_json::from_slice::<Value>(&body) {
                return request;
            }
        }
        panic!("no request was sent");
    }

    fn write_document(stream: &mut TcpStream, document: Value) {
        let bytes = serde_json::to_vec(&document).unwrap();
        stream
            .write_all(&(bytes.len() as u32).to_be_bytes())
            .unwrap();
        stream.write_all(&bytes).unwrap();
    }

    #[test]
    fn a_set_the_service_has_no_place_for_is_busy_and_its_secret_is_not_sent() {
        let (sent, received) = std::sync::mpsc::channel();
        let port = serve(move |mut stream| {
            let request = read_request(&mut stream);
            assert_eq!(request["action"], "set");
            write_document(
                &mut stream,
                json!({"version": 1, "request_id": request["request_id"],
                    "result": {"kind": "refused", "code": "busy"}}),
            );
            // Whatever the desktop sends after the busy answer.
            let mut rest = Vec::new();
            stream.read_to_end(&mut rest).unwrap();
            sent.send(rest).unwrap();
        });
        let reply = endpoint(port)
            .exchange(
                json!({"action": "set"}),
                Some(Zeroizing::new(b"secret-bytes".to_vec())),
            )
            .unwrap();
        assert_eq!(reply, json!({"kind": "refused", "code": "busy"}));
        assert!(received.recv().unwrap().is_empty());
    }

    #[test]
    fn another_answer_where_the_secret_is_asked_for_is_still_a_mismatch() {
        let port = serve(|mut stream| {
            let request = read_request(&mut stream);
            write_document(
                &mut stream,
                json!({"version": 1, "request_id": request["request_id"],
                    "result": {"kind": "refused", "code": "signed_out"}}),
            );
        });
        let error = endpoint(port)
            .exchange(
                json!({"action": "set"}),
                Some(Zeroizing::new(b"secret-bytes".to_vec())),
            )
            .unwrap_err();
        assert_eq!(error.reason.as_deref(), Some("admin_set"));
        assert_eq!(check(&error), Some("admin_secret_ready_mismatch"));
    }

    #[test]
    fn a_busy_answer_is_a_result_the_caller_reads_again() {
        let port = serve(|mut stream| {
            let request = read_request(&mut stream);
            write_document(
                &mut stream,
                json!({"version": 1, "request_id": request["request_id"],
                    "result": {"kind": "refused", "code": "busy"}}),
            );
        });
        let reply = endpoint(port)
            .exchange(json!({"action": "catalog"}), None)
            .unwrap();
        assert!(super::super::catalog_busy(&reply));
    }
}
