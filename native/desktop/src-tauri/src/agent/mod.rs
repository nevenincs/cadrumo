//! The desktop's verified agent service host.
//!
//! It runs the dedicated installed service image while the
//! person's sign-in allows it, supervised in a kill-on-close job, and serves
//! the agent column a closed list of token-checked commands over the
//! launcher's loopback gateway, with each run's stream on a Tauri channel.
//! The launcher admits the agent bundled by CMake or returns a typed refusal.

mod admin;
mod dropping;
mod gateway;
mod launcher;
pub(crate) mod model_roles;
pub(crate) mod person;
pub(crate) mod runner;
mod session;
mod sse;
mod stream;
mod supervisor;
mod upload;

use crate::{
    app::Commands,
    environment::Launch,
    shell::sign_in::{Presence, SignIn},
};
use cadrumo_application::{diagnostics::Diagnostics, error::application::Result};
use serde::Serialize;
use serde_json::Value;
use session::{Answer, RequestRef, SendRequest, Session};
use std::sync::Arc;
use stream::StreamEvent;
use supervisor::{Observation, Status, Supervisor};
use tauri::{Manager, Runtime, State, ipc::Channel, plugin::TauriPlugin};

/// A refusal the column words from its stable code.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Refused {
    pub code: String,
}

impl Refused {
    pub fn new(code: String) -> Self {
        Self { code }
    }
}

/// The agent host one window serves.
pub struct AgentHost {
    supervisor: Supervisor,
    session: Session,
    diagnostics: Arc<Diagnostics>,
    sign_in: Arc<SignIn>,
    drops: dropping::Drops,
    attendance: std::sync::Mutex<Option<(u32, tauri::async_runtime::JoinHandle<()>)>>,
}

impl AgentHost {
    fn new(sign_in: Arc<SignIn>, diagnostics: Arc<Diagnostics>) -> Self {
        let watched = sign_in.clone();
        let changed: supervisor::Changed =
            Arc::new(move || Box::pin(watched.observation_changed()));
        let held = sign_in.clone();
        let observed = sign_in.clone();
        let observe = Arc::new(move || {
            let sign_in = observed.clone();
            Box::pin(async move {
                sign_in.read_status().await.map(|status| Observation {
                    supported: status.supported,
                    present: status.state == Presence::Present,
                    runtime_available: status.runtime_available,
                    refused: status.refusal.is_some(),
                    active_profile: status.active_profile,
                })
            }) as std::pin::Pin<Box<dyn Future<Output = Result<Observation>> + Send>>
        });
        let launch: supervisor::Launch = Arc::new(move |_bearer: &str, profile: &str| {
            let profile_id = sign_in.profile_id(profile)?;
            let person = sign_in.person(&profile_id)?;
            let mut command = sign_in.service()?.command();
            command.args(["serve", "--profile-id", &profile_id]);
            Ok(supervisor::Prepared {
                command,
                person: Some(person),
            })
        });
        Self {
            supervisor: Supervisor::new(observe, changed, Some(launch), diagnostics.clone()),
            session: Session::default(),
            diagnostics,
            sign_in: held,
            drops: dropping::Drops::default(),
            attendance: std::sync::Mutex::new(None),
        }
    }

    /// Stops the launcher and everything it started, for good.
    pub async fn close(&self) -> Result<()> {
        self.drops.clear(None);
        self.stop_attendance(None);
        self.session.close();
        self.supervisor.close().await
    }

    /// The person's own session, held for the profile signed in now. Deciding
    /// who follows the person's sign-in is the person's act, whether or not an
    /// agent service runs.
    fn person(&self) -> Result<person::HeldPerson> {
        let status = self.sign_in.current_observation()?;
        let signed_in = status.state == Presence::Present && status.runtime_ready();
        let profile = status.active_profile.filter(|_| signed_in).ok_or_else(|| {
            cadrumo_application::error::application::ApplicationError::new(
                cadrumo_application::error::application::ErrorCode::ReadFailed,
                cadrumo_application::error::application::Operation::Cli,
            )
            .with_reason("person_not_signed_in")
        })?;
        self.sign_in.person(&self.sign_in.profile_id(&profile)?)
    }

