//! File transfers on a view connection: the receiving and the sending end.
//!
//! A download carries a file from the page toward the window, an upload the
//! file the person chose toward the page. A `J` document announces and closes
//! each transfer, and `B` chunks carry its bytes. Each transfer has its own
//! credit, counted in chunks and granted by the receiver, so a file never
//! waits on an image and no file byte is ever dropped. Credit bounds only
//! what is in flight; nothing here caps a file's size, a file count or a rate.
//!
//! [`TransferReceiver`] checks every chunk and the closing document against
//! what was expected, granted and received. [`TransferSender`] cuts a source
//! into ordered chunks, one per unit of credit, and totals the bytes and
//! their sha256 for the closing document. Bytes are held in wiped buffers.

use super::{
    Violation,
    chunks::{CHUNK_BODY_BYTES, CHUNK_HEADER_BYTES, TransferChunkHeader},
    documents::{
        TRANSFER_CREDIT_MAX_CHUNKS, ViewTransferCancel, ViewTransferComplete, ViewTransferCredit,
        ViewTransferDirection,
    },
};
use crate::value::Sha256Digest;
use sha2::{Digest, Sha256};
use std::{
    collections::HashMap,
    fmt,
    io::{self, Read},
    sync::{Arc, Condvar, Mutex, MutexGuard},
};
use zeroize::Zeroizing;

fn digest_hex(hasher: &Sha256) -> String {
    Sha256Digest::from_hash(hasher.clone().finalize()).map_or_else(|_| String::new(), String::from)
}

/// One checked chunk of an expected transfer, for the receiver to write out in order.
pub struct TransferChunk {
    pub transfer_id: u32,
    pub offset: u64,
    pub data: Zeroizing<Vec<u8>>,
    pub last: bool,
}

impl fmt::Debug for TransferChunk {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("TransferChunk(..)")
    }
}

struct Inbound {
    declared_size: Option<u64>,
    received: u64,
    credit: u8,
    last_seen: bool,
    cancelled: bool,
    digest: Sha256,
}

#[derive(Default)]
struct ReceiverState {
    transfers: HashMap<u32, Inbound>,
    last_id: u32,
    streaming: Option<u32>,
    refused: bool,
}

impl ReceiverState {
    fn require_usable(&self) -> Result<(), Violation> {
        if self.refused {
            return Err(Violation("view_stream_refused"));
        }
        Ok(())
    }

    fn refuse(&mut self, check: &'static str) -> Violation {
        self.transfers.clear();
        self.streaming = None;
        self.refused = true;
        Violation(check)
    }
}

/// Checks the transfers one end of a view connection receives, refusing every violation.
///
/// The application names each transfer it is ready to take with `expect` and
/// admits chunks with `grant`. A chunk of any other transfer, one beyond the
/// credit granted, or one out of order is a violation. At most one transfer
/// streams at a time: once a transfer's first chunk has arrived, a chunk of
/// another transfer before its last is an interleaving, while documents and
/// whole images may sit between chunks. A transfer ends with the sender's
/// `view.transfer_complete`, which must agree in size and sha256 with the
/// bytes received, and in size with the sender's declared size when it gave
/// one. A violation of the connection's bytes leaves the receiver unusable
/// and must close the connection; a refused call of the application's own
/// (`expect`, `grant`) leaves it usable.
///
/// `expect`, `grant` and `cancel` belong to the application; `accept` and
/// the `observe` methods belong to the connection's reader, which runs on
/// another thread.
pub struct TransferReceiver {
    direction: ViewTransferDirection,
    state: Mutex<ReceiverState>,
}

impl TransferReceiver {
    /// Receives the transfers whose bytes travel in `direction`.
    pub fn new(direction: ViewTransferDirection) -> Self {
        Self {
            direction,
            state: Mutex::new(ReceiverState::default()),
        }
    }

    pub fn direction(&self) -> ViewTransferDirection {
        self.direction
    }

