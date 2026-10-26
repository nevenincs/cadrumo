//! The loopback client of the launcher's cadrumo-agent gateway.
//!
//! Every call goes to `127.0.0.1` on the port the launcher reported, with the
//! bearer this host minted, and never through a proxy or a redirect. Answers
//! are read as JSON; a refusal leaves as a typed code, never as the gateway's
//! prose.

use super::{Refused, supervisor::Gateway};
use serde_json::Value;
use std::{io::Read, time::Duration};

/// The most a call's answer may hold; the gateway's own pass-through cap.
const ANSWER_LIMIT: u64 = 8 * 1024 * 1024;
/// How long one call may take.
const CALL_DEADLINE: Duration = Duration::from_secs(30);

/// `RUN_ID_PATTERN`: a path-safe run id of at most 128 characters.
pub fn run_id(value: &str) -> bool {
    let bytes = value.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= 128
        && (bytes[0].is_ascii_alphanumeric() || bytes[0] == b'_')
        && bytes
            .iter()
            .all(|b| b.is_ascii_alphanumeric() || *b == b'_' || *b == b'-')
}

/// `REQUEST_ID_PATTERN`, bounded by `MAX_REQUEST_ID_CHARS`.
pub fn request_id(value: &str) -> bool {
    let bytes = value.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= 128
        && (bytes[0].is_ascii_alphanumeric() || bytes[0] == b'_')
        && bytes
            .iter()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'.' | b'-'))
}