    fn person_request(&self, request: Value) -> Result<Value> {
        let person = self.person()?;
        let mut held = person.lock().unwrap_or_else(|e| e.into_inner());
        held.exchange(request)
    }

    /// Ends the attendance forwarding `subscription`, or any when none is named.
    fn stop_attendance(&self, subscription: Option<u32>) {
        let mut attendance = self.attendance.lock().unwrap_or_else(|e| e.into_inner());
        if attendance
            .as_ref()
            .is_some_and(|(id, _)| subscription.is_none_or(|wanted| *id == wanted))
            && let Some((_, forwarding)) = attendance.take()
        {
            forwarding.abort();
        }
    }

    pub(crate) fn administer(
        &self,
        request: Value,
        secret: Option<zeroize::Zeroizing<Vec<u8>>>,
    ) -> Result<Value> {
        if !matches!(request["action"].as_str(), Some("catalog" | "status")) {
            self.require_person()?;
        }
        self.supervisor.administer(request, secret)
    }

    fn require_person(&self) -> Result<()> {
        let reply = self
            .supervisor
            .person_request(serde_json::json!({"action":"status"}))?;
        if reply["kind"] != "profile_status"
            || reply["status"]["credential_authenticated"] != true
            || reply["status"]["session_id"].is_null()
            || !reply["status"]["denial"].is_null()
        {
            return Err(
                cadrumo_application::error::application::ApplicationError::new(
                    cadrumo_application::error::application::ErrorCode::ReadFailed,
                    cadrumo_application::error::application::Operation::Cli,
                )
                .with_reason("person_not_signed_in"),
            );
        }
        Ok(())
    }

    /// The column receives a stable code; failures outside initial admission
    /// retain their reason and cause chain in diagnostics.
    fn refuse(
        &self,
        code: &str,
        error: cadrumo_application::error::application::ApplicationError,
    ) -> Refused {
        command_refusal(
            &self.diagnostics,
            &self.supervisor.status().state,
            code,
            error,
        )
    }
}

/// Calls racing service admission are retryable; other failures keep their diagnostics.
fn command_refusal(
    diagnostics: &Diagnostics,
    state: &supervisor::State,
    code: &str,
    error: cadrumo_application::error::application::ApplicationError,
) -> Refused {
    use cadrumo_application::error::application::ErrorCode;
    let awaiting_admission = matches!(state, supervisor::State::Starting)
        && matches!(
            (error.code, error.reason.as_deref()),
            (
                ErrorCode::SessionUnavailable,
                Some("agent_service_unavailable")
            ) | (ErrorCode::ReadFailed, Some("agent_admin_unavailable"))
        );
    if awaiting_admission {
        return Refused::new("agent_service_busy".to_owned());
    }
    diagnostics.host_failure(cadrumo_application::diagnostics::HostStage::Agent, error);
    Refused::new(code.to_owned())
}

/// Registers the host once the shell's sign-in owner exists.
/// The host's own file dialog, for the files the agent column attaches. The
/// webview is granted none of its commands.
pub fn dialog_plugin<R: Runtime>() -> TauriPlugin<R> {
    tauri_plugin_dialog::init()
}

pub fn plugin<R: Runtime>(launch: &Launch) -> TauriPlugin<R> {
    let diagnostics = launch.diagnostics.clone();
    tauri::plugin::Builder::new("cadrumo-agent")
        .setup(move |app, _| {
            let sign_in = app.state::<Arc<SignIn>>().inner().clone();
            app.manage(Arc::new(AgentHost::new(sign_in, diagnostics.clone())));
            Ok(())
        })
        .build()
}

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![
        agent_status,
        agent_retry,
        agent_status_subscribe,
        agent_status_unsubscribe,
        agent_provider_catalog,
        agent_model_roles,
        agent_model_role_set,
        agent_model_role_clear,
        agent_model_licence,
        agent_skills,
        agent_skill,
        agent_skill_verify,
        agent_conversation_start,
        agent_conversation_rename,
        agent_conversation_delete,
        agent_conversation_archive,
        agent_send,
        agent_cancel,
        agent_pending,
        agent_questions_answer,
        agent_approval_decide,
        agent_observe,
        agent_unobserve,
        agent_conversations,
        agent_history,
        agent_snapshot,
        agent_documents,
        agent_attach,
        agent_drop_observe,
        agent_drop_unobserve,
        runtime_attendance_inventory,
        runtime_attendance_decide,
        runtime_attendance_subscribe,
        runtime_attendance_unsubscribe
    ]
}