    fn lock(&self) -> MutexGuard<'_, ReceiverState> {
        self.state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    /// Registers a transfer this end will receive; ids strictly increase.
    /// `size` is the exact byte count the sender declared, or `None`.
    pub fn expect(&self, transfer_id: u32, size: Option<u64>) -> Result<(), Violation> {
        let mut state = self.lock();
        state.require_usable()?;
        if transfer_id <= state.last_id {
            return Err(Violation("view_transfer_id"));
        }
        state.last_id = transfer_id;
        state.transfers.insert(
            transfer_id,
            Inbound {
                declared_size: size,
                received: 0,
                credit: 0,
                last_seen: false,
                cancelled: false,
                digest: Sha256::new(),
            },
        );
        Ok(())
    }

    /// Admits `chunks` more chunks of a transfer; returns the credit document to send.
    pub fn grant(&self, transfer_id: u32, chunks: u8) -> Result<ViewTransferCredit, Violation> {
        let mut state = self.lock();
        state.require_usable()?;
        let Some(transfer) = state.transfers.get_mut(&transfer_id) else {
            return Err(Violation("view_transfer_unknown"));
        };
        if transfer.cancelled || transfer.last_seen {
            return Err(Violation("view_transfer_closed"));
        }
        if chunks < 1
            || u16::from(transfer.credit) + u16::from(chunks)
                > u16::from(TRANSFER_CREDIT_MAX_CHUNKS)
        {
            return Err(Violation("view_transfer_credit"));
        }
        transfer.credit += chunks;
        Ok(ViewTransferCredit {
            transfer_id,
            chunks,
        })
    }

    /// Stops receiving a transfer; returns the cancel document to send, if one is due.
    ///
    /// Chunks the sender had already sent are discarded until the sender's own
    /// cancel or completion arrives.
    pub fn cancel(&self, transfer_id: u32) -> Option<ViewTransferCancel> {
        let mut state = self.lock();
        let transfer = state.transfers.get_mut(&transfer_id)?;
        if transfer.cancelled {
            return None;
        }
        transfer.cancelled = true;
        Some(ViewTransferCancel {
            direction: self.direction,
            transfer_id,
        })
    }

    /// Checks one transfer `B` payload; returns its chunk, or `None` when a cancel discards it.
    pub fn accept(&self, payload: &[u8]) -> Result<Option<TransferChunk>, Violation> {
        let mut state = self.lock();
        state.require_usable()?;
        match Self::admit(&mut state, payload) {
            Ok(chunk) => Ok(chunk),
            Err(check) => Err(state.refuse(check)),
        }
    }

