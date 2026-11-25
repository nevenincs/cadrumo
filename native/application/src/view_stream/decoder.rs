//! The downstream frame state machine: what a window makes of the frames it reads.
//!
//! [`DownstreamDecoder`] takes one frame at a time, of kind `J` or `B`, and
//! returns the document, complete image or transfer chunk it completes, or
//! nothing when the frame only advances an image or is a chunk a cancel
//! discards. It holds no I/O, so the shared vectors drive it directly.
//!
//! `view.image` is consumed here and returned only with its assembled bytes. A
//! `B` frame without an announcement, a document inside an image, a transfer
//! chunk inside an image's chunk run, or any other kind is a violation, and
//! so is every transfer rule the [`TransferReceiver`] enforces. A violation
//! drops the partial image and must end the connection.

use super::{
    Violation,
    chunks::{AssembledImage, ImageAssembler, KIND_CHUNK, KIND_DOCUMENT, is_transfer_chunk},
    documents::ViewDownstream,
    transfer::{TransferChunk, TransferReceiver},
};
use std::{fmt, sync::Arc};

/// What one frame completed.
pub enum Downstream {
    Image(AssembledImage),
    /// Any document but `view.image`, which the decoder consumes.
    Document(ViewDownstream),
    Chunk(TransferChunk),
}

impl fmt::Debug for Downstream {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("Downstream(..)")
    }
}

pub struct DownstreamDecoder {
    assembler: ImageAssembler,
    transfers: Arc<TransferReceiver>,
}

impl DownstreamDecoder {
    /// Reads a connection whose downloads `transfers` receives.
    pub fn new(transfers: Arc<TransferReceiver>) -> Self {
        Self {
            assembler: ImageAssembler::default(),
            transfers,
        }
    }

    /// Takes one frame's kind and payload.
    pub fn push(&mut self, kind: u8, payload: &[u8]) -> Result<Option<Downstream>, Violation> {
        let outcome = self.step(kind, payload);
        if outcome.is_err() {
            self.assembler.discard();
        }
        outcome
    }

    /// Zeroes and drops any partial image.
    pub fn discard(&mut self) {
        self.assembler.discard();
    }