#[tauri::command]
async fn runtime_attendance_inventory(host: State<'_, Arc<AgentHost>>) -> Result<Value> {
    let host = host.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        host.person_request(serde_json::json!({"action":"attendance_inventory"}))
    })
    .await
    .map_err(|_| {
        cadrumo_application::error::application::ApplicationError::new(
            cadrumo_application::error::application::ErrorCode::Panic,
            cadrumo_application::error::application::Operation::Cli,
        )
    })?
}

#[tauri::command]
async fn runtime_attendance_decide(
    host: State<'_, Arc<AgentHost>>,
    attendance_id: String,
    approve: bool,
) -> Result<Value> {
    if !crate::shell::agent_access::wire::is_uuid(&attendance_id) {
        return Err(
            cadrumo_application::error::application::ApplicationError::new(
                cadrumo_application::error::application::ErrorCode::InvalidArguments,
                cadrumo_application::error::application::Operation::Cli,
            ),
        );
    }
    let host = host.inner().clone();
    tauri::async_runtime::spawn_blocking(move || host.person_request(serde_json::json!({"action":"attendance_decision", "attendance_id":attendance_id,"approve":approve})))
        .await.map_err(|_| cadrumo_application::error::application::ApplicationError::new(cadrumo_application::error::application::ErrorCode::Panic, cadrumo_application::error::application::Operation::Cli))?
}

/// Tells the window each time the asks pending for the person may have changed,
/// as the runtime pushes it; the window then reads the inventory again. One
/// window listens at a time, and a newer subscription replaces an older one.
#[tauri::command]
async fn runtime_attendance_subscribe(
    host: State<'_, Arc<AgentHost>>,
    updates: Channel<()>,
) -> Result<u32> {
    use person::PersonEvent;
    use tokio::sync::broadcast::error::RecvError;
    let subscription = updates.id();
    let mut events = host.sign_in.person_events();
    let forwarding = tauri::async_runtime::spawn(async move {
        loop {
            let changed = match events.recv().await {
                Ok(PersonEvent::AttendanceChanged) | Err(RecvError::Lagged(_)) => true,
                Ok(
                    PersonEvent::LanguageChanged
                    | PersonEvent::RecordsChanged
                    | PersonEvent::OperationChanged
                    | PersonEvent::Retired,
                ) => false,
                Err(RecvError::Closed) => return,
            };
            if changed && updates.send(()).is_err() {
                return;
            }
        }
    });
    host.stop_attendance(None);
    *host.attendance.lock().unwrap_or_else(|e| e.into_inner()) = Some((subscription, forwarding));
    Ok(subscription)
}

#[tauri::command]
fn runtime_attendance_unsubscribe(host: State<'_, Arc<AgentHost>>, subscription: u32) {
    host.stop_attendance(Some(subscription));
}

/// Runs a gateway call off the async workers.
async fn blocking<T: Send + 'static>(
    host: &State<'_, Arc<AgentHost>>,
    work: impl FnOnce(&AgentHost) -> std::result::Result<T, Refused> + Send + 'static,
) -> std::result::Result<T, Refused> {
    let host = host.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        host.require_person()
            .map_err(|error| host.refuse(person_refusal(&error), error))?;
        work(&host)
    })
    .await
    .map_err(|_| Refused::new("agent_host_failed".to_owned()))?
}

/// A service still starting or recovering does not mean the person signed out.
fn person_refusal(
    error: &cadrumo_application::error::application::ApplicationError,
) -> &'static str {
    match error.reason.as_deref() {
        Some("agent_service_unavailable") => "agent_service_busy",
        Some("person_not_signed_in" | "person_request_refused" | "person_session_retired") => {
            "agent_signed_out"
        }
        _ => "agent_service_failed",
    }
}