    fn admit(
        state: &mut ReceiverState,
        payload: &[u8],
    ) -> Result<Option<TransferChunk>, &'static str> {
        let header = TransferChunkHeader::decode(payload).map_err(|_| "view_transfer_header")?;
        let streaming = state.streaming;
        let transfer = state
            .transfers
            .get_mut(&header.transfer_id)
            .ok_or("view_transfer_unknown")?;
        if streaming.is_some_and(|current| current != header.transfer_id) {
            return Err("view_transfer_interleaved");
        }
        if transfer.last_seen || header.offset != transfer.received {
            return Err("view_transfer_order");
        }
        if transfer.credit == 0 {
            return Err("view_transfer_credit");
        }
        let received = transfer
            .received
            .checked_add(header.body_length as u64)
            .ok_or("view_transfer_size")?;
        if received > transfer.declared_size.unwrap_or(u64::MAX) {
            return Err("view_transfer_size");
        }
        transfer.credit -= 1;
        transfer.received = received;
        transfer.last_seen = header.last;
        let body = &payload[CHUNK_HEADER_BYTES..];
        let kept = (!transfer.cancelled).then(|| {
            transfer.digest.update(body);
            TransferChunk {
                transfer_id: header.transfer_id,
                offset: header.offset,
                data: Zeroizing::new(body.to_vec()),
                last: header.last,
            }
        });
        state.streaming = if header.last {
            None
        } else {
            Some(header.transfer_id)
        };
        Ok(kept)
    }

    /// Applies the sender's closing document: its size and sha256 must be what was received.
    pub fn observe_complete(&self, document: &ViewTransferComplete) -> Result<(), Violation> {
        let mut state = self.lock();
        state.require_usable()?;
        let checked = match state.transfers.get(&document.transfer_id) {
            None => Err("view_transfer_unknown"),
            Some(transfer) if !transfer.last_seen => Err("view_transfer_incomplete"),
            Some(transfer)
                if document.size != transfer.received
                    || transfer
                        .declared_size
                        .is_some_and(|declared| declared != transfer.received) =>
            {
                Err("view_transfer_size")
            }
            Some(transfer)
                if !transfer.cancelled && document.sha256 != digest_hex(&transfer.digest) =>
            {
                Err("view_transfer_digest")
            }
            Some(_) => Ok(()),
        };
        match checked {
            Ok(()) => {
                state.transfers.remove(&document.transfer_id);
                Ok(())
            }
            Err(check) => Err(state.refuse(check)),
        }
    }

    /// Applies a cancel read from the same connection: the sender's stop of an inbound transfer.
    /// A cancel of the other direction is not this receiver's.
    pub fn observe_cancel(&self, document: &ViewTransferCancel) -> Result<(), Violation> {
        let mut state = self.lock();
        state.require_usable()?;
        if document.direction == self.direction {
            state.transfers.remove(&document.transfer_id);
            if state.streaming == Some(document.transfer_id) {
                state.streaming = None;
            }
        }
        Ok(())
    }
}

#[derive(Default)]
struct ControlState {
    credit: u8,
    cancelled: bool,
}

/// The credit and cancel signals of one outgoing transfer.
///
/// The connection's reader calls `grant` and `cancel` from its own thread
/// while the sender's writer waits in `wait_ready`.
#[derive(Default)]
pub struct SenderControl {
    state: Mutex<ControlState>,
    wake: Condvar,
}

impl SenderControl {
    fn lock(&self) -> MutexGuard<'_, ControlState> {
        self.state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    /// Adds the credit a `view.transfer_credit` document granted.
    pub fn grant(&self, chunks: u8) -> Result<(), Violation> {
        let mut state = self.lock();
        if chunks < 1
            || u16::from(state.credit) + u16::from(chunks) > u16::from(TRANSFER_CREDIT_MAX_CHUNKS)
        {
            return Err(Violation("view_transfer_credit"));
        }
        state.credit += chunks;
        self.wake.notify_all();
        Ok(())
    }

    /// Stops the transfer: no chunk is produced afterwards.
    pub fn cancel(&self) {
        let mut state = self.lock();
        state.cancelled = true;
        state.credit = 0;
        self.wake.notify_all();
    }

    /// Blocks until a chunk may be sent (`true`) or the transfer was cancelled (`false`).
    pub fn wait_ready(&self) -> bool {
        let mut state = self.lock();
        loop {
            if state.cancelled {
                return false;
            }
            if state.credit > 0 {
                return true;
            }
            state = self
                .wake
                .wait(state)
                .unwrap_or_else(|poisoned| poisoned.into_inner());
        }
    }

    /// Chunks admitted and not yet sent.
    pub fn credit(&self) -> u8 {
        self.lock().credit
    }

    fn take(&self) -> bool {
        let mut state = self.lock();
        if state.cancelled || state.credit == 0 {
            return false;
        }
        state.credit -= 1;
        true
    }
}

/// One `B` payload of an outgoing transfer, header included.
pub struct OutboundChunk {
    pub payload: Zeroizing<Vec<u8>>,
    pub offset: u64,
    pub body_length: usize,
    pub last: bool,
}

