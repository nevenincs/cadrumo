//! Real local servers for the provisioning tests: a TLS server with a certificate made in
//! the test, and a `CONNECT` proxy. Every server listens on a loopback port the system
//! picks, answers each request through the test's handler, and joins its threads when
//! dropped.

use super::connection::{Network, Resolve};
use super::proxy::ProxySettings;
use ring::{
    rand::SystemRandom,
    signature::{ECDSA_P256_SHA256_ASN1_SIGNING, EcdsaKeyPair, KeyPair},
};
use rustls::{
    RootCertStore, ServerConfig, ServerConnection, StreamOwned,
    pki_types::{CertificateDer, PrivateKeyDer, PrivatePkcs8KeyDer},
};
use std::{
    collections::BTreeMap,
    io::{self, BufRead, BufReader, Write},
    net::{Shutdown, SocketAddr, TcpListener, TcpStream},
    sync::{
        Arc, Condvar, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread::JoinHandle,
};

fn der(tag: u8, content: &[u8]) -> Vec<u8> {
    let mut out = vec![tag];
    let length = content.len();
    if length < 0x80 {
        out.push(length as u8);
    } else {
        let bytes: Vec<u8> = length
            .to_be_bytes()
            .into_iter()
            .skip_while(|byte| *byte == 0)
            .collect();
        out.push(0x80 | bytes.len() as u8);
        out.extend(bytes);
    }
    out.extend_from_slice(content);
    out
}

fn sequence(parts: &[Vec<u8>]) -> Vec<u8> {
    der(0x30, &parts.concat())
}

const ECDSA_WITH_SHA256: &[u8] = &[0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x04, 0x03, 0x02];
const EC_PUBLIC_KEY: &[u8] = &[0x06, 0x07, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01];
const PRIME256V1: &[u8] = &[0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07];
const COMMON_NAME: &[u8] = &[0x06, 0x03, 0x55, 0x04, 0x03];
const SUBJECT_ALT_NAME: &[u8] = &[0x06, 0x03, 0x55, 0x1d, 0x11];

/// A self-signed P-256 certificate for `hosts`, generated in the test, with its key.
pub(crate) struct TestCertificate {
    pub der: Vec<u8>,
    pkcs8: Vec<u8>,
}

impl TestCertificate {
    pub fn new(hosts: &[&str]) -> Self {
        let random = SystemRandom::new();
        let pkcs8 = EcdsaKeyPair::generate_pkcs8(&ECDSA_P256_SHA256_ASN1_SIGNING, &random)
            .unwrap()
            .as_ref()
            .to_vec();
        let pair =
            EcdsaKeyPair::from_pkcs8(&ECDSA_P256_SHA256_ASN1_SIGNING, &pkcs8, &random).unwrap();
        let algorithm = sequence(&[ECDSA_WITH_SHA256.to_vec()]);
        let name = sequence(&[der(
            0x31,
            &sequence(&[COMMON_NAME.to_vec(), der(0x0c, b"Cadrumo test server")]),
        )]);
        let mut point = vec![0];
        point.extend_from_slice(pair.public_key().as_ref());
        let key = sequence(&[
            sequence(&[EC_PUBLIC_KEY.to_vec(), PRIME256V1.to_vec()]),
            der(0x03, &point),
        ]);
        let names: Vec<u8> = hosts
            .iter()
            .flat_map(|host| der(0x82, host.as_bytes()))
            .collect();
        let extensions = der(
            0xa3,
            &sequence(&[sequence(&[
                SUBJECT_ALT_NAME.to_vec(),
                der(0x04, &der(0x30, &names)),
            ])]),
        );
        let mut serial = [0u8; 8];
        ring::rand::SecureRandom::fill(&random, &mut serial).unwrap();
        serial[0] &= 0x7f;
        serial[0] |= 0x01;
        let tbs = sequence(&[
            der(0xa0, &der(0x02, &[2])),
            der(0x02, &serial),
            algorithm.clone(),
            name.clone(),
            sequence(&[der(0x17, b"200101000000Z"), der(0x18, b"20991231235959Z")]),
            name,
            key,
            extensions,
        ]);
        let signature = pair.sign(&random, &tbs).unwrap();
        let mut bits = vec![0];
        bits.extend_from_slice(signature.as_ref());
        Self {
            der: sequence(&[tbs, algorithm, der(0x03, &bits)]),
            pkcs8,
        }
    }

    pub fn roots(&self) -> RootCertStore {
        let mut roots = RootCertStore::empty();
        roots.add(CertificateDer::from(self.der.clone())).unwrap();
        roots
    }

    fn server_config(&self) -> Arc<ServerConfig> {
        let config =
            ServerConfig::builder_with_provider(Arc::new(rustls::crypto::ring::default_provider()))
                .with_safe_default_protocol_versions()
                .unwrap()
                .with_no_client_auth()
                .with_single_cert(
                    vec![CertificateDer::from(self.der.clone())],
                    PrivateKeyDer::Pkcs8(PrivatePkcs8KeyDer::from(self.pkcs8.clone())),
                )
                .unwrap();
        Arc::new(config)
    }
}

/// One request a server received.
#[derive(Clone, Debug)]
pub(crate) struct Request {
    pub line: String,
    pub headers: BTreeMap<String, String>,
}

impl Request {
    pub fn target(&self) -> &str {
        self.line.split(' ').nth(1).unwrap_or_default()
    }

    pub fn header(&self, name: &str) -> Option<&str> {
        self.headers
            .get(&name.to_ascii_lowercase())
            .map(String::as_str)
    }
}

/// How a server answers one request.
pub(crate) enum Reply {
    /// These bytes, then an orderly close.
    Bytes(Vec<u8>),
    /// These bytes, then the connection is dropped without a TLS close.
    Cut(Vec<u8>),
    /// These bytes, then nothing until the server is dropped.
    Hold(Vec<u8>),
}

pub(crate) fn response(status: &str, headers: &[(&str, String)], body: &[u8]) -> Vec<u8> {
    let mut out = format!("HTTP/1.1 {status}\r\n").into_bytes();
    for (name, value) in headers {
        out.extend_from_slice(format!("{name}: {value}\r\n").as_bytes());
    }
    out.extend_from_slice(b"\r\n");
    out.extend_from_slice(body);
    out
}

type Handler = dyn Fn(&Request) -> Reply + Send + Sync;

fn read_request(reader: &mut impl BufRead) -> io::Result<Request> {
    let mut line = String::new();
    reader.read_line(&mut line)?;
    let mut headers = BTreeMap::new();
    loop {
        let mut header = String::new();
        if reader.read_line(&mut header)? == 0 || header.trim().is_empty() {
            break;
        }
        if let Some((name, value)) = header.trim_end().split_once(':') {
            headers.insert(name.trim().to_ascii_lowercase(), value.trim().to_owned());
        }
    }
    Ok(Request {
        line: line.trim_end().to_owned(),
        headers,
    })
}

/// Set once the server is dropped; a held reply waits for it.
#[derive(Default)]
pub(crate) struct Released {
    done: Mutex<bool>,
    signal: Condvar,
}

impl Released {
    fn wait(&self) {
        let mut done = self.done.lock().unwrap();
        while !*done {
            done = self.signal.wait(done).unwrap();
        }
    }

    fn release(&self) {
        *self.done.lock().unwrap() = true;
        self.signal.notify_all();
    }
}

struct Listening {
    address: SocketAddr,
    stop: Arc<AtomicBool>,
    released: Arc<Released>,
    accept: Option<JoinHandle<()>>,
    workers: Arc<Mutex<Vec<JoinHandle<()>>>>,
}

impl Listening {
    fn start(serve: impl Fn(TcpStream, &Released) + Send + Sync + 'static) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let stop = Arc::new(AtomicBool::new(false));
        let released = Arc::new(Released::default());
        let workers: Arc<Mutex<Vec<JoinHandle<()>>>> = Arc::default();
        let serve = Arc::new(serve);
        let accept = {
            let stop = stop.clone();
            let workers = workers.clone();
            let released = released.clone();
            std::thread::spawn(move || {
                for stream in listener.incoming() {
                    if stop.load(Ordering::Acquire) {
                        break;
                    }
                    let Ok(stream) = stream else { continue };
                    let serve = serve.clone();
                    let released = released.clone();
                    workers
                        .lock()
                        .unwrap()
                        .push(std::thread::spawn(move || serve(stream, &released)));
                }
            })
        };
        Self {
            address,
            stop,
            released,
            accept: Some(accept),
            workers,
        }
    }
}

impl Drop for Listening {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Release);
        self.released.release();
        let _ = TcpStream::connect(self.address);
        if let Some(accept) = self.accept.take() {
            let _ = accept.join();
        }
        let workers: Vec<JoinHandle<()>> = self.workers.lock().unwrap().drain(..).collect();
        for worker in workers {
            let _ = worker.join();
        }
    }
}