/// What an administration failure tells the column: a service that did not
/// answer in time, or let a connection go while it was busy, is busy and
/// can be asked again; anything else failed.
fn admin_refusal(
    error: &cadrumo_application::error::application::ApplicationError,
) -> &'static str {
    use cadrumo_application::error::application::ErrorCode;
    use std::io::ErrorKind;
    let transient = error.code == ErrorCode::TimedOut
        || matches!(
            error.io_kind,
            Some(ErrorKind::TimedOut | ErrorKind::ConnectionReset | ErrorKind::ConnectionAborted)
        );
    if transient {
        "agent_service_busy"
    } else {
        "agent_service_failed"
    }
}

fn selection_refusal(
    error: &crate::shell::provider_settings::wire::CommandFailure,
) -> &'static str {
    use crate::shell::provider_settings::wire::{CommandFailure, Refusal};
    match error {
        CommandFailure::Host(error) => admin_refusal(error),
        CommandFailure::Refused(refused) => match refused.code {
            Refusal::Busy => "agent_service_busy",
            Refusal::NotSignedIn | Refusal::ProfileLocked => "agent_signed_out",
            Refusal::CatalogUnavailable | Refusal::RuntimeUnavailable => "agent_service_not_ready",
            _ => "agent_service_failed",
        },
    }
}

/// Whether the service answered that it is still working on the request.
fn catalog_busy(answer: &Value) -> bool {
    answer["kind"] == "refused" && answer["code"] == "busy"
}

fn refused<T>(code: &str) -> std::result::Result<T, Refused> {
    Err(Refused::new(code.to_owned()))
}

#[tauri::command]
async fn agent_status(host: State<'_, Arc<AgentHost>>) -> Result<Status> {
    Ok(host.supervisor.status())
}

#[tauri::command]
async fn agent_retry(host: State<'_, Arc<AgentHost>>) -> Result<()> {
    let host = host.inner().clone();
    tauri::async_runtime::spawn_blocking(move || host.supervisor.restart_agent())
        .await
        .map_err(|_| {
            cadrumo_application::error::application::ApplicationError::new(
                cadrumo_application::error::application::ErrorCode::Panic,
                cadrumo_application::error::application::Operation::Cli,
            )
        })?
}

#[tauri::command]
async fn agent_status_subscribe(
    host: State<'_, Arc<AgentHost>>,
    updates: Channel<Status>,
) -> Result<u32> {
    Ok(host.supervisor.subscribe(updates))
}

#[tauri::command]
async fn agent_status_unsubscribe(
    host: State<'_, Arc<AgentHost>>,
    subscription: u32,
) -> Result<()> {
    host.supervisor.unsubscribe(subscription);
    Ok(())
}

/// cadrumo-agent's provider catalog, relayed unchanged and unfiltered.
#[tauri::command]
async fn agent_provider_catalog(
    host: State<'_, Arc<AgentHost>>,
) -> std::result::Result<Value, Refused> {
    blocking(&host, |host| {
        let catalog = host
            .administer(serde_json::json!({"action":"catalog"}), None)
            .map_err(|error| host.refuse(admin_refusal(&error), error))?;
        // The service still working on it answers busy and keeps the answer
        // for the next read, which the column makes.
        if catalog_busy(&catalog) {
            return refused("agent_service_busy");
        }
        Ok(catalog)
    })
    .await
}

/// The person's model selection for every role, as the agent service stores it.
#[tauri::command]
async fn agent_model_roles(
    host: State<'_, Arc<AgentHost>>,
) -> std::result::Result<model_roles::ModelRoles, Refused> {
    blocking(&host, |host| {
        let answer = host
            .administer(serde_json::json!({"action":"model_roles"}), None)
            .map_err(|error| host.refuse(admin_refusal(&error), error))?;
        if let Some(code) = model_roles::refusal(&answer) {
            return refused(code);
        }
        model_roles::parse(&answer).ok_or_else(|| {
            host.refuse(
                "agent_service_failed",
                cadrumo_application::error::application::ApplicationError::new(
                    cadrumo_application::error::application::ErrorCode::ReadFailed,
                    cadrumo_application::error::application::Operation::Cli,
                )
                .with_reason("admin_model_roles_contract"),
            )
        })
    })
    .await
}

