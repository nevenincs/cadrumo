//! The `B` frame kind: image and transfer chunks, and the frames around them.
//!
//! A frame is `kind || u32 length || payload`, the length in network order, at
//! most [`MAXIMUM_FRAME_BYTES`]. A `B` payload is a 16-byte header, all
//! integers in network order, followed by the chunk body. Flag bit 1 says what
//! the chunk carries. Clear, it carries part of an image:
//!
//! | offset | bytes | field |
//! |---|---|---|
//! | 0 | 1 | version, always 1 |
//! | 1 | 1 | flags: bit 0 marks the last chunk, every other bit is zero |
//! | 2 | 2 | reserved, zero |
//! | 4 | 4 | image sequence, equal to the announcing `view.image` |
//! | 8 | 2 | chunk index, from zero |
//! | 10 | 2 | chunk count, `ceil(image length / 65,520)` |
//! | 12 | 4 | image length, 1 to 2 MiB, equal to `byte_length` |
//!
//! Set, it carries part of a download or upload:
//!
//! | offset | bytes | field |
//! |---|---|---|
//! | 0 | 1 | version, always 1 |
//! | 1 | 1 | flags: bit 0 marks the last chunk, bit 1 is set, every other bit is zero |
//! | 2 | 2 | reserved, zero |
//! | 4 | 4 | transfer id, from 1 |
//! | 8 | 8 | byte offset of the chunk's first body byte |
//!
//! Every chunk but the last carries exactly [`CHUNK_BODY_BYTES`] body bytes. An
//! image is announced by `view.image`, and its chunks follow at once,
//! contiguous and in order, before any other frame. Anything else is a
//! violation. The check names are the Python codec's own.

use super::{
    Violation,
    documents::{IMAGE_MAX_BYTES, ViewImage},
};
use std::fmt;
use zeroize::{Zeroize, Zeroizing};

pub const KIND_DOCUMENT: u8 = b'J';
pub const KIND_CHUNK: u8 = b'B';
pub const MAXIMUM_FRAME_BYTES: usize = 64 * 1024;
pub const CHUNK_HEADER_BYTES: usize = 16;
/// The body every chunk but a stream's last carries.
pub const CHUNK_BODY_BYTES: usize = MAXIMUM_FRAME_BYTES - CHUNK_HEADER_BYTES;

const VERSION: u8 = 1;
const LAST_FLAG: u8 = 0x01;
const TRANSFER_FLAG: u8 = 0x02;

/// Frames one payload under a one-byte kind and its network-order size. The
/// frame holds private bytes, so it is wiped when dropped.
pub fn encode_frame(kind: u8, payload: &[u8]) -> Result<Zeroizing<Vec<u8>>, Violation> {
    if payload.is_empty() || payload.len() > MAXIMUM_FRAME_BYTES {
        return Err(Violation("view_frame"));
    }
    let size = u32::try_from(payload.len()).map_err(|_| Violation("view_frame"))?;
    let mut frame = Zeroizing::new(Vec::with_capacity(5 + payload.len()));
    frame.push(kind);
    frame.extend_from_slice(&size.to_be_bytes());
    frame.extend_from_slice(payload);
    Ok(frame)
}

/// How many chunks carry an image of `image_length` bytes.
pub fn image_chunk_count(image_length: u32) -> Result<u16, Violation> {
    if !(1..=IMAGE_MAX_BYTES).contains(&image_length) {
        return Err(Violation("view_image_length"));
    }
    let chunks = image_length.div_ceil(CHUNK_BODY_BYTES as u32);
    u16::try_from(chunks).map_err(|_| Violation("view_image_length"))
}

/// Whether a `B` payload's flags say it carries a transfer rather than an image.
pub fn is_transfer_chunk(payload: &[u8]) -> bool {
    payload
        .get(1)
        .is_some_and(|flags| flags & TRANSFER_FLAG != 0)
}

/// One validated image chunk header; the last chunk follows from index and count.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ImageChunkHeader {
    pub sequence: u32,
    pub chunk_index: u16,
    pub chunk_count: u16,
    pub image_length: u32,
}

impl ImageChunkHeader {
    /// Validates a header's fields against each other.
    pub fn new(
        sequence: u32,
        chunk_index: u16,
        chunk_count: u16,
        image_length: u32,
    ) -> Result<Self, Violation> {
        if chunk_count != image_chunk_count(image_length)? {
            return Err(Violation("view_chunk_count"));
        }
        if chunk_index >= chunk_count {
            return Err(Violation("view_chunk_index"));
        }
        Ok(Self {
            sequence,
            chunk_index,
            chunk_count,
            image_length,
        })
    }

    /// Whether this chunk ends its image.
    pub fn last(&self) -> bool {
        self.chunk_index == self.chunk_count.saturating_sub(1)
    }

