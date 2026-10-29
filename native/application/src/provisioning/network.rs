//! The network preflight: can this computer reach the hosts an item downloads from?
//!
//! Before a setup moves a byte, and in a full check, every host an item declares is
//! resolved, connected, taken through TLS and sent one `HEAD /`, with 3 s per host, all
//! hosts together. Any HTTP answer from the host itself over the verified connection, a
//! 403, a 5xx or a redirect to another host included, proves the host is reachable: the
//! question is whether the host can be reached, not whether a resource exists. A proxy
//! that refuses the tunnel or demands credentials is the network in between. When no host
//! was even connected and no proxy stood in between, the computer is offline. The
//! preflight runs on request only, never on a timer, and sends no taxpayer data.
//!
//! The 3 s is a bound on the whole host, name resolution included: a resolver that never
//! answers ends the host as unreachable, and so as offline when no host connected at all.
//! A cancellation ends the wait for a name at once and stops further addresses; a
//! connection or answer already under way ends at the same bound.

use super::{
    connection::{Network, Stage},
    failure::FailureCategory,
    http,
    pins::ComponentPins,
    url::HttpsUrl,
};
use crate::{component::Cancellation, value::HostName};
use serde::Serialize;
use std::{collections::BTreeSet, io::BufReader, time::Duration};

/// Bound for one host's whole preflight: resolution, connection, TLS and the answer.
pub const HOST_TIMEOUT: Duration = Duration::from_secs(3);

/// What the preflight found for one host, or for an item's hosts together.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Reachability {
    Offline,
    BlockedByNetwork,
    SecureConnectionFailed,
    HostUnreachable,
    Reachable,
}

impl Reachability {
    /// The failure category this outcome reports, or `None` when the host answered.
    pub fn failure_category(self) -> Option<FailureCategory> {
        match self {
            Self::Offline => Some(FailureCategory::Offline),
            Self::BlockedByNetwork => Some(FailureCategory::BlockedByNetwork),
            Self::SecureConnectionFailed => Some(FailureCategory::SecureConnectionFailed),
            Self::HostUnreachable => Some(FailureCategory::HostUnreachable),
            Self::Reachable => None,
        }
    }
}

/// One host's answer. `connected` records whether a TCP connection to the host, or to
/// the proxy, was ever made: it is what separates an offline computer from one host.
#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct HostCheck {
    pub host: HostName,
    pub outcome: Reachability,
    pub connected: bool,
    pub via_proxy: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status: Option<u16>,
}

/// The preflight of every host one item needs, in the order given.
#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct NetworkReport {
    pub hosts: Vec<HostCheck>,
}

impl NetworkReport {
    /// The worst outcome among the hosts, in the order offline, blocked by the network,
    /// secure connection failed, host unreachable; reachable only when every host is.
    pub fn outcome(&self) -> Reachability {
        self.hosts
            .iter()
            .map(|check| check.outcome)
            .min()
            .unwrap_or(Reachability::Reachable)
    }

    pub fn failure_category(&self) -> Option<FailureCategory> {
        self.outcome().failure_category()
    }
}

/// The hosts an item downloads from, as its pins declare them; `None` when this build
/// carries no pins for the item. The local AI's models come from the registries their
/// selected names state, which the engine adds.
pub fn item_hosts(pins: &ComponentPins, item: &str) -> Option<BTreeSet<HostName>> {
    match item {
        "browser" => pins.browser.as_ref().map(|browser| browser.hosts.clone()),
        "local_ai" => pins.program.as_ref().map(|program| program.hosts.clone()),
        _ => None,
    }
}

/// Checks every host together, each within `timeout`, through `network`. Once
/// `cancellation` is cancelled the report is no finding: its hosts read as unreachable.
pub fn preflight(
    network: &Network,
    hosts: &[HostName],
    timeout: Duration,
    cancellation: &Cancellation,
) -> NetworkReport {
    let checks: Vec<HostCheck> = std::thread::scope(|scope| {
        let running: Vec<_> = hosts
            .iter()
            .map(|host| scope.spawn(move || check(network, host, timeout, cancellation)))
            .collect();
        running
            .into_iter()
            .zip(hosts)
            .map(|(thread, host)| {
                thread.join().unwrap_or_else(|_| HostCheck {
                    host: host.clone(),
                    outcome: Reachability::HostUnreachable,
                    connected: false,
                    via_proxy: network.proxied(host.as_str()).is_some(),
                    status: None,
                })
            })
            .collect()
    });
    let nowhere = !checks.is_empty()
        && checks.iter().all(|check| {
            check.outcome == Reachability::HostUnreachable && !check.connected && !check.via_proxy
        });
    let hosts = checks
        .into_iter()
        .map(|mut check| {
            if nowhere {
                check.outcome = Reachability::Offline;
            }
            check
        })
        .collect();
    NetworkReport { hosts }
}