/// One guarded change to the person's selections, answered with every role's
/// selection after it or the reason it was not made.
fn change_model_roles(
    host: &AgentHost,
    request: Value,
) -> std::result::Result<model_roles::ModelRoles, Refused> {
    let answer = host
        .administer(request, None)
        .map_err(|error| host.refuse(admin_refusal(&error), error))?;
    if let Some(code) = model_roles::change_refusal(&answer) {
        return refused(code);
    }
    model_roles::parse(&answer).ok_or_else(|| {
        host.refuse(
            "agent_service_failed",
            cadrumo_application::error::application::ApplicationError::new(
                cadrumo_application::error::application::ErrorCode::ReadFailed,
                cadrumo_application::error::application::Operation::Cli,
            )
            .with_reason("admin_model_roles_contract"),
        )
    })
}

/// Selects `lane` and `model` for `role`, at the revision the person read.
#[tauri::command]
async fn agent_model_role_set(
    host: State<'_, Arc<AgentHost>>,
    role: String,
    lane: String,
    model: String,
    expected_revision: String,
) -> std::result::Result<model_roles::ModelRoles, Refused> {
    if !model_roles::is_role(&role)
        || !model_roles::is_lane(&lane)
        || !model_roles::is_model(&model)
        || !model_roles::is_revision(&expected_revision)
    {
        return refused("agent_invalid_request");
    }
    blocking(&host, move |host| {
        change_model_roles(
            host,
            serde_json::json!({
                "action": "model_role_set",
                "role": role,
                "provider": lane,
                "model": model,
                "expected_revision": expected_revision,
            }),
        )
    })
    .await
}

/// Clears the selection for `role`, at the revision the person read.
#[tauri::command]
async fn agent_model_role_clear(
    host: State<'_, Arc<AgentHost>>,
    role: String,
    expected_revision: String,
) -> std::result::Result<model_roles::ModelRoles, Refused> {
    if !model_roles::is_role(&role) || !model_roles::is_revision(&expected_revision) {
        return refused("agent_invalid_request");
    }
    blocking(&host, move |host| {
        change_model_roles(
            host,
            serde_json::json!({
                "action": "model_role_clear",
                "role": role,
                "expected_revision": expected_revision,
            }),
        )
    })
    .await
}

/// The licence text of one model a lane lists, relayed from the ready agent.
#[tauri::command]
async fn agent_model_licence(
    host: State<'_, Arc<AgentHost>>,
    provider: String,
    transport: String,
    model: String,
) -> std::result::Result<Value, Refused> {
    // A provider identity has the grammar of a role: a lowercase slug of up to 64.
    if !model_roles::is_role(&provider)
        || !matches!(transport.as_str(), "api" | "cli")
        || !model_roles::is_model(&model)
    {
        return refused("agent_invalid_request");
    }
    blocking(&host, move |host| {
        gateway::Client::new(&Session::gateway(&host.supervisor)?)
            .licence(&provider, &transport, &model)
    })
    .await
}

/// cadrumo-agent's skills, relayed unchanged.
#[tauri::command]
async fn agent_skills(host: State<'_, Arc<AgentHost>>) -> std::result::Result<Value, Refused> {
    blocking(&host, |host| {
        gateway::Client::new(&Session::gateway(&host.supervisor)?).skills()
    })
    .await
}

/// One skill with its SKILL.md, for a name of the skill grammar.
#[tauri::command]
async fn agent_skill(
    host: State<'_, Arc<AgentHost>>,
    name: String,
) -> std::result::Result<Value, Refused> {
    if !session::skill_name(&name) {
        return refused("agent_invalid_request");
    }
    blocking(&host, move |host| {
        gateway::Client::new(&Session::gateway(&host.supervisor)?).skill(&name)
    })
    .await
}

/// The agent's checks of one skill, for a name of the skill grammar.
#[tauri::command]
async fn agent_skill_verify(
    host: State<'_, Arc<AgentHost>>,
    name: String,
) -> std::result::Result<Value, Refused> {
    if !session::skill_name(&name) {
        return refused("agent_invalid_request");
    }
    blocking(&host, move |host| {
        gateway::Client::new(&Session::gateway(&host.supervisor)?).verify_skill(&name)
    })
    .await
}