    fn step(&mut self, kind: u8, payload: &[u8]) -> Result<Option<Downstream>, Violation> {
        match kind {
            KIND_CHUNK if is_transfer_chunk(payload) => {
                if self.assembler.assembling() {
                    // An image's chunks run unbroken; a transfer chunk inside them is an interleaving.
                    return Err(Violation("view_image_interleaved"));
                }
                Ok(self.transfers.accept(payload)?.map(Downstream::Chunk))
            }
            KIND_CHUNK => Ok(self.assembler.accept(payload)?.map(Downstream::Image)),
            KIND_DOCUMENT => {
                if self.assembler.assembling() {
                    return Err(Violation("view_image_interleaved"));
                }
                let document = ViewDownstream::decode(payload)?;
                match &document {
                    ViewDownstream::TransferComplete(complete) => {
                        self.transfers.observe_complete(complete)?;
                    }
                    ViewDownstream::TransferCancel(cancel) => {
                        self.transfers.observe_cancel(cancel)?;
                    }
                    _ => {}
                }
                if let ViewDownstream::Image(announcement) = document {
                    self.assembler.announce(announcement)?;
                    return Ok(None);
                }
                Ok(Some(Downstream::Document(document)))
            }
            _ => Err(Violation("view_frame")),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::view_stream::{
        documents::ViewTransferDirection,
        vectors::{self, chunk_payload, sha256_hex},
    };
    use serde_json::Value;

    #[derive(Debug, PartialEq, Eq)]
    enum Output {
        Image {
            sequence: u32,
            byte_length: u32,
            sha256: String,
        },
        Document(String),
        Chunk {
            transfer_id: u32,
            offset: u64,
            length: usize,
            last: bool,
            sha256: String,
        },
    }

    fn expected(stream: &Value) -> Vec<Output> {
        stream["expect"]
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or_default()
            .iter()
            .map(|entry| {
                if let Some(image) = entry.get("image") {
                    Output::Image {
                        sequence: image["sequence"].as_u64().unwrap() as u32,
                        byte_length: image["byte_length"].as_u64().unwrap() as u32,
                        sha256: image["sha256"].as_str().unwrap().to_owned(),
                    }
                } else if let Some(chunk) = entry.get("chunk") {
                    Output::Chunk {
                        transfer_id: chunk["transfer_id"].as_u64().unwrap() as u32,
                        offset: chunk["offset"].as_u64().unwrap(),
                        length: chunk["length"].as_u64().unwrap() as usize,
                        last: chunk["last"].as_bool().unwrap(),
                        sha256: chunk["sha256"].as_str().unwrap().to_owned(),
                    }
                } else {
                    Output::Document(entry["document"].as_str().unwrap().to_owned())
                }
            })
            .collect()
    }

    fn observed(downstream: Downstream) -> Output {
        match downstream {
            Downstream::Image(image) => Output::Image {
                sequence: image.announcement.sequence,
                byte_length: image.announcement.byte_length,
                sha256: sha256_hex(&image.data),
            },
            Downstream::Document(document) => Output::Document(document.kind().to_owned()),
            Downstream::Chunk(chunk) => Output::Chunk {
                transfer_id: chunk.transfer_id,
                offset: chunk.offset,
                length: chunk.data.len(),
                last: chunk.last,
                sha256: sha256_hex(&chunk.data),
            },
        }
    }

    /// Runs one vector stream; returns what was produced and the step that refused.
    fn run(decoder: &mut DownstreamDecoder, stream: &Value) -> (Vec<Output>, Option<usize>) {
        let mut outputs = Vec::new();
        for (index, step) in stream["steps"].as_array().unwrap().iter().enumerate() {
            let (kind, payload) = if let Some(chunk) = step.get("chunk") {
                (KIND_CHUNK, chunk_payload(chunk))
            } else {
                let document = step
                    .get("announce")
                    .or_else(|| step.get("document"))
                    .expect("a step is a chunk, an announcement or a document");
                (KIND_DOCUMENT, serde_json::to_vec(document).unwrap())
            };
            match decoder.push(kind, &payload) {
                Ok(Some(output)) => outputs.push(observed(output)),
                Ok(None) => {}
                Err(_) => return (outputs, Some(index)),
            }
        }
        (outputs, None)
    }

    #[test]
    fn image_streams_in_the_vectors_assemble_or_refuse_as_python_does() {
        let vectors = vectors::load();
        let streams = vectors.array("streams");
        assert!(streams.len() >= 15);
        for stream in streams {
            let name = stream["name"].as_str().unwrap();
            let mut decoder = DownstreamDecoder::new(Arc::new(TransferReceiver::new(
                ViewTransferDirection::Download,
            )));
            let (outputs, refused_at) = run(&mut decoder, stream);
            assert_eq!(
                refused_at,
                stream["refused_at"].as_u64().map(|index| index as usize),
                "{name}"
            );
            if refused_at.is_none() {
                assert_eq!(outputs, expected(stream), "{name}");
            }
        }
    }

    #[test]
    fn downstream_transfer_streams_in_the_vectors_run_as_python_runs_them() {
        let vectors = vectors::load();
        let mut ran = 0;
        for stream in vectors.array("transfer_streams") {
            if stream["direction"] != "downstream" {
                continue;
            }
            let name = stream["name"].as_str().unwrap();
            let receiver = Arc::new(TransferReceiver::new(ViewTransferDirection::Download));
            for setup in stream["setup"].as_array().unwrap() {
                if let Some(expect) = setup.get("expect") {
                    receiver
                        .expect(
                            expect["transfer_id"].as_u64().unwrap() as u32,
                            expect["size"].as_u64(),
                        )
                        .unwrap();
                } else if let Some(grant) = setup.get("grant") {
                    receiver
                        .grant(
                            grant["transfer_id"].as_u64().unwrap() as u32,
                            grant["chunks"].as_u64().unwrap() as u8,
                        )
                        .unwrap();
                } else if let Some(cancel) = setup.get("cancel") {
                    receiver.cancel(cancel["transfer_id"].as_u64().unwrap() as u32);
                }
            }
            let mut decoder = DownstreamDecoder::new(receiver);
            let (outputs, refused_at) = run(&mut decoder, stream);
            assert_eq!(
                refused_at,
                stream["refused_at"].as_u64().map(|index| index as usize),
                "{name}"
            );
            if refused_at.is_none() {
                assert_eq!(outputs, expected(stream), "{name}");
            }
            ran += 1;
        }
        assert!(ran >= 20, "{ran}");
    }

    #[test]
    fn a_violation_drops_the_partial_image_and_a_refused_assembler_stays_refused() {
        let mut decoder = DownstreamDecoder::new(Arc::new(TransferReceiver::new(
            ViewTransferDirection::Download,
        )));
        let announce = serde_json::json!({
            "kind": "view.image", "sequence": 1, "byte_length": 65521, "pixel_width": 4,
            "pixel_height": 4, "css_width": 4, "css_height": 4, "scale": 1.0
        });
        assert!(
            decoder
                .push(KIND_DOCUMENT, &serde_json::to_vec(&announce).unwrap())
                .unwrap()
                .is_none()
        );
        assert_eq!(
            decoder.push(KIND_DOCUMENT, b"{}").unwrap_err(),
            Violation("view_image_interleaved")
        );
        // The announced image is gone, so a chunk of it has nothing to join.
        assert_eq!(
            decoder.push(KIND_CHUNK, &[0; 17]).unwrap_err(),
            Violation("view_chunk_unannounced")
        );
        assert_eq!(
            decoder.push(KIND_CHUNK, &[0; 17]).unwrap_err(),
            Violation("view_stream_refused")
        );
        assert_eq!(
            decoder.push(b'S', b"x").unwrap_err(),
            Violation("view_frame")
        );
    }
}
