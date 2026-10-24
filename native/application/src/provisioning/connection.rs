//! How the engine reaches a publisher: name resolution, a TCP connection, the operator's
//! proxy tunnel when one applies, and a verified TLS session.
//!
//! Each stage fails in its own way, and the stage is what tells a person what to do, so a
//! failure keeps it: no resolution or connection means the computer may be offline, a
//! refused tunnel is the network in between, a refused certificate is a secure-connection
//! problem. Trust anchors are the bundled web PKI roots; the system trust store is not
//! consulted.

use super::{http, proxy::ProxySettings, url::HttpsUrl};
use rustls::{ClientConfig, ClientConnection, RootCertStore, StreamOwned, pki_types::ServerName};
use std::{
    io::{self, BufReader, Read, Write},
    net::{SocketAddr, TcpStream, ToSocketAddrs},
    sync::{Arc, mpsc},
    time::{Duration, Instant},
};

/// Resolves a host and port to the addresses a connection may try, in order.
pub type Resolve = dyn Fn(&str, u16) -> io::Result<Vec<SocketAddr>> + Send + Sync;

/// Where a connection attempt stopped.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum Stage {
    /// The name, or the proxy's name, did not resolve.
    Resolve,
    /// No TCP connection was made.
    Connect,
    /// The proxy answered `CONNECT` with this status, or with no readable answer.
    Tunnel(Option<u16>),
    /// The TLS handshake was refused: a certificate, protocol or name problem.
    Tls,
    /// The connection broke or stalled after it was made.
    Io,
}

#[derive(Debug)]
pub(crate) struct ConnectFailure {
    pub stage: Stage,
    /// Whether a TCP connection to the host, or to the proxy, was ever made.
    pub connected: bool,
    pub io_kind: Option<io::ErrorKind>,
    pub os_code: Option<i32>,
}

pub(crate) type TlsStream = StreamOwned<ClientConnection, TcpStream>;

/// The engine's network: trust anchors, name resolution, the operator's proxy and the
/// time bounds of one connection.
pub struct Network {
    tls: Arc<ClientConfig>,
    resolve: Arc<Resolve>,
    proxy: Option<ProxySettings>,
    /// Bound for each connection attempt to one address.
    pub connect_timeout: Duration,
    /// Bound for each read or write once connected; a stall past it is a timeout.
    pub io_timeout: Duration,
}

impl std::fmt::Debug for Network {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Network")
            .field("proxy", &self.proxy)
            .field("connect_timeout", &self.connect_timeout)
            .field("io_timeout", &self.io_timeout)
            .finish_non_exhaustive()
    }
}

fn system_resolve(host: &str, port: u16) -> io::Result<Vec<SocketAddr>> {
    Ok((host, port).to_socket_addrs()?.collect())
}

impl Network {
    /// The production network: the bundled web PKI roots and the system resolver.
    pub fn new(proxy: Option<ProxySettings>) -> Self {
        let roots = RootCertStore::from_iter(webpki_roots::TLS_SERVER_ROOTS.iter().cloned());
        Self::with_parts(roots, Arc::new(system_resolve), proxy)
    }

    /// A network with the owner's trust anchors and resolver, for an owner that controls
    /// both, such as a test against its own servers.
    pub fn with_parts(
        roots: RootCertStore,
        resolve: Arc<Resolve>,
        proxy: Option<ProxySettings>,
    ) -> Self {
        let tls =
            ClientConfig::builder_with_provider(Arc::new(rustls::crypto::ring::default_provider()))
                .with_safe_default_protocol_versions()
                .expect("the ring provider supports the default protocol versions")
                .with_root_certificates(roots)
                .with_no_client_auth();
        Self {
            tls: Arc::new(tls),
            resolve,
            proxy,
            connect_timeout: Duration::from_secs(10),
            io_timeout: Duration::from_secs(30),
        }
    }

    pub(crate) fn proxied(&self, host: &str) -> Option<&ProxySettings> {
        self.proxy.as_ref().filter(|proxy| !proxy.bypasses(host))
    }

