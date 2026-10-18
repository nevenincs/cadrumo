//! The desktop's verified agent service host.
//!
//! It runs the dedicated installed service image while the
//! person's sign-in allows it, supervised in a kill-on-close job, and serves
//! the agent column a closed list of token-checked commands over the
//! launcher's loopback gateway, with each run's stream on a Tauri channel.
//! The launcher admits the agent bundled by CMake or returns a typed refusal.

mod admin;
mod gateway;
mod launcher;
pub(crate) mod person;
mod runner;
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
            attendance: std::sync::Mutex::new(None),
        }
    }

    /// Stops the launcher and everything it started, for good.
    pub async fn close(&self) -> Result<()> {
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

    /// The column receives only `code`; the failure behind it is recorded with
    /// its reason and cause chain.
    fn refuse(
        &self,
        code: &str,
        error: cadrumo_application::error::application::ApplicationError,
    ) -> Refused {
        self.diagnostics
            .host_failure(cadrumo_application::diagnostics::HostStage::Agent, error);
        Refused::new(code.to_owned())
    }
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
        agent_skills,
        agent_skill,
        agent_skill_verify,
        agent_conversation_start,
        agent_conversation_rename,
        agent_send,
        agent_cancel,
        agent_pending,
        agent_questions_answer,
        agent_approval_decide,
        agent_observe,
        agent_unobserve,
        agent_conversations,
        agent_history,
        agent_documents,
        agent_attach,
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
                Ok(PersonEvent::LanguageChanged | PersonEvent::Retired) => false,
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
            .map_err(|error| host.refuse("agent_signed_out", error))?;
        work(&host)
    })
    .await
    .map_err(|_| Refused::new("agent_host_failed".to_owned()))?
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
        host.administer(serde_json::json!({"action":"catalog"}), None)
            .map_err(|error| host.refuse("agent_service_failed", error))
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

#[tauri::command]
async fn agent_send(
    host: State<'_, Arc<AgentHost>>,
    request: SendRequest,
) -> std::result::Result<Value, Refused> {
    blocking(&host, move |host| {
        host.session.send(&host.supervisor, &request)
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
        let paths: Vec<std::path::PathBuf> = match upload::lane_picks(upload::lane_directory()) {
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
