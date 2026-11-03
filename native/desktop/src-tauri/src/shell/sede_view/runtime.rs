use super::super::relay::{self, Relayed, Result, lock};
use super::super::user_profile::ProfileHost;
use super::lane::Lane;
use super::protocol::{Condition, Finish, Outcome, Publication, Size};
use crate::agent::person::HeldPerson;
use cadrumo_application::provisioning::items::ItemId;
use cadrumo_application::runtime_client::refusal::Refusal;
use cadrumo_application::view_stream::lane::ViewLane;
use serde::Deserialize;
use serde_json::{Value, json};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

pub(super) const DEFINITION: &str = "live.sede.view";

/// The schema a refused operation's recorded detail is read under.
pub(super) const ERROR_DETAIL_SCHEMA: &str = "operation.error_detail";

/// How long the runtime may take to answer one request to attach.
pub(super) const ATTACH_EXCHANGE: Duration = Duration::from_secs(5);

/// How long a new view connection may take to open.
pub(super) const CONNECT: Duration = Duration::from_secs(5);

/// How long between looks at a closing view's operation.
pub(super) const SETTLE_POLL: Duration = Duration::from_millis(500);

/// The view's result: how it ended and what it did with the session. The
/// operation's journal holds no more than this.
#[derive(Deserialize)]
pub(super) struct Report {
    pub(super) end: Finish,
    pub(super) publication: Option<Publication>,
}

/// What the host needs of the runtime for one submitted view.
pub(super) trait ViewRuntime: Send + Sync {
    /// A connection bound to the running view, or why none is yet.
    fn attach(&self, operation: &str) -> std::result::Result<Arc<dyn Lane>, Refusal>;
    /// Whether the operation still runs; `None` when that cannot be told.
    fn running(&self, operation: &str) -> Option<bool>;
    /// Asks the runtime to cancel the operation, which ends the view without
    /// publishing. Best effort: a lost session cancels it on its own.
    fn cancel(&self, operation: &str);
    /// Follows the operation to its terminal receipt and says what it reported;
    /// `None` when that could not be observed in time.
    fn settled(&self, operation: &str) -> Option<Outcome>;
    /// Whether the session that submitted the view is still held.
    fn held(&self) -> bool;
    /// The component a refused operation's recorded verdict says must be set
    /// up first; `None` when it names none or its detail cannot be read.
    fn needs(&self, operation: &str) -> Option<ItemId>;
}

/// The setup item a stopped operation's recorded refusal stands for.
pub(super) fn needed_component(document: &Value) -> Option<ItemId> {
    if document["result_schema"]["schema_id"] != ERROR_DETAIL_SCHEMA {
        return None;
    }
    super::super::setup::wire::refused_item(&document["projection"])
}

/// The runtime as the window's own person session reaches it.
pub(super) struct PersonRuntime {
    pub(super) person: HeldPerson,
    pub(super) sign_in: Arc<super::super::sign_in::SignIn>,
    pub(super) subject: String,
}

impl PersonRuntime {
    pub(super) fn relayed<'a>(&'a self, operation: &str) -> Relayed<'a> {
        Relayed {
            person: &self.person,
            operation: operation.to_owned(),
            definition: DEFINITION,
            subject: self.subject.clone(),
        }
    }
}

impl ViewRuntime for PersonRuntime {
    fn attach(&self, operation: &str) -> std::result::Result<Arc<dyn Lane>, Refusal> {
        let grant = lock(&self.person).view_attach(operation, Instant::now() + ATTACH_EXCHANGE)?;
        let (endpoint, cohort) = self.sign_in.runtime_target()?;
        let lane = ViewLane::open(&endpoint, &cohort, grant, Instant::now() + CONNECT)?;
        Ok(Arc::new(lane))
    }

    fn running(&self, operation: &str) -> Option<bool> {
        match tauri::async_runtime::block_on(relay::observe(&self.relayed(operation))) {
            Ok(projection) => Some(projection["lifecycle"] != "terminal"),
            // The runtime no longer knows the operation, so nothing of it runs.
            Err(gone) if gone.code == "not_admitted" => Some(false),
            Err(_) => None,
        }
    }

    fn cancel(&self, operation: &str) {
        let relayed = self.relayed(operation);
        tauri::async_runtime::block_on(async {
            let Ok(projection) = relay::observe(&relayed).await else {
                return;
            };
            if projection["lifecycle"] == "terminal" {
                return;
            }
            let _ = relay::call(
                &self.person,
                json!({"action":"operation_cancel", "operation_id":operation,
                    "expected_revision":projection["revision"]}),
            )
            .await;
        });
    }

    fn settled(&self, operation: &str) -> Option<Outcome> {
        let relayed = self.relayed(operation);
        let deadline = Instant::now() + relay::SETTLE_LIMIT;
        loop {
            let projection = tauri::async_runtime::block_on(relay::observe(&relayed)).ok()?;
            if projection["lifecycle"] == "terminal" {
                let condition: Condition =
                    serde_json::from_value(projection["terminal_condition"].clone()).ok()?;
                if condition != Condition::Succeeded {
                    return Some(Outcome {
                        condition,
                        end: None,
                        publication: None,
                    });
                }
                let document = tauri::async_runtime::block_on(relay::result(&relayed)).ok()?;
                let report: Report = serde_json::from_value(document["projection"].clone()).ok()?;
                return Some(Outcome {
                    condition,
                    end: Some(report.end),
                    publication: report.publication,
                });
            }
            if Instant::now() >= deadline {
                return None;
            }
            thread::sleep(SETTLE_POLL);
        }
    }

    fn needs(&self, operation: &str) -> Option<ItemId> {
        let document =
            tauri::async_runtime::block_on(relay::result(&self.relayed(operation))).ok()?;
        needed_component(&document)
    }

    fn held(&self) -> bool {
        match self.person.try_lock() {
            Ok(mut person) => person.is_open(),
            Err(std::sync::TryLockError::Poisoned(poisoned)) => poisoned.into_inner().is_open(),
            // An exchange is in flight, so the session is in use.
            Err(std::sync::TryLockError::WouldBlock) => true,
        }
    }
}

/// A view the host submitted: its operation and the runtime that runs it.
pub(super) struct Started {
    pub(super) operation: String,
    pub(super) runtime: Arc<dyn ViewRuntime>,
}

/// The view's registered request: the profile and the panel's starting size.
/// The start page is the backend's own; the window never names one.
pub(super) fn request(profile_id: &str, size: &Size) -> Value {
    json!({"profile_id":profile_id, "css_width":size.css_width,
        "css_height":size.css_height, "scale":size.scale})
}

/// Submits the Sede view for the window's signed-in profile.
pub(super) async fn start(profile: &ProfileHost, size: &Size) -> Result<Started> {
    let _serial = profile.serial().await;
    let person = profile.person(None).await?;
    let profile_id = relay::profile_of(&person).await?;
    let subject = relay::subject(&profile_id);
    // A lost answer may still have started a view, so the submission counts as a mutation.
    let operation = relay::submit(
        &person,
        DEFINITION,
        &subject,
        request(&profile_id, size),
        true,
    )
    .await?;
    Ok(Started {
        operation,
        runtime: Arc::new(PersonRuntime {
            person,
            sign_in: profile.sign_in().clone(),
            subject,
        }),
    })
}
