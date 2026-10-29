//! The small HTTP/1.1 client codec the engine's transfers and checks speak over a stream.
//!
//! One request per connection (`Connection: close`), identity encoding only, and bounded
//! response heads, interim answers, chunk lines and trailers. Each read of a head line, an
//! interim answer or a trailer line first asks the caller's `stop`, so a host that keeps
//! sending them cannot hold the reader past a cancellation. Framing is whatever the response declares: a length,
//! chunks, or the connection closing. A body that ends before its declared framing does
//! reads as an `UnexpectedEof` error, never as a short success.

use std::io::{self, BufRead, Read, Write};

const HEAD_BYTES_LIMIT: usize = 16 * 1024;
/// Bound for a status line and a chunk line. A header field line is bounded by what is
/// left of the head's own bound instead: hosts send single fields longer than this, such
/// as a content security policy, and the head bound already keeps the whole head small.
const LINE_BYTES_LIMIT: usize = 4096;
/// Interim `1xx` answers accepted before the final head.
const INTERIM_ANSWERS_LIMIT: usize = 8;
/// Trailer bytes accepted after the last chunk.
const TRAILER_BYTES_LIMIT: usize = HEAD_BYTES_LIMIT;

/// Asked before each bounded read; `true` ends the read with a [`stopped`] error.
pub(crate) type Stop<'a> = &'a (dyn Fn() -> bool + 'a);

/// A stop for a reader that has no cancellation of its own.
pub(crate) fn never() -> bool {
    false
}

#[derive(Debug)]
pub(crate) struct ResponseHead {
    pub status: u16,
    headers: Vec<(String, String)>,
}

impl ResponseHead {
    /// The value of the first header called `name`, which is matched without case.
    pub fn header(&self, name: &str) -> Option<&str> {
        self.headers
            .iter()
            .find(|(key, _)| key.eq_ignore_ascii_case(name))
            .map(|(_, value)| value.as_str())
    }

    pub fn redirect(&self) -> bool {
        matches!(self.status, 301 | 302 | 303 | 307 | 308)
    }
}

/// Writes one request head. Header values are the caller's and must hold no line breaks.
pub(crate) fn write_request(
    stream: &mut impl Write,
    method: &str,
    target: &str,
    authority: &str,
    headers: &[(&str, &str)],
) -> io::Result<()> {
    let mut head = format!(
        "{method} {target} HTTP/1.1\r\nHost: {authority}\r\nUser-Agent: Cadrumo\r\nAccept: */*\r\nAccept-Encoding: identity\r\nConnection: close\r\n"
    );
    for (name, value) in headers {
        if value.contains(['\r', '\n']) {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "header value"));
        }
        head.push_str(name);
        head.push_str(": ");
        head.push_str(value);
        head.push_str("\r\n");
    }
    head.push_str("\r\n");
    stream.write_all(head.as_bytes())?;
    stream.flush()
}

fn malformed() -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, "malformed HTTP response")
}

/// The error a read ends with once its caller's stop says so; the caller decides what the
/// stop meant.
fn stopped() -> io::Error {
    io::Error::other("read stopped")
}

fn checked(stop: Stop<'_>) -> io::Result<()> {
    if stop() { Err(stopped()) } else { Ok(()) }
}

fn read_line(reader: &mut impl BufRead, limit: usize) -> io::Result<String> {
    let mut line = Vec::new();
    let read = reader.take(limit as u64 + 1).read_until(b'\n', &mut line)?;
    if read == 0 {
        return Err(io::ErrorKind::UnexpectedEof.into());
    }
    if line.len() > limit || !line.ends_with(b"\n") {
        return Err(if line.len() > limit {
            malformed()
        } else {
            io::ErrorKind::UnexpectedEof.into()
        });
    }
    line.pop();
    if line.ends_with(b"\r") {
        line.pop();
    }
    String::from_utf8(line).map_err(|_| malformed())
}

/// Reads one response head, skipping at most [`INTERIM_ANSWERS_LIMIT`] interim `1xx`
/// answers.
pub(crate) fn read_head(reader: &mut impl BufRead, stop: Stop<'_>) -> io::Result<ResponseHead> {
    for _ in 0..=INTERIM_ANSWERS_LIMIT {
        let mut total = 0usize;
        checked(stop)?;
        let status_line = read_line(reader, LINE_BYTES_LIMIT)?;
        total += status_line.len();
        let mut fields = status_line.splitn(3, ' ');
        let version = fields.next().unwrap_or_default();
        let code = fields.next().unwrap_or_default();
        if !version.starts_with("HTTP/1.") || code.len() != 3 {
            return Err(malformed());
        }
        let status: u16 = code.parse().map_err(|_| malformed())?;
        if !(100..=599).contains(&status) {
            return Err(malformed());
        }
        let mut headers = Vec::new();
        loop {
            checked(stop)?;
            let line = read_line(reader, HEAD_BYTES_LIMIT.saturating_sub(total))?;
            total += line.len() + 2;
            if total > HEAD_BYTES_LIMIT {
                return Err(malformed());
            }
            if line.is_empty() {
                break;
            }
            let (name, value) = line.split_once(':').ok_or_else(malformed)?;
            headers.push((name.trim().to_owned(), value.trim().to_owned()));
        }
        if (100..200).contains(&status) {
            continue;
        }
        return Ok(ResponseHead { status, headers });
    }
    Err(malformed())
}