    /// The exact body length this chunk must carry.
    pub fn body_length(&self) -> usize {
        if self.last() {
            let before = CHUNK_BODY_BYTES * usize::from(self.chunk_count.saturating_sub(1));
            (self.image_length as usize).saturating_sub(before)
        } else {
            CHUNK_BODY_BYTES
        }
    }

    /// Validates a `B` payload's header and body length, returning the header.
    pub fn decode(payload: &[u8]) -> Result<Self, Violation> {
        let Some((header, body)) = payload.split_first_chunk::<CHUNK_HEADER_BYTES>() else {
            return Err(Violation("view_chunk_header_length"));
        };
        let [
            version,
            flags,
            reserved_high,
            reserved_low,
            s0,
            s1,
            s2,
            s3,
            i0,
            i1,
            c0,
            c1,
            l0,
            l1,
            l2,
            l3,
        ] = *header;
        if version != VERSION {
            return Err(Violation("view_chunk_version"));
        }
        if reserved_high != 0 || reserved_low != 0 || flags & !LAST_FLAG != 0 {
            return Err(Violation("view_chunk_reserved"));
        }
        let parsed = Self::new(
            u32::from_be_bytes([s0, s1, s2, s3]),
            u16::from_be_bytes([i0, i1]),
            u16::from_be_bytes([c0, c1]),
            u32::from_be_bytes([l0, l1, l2, l3]),
        )?;
        if (flags & LAST_FLAG != 0) != parsed.last() {
            return Err(Violation("view_chunk_last_flag"));
        }
        if body.len() != parsed.body_length() {
            return Err(Violation("view_chunk_body_length"));
        }
        Ok(parsed)
    }
}

/// One validated transfer chunk header; `body_length` is what the chunk carries.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TransferChunkHeader {
    pub transfer_id: u32,
    pub offset: u64,
    pub last: bool,
    pub body_length: usize,
}

impl TransferChunkHeader {
    /// Validates a header's fields against each other.
    pub fn new(
        transfer_id: u32,
        offset: u64,
        last: bool,
        body_length: usize,
    ) -> Result<Self, Violation> {
        if transfer_id == 0 {
            return Err(Violation("view_transfer_id"));
        }
        if !offset.is_multiple_of(CHUNK_BODY_BYTES as u64) {
            return Err(Violation("view_transfer_offset"));
        }
        // Only an empty file has an empty chunk, and then it is the one chunk.
        let admitted = if last {
            body_length <= CHUNK_BODY_BYTES && (body_length > 0 || offset == 0)
        } else {
            body_length == CHUNK_BODY_BYTES
        };
        if !admitted {
            return Err(Violation("view_transfer_body_length"));
        }
        Ok(Self {
            transfer_id,
            offset,
            last,
            body_length,
        })
    }

    /// The 16 header bytes.
    pub fn encode(&self) -> [u8; CHUNK_HEADER_BYTES] {
        let flags = TRANSFER_FLAG | if self.last { LAST_FLAG } else { 0 };
        let mut header = [0u8; CHUNK_HEADER_BYTES];
        header[0] = VERSION;
        header[1] = flags;
        header[4..8].copy_from_slice(&self.transfer_id.to_be_bytes());
        header[8..16].copy_from_slice(&self.offset.to_be_bytes());
        header
    }

    /// Validates a transfer `B` payload's header and body length, returning the header.
    pub fn decode(payload: &[u8]) -> Result<Self, Violation> {
        let Some((header, body)) = payload.split_first_chunk::<CHUNK_HEADER_BYTES>() else {
            return Err(Violation("view_chunk_header_length"));
        };
        let [
            version,
            flags,
            reserved_high,
            reserved_low,
            i0,
            i1,
            i2,
            i3,
            o0,
            o1,
            o2,
            o3,
            o4,
            o5,
            o6,
            o7,
        ] = *header;
        if version != VERSION {
            return Err(Violation("view_chunk_version"));
        }
        if reserved_high != 0 || reserved_low != 0 || flags & !(LAST_FLAG | TRANSFER_FLAG) != 0 {
            return Err(Violation("view_chunk_reserved"));
        }
        if flags & TRANSFER_FLAG == 0 {
            return Err(Violation("view_transfer_flag"));
        }
        Self::new(
            u32::from_be_bytes([i0, i1, i2, i3]),
            u64::from_be_bytes([o0, o1, o2, o3, o4, o5, o6, o7]),
            flags & LAST_FLAG != 0,
            body.len(),
        )
    }
}

/// One complete image with the announcement that described it.
pub struct AssembledImage {
    pub announcement: ViewImage,
    pub data: Zeroizing<Vec<u8>>,
}

