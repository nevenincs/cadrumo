//! Successor admission and bounded reports on the parent's private cutover pipe.
use super::{InitialPermit, Phase, ReportResult, Reporter};
use crate::{
    cutover::{Designation, Report},
    installation::CurrentInstallation,
    ipc::{self, Outcome, Request},
    supervision::{
        environment::ManagedLocations,
        process::{RuntimeProcess, open_process},
    },
};
use cadrumo_application::{component::Cancellation, installation::DiscoveryContract};
use std::{
    io,
    path::{Path, PathBuf},
    sync::mpsc,
    thread,
    time::Duration,
};

pub struct Admitted {
    pub installation: CurrentInstallation,
    pub permit: InitialPermit,
    pub reporter: Reporter,
}
pub fn admit(designation: Designation) -> io::Result<Admitted> {
    let contract: DiscoveryContract =
        serde_json::from_str(crate::contract::INSTALLATION_CONTRACT).map_err(io::Error::other)?;
    let image = std::env::current_exe()?;
    let prefix = contract
        .local_prefix(&image)
        .ok_or_else(|| io::Error::from(io::ErrorKind::PermissionDenied))?;
    let cancellation = Cancellation::default();
    let selected = contract
        .inspect_version_cancellable(&prefix, crate::identity::VERSION, &cancellation)
        .map_err(io::Error::other)?;
    let previous = parent_manager(
        &contract,
        &prefix,
        &designation.parent_version,
        selected.version,
    )?;
    let parent = open_process(designation.parent_pid)
        .map_err(|_| io::Error::from(io::ErrorKind::PermissionDenied))?;
    ipc::windows::verify_process(designation.parent_pid, &previous)?;
    if !crate::cutover_windows::children(designation.parent_pid)?.contains(&std::process::id()) {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let installation = crate::installation::admit_selection(&image, &selected)?;
    let locations = ManagedLocations::resolve(&selected.manager)?;
    let response = ipc::windows::request_expected(
        &designation.endpoint(),
        &previous,
        Some(designation.parent_pid),
        &Request::SuccessorReady {
            schema: 1,
            runtime_pid: 0,
            report: Some(Report::Claim {
                nonce: designation.nonce.clone(),
            }),
        },
    )?;
    if response.outcome != Outcome::DesignationAccepted {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let permit = InitialPermit {
        root: locations.storage_root().to_path_buf(),
    };
    let (send, notices) = mpsc::sync_channel(2);
    let (report, result) = mpsc::sync_channel(1);
    thread::Builder::new()
        .name("manager-cutover-reports".into())
        .spawn(move || {
            // Holding the native parent handle prevents its PID being reused. Its
            // already-admitted process retains its own package lease. Missing old
            // auxiliary files cannot invalidate this exact live parent identity.
            let mut parent = RuntimeProcess::Adopted(parent);
            loop {
                if matches!(parent.try_exit(), Ok(Some(_))) {
                    let _ = report.send(ReportResult::ParentExited);
                    break;
                }
                let notice = match notices.recv_timeout(Duration::from_millis(100)) {
                    Ok(notice) => notice,
                    Err(mpsc::RecvTimeoutError::Timeout) => continue,
                    Err(mpsc::RecvTimeoutError::Disconnected) => break,
                };
                let (pid, ready) = match notice {
                    (pid, Phase::Launched) => (pid, false),
                    (pid, Phase::Ready) => (pid, true),
                };
                let phase = if ready {
                    Report::Ready {
                        nonce: designation.nonce.clone(),
                    }
                } else {
                    Report::Launched {
                        nonce: designation.nonce.clone(),
                    }
                };
                let response = ipc::windows::request_expected(
                    &designation.endpoint(),
                    &previous,
                    Some(designation.parent_pid),
                    &Request::SuccessorReady {
                        schema: 1,
                        runtime_pid: pid,
                        report: Some(phase),
                    },
                );
                match response {
                    Ok(response)
                        if response.outcome
                            == if ready {
                                Outcome::SuccessorReady
                            } else {
                                Outcome::SuccessorObserved
                            } =>
                    {
                        if ready {
                            // A distinct authenticated request proves that the Ready
                            // response was consumed, even if the parent exits before
                            // replying to this final acknowledgement.
                            let acknowledged = ipc::windows::request_expected(
                                &designation.endpoint(),
                                &previous,
                                Some(designation.parent_pid),
                                &Request::SuccessorReady {
                                    schema: 1,
                                    runtime_pid: pid,
                                    report: Some(Report::Acknowledged {
                                        nonce: designation.nonce.clone(),
                                    }),
                                },
                            );
                            let result = if acknowledged
                                .is_ok_and(|response| response.outcome == Outcome::SuccessorReady)
                            {
                                ReportResult::Committed
                            } else if wait_for_parent_exit(Duration::from_secs(10), || {
                                matches!(parent.try_exit(), Ok(Some(_)))
                            }) {
                                ReportResult::ParentExited
                            } else {
                                ReportResult::Rejected
                            };
                            let _ = report.send(result);
                            break;
                        }
                    }
                    _ => {
                        let result = if matches!(parent.try_exit(), Ok(Some(_))) {
                            ReportResult::ParentExited
                        } else {
                            ReportResult::Rejected
                        };
                        let _ = report.send(result);
                        break;
                    }
                }
            }
        })?;
    Ok(Admitted {
        installation,
        permit,
        reporter: Reporter { send, result },
    })
}

fn wait_for_parent_exit(bound: Duration, mut ended: impl FnMut() -> bool) -> bool {
    let deadline = std::time::Instant::now() + bound;
    loop {
        if ended() {
            return true;
        }
        if std::time::Instant::now() >= deadline {
            return false;
        }
        thread::sleep(Duration::from_millis(25));
    }
}

fn parent_manager(
    contract: &DiscoveryContract,
    prefix: &Path,
    release: &str,
    successor: [u32; 3],
) -> io::Result<PathBuf> {
    if cadrumo_application::installation::version(release).map_err(io::Error::other)? >= successor {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let package = contract
        .layout
        .installation
        .versions
        .under(prefix)
        .join(release);
    let image = contract
        .manager_member()
        .map_err(io::Error::other)?
        .under(&package);
    let canonical = std::fs::canonicalize(&image)?;
    if !ipc::windows::same_image(&canonical, &image) {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(canonical)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn final_ack_pipe_closure_waits_for_held_parent_exit_with_a_bound() {
        let mut observations = 0;
        assert!(wait_for_parent_exit(Duration::from_secs(1), || {
            observations += 1;
            observations == 3
        }));
        assert_eq!(observations, 3);
        assert!(!wait_for_parent_exit(Duration::ZERO, || false));
    }
    #[test]
    fn parent_image_derivation_survives_missing_auxiliary_files_but_refuses_forged_versions() {
        let contract: DiscoveryContract =
            serde_json::from_str(crate::contract::INSTALLATION_CONTRACT).unwrap();
        let root = std::env::temp_dir().join(format!(
            "manager-parent-image-{}-{}",
            std::process::id(),
            crate::cutover_windows::nonce().unwrap()
        ));
        let package = contract
            .layout
            .installation
            .versions
            .under(&root)
            .join("1.0.0");
        std::fs::create_dir_all(&package).unwrap();
        let image = contract.manager_member().unwrap().under(&package);
        std::fs::write(
            &image,
            b"test image path only, native authentication remains separate",
        )
        .unwrap();
        let auxiliary = package.join("auxiliary");
        std::fs::write(&auxiliary, b"old data").unwrap();
        std::fs::remove_file(auxiliary).unwrap();
        assert_eq!(
            parent_manager(&contract, &root, "1.0.0", [2, 0, 0]).unwrap(),
            std::fs::canonicalize(image).unwrap()
        );
        for invalid in ["../1.0.0", "01.0.0", "2.0.0", "0.9.0"] {
            assert!(parent_manager(&contract, &root, invalid, [2, 0, 0]).is_err());
        }
        std::fs::remove_dir_all(root).unwrap();
    }
}