/// How the body after a head is framed.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum Framing {
    Length(u64),
    Chunked,
    Close,
}

impl Framing {
    pub fn of(head: &ResponseHead) -> io::Result<Self> {
        if let Some(encoding) = head.header("transfer-encoding") {
            return if encoding.eq_ignore_ascii_case("chunked") {
                Ok(Self::Chunked)
            } else {
                Err(malformed())
            };
        }
        match head.header("content-length") {
            Some(length) => length.parse().map(Self::Length).map_err(|_| malformed()),
            None => Ok(Self::Close),
        }
    }
}

/// A response body read through its framing.
pub(crate) struct Body<'a, R> {
    reader: R,
    framing: Framing,
    stop: Stop<'a>,
    /// Bytes left in the declared length or the current chunk.
    left: u64,
    done: bool,
}

impl<'a, R: BufRead> Body<'a, R> {
    pub fn new(reader: R, framing: Framing, stop: Stop<'a>) -> Self {
        let left = match framing {
            Framing::Length(length) => length,
            _ => 0,
        };
        Self {
            reader,
            framing,
            stop,
            left,
            done: framing == Framing::Length(0),
        }
    }

    fn next_chunk(&mut self) -> io::Result<()> {
        checked(self.stop)?;
        let line = read_line(&mut self.reader, LINE_BYTES_LIMIT)?;
        let size = line.split(';').next().unwrap_or_default().trim();
        self.left = u64::from_str_radix(size, 16).map_err(|_| malformed())?;
        if self.left == 0 {
            let mut trailers = 0usize;
            loop {
                checked(self.stop)?;
                let line = read_line(&mut self.reader, LINE_BYTES_LIMIT)?;
                if line.is_empty() {
                    break;
                }
                trailers += line.len() + 2;
                if trailers > TRAILER_BYTES_LIMIT {
                    return Err(malformed());
                }
            }
            self.done = true;
        }
        Ok(())
    }
}