impl fmt::Debug for AssembledImage {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("AssembledImage(..)")
    }
}

/// Reassembles announced images from their chunks, refusing every violation.
///
/// Sequences strictly increase across images and may skip values. A refusal
/// zeroes the partial image and leaves the assembler unusable.
#[derive(Default)]
pub struct ImageAssembler {
    announcement: Option<ViewImage>,
    buffer: Zeroizing<Vec<u8>>,
    next_index: u16,
    last_sequence: Option<u32>,
    refused: bool,
}

impl ImageAssembler {
    /// Whether an announced image still awaits chunks.
    pub fn assembling(&self) -> bool {
        self.announcement.is_some()
    }

    /// Begins the announced image; one already in progress makes this an interleaving.
    pub fn announce(&mut self, announcement: ViewImage) -> Result<(), Violation> {
        self.require_usable()?;
        if let Err(violation) = announcement.validate() {
            return Err(self.refuse(violation.check()));
        }
        if self.announcement.is_some() {
            return Err(self.refuse("view_image_interleaved"));
        }
        if self
            .last_sequence
            .is_some_and(|last| announcement.sequence <= last)
        {
            return Err(self.refuse("view_image_sequence"));
        }
        self.last_sequence = Some(announcement.sequence);
        self.buffer = Zeroizing::new(vec![0u8; announcement.byte_length as usize]);
        self.next_index = 0;
        self.announcement = Some(announcement);
        Ok(())
    }

    /// Adds one `B` payload; returns the image once its last chunk arrives.
    pub fn accept(&mut self, payload: &[u8]) -> Result<Option<AssembledImage>, Violation> {
        self.require_usable()?;
        let Some(announcement) = self.announcement else {
            return Err(self.refuse("view_chunk_unannounced"));
        };
        let Ok(header) = ImageChunkHeader::decode(payload) else {
            return Err(self.refuse("view_chunk_header"));
        };
        if header.sequence != announcement.sequence {
            return Err(self.refuse("view_image_interleaved"));
        }
        if header.image_length != announcement.byte_length {
            return Err(self.refuse("view_image_announcement"));
        }
        if header.chunk_index != self.next_index {
            return Err(self.refuse("view_chunk_order"));
        }
        let offset = usize::from(header.chunk_index) * CHUNK_BODY_BYTES;
        let body = &payload[CHUNK_HEADER_BYTES..];
        let Some(target) = self.buffer.get_mut(offset..offset + body.len()) else {
            return Err(self.refuse("view_chunk_body_length"));
        };
        target.copy_from_slice(body);
        self.next_index += 1;
        if !header.last() {
            return Ok(None);
        }
        let data = Zeroizing::new(std::mem::take(&mut *self.buffer));
        self.clear();
        Ok(Some(AssembledImage { announcement, data }))
    }

    /// Zeroes and drops any partial image.
    pub fn discard(&mut self) {
        self.clear();
    }

    fn clear(&mut self) {
        self.buffer.zeroize();
        self.announcement = None;
        self.next_index = 0;
    }

    fn refuse(&mut self, check: &'static str) -> Violation {
        self.clear();
        self.refused = true;
        Violation(check)
    }

