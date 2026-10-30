//! The local model the desktop hands its component engine for one download.
//!
//! General setup admits the local AI as its program alone; a model is pulled only when
//! the person downloads it from a local lane's model list. That list is the models
//! cadrumo-agent's catalogue recommends for the lane and the models the person added to it
//! by name. Both facts are the agent service's: a lane's kind comes from the provider
//! status, its recommended models and a model's size from cadrumo-agent's catalogue, and
//! the added models from the service's `local_models` record. This module reads them over
//! the service's administration channel at the moment a download starts and invents
//! nothing:
//!
//! - a lane that takes a key or a sign-in reads off this computer, a keyless lane the
//!   person turned off is not to be used, and a lane the status does not list is unknown;
//!   none of them admits a download;
//! - a model on neither of the lane's lists is not one the person can download, and an
//!   unreadable record of added models admits no added model;
//! - the size is the one the catalogue states for the model, and unknown when it states
//!   none or a zero one, as for a model the person named;
//! - a service that does not answer or refuses refuses the download as unavailable, with
//!   what it answered kept for diagnostics;
//! - a list reply outside the service's contract is a host failure, not a service that is
//!   not answering.
//!
//! A keyless lane is a lane on this computer: the service's catalogue admits a keyless
//! lane only with a loopback address. The catalogue's `reads_off_host` flag is not part
//! of the provider status, the one record that names a lane's kind whether or not an
//! agent is ready, so this module does not read it.
use super::wire::{ModelDownload, Refusal, Stop};
use crate::{
    agent::{AgentHost, local_models},
    shell::provider_settings::{
        outcome, read_status,
        wire::{
            self, AuthKind, CommandFailure, Entry, Mode, Refusal as ProviderRefusal, Transport,
        },
    },
};
use cadrumo_application::{
    component::Cancellation,
    error::application::{ApplicationError, ChildRefusal, ErrorCode, Operation},
    provisioning::local_ai::models::{LocalModels, SelectedModel},
};
use serde_json::{Value, json};
use std::{
    sync::Arc,
    time::{Duration, Instant},
};

/// How long a read that the service answered with `busy` waits before it asks again.
const READ_PAUSE: Duration = Duration::from_millis(250);
const READ_ATTEMPTS: usize = 4;

/// Only a definite busy answer is safe to collect again. An exchange error or another
/// refusal is returned unchanged, and the last busy answer remains diagnostic evidence.
fn read_busy(
    mut request: impl FnMut() -> Result<Value, ApplicationError>,
    pause: Duration,
) -> Result<Value, ApplicationError> {
    for attempt in 0..READ_ATTEMPTS {
        let answer = request()?;
        if answer["kind"] != "refused" || answer["code"] != "busy" || attempt + 1 == READ_ATTEMPTS {
            return Ok(answer);
        }
        std::thread::sleep(pause);
    }
    unreachable!("the last attempt returns its answer")
}

/// The agent service as admission reads it: one administration exchange per read.
pub trait Agent: Send + Sync {
    fn exchange(&self, request: Value) -> Result<Value, ApplicationError>;
    fn generation(&self) -> Result<u64, ApplicationError>;
    fn exchange_generation(
        &self,
        request: Value,
        generation: u64,
    ) -> Result<Value, ApplicationError> {
        if self.generation()? != generation {
            return Err(generation_changed());
        }
        let answer = self.exchange(request)?;
        if self.generation()? != generation {
            return Err(generation_changed());
        }
        Ok(answer)
    }
}

impl Agent for AgentHost {
    fn exchange(&self, request: Value) -> Result<Value, ApplicationError> {
        self.administer(request, None)
    }
    fn generation(&self) -> Result<u64, ApplicationError> {
        self.admin_generation()
    }
    fn exchange_generation(
        &self,
        request: Value,
        generation: u64,
    ) -> Result<Value, ApplicationError> {
        self.administer_generation(request, generation)
    }
}

