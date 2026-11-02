use super::connection::{Connection, SessionExchange};
use super::events::{Event, event};
use super::framing::{document, is_uuid, request_id, text};
use super::refusal::{CUSTODY_RECOVERING, Refusal};
use super::stored_proof::{ResumeRefusal, present_stored_proof};
use serde_json::{Map, Value, json};
use std::path::Path;
use std::sync::mpsc;
use std::time::Instant;

/// The frontend a sign-in is made from; the runtime decides what each may do.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Frontend {
    Desktop,
    Cli,
    Tui,
}

impl Frontend {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Desktop => "desktop",
            Self::Cli => "cli",
            Self::Tui => "tui",
        }
    }
}

/// A profile's stored sign-in as the runtime observes it: never proof of authentication.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SignInStatus {
    /// `present`, `absent` or `unknown`.
    pub presence: String,
    pub idle_deadline: Option<String>,
    pub absolute_deadline: Option<String>,
}

/// Which profile is selected and which holds the live sign-in.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ActiveProfile {
    pub selected_profile_id: Option<String>,
    pub signed_in_profile_id: Option<String>,
    pub presence: String,
}

/// A session the runtime admitted on this connection.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Admitted {
    pub profile_id: String,
    pub session_id: String,
    pub connection_id: String,
    pub runtime_boot_id: String,
    pub expires_at: Option<String>,
    /// Whether the person's sign-in was stored for other frontends, when the
    /// reply says.
    pub session_persisted: Option<bool>,
    pub signed_out_profile_ids: Vec<String>,
}

/// What a sign-out removed.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SignedOut {
    pub session_ids: Vec<String>,
    pub receipt_removed: bool,
    pub keychain_removed: bool,
    /// The profile's persisted automation setting, which a sign-out keeps; not access.
    pub automation_enabled: Option<bool>,
    /// Whether an issued key can still admit; `None` when the runtime could not say.
    pub automation_access_remains: Option<bool>,
}

pub(super) fn uuid_list(value: Option<&Value>) -> Vec<String> {
    value
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_owned)
                .collect()
        })
        .unwrap_or_default()
}

/// The runtime's typed refusal as its `access_refusal` document spells it.
/// A recovering session's refusal of a change whose effect is `unknown` is
/// [`Refusal::Unsettled`], never the plain refusal of a request nothing served.
pub(super) fn access_refusal(reply: &Map<String, Value>) -> Refusal {
    if text(reply, "code") == Some("runtime_timeout") {
        return Refusal::Timeout;
    }
    if text(reply, "code") == Some(CUSTODY_RECOVERING) && text(reply, "effect") == Some("unknown") {
        return Refusal::Unsettled {
            operation_id: text(reply, "operation_id").map(str::to_owned),
            recovery_remaining_seconds: recovery_window(reply),
        };
    }
    Refusal::Denied {
        code: text(reply, "code").unwrap_or_default().to_owned(),
        sign_in: reply
            .get("sign_in")
            .filter(|value| !value.is_null())
            .cloned(),
        holder_operation_id: text(reply, "holder_operation_id").map(str::to_owned),
        recovery_remaining_seconds: recovery_window(reply),
    }
}

/// The whole seconds a document names as left in a suspended session's recovery window.
pub(super) fn recovery_window(document: &Map<String, Value>) -> Option<u64> {
    document
        .get("recovery_remaining_seconds")
        .and_then(Value::as_u64)
}

/// The refusal a status's `denial` stands for, with the window a suspended session names.
pub(super) fn denial(status: &Map<String, Value>) -> Option<Refusal> {
    text(status, "denial").map(|code| Refusal::Denied {
        code: code.to_owned(),
        sign_in: None,
        holder_operation_id: None,
        recovery_remaining_seconds: recovery_window(status),
    })
}

/// Where a session stands, as the runtime's status for it reads.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Standing {
    /// The lease grants access.
    Held,
    /// A lost worker suspended it: it grants nothing until a fresh proof on
    /// its own connection rebinds it, or its window ends.
    Recovering { remaining_seconds: Option<u64> },
    /// The runtime refuses it for the denial's own reason; it is not coming back by itself.
    Refused(String),
}

impl Standing {
    /// Reads the status object the runtime answered for `session`.
    pub fn of(status: &Map<String, Value>, session: &Admitted) -> Self {
        match text(status, "denial") {
            Some(CUSTODY_RECOVERING) => Self::Recovering {
                remaining_seconds: recovery_window(status),
            },
            Some(code) => Self::Refused(code.to_owned()),
            None if text(status, "session_id") == Some(session.session_id.as_str()) => Self::Held,
            None => Self::Refused("profile_mismatch".to_owned()),
        }
    }
}

