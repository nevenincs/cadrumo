//! Fixed-width Darwin libproc records, decoded without alignment assumptions.

use std::io;

pub const BSD_INFO_BYTES: usize = 136;
pub const UNIQUE_INFO_BYTES: usize = 56;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Incarnation {
    pub pid: u32,
    pub version: u32,
    pub unique_id: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Observation {
    pub pid: u32,
    pub parent_pid: u32,
    pub uid: u32,
    pub gid: u32,
    pub process_group: u32,
    pub started_seconds: u64,
    pub started_microseconds: u64,
}

fn word(bytes: &[u8], offset: usize) -> io::Result<u32> {
    let value = bytes
        .get(offset..offset + 4)
        .ok_or(io::ErrorKind::InvalidData)?;
    Ok(u32::from_ne_bytes(
        value.try_into().map_err(|_| io::ErrorKind::InvalidData)?,
    ))
}

fn wide(bytes: &[u8], offset: usize) -> io::Result<u64> {
    let value = bytes
        .get(offset..offset + 8)
        .ok_or(io::ErrorKind::InvalidData)?;
    Ok(u64::from_ne_bytes(
        value.try_into().map_err(|_| io::ErrorKind::InvalidData)?,
    ))
}

fn pid_valid(pid: u32) -> bool {
    pid > 0 && pid <= i32::MAX as u32
}

pub fn incarnation(bytes: &[u8], pid: u32) -> io::Result<Incarnation> {
    if bytes.len() != UNIQUE_INFO_BYTES || !pid_valid(pid) {
        return Err(io::ErrorKind::InvalidData.into());
    }
    let version = word(bytes, 32)?;
    let unique_id = wide(bytes, 16)?;
    if !pid_valid(version) || unique_id == 0 {
        return Err(io::ErrorKind::InvalidData.into());
    }
    Ok(Incarnation {
        pid,
        version,
        unique_id,
    })
}

pub fn observation(bytes: &[u8], pid: u32, owner: u32) -> io::Result<Observation> {
    if bytes.len() != BSD_INFO_BYTES || !pid_valid(pid) {
        return Err(io::ErrorKind::InvalidData.into());
    }
    let value = Observation {
        pid: word(bytes, 12)?,
        parent_pid: word(bytes, 16)?,
        uid: word(bytes, 20)?,
        gid: word(bytes, 24)?,
        process_group: word(bytes, 100)?,
        started_seconds: wide(bytes, 120)?,
        started_microseconds: wide(bytes, 128)?,
    };
    if value.pid != pid
        || value.uid != owner
        || word(bytes, 28)? != owner
        || word(bytes, 36)? != owner
        || word(bytes, 4)? == 5
        || word(bytes, 0)? & 4 != 0
        || value.process_group == 0
        || value.started_seconds == 0
        || value.started_microseconds >= 1_000_000
    {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(value)
}

impl Observation {
    pub fn created_microseconds(self) -> io::Result<u64> {
        self.started_seconds
            .checked_mul(1_000_000)
            .and_then(|seconds| seconds.checked_add(self.started_microseconds))
            .ok_or_else(|| io::ErrorKind::InvalidData.into())
    }
}

/// This token is only for exact-incarnation signalling/image lookup, never login evidence.
pub fn signal_token(incarnation: Incarnation, uid: u32, gid: u32) -> io::Result<[u32; 8]> {
    if !pid_valid(incarnation.pid) || !pid_valid(incarnation.version) || incarnation.unique_id == 0
    {
        return Err(io::ErrorKind::InvalidData.into());
    }
    Ok([
        uid,
        uid,
        gid,
        uid,
        gid,
        incarnation.pid,
        0,
        incarnation.version,
    ])
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SignalDelivery {
    Delivered,
    Gone,
}

/// Darwin libproc returns an errno directly; only ESRCH proves absence.
pub fn signal_delivery(result: i32) -> io::Result<SignalDelivery> {
    match result {
        0 => Ok(SignalDelivery::Delivered),
        3 => Ok(SignalDelivery::Gone),
        error if error > 0 => Err(io::Error::from_raw_os_error(error)),
        _ => Err(io::ErrorKind::InvalidData.into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unique(version: u32, identity: u64) -> [u8; UNIQUE_INFO_BYTES] {
        let mut bytes = [0; UNIQUE_INFO_BYTES];
        bytes[16..24].copy_from_slice(&identity.to_ne_bytes());
        bytes[32..36].copy_from_slice(&version.to_ne_bytes());
        bytes
    }

    fn bsd() -> [u8; BSD_INFO_BYTES] {
        let mut bytes = [0; BSD_INFO_BYTES];
        for (offset, value) in [
            (4, 2u32),
            (12, 123),
            (16, 1),
            (20, 501),
            (24, 20),
            (28, 501),
            (36, 501),
            (100, 123),
        ] {
            bytes[offset..offset + 4].copy_from_slice(&value.to_ne_bytes());
        }
        bytes[120..128].copy_from_slice(&1234u64.to_ne_bytes());
        bytes[128..136].copy_from_slice(&567u64.to_ne_bytes());
        bytes
    }

    #[test]
    fn exec_or_pid_reuse_changes_incarnation_and_token_targets_exact_version() {
        let first = incarnation(&unique(41, 9_000_001), 123).unwrap();
        assert_ne!(first, incarnation(&unique(42, 9_000_001), 123).unwrap());
        assert_ne!(first, incarnation(&unique(41, 9_000_002), 123).unwrap());
        assert_eq!(
            signal_token(first, 501, 20).unwrap(),
            [501, 501, 20, 501, 20, 123, 0, 41]
        );
        for bytes in [unique(0, 1), unique(u32::MAX, 1), unique(1, 0)] {
            assert!(incarnation(&bytes, 123).is_err());
        }
        assert!(incarnation(&unique(1, 1)[..55], 123).is_err());
        assert!(incarnation(&unique(1, 1), 0).is_err());
    }

    #[test]
    fn bsd_record_refuses_changed_owner_zombie_exit_and_invalid_clock() {
        let bytes = bsd();
        let value = observation(&bytes, 123, 501).unwrap();
        assert_eq!(value.created_microseconds().unwrap(), 1_234_000_567);
        for (offset, changed) in [(20, 0u32), (28, 0), (36, 0), (4, 5), (0, 4), (100, 0)] {
            let mut altered = bytes;
            altered[offset..offset + 4].copy_from_slice(&changed.to_ne_bytes());
            assert!(observation(&altered, 123, 501).is_err());
        }
        assert!(observation(&bytes[..135], 123, 501).is_err());
        let mut altered = bytes;
        altered[128..136].copy_from_slice(&1_000_000u64.to_ne_bytes());
        assert!(observation(&altered, 123, 501).is_err());
        assert!(
            Observation {
                started_seconds: u64::MAX,
                ..value
            }
            .created_microseconds()
            .is_err()
        );
    }

    #[test]
    fn signal_refusal_is_never_reported_as_success_or_process_exit() {
        assert_eq!(signal_delivery(0).unwrap(), SignalDelivery::Delivered);
        assert_eq!(signal_delivery(3).unwrap(), SignalDelivery::Gone);
        for value in [-1, 1, 22] {
            assert!(signal_delivery(value).is_err());
        }
    }
}
