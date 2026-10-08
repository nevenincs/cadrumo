//! Bounded length-prefix framing shared by native Unix manager transports.

use super::MAXIMUM_FRAME_BYTES;
use std::io::{self, Read, Write};

pub(crate) struct Frame {
    bytes: Vec<u8>,
    expected: Option<usize>,
}

impl Frame {
    pub(crate) fn new() -> Self {
        Self {
            bytes: Vec::new(),
            expected: None,
        }
    }

    pub(crate) fn read(&mut self, stream: &mut impl Read) -> io::Result<Option<Vec<u8>>> {
        let target = self.expected.map_or(4, |size| size + 4);
        let mut buffer = [0u8; MAXIMUM_FRAME_BYTES];
        let limit = target - self.bytes.len();
        match stream.read(&mut buffer[..limit]) {
            Ok(0) => return Err(io::ErrorKind::UnexpectedEof.into()),
            Ok(count) => self.bytes.extend_from_slice(&buffer[..count]),
            Err(error)
                if matches!(
                    error.kind(),
                    io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                ) =>
            {
                return Ok(None);
            }
            Err(error) => return Err(error),
        }
        if self.expected.is_none() && self.bytes.len() == 4 {
            let length = u32::from_be_bytes(
                self.bytes[..4]
                    .try_into()
                    .map_err(|_| io::ErrorKind::InvalidData)?,
            ) as usize;
            if length == 0 || length > MAXIMUM_FRAME_BYTES {
                return Err(io::ErrorKind::InvalidData.into());
            }
            self.expected = Some(length);
        }
        if self
            .expected
            .is_some_and(|size| self.bytes.len() == size + 4)
        {
            Ok(Some(self.bytes[4..].to_vec()))
        } else {
            Ok(None)
        }
    }
}

pub(crate) fn encode(bytes: &[u8]) -> io::Result<Vec<u8>> {
    if bytes.is_empty() || bytes.len() > MAXIMUM_FRAME_BYTES {
        return Err(io::ErrorKind::InvalidData.into());
    }
    let mut framed = (bytes.len() as u32).to_be_bytes().to_vec();
    framed.extend_from_slice(bytes);
    Ok(framed)
}

pub(crate) fn write_some(
    stream: &mut impl Write,
    bytes: &[u8],
    written: &mut usize,
) -> io::Result<bool> {
    match stream.write(&bytes[*written..]) {
        Ok(0) => return Err(io::ErrorKind::WriteZero.into()),
        Ok(count) => *written += count,
        Err(error)
            if matches!(
                error.kind(),
                io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
            ) => {}
        Err(error) => return Err(error),
    }
    Ok(*written == bytes.len())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ipc::{Request, decode};
    use std::os::unix::net::UnixStream;
    #[test]
    fn framing_handles_partial_header_and_payload_without_blocking() {
        let (mut writer, mut reader) = UnixStream::pair().unwrap();
        reader.set_nonblocking(true).unwrap();
        let payload = br#"{"schema":1,"request":"retry"}"#;
        let encoded = encode(payload).unwrap();
        let mut frame = Frame::new();
        assert!(frame.read(&mut reader).unwrap().is_none());
        writer.write_all(&encoded[..2]).unwrap();
        assert!(frame.read(&mut reader).unwrap().is_none());
        writer.write_all(&encoded[2..6]).unwrap();
        assert!(frame.read(&mut reader).unwrap().is_none());
        assert!(frame.read(&mut reader).unwrap().is_none());
        writer.write_all(&encoded[6..]).unwrap();
        assert_eq!(
            decode(&frame.read(&mut reader).unwrap().unwrap()).unwrap(),
            Request::Retry { schema: 1 }
        );
    }

    #[test]
    fn oversized_or_empty_frames_refuse_before_allocating_payload() {
        for length in [0, MAXIMUM_FRAME_BYTES as u32 + 1, u32::MAX] {
            let (mut writer, mut reader) = UnixStream::pair().unwrap();
            reader.set_nonblocking(true).unwrap();
            writer.write_all(&length.to_be_bytes()).unwrap();
            let mut frame = Frame::new();
            assert_eq!(
                frame.read(&mut reader).unwrap_err().kind(),
                io::ErrorKind::InvalidData
            );
            assert_eq!(frame.bytes.len(), 4);
        }
    }
}
