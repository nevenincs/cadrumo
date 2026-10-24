//! The engine's client for the local AI program's own API, on a loopback address only.
//!
//! The program answers plain HTTP on this computer, so nothing here crosses the network
//! and no proxy applies. Requests and answers use the same bounded codec as the
//! transfers. A JSON answer is read whole up to a bound; a streamed answer is read one
//! line at a time, each line bounded, and ends early when the caller's stop says so.

use crate::{
    error::Error,
    provisioning::http::{self, Body, Framing, Stop},
};
use std::{
    io::{self, BufRead, BufReader, Read},
    net::{SocketAddr, TcpStream},
    time::Duration,
};

/// The largest whole answer read.
const ANSWER_BYTES_LIMIT: u64 = 1024 * 1024;
/// The longest line of a streamed answer.
const LINE_BYTES_LIMIT: u64 = 64 * 1024;

/// One loopback address and the bounds of each exchange with it.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Loopback {
    address: SocketAddr,
    /// Bound for connecting.
    pub connect_timeout: Duration,
    /// Bound for each read or write once connected.
    pub io_timeout: Duration,
}

impl Loopback {
    /// Refuses any address that is not this computer's.
    pub fn new(address: SocketAddr) -> Result<Self, Error> {
        if !address.ip().is_loopback() {
            return Err(Error::Invalid(
                "the local AI answers on loopback only".into(),
            ));
        }
        Ok(Self {
            address,
            connect_timeout: Duration::from_secs(2),
            io_timeout: Duration::from_secs(10),
        })
    }

    pub fn address(&self) -> SocketAddr {
        self.address
    }

    /// The same address with a longer bound for each read, for an answer the program
    /// takes a while to start, such as a model it first loads.
    pub fn with_io_timeout(mut self, io_timeout: Duration) -> Self {
        self.io_timeout = io_timeout;
        self
    }

    fn exchange<'a>(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
        stop: Stop<'a>,
    ) -> io::Result<(u16, Body<'a, BufReader<TcpStream>>)> {
        let mut stream = TcpStream::connect_timeout(&self.address, self.connect_timeout)?;
        stream.set_read_timeout(Some(self.io_timeout))?;
        stream.set_write_timeout(Some(self.io_timeout))?;
        stream.set_nodelay(true)?;
        let authority = self.address.to_string();
        let length = body.map(|body| body.len().to_string());
        let mut headers = Vec::new();
        if let Some(length) = &length {
            headers.push(("Content-Type", "application/json"));
            headers.push(("Content-Length", length.as_str()));
        }
        http::write_request(&mut stream, method, path, &authority, &headers)?;
        if let Some(body) = body {
            io::Write::write_all(&mut stream, body)?;
            io::Write::flush(&mut stream)?;
        }
        let mut reader = BufReader::new(stream);
        let head = http::read_head(&mut reader, stop)?;
        let framing = Framing::of(&head)?;
        Ok((head.status, Body::new(reader, framing, stop)))
    }

    /// `GET path`: the status and the whole answer.
    pub fn get(&self, path: &str) -> io::Result<(u16, Vec<u8>)> {
        let (status, body) = self.exchange("GET", path, None, &http::never)?;
        Ok((status, whole(body)?))
    }

    /// `POST path` with a JSON body: the status and the whole answer.
    pub fn post(&self, path: &str, json: &[u8]) -> io::Result<(u16, Vec<u8>)> {
        let (status, body) = self.exchange("POST", path, Some(json), &http::never)?;
        Ok((status, whole(body)?))
    }
    /// `POST path` with a JSON body, handing each non-empty line of a successful answer
    /// to `line` as it arrives, and asking `stop` before each line. An unsuccessful
    /// answer is read whole and returned instead.
    pub fn post_lines(
        &self,
        path: &str,
        json: &[u8],
        stop: &dyn Fn() -> bool,
        line: &mut dyn FnMut(&[u8]) -> io::Result<()>,
    ) -> io::Result<(u16, Vec<u8>)> {
        let (status, body) = self.exchange("POST", path, Some(json), stop)?;
        if !(200..300).contains(&status) {
            return Ok((status, whole(body)?));
        }
        let mut reader = BufReader::new(body);
        let mut buffer = Vec::new();
        loop {
            if stop() {
                return Err(io::Error::from(io::ErrorKind::Interrupted));
            }
            buffer.clear();
            let read = (&mut reader)
                .take(LINE_BYTES_LIMIT + 1)
                .read_until(b'\n', &mut buffer)?;
            if read == 0 {
                return Ok((status, Vec::new()));
            }
            if buffer.len() as u64 > LINE_BYTES_LIMIT {
                return Err(io::Error::new(io::ErrorKind::InvalidData, "answer line"));
            }
            let text = buffer.trim_ascii();
            if !text.is_empty() {
                line(text)?;
            }
        }
    }
}

fn whole(body: impl Read) -> io::Result<Vec<u8>> {
    let mut out = Vec::new();
    body.take(ANSWER_BYTES_LIMIT + 1).read_to_end(&mut out)?;
    if out.len() as u64 > ANSWER_BYTES_LIMIT {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "answer too long",
        ));
    }
    Ok(out)
}