fn check(
    network: &Network,
    host: &HostName,
    timeout: Duration,
    cancellation: &Cancellation,
) -> HostCheck {
    let via_proxy = network.proxied(host.as_str()).is_some();
    let mut answer = HostCheck {
        host: host.clone(),
        outcome: Reachability::HostUnreachable,
        connected: false,
        via_proxy,
        status: None,
    };
    let Ok(url) = HttpsUrl::parse(&format!("https://{host}/")) else {
        return answer;
    };
    let deadline = network.deadline_after(timeout);
    let mut stream =
        match network.open_unless_cancelled(&url, Some(deadline.clone()), Some(cancellation)) {
            Ok(stream) => stream,
            Err(failure) => {
                answer.connected = failure.connected;
                answer.outcome = match failure.stage {
                    Stage::Tls => Reachability::SecureConnectionFailed,
                    Stage::Tunnel(Some(403 | 407)) => Reachability::BlockedByNetwork,
                    Stage::Resolve | Stage::Connect | Stage::Tunnel(_) | Stage::Io => {
                        Reachability::HostUnreachable
                    }
                };
                if let Stage::Tunnel(status) = failure.stage {
                    answer.status = status;
                }
                return answer;
            }
        };
    answer.connected = true;
    if http::write_request(&mut stream, "HEAD", url.target(), &url.authority(), &[]).is_err() {
        return answer;
    }
    // Every read of the stream is held to the deadline itself; this stop only ends the
    // wait between lines at once, and for a cancellation.
    let expired = || cancellation.is_cancelled() || deadline.left().is_zero();
    if let Ok(head) = http::read_head(&mut BufReader::new(stream), &expired) {
        answer.outcome = Reachability::Reachable;
        answer.status = Some(head.status);
    }
    answer
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::provisioning::{
        connection::{ManualClock, Resolve},
        pins::committed_tables,
        proxy::{PROXY_URL, ProxySettings},
        test_servers::{
            ProxyAnswer, ProxyServer, Reply, Request, TestCertificate, TlsServer, network_nowhere,
            network_to, response,
        },
    };
    use std::{
        net::{SocketAddr, TcpListener},
        sync::{Arc, Mutex, mpsc},
    };

    fn host(name: &str) -> HostName {
        HostName::new(name).unwrap()
    }

    fn proxied(url: String) -> Option<ProxySettings> {
        ProxySettings::from_settings(move |name| (name == PROXY_URL).then(|| url.clone())).unwrap()
    }

    fn answering(status: &'static str) -> impl Fn(&Request) -> Reply + Send + Sync + 'static {
        move |request: &Request| {
            assert!(request.line.starts_with("HEAD / "));
            Reply::Bytes(response(
                status,
                &[("Location", "https://elsewhere.example.org/".into())],
                b"",
            ))
        }
    }

    #[test]
    fn any_answer_from_the_verified_host_is_reachable() {
        let certificate = TestCertificate::new(&["cdn.example.com"]);
        for status in [
            "200 OK",
            "403 Forbidden",
            "404 Not Found",
            "503 Busy",
            "302 Found",
        ] {
            let server = TlsServer::start(&certificate, answering(status));
            let network = network_to(certificate.roots(), server.address(), None);
            let report = preflight(
                &network,
                &[host("cdn.example.com")],
                HOST_TIMEOUT,
                &Cancellation::default(),
            );
            assert_eq!(report.outcome(), Reachability::Reachable, "{status}");
            assert_eq!(report.failure_category(), None);
            assert_eq!(report.hosts[0].status, Some(status[..3].parse().unwrap()));
            assert!(report.hosts[0].connected);
        }
    }

    #[test]
    fn a_host_answering_with_a_header_longer_than_a_line_is_reachable() {
        // github.com, which the local AI program downloads from, answers `HEAD /` with a
        // content security policy longer than 4 KiB.
        let certificate = TestCertificate::new(&["github.com"]);
        let policy = format!("default-src 'none'; {}", "a".repeat(4_200));
        let server = TlsServer::start(&certificate, move |request: &Request| {
            assert!(request.line.starts_with("HEAD / "));
            Reply::Bytes(response(
                "200 OK",
                &[("Content-Security-Policy", policy.clone())],
                b"",
            ))
        });
        let network = network_to(certificate.roots(), server.address(), None);
        let report = preflight(
            &network,
            &[host("github.com")],
            HOST_TIMEOUT,
            &Cancellation::default(),
        );
        assert_eq!(report.outcome(), Reachability::Reachable);
        assert_eq!(report.hosts[0].status, Some(200));
    }

    #[test]
    fn an_untrusted_certificate_is_a_secure_connection_failure() {
        let certificate = TestCertificate::new(&["cdn.example.com"]);
        let server = TlsServer::start(&certificate, answering("200 OK"));
        let stranger = TestCertificate::new(&["cdn.example.com"]);
        let network = network_to(stranger.roots(), server.address(), None);
        let report = preflight(
            &network,
            &[host("cdn.example.com")],
            HOST_TIMEOUT,
            &Cancellation::default(),
        );
        assert_eq!(report.outcome(), Reachability::SecureConnectionFailed);
        assert_eq!(
            report.failure_category(),
            Some(FailureCategory::SecureConnectionFailed)
        );
    }

    #[test]
    fn a_proxy_refusing_the_tunnel_is_the_network_and_other_refusals_are_the_host() {
        let certificate = TestCertificate::new(&["cdn.example.com"]);
        let server = TlsServer::start(&certificate, answering("200 OK"));
        for (status, outcome) in [
            (407, Reachability::BlockedByNetwork),
            (403, Reachability::BlockedByNetwork),
            (502, Reachability::HostUnreachable),
        ] {
            let proxy = ProxyServer::start(ProxyAnswer::Refuse(status));
            let network = network_to(
                certificate.roots(),
                server.address(),
                proxied(proxy.url("")),
            );
            let report = preflight(
                &network,
                &[host("cdn.example.com")],
                HOST_TIMEOUT,
                &Cancellation::default(),
            );
            assert_eq!(report.outcome(), outcome, "{status}");
            assert_eq!(report.hosts[0].status, Some(status));
            assert!(report.hosts[0].via_proxy && report.hosts[0].connected);
        }
        let proxy = ProxyServer::start(ProxyAnswer::Tunnel(server.address()));
        let network = network_to(
            certificate.roots(),
            server.address(),
            proxied(proxy.url("")),
        );
        let report = preflight(
            &network,
            &[host("cdn.example.com")],
            HOST_TIMEOUT,
            &Cancellation::default(),
        );
        assert_eq!(report.outcome(), Reachability::Reachable);
        assert_eq!(proxy.requests.lock().unwrap().len(), 1);
    }

    #[test]
    fn no_resolution_or_connection_anywhere_is_offline_but_one_dead_host_is_that_host() {
        let certificate = TestCertificate::new(&["cdn.example.com"]);
        let report = preflight(
            &network_nowhere(certificate.roots()),
            &[host("cdn.example.com"), host("mirror.example.com")],
            HOST_TIMEOUT,
            &Cancellation::default(),
        );
        assert_eq!(report.outcome(), Reachability::Offline);
        assert!(
            report
                .hosts
                .iter()
                .all(|check| check.outcome == Reachability::Offline)
        );
        assert_eq!(report.failure_category(), Some(FailureCategory::Offline));

        let server = TlsServer::start(&certificate, answering("200 OK"));
        let closed = {
            let listener = TcpListener::bind("127.0.0.1:0").unwrap();
            listener.local_addr().unwrap()
        };
        let live = server.address();
        let resolve: Arc<Resolve> = Arc::new(
            move |name: &str, _port: u16| -> std::io::Result<Vec<SocketAddr>> {
                Ok(vec![if name == "cdn.example.com" {
                    live
                } else {
                    closed
                }])
            },
        );
        let network = Network::with_parts(certificate.roots(), resolve, None);
        let report = preflight(
            &network,
            &[host("cdn.example.com"), host("mirror.example.com")],
            HOST_TIMEOUT,
            &Cancellation::default(),
        );
        assert_eq!(
            report
                .hosts
                .iter()
                .map(|check| check.outcome)
                .collect::<Vec<_>>(),
            [Reachability::Reachable, Reachability::HostUnreachable]
        );
        assert!(!report.hosts[1].connected);
        assert_eq!(report.outcome(), Reachability::HostUnreachable);

        let unreachable_proxy = proxied(format!("http://{closed}"));
        let network = network_to(certificate.roots(), closed, unreachable_proxy);
        let report = preflight(
            &network,
            &[host("cdn.example.com")],
            HOST_TIMEOUT,
            &Cancellation::default(),
        );
        assert_eq!(
            report.outcome(),
            Reachability::HostUnreachable,
            "a dead proxy proves nothing about the computer"
        );
    }

    #[test]
    fn a_host_that_never_answers_is_unreachable_within_its_bound() {
        let certificate = TestCertificate::new(&["cdn.example.com"]);
        let server = TlsServer::start(&certificate, |_: &Request| Reply::Hold(Vec::new()));
        let network = network_to(certificate.roots(), server.address(), None);
        let report = preflight(
            &network,
            &[host("cdn.example.com")],
            Duration::from_millis(300),
            &Cancellation::default(),
        );
        assert_eq!(report.outcome(), Reachability::HostUnreachable);
        assert!(report.hosts[0].connected);
    }

    #[test]
    fn a_host_dripping_its_answer_is_unreachable_once_its_bound_has_passed() {
        let certificate = TestCertificate::new(&["cdn.example.com"]);
        let (chunks, fed) = mpsc::channel::<Vec<u8>>();
        let (asked, request_seen) = mpsc::channel::<()>();
        let fed = Mutex::new(Some(fed));
        let asked = Mutex::new(asked);
        let server = TlsServer::start(&certificate, move |_: &Request| {
            asked.lock().unwrap().send(()).unwrap();
            Reply::Fed(Mutex::new(fed.lock().unwrap().take().unwrap()))
        });
        let clock = ManualClock::new();
        let network =
            network_to(certificate.roots(), server.address(), None).with_clock(clock.clone());
        let report = std::thread::scope(|scope| {
            let checking = scope.spawn(|| {
                preflight(
                    &network,
                    &[host("cdn.example.com")],
                    HOST_TIMEOUT,
                    &Cancellation::default(),
                )
            });
            // The connection is up and the host has the request; it answers byte by byte
            // and sends the last byte of the head only after the bound has passed.
            request_seen.recv().unwrap();
            chunks.send(b"HTTP/1.1 200 OK\r\n\r".to_vec()).unwrap();
            clock.advance(HOST_TIMEOUT);
            chunks.send(b"\n".to_vec()).unwrap();
            let report = checking.join().unwrap();
            drop(chunks);
            report
        });
        assert_eq!(report.outcome(), Reachability::HostUnreachable);
        assert!(report.hosts[0].connected);
        assert_eq!(report.hosts[0].status, None);
    }

    #[test]
    fn a_host_dripping_its_answer_inside_its_bound_is_still_found() {
        let certificate = TestCertificate::new(&["cdn.example.com"]);
        let (chunks, fed) = mpsc::channel::<Vec<u8>>();
        let (asked, request_seen) = mpsc::channel::<()>();
        let fed = Mutex::new(Some(fed));
        let asked = Mutex::new(asked);
        let server = TlsServer::start(&certificate, move |_: &Request| {
            asked.lock().unwrap().send(()).unwrap();
            Reply::Fed(Mutex::new(fed.lock().unwrap().take().unwrap()))
        });
        let clock = ManualClock::new();
        let network =
            network_to(certificate.roots(), server.address(), None).with_clock(clock.clone());
        let report = std::thread::scope(|scope| {
            let checking = scope.spawn(|| {
                preflight(
                    &network,
                    &[host("cdn.example.com")],
                    HOST_TIMEOUT,
                    &Cancellation::default(),
                )
            });
            request_seen.recv().unwrap();
            chunks
                .send(
                    b"HTTP/1.1 204 No Content
X-Slow: "
                        .to_vec(),
                )
                .unwrap();
            clock.advance(HOST_TIMEOUT - Duration::from_millis(1));
            chunks
                .send(
                    b"drip

"
                    .to_vec(),
                )
                .unwrap();
            let report = checking.join().unwrap();
            drop(chunks);
            report
        });
        assert_eq!(report.outcome(), Reachability::Reachable);
        assert_eq!(report.hosts[0].status, Some(204));
    }

    /// A resolver that never answers on its own: each lookup reports itself on `entered`
    /// and then waits until the returned sender is dropped.
    fn stalled_resolver() -> (Arc<Resolve>, mpsc::Receiver<()>, mpsc::Sender<()>) {
        let (entered, reached) = mpsc::channel();
        let (release, released) = mpsc::channel::<()>();
        let entered = Mutex::new(entered);
        let released = Mutex::new(released);
        let resolve: Arc<Resolve> = Arc::new(move |_: &str, _: u16| {
            entered.lock().unwrap().send(()).unwrap();
            let _ = released.lock().unwrap().recv();
            Err(std::io::Error::from(std::io::ErrorKind::NotFound))
        });
        (resolve, reached, release)
    }

    #[test]
    fn a_resolver_that_never_answers_ends_the_host_at_its_bound() {
        let certificate = TestCertificate::new(&["cdn.example.com"]);
        let hosts = [host("cdn.example.com"), host("mirror.example.com")];

        let (resolve, reached, release) = stalled_resolver();
        let network = Network::with_parts(certificate.roots(), resolve, None);
        let report = preflight(
            &network,
            &hosts,
            Duration::from_millis(100),
            &Cancellation::default(),
        );
        // The report came back while every lookup was still held, so the bound ended it.
        reached.recv().unwrap();
        assert_eq!(report.outcome(), Reachability::Offline);
        assert_eq!(report.failure_category(), Some(FailureCategory::Offline));
        assert!(report.hosts.iter().all(|check| !check.connected));
        drop(release);

        let (resolve, reached, release) = stalled_resolver();
        let proxy = proxied("http://proxy.example.net:3128".into());
        let network = Network::with_parts(certificate.roots(), resolve, proxy);
        let report = preflight(
            &network,
            &hosts[..1],
            Duration::from_millis(100),
            &Cancellation::default(),
        );
        reached.recv().unwrap();
        assert_eq!(
            report.outcome(),
            Reachability::HostUnreachable,
            "a stalled proxy name proves nothing about the computer"
        );
        assert!(report.hosts[0].via_proxy && !report.hosts[0].connected);
        drop(release);
    }

    #[test]
    fn a_cancellation_ends_the_wait_for_a_name_at_once() {
        let certificate = TestCertificate::new(&["cdn.example.com"]);
        let (resolve, reached, release) = stalled_resolver();
        let mut network = Network::with_parts(certificate.roots(), resolve, None);
        // Only the cancellation can end this wait.
        network.connect_timeout = Duration::from_secs(3600);
        let cancellation = Cancellation::default();
        let report = std::thread::scope(|scope| {
            let cancelling = &cancellation;
            scope.spawn(move || {
                reached.recv().unwrap();
                cancelling.cancel();
            });
            preflight(
                &network,
                &[host("cdn.example.com")],
                Duration::from_secs(3600),
                &cancellation,
            )
        });
        assert!(cancellation.is_cancelled());
        assert!(!report.hosts[0].connected);
        drop(release);

        // A cancellation that came first stops the lookup before it is waited for.
        let (resolve, _reached, release) = stalled_resolver();
        let mut network = Network::with_parts(certificate.roots(), resolve, None);
        network.connect_timeout = Duration::from_secs(3600);
        let report = preflight(
            &network,
            &[host("cdn.example.com")],
            Duration::from_secs(3600),
            &cancellation,
        );
        assert!(!report.hosts[0].connected);
        drop(release);
    }

    #[test]
    fn items_check_the_hosts_their_pins_declare() {
        let pins = ComponentPins::load(&committed_tables()).unwrap();
        let browser = item_hosts(&pins, "browser").unwrap();
        assert!(browser.contains(&host("cdn.playwright.dev")));
        let local_ai = item_hosts(&pins, "local_ai").unwrap();
        assert!(local_ai.contains(&host("github.com")));
        assert_eq!(item_hosts(&pins, "google"), None);
        let none = ComponentPins {
            browser: pins.browser.clone(),
            program: None,
        };
        assert_eq!(item_hosts(&none, "local_ai"), None);
    }
}