impl<R: BufRead> Read for Body<'_, R> {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        if self.done || buffer.is_empty() {
            return Ok(0);
        }
        match self.framing {
            Framing::Close => self.reader.read(buffer),
            Framing::Length(_) => {
                let limit = buffer
                    .len()
                    .min(usize::try_from(self.left).unwrap_or(usize::MAX));
                let read = self.reader.read(&mut buffer[..limit])?;
                if read == 0 {
                    return Err(io::ErrorKind::UnexpectedEof.into());
                }
                self.left -= read as u64;
                self.done = self.left == 0;
                Ok(read)
            }
            Framing::Chunked => {
                if self.left == 0 {
                    self.next_chunk()?;
                    if self.done {
                        return Ok(0);
                    }
                }
                let limit = buffer
                    .len()
                    .min(usize::try_from(self.left).unwrap_or(usize::MAX));
                let read = self.reader.read(&mut buffer[..limit])?;
                if read == 0 {
                    return Err(io::ErrorKind::UnexpectedEof.into());
                }
                self.left -= read as u64;
                if self.left == 0 && !read_line(&mut self.reader, 2)?.is_empty() {
                    return Err(malformed());
                }
                Ok(read)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufReader, Cursor};

    fn body(raw: &[u8]) -> io::Result<(u16, Vec<u8>)> {
        let mut reader = BufReader::new(Cursor::new(raw.to_vec()));
        let head = read_head(&mut reader, &never)?;
        let mut out = Vec::new();
        Body::new(reader, Framing::of(&head)?, &never).read_to_end(&mut out)?;
        Ok((head.status, out))
    }

    #[test]
    fn length_chunked_and_close_framings_read_exactly_their_body() {
        assert_eq!(
            body(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhelloEXTRA").unwrap(),
            (200, b"hello".to_vec())
        );
        assert_eq!(
            body(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5;x=y\r\nhello\r\n6\r\n world\r\n0\r\nTrailer: 1\r\n\r\n")
                .unwrap(),
            (200, b"hello world".to_vec())
        );
        assert_eq!(
            body(b"HTTP/1.0 206 Partial\r\n\r\nrest of it").unwrap(),
            (206, b"rest of it".to_vec())
        );
        assert_eq!(
            body(b"HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n").unwrap(),
            (204, Vec::new())
        );
    }

    #[test]
    fn a_body_shorter_than_its_framing_is_an_unexpected_end() {
        for raw in [
            &b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nshort"[..],
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\na\r\nshort",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n",
            b"HTTP/1.1 200 OK\r\nContent-",
        ] {
            assert_eq!(body(raw).unwrap_err().kind(), io::ErrorKind::UnexpectedEof);
        }
    }

    #[test]
    fn malformed_heads_and_framings_are_refused() {
        for raw in [
            &b"HTTP/2 200 OK\r\n\r\n"[..],
            b"HTTP/1.1 2000 OK\r\n\r\n",
            b"HTTP/1.1 099 Odd\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nno colon\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nContent-Length: ten\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: gzip\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\n",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nabXX0\r\n\r\n",
        ] {
            assert_eq!(
                body(raw).unwrap_err().kind(),
                io::ErrorKind::InvalidData,
                "{raw:?}"
            );
        }
        let mut huge = b"HTTP/1.1 200 OK\r\n".to_vec();
        for _ in 0..20 {
            huge.extend_from_slice(format!("X-Pad: {}\r\n", "a".repeat(1000)).as_bytes());
        }
        huge.extend_from_slice(b"\r\n");
        assert_eq!(body(&huge).unwrap_err().kind(), io::ErrorKind::InvalidData);
        let mut one_huge_field = b"HTTP/1.1 200 OK\r\nX-Pad: ".to_vec();
        one_huge_field.extend_from_slice("a".repeat(HEAD_BYTES_LIMIT).as_bytes());
        one_huge_field.extend_from_slice(b"\r\n\r\n");
        assert_eq!(
            body(&one_huge_field).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        let long_status = format!("HTTP/1.1 200 {}\r\n\r\n", "a".repeat(LINE_BYTES_LIMIT));
        assert_eq!(
            body(long_status.as_bytes()).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
    }

    #[test]
    fn a_header_field_longer_than_a_line_is_read_within_the_head_bound() {
        // A content security policy as long as the one github.com sends on every answer.
        let policy = format!("default-src 'none'; {}", "a".repeat(4_200));
        let raw = format!(
            "HTTP/1.1 302 Found\r\nContent-Security-Policy: {policy}\r\nLocation: https://elsewhere.example.org/\r\nContent-Length: 0\r\n\r\n"
        );
        let head = read_head(&mut BufReader::new(Cursor::new(raw.into_bytes())), &never).unwrap();
        assert_eq!(head.status, 302);
        assert_eq!(
            head.header("content-security-policy"),
            Some(policy.as_str())
        );
        assert_eq!(
            head.header("location"),
            Some("https://elsewhere.example.org/")
        );
    }

    #[test]
    fn interim_answers_and_trailers_are_bounded_and_stop_when_asked() {
        let interim = |count: usize| {
            let mut raw = b"HTTP/1.1 103 Early Hints\r\n\r\n".repeat(count);
            raw.extend_from_slice(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok");
            raw
        };
        assert_eq!(
            body(&interim(INTERIM_ANSWERS_LIMIT)).unwrap(),
            (200, b"ok".to_vec())
        );
        assert_eq!(
            body(&interim(INTERIM_ANSWERS_LIMIT + 1))
                .unwrap_err()
                .kind(),
            io::ErrorKind::InvalidData
        );

        let trailed = |lines: usize| {
            let mut raw =
                b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nok\r\n0\r\n".to_vec();
            for _ in 0..lines {
                raw.extend_from_slice(format!("X-Pad: {}\r\n", "a".repeat(1000)).as_bytes());
            }
            raw.extend_from_slice(b"\r\n");
            raw
        };
        assert_eq!(body(&trailed(2)).unwrap(), (200, b"ok".to_vec()));
        assert_eq!(
            body(&trailed(20)).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );

        let asked = std::cell::Cell::new(0usize);
        let stop = || {
            asked.set(asked.get() + 1);
            asked.get() > 1
        };
        let mut reader = BufReader::new(Cursor::new(interim(3)));
        let error = read_head(&mut reader, &stop).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::Other);
        assert_eq!(asked.get(), 2, "the stop is asked before the second line");

        let mut reader = BufReader::new(Cursor::new(trailed(2)));
        let head = read_head(&mut reader, &never).unwrap();
        let stopped = std::cell::Cell::new(false);
        let stop = || stopped.get();
        let mut body = Body::new(reader, Framing::of(&head).unwrap(), &stop);
        let mut buffer = [0u8; 2];
        assert_eq!(body.read(&mut buffer).unwrap(), 2);
        stopped.set(true);
        assert_eq!(
            body.read(&mut buffer).unwrap_err().kind(),
            io::ErrorKind::Other
        );
    }

    #[test]
    fn requests_carry_identity_encoding_and_refuse_header_injection() {
        let mut out = Vec::new();
        write_request(
            &mut out,
            "GET",
            "/a?b",
            "cdn.example.com",
            &[("Range", "bytes=5-")],
        )
        .unwrap();
        assert_eq!(
            String::from_utf8(out).unwrap(),
            "GET /a?b HTTP/1.1\r\nHost: cdn.example.com\r\nUser-Agent: Cadrumo\r\nAccept: */*\r\nAccept-Encoding: identity\r\nConnection: close\r\nRange: bytes=5-\r\n\r\n"
        );
        assert!(
            write_request(
                &mut Vec::new(),
                "GET",
                "/",
                "h.example",
                &[("X", "a\r\nInjected: 1")]
            )
            .is_err()
        );
    }
}