pub(super) fn admitted(reply: &Map<String, Value>, profile_id: &str) -> Result<Admitted, Refusal> {
    if text(reply, "kind") != Some("profile_status") {
        return Err(Refusal::InvalidFrame);
    }
    let status = reply
        .get("status")
        .and_then(Value::as_object)
        .ok_or(Refusal::InvalidFrame)?;
    let flag = |key: &str| status.get(key).and_then(Value::as_bool).unwrap_or(false);
    if let Some(refusal) = denial(status) {
        return Err(refusal);
    }
    let session_id = text(status, "session_id");
    if !flag("connected")
        || !flag("credential_authenticated")
        || !flag("profile_bound")
        || text(status, "profile_id") != Some(profile_id)
        || session_id.is_none()
    {
        return Err(Refusal::denied("profile_mismatch"));
    }
    Ok(Admitted {
        profile_id: profile_id.to_owned(),
        session_id: session_id.unwrap_or_default().to_owned(),
        connection_id: text(reply, "connection_id").unwrap_or_default().to_owned(),
        runtime_boot_id: text(reply, "runtime_boot_id")
            .unwrap_or_default()
            .to_owned(),
        expires_at: text(status, "session_expires_at").map(str::to_owned),
        session_persisted: reply
            .get("human_login")
            .and_then(Value::as_object)
            .and_then(|login| login.get("session_persisted"))
            .and_then(Value::as_bool),
        signed_out_profile_ids: uuid_list(reply.get("signed_out_profile_ids")),
    })
}

impl Connection {
    /// The stored sign-in of `profile_id`, without admitting a session. With
    /// `watch`, the runtime also pushes [`Event::SignInChanged`] whenever any
    /// sign-in may have changed, until the connection closes.
    pub fn sign_in_status(
        &self,
        profile_id: &str,
        watch: bool,
        deadline: Instant,
    ) -> Result<SignInStatus, Refusal> {
        let reply = self.exchange(
            &json!({
                "action": "sign_in_status",
                "request_id": request_id(),
                "profile_id": profile_id,
                "watch": watch,
            }),
            deadline,
        )?;
        if text(&reply, "kind") != Some("sign_in_status")
            || text(&reply, "profile_id") != Some(profile_id)
        {
            return Err(self.fail(Refusal::InvalidFrame));
        }
        let status = reply
            .get("status")
            .and_then(Value::as_object)
            .ok_or_else(|| self.fail(Refusal::InvalidFrame))?;
        Ok(SignInStatus {
            presence: text(status, "presence").unwrap_or("unknown").to_owned(),
            idle_deadline: text(status, "idle_deadline").map(str::to_owned),
            absolute_deadline: text(status, "absolute_deadline").map(str::to_owned),
        })
    }

    /// Which profile is selected and signed in, on a connection that holds no
    /// session. With `watch`, [`Event::SignInChanged`] follows every change.
    pub fn active_profile(&self, watch: bool, deadline: Instant) -> Result<ActiveProfile, Refusal> {
        let reply = self.exchange(
            &json!({"action": "active_profile", "request_id": request_id(), "watch": watch}),
            deadline,
        )?;
        if text(&reply, "kind") != Some("active_profile") {
            return Err(self.fail(Refusal::InvalidFrame));
        }
        Ok(ActiveProfile {
            selected_profile_id: text(&reply, "selected_profile_id").map(str::to_owned),
            signed_in_profile_id: text(&reply, "signed_in_profile_id").map(str::to_owned),
            presence: text(&reply, "presence").unwrap_or("unknown").to_owned(),
        })
    }

    /// The profile `name` resolves to, by identifier or exact label, with its
    /// label; `None` when it names no live profile. Credential-free.
    pub fn login_target(
        &self,
        name: &str,
        deadline: Instant,
    ) -> Result<Option<(String, String)>, Refusal> {
        let reply = self.exchange(
            &json!({"action": "login_target", "request_id": request_id(), "name": name}),
            deadline,
        )?;
        if text(&reply, "kind") != Some("login_target") {
            return Err(self.fail(Refusal::InvalidFrame));
        }
        Ok(match (text(&reply, "profile_id"), text(&reply, "label")) {
            (Some(profile_id), Some(label)) if is_uuid(profile_id) => {
                Some((profile_id.to_owned(), label.to_owned()))
            }
            (None, None) => None,
            _ => return Err(self.fail(Refusal::InvalidFrame)),
        })
    }

    pub(super) fn login(
        &self,
        profile_id: &str,
        frontend: Frontend,
        method: &str,
        secret: &[u8],
        persist_receipt: bool,
        deadline: Instant,
    ) -> Result<Admitted, Refusal> {
        present_login(
            self,
            profile_id,
            frontend,
            method,
            secret,
            persist_receipt,
            deadline,
        )
        .map_err(|refusal| self.fail(refusal))
    }