/// Reserves a conversation: the id its first run will have.
#[tauri::command]
async fn agent_conversation_start(
    host: State<'_, Arc<AgentHost>>,
) -> std::result::Result<Value, Refused> {
    blocking(&host, |host| {
        host.session.start_conversation(&host.supervisor)
    })
    .await
}

/// Gives a conversation the title the person chose.
#[tauri::command]
async fn agent_conversation_rename(
    host: State<'_, Arc<AgentHost>>,
    conversation_id: String,
    title: String,
) -> std::result::Result<(), Refused> {
    blocking(&host, move |host| {
        host.session
            .rename(&host.supervisor, &conversation_id, &title)
    })
    .await
}

/// Deletes a conversation with every run of it and the documents stored for it.
#[tauri::command]
async fn agent_conversation_delete(
    host: State<'_, Arc<AgentHost>>,
    conversation_id: String,
) -> std::result::Result<(), Refused> {
    blocking(&host, move |host| {
        host.session.delete(&host.supervisor, &conversation_id)
    })
    .await
}

/// Archives the whole settled conversation, preserving its records.
#[tauri::command]
async fn agent_conversation_archive(
    host: State<'_, Arc<AgentHost>>,
    conversation_id: String,
) -> std::result::Result<(), Refused> {
    blocking(&host, move |host| {
        host.session.archive(&host.supervisor, &conversation_id)
    })
    .await
}

#[tauri::command]
async fn agent_send(
    host: State<'_, Arc<AgentHost>>,
    request: SendRequest,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        session::admit_send(&request)?;
        let gateway = host
            .supervisor
            .gateway()
            .ok_or_else(|| Refused::new("agent_service_not_ready".to_owned()))?;
        let available = crate::shell::provider_settings::agent_selection_available(
            host,
            &request.selection.provider,
            &request.selection.transport,
        )
        .map_err(|error| {
            let code = selection_refusal(&error);
            match error {
                crate::shell::provider_settings::wire::CommandFailure::Host(error) => {
                    host.refuse(code, error)
                }
                // A correlated busy/signed-out response is not a broken child
                // stream. Preserve the response without inventing an I/O failure.
                _ => Refused::new(code.to_owned()),
            }
        })?;
        if !available {
            return refused("agent_provider_credential_missing");
        }
        host.session.send(&host.supervisor, &request, &gateway)
    })
    .await
}

#[tauri::command]
async fn agent_cancel(
    host: State<'_, Arc<AgentHost>>,
    reply_id: String,
) -> std::result::Result<(), Refused> {
    blocking(&host, move |host| {
        host.session.cancel(&host.supervisor, &reply_id)
    })
    .await
}

#[tauri::command]
async fn agent_pending(
    host: State<'_, Arc<AgentHost>>,
    conversation_id: String,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        host.session.pending(&host.supervisor, &conversation_id)
    })
    .await
}

#[tauri::command]
async fn agent_questions_answer(
    host: State<'_, Arc<AgentHost>>,
    questionnaire: RequestRef,
    answer: Answer,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        host.session
            .answer(&host.supervisor, &questionnaire, &answer)
    })
    .await
}

/// Answers a tool approval. Cadrumo reviews are not served.
#[tauri::command]
async fn agent_approval_decide(
    host: State<'_, Arc<AgentHost>>,
    approval: RequestRef,
    option_id: String,
) -> std::result::Result<(), Refused> {
    blocking(&host, move |host| {
        host.session.decide(&host.supervisor, &approval, &option_id)
    })
    .await
}

#[tauri::command]
async fn agent_observe(
    host: State<'_, Arc<AgentHost>>,
    conversation_id: String,
    events: Channel<StreamEvent>,
) -> std::result::Result<u32, Refused> {
    blocking(&host, move |host| {
        host.session
            .observe(&host.supervisor, &conversation_id, events)
    })
    .await
}

#[tauri::command]
async fn agent_unobserve(
    host: State<'_, Arc<AgentHost>>,
    subscription: u32,
) -> std::result::Result<(), Refused> {
    host.session.unobserve(subscription);
    Ok(())
}

/// Every conversation: each chain of runs, and those reserved here.
#[tauri::command]
async fn agent_conversations(
    host: State<'_, Arc<AgentHost>>,
) -> std::result::Result<Value, Refused> {
    blocking(&host, |host| host.session.conversations(&host.supervisor)).await
}