    /// Opens a verified TLS session to `url`'s host, through the proxy unless bypassed.
    /// `deadline` bounds every stage together; without one each stage has its own bound.
    pub(crate) fn open(
        &self,
        url: &HttpsUrl,
        deadline: Option<Instant>,
    ) -> Result<TlsStream, ConnectFailure> {
        let host = url.host().as_str();
        let proxy = self.proxied(host);
        let mut failure = ConnectFailure {
            stage: Stage::Resolve,
            connected: false,
            io_kind: None,
            os_code: None,
        };
        let (connect_host, connect_port) = match proxy {
            Some(proxy) => (proxy.host(), proxy.port()),
            None => (host, url.port()),
        };
        let remaining = |bound: Duration| match deadline {
            Some(deadline) => deadline
                .saturating_duration_since(Instant::now())
                .min(bound),
            None => bound,
        };
        let addresses =
            match self.resolved(connect_host, connect_port, remaining(self.connect_timeout)) {
                Ok(addresses) if !addresses.is_empty() => addresses,
                Ok(_) => return Err(failure),
                Err(error) => return Err(failure.with_io(&error)),
            };
        failure.stage = Stage::Connect;
        let mut last = None;
        let mut tcp = None;
        for address in addresses {
            let bound = remaining(self.connect_timeout);
            if bound.is_zero() {
                last = Some(io::Error::from(io::ErrorKind::TimedOut));
                break;
            }
            match TcpStream::connect_timeout(&address, bound) {
                Ok(stream) => {
                    tcp = Some(stream);
                    break;
                }
                Err(error) => last = Some(error),
            }
        }
        let Some(mut tcp) = tcp else {
            return Err(match last {
                Some(error) => failure.with_io(&error),
                None => failure,
            });
        };
        failure.connected = true;
        failure.stage = Stage::Io;
        let timeouts = |tcp: &TcpStream| {
            let bound = remaining(self.io_timeout);
            if bound.is_zero() {
                return Err(io::Error::from(io::ErrorKind::TimedOut));
            }
            tcp.set_read_timeout(Some(bound))?;
            tcp.set_write_timeout(Some(bound))
        };
        if let Err(error) = timeouts(&tcp).and_then(|()| tcp.set_nodelay(true)) {
            return Err(failure.with_io(&error));
        }
        if let Some(proxy) = proxy {
            failure.stage = Stage::Tunnel(None);
            if let Err((status, error)) = tunnel(&mut tcp, url, proxy) {
                failure.stage = Stage::Tunnel(status);
                return Err(match error {
                    Some(error) => failure.with_io(&error),
                    None => failure,
                });
            }
            if let Err(error) = timeouts(&tcp) {
                failure.stage = Stage::Io;
                return Err(failure.with_io(&error));
            }
        }
        failure.stage = Stage::Tls;
        let Ok(name) = ServerName::try_from(host.to_owned()) else {
            return Err(failure);
        };
        let Ok(mut connection) = ClientConnection::new(self.tls.clone(), name) else {
            return Err(failure);
        };
        while connection.is_handshaking() {
            if let Err(error) = connection.complete_io(&mut tcp) {
                // rustls reports its own refusals as InvalidData carrying a rustls error;
                // anything else is the socket.
                let refused = error
                    .get_ref()
                    .is_some_and(|inner| inner.is::<rustls::Error>());
                if !refused {
                    failure.stage = Stage::Io;
                }
                return Err(failure.with_io(&error));
            }
        }
        if let Err(error) = timeouts(&tcp) {
            failure.stage = Stage::Io;
            return Err(failure.with_io(&error));
        }
        Ok(StreamOwned::new(connection, tcp))
    }

    /// Resolution with a bound: the system resolver cannot be interrupted, so it runs on
    /// its own thread and an answer that comes too late is dropped with it.
    fn resolved(&self, host: &str, port: u16, bound: Duration) -> io::Result<Vec<SocketAddr>> {
        let (sender, receiver) = mpsc::channel();
        let resolve = self.resolve.clone();
        let name = host.to_owned();
        std::thread::Builder::new()
            .name("cadrumo-resolve".into())
            .spawn(move || {
                let _ = sender.send(resolve(&name, port));
            })?;
        receiver
            .recv_timeout(bound)
            .map_err(|_| io::Error::from(io::ErrorKind::TimedOut))?
    }
}

impl ConnectFailure {
    fn with_io(mut self, error: &io::Error) -> Self {
        self.io_kind = Some(error.kind());
        self.os_code = error.raw_os_error();
        self
    }
}

/// Opens a `CONNECT` tunnel; on refusal returns the proxy's status, or the socket error.
fn tunnel(
    tcp: &mut TcpStream,
    url: &HttpsUrl,
    proxy: &ProxySettings,
) -> Result<(), (Option<u16>, Option<io::Error>)> {
    let target = format!("{}:{}", url.host(), url.port());
    let authorization = proxy.authorization();
    let mut head = zeroize::Zeroizing::new(format!(
        "CONNECT {target} HTTP/1.1\r\nHost: {target}\r\nUser-Agent: Cadrumo\r\n"
    ));
    if let Some(authorization) = &authorization {
        head.push_str("Proxy-Authorization: ");
        head.push_str(authorization);
        head.push_str("\r\n");
    }
    head.push_str("\r\n");
    tcp.write_all(head.as_bytes())
        .and_then(|()| tcp.flush())
        .map_err(|error| (None, Some(error)))?;
    // Read the answer byte by byte so no tunnelled byte is consumed into a buffer.
    let mut reader = BufReader::with_capacity(1, ByteReader(tcp));
    let answer = http::read_head(&mut reader, &http::never).map_err(|error| (None, Some(error)))?;
    if (200..300).contains(&answer.status) {
        Ok(())
    } else {
        Err((Some(answer.status), None))
    }
}

struct ByteReader<'a>(&'a mut TcpStream);

impl Read for ByteReader<'_> {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        let limit = buffer.len().min(1);
        self.0.read(&mut buffer[..limit])
    }
}