fn generation_changed() -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
        .with_reason("agent_admin_generation_changed")
}

struct Pending<'a> {
    cancellation: &'a Cancellation,
    // Stops issuing reads at the owner budget. An already admitted exchange may
    // finish within its existing queue and transport bounds; a late success is refused.
    deadline: Instant,
    generation: u64,
}

impl Pending<'_> {
    fn check(&self, agent: &dyn Agent) -> Result<(), ApplicationError> {
        if self.cancellation.is_cancelled() {
            return Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                .with_reason("setup_admission_cancelled"));
        }
        if agent.generation()? != self.generation {
            return Err(generation_changed());
        }
        Ok(())
    }

    fn read(&self, agent: &dyn Agent, action: &str) -> Result<Value, ApplicationError> {
        let mut busy = None;
        loop {
            self.check(agent)?;
            if Instant::now() >= self.deadline {
                return busy.ok_or_else(|| {
                    ApplicationError::new(ErrorCode::TimedOut, Operation::Cli)
                        .with_reason("setup_admission_expired")
                });
            }
            let answer = agent.exchange_generation(json!({"action": action}), self.generation)?;
            self.check(agent)?;
            if answer["kind"] != "refused" || answer["code"] != "busy" {
                if Instant::now() >= self.deadline {
                    return Err(ApplicationError::new(ErrorCode::TimedOut, Operation::Cli)
                        .with_reason("setup_admission_expired"));
                }
                return Ok(answer);
            }
            busy = Some(answer);
            std::thread::sleep(
                READ_PAUSE.min(self.deadline.saturating_duration_since(Instant::now())),
            );
        }
    }
}

/// Reads what a download is admitted with.
pub struct Admission {
    agent: Arc<dyn Agent>,
}

impl Admission {
    pub fn new(agent: Arc<dyn Agent>) -> Self {
        Self { agent }
    }

    /// Admits the requested model alone, if it is on the requested local lane's list.
    pub fn download(&self, request: &ModelDownload) -> Result<LocalModels, Stop> {
        self.download_with(request, None)
    }

    pub fn download_cancellable(
        &self,
        request: &ModelDownload,
        cancellation: &Cancellation,
    ) -> Result<LocalModels, Stop> {
        self.download_with_budget(
            request,
            cancellation,
            Duration::from_secs(cadrumo_platform::DEFAULT_ORCHESTRATION_TIMEOUT_SECONDS),
        )
    }

    fn download_with_budget(
        &self,
        request: &ModelDownload,
        cancellation: &Cancellation,
        budget: Duration,
    ) -> Result<LocalModels, Stop> {
        if cancellation.is_cancelled() {
            return Err(unanswered(
                ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                    .with_reason("setup_admission_cancelled"),
                "setup_admission_unanswered",
            ));
        }
        let generation = self
            .agent
            .generation()
            .map_err(|error| unanswered(error, "setup_provider_status_unanswered"))?;
        let pending = Pending {
            cancellation,
            deadline: Instant::now() + budget,
            generation,
        };
        self.download_with(request, Some(&pending))
    }

    fn download_with(
        &self,
        request: &ModelDownload,
        pending: Option<&Pending<'_>>,
    ) -> Result<LocalModels, Stop> {
        let unusable = || Stop::Refused(Refusal::ModelSelectionUnusable);
        let lanes = self.lanes(pending)?;
        let lane = lanes
            .iter()
            .find(|lane| {
                lane.id == request.lane
                    && lane.auth_kind == AuthKind::Keyless
                    && lane.mode != Mode::Disabled
            })
            .ok_or_else(unusable)?;
        let catalogue = self.catalogue(pending)?;
        let record = lane_record(&catalogue, lane);
        let recommended = record.is_some_and(|record| record.recommends(&request.model));
        if !recommended && !self.added(&lane.id, &request.model, pending)? {
            return Err(unusable());
        }
        let size = record
            .and_then(|record| record.stated_size(&request.model))
            .filter(|size| *size > 0);
        // This part identifies the transfer in the engine plan, never a stored task.
        let model = SelectedModel::new("download", &request.model, size).map_err(|_| unusable())?;
        if let Some(pending) = pending {
            pending
                .check(&*self.agent)
                .map_err(|error| unanswered(error, "setup_admission_unanswered"))?;
        }
        LocalModels::new(vec![model]).map_err(|_| unusable())
    }