    /// Signs `profile_id` in with `password`. With `persist_receipt`, the
    /// runtime stores the sign-in for the person's other frontends.
    pub fn login_password(
        &self,
        profile_id: &str,
        frontend: Frontend,
        password: &[u8],
        persist_receipt: bool,
        deadline: Instant,
    ) -> Result<Admitted, Refusal> {
        self.login(
            profile_id,
            frontend,
            "password",
            password,
            persist_receipt,
            deadline,
        )
    }

    /// Resumes the stored sign-in of `profile_id` by presenting its `proof`.
    pub fn login_receipt(
        &self,
        profile_id: &str,
        frontend: Frontend,
        proof: &[u8],
        deadline: Instant,
    ) -> Result<Admitted, Refusal> {
        self.login(profile_id, frontend, "receipt", proof, false, deadline)
    }

    /// Resumes the stored sign-in of `profile_id` from `storage_root` with the
    /// proof its receipt names, as every other frontend resumes it.
    ///
    /// A sign-in that completes between reading the proof and the runtime's
    /// check replaces the receipt, so the proof read before it no longer
    /// unwraps the one the runtime reads. Such a refusal is retried with a
    /// fresh read, a bounded number of times and only while the proof differs
    /// from the one refused.
    pub fn resume_receipt(
        &self,
        storage_root: &Path,
        profile_id: &str,
        frontend: Frontend,
        deadline: Instant,
    ) -> Result<Admitted, ResumeRefusal> {
        present_stored_proof(
            storage_root,
            profile_id,
            deadline,
            || self.closed(),
            |proof| self.login_receipt(profile_id, frontend, proof, deadline),
        )
    }

    /// Rechecks `session` without extending it; the runtime's status object.
    pub fn status(
        &self,
        session: &Admitted,
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        session_status(self, session, deadline).map_err(|refusal| self.fail(refusal))
    }

    /// Reports the person's own input on `session`, which may extend it.
    pub fn note_activity(&self, session: &Admitted, deadline: Instant) -> Result<(), Refusal> {
        let reply = session_exchange(self, "session_activity", session, deadline)?;
        match reply
            .get("status")
            .and_then(Value::as_object)
            .and_then(denial)
        {
            Some(refusal) => Err(refusal),
            None => Ok(()),
        }
    }

    /// Signs the person out of the profile everywhere: the stored sign-in is
    /// revoked and every human session of the profile ends.
    pub fn sign_out(&self, session: &Admitted, deadline: Instant) -> Result<SignedOut, Refusal> {
        human_sign_out(self, session, deadline).map_err(|refusal| self.fail(refusal))
    }
}

/// Asks the runtime for one of `session`'s own actions, which names no more than its identity.
pub(super) fn session_exchange(
    exchange: &dyn SessionExchange,
    action: &str,
    session: &Admitted,
    deadline: Instant,
) -> Result<Map<String, Value>, Refusal> {
    exchange.exchange(
        &json!({
            "action": action,
            "request_id": request_id(),
            "profile_id": session.profile_id,
            "session_id": session.session_id,
        }),
        deadline,
    )
}

/// Rechecks `session` without extending it, through whatever carries its
/// exchanges: the runtime's status object.
pub fn session_status(
    exchange: &dyn SessionExchange,
    session: &Admitted,
    deadline: Instant,
) -> Result<Map<String, Value>, Refusal> {
    session_exchange(exchange, "session_status", session, deadline)?
        .get("status")
        .and_then(Value::as_object)
        .cloned()
        .ok_or(Refusal::InvalidFrame)
}

/// Where `session` stands now. A refusal the runtime answers in place of a
/// status is a standing too; a lost or failed exchange is not.
pub fn session_standing(
    exchange: &dyn SessionExchange,
    session: &Admitted,
    deadline: Instant,
) -> Result<Standing, Refusal> {
    match session_status(exchange, session, deadline) {
        Ok(status) => Ok(Standing::of(&status, session)),
        Err(Refusal::Denied {
            code,
            recovery_remaining_seconds,
            ..
        }) => Ok(if code == CUSTODY_RECOVERING {
            Standing::Recovering {
                remaining_seconds: recovery_remaining_seconds,
            }
        } else {
            Standing::Refused(code)
        }),
        Err(refusal) => Err(refusal),
    }
}