/// A conversation's records, composed from its runs.
#[tauri::command]
async fn agent_history(
    host: State<'_, Arc<AgentHost>>,
    conversation_id: String,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        host.session.history(&host.supervisor, &conversation_id)
    })
    .await
}

/// A single read of the conversation and what its current reply waits on.
#[tauri::command]
async fn agent_snapshot(
    host: State<'_, Arc<AgentHost>>,
    conversation_id: String,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        host.session.snapshot(&host.supervisor, &conversation_id)
    })
    .await
}

/// One page of the documents stored for a conversation, which its messages
/// can name; never their bytes, and never where they are kept.
#[tauri::command]
async fn agent_documents(
    host: State<'_, Arc<AgentHost>>,
    query: session::DocumentsQuery,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        host.session.documents(&host.supervisor, &query)
    })
    .await
}

/// Opens the host's file dialog over the window, for files of the kinds the
/// conversation's storage takes, and streams each one the person picks into
/// that storage. It answers with what was picked, each queued or refused
/// already, and follows each upload on `updates`. The page never learns a
/// file's path or reads its bytes. A dialog closed without a pick picks
/// nothing.
#[tauri::command]
async fn agent_attach<R: Runtime>(
    host: State<'_, Arc<AgentHost>>,
    window: tauri::WebviewWindow<R>,
    conversation_id: String,
    filter_label: String,
    drop_id: Option<String>,
    updates: Channel<upload::UploadEvent>,
) -> std::result::Result<Vec<upload::Picked>, Refused> {
    use tauri_plugin_dialog::DialogExt;
    if !gateway::run_id(&conversation_id)
        || filter_label.is_empty()
        || filter_label.chars().count() > 64
        || filter_label.chars().any(char::is_control)
    {
        return refused("agent_invalid_request");
    }
    blocking(&host, move |host| {
        let gateway = Session::gateway(&host.supervisor)?;
        let policy = upload::policy_of(&gateway::Client::new(&gateway).attachment_policy()?)?;
        let extensions: Vec<&str> = policy.extensions.iter().map(String::as_str).collect();
        // The packaged test host takes the lane's files where the lane gives
        // some; every other build always asks the person.
        let paths: Vec<std::path::PathBuf> = if let Some(id) = drop_id {
            host.drops.take(&id, &gateway)?
        } else {
            match upload::lane_picks(upload::lane_directory()) {
                Some(paths) => paths,
                None => window
                    .dialog()
                    .file()
                    .set_parent(&window)
                    .add_filter(filter_label, &extensions)
                    .blocking_pick_files()
                    .unwrap_or_default()
                    .into_iter()
                    .filter_map(|picked| picked.into_path().ok())
                    .collect(),
            }
        };
        let (picked, queued) = upload::stage(paths, &policy);
        if !queued.is_empty() {
            std::thread::spawn(move || {
                upload::send_all(&gateway, &conversation_id, queued, &updates);
            });
        }
        Ok(picked)
    })
    .await
}

/// Watches native drags without exposing file paths to the webview.
#[tauri::command]
async fn agent_drop_observe<R: Runtime>(
    host: State<'_, Arc<AgentHost>>,
    window: tauri::WebviewWindow<R>,
    updates: Channel<dropping::Signal>,
) -> std::result::Result<u32, Refused> {
    let subscription = blocking(&host, move |host| {
        Ok(host
            .drops
            .observe(updates, Session::gateway(&host.supervisor)?))
    })
    .await?;
    if !host
        .drops
        .listening
        .swap(true, std::sync::atomic::Ordering::AcqRel)
    {
        let owner = host.inner().clone();
        let observed = window.clone();
        window.on_window_event(move |event| {
            if let tauri::WindowEvent::DragDrop(drag) = event
                && let Ok(scale) = observed.scale_factor()
            {
                owner.drops.event(drag, scale);
            }
        });
    }
    Ok(subscription)
}