    fn require_usable(&self) -> Result<(), Violation> {
        if self.refused {
            return Err(Violation("view_stream_refused"));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::view_stream::vectors::{self, hex_bytes};

    #[test]
    fn the_layout_constants_are_the_vectors() {
        let vectors = vectors::load();
        assert_eq!(
            vectors.layout("frame_max_bytes"),
            MAXIMUM_FRAME_BYTES as u64
        );
        assert_eq!(
            vectors.layout("chunk_header_bytes"),
            CHUNK_HEADER_BYTES as u64
        );
        assert_eq!(vectors.layout("chunk_body_bytes"), CHUNK_BODY_BYTES as u64);
        assert_eq!(
            vectors.layout("image_max_bytes"),
            u64::from(IMAGE_MAX_BYTES)
        );
        assert_eq!(vectors.layout("version"), u64::from(VERSION));
        assert_eq!(vectors.layout("last_flag"), u64::from(LAST_FLAG));
        assert_eq!(vectors.layout("transfer_flag"), u64::from(TRANSFER_FLAG));
        assert_eq!(vectors.layout_text("frame_kind").as_bytes(), [KIND_CHUNK]);
        assert_eq!(
            vectors.layout_text("control_frame_kind").as_bytes(),
            [KIND_DOCUMENT]
        );
    }

    fn payload_of(header: &str, body_length: u64) -> Vec<u8> {
        let mut payload = hex_bytes(header);
        payload.resize(payload.len() + body_length as usize, 0);
        payload
    }

    #[test]
    fn image_headers_in_the_vectors_decode_to_their_fields() {
        for entry in vectors::load().array("headers") {
            let name = entry["name"].as_str().unwrap();
            let payload = payload_of(
                entry["header"].as_str().unwrap(),
                entry["body_length"].as_u64().unwrap(),
            );
            let header = ImageChunkHeader::decode(&payload)
                .unwrap_or_else(|violation| panic!("{name}: {violation}"));
            assert_eq!(u64::from(header.sequence), entry["sequence"], "{name}");
            assert_eq!(
                u64::from(header.chunk_index),
                entry["chunk_index"],
                "{name}"
            );
            assert_eq!(
                u64::from(header.chunk_count),
                entry["chunk_count"],
                "{name}"
            );
            assert_eq!(
                u64::from(header.image_length),
                entry["image_length"],
                "{name}"
            );
            assert_eq!(header.last(), entry["last"].as_bool().unwrap(), "{name}");
            assert_eq!(header.body_length() as u64, entry["body_length"], "{name}");
        }
    }

    #[test]
    fn image_headers_in_the_vectors_are_refused_with_the_python_check() {
        for entry in vectors::load().array("header_refusals") {
            let name = entry["name"].as_str().unwrap();
            let payload = payload_of(
                entry["header"].as_str().unwrap(),
                entry["body_length"].as_u64().unwrap(),
            );
            assert_eq!(
                ImageChunkHeader::decode(&payload).unwrap_err().check(),
                entry["check"].as_str().unwrap(),
                "{name}"
            );
        }
    }

    #[test]
    fn transfer_headers_in_the_vectors_decode_encode_and_are_refused_as_python_does() {
        let vectors = vectors::load();
        for entry in vectors.array("transfer_headers") {
            let name = entry["name"].as_str().unwrap();
            let payload = payload_of(
                entry["header"].as_str().unwrap(),
                entry["body_length"].as_u64().unwrap(),
            );
            let header = TransferChunkHeader::decode(&payload)
                .unwrap_or_else(|violation| panic!("{name}: {violation}"));
            assert_eq!(
                u64::from(header.transfer_id),
                entry["transfer_id"],
                "{name}"
            );
            assert_eq!(header.offset, entry["offset"].as_u64().unwrap(), "{name}");
            assert_eq!(header.last, entry["last"].as_bool().unwrap(), "{name}");
            assert_eq!(header.body_length as u64, entry["body_length"], "{name}");
            assert_eq!(
                header.encode().to_vec(),
                hex_bytes(entry["header"].as_str().unwrap()),
                "{name}"
            );
            assert!(is_transfer_chunk(&payload), "{name}");
        }
        for entry in vectors.array("transfer_header_refusals") {
            let name = entry["name"].as_str().unwrap();
            let payload = payload_of(
                entry["header"].as_str().unwrap(),
                entry["body_length"].as_u64().unwrap(),
            );
            assert_eq!(
                TransferChunkHeader::decode(&payload).unwrap_err().check(),
                entry["check"].as_str().unwrap(),
                "{name}"
            );
        }
    }

    #[test]
    fn an_image_header_that_sets_the_transfer_flag_is_not_an_image_chunk() {
        let payload = payload_of("01020000000000000000000100000001", 1);
        assert!(is_transfer_chunk(&payload));
        assert_eq!(
            ImageChunkHeader::decode(&payload),
            Err(Violation("view_chunk_reserved"))
        );
        assert!(!is_transfer_chunk(&[]));
        assert!(!is_transfer_chunk(&[1]));
    }

    #[test]
    fn chunk_counts_cover_the_image_bounds() {
        assert_eq!(image_chunk_count(1), Ok(1));
        assert_eq!(image_chunk_count(65_520), Ok(1));
        assert_eq!(image_chunk_count(65_521), Ok(2));
        assert_eq!(image_chunk_count(IMAGE_MAX_BYTES), Ok(33));
        assert_eq!(image_chunk_count(0), Err(Violation("view_image_length")));
        assert_eq!(
            image_chunk_count(IMAGE_MAX_BYTES + 1),
            Err(Violation("view_image_length"))
        );
    }

    #[test]
    fn frames_are_kind_length_payload_and_bounded() {
        let frame = encode_frame(KIND_DOCUMENT, b"{}").unwrap();
        assert_eq!(frame.as_slice(), [b'J', 0, 0, 0, 2, b'{', b'}']);
        assert!(encode_frame(KIND_CHUNK, &[]).is_err());
        assert!(encode_frame(KIND_CHUNK, &vec![0; MAXIMUM_FRAME_BYTES]).is_ok());
        assert!(encode_frame(KIND_CHUNK, &vec![0; MAXIMUM_FRAME_BYTES + 1]).is_err());
    }
}