/// Cuts one transfer's bytes into ordered `B` payloads, one per unit of credit.
///
/// A transfer starts with no credit. The peer's `view.transfer_credit`
/// documents add to it through the [`SenderControl`], and `next_chunk` spends
/// one unit per chunk, so the sender never sends a chunk the receiver has not
/// admitted and never drops a byte: without credit it yields nothing and the
/// bytes stay in the source. The source is read one chunk ahead, so a file of
/// any size passes through without being held, and the chunk that ends it is
/// known to be last. After the last chunk, `completion` is the
/// `view.transfer_complete` to send.
pub struct TransferSender {
    transfer_id: u32,
    source: Box<dyn Read + Send>,
    control: Arc<SenderControl>,
    started: bool,
    done: bool,
    pending: Zeroizing<Vec<u8>>,
    offset: u64,
    digest: Sha256,
}

impl TransferSender {
    /// Sends `source` as transfer `transfer_id`.
    pub fn new(transfer_id: u32, source: Box<dyn Read + Send>) -> Result<Self, Violation> {
        if transfer_id == 0 {
            return Err(Violation("view_transfer_id"));
        }
        Ok(Self {
            transfer_id,
            source,
            control: Arc::new(SenderControl::default()),
            started: false,
            done: false,
            pending: Zeroizing::default(),
            offset: 0,
            digest: Sha256::new(),
        })
    }

    pub fn transfer_id(&self) -> u32 {
        self.transfer_id
    }

    /// The handle through which credit and cancel reach this sender.
    pub fn control(&self) -> Arc<SenderControl> {
        self.control.clone()
    }

    /// Whether the last chunk has been produced.
    pub fn done(&self) -> bool {
        self.done
    }

    /// The bytes produced so far.
    pub fn sent(&self) -> u64 {
        self.offset
    }

    /// Produces the next chunk, or `None` without credit, once done or once cancelled.
    ///
    /// An error from the source ends the transfer: the caller cancels it.
    pub fn next_chunk(&mut self) -> io::Result<Option<OutboundChunk>> {
        if self.done || !self.control.take() {
            return Ok(None);
        }
        if !self.started {
            self.pending = self.read_chunk()?;
            self.started = true;
        }
        let body = std::mem::take(&mut self.pending);
        let mut last = body.len() < CHUNK_BODY_BYTES;
        if !last {
            self.pending = self.read_chunk()?;
            last = self.pending.is_empty();
        }
        let header = TransferChunkHeader::new(self.transfer_id, self.offset, last, body.len())
            .map_err(io::Error::other)?;
        let mut payload = Zeroizing::new(Vec::with_capacity(CHUNK_HEADER_BYTES + body.len()));
        payload.extend_from_slice(&header.encode());
        payload.extend_from_slice(&body);
        self.digest.update(&body[..]);
        let offset = self.offset;
        self.offset += body.len() as u64;
        self.done = last;
        Ok(Some(OutboundChunk {
            payload,
            offset,
            body_length: body.len(),
            last,
        }))
    }

    /// The completion document for the bytes sent; valid once the last chunk is produced.
    pub fn completion(&self) -> Result<ViewTransferComplete, Violation> {
        if !self.done {
            return Err(Violation("view_transfer_incomplete"));
        }
        Ok(ViewTransferComplete {
            transfer_id: self.transfer_id,
            size: self.offset,
            sha256: digest_hex(&self.digest),
        })
    }