    /// Every model on the list of a local lane that is turned on, recommended or added:
    /// the models the person manages here and a removal of the local AI takes with it. A
    /// model the person keeps off those lists is not among them.
    pub fn listed(&self) -> Result<LocalModels, Stop> {
        let lanes = self.lanes(None)?;
        let catalogue = self.catalogue(None)?;
        let added = self.added_models(None)?;
        let mut names: Vec<String> = Vec::new();
        for lane in lanes
            .iter()
            .filter(|lane| lane.auth_kind == AuthKind::Keyless && lane.mode != Mode::Disabled)
        {
            let recommended = lane_record(&catalogue, lane)
                .map(LaneRecord::recommended_models)
                .unwrap_or_default();
            let listed = recommended
                .into_iter()
                .chain(added.added_to(&lane.id).map(str::to_owned));
            for name in listed {
                if !names.contains(&name) {
                    names.push(name);
                }
            }
        }
        // A name the engine cannot pull is on no list the engine could have filled.
        let selected = names
            .iter()
            .enumerate()
            .map(|(index, name)| SelectedModel::new(&format!("listed{index}"), name, None))
            .collect::<Result<Vec<_>, _>>()
            .map_err(|_| Stop::Refused(Refusal::ModelSelectionUnusable))?;
        LocalModels::new(selected).map_err(|_| Stop::Refused(Refusal::ModelSelectionUnusable))
    }

    /// Whether the person added `model` to `lane`'s list.
    fn added(&self, lane: &str, model: &str, pending: Option<&Pending<'_>>) -> Result<bool, Stop> {
        Ok(self
            .added_models(pending)?
            .added_to(lane)
            .any(|added| added == model))
    }

    /// The models the person added to their lanes' lists. A record nobody can read lists
    /// no model.
    fn added_models(
        &self,
        pending: Option<&Pending<'_>>,
    ) -> Result<local_models::LocalModels, Stop> {
        let answer = self
            .read("local_models", pending)
            .map_err(|error| unanswered(error, "setup_local_models_unanswered"))?;
        if let Some(code) = local_models::refusal(&answer) {
            return Err(refused_by(
                code == "agent_signed_out",
                "setup_local_models_refused",
                &answer,
            ));
        }
        // The service answered, so "not answering" would misname a reply outside its contract.
        local_models::parse(&answer).ok_or_else(|| {
            Stop::Host(
                ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                    .with_reason("setup_local_models_contract"),
            )
        })
    }

    /// Every lane the profile lists, with the kind of access it takes.
    fn lanes(&self, pending: Option<&Pending<'_>>) -> Result<Vec<Entry>, Stop> {
        let status = if let Some(pending) = pending {
            self.read("status", Some(pending))
                .map_err(CommandFailure::Host)
                .and_then(|answer| wire::status(outcome(answer)))
        } else {
            read_status(
                || self.agent.exchange(json!({"action": "status"})),
                READ_PAUSE,
            )
        };
        status
            .map(|status| status.providers)
            .map_err(|failure| match failure {
                CommandFailure::Host(error) => {
                    unanswered(error, "setup_provider_status_unanswered")
                }
                CommandFailure::Refused(refused) => refused_by(
                    matches!(
                        refused.code,
                        ProviderRefusal::NotSignedIn | ProviderRefusal::ProfileLocked
                    ),
                    "setup_provider_status_refused",
                    &json!({"code": refused.code}),
                ),
            })
    }

