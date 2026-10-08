//! Owner/session-qualified Unix sockets for the closed manager protocol.
#![allow(unsafe_code)]

mod socket;
use super::{
    login::{Login, Session},
    process::{Identity, Process},
};
use crate::ipc::{
    Request, Response, decode,
    framing::{Frame, encode, write_some},
};
use socket::{Directory, Socket, configure, connect_now};
use std::{
    fs, io,
    os::unix::net::UnixStream,
    path::{Path, PathBuf},
    thread,
    time::{Duration, Instant},
};

const TIMEOUT: Duration = Duration::from_secs(2);
const POLL: Duration = Duration::from_millis(10);

struct Peer {
    process: Process,
    identity: Identity,
    stream: Option<UnixStream>,
}

impl Peer {
    fn inspect(stream: &UnixStream, session: &Session, images: &[PathBuf]) -> io::Result<Self> {
        let (process, observed) = Login::open()?.peer(stream)?;
        let identity = process.identity()?.clone();
        if observed != *session || !images.contains(&identity.image) {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let peer = Self {
            process,
            identity,
            stream: Some(stream.try_clone()?),
        };
        peer.revalidate(session)?;
        Ok(peer)
    }

    fn revalidate(&self, session: &Session) -> io::Result<()> {
        let login = Login::open()?;
        let observed = match &self.stream {
            Some(stream) => login.capture_peer(stream, &self.process)?,
            None => login.current(&self.process)?,
        };
        if observed != *session || self.process.identity()? != &self.identity {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(())
    }
}

enum State {
    Reading {
        stream: UnixStream,
        peer: Peer,
        frame: Frame,
        deadline: Instant,
    },
    Writing {
        stream: UnixStream,
        peer: Peer,
        bytes: Vec<u8>,
        written: usize,
        deadline: Instant,
    },
}

/// One bounded connection at a time; polling never waits for socket I/O.
pub struct Server {
    socket: Socket,
    state: Option<State>,
    session: Session,
    images: Vec<PathBuf>,
    manager: PathBuf,
    owner: Peer,
}

impl Server {
    /// Package admission and the session lock precede this call.
    pub fn bind_installed(
        package: &Path,
        _session_lock: &crate::session::instance::SessionLock,
    ) -> io::Result<Self> {
        let contract: cadrumo_application::installation::DiscoveryContract =
            serde_json::from_str(crate::contract::INSTALLATION_CONTRACT)
                .map_err(io::Error::other)?;
        let manager = fs::canonicalize(
            contract
                .manager_member()
                .map_err(io::Error::other)?
                .under(package),
        )?;
        if manager != fs::canonicalize(std::env::current_exe()?)? {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let mut images = vec![manager.clone()];
        for image in contract
            .layout
            .application_images
            .iter()
            .filter(|image| image.target == "desktop-host-build")
        {
            let leaf = format!("{}{}", image.name, contract.layout.entrypoint_suffix);
            let member = cadrumo_application::value::RelativePath::new(if image.placement == "." {
                leaf
            } else {
                format!("{}/{leaf}", image.placement)
            })
            .map_err(io::Error::other)?;
            let path = member.under(package);
            if path.is_file() {
                images.push(fs::canonicalize(path)?);
            }
        }
        let process = Process::open(std::process::id())?;
        let session = Login::open()?.current(&process)?;
        let owner = Peer {
            identity: process.identity()?.clone(),
            process,
            stream: None,
        };
        owner.revalidate(&session)?;
        let directory = Directory::installed(true)?;
        let name = super::naming::socket_name(
            crate::identity::MANAGER_ID,
            &session.uid().to_string(),
            &session.id().to_string(),
        )?;
        let socket = Socket::bind_in(directory, &name)?;
        Ok(Self {
            socket,
            state: None,
            session,
            images,
            manager,
            owner,
        })
    }

    /// The held peer is exposed to cutover admission; a request PID is never authority.
    pub fn poll(
        &mut self,
        mut handle: impl FnMut(&Process, Request) -> Response,
    ) -> io::Result<()> {
        self.owner.revalidate(&self.session)?;
        self.socket.verify()?;
        for _ in 0..4 {
            if self.state.is_none() {
                let (stream, _) = match self.socket.listener.accept() {
                    Ok(connection) => connection,
                    Err(error)
                        if matches!(
                            error.kind(),
                            io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                        ) =>
                    {
                        break;
                    }
                    Err(error) => return Err(error),
                };
                configure(&stream)?;
                let Ok(peer) = Peer::inspect(&stream, &self.session, &self.images) else {
                    continue;
                };
                self.state = Some(State::Reading {
                    stream,
                    peer,
                    frame: Frame::new(),
                    deadline: Instant::now() + TIMEOUT,
                });
            }
            let state = self.state.take().ok_or(io::ErrorKind::BrokenPipe)?;
            match self.advance(state, &mut handle) {
                Ok((next, progressed)) => {
                    self.state = next;
                    if !progressed {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
        Ok(())
    }

    fn advance(
        &self,
        state: State,
        handle: &mut impl FnMut(&Process, Request) -> Response,
    ) -> io::Result<(Option<State>, bool)> {
        match state {
            State::Reading {
                mut stream,
                peer,
                mut frame,
                deadline,
            } => {
                if Instant::now() >= deadline {
                    return Err(io::ErrorKind::TimedOut.into());
                }
                peer.revalidate(&self.session)?;
                let Some(bytes) = frame.read(&mut stream)? else {
                    return Ok((
                        Some(State::Reading {
                            stream,
                            peer,
                            frame,
                            deadline,
                        }),
                        false,
                    ));
                };
                let request = decode(&bytes)?;
                if matches!(request, Request::SuccessorReady { .. })
                    && peer.identity.image != self.manager
                {
                    return Err(io::ErrorKind::PermissionDenied.into());
                }
                peer.revalidate(&self.session)?;
                let response = handle(&peer.process, request);
                let bytes = encode(&serde_json::to_vec(&response).map_err(io::Error::other)?)?;
                Ok((
                    Some(State::Writing {
                        stream,
                        peer,
                        bytes,
                        written: 0,
                        deadline,
                    }),
                    true,
                ))
            }
            State::Writing {
                mut stream,
                peer,
                bytes,
                mut written,
                deadline,
            } => {
                if Instant::now() >= deadline {
                    return Err(io::ErrorKind::TimedOut.into());
                }
                peer.revalidate(&self.session)?;
                if write_some(&mut stream, &bytes, &mut written)? {
                    Ok((None, true))
                } else {
                    Ok((
                        Some(State::Writing {
                            stream,
                            peer,
                            bytes,
                            written,
                            deadline,
                        }),
                        false,
                    ))
                }
            }
        }
    }
}

/// Bounded client exchange; authenticate the manager before transmitting a request.
pub fn request(manager: &Path, request: &Request) -> io::Result<Response> {
    let owner = Process::open(std::process::id())?;
    let session = Login::open()?.current(&owner)?;
    let directory = Directory::installed(false)?;
    let name = super::naming::socket_name(
        crate::identity::MANAGER_ID,
        &session.uid().to_string(),
        &session.id().to_string(),
    )?;
    let identity = directory.private_socket(&name)?;
    let deadline = Instant::now() + TIMEOUT;
    let mut stream = loop {
        match connect_now(&directory.leaf(&name)) {
            Ok(stream) => break stream,
            Err(error) if error.kind() == io::ErrorKind::WouldBlock => {}
            Err(error) => return Err(error),
        }
        if Instant::now() >= deadline {
            return Err(io::ErrorKind::TimedOut.into());
        }
        thread::sleep(POLL);
    };
    if directory.private_socket(&name)? != identity {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    let peer = Peer::inspect(&stream, &session, &[fs::canonicalize(manager)?])?;
    let bytes = serde_json::to_vec(request).map_err(io::Error::other)?;
    decode(&bytes)?;
    let bytes = encode(&bytes)?;
    let mut written = 0;
    let mut frame = Frame::new();
    loop {
        if Instant::now() >= deadline {
            return Err(io::ErrorKind::TimedOut.into());
        }
        if Login::open()?.current(&owner)? != session {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        if directory.private_socket(&name)? != identity {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        peer.revalidate(&session)?;
        if written != bytes.len() {
            write_some(&mut stream, &bytes, &mut written)?;
        } else if let Some(bytes) = frame.read(&mut stream)? {
            peer.revalidate(&session)?;
            if directory.private_socket(&name)? != identity {
                return Err(io::ErrorKind::PermissionDenied.into());
            }
            let response: Response = serde_json::from_slice(&bytes).map_err(io::Error::other)?;
            if response.schema != 1 {
                return Err(io::ErrorKind::InvalidData.into());
            }
            return Ok(response);
        }
        thread::sleep(POLL);
    }
}