/// Sends one `profile_login` with its `secret` and reads the session it admits.
pub(super) fn present_login(
    exchange: &dyn SessionExchange,
    profile_id: &str,
    frontend: Frontend,
    method: &str,
    secret: &[u8],
    persist_receipt: bool,
    deadline: Instant,
) -> Result<Admitted, Refusal> {
    let changed = exchange.subscribe_scoped();
    let request = json!({
        "action": "profile_login",
        "request_id": request_id(),
        "profile_id": profile_id,
        "frontend": frontend.as_str(),
        "method": method,
        "persist_receipt": persist_receipt,
    });
    let mut reply = exchange.exchange_with_secret(&request, secret, deadline)?;
    if text(&reply, "kind") == Some("profile_login_pending") {
        let login_request_id = text(&reply, "login_request_id")
            .filter(|id| is_uuid(id))
            .ok_or(Refusal::InvalidFrame)?
            .to_owned();
        if login_request_id != request["request_id"].as_str().unwrap_or_default()
            || text(&reply, "profile_id") != Some(profile_id)
        {
            return Err(Refusal::InvalidFrame);
        }
        loop {
            reply = exchange.exchange(
                &json!({
                    "action": "profile_login_status", "request_id": request_id(),
                    "profile_id": profile_id, "login_request_id": login_request_id,
                }),
                deadline,
            )?;
            if text(&reply, "kind") != Some("profile_login_pending") {
                break;
            }
            loop {
                let remaining = deadline
                    .checked_duration_since(Instant::now())
                    .ok_or(Refusal::Timeout)?;
                let cue = changed
                    .recv_timeout(remaining)
                    .map_err(|error| match error {
                        mpsc::RecvTimeoutError::Timeout => Refusal::Timeout,
                        mpsc::RecvTimeoutError::Disconnected => Refusal::ConnectionClosed,
                    })?;
                match cue.event {
                    Event::Disconnected => return Err(Refusal::ConnectionClosed),
                    Event::ProfileLoginChanged {
                        login_request_id: changed,
                    } if changed == login_request_id
                        && cue.profile_id.as_deref() == Some(profile_id) =>
                    {
                        break;
                    }
                    _ => {}
                }
            }
        }
    }
    admitted(&reply, profile_id)
}

/// Presents a fresh proof for `session` on the connection that holds it. A
/// suspended session returns under its own identity; a login that admits
/// another one is no rebind.
pub(super) fn rebind(
    exchange: &dyn SessionExchange,
    session: &Admitted,
    frontend: Frontend,
    method: &str,
    secret: &[u8],
    persist_receipt: bool,
    deadline: Instant,
) -> Result<Admitted, Refusal> {
    let rebound = present_login(
        exchange,
        &session.profile_id,
        frontend,
        method,
        secret,
        persist_receipt,
        deadline,
    )?;
    if rebound.session_id != session.session_id {
        return Err(Refusal::denied("session_mismatch"));
    }
    Ok(rebound)
}

/// Rebinds a suspended `session` on the connection that holds it, by the
/// profile's `password`. The sign-in is stored for the person's other
/// frontends, as the window's own password sign-in stores it.
pub fn rebind_password(
    exchange: &dyn SessionExchange,
    session: &Admitted,
    frontend: Frontend,
    password: &[u8],
    deadline: Instant,
) -> Result<Admitted, Refusal> {
    rebind(
        exchange, session, frontend, "password", password, true, deadline,
    )
}

/// Rebinds a suspended `session` on the connection that holds it, by the
/// proof of the stored sign-in under `storage_root`, read fresh as every
/// presentation of it is.
pub fn rebind_receipt(
    exchange: &dyn SessionExchange,
    storage_root: &Path,
    session: &Admitted,
    frontend: Frontend,
    deadline: Instant,
) -> Result<Admitted, ResumeRefusal> {
    present_stored_proof(
        storage_root,
        &session.profile_id,
        deadline,
        || false,
        |proof| {
            rebind(
                exchange, session, frontend, "receipt", proof, false, deadline,
            )
        },
    )
}

/// Signs the person out of `session`'s profile everywhere, through whatever
/// carries that session's exchanges: the stored sign-in is revoked and every
/// human session of the profile ends.
pub fn human_sign_out(
    exchange: &dyn SessionExchange,
    session: &Admitted,
    deadline: Instant,
) -> Result<SignedOut, Refusal> {
    let reply = exchange.exchange(
        &json!({
            "action": "human_sign_out",
            "request_id": request_id(),
            "profile_id": session.profile_id,
            "session_id": session.session_id,
        }),
        deadline,
    )?;
    if text(&reply, "kind") != Some("human_signed_out") {
        return Err(Refusal::InvalidFrame);
    }
    let flag = |key: &str| reply.get(key).and_then(Value::as_bool).unwrap_or(false);
    Ok(SignedOut {
        session_ids: uuid_list(reply.get("session_ids")),
        receipt_removed: flag("receipt_removed"),
        keychain_removed: flag("keychain_removed"),
        automation_enabled: reply.get("automation_enabled").and_then(Value::as_bool),
        automation_access_remains: reply
            .get("automation_access_remains")
            .and_then(Value::as_bool),
    })
}
