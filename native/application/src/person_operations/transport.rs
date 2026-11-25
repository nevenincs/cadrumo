use super::failure::{Failure, Outcome};
use super::lifecycle::Upload;
use super::protocol::{REPLY_KINDS, members, text};
use crate::runtime_client::{
    connection::SessionExchange,
    framing::{MAXIMUM_FRAME_BYTES, request_id},
    refusal::Refusal,
    session::Admitted,
};
use crate::value::Sha256Digest;
use serde_json::{Map, Value, json};
use std::time::{Duration, Instant};
use zeroize::Zeroizing;

/// The held session's connection, for exchanges under its exact coordinates.
pub(super) struct Held<'a> {
    pub(super) connection: &'a dyn SessionExchange,
    pub(super) session: &'a Admitted,
}

impl Held<'_> {
    /// Sends `action` with `fields` under the held session and returns a reply
    /// of a registered operation kind; a refusal is the runtime's.
    pub(super) fn exchange(
        &self,
        action: &str,
        fields: Value,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        let request = self.request(action, fields, deadline)?;
        self.send(&request, deadline)
    }

    /// Submits `payload_json` streamed to the runtime's staging: the upload's
    /// header first, then its bytes once the runtime is ready for them. The
    /// runtime refuses a financial upload for a definition that takes none,
    /// and a plain one whose bytes do not match the digest declared.
    pub(super) fn streamed(
        &self,
        definition: &str,
        subject_ref: &str,
        payload_json: &str,
        upload: Upload,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        let byte_count = payload_json.len();
        let descriptor = match upload {
            Upload::Financial => {
                json!({"kind": "financial_operand_input", "byte_count": byte_count})
            }
            Upload::Payload => json!({
                "byte_count": byte_count,
                "payload_digest": Sha256Digest::of(payload_json.as_bytes()).to_string(),
            }),
        };
        let request = self.request(
            "operation_submit_payload",
            json!({
                "definition_id": definition,
                "subject_ref": subject_ref,
                "idempotency_key": null,
                "descriptor": descriptor,
            }),
            deadline,
        )?;
        let reply =
            self.connection
                .exchange_streamed(&request, payload_json.as_bytes(), deadline)?;
        match text(&reply, "kind") {
            Some(kind) if REPLY_KINDS.contains(&kind) => Ok(reply),
            _ => Err(Failure::frame()),
        }
    }

    pub(super) fn request(&self, action: &str, fields: Value, deadline: Instant) -> Outcome<Value> {
        remaining(deadline)?;
        let mut request = members(json!({
            "action": action,
            "request_id": request_id(),
            "profile_id": self.session.profile_id,
            "session_id": self.session.session_id,
        }));
        request.extend(members(fields));
        Ok(Value::Object(request))
    }

    pub(super) fn send(&self, request: &Value, deadline: Instant) -> Outcome<Map<String, Value>> {
        // Bounded by the exact bytes the connection writes as the frame.
        let encoded = Zeroizing::new(serde_json::to_vec(request).map_err(|_| Failure::frame())?);
        if encoded.len() > MAXIMUM_FRAME_BYTES {
            return Err(Failure::frame());
        }
        drop(encoded);
        let reply = self.connection.exchange(request, deadline)?;
        match text(&reply, "kind") {
            Some(kind) if REPLY_KINDS.contains(&kind) => Ok(reply),
            _ => Err(Failure::frame()),
        }
    }

    pub(super) fn subject(&self) -> String {
        format!("profile:{}", self.session.profile_id)
    }
}

pub(super) fn remaining(deadline: Instant) -> Outcome<Duration> {
    let left = deadline.saturating_duration_since(Instant::now());
    if left.is_zero() {
        return Err(Failure::Runtime(Refusal::Timeout));
    }
    Ok(left)
}