    /// cadrumo-agent's catalogue, as the service relays it.
    fn catalogue(&self, pending: Option<&Pending<'_>>) -> Result<Value, Stop> {
        let answer = self
            .read("catalog", pending)
            .map_err(|error| unanswered(error, "setup_catalogue_unanswered"))?;
        if answer["kind"] == "refused" {
            return Err(refused_by(
                answer["code"] == "signed_out",
                "setup_catalogue_refused",
                &answer,
            ));
        }
        Ok(answer)
    }

    fn read(&self, action: &str, pending: Option<&Pending<'_>>) -> Result<Value, ApplicationError> {
        if let Some(pending) = pending {
            pending.read(&*self.agent, action)
        } else {
            read_busy(
                || self.agent.exchange(json!({"action": action})),
                READ_PAUSE,
            )
        }
    }
}

/// What a service that did not answer is to the window, and to diagnostics: nobody is
/// signed in, or the failure of the exchange named `reason`.
fn unanswered(error: ApplicationError, reason: &'static str) -> Stop {
    if error.reason.as_deref() == Some("person_not_signed_in") {
        return Refusal::NotSignedIn.into();
    }
    Stop::unavailable(reason).because(error)
}

/// What a service that refused with `answer` is to the window: nobody is signed in, or it
/// is not ready for the reason named. The refusal code the service gave is kept.
fn refused_by(signed_out: bool, reason: &'static str, answer: &Value) -> Stop {
    if signed_out {
        Refusal::NotSignedIn.into()
    } else {
        Stop::unavailable(reason).because(ChildRefusal::answered(answer))
    }
}

/// A lane's record in the catalogue: its recommended models and its model entries, each
/// entry named under the key the catalogue's shape uses.
#[derive(Clone, Copy)]
struct LaneRecord<'a> {
    recommended: &'a Value,
    models: &'a Value,
    key: &'static str,
}

impl LaneRecord<'_> {
    /// Whether the catalogue recommends `model` for any capability of the lane.
    fn recommends(self, model: &str) -> bool {
        self.recommended
            .as_object()
            .is_some_and(|recommended| recommended.values().any(|named| named == model))
    }

    /// The models the catalogue recommends for the lane.
    fn recommended_models(self) -> Vec<String> {
        self.recommended
            .as_object()
            .into_iter()
            .flat_map(|recommended| recommended.values())
            .filter_map(|named| named.as_str().map(str::to_owned))
            .collect()
    }

    /// The download size the catalogue states for `model`; `None` when it lists no such
    /// model or its entry states no size.
    fn stated_size(self, model: &str) -> Option<u64> {
        self.models
            .as_array()?
            .iter()
            .find(|entry| entry[self.key] == model)?["size_bytes"]
            .as_u64()
    }
}

/// `lane`'s record in `catalogue`. A ready agent serves a lane's record by provider and
/// transport, and names a model `model`; while none is ready the declared catalogue
/// arrives in an envelope, lists its lanes by id and names a model `id`.
fn lane_record<'a>(catalogue: &'a Value, lane: &Entry) -> Option<LaneRecord<'a>> {
    if catalogue["kind"] == "declared" {
        let record = catalogue["catalog"]["providers"]
            .as_array()?
            .iter()
            .find(|record| record["id"] == lane.id)?;
        return Some(LaneRecord {
            recommended: &record["recommended"],
            models: &record["models"],
            key: "id",
        });
    }
    let transport = match lane.transport {
        Transport::Api => "api",
        Transport::Cli => "cli",
    };
    let record = catalogue["providers"].as_array()?.iter().find(|record| {
        record["provider_id"] == lane.provider && record["transport"] == transport
    })?;
    Some(LaneRecord {
        recommended: &record["catalog"]["recommended"],
        models: &record["catalog"]["models"],
        key: "model",
    })
}

#[cfg(test)]
#[path = "admission_tests.rs"]
pub(super) mod tests;