/// A file name as one path segment: every byte but the unreserved ones
/// percent-encoded, so no name reaches another route.
pub fn segment(name: &str) -> String {
    name.bytes().fold(String::new(), |mut out, b| {
        if b.is_ascii_alphanumeric() || matches!(b, b'-' | b'.' | b'_' | b'~') {
            out.push(char::from(b));
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
        out
    })
}

/// The typed code of a gateway refusal: its own code where it gives one,
/// else its status.
pub fn refusal(status: u16, body: &[u8]) -> Refused {
    let coded = serde_json::from_slice::<Value>(body)
        .ok()
        .and_then(|body| body.get("detail")?.get("code")?.as_str().map(str::to_owned))
        .filter(|code| {
            !code.is_empty()
                && code.len() <= 64
                && code
                    .bytes()
                    .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
        });
    match coded {
        Some(code) => Refused::new(format!("agent_gateway_{code}")),
        None => Refused::new(format!("agent_gateway_{status}")),
    }
}

pub struct Client {
    base: String,
    authorization: String,
    calls: ureq::Agent,
    streams: ureq::Agent,
}

impl Drop for Client {
    fn drop(&mut self) {
        zeroize::Zeroize::zeroize(&mut self.authorization);
    }
}

fn agent(deadline: Option<Duration>) -> ureq::Agent {
    ureq::Agent::config_builder()
        .http_status_as_error(false)
        .proxy(None)
        .max_redirects(0)
        .timeout_connect(Some(Duration::from_secs(5)))
        .timeout_global(deadline)
        .build()
        .into()
}

fn unreachable() -> Refused {
    Refused::new("agent_gateway_unreachable".to_owned())
}

impl Client {
    pub fn new(gateway: &Gateway) -> Self {
        Self {
            base: format!("http://127.0.0.1:{}/v1", gateway.port),
            authorization: format!("Bearer {}", gateway.bearer.as_str()),
            calls: agent(Some(CALL_DEADLINE)),
            streams: agent(None),
        }
    }

    fn answer(response: ureq::http::Response<ureq::Body>) -> Result<Value, Refused> {
        let status = response.status().as_u16();
        let body = response
            .into_body()
            .with_config()
            .limit(ANSWER_LIMIT)
            .read_to_vec()
            .map_err(|_| unreachable())?;
        if !(200..300).contains(&status) {
            return Err(refusal(status, &body));
        }
        if body.is_empty() {
            return Ok(Value::Null);
        }
        serde_json::from_slice(&body)
            .map_err(|_| Refused::new("agent_gateway_unreadable".to_owned()))
    }

    fn get(&self, path: &str) -> Result<Value, Refused> {
        let response = self
            .calls
            .get(format!("{}{path}", self.base))
            .header("Authorization", &self.authorization)
            .call()
            .map_err(|_| unreachable())?;
        Self::answer(response)
    }

    fn post(&self, path: &str, body: &Value, key: Option<&str>) -> Result<Value, Refused> {
        let mut request = self
            .calls
            .post(format!("{}{path}", self.base))
            .header("Authorization", &self.authorization)
            .header("Content-Type", "application/json");
        if let Some(key) = key {
            request = request.header("Idempotency-Key", key);
        }
        let response = request
            .send(serde_json::to_vec(body).map_err(|_| unreachable())?)
            .map_err(|_| unreachable())?;
        Self::answer(response)
    }

    /// `GET /v1/runs/{id}`: the authoritative run status.
    pub fn run_status(&self, run: &str) -> Result<Value, Refused> {
        self.get(&format!("/runs/{run}"))
    }

    /// `POST /v1/runs/{id}/cancel`.
    pub fn cancel(&self, run: &str) -> Result<Value, Refused> {
        self.post(&format!("/runs/{run}/cancel"), &serde_json::json!({}), None)
    }

    /// `POST /v1/runs/{id}/permissions/{request}/respond`.
    pub fn permission(&self, run: &str, request: &str, option_id: &str) -> Result<Value, Refused> {
        self.post(
            &format!("/runs/{run}/permissions/{request}/respond"),
            &serde_json::json!({"option_id": option_id}),
            None,
        )
    }

    /// `POST /v1/runs/{id}/clarifications/{request}/respond`, with exactly one
    /// of answers, a prompt, or a decline.
    pub fn clarification(&self, run: &str, request: &str, body: &Value) -> Result<Value, Refused> {
        self.post(
            &format!("/runs/{run}/clarifications/{request}/respond"),
            body,
            None,
        )
    }

    /// `GET /v1/runs?state=all`: one page of every run, newest created first.
    pub fn runs(&self, offset: usize, limit: usize) -> Result<Value, Refused> {
        let response = self
            .calls
            .get(format!("{}/runs", self.base))
            .query("state", "all")
            .query("limit", limit.to_string())
            .query("offset", offset.to_string())
            .header("Authorization", &self.authorization)
            .call()
            .map_err(|_| unreachable())?;
        Self::answer(response)
    }

    /// `POST /v1/runs`: starts a run under the id the host chose.
    pub fn start_run(&self, body: &Value) -> Result<Value, Refused> {
        self.post("/runs", body, None)
    }

    /// `POST /v1/conversations/chain/delete`: every run of the conversation
    /// whose first run is `root`, and the documents stored for it.
    pub fn delete_conversation(&self, root: &str) -> Result<Value, Refused> {
        self.post(
            "/conversations/chain/delete",
            &serde_json::json!({ "run_id": root }),
            None,
        )
    }

    /// Archive the whole settled conversation in one gateway transaction.
    pub fn archive_conversation(&self, root: &str) -> Result<Value, Refused> {
        self.post(
            &format!("/conversations/{root}/archive"),
            &serde_json::json!({}),
            None,
        )
    }

    /// `PATCH /v1/conversations/{root}`: the conversation's title, kept on its
    /// first run.
    pub fn rename_conversation(&self, root: &str, title: &str) -> Result<Value, Refused> {
        let response = self
            .calls
            .patch(format!("{}/conversations/{root}", self.base))
            .header("Authorization", &self.authorization)
            .header("Content-Type", "application/json")
            .send(
                serde_json::to_vec(&serde_json::json!({ "title": title }))
                    .map_err(|_| unreachable())?,
            )
            .map_err(|_| unreachable())?;
        Self::answer(response)
    }

    /// `GET /v1/attachments/policy`: what a conversation's storage takes.
    pub fn attachment_policy(&self) -> Result<Value, Refused> {
        self.get("/attachments/policy")
    }

    /// `PUT /v1/conversations/{id}/attachments/{name}`: stores `length` bytes
    /// read from `body` under `name` in the conversation's own storage, with
    /// the digest the service checks them against. Not bounded by the call
    /// deadline: a large file on a slow disk takes the time it takes.
    pub fn upload(
        &self,
        conversation: &str,
        name: &str,
        body: &mut dyn Read,
        length: u64,
        sha256: &str,
    ) -> Result<Value, Refused> {
        let response = self
            .streams
            .put(format!(
                "{}/conversations/{conversation}/attachments/{}",
                self.base,
                segment(name)
            ))
            .header("Authorization", &self.authorization)
            .header("Content-Type", "application/octet-stream")
            .header("Content-Length", length.to_string())
            .header("X-Content-SHA256", sha256)
            .send(ureq::SendBody::from_reader(body))
            .map_err(|_| unreachable())?;
        Self::answer(response)
    }

    /// `GET /v1/conversations/{id}/attachments`: one page of the documents
    /// stored for the conversation whose first run is `conversation`, by name,
    /// after `after`, whose names hold `q`.
    pub fn attachments(
        &self,
        conversation: &str,
        after: Option<&str>,
        q: Option<&str>,
        limit: usize,
    ) -> Result<Value, Refused> {
        let mut request = self
            .calls
            .get(format!(
                "{}/conversations/{conversation}/attachments",
                self.base
            ))
            .query("limit", limit.to_string());
        if let Some(after) = after {
            request = request.query("after", after);
        }
        if let Some(q) = q {
            request = request.query("q", q);
        }
        let response = request
            .header("Authorization", &self.authorization)
            .call()
            .map_err(|_| unreachable())?;
        Self::answer(response)
    }

    /// `GET /v1/runs/{id}/history`.
    pub fn history(&self, run: &str) -> Result<Value, Refused> {
        self.get(&format!("/runs/{run}/history"))
    }

    /// `GET /v1/provider-licences/{provider}/{transport}/{model}`: the licence
    /// text of one model a lane lists, for names the caller has checked. Each
    /// is one percent-encoded segment, so a model id reaches no other route.
    pub fn licence(&self, provider: &str, transport: &str, model: &str) -> Result<Value, Refused> {
        self.get(&format!(
            "/provider-licences/{}/{}/{}",
            segment(provider),
            segment(transport),
            segment(model)
        ))
    }

    /// `GET /v1/skills`: every skill of the agent, by name.
    pub fn skills(&self) -> Result<Value, Refused> {
        self.get("/skills")
    }

    /// `GET /v1/skills/{name}`, for a name the caller has checked.
    pub fn skill(&self, name: &str) -> Result<Value, Refused> {
        self.get(&format!("/skills/{name}"))
    }

    /// `POST /v1/skills/{name}/verify`, for a name the caller has checked.
    pub fn verify_skill(&self, name: &str) -> Result<Value, Refused> {
        self.post(
            &format!("/skills/{name}/verify"),
            &serde_json::json!({}),
            None,
        )
    }

    /// `GET /v1/runs/{id}/stream`, resumed after `cursor`, or from the start
    /// of what the run retains.
    pub fn stream(&self, run: &str, cursor: Option<&str>) -> Result<impl Read + use<>, Refused> {
        let response = self
            .streams
            .get(format!("{}/runs/{run}/stream", self.base))
            .header("Authorization", &self.authorization)
            .header("Accept", "text/event-stream")
            .header("Last-Event-ID", cursor.unwrap_or("-"))
            .call()
            .map_err(|_| unreachable())?;
        let status = response.status().as_u16();
        if status != 200 {
            let body = response
                .into_body()
                .with_config()
                .limit(64 * 1024)
                .read_to_vec()
                .unwrap_or_default();
            return Err(refusal(status, &body));
        }
        Ok(response.into_body().into_reader())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ids_follow_the_gateway_grammar() {
        for good in ["run-1", "_x", "a".repeat(128).as_str()] {
            assert!(run_id(good), "{good}");
        }
        for bad in [
            "",
            "-run",
            "run/1",
            "run.1",
            "a".repeat(129).as_str(),
            "..",
            "run 1",
        ] {
            assert!(!run_id(bad), "{bad}");
        }
        assert!(request_id("perm-1.a_b"));
        for bad in ["", ".x", "a/b", "a?b", "a".repeat(129).as_str()] {
            assert!(!request_id(bad), "{bad}");
        }
    }

    #[test]
    fn a_file_name_is_one_path_segment() {
        assert_eq!(segment("factura-2026_01.pdf"), "factura-2026_01.pdf");
        assert_eq!(segment("notas del año.txt"), "notas%20del%20a%C3%B1o.txt");
        assert_eq!(segment("a/b?c#d%"), "a%2Fb%3Fc%23d%25");
    }

    #[test]
    fn a_refusal_crosses_as_its_code_never_its_prose() {
        let coded = br#"{"detail": {"code": "run_busy", "message": "private prose"}}"#;
        assert_eq!(refusal(409, coded).code, "agent_gateway_run_busy");
        assert_eq!(
            refusal(409, br#"{"detail": "a sentence with private words"}"#).code,
            "agent_gateway_409"
        );
        assert_eq!(
            refusal(422, br#"{"detail": {"code": "Not A Code"}}"#).code,
            "agent_gateway_422"
        );
        assert_eq!(refusal(401, b"").code, "agent_gateway_401");
    }
}
