//! Bounded public phase evidence; final maintenance stdout remains unchanged.
use serde::Serialize;
use std::{io::Write, time::Instant};

#[derive(Clone, Copy, Serialize)]
#[serde(rename_all = "snake_case")]
pub(super) enum Phase {
    VersionInstall,
    CandidateVerification,
    RegistrationInstall,
    Commit,
    PublicationAdmission,
    ProductVerification,
    RegistrationVerification,
    PublicationHash,
}

#[derive(Serialize)]
#[serde(rename_all = "snake_case")]
enum Transition {
    Enter,
    Completed,
    Failed,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct Fact {
    schema: u32,
    event: &'static str,
    phase: Phase,
    transition: Transition,
    elapsed_ms: u64,
}

pub(super) fn run<T, E>(
    phase: Phase,
    started: Instant,
    action: impl FnOnce() -> Result<T, E>,
) -> Result<T, E> {
    recorded(phase, started, &mut std::io::stderr().lock(), action)
}

fn recorded<T, E>(
    phase: Phase,
    started: Instant,
    output: &mut impl Write,
    action: impl FnOnce() -> Result<T, E>,
) -> Result<T, E> {
    let mut emit = |transition| {
        let fact = Fact {
            schema: 1,
            event: "native_maintenance_phase",
            phase,
            transition,
            elapsed_ms: u64::try_from(started.elapsed().as_millis()).unwrap_or(u64::MAX),
        };
        // Diagnostics never replace the actual native transaction result.
        if serde_json::to_writer(&mut *output, &fact).is_ok() {
            let _ = output.write_all(b"\n");
            let _ = output.flush();
        }
    };
    emit(Transition::Enter);
    let result = action();
    emit(if result.is_ok() {
        Transition::Completed
    } else {
        Transition::Failed
    });
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bookends_preserve_results_without_private_errors() {
        let mut output = Vec::new();
        let started = Instant::now();
        assert_eq!(
            recorded(Phase::Commit, started, &mut output, || Ok::<_, &str>(7)),
            Ok(7)
        );
        assert_eq!(
            recorded(Phase::PublicationAdmission, started, &mut output, || Err::<
                (),
                _,
            >(
                "private-path"
            )),
            Err("private-path")
        );
        let text = String::from_utf8(output).unwrap();
        assert!(!text.contains("private-path"));
        let facts: Vec<serde_json::Value> = text
            .lines()
            .map(|line| serde_json::from_str(line).unwrap())
            .collect();
        let stages: Vec<_> = facts
            .iter()
            .map(|fact| {
                (
                    fact["phase"].as_str().unwrap(),
                    fact["transition"].as_str().unwrap(),
                )
            })
            .collect();
        assert_eq!(
            stages,
            [
                ("commit", "enter"),
                ("commit", "completed"),
                ("publication_admission", "enter"),
                ("publication_admission", "failed")
            ]
        );
        assert!(
            facts
                .windows(2)
                .all(|pair| pair[0]["elapsedMs"].as_u64() <= pair[1]["elapsedMs"].as_u64())
        );
        assert!(
            facts
                .iter()
                .all(|fact| fact.as_object().unwrap().len() == 5)
        );
        let mut empty = [0_u8; 0];
        assert_eq!(
            recorded(
                Phase::Commit,
                started,
                &mut std::io::Cursor::new(empty.as_mut_slice()),
                || Ok::<_, ()>(9)
            ),
            Ok(9)
        );
    }
}
