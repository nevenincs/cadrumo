use super::{Shared, lock};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Instant;
use tokio::sync::Notify;

pub(super) struct AdmissionWork {
    pub(super) person: super::super::person::HeldPerson,
    pub(super) boot: String,
    pub(super) profile: String,
    pub(super) recipient: String,
    pub(super) service: String,
    pub(super) deadline: Instant,
    pub(super) cancelled: Arc<AtomicBool>,
    pub(super) cancel: Arc<Notify>,
}

/// A failed shared profile read must retire the service it admitted promptly,
/// without waiting for the busy bridge child or another sign-in observation.
pub(super) async fn person_failed(shared: &Shared) -> (u64, ApplicationError) {
    let held = lock(&shared.running).as_ref().and_then(|running| {
        running
            .person_failure
            .clone()
            .map(|failure| (running.generation, failure))
    });
    let Some((generation, mut failure)) = held else {
        return std::future::pending().await;
    };
    loop {
        if let Some(error) = failure.borrow_and_update().clone() {
            return (generation, error);
        }
        if failure.changed().await.is_err() {
            return std::future::pending().await;
        }
    }
}

/// Exchanges one admission request under the held person and its deadline.
pub(super) async fn person_exchange(
    person: super::super::person::HeldPerson,
    request: serde_json::Value,
    deadline: Instant,
) -> Result<serde_json::Value> {
    tauri::async_runtime::spawn_blocking(move || lock(&person).exchange_before(request, deadline))
        .await
        .map_err(|_| ApplicationError::new(ErrorCode::Panic, Operation::Cli))?
}

pub(super) async fn admit_person(work: AdmissionWork) -> Result<()> {
    let AdmissionWork {
        person,
        boot,
        profile,
        recipient,
        service,
        deadline,
        cancelled,
        cancel,
    } = work;
    let held = person.clone();
    let changed = tauri::async_runtime::spawn_blocking(move || {
        let held = lock(&held);
        if held.identity["runtime_boot_id"] != boot || held.identity["profile_id"] != profile {
            return Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                .with_reason("service_ready_identity_mismatch"));
        }
        Ok(held.admission_changed())
    })
    .await
    .map_err(|_| ApplicationError::new(ErrorCode::Panic, Operation::Cli))??;
    if cancelled.load(Ordering::Acquire) {
        return Ok(());
    }
    let base = serde_json::json!({"recipient_connection_id":recipient, "service_id":service});
    let mut request = base.clone();
    request["action"] = serde_json::json!(if changed.is_some() {
        "service_admission_begin"
    } else {
        "service_admission"
    });
    let mut reply = person_exchange(person.clone(), request, deadline).await?;
    if reply["kind"] == "service_connected" {
        return Ok(());
    }
    let Some(changed) = changed else {
        return Err(ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
            .with_reason("service_admission_reply_unexpected"));
    };
    let admission_id = reply["admission_id"].clone();
    loop {
        if Instant::now() >= deadline {
            return Err(ApplicationError::new(ErrorCode::TimedOut, Operation::Cli)
                .with_reason("agent_timeout"));
        }
        let notified = changed.notified();
        tokio::pin!(notified);
        notified.as_mut().enable();
        let mut request = base.clone();
        request["action"] = serde_json::json!(if cancelled.load(Ordering::Acquire) {
            "service_admission_cancel"
        } else {
            "service_admission_status"
        });
        request["admission_id"] = admission_id.clone();
        reply = person_exchange(person.clone(), request, deadline).await?;
        if reply["kind"] == "service_connected" || reply["cancelled"] == true {
            return Ok(());
        }
        tokio::select! {
            () = &mut notified => {},
            () = cancel.notified() => {},
            () = tokio::time::sleep_until(deadline.into()) => {
                return Err(ApplicationError::new(ErrorCode::TimedOut, Operation::Cli).with_reason("agent_timeout"));
            }
        }
    }
}
