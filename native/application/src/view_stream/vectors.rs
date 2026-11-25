//! Test access to the shared conformance vectors.
//!
//! The vectors are the Python codec's own test data, read in place from
//! `src/cadrumo_client/contracts/tests/view_stream_vectors.json`; the Rust
//! tests never keep a copy. The file describes itself in its `about` member.

use crate::value::Sha256Digest;
use serde_json::Value;

const VECTORS: &str =
    include_str!("../../../../src/cadrumo_client/contracts/tests/view_stream_vectors.json");

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Direction {
    Downstream,
    Upstream,
}

impl Direction {
    fn named(name: &str) -> Self {
        match name {
            "downstream" => Self::Downstream,
            "upstream" => Self::Upstream,
            other => panic!("unknown direction {other}"),
        }
    }
}

pub struct Vectors(Value);

pub fn load() -> Vectors {
    let root: Value = serde_json::from_str(VECTORS).expect("the vectors file is JSON");
    assert_eq!(root["schema"], 1, "the vectors schema changed");
    Vectors(root)
}

/// One control document the vectors say a direction accepts or refuses.
pub struct DocumentEntry {
    pub name: String,
    pub direction: Direction,
    pub document: Value,
}

impl DocumentEntry {
    /// The document as a `J` payload.
    pub fn payload(&self) -> Vec<u8> {
        serde_json::to_vec(&self.document).expect("a document encodes")
    }
}

impl Vectors {
    pub fn layout(&self, key: &str) -> u64 {
        self.0["layout"][key]
            .as_u64()
            .unwrap_or_else(|| panic!("layout.{key}"))
    }

    pub fn layout_text(&self, key: &str) -> &str {
        self.0["layout"][key]
            .as_str()
            .unwrap_or_else(|| panic!("layout.{key}"))
    }

    pub fn array(&self, key: &str) -> &[Value] {
        self.0[key]
            .as_array()
            .unwrap_or_else(|| panic!("{key} is an array"))
    }

    fn documents(&self, member: &str) -> Vec<DocumentEntry> {
        self.0["documents"][member]
            .as_array()
            .unwrap_or_else(|| panic!("documents.{member}"))
            .iter()
            .map(|entry| DocumentEntry {
                name: entry["name"].as_str().expect("name").to_owned(),
                direction: Direction::named(entry["direction"].as_str().expect("direction")),
                document: entry["document"].clone(),
            })
            .collect()
    }

    pub fn accepted_documents(&self) -> Vec<DocumentEntry> {
        self.documents("accepted")
    }

    pub fn refused_documents(&self) -> Vec<DocumentEntry> {
        self.documents("refused")
    }
}

pub fn hex_bytes(hex: &str) -> Vec<u8> {
    assert!(hex.len().is_multiple_of(2), "{hex}");
    (0..hex.len())
        .step_by(2)
        .map(|index| u8::from_str_radix(&hex[index..index + 2], 16).expect("hex"))
        .collect()
}

/// The bytes the vectors name: byte `k` of an image or transfer is `k mod 251`.
pub fn pattern(offset: u64, length: usize) -> Vec<u8> {
    (offset..offset + length as u64)
        .map(|position| u8::try_from(position % 251).expect("below 251"))
        .collect()
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    Sha256Digest::of(bytes).to_string()
}

/// A `B` payload a stream step describes: its header, then the pattern body.
pub fn chunk_payload(chunk: &Value) -> Vec<u8> {
    let mut payload = hex_bytes(chunk["header"].as_str().expect("header"));
    payload.extend(pattern(
        chunk["body_offset"].as_u64().expect("body_offset"),
        chunk["body_length"].as_u64().expect("body_length") as usize,
    ));
    payload
}