/// A TLS server answering every request through its handler, recording each request.
pub(crate) struct TlsServer {
    listening: Listening,
    pub requests: Arc<Mutex<Vec<Request>>>,
}

impl TlsServer {
    pub fn start(
        certificate: &TestCertificate,
        handler: impl Fn(&Request) -> Reply + Send + Sync + 'static,
    ) -> Self {
        let config = certificate.server_config();
        let requests: Arc<Mutex<Vec<Request>>> = Arc::default();
        let handler: Arc<Handler> = Arc::new(handler);
        let recorded = requests.clone();
        let listening = Listening::start(move |tcp, released| {
            let Ok(connection) = ServerConnection::new(config.clone()) else {
                return;
            };
            let mut stream = StreamOwned::new(connection, tcp);
            let request = {
                let mut reader = BufReader::new(&mut stream);
                match read_request(&mut reader) {
                    Ok(request) if !request.line.is_empty() => request,
                    _ => return,
                }
            };
            recorded.lock().unwrap().push(request.clone());
            match handler(&request) {
                Reply::Bytes(bytes) => {
                    let _ = stream.write_all(&bytes);
                    stream.conn.send_close_notify();
                    let _ = stream.flush();
                }
                Reply::Cut(bytes) => {
                    let _ = stream.write_all(&bytes);
                    let _ = stream.flush();
                    let _ = stream.sock.shutdown(Shutdown::Both);
                }
                Reply::Hold(bytes) => {
                    let _ = stream.write_all(&bytes);
                    let _ = stream.flush();
                    released.wait();
                }
            }
        });
        Self {
            listening,
            requests,
        }
    }

