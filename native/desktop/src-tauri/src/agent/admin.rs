//! One authenticated bounded administration exchange; mutations are never replayed.
use super::person;
use cadrumo_application::error::application::{
    ApplicationError, ChildRefusal, ErrorCode, Operation, Result,
};
use serde_json::{Value, json};
use std::{
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    sync::Arc,
    time::{Duration, Instant},
};
use zeroize::Zeroizing;

#[derive(Clone)]
pub struct Endpoint {
    pub port: u16,
    pub bearer: Arc<Zeroizing<String>>,
    pub generation: u64,
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
    pub fn exchange(
        &self,
        mut request: Value,
        secret: Option<Zeroizing<Vec<u8>>>,
    ) -> Result<Value> {
        let id = person::request_id()?;
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
        let bound = Duration::from_secs(6);
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
    use cadrumo_application::error::application::Cause;
    use std::{error::Error, net::TcpListener};

    fn endpoint(port: u16) -> Endpoint {
        Endpoint {
            port,
            bearer: Arc::new(Zeroizing::new("b".repeat(64))),
            generation: 1,
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
    fn each_admin_failure_names_its_check_and_keeps_its_source() {
        let refused = {
            let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
            let port = listener.local_addr().unwrap().port();
            drop(listener);
            exchange(port)
        };
        assert_eq!(refused.reason.as_deref(), Some("admin_connect"));
        assert!(
            matches!(&refused.causes[..], [Cause::Io { io_kind, .. }] if io_kind == "ConnectionRefused")
        );
        assert!(refused.source().is_some());

        let closed = exchange(serve(|mut stream| drain_request(&mut stream)));
        assert_eq!(closed.reason.as_deref(), Some("admin_read_eof"));

        let oversized = exchange(serve(|mut stream| {
            drain_request(&mut stream);
            stream.write_all(&u32::MAX.to_be_bytes()).unwrap();
        }));
        assert_eq!(oversized.reason.as_deref(), Some("admin_frame_size"));

        let garbled = exchange(serve(|mut stream| {
            drain_request(&mut stream);
            stream.write_all(&3u32.to_be_bytes()).unwrap();
            stream.write_all(b"{x}").unwrap();
        }));
        assert_eq!(garbled.reason.as_deref(), Some("admin_document_parse"));
        assert!(
            matches!(&garbled.causes[..], [Cause::Json { category, .. }] if category == "syntax")
        );

        let mismatched = exchange(serve(|mut stream| {
            drain_request(&mut stream);
            let reply = br#"{"version":1,"request_id":"other"}"#;
            stream
                .write_all(&(reply.len() as u32).to_be_bytes())
                .unwrap();
            stream.write_all(reply).unwrap();
        }));
        assert_eq!(
            mismatched.reason.as_deref(),
            Some("admin_reply_request_mismatch")
        );
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
        assert_eq!(error.reason.as_deref(), Some("admin_reply_without_result"));
        let [Cause::Child(refusal)] = &error.causes[..] else {
            panic!("expected the service refusal, got {:?}", error.causes);
        };
        assert_eq!(refusal.code.as_deref(), Some("provider_unavailable"));
        assert!(!serde_json::to_string(&error).unwrap().contains("PRIVATE"));
    }
}