    /// Reads a full chunk, or the short remainder that ends the source.
    fn read_chunk(&mut self) -> io::Result<Zeroizing<Vec<u8>>> {
        let mut chunk = Zeroizing::new(vec![0u8; CHUNK_BODY_BYTES]);
        let mut filled = 0;
        while filled < CHUNK_BODY_BYTES {
            match self.source.read(&mut chunk[filled..]) {
                Ok(0) => break,
                Ok(count) => filled += count,
                Err(error) if error.kind() == io::ErrorKind::Interrupted => {}
                Err(error) => return Err(error),
            }
        }
        chunk.truncate(filled);
        Ok(chunk)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::view_stream::{
        chunks::is_transfer_chunk,
        documents::ViewUpstream,
        vectors::{self, chunk_payload, sha256_hex},
    };
    use serde_json::Value;
    use std::io::Cursor;

    fn source(length: usize) -> Box<dyn Read + Send> {
        Box::new(Cursor::new(vectors::pattern(0, length)))
    }

    fn drain(sender: &mut TransferSender) -> Vec<OutboundChunk> {
        sender.control().grant(TRANSFER_CREDIT_MAX_CHUNKS).unwrap();
        let mut chunks = Vec::new();
        while let Some(chunk) = sender.next_chunk().unwrap() {
            chunks.push(chunk);
        }
        chunks
    }

    #[test]
    fn a_sender_cuts_a_file_into_full_chunks_and_a_remainder() {
        let mut sender = TransferSender::new(7, source(2 * CHUNK_BODY_BYTES + 100)).unwrap();
        let chunks = drain(&mut sender);
        let shape: Vec<_> = chunks
            .iter()
            .map(|chunk| (chunk.offset, chunk.body_length, chunk.last))
            .collect();
        assert_eq!(
            shape,
            [
                (0, CHUNK_BODY_BYTES, false),
                (CHUNK_BODY_BYTES as u64, CHUNK_BODY_BYTES, false),
                (2 * CHUNK_BODY_BYTES as u64, 100, true),
            ]
        );
        for chunk in &chunks {
            let header = TransferChunkHeader::decode(&chunk.payload).unwrap();
            assert_eq!(header.transfer_id, 7);
            assert_eq!(header.offset, chunk.offset);
            assert_eq!(header.last, chunk.last);
        }
        let completion = sender.completion().unwrap();
        assert_eq!(completion.size, 2 * CHUNK_BODY_BYTES as u64 + 100);
        assert_eq!(
            completion.sha256,
            sha256_hex(&vectors::pattern(0, completion.size as usize))
        );
    }

    #[test]
    fn a_file_of_exactly_whole_chunks_ends_with_a_full_last_chunk() {
        let mut sender = TransferSender::new(1, source(CHUNK_BODY_BYTES)).unwrap();
        let chunks = drain(&mut sender);
        assert_eq!(chunks.len(), 1);
        assert!(chunks[0].last);
        assert_eq!(chunks[0].body_length, CHUNK_BODY_BYTES);
    }

    #[test]
    fn an_empty_file_is_one_empty_last_chunk() {
        let mut sender = TransferSender::new(1, source(0)).unwrap();
        let chunks = drain(&mut sender);
        assert_eq!(chunks.len(), 1);
        assert!(chunks[0].last);
        assert_eq!(chunks[0].body_length, 0);
        let completion = sender.completion().unwrap();
        assert_eq!(completion.size, 0);
        assert_eq!(completion.sha256, sha256_hex(&[]));
    }

    #[test]
    fn a_sender_without_credit_produces_nothing_and_keeps_its_bytes() {
        let mut sender = TransferSender::new(1, source(3 * CHUNK_BODY_BYTES)).unwrap();
        assert!(sender.next_chunk().unwrap().is_none());
        assert_eq!(sender.sent(), 0);
        sender.control().grant(1).unwrap();
        assert_eq!(sender.control().credit(), 1);
        assert!(sender.next_chunk().unwrap().is_some());
        assert!(sender.next_chunk().unwrap().is_none());
        assert_eq!(sender.sent(), CHUNK_BODY_BYTES as u64);
        assert!(!sender.done());
        assert_eq!(
            sender.completion().unwrap_err(),
            Violation("view_transfer_incomplete")
        );
    }

    #[test]
    fn credit_beyond_the_window_or_of_nothing_is_refused_and_a_cancel_ends_the_transfer() {
        let sender = TransferSender::new(1, source(10)).unwrap();
        let control = sender.control();
        assert!(control.grant(0).is_err());
        control.grant(TRANSFER_CREDIT_MAX_CHUNKS).unwrap();
        assert_eq!(control.grant(1), Err(Violation("view_transfer_credit")));
        control.cancel();
        assert_eq!(control.credit(), 0);
        assert!(!control.wait_ready());
        let mut sender = sender;
        assert!(sender.next_chunk().unwrap().is_none());
        assert!(TransferSender::new(0, source(1)).is_err());
    }

    #[test]
    fn a_sender_and_a_receiver_agree_and_a_changed_byte_is_a_digest_violation() {
        let size = 2 * CHUNK_BODY_BYTES + 5;
        let run = |corrupt: bool| {
            let mut sender = TransferSender::new(1, source(size)).unwrap();
            let chunks = drain(&mut sender);
            let receiver = TransferReceiver::new(ViewTransferDirection::Upload);
            receiver.expect(1, Some(size as u64)).unwrap();
            receiver.grant(1, 3).unwrap();
            for chunk in &chunks {
                let mut payload = chunk.payload.to_vec();
                if corrupt && chunk.offset == 0 {
                    payload[CHUNK_HEADER_BYTES] ^= 1;
                }
                let received = receiver.accept(&payload).unwrap().unwrap();
                assert_eq!(received.offset, chunk.offset);
            }
            receiver.observe_complete(&sender.completion().unwrap())
        };
        assert_eq!(run(false), Ok(()));
        assert_eq!(run(true), Err(Violation("view_transfer_digest")));
    }

    #[test]
    fn the_receiver_rules_a_caller_breaks_do_not_refuse_the_stream() {
        let receiver = TransferReceiver::new(ViewTransferDirection::Download);
        receiver.expect(2, None).unwrap();
        assert_eq!(receiver.expect(2, None), Err(Violation("view_transfer_id")));
        assert_eq!(receiver.expect(1, None), Err(Violation("view_transfer_id")));
        assert_eq!(
            receiver.grant(9, 1),
            Err(Violation("view_transfer_unknown"))
        );
        assert_eq!(receiver.grant(2, 0), Err(Violation("view_transfer_credit")));
        receiver.grant(2, TRANSFER_CREDIT_MAX_CHUNKS).unwrap();
        assert_eq!(receiver.grant(2, 1), Err(Violation("view_transfer_credit")));
        // The stream itself was never refused: a legal chunk is still taken.
        let mut sender = TransferSender::new(2, source(4)).unwrap();
        let chunk = drain(&mut sender).remove(0);
        assert!(receiver.accept(&chunk.payload).unwrap().is_some());
        assert_eq!(
            receiver.cancel(2),
            Some(ViewTransferCancel {
                direction: ViewTransferDirection::Download,
                transfer_id: 2
            })
        );
        assert_eq!(receiver.cancel(2), None);
        assert_eq!(receiver.cancel(5), None);
        assert_eq!(receiver.grant(2, 1), Err(Violation("view_transfer_closed")));
    }

    #[test]
    fn a_refused_stream_stays_refused() {
        let receiver = TransferReceiver::new(ViewTransferDirection::Download);
        assert_eq!(
            receiver
                .accept(&chunk_payload(&serde_json::json!({
                    "header": "01030000000000010000000000000000", "body_offset": 0, "body_length": 1
                })))
                .unwrap_err(),
            Violation("view_transfer_unknown")
        );
        assert_eq!(
            receiver.expect(1, None),
            Err(Violation("view_stream_refused"))
        );
        assert_eq!(
            receiver.observe_cancel(&ViewTransferCancel {
                direction: ViewTransferDirection::Download,
                transfer_id: 1
            }),
            Err(Violation("view_stream_refused"))
        );
    }

    /// Drives the shared `transfer_streams` vectors whose reader is the worker side:
    /// uploads arrive upstream, and the receiver is the one a window never needs.
    #[test]
    fn upstream_transfer_streams_in_the_vectors_run_as_python_runs_them() {
        let vectors = vectors::load();
        let mut ran = 0;
        for stream in vectors.array("transfer_streams") {
            if stream["direction"] != "upstream" {
                continue;
            }
            let name = stream["name"].as_str().unwrap();
            let receiver = TransferReceiver::new(ViewTransferDirection::Upload);
            for setup in stream["setup"].as_array().unwrap() {
                apply_setup(&receiver, setup);
            }
            let mut outputs = Vec::new();
            let mut refused_at = None;
            for (index, step) in stream["steps"].as_array().unwrap().iter().enumerate() {
                match upstream_step(&receiver, step) {
                    Ok(Some(output)) => outputs.push(output),
                    Ok(None) => {}
                    Err(_) => {
                        refused_at = Some(index);
                        break;
                    }
                }
            }
            assert_eq!(
                refused_at,
                stream["refused_at"].as_u64().map(|index| index as usize),
                "{name}"
            );
            if refused_at.is_none() {
                assert_eq!(outputs, expected_outputs(stream), "{name}");
            }
            ran += 1;
        }
        assert!(ran >= 2, "{ran}");
    }

    fn apply_setup(receiver: &TransferReceiver, setup: &Value) {
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

    #[derive(Debug, PartialEq, Eq)]
    enum Output {
        Chunk {
            transfer_id: u32,
            offset: u64,
            length: usize,
            last: bool,
            sha256: String,
        },
        Document(String),
    }

    fn expected_outputs(stream: &Value) -> Vec<Output> {
        stream["expect"]
            .as_array()
            .unwrap()
            .iter()
            .map(|entry| match (entry.get("chunk"), entry.get("document")) {
                (Some(chunk), _) => Output::Chunk {
                    transfer_id: chunk["transfer_id"].as_u64().unwrap() as u32,
                    offset: chunk["offset"].as_u64().unwrap(),
                    length: chunk["length"].as_u64().unwrap() as usize,
                    last: chunk["last"].as_bool().unwrap(),
                    sha256: chunk["sha256"].as_str().unwrap().to_owned(),
                },
                (_, Some(kind)) => Output::Document(kind.as_str().unwrap().to_owned()),
                _ => panic!("an expected output"),
            })
            .collect()
    }

    fn upstream_step(
        receiver: &TransferReceiver,
        step: &Value,
    ) -> Result<Option<Output>, Violation> {
        if let Some(chunk) = step.get("chunk") {
            let payload = chunk_payload(chunk);
            // The worker side admits only transfer chunks upstream.
            if !is_transfer_chunk(&payload) {
                return Err(Violation("view_image_chunk_upstream"));
            }
            return Ok(receiver.accept(&payload)?.map(|chunk| Output::Chunk {
                transfer_id: chunk.transfer_id,
                offset: chunk.offset,
                length: chunk.data.len(),
                last: chunk.last,
                sha256: sha256_hex(&chunk.data),
            }));
        }
        let document = step
            .get("document")
            .expect("a step is a chunk or a document");
        let payload = serde_json::to_vec(document).unwrap();
        let decoded: ViewUpstream =
            serde_json::from_slice(&payload).map_err(|_| Violation("view_document"))?;
        decoded.validate()?;
        match &decoded {
            ViewUpstream::TransferComplete(complete) => receiver.observe_complete(complete)?,
            ViewUpstream::TransferCancel(cancel) => receiver.observe_cancel(cancel)?,
            _ => {}
        }
        Ok(Some(Output::Document(decoded.kind().to_owned())))
    }

    #[test]
    fn the_vectors_name_both_directions() {
        let directions: Vec<_> = vectors::load()
            .array("transfer_streams")
            .iter()
            .map(|stream| stream["direction"].as_str().unwrap().to_owned())
            .collect();
        assert!(directions.iter().any(|name| name == "downstream"));
        assert!(directions.iter().any(|name| name == "upstream"));
    }
}