    pub fn address(&self) -> SocketAddr {
        self.listening.address
    }

    pub fn targets(&self) -> Vec<String> {
        self.requests
            .lock()
            .unwrap()
            .iter()
            .map(|request| request.target().to_owned())
            .collect()
    }
}

/// How the proxy answers a `CONNECT`.
#[derive(Clone, Copy)]
pub(crate) enum ProxyAnswer {
    /// Tunnel to the given address.
    Tunnel(SocketAddr),
    /// Refuse with this status.
    Refuse(u16),
}

/// A plain `CONNECT` proxy recording each tunnel request.
pub(crate) struct ProxyServer {
    listening: Listening,
    pub requests: Arc<Mutex<Vec<Request>>>,
}

impl ProxyServer {
    pub fn start(answer: ProxyAnswer) -> Self {
        let requests: Arc<Mutex<Vec<Request>>> = Arc::default();
        let recorded = requests.clone();
        let listening = Listening::start(move |mut client, _released| {
            let request = {
                let Ok(clone) = client.try_clone() else {
                    return;
                };
                let mut reader = BufReader::with_capacity(1, clone);
                match read_request(&mut reader) {
                    Ok(request) => request,
                    Err(_) => return,
                }
            };
            recorded.lock().unwrap().push(request);
            match answer {
                ProxyAnswer::Refuse(status) => {
                    let _ = client.write_all(&response(
                        &format!("{status} Refused"),
                        &[("Content-Length", "0".into())],
                        b"",
                    ));
                }
                ProxyAnswer::Tunnel(target) => {
                    let Ok(upstream) = TcpStream::connect(target) else {
                        return;
                    };
                    if client
                        .write_all(b"HTTP/1.1 200 Connection established\r\n\r\n")
                        .is_err()
                    {
                        return;
                    }
                    let (Ok(mut client_read), Ok(mut upstream_write)) =
                        (client.try_clone(), upstream.try_clone())
                    else {
                        return;
                    };
                    let forward = std::thread::spawn(move || {
                        let _ = io::copy(&mut client_read, &mut upstream_write);
                        let _ = upstream_write.shutdown(Shutdown::Write);
                    });
                    let mut upstream_read = upstream;
                    let _ = io::copy(&mut upstream_read, &mut client);
                    let _ = client.shutdown(Shutdown::Both);
                    let _ = forward.join();
                }
            }
        });
        Self {
            listening,
            requests,
        }
    }

    pub fn url(&self, credentials: &str) -> String {
        format!("http://{credentials}{}", self.listening.address)
    }
}

/// A network that trusts `roots` and resolves every name to `address`.
pub(crate) fn network_to(
    roots: RootCertStore,
    address: SocketAddr,
    proxy: Option<ProxySettings>,
) -> Network {
    let resolve: Arc<Resolve> = Arc::new(move |host: &str, port: u16| {
        if let Ok(ip) = host.parse::<std::net::IpAddr>() {
            return Ok(vec![SocketAddr::new(ip, port)]);
        }
        Ok(vec![address])
    });
    Network::with_parts(roots, resolve, proxy)
}

/// A network whose resolver finds no name at all.
pub(crate) fn network_nowhere(roots: RootCertStore) -> Network {
    let resolve: Arc<Resolve> =
        Arc::new(|_: &str, _: u16| Err(io::Error::new(io::ErrorKind::NotFound, "no such name")));
    Network::with_parts(roots, resolve, None)
}
