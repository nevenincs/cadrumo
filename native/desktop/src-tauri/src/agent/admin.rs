//! One authenticated bounded administration exchange; mutations are never replayed.
use super::person;
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
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
fn failed() -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
}
fn remaining(deadline: Instant) -> Result<Duration> {
    deadline
        .checked_duration_since(Instant::now())
        .filter(|bound| !bound.is_zero())
        .ok_or_else(failed)
}
fn write_within(stream: &mut TcpStream, mut bytes: &[u8], deadline: Instant) -> Result<()> {
    while !bytes.is_empty() {
        stream
            .set_write_timeout(Some(remaining(deadline)?))
            .map_err(|_| failed())?;
        let count = stream.write(bytes).map_err(|_| failed())?;
        if count == 0 {
            return Err(failed());
        }
        bytes = &bytes[count..];
    }
    Ok(())
}
fn read_within(stream: &mut TcpStream, mut bytes: &mut [u8], deadline: Instant) -> Result<()> {
    while !bytes.is_empty() {
        stream
            .set_read_timeout(Some(remaining(deadline)?))
            .map_err(|_| failed())?;
        let count = stream.read(bytes).map_err(|_| failed())?;
        if count == 0 {
            return Err(failed());
        }
        bytes = &mut bytes[count..];
    }
    Ok(())
}
fn write_frame(stream: &mut TcpStream, bytes: &[u8], deadline: Instant) -> Result<()> {
    let size = u32::try_from(bytes.len()).map_err(|_| failed())?;
    write_within(stream, &size.to_be_bytes(), deadline)?;
    write_within(stream, bytes, deadline)
}
fn read_document(stream: &mut TcpStream, deadline: Instant) -> Result<Value> {
    let mut header = [0u8; 4];
    read_within(stream, &mut header, deadline)?;
    let size = u32::from_be_bytes(header) as usize;
    if !(1..=256 * 1024).contains(&size) {
        return Err(failed());
    }
    let mut bytes = vec![0u8; size];
    read_within(stream, &mut bytes, deadline)?;
    serde_json::from_slice(&bytes).map_err(|_| failed())
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
                return Err(failed());
            }
            request["secret_bytes"] = json!(secret.len());
        }
        let bytes = serde_json::to_vec(&request).map_err(|_| failed())?;
        if bytes.len() > 4096 {
            return Err(failed());
        }
        let address = SocketAddr::from(([127, 0, 0, 1], self.port));
        let bound = Duration::from_secs(6);
        let deadline = Instant::now() + bound;
        let mut stream = TcpStream::connect_timeout(&address, bound).map_err(|_| failed())?;
        stream.set_read_timeout(Some(bound)).map_err(|_| failed())?;
        stream
            .set_write_timeout(Some(bound))
            .map_err(|_| failed())?;
        write_frame(&mut stream, self.bearer.as_bytes(), deadline)?;
        write_frame(&mut stream, &bytes, deadline)?;
        if let Some(secret) = secret {
            let ready = read_document(&mut stream, deadline)?;
            if ready["event"] != "secret_ready" || ready["request_id"] != id {
                return Err(failed());
            }
            write_frame(&mut stream, &secret, deadline)?;
        }
        let reply = read_document(&mut stream, deadline)?;
        if reply["version"] != 1 || reply["request_id"] != id {
            return Err(failed());
        }
        reply.get("result").cloned().ok_or_else(failed)
    }
}