#[tauri::command]
fn agent_drop_unobserve(host: State<'_, Arc<AgentHost>>, subscription: u32) {
    host.drops.clear(Some(subscription));
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation};

    #[test]
    fn admission_races_are_quiet_and_retryable_only_while_starting() {
        for (code, reason) in [
            (ErrorCode::SessionUnavailable, "agent_service_unavailable"),
            (ErrorCode::ReadFailed, "agent_admin_unavailable"),
        ] {
            for (state, expected, failures) in [
                (supervisor::State::Starting, "agent_service_busy", 0),
                (supervisor::State::Stopped, "agent_service_failed", 1),
                (
                    supervisor::State::Ready {
                        agent_version: "synthetic".into(),
                    },
                    "agent_service_failed",
                    1,
                ),
                (
                    supervisor::State::Refused {
                        code: supervisor::Refusal::ServiceFailed,
                    },
                    "agent_service_failed",
                    1,
                ),
            ] {
                let diagnostics = Diagnostics::default();
                let error = ApplicationError::new(code, Operation::Cli).with_reason(reason);
                let refused = command_refusal(&diagnostics, &state, "agent_service_failed", error);
                assert_eq!(refused.code, expected);
                assert_eq!(diagnostics.snapshot(u64::MAX).events.len(), failures);
            }
        }
    }

    #[test]
    fn unexpected_startup_failures_remain_visible() {
        for (code, reason) in [
            (ErrorCode::ReadFailed, "admin_document_parse"),
            (ErrorCode::Panic, "agent_admin_unavailable"),
            (ErrorCode::SessionUnavailable, "person_session_retired"),
        ] {
            let diagnostics = Diagnostics::default();
            let error = ApplicationError::new(code, Operation::Cli).with_reason(reason);
            let refused = command_refusal(
                &diagnostics,
                &supervisor::State::Starting,
                "agent_service_failed",
                error,
            );
            assert_eq!(refused.code, "agent_service_failed");
            let snapshot = diagnostics.snapshot(u64::MAX);
            assert_eq!(snapshot.events.len(), 1);
            assert_eq!(snapshot.events[0].failure.as_ref().unwrap().code, code);
        }
    }

    #[test]
    fn provider_selection_preserves_busy_and_sign_in_refusals() {
        use crate::shell::provider_settings::wire::{CommandFailure, Refusal};
        for (refusal, expected) in [
            (Refusal::Busy, "agent_service_busy"),
            (Refusal::NotSignedIn, "agent_signed_out"),
            (Refusal::ProfileLocked, "agent_signed_out"),
            (Refusal::CatalogUnavailable, "agent_service_not_ready"),
            (Refusal::Unknown, "agent_service_failed"),
        ] {
            assert_eq!(selection_refusal(&CommandFailure::from(refusal)), expected);
        }
    }

    #[test]
    fn a_service_start_or_lost_bridge_is_not_reported_as_sign_out() {
        for (reason, expected) in [
            ("agent_service_unavailable", "agent_service_busy"),
            ("person_bridge_closed", "agent_service_failed"),
            ("person_reply_timeout", "agent_service_failed"),
            ("person_not_signed_in", "agent_signed_out"),
            ("person_session_retired", "agent_signed_out"),
        ] {
            let error = ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                .with_reason(reason);
            assert_eq!(person_refusal(&error), expected, "{reason}");
        }
    }

    #[test]
    fn an_admin_exchange_that_ran_out_of_time_is_busy_and_can_be_asked_again() {
        let io = |kind: std::io::ErrorKind| {
            ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                .with_reason("admin_catalog")
                .caused_by(
                    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                        .with_reason("admin_read")
                        .caused_by(std::io::Error::from(kind)),
                )
        };
        for kind in [
            std::io::ErrorKind::TimedOut,
            std::io::ErrorKind::ConnectionReset,
            std::io::ErrorKind::ConnectionAborted,
        ] {
            assert_eq!(admin_refusal(&io(kind)), "agent_service_busy", "{kind:?}");
        }
        let queued = ApplicationError::new(ErrorCode::TimedOut, Operation::Cli)
            .with_reason("admin_queue_elapsed");
        assert_eq!(admin_refusal(&queued), "agent_service_busy");
        assert_eq!(
            admin_refusal(&io(std::io::ErrorKind::ConnectionRefused)),
            "agent_service_failed"
        );
        let parse = ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
            .with_reason("admin_document_parse");
        assert_eq!(admin_refusal(&parse), "agent_service_failed");
    }
}
