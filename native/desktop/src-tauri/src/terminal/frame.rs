//! The terminal frame encoding carried by one channel per session.
//!
//! Every frame is one tag byte followed by its payload:
//!
//! | Tag | Frame     | Payload                                            |
//! | --- | --------- | -------------------------------------------------- |
//! | 0   | `data`    | PTY output bytes, 1 to 8192, counted by acks       |
//! | 1   | `started` | UTF-8 JSON `{"pid": number}`                       |
//! | 2   | `exited`  | UTF-8 JSON `{"code": number \| null}`              |
//! | 3   | `failed`  | UTF-8 JSON `{"error": HostFailure}`                |
//!
//! `HostFailure` is the serialized `ApplicationError` (`code`, `operation`,
//! `message`). One channel orders every frame, so `exited` always follows the
//! last `data` frame. Only `data` payload bytes advance the acknowledged
//! offset.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde::{Deserialize, Serialize};

const DATA: u8 = 0;
const STARTED: u8 = 1;
const EXITED: u8 = 2;
const FAILED: u8 = 3;

#[derive(Debug, PartialEq, Serialize, Deserialize)]
struct Started {
    pid: u32,
}

#[derive(Debug, PartialEq, Serialize, Deserialize)]
struct Exited {
    code: Option<u32>,
}

#[derive(Serialize)]
struct Failed<'a> {
    error: &'a ApplicationError,
}

/// A failure as the frontend receives it; decoding keeps the wire fields.
#[cfg(test)]
#[derive(Debug, PartialEq, Deserialize)]
pub struct HostFailure {
    pub code: String,
    pub operation: String,
    pub message: String,
}

#[cfg(test)]
#[derive(Debug, PartialEq, Deserialize)]
struct DecodedFailed {
    error: HostFailure,
}

pub enum Frame<'a> {
    Data(&'a [u8]),
    Started { pid: u32 },
    Exited { code: Option<u32> },
    Failed(&'a ApplicationError),
}

fn malformed() -> ApplicationError {
    ApplicationError::new(ErrorCode::WriteFailed, Operation::Terminal)
}

impl Frame<'_> {
    pub fn encode(&self) -> Result<Vec<u8>> {
        let json = |tag: u8, value: serde_json::Result<Vec<u8>>| {
            value
                .map(|payload| {
                    let mut frame = Vec::with_capacity(payload.len() + 1);
                    frame.push(tag);
                    frame.extend(payload);
                    frame
                })
                .map_err(|e| malformed().caused_by(e))
        };
        match self {
            Self::Data(bytes) => {
                let mut frame = Vec::with_capacity(bytes.len() + 1);
                frame.push(DATA);
                frame.extend_from_slice(bytes);
                Ok(frame)
            }
            Self::Started { pid } => json(STARTED, serde_json::to_vec(&Started { pid: *pid })),
            Self::Exited { code } => json(EXITED, serde_json::to_vec(&Exited { code: *code })),
            Self::Failed(error) => json(FAILED, serde_json::to_vec(&Failed { error })),
        }
    }
}

/// The decoded form of a frame, as a frontend reads it.
#[cfg(test)]
#[derive(Debug, PartialEq)]
pub enum Decoded {
    Data(Vec<u8>),
    Started { pid: u32 },
    Exited { code: Option<u32> },
    Failed(HostFailure),
}

/// Reference decoder for the encoding above; the frontend implements the same.
#[cfg(test)]
pub fn decode(frame: &[u8]) -> std::result::Result<Decoded, &'static str> {
    fn json<T: serde::de::DeserializeOwned>(
        payload: &[u8],
    ) -> std::result::Result<T, &'static str> {
        serde_json::from_slice(payload).map_err(|_| "malformed payload")
    }
    let (&tag, payload) = frame.split_first().ok_or("empty frame")?;
    match tag {
        DATA if payload.is_empty() => Err("empty data frame"),
        DATA => Ok(Decoded::Data(payload.to_vec())),
        STARTED => json(payload).map(|Started { pid }| Decoded::Started { pid }),
        EXITED => json(payload).map(|Exited { code }| Decoded::Exited { code }),
        FAILED => json(payload).map(|DecodedFailed { error }| Decoded::Failed(error)),
        _ => Err("unknown tag"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_tag_round_trips() {
        let error = ApplicationError::new(ErrorCode::ReadFailed, Operation::Terminal);
        let data = [0u8, 0x1b, b'[', 0xff];
        assert_eq!(
            decode(&Frame::Data(&data).encode().unwrap()).unwrap(),
            Decoded::Data(data.to_vec())
        );
        assert_eq!(Frame::Data(b"ab").encode().unwrap(), b"\x00ab");
        assert_eq!(
            Frame::Started { pid: 42 }.encode().unwrap(),
            b"\x01{\"pid\":42}"
        );
        assert_eq!(
            decode(&Frame::Started { pid: 42 }.encode().unwrap()).unwrap(),
            Decoded::Started { pid: 42 }
        );
        for code in [Some(0), Some(3_221_225_786), None] {
            assert_eq!(
                decode(&Frame::Exited { code }.encode().unwrap()).unwrap(),
                Decoded::Exited { code }
            );
        }
        assert_eq!(
            Frame::Exited { code: None }.encode().unwrap(),
            b"\x02{\"code\":null}"
        );
        assert_eq!(
            decode(&Frame::Failed(&error).encode().unwrap()).unwrap(),
            Decoded::Failed(HostFailure {
                code: "read_failed".into(),
                operation: "terminal".into(),
                message: error.message.into(),
            })
        );
    }

    #[test]
    fn unknown_tags_and_truncated_frames_are_refused() {
        assert_eq!(decode(b""), Err("empty frame"));
        assert_eq!(decode(b"\x00"), Err("empty data frame"));
        assert_eq!(decode(b"\x04{}"), Err("unknown tag"));
        assert_eq!(decode(b"\xff"), Err("unknown tag"));
        let started = Frame::Started { pid: 7 }.encode().unwrap();
        for cut in 1..started.len() {
            assert_eq!(decode(&started[..cut]), Err("malformed payload"), "{cut}");
        }
        let exited = Frame::Exited { code: Some(1) }.encode().unwrap();
        assert_eq!(
            decode(&exited[..exited.len() - 1]),
            Err("malformed payload")
        );
        assert_eq!(decode(b"\x01{\"pid\":-1}"), Err("malformed payload"));
    }
}
