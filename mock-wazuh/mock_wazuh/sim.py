"""Simulated Wazuh environment: agents, processes, ports, users, files,
vulnerabilities, and a continuously generated alert stream.

Everything is seeded from MOCK_SEED so a fresh start always produces the same
fleet and the same 7-day alert history. Live alerts keep arriving afterwards.
"""

from __future__ import annotations

import collections
import copy
import random
import threading
import time
from datetime import datetime, timedelta, timezone

MANAGER = {"name": "wazuh-manager"}
WAZUH_VERSION = "v4.12.0"

# ---------------------------------------------------------------------------
# Fleet
# ---------------------------------------------------------------------------
AGENTS = [
    {"id": "000", "name": "wazuh-manager", "ip": "127.0.0.1", "os": ("ubuntu", "Ubuntu", "24.04"), "groups": ["default"], "role": "manager"},
    {"id": "001", "name": "web-prod-01", "ip": "10.0.1.11", "os": ("ubuntu", "Ubuntu", "22.04"), "groups": ["default", "linux", "web", "pci"], "role": "web"},
    {"id": "002", "name": "web-prod-02", "ip": "10.0.1.12", "os": ("ubuntu", "Ubuntu", "22.04"), "groups": ["default", "linux", "web", "pci"], "role": "web"},
    {"id": "003", "name": "db-prod-01", "ip": "10.0.2.21", "os": ("rhel", "Red Hat Enterprise Linux", "9.4"), "groups": ["default", "linux", "database", "pci"], "role": "db"},
    {"id": "004", "name": "dc-01", "ip": "10.0.3.10", "os": ("windows", "Microsoft Windows Server 2022 Datacenter", "10.0.20348"), "groups": ["default", "windows", "domain-controllers"], "role": "dc"},
    {"id": "005", "name": "fin-ws-17", "ip": "10.0.5.117", "os": ("windows", "Microsoft Windows 11 Enterprise", "10.0.22631"), "groups": ["default", "windows", "workstations", "finance"], "role": "ws"},
    {"id": "006", "name": "k8s-node-1", "ip": "10.0.4.31", "os": ("ubuntu", "Ubuntu", "22.04"), "groups": ["default", "linux", "kubernetes"], "role": "k8s"},
    {"id": "007", "name": "k8s-node-2", "ip": "10.0.4.32", "os": ("ubuntu", "Ubuntu", "22.04"), "groups": ["default", "linux", "kubernetes"], "role": "k8s"},
    {"id": "008", "name": "k8s-node-3", "ip": "10.0.4.33", "os": ("ubuntu", "Ubuntu", "22.04"), "groups": ["default", "linux", "kubernetes"], "role": "k8s"},
    {"id": "009", "name": "vpn-gw-01", "ip": "10.0.0.5", "os": ("debian", "Debian GNU/Linux", "12"), "groups": ["default", "linux", "perimeter"], "role": "vpn"},
    {"id": "010", "name": "mail-01", "ip": "10.0.6.25", "os": ("ubuntu", "Ubuntu", "22.04"), "groups": ["default", "linux", "mail"], "role": "mail"},
    {"id": "011", "name": "jump-01", "ip": "10.0.0.22", "os": ("ubuntu", "Ubuntu", "24.04"), "groups": ["default", "linux", "perimeter", "admin"], "role": "jump"},
    {"id": "012", "name": "dev-ws-04", "ip": "10.0.7.44", "os": ("macos", "macOS", "15.2"), "groups": ["default", "macos", "workstations", "engineering"], "role": "ws"},
    {"id": "013", "name": "backup-01", "ip": "10.0.2.40", "os": ("rhel", "Red Hat Enterprise Linux", "8.10"), "groups": ["default", "linux", "backup"], "role": "backup"},
]
AGENTS_BY_ID = {a["id"]: a for a in AGENTS}
AGENTS_BY_NAME = {a["name"]: a for a in AGENTS}

# Attacker infrastructure used by the recurring campaigns. Reputation data for
# these lives in THREAT_INTEL and is entirely fictional (mock environment).
ATTACKERS = {
    "185.220.101.45": {"country": "Germany", "city": "Frankfurt am Main", "lat": 50.11, "lon": 8.68, "asn": "AS208294", "org": "Tor exit relay"},
    "45.155.205.233": {"country": "Russia", "city": "Moscow", "lat": 55.75, "lon": 37.62, "asn": "AS49505", "org": "Hosting provider"},
    "222.186.30.112": {"country": "China", "city": "Nanjing", "lat": 32.06, "lon": 118.78, "asn": "AS4134", "org": "Chinanet"},
    "103.145.13.87": {"country": "Vietnam", "city": "Hanoi", "lat": 21.03, "lon": 105.85, "asn": "AS135905", "org": "VNPT"},
    "91.240.118.172": {"country": "Russia", "city": "Saint Petersburg", "lat": 59.93, "lon": 30.36, "asn": "AS57523", "org": "Chang Way Technologies"},
    "193.35.18.49": {"country": "Netherlands", "city": "Amsterdam", "lat": 52.37, "lon": 4.90, "asn": "AS213035", "org": "VPS provider"},
    "179.43.180.10": {"country": "Switzerland", "city": "Zurich", "lat": 47.37, "lon": 8.54, "asn": "AS51852", "org": "Private Layer"},
    "196.251.72.18": {"country": "Seychelles", "city": "Victoria", "lat": -4.62, "lon": 55.45, "asn": "AS401116", "org": "Bulletproof hosting"},
    "138.197.93.4": {"country": "United States", "city": "Clifton", "lat": 40.86, "lon": -74.16, "asn": "AS14061", "org": "DigitalOcean"},
    "177.54.144.9": {"country": "Brazil", "city": "Sao Paulo", "lat": -23.55, "lon": -46.63, "asn": "AS262287", "org": "Hosting provider"},
}
SSH_ATTACKERS = ["185.220.101.45", "45.155.205.233", "222.186.30.112", "103.145.13.87", "138.197.93.4", "177.54.144.9"]
WEB_ATTACKERS = ["91.240.118.172", "193.35.18.49", "196.251.72.18", "138.197.93.4"]
C2_IPS = ["45.155.205.233", "179.43.180.10"]

MALWARE_HASHES = {
    "kworkerd": "8f3a1c9e5b7d2a4f6e0c1b3d5a7e9f2c4b6d8a0e1f3c5b7d9e2a4c6b8d0f1e3a",
    "invoice_0924.js": "2b7e151628aed2a6abf7158809cf4f3c762e7160f38b4da56a784d9045190cfe",
    "msupdate.dll": "c0535e4be2b79ffd93291305436bf889314e4a3faec05ecffcbb7df31ad9e51a",
}

THREAT_INTEL = {
    "185.220.101.45": {"reputation": "malicious", "risk_score": 88, "tags": ["tor-exit", "ssh-bruteforce", "scanner"], "sources": ["mock-abuse-feed", "mock-tor-list"]},
    "45.155.205.233": {"reputation": "malicious", "risk_score": 96, "tags": ["ssh-bruteforce", "cryptominer-c2", "xmrig-pool-proxy"], "sources": ["mock-abuse-feed", "mock-c2-tracker"]},
    "222.186.30.112": {"reputation": "malicious", "risk_score": 81, "tags": ["ssh-bruteforce", "mass-scanner"], "sources": ["mock-abuse-feed"]},
    "103.145.13.87": {"reputation": "suspicious", "risk_score": 64, "tags": ["ssh-bruteforce"], "sources": ["mock-abuse-feed"]},
    "91.240.118.172": {"reputation": "malicious", "risk_score": 90, "tags": ["web-exploitation", "sqli", "scanner"], "sources": ["mock-abuse-feed", "mock-waf-shared"]},
    "193.35.18.49": {"reputation": "suspicious", "risk_score": 58, "tags": ["web-scanner"], "sources": ["mock-waf-shared"]},
    "179.43.180.10": {"reputation": "malicious", "risk_score": 97, "tags": ["cobalt-strike", "c2", "beacon"], "sources": ["mock-c2-tracker"]},
    "196.251.72.18": {"reputation": "malicious", "risk_score": 85, "tags": ["bulletproof-hosting", "exploit-kit"], "sources": ["mock-abuse-feed"]},
    "138.197.93.4": {"reputation": "suspicious", "risk_score": 47, "tags": ["cloud-scanner"], "sources": ["mock-abuse-feed"]},
    "177.54.144.9": {"reputation": "suspicious", "risk_score": 55, "tags": ["ssh-bruteforce"], "sources": ["mock-abuse-feed"]},
    "pool.minexmr-proxy.net": {"reputation": "malicious", "risk_score": 93, "tags": ["cryptomining", "xmrig"], "sources": ["mock-c2-tracker"]},
    "cdn-update-check.com": {"reputation": "malicious", "risk_score": 95, "tags": ["cobalt-strike", "c2-domain"], "sources": ["mock-c2-tracker"]},
    MALWARE_HASHES["kworkerd"]: {"reputation": "malicious", "risk_score": 94, "tags": ["xmrig", "linux-miner"], "sources": ["mock-virustotal"], "detections": "58/72"},
    MALWARE_HASHES["invoice_0924.js"]: {"reputation": "malicious", "risk_score": 91, "tags": ["js-dropper", "phishing"], "sources": ["mock-virustotal"], "detections": "41/68"},
    MALWARE_HASHES["msupdate.dll"]: {"reputation": "malicious", "risk_score": 98, "tags": ["cobalt-strike", "beacon"], "sources": ["mock-virustotal"], "detections": "63/72"},
}

LINUX_USERS = ["root", "ubuntu", "deploy", "svc_backup", "jdoe", "asmith", "postgres", "www-data"]
WIN_USERS = ["Administrator", "svc_sql", "j.doe", "a.smith", "m.garcia", "helpdesk01", "svc_backup"]
BRUTE_USERNAMES = ["admin", "root", "test", "oracle", "user", "ubuntu", "postgres", "git", "ftpuser", "support", "guest", "pi"]

KEV_CVES = {"CVE-2024-3400", "CVE-2023-4966", "CVE-2021-44228", "CVE-2024-6387", "CVE-2023-44487", "CVE-2024-3094", "CVE-2023-38831"}

VULN_CATALOG = [
    # cve, package, version, severity, cvss, published, description
    ("CVE-2024-6387", "openssh-server", "1:8.9p1-3ubuntu0.6", "High", 8.1, "2024-07-01", "regreSSHion: signal handler race condition in sshd allows unauthenticated remote code execution."),
    ("CVE-2021-44228", "log4j-core", "2.14.1", "Critical", 10.0, "2021-12-10", "Log4Shell: JNDI lookup in Apache Log4j2 allows remote code execution."),
    ("CVE-2024-3094", "xz-utils", "5.6.0-0.2", "Critical", 10.0, "2024-03-29", "Malicious code in xz/liblzma upstream tarballs (backdoor in sshd via systemd)."),
    ("CVE-2023-44487", "nginx", "1.18.0-6ubuntu14.4", "High", 7.5, "2023-10-10", "HTTP/2 Rapid Reset denial of service."),
    ("CVE-2024-3400", "pan-os-globalprotect", "10.2.9", "Critical", 10.0, "2024-04-12", "Command injection in PAN-OS GlobalProtect gateway."),
    ("CVE-2023-4966", "netscaler-adc", "13.1-48.47", "Critical", 9.4, "2023-10-10", "Citrix Bleed: sensitive information disclosure in NetScaler ADC/Gateway."),
    ("CVE-2023-38831", "winrar", "6.22", "High", 7.8, "2023-08-23", "WinRAR allows code execution when a user opens a benign file within a ZIP archive."),
    ("CVE-2024-21413", "microsoft-outlook", "16.0.17126", "Critical", 9.8, "2024-02-13", "Microsoft Outlook MonikerLink remote code execution."),
    ("CVE-2024-38063", "windows-tcpip", "10.0.20348.2582", "Critical", 9.8, "2024-08-13", "Windows TCP/IP IPv6 remote code execution."),
    ("CVE-2024-1086", "linux-image-generic", "5.15.0-94", "High", 7.8, "2024-01-31", "Use-after-free in netfilter nf_tables allows local privilege escalation."),
    ("CVE-2023-4911", "glibc", "2.35-0ubuntu3.4", "High", 7.8, "2023-10-03", "Looney Tunables: buffer overflow in glibc ld.so GLIBC_TUNABLES handling."),
    ("CVE-2024-2961", "glibc", "2.35-0ubuntu3.6", "High", 7.3, "2024-04-17", "iconv() out-of-bounds write in ISO-2022-CN-EXT conversion."),
    ("CVE-2023-38545", "curl", "7.81.0-1ubuntu1.13", "High", 9.8, "2023-10-11", "SOCKS5 heap buffer overflow in libcurl."),
    ("CVE-2024-24790", "golang-1.21", "1.21.5", "Critical", 9.8, "2024-06-05", "net/netip Is* methods misclassify IPv4-mapped IPv6 addresses."),
    ("CVE-2023-5678", "openssl", "3.0.2-0ubuntu1.12", "Medium", 5.3, "2023-11-06", "Excessive time spent in DH key generation and checks."),
    ("CVE-2024-0727", "openssl", "3.0.2-0ubuntu1.14", "Medium", 5.5, "2024-01-26", "NULL dereference processing malformed PKCS12 files."),
    ("CVE-2024-28182", "nghttp2", "1.43.0-1ubuntu0.1", "Medium", 5.3, "2024-04-04", "Unbounded CONTINUATION frames cause resource exhaustion."),
    ("CVE-2023-48795", "openssh-client", "1:8.9p1-3ubuntu0.4", "Medium", 5.9, "2023-12-18", "Terrapin: SSH prefix truncation attack."),
    ("CVE-2024-26130", "python3-cryptography", "38.0.4", "High", 7.5, "2024-02-21", "NULL pointer dereference in pkcs12 serialization."),
    ("CVE-2023-2650", "openssl", "3.0.2-0ubuntu1.9", "Medium", 6.5, "2023-05-30", "Possible DoS translating ASN.1 object identifiers."),
    ("CVE-2024-6345", "python3-setuptools", "59.6.0", "High", 8.8, "2024-07-15", "Remote code execution via package_index download functions."),
    ("CVE-2024-4577", "php8.1-cgi", "8.1.2", "Critical", 9.8, "2024-06-09", "PHP-CGI argument injection on Windows best-fit mapping."),
    ("CVE-2023-22515", "confluence", "8.3.2", "Critical", 10.0, "2023-10-04", "Broken access control in Confluence Data Center allows admin account creation."),
    ("CVE-2024-21762", "fortios-sslvpn", "7.2.6", "Critical", 9.8, "2024-02-09", "Out-of-bounds write in FortiOS SSL VPN."),
    ("CVE-2024-5535", "openssl", "3.0.2-0ubuntu1.15", "Low", 3.7, "2024-06-27", "SSL_select_next_proto buffer overread."),
    ("CVE-2023-7104", "sqlite3", "3.37.2-2ubuntu0.1", "Medium", 7.3, "2023-12-29", "Heap buffer overflow in sessionReadRecord."),
]

VULNS_FOR_ROLE = {
    "web": ["CVE-2024-6387", "CVE-2023-44487", "CVE-2024-4577", "CVE-2023-38545", "CVE-2023-4911", "CVE-2023-5678", "CVE-2024-28182", "CVE-2024-5535"],
    "db": ["CVE-2021-44228", "CVE-2024-1086", "CVE-2023-4911", "CVE-2023-7104", "CVE-2024-0727"],
    "dc": ["CVE-2024-38063", "CVE-2024-21413"],
    "ws": ["CVE-2023-38831", "CVE-2024-21413", "CVE-2024-38063"],
    "k8s": ["CVE-2024-24790", "CVE-2024-1086", "CVE-2024-6387", "CVE-2024-3094", "CVE-2023-48795"],
    "vpn": ["CVE-2024-3400", "CVE-2024-21762", "CVE-2024-6387"],
    "mail": ["CVE-2023-4966", "CVE-2023-38545", "CVE-2024-6345"],
    "jump": ["CVE-2024-6387", "CVE-2023-48795", "CVE-2024-2961"],
    "backup": ["CVE-2023-22515", "CVE-2024-26130", "CVE-2023-2650"],
    "manager": ["CVE-2024-5535"],
}


def fmt_ts(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}+0000"


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mitre(ids, tactics, techniques):
    return {"id": list(ids), "tactic": list(tactics), "technique": list(techniques)}


class Environment:
    """All mutable state. Guarded by a single lock; handlers hold it briefly."""

    def __init__(self, seed: int = 1337, backfill_days: int = 7, ring_size: int = 20000):
        self.lock = threading.RLock()
        self.rng = random.Random(seed)
        self.started_at = time.time()
        self.alerts: collections.deque = collections.deque(maxlen=ring_size)
        self.counter = 0
        self.firedtimes: collections.Counter = collections.Counter()
        self.blocked_ips: dict[str, dict] = {}       # ip -> {"agents": set|"all", "command", "since"}
        self.host_denied: dict[str, set] = {}        # ip -> set(agent_id)
        self.isolated: dict[str, float] = {}         # agent_id -> since
        self.disabled_users: dict[tuple, float] = {}  # (agent_id, username) -> since
        self.quarantined: dict[tuple, dict] = {}      # (agent_id, path) -> info
        self.ar_log: list[dict] = []
        self.manager_logs: collections.deque = collections.deque(maxlen=2000)
        self.processes: dict[str, dict[int, dict]] = {}
        self.ports: dict[str, list[dict]] = {}
        self.users: dict[str, list[str]] = {}
        self.files: dict[str, dict[str, dict]] = {}
        self.vulns: dict[str, list[dict]] = {}
        self.agent_state: dict[str, dict] = {}
        self._build_fleet()
        self._backfill(backfill_days)

    # ------------------------------------------------------------------ fleet
    def _build_fleet(self):
        rng = self.rng
        now = time.time()
        for a in AGENTS:
            aid = a["id"]
            linux = a["os"][0] in ("ubuntu", "rhel", "debian")
            windows = a["os"][0] == "windows"
            status = "disconnected" if aid == "012" else "active"
            self.agent_state[aid] = {
                "status": status,
                "registered": now - 86400 * rng.randint(60, 400),
                "last_keepalive": now - (rng.randint(3600 * 5, 3600 * 9) if status == "disconnected" else rng.randint(1, 50)),
            }
            procs: dict[int, dict] = {}

            def add(name, cmd, user="root", pid=None, ppid=1, mem=None):
                pid = pid or rng.randint(300, 48000)
                while pid in procs:
                    pid += 1
                procs[pid] = {
                    "pid": pid, "name": name, "cmd": cmd, "euser": user, "ppid": ppid,
                    "state": "S", "priority": 20, "nlwp": rng.randint(1, 16),
                    "resident": mem or rng.randint(2_000, 400_000), "vm_size": rng.randint(20_000, 2_000_000),
                    "start_time": int(now - rng.randint(600, 86400 * 20)),
                }
                return pid

            if windows:
                for n, c, u in [("System", "System", "SYSTEM"), ("smss.exe", r"\SystemRoot\System32\smss.exe", "SYSTEM"),
                                ("lsass.exe", r"C:\Windows\system32\lsass.exe", "SYSTEM"), ("services.exe", r"C:\Windows\system32\services.exe", "SYSTEM"),
                                ("svchost.exe", r"C:\Windows\system32\svchost.exe -k netsvcs -p", "SYSTEM"),
                                ("wazuh-agent.exe", r"C:\Program Files (x86)\ossec-agent\wazuh-agent.exe", "SYSTEM"),
                                ("explorer.exe", r"C:\Windows\explorer.exe", "CORP\\j.doe")]:
                    add(n, c, u)
                if a["role"] == "dc":
                    add("ntds.exe", r"C:\Windows\System32\ntds.exe", "SYSTEM")
                    add("dns.exe", r"C:\Windows\System32\dns.exe", "SYSTEM")
            elif linux or a["os"][0] == "macos":
                for n, c in [("systemd", "/sbin/init"), ("sshd", "sshd: /usr/sbin/sshd -D [listener] 0 of 10-100 startups"),
                             ("cron", "/usr/sbin/cron -f"), ("rsyslogd", "/usr/sbin/rsyslogd -n -iNONE"),
                             ("wazuh-agentd", "/var/ossec/bin/wazuh-agentd"), ("wazuh-syscheckd", "/var/ossec/bin/wazuh-syscheckd"),
                             ("wazuh-modulesd", "/var/ossec/bin/wazuh-modulesd")]:
                    add(n, c, "wazuh" if n.startswith("wazuh-agentd") else "root")
            role = a["role"]
            if role == "web":
                add("nginx", "nginx: master process /usr/sbin/nginx -g daemon on; master_process on;")
                for _ in range(4):
                    add("nginx", "nginx: worker process", "www-data")
                add("php-fpm8.1", "php-fpm: pool www", "www-data")
            if role == "db":
                add("java", "/usr/bin/java -jar /opt/reporting/reporting-service.jar", "svc_report")
                add("postgres", "/usr/lib/postgresql/15/bin/postgres -D /var/lib/postgresql/15/main", "postgres")
            if role == "k8s":
                add("kubelet", "/usr/bin/kubelet --config=/var/lib/kubelet/config.yaml")
                add("containerd", "/usr/bin/containerd")
            if role == "vpn":
                add("openvpn", "/usr/sbin/openvpn --config /etc/openvpn/server.conf")
            if role == "mail":
                add("master", "/usr/lib/postfix/sbin/master -w")
                add("dovecot", "/usr/sbin/dovecot -F")
            if role == "manager":
                for n in ("wazuh-analysisd", "wazuh-remoted", "wazuh-db", "wazuh-apid", "wazuh-indexer"):
                    add(n, f"/var/ossec/bin/{n}", "wazuh")
            # --- compromised hosts --------------------------------------------------
            if aid == "007":  # crypto miner on k8s-node-2
                self.miner_pid = add("kworkerd", "/tmp/.x/kworkerd -o pool.minexmr-proxy.net:443 -u 44Ai...x --cpu-max-threads-hint=90", "www-data", pid=31337, mem=2_400_000)
            if aid == "005":  # Cobalt Strike-like beacon on fin-ws-17
                self.beacon_pid = add("rundll32.exe", r'rundll32.exe C:\Users\j.doe\AppData\Roaming\Microsoft\msupdate.dll,StartW', "CORP\\j.doe", pid=6644)
            self.processes[aid] = procs

            ports = []

            def port(proto, lport, pname, state="listening", rip="0.0.0.0", rport=0, lip="0.0.0.0"):
                pid = next((p["pid"] for p in procs.values() if p["name"] == pname), None)
                ports.append({"protocol": proto, "local": {"ip": lip, "port": lport}, "remote": {"ip": rip, "port": rport},
                              "state": state, "pid": pid, "process": pname, "inode": rng.randint(10_000, 999_999), "tx_queue": 0, "rx_queue": 0})

            if windows:
                port("tcp", 135, "svchost.exe"); port("tcp", 445, "System"); port("tcp", 3389, "svchost.exe")
                if role == "dc":
                    port("tcp", 88, "lsass.exe"); port("tcp", 389, "lsass.exe"); port("udp", 53, "dns.exe", state="")
                if aid == "005":
                    port("tcp", 51544, "rundll32.exe", state="established", rip="179.43.180.10", rport=443, lip=a["ip"])
            else:
                port("tcp", 22, "sshd")
                if role == "web":
                    port("tcp", 80, "nginx"); port("tcp", 443, "nginx")
                if role == "db":
                    port("tcp", 5432, "postgres", lip="10.0.2.21"); port("tcp", 8080, "java")
                if role == "vpn":
                    port("udp", 1194, "openvpn", state="")
                if role == "mail":
                    port("tcp", 25, "master"); port("tcp", 993, "dovecot")
                if role == "k8s":
                    port("tcp", 10250, "kubelet")
                if role == "manager":
                    port("tcp", 1514, "wazuh-remoted"); port("tcp", 1515, "wazuh-authd"); port("tcp", 55000, "wazuh-apid")
                if aid == "007":
                    port("tcp", 3333, "kworkerd")
                    port("tcp", 40112, "kworkerd", state="established", rip="45.155.205.233", rport=443, lip=a["ip"])
            self.ports[aid] = ports

            self.users[aid] = list(WIN_USERS if windows else LINUX_USERS)
            files = {}
            if aid == "007":
                files["/tmp/.x/kworkerd"] = {"sha256": MALWARE_HASHES["kworkerd"], "size": 2_811_392}
            if aid == "005":
                files[r"C:\Users\j.doe\AppData\Roaming\Microsoft\msupdate.dll"] = {"sha256": MALWARE_HASHES["msupdate.dll"], "size": 311_808}
                files[r"C:\Users\j.doe\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\invoice_0924.js"] = {"sha256": MALWARE_HASHES["invoice_0924.js"], "size": 18_220}
            self.files[aid] = files

            vulns = []
            cat = {v[0]: v for v in VULN_CATALOG}
            for cve in VULNS_FOR_ROLE.get(role, []):
                c = cat[cve]
                detected = now - 86400 * rng.uniform(0.2, 25)
                vulns.append({
                    "agent": {"id": aid, "name": a["name"]},
                    "vulnerability": {
                        "id": c[0], "severity": c[3], "score": {"base": c[4], "version": "3.1"},
                        "description": c[6], "reference": f"https://nvd.nist.gov/vuln/detail/{c[0]}",
                        "published_at": c[5] + "T00:00:00Z", "detected_at": iso(detected),
                        "category": "Packages", "classification": "CVSS", "scanner": {"vendor": "Wazuh"},
                        "under_evaluation": False, "enumeration": "CVE",
                    },
                    "package": {"name": c[1], "version": c[2], "architecture": "amd64" if not windows else "x86_64", "type": "deb" if a["os"][0] in ("ubuntu", "debian") else ("rpm" if a["os"][0] == "rhel" else "win")},
                    "kev": c[0] in KEV_CVES,
                    "_detected_ts": detected,
                })
            self.vulns[aid] = vulns

    # ----------------------------------------------------------------- alerts
    def _next_id(self, ts: float) -> str:
        self.counter += 1
        return f"{int(ts)}.{self.counter:07d}"

    def _alert(self, ts, agent_id, rule_id, level, desc, groups, decoder, location, full_log,
               data=None, mitre_block=None, compliance=None, extra=None):
        a = AGENTS_BY_ID[agent_id]
        self.firedtimes[rule_id] += 1
        rule = {"level": level, "description": desc, "id": str(rule_id), "firedtimes": self.firedtimes[rule_id],
                "mail": level >= 12, "groups": groups}
        if mitre_block:
            rule["mitre"] = mitre_block
        for k, v in (compliance or {}).items():
            rule[k] = v
        alert = {
            "timestamp": fmt_ts(ts), "rule": rule,
            "agent": {"id": agent_id, "name": a["name"], "ip": a["ip"]},
            "manager": dict(MANAGER), "id": self._next_id(ts), "cluster": {"name": "wazuh-cluster", "node": "master-node"},
            "decoder": {"name": decoder} if isinstance(decoder, str) else decoder,
            "full_log": full_log, "location": location, "_ts": ts,
        }
        if data:
            alert["data"] = data
            src = data.get("srcip")
            if src in ATTACKERS:
                g = ATTACKERS[src]
                alert["GeoLocation"] = {"country_name": g["country"], "city_name": g["city"], "location": {"lat": g["lat"], "lon": g["lon"]}}
        if extra:
            alert.update(extra)
        self.alerts.append(alert)
        return alert

    def _syslog_ts(self, ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%b %d %H:%M:%S")

    # --- individual event generators (return list of alerts) -------------------
    def ev_noise(self, ts):
        rng = self.rng
        a = rng.choice([x for x in AGENTS if self.agent_state[x["id"]]["status"] == "active"])
        aid, host = a["id"], a["name"]
        st = self._syslog_ts(ts)
        if a["os"][0] == "windows":
            kind = rng.choice(["logon", "logon", "service", "sca", "logoff"])
            user = rng.choice(WIN_USERS[1:])
            if kind == "logon":
                return self._alert(ts, aid, 60106, 3, "Windows logon success.", ["windows", "windows_security", "authentication_success"],
                                   "windows_eventchannel", "EventChannel", f"An account was successfully logged on. Account Name: {user} Logon Type: 3",
                                   data={"win": {"system": {"eventID": "4624", "computer": f"{host}.corp.local", "channel": "Security"},
                                                 "eventdata": {"targetUserName": user, "logonType": "3", "ipAddress": f"10.0.{rng.randint(1,7)}.{rng.randint(10,200)}"}},
                                         "dstuser": user},
                                   mitre_block=mitre(["T1078"], ["Defense Evasion", "Persistence", "Privilege Escalation", "Initial Access"], ["Valid Accounts"]))
            if kind == "logoff":
                return self._alert(ts, aid, 60137, 3, "Windows User Logoff.", ["windows", "windows_security"], "windows_eventchannel", "EventChannel",
                                   f"An account was logged off. Account Name: {user}", data={"win": {"system": {"eventID": "4634"}}, "dstuser": user})
            if kind == "service":
                return self._alert(ts, aid, 61104, 3, "Service startup type was changed.", ["windows", "windows_system"], "windows_eventchannel", "EventChannel",
                                   "The start type of the Background Intelligent Transfer Service service was changed.",
                                   data={"win": {"system": {"eventID": "7040", "channel": "System"}}})
            return self._alert(ts, aid, 19007, 7, "CIS Microsoft Windows Benchmark: Ensure 'Minimum password length' is set to '14 or more character(s)'.",
                               ["sca"], "sca", "sca", "SCA check failed", data={"sca": {"type": "check", "policy": "CIS Microsoft Windows Benchmark", "check": {"result": "failed", "id": "26012"}}},
                               compliance={"pci_dss": ["8.2.3"], "nist_800_53": ["IA.5"], "gdpr_IV": ["35.7.d"]})
        kind = rng.choice(["pam_open", "pam_close", "sudo", "cron", "dpkg", "ssh_ok_internal", "netstat", "sca", "pam_open", "pam_close"])
        user = rng.choice(["deploy", "ubuntu", "svc_backup", "jdoe"])
        if kind == "pam_open":
            return self._alert(ts, aid, 5501, 3, "PAM: Login session opened.", ["pam", "syslog", "authentication_success"], "pam", "/var/log/auth.log",
                               f"{st} {host} sshd[{rng.randint(1000,60000)}]: pam_unix(sshd:session): session opened for user {user}(uid=1001) by (uid=0)",
                               data={"dstuser": user, "uid": "0"}, mitre_block=mitre(["T1078"], ["Defense Evasion", "Persistence", "Privilege Escalation", "Initial Access"], ["Valid Accounts"]),
                               compliance={"pci_dss": ["10.2.5"], "gdpr": ["IV_32.2"], "nist_800_53": ["AU.14", "AC.7"]})
        if kind == "pam_close":
            return self._alert(ts, aid, 5502, 3, "PAM: Login session closed.", ["pam", "syslog"], "pam", "/var/log/auth.log",
                               f"{st} {host} sshd[{rng.randint(1000,60000)}]: pam_unix(sshd:session): session closed for user {user}", data={"dstuser": user})
        if kind == "sudo":
            cmd = rng.choice(["/usr/bin/systemctl restart nginx", "/usr/bin/apt update", "/usr/bin/journalctl -u kubelet", "/bin/cat /var/log/syslog"])
            return self._alert(ts, aid, 5402, 3, "Successful sudo to ROOT executed.", ["syslog", "sudo"], "sudo", "/var/log/auth.log",
                               f"{st} {host} sudo: {user} : TTY=pts/0 ; PWD=/home/{user} ; USER=root ; COMMAND={cmd}",
                               data={"srcuser": user, "dstuser": "root", "tty": "pts/0", "command": cmd},
                               mitre_block=mitre(["T1548.003"], ["Privilege Escalation", "Defense Evasion"], ["Sudo and Sudo Caching"]),
                               compliance={"pci_dss": ["10.2.5", "10.2.2"], "nist_800_53": ["AU.14", "AC.7", "AC.6"]})
        if kind == "cron":
            return self._alert(ts, aid, 2832, 5, "Crontab entry changed.", ["syslog", "cron"], "cron", "/var/log/syslog",
                               f"{st} {host} crontab[{rng.randint(1000,60000)}]: (root) LIST (root)", data={"srcuser": "root"})
        if kind == "dpkg":
            pkg = rng.choice(["libssl3", "curl", "tzdata", "python3-urllib3", "linux-libc-dev"])
            return self._alert(ts, aid, 2902, 7, "New dpkg (Debian Package) installed.", ["syslog", "dpkg", "config_changed"], "dpkg-decoder", "/var/log/dpkg.log",
                               f"{datetime.fromtimestamp(ts, tz=timezone.utc):%Y-%m-%d %H:%M:%S} status installed {pkg}:amd64 1.0",
                               data={"package": pkg, "arch": "amd64"}, compliance={"pci_dss": ["10.6.1"], "nist_800_53": ["AU.6"]})
        if kind == "ssh_ok_internal":
            src = f"10.0.0.{rng.choice([22, 22, 5])}"
            return self._alert(ts, aid, 5715, 3, "sshd: authentication success.", ["syslog", "sshd", "authentication_success"], "sshd", "/var/log/auth.log",
                               f"{st} {host} sshd[{rng.randint(1000,60000)}]: Accepted publickey for {user} from {src} port {rng.randint(30000,65000)} ssh2: ED25519 SHA256:x",
                               data={"srcip": src, "dstuser": user, "srcport": str(rng.randint(30000, 65000))},
                               mitre_block=mitre(["T1078", "T1021"], ["Defense Evasion", "Persistence", "Privilege Escalation", "Initial Access", "Lateral Movement"], ["Valid Accounts", "Remote Services"]),
                               compliance={"pci_dss": ["10.2.5"], "nist_800_53": ["AU.14", "AC.7"]})
        if kind == "netstat":
            return self._alert(ts, aid, 533, 7, "Listened ports status (netstat) changed (new port opened or closed).", ["ossec"], "ossec", "netstat listening ports",
                               "ossec: output: 'netstat listening ports':\ntcp 0.0.0.0:22 0.0.0.0:* 812/sshd", compliance={"pci_dss": ["10.2.7", "10.6.1"], "nist_800_53": ["AU.14", "AU.6"]})
        return self._alert(ts, aid, 19004, 7, "CIS Ubuntu Linux 22.04 LTS Benchmark: Ensure permissions on /etc/ssh/sshd_config are configured.",
                           ["sca"], "sca", "sca", "SCA check failed", data={"sca": {"type": "check", "policy": "CIS Ubuntu Linux 22.04 LTS Benchmark v1.0.0", "check": {"result": "failed", "id": "28570"}}},
                           compliance={"pci_dss": ["2.2"], "nist_800_53": ["CM.1"]})

    def ev_ssh_bruteforce(self, ts, success_chance=0.25):
        rng = self.rng
        src = rng.choice(SSH_ATTACKERS)
        target = rng.choice(["009", "011", "009", "001", "006", "013"])
        host = AGENTS_BY_ID[target]["name"]
        n = rng.randint(12, 45)
        out = []
        t = ts
        for i in range(n):
            t += rng.uniform(0.3, 4.0)
            user = rng.choice(BRUTE_USERNAMES)
            port = rng.randint(30000, 65000)
            st = self._syslog_ts(t)
            if rng.random() < 0.6:
                out.append(self._alert(t, target, 5710, 5, "sshd: Attempt to login using a non-existent user", ["syslog", "sshd", "authentication_failed", "invalid_login"],
                                       "sshd", "/var/log/auth.log", f"{st} {host} sshd[{rng.randint(1000,60000)}]: Invalid user {user} from {src} port {port}",
                                       data={"srcip": src, "srcuser": user, "srcport": str(port)},
                                       mitre_block=mitre(["T1110.001", "T1021.004"], ["Credential Access", "Lateral Movement"], ["Password Guessing", "SSH"]),
                                       compliance={"pci_dss": ["10.2.4", "10.2.5", "10.6.1"], "gdpr": ["IV_35.7.d", "IV_32.2"], "nist_800_53": ["AU.14", "AC.7", "AU.6"], "tsc": ["CC6.1", "CC6.8"]}))
            else:
                out.append(self._alert(t, target, 5760, 5, "sshd: authentication failed.", ["syslog", "sshd", "authentication_failed"],
                                       "sshd", "/var/log/auth.log", f"{st} {host} sshd[{rng.randint(1000,60000)}]: Failed password for root from {src} port {port} ssh2",
                                       data={"srcip": src, "dstuser": "root", "srcport": str(port)},
                                       mitre_block=mitre(["T1110.001", "T1021.004"], ["Credential Access", "Lateral Movement"], ["Password Guessing", "SSH"]),
                                       compliance={"pci_dss": ["10.2.4", "10.2.5"], "nist_800_53": ["AU.14", "AC.7"]}))
            if i in (8, 30):
                out.append(self._alert(t + 0.1, target, 5712, 10, "sshd: brute force trying to get access to the system. Non existent user.",
                                       ["syslog", "sshd", "authentication_failures", "invalid_login"], "sshd", "/var/log/auth.log",
                                       f"{st} {host} sshd[{rng.randint(1000,60000)}]: Invalid user {user} from {src} port {port}",
                                       data={"srcip": src, "srcuser": user, "srcport": str(port)},
                                       mitre_block=mitre(["T1110"], ["Credential Access"], ["Brute Force"]),
                                       compliance={"pci_dss": ["11.4", "10.2.4", "10.2.5"], "nist_800_53": ["SI.4", "AU.14", "AC.7"], "tsc": ["CC6.1", "CC6.8", "CC7.2", "CC7.3"]}))
        if src not in self.blocked_ips and rng.random() < success_chance:
            t += rng.uniform(1, 20)
            user = "deploy" if target in ("009", "011") else "ubuntu"
            port = rng.randint(30000, 65000)
            out.append(self._alert(t, target, 5715, 3, "sshd: authentication success.", ["syslog", "sshd", "authentication_success"], "sshd", "/var/log/auth.log",
                                   f"{self._syslog_ts(t)} {host} sshd[{rng.randint(1000,60000)}]: Accepted password for {user} from {src} port {port} ssh2",
                                   data={"srcip": src, "dstuser": user, "srcport": str(port)},
                                   mitre_block=mitre(["T1078", "T1021"], ["Defense Evasion", "Persistence", "Privilege Escalation", "Initial Access", "Lateral Movement"], ["Valid Accounts", "Remote Services"]),
                                   compliance={"pci_dss": ["10.2.5"], "nist_800_53": ["AU.14", "AC.7"]}))
            out.append(self._alert(t + 40, target, 40111, 10, "Multiple authentication failures followed by a success.", ["syslog", "attack", "authentication_success"],
                                   "sshd", "/var/log/auth.log", f"{self._syslog_ts(t + 40)} {host} sshd: Accepted password for {user} from {src} after repeated failures",
                                   data={"srcip": src, "dstuser": user},
                                   mitre_block=mitre(["T1110", "T1078"], ["Credential Access", "Initial Access"], ["Brute Force", "Valid Accounts"]),
                                   compliance={"pci_dss": ["10.2.4", "10.2.5", "11.4"], "nist_800_53": ["AU.14", "AC.7", "SI.4"]}))
        return out

    def ev_web_attack(self, ts):
        rng = self.rng
        src = rng.choice(WEB_ATTACKERS)
        target = rng.choice(["001", "002"])
        host = AGENTS_BY_ID[target]["name"]
        out = []
        t = ts
        payloads = [
            (31103, 7, "SQL injection attempt.", ["web", "accesslog", "attack", "sql_injection"], "/products.php?id=1%27%20UNION%20SELECT%20username,password%20FROM%20users--", 403),
            (31105, 6, "XSS (Cross Site Scripting) attempt.", ["web", "accesslog", "attack"], "/search?q=%3Cscript%3Ealert(document.cookie)%3C/script%3E", 403),
            (31104, 6, "Common web attack.", ["web", "accesslog", "attack"], "/index.php?page=../../../../etc/passwd", 404),
            (31101, 5, "Web server 400 error code.", ["web", "accesslog"], "/wp-login.php", 404),
            (31101, 5, "Web server 400 error code.", ["web", "accesslog"], "/.env", 404),
            (31101, 5, "Web server 400 error code.", ["web", "accesslog"], "/actuator/gateway/routes", 404),
        ]
        for _ in range(rng.randint(8, 30)):
            t += rng.uniform(0.2, 3)
            rid, lvl, desc, groups, url, code = rng.choice(payloads)
            ua = rng.choice(["sqlmap/1.8.3#stable (https://sqlmap.org)", "Mozilla/5.0 zgrab/0.x", "Nuclei - Open-source project (github.com/projectdiscovery/nuclei)", "python-requests/2.31.0"])
            log = f'{src} - - [{datetime.fromtimestamp(t, tz=timezone.utc):%d/%b/%Y:%H:%M:%S +0000}] "GET {url} HTTP/1.1" {code} 162 "-" "{ua}"'
            out.append(self._alert(t, target, rid, lvl, desc, groups, "web-accesslog", "/var/log/nginx/access.log", log,
                                   data={"srcip": src, "protocol": "GET", "url": url, "id": str(code)},
                                   mitre_block=mitre(["T1190"], ["Initial Access"], ["Exploit Public-Facing Application"]) if rid != 31101 else None,
                                   compliance={"pci_dss": ["6.5", "11.4"], "nist_800_53": ["SA.11", "SI.4"], "tsc": ["CC6.6", "CC7.1", "CC8.1"]}))
        out.append(self._alert(t + 1, target, 31151, 10, "Multiple web server 400 error codes", ["web", "accesslog", "web_scan", "recon"],
                               "web-accesslog", "/var/log/nginx/access.log", f'{src} - - "GET /.git/config HTTP/1.1" 404 162',
                               data={"srcip": src, "url": "/.git/config", "id": "404"},
                               mitre_block=mitre(["T1595.002"], ["Reconnaissance"], ["Vulnerability Scanning"]),
                               compliance={"pci_dss": ["6.5", "11.4"], "nist_800_53": ["SA.11", "SI.4"]}))
        if rng.random() < 0.35:
            url = "/products.php?id=1%27%20OR%20%271%27=%271"
            out.append(self._alert(t + 1.5, target, 31152, 10, "Multiple SQL injection attempts from same source ip.", ["web", "accesslog", "attack"],
                                   "web-accesslog", "/var/log/nginx/access.log",
                                   f'{src} - - [{datetime.fromtimestamp(t + 1.5, tz=timezone.utc):%d/%b/%Y:%H:%M:%S +0000}] "GET {url} HTTP/1.1" 500 312 "-" "sqlmap/1.8.3#stable"',
                                   data={"srcip": src, "protocol": "GET", "url": url, "id": "500"},
                                   mitre_block=mitre(["T1190"], ["Initial Access"], ["Exploit Public-Facing Application"]),
                                   compliance={"pci_dss": ["6.5", "11.4"], "nist_800_53": ["SA.11", "SI.4"]}))
            out.append(self._alert(t + 2, target, 31106, 6, "A web attack returned code 200 (success).", ["web", "accesslog", "attack"],
                                   "web-accesslog", "/var/log/nginx/access.log",
                                   f'{src} - - [{datetime.fromtimestamp(t + 2, tz=timezone.utc):%d/%b/%Y:%H:%M:%S +0000}] "GET {url} HTTP/1.1" 200 48211 "-" "sqlmap/1.8.3#stable"',
                                   data={"srcip": src, "protocol": "GET", "url": url, "id": "200"},
                                   mitre_block=mitre(["T1190"], ["Initial Access"], ["Exploit Public-Facing Application"]),
                                   compliance={"pci_dss": ["6.5", "11.4"], "nist_800_53": ["SA.11", "SI.4"]}))
        return out

    def ev_windows_auth(self, ts):
        rng = self.rng
        out = []
        t = ts
        src = rng.choice(["10.0.5.117", "10.0.7.44", "10.0.5.117", "193.35.18.49"])
        victim = rng.choice(["svc_sql", "Administrator", "a.smith", "helpdesk01"])
        for _ in range(rng.randint(8, 25)):
            t += rng.uniform(0.5, 6)
            out.append(self._alert(t, "004", 60122, 5, "Logon failure - Unknown user or bad password.", ["windows", "windows_security", "authentication_failed"],
                                   "windows_eventchannel", "EventChannel", f"An account failed to log on. Account Name: {victim} Failure Reason: Unknown user name or bad password. Source Network Address: {src}",
                                   data={"srcip": src, "dstuser": victim, "win": {"system": {"eventID": "4625", "computer": "dc-01.corp.local", "channel": "Security"},
                                                                                  "eventdata": {"targetUserName": victim, "ipAddress": src, "logonType": "3", "status": "0xc000006d", "subStatus": "0xc000006a"}}},
                                   mitre_block=mitre(["T1531"], ["Impact"], ["Account Access Removal"]),
                                   compliance={"pci_dss": ["10.2.4", "10.2.5"], "nist_800_53": ["AU.14", "AC.7"], "hipaa": ["164.312.b"]}))
        out.append(self._alert(t + 0.5, "004", 60204, 10, "Multiple Windows logon failures.", ["windows", "windows_security", "authentication_failures"],
                               "windows_eventchannel", "EventChannel", f"Multiple failed logons for {victim} from {src}",
                               data={"srcip": src, "dstuser": victim, "win": {"system": {"eventID": "4625"}, "eventdata": {"targetUserName": victim, "ipAddress": src}}},
                               mitre_block=mitre(["T1110"], ["Credential Access"], ["Brute Force"]),
                               compliance={"pci_dss": ["11.4", "10.2.4", "10.2.5"], "nist_800_53": ["SI.4", "AU.14", "AC.7"], "hipaa": ["164.312.b"]}))
        if rng.random() < 0.4:
            out.append(self._alert(t + 30, "004", 60106, 3, "Windows logon success.", ["windows", "windows_security", "authentication_success"],
                                   "windows_eventchannel", "EventChannel", f"An account was successfully logged on. Account Name: {victim} Source Network Address: {src}",
                                   data={"srcip": src, "dstuser": victim, "win": {"system": {"eventID": "4624"}, "eventdata": {"targetUserName": victim, "ipAddress": src, "logonType": "3"}}},
                                   mitre_block=mitre(["T1078"], ["Defense Evasion", "Persistence", "Privilege Escalation", "Initial Access"], ["Valid Accounts"])))
            out.append(self._alert(t + 31, "004", 67028, 3, "Special privileges assigned to new logon.", ["windows", "windows_security", "privilege_escalation"],
                                   "windows_eventchannel", "EventChannel", f"Special privileges assigned to new logon. Account Name: {victim} Privileges: SeDebugPrivilege SeBackupPrivilege",
                                   data={"dstuser": victim, "win": {"system": {"eventID": "4672"}, "eventdata": {"subjectUserName": victim, "privilegeList": "SeDebugPrivilege SeBackupPrivilege SeTcbPrivilege"}}},
                                   mitre_block=mitre(["T1078.002", "T1134"], ["Privilege Escalation", "Defense Evasion"], ["Domain Accounts", "Access Token Manipulation"])))
        return out

    def ev_fim(self, ts):
        rng = self.rng
        out = []
        choice = rng.choice(["passwd", "sshd", "startup", "cron"])
        if choice == "passwd":
            aid = rng.choice(["003", "011", "009"])
            path = rng.choice(["/etc/passwd", "/etc/shadow", "/etc/sudoers"])
            out.append(self._alert(ts, aid, 550, 7, "Integrity checksum changed.", ["ossec", "syscheck", "syscheck_entry_modified", "syscheck_file"], "syscheck_integrity_changed",
                                   "syscheck", f"File '{path}' modified\nMode: realtime\nChanged attributes: size,mtime,md5,sha1,sha256",
                                   mitre_block=mitre(["T1565.001", "T1098"], ["Impact", "Persistence"], ["Stored Data Manipulation", "Account Manipulation"]),
                                   compliance={"pci_dss": ["11.5"], "nist_800_53": ["SI.7"], "hipaa": ["164.312.c.1", "164.312.c.2"]},
                                   extra={"syscheck": {"path": path, "event": "modified", "mode": "realtime", "changed_attributes": ["size", "mtime", "md5", "sha1", "sha256"],
                                                       "uname_after": "root", "size_before": "2890", "size_after": "2951",
                                                       "sha256_after": "%064x" % rng.getrandbits(256)}}))
        elif choice == "sshd":
            aid = rng.choice(["001", "002", "006"])
            path = "/root/.ssh/authorized_keys"
            out.append(self._alert(ts, aid, 554, 5, "File added to the system.", ["ossec", "syscheck", "syscheck_entry_added", "syscheck_file"], "syscheck_new_entry",
                                   "syscheck", f"File '{path}' added\nMode: realtime",
                                   mitre_block=mitre(["T1098.004"], ["Persistence"], ["SSH Authorized Keys"]),
                                   compliance={"pci_dss": ["11.5"], "nist_800_53": ["SI.7"]},
                                   extra={"syscheck": {"path": path, "event": "added", "mode": "realtime", "uname_after": "root"}}))
        elif choice == "startup":
            path = r"c:\users\j.doe\appdata\roaming\microsoft\windows\start menu\programs\startup\invoice_0924.js"
            out.append(self._alert(ts, "005", 554, 5, "File added to the system.", ["ossec", "syscheck", "syscheck_entry_added", "syscheck_file"], "syscheck_new_entry",
                                   "syscheck", f"File '{path}' added\nMode: realtime",
                                   mitre_block=mitre(["T1547.001"], ["Persistence", "Privilege Escalation"], ["Registry Run Keys / Startup Folder"]),
                                   compliance={"pci_dss": ["11.5"], "nist_800_53": ["SI.7"]},
                                   extra={"syscheck": {"path": path, "event": "added", "mode": "realtime", "sha256_after": MALWARE_HASHES["invoice_0924.js"]}}))
        else:
            aid = rng.choice(["006", "007", "008"])
            path = "/etc/cron.d/.system-update"
            out.append(self._alert(ts, aid, 554, 5, "File added to the system.", ["ossec", "syscheck", "syscheck_entry_added", "syscheck_file"], "syscheck_new_entry",
                                   "syscheck", f"File '{path}' added\nMode: realtime",
                                   mitre_block=mitre(["T1053.003"], ["Execution", "Persistence", "Privilege Escalation"], ["Cron"]),
                                   compliance={"pci_dss": ["11.5"], "nist_800_53": ["SI.7"]},
                                   extra={"syscheck": {"path": path, "event": "added", "mode": "realtime"}}))
        return out

    def ev_miner(self, ts):
        out = []
        if 31337 not in self.processes["007"]:
            return out
        out.append(self._alert(ts, "007", 510, 7, "Host-based anomaly detection event (rootcheck).", ["ossec", "rootcheck"], "rootcheck", "rootcheck",
                               "Process '31337' hidden from /bin/ps. Possible kernel level rootkit.",
                               data={"title": "Process '31337' hidden from /bin/ps.", "file": "/proc/31337"},
                               mitre_block=mitre(["T1014"], ["Defense Evasion"], ["Rootkit"]),
                               compliance={"pci_dss": ["10.6.1"], "nist_800_53": ["AU.6"]}))
        out.append(self._alert(ts + 5, "007", 87105, 12, "VirusTotal: Alert - /tmp/.x/kworkerd - 58 engines detected this file", ["virustotal"], "json", "virustotal",
                               "VirusTotal: Alert - /tmp/.x/kworkerd - 58 engines detected this file",
                               data={"virustotal": {"found": "1", "malicious": "1", "positives": "58", "total": "72", "sha256": MALWARE_HASHES["kworkerd"],
                                                    "source": {"file": "/tmp/.x/kworkerd", "sha256": MALWARE_HASHES["kworkerd"]},
                                                    "permalink": "https://www.virustotal.com/gui/file/" + MALWARE_HASHES["kworkerd"]}, "integration": "virustotal"},
                               mitre_block=mitre(["T1496", "T1204.002"], ["Impact", "Execution"], ["Resource Hijacking", "Malicious File"]),
                               compliance={"pci_dss": ["10.6.1", "11.4"], "nist_800_53": ["AU.6", "SI.4"]}))
        out.append(self._alert(ts + 9, "007", 100105, 12, "Outbound connection to known cryptomining pool (custom rule).", ["network", "cryptomining", "attack"], "json", "/var/log/audit/audit.log",
                               "kworkerd (pid 31337) connected to 45.155.205.233:443 (pool.minexmr-proxy.net)",
                               data={"dstip": "45.155.205.233", "dstport": "443", "process": "kworkerd", "pid": "31337", "hostname": "pool.minexmr-proxy.net"},
                               mitre_block=mitre(["T1496", "T1071.001"], ["Impact", "Command and Control"], ["Resource Hijacking", "Web Protocols"])))
        return out

    def ev_beacon(self, ts):
        out = []
        if 6644 not in self.processes["005"] or "005" in self.isolated:
            return out
        out.append(self._alert(ts, "005", 100106, 12, "Rundll32 loading a DLL from a user-writable AppData directory (custom rule).", ["windows", "sysmon", "sysmon_event1", "attack"],
                               "windows_eventchannel", "EventChannel",
                               r'Process Create: Image: C:\Windows\System32\rundll32.exe CommandLine: rundll32.exe C:\Users\j.doe\AppData\Roaming\Microsoft\msupdate.dll,StartW',
                               data={"win": {"system": {"eventID": "1", "channel": "Microsoft-Windows-Sysmon/Operational"},
                                             "eventdata": {"image": r"C:\Windows\System32\rundll32.exe", "commandLine": r"rundll32.exe C:\Users\j.doe\AppData\Roaming\Microsoft\msupdate.dll,StartW",
                                                           "parentImage": r"C:\Windows\explorer.exe", "user": r"CORP\j.doe", "processId": "6644",
                                                           "hashes": "SHA256=" + MALWARE_HASHES["msupdate.dll"]}}},
                               mitre_block=mitre(["T1218.011"], ["Defense Evasion"], ["Rundll32"])))
        out.append(self._alert(ts + 60, "005", 100107, 12, "Suspicious periodic outbound HTTPS connection, possible C2 beacon (custom rule).", ["windows", "sysmon", "sysmon_event3", "attack"],
                               "windows_eventchannel", "EventChannel", "Network connection detected: rundll32.exe -> 179.43.180.10:443 (cdn-update-check.com)",
                               data={"dstip": "179.43.180.10", "dstport": "443", "win": {"system": {"eventID": "3"}, "eventdata": {"image": r"C:\Windows\System32\rundll32.exe",
                                                                                                                                 "destinationIp": "179.43.180.10", "destinationHostname": "cdn-update-check.com", "processId": "6644"}}},
                               mitre_block=mitre(["T1071.001", "T1573"], ["Command and Control"], ["Web Protocols", "Encrypted Channel"])))
        return out

    def ev_vuln_detector(self, ts):
        rng = self.rng
        aid = rng.choice([a["id"] for a in AGENTS if self.vulns.get(a["id"])])
        v = rng.choice(self.vulns[aid])
        sev = v["vulnerability"]["severity"]
        level = {"Critical": 13, "High": 10, "Medium": 7, "Low": 5}[sev]
        return [self._alert(ts, aid, 23506 if sev in ("Critical", "High") else 23505, level,
                            f"{v['vulnerability']['id']} affects {v['package']['name']}", ["vulnerability-detector"], "json", "vulnerability-detector",
                            f"{v['vulnerability']['id']} affects {v['package']['name']} {v['package']['version']}",
                            data={"vulnerability": {"cve": v["vulnerability"]["id"], "severity": sev, "cvss": {"cvss3": {"base_score": str(v["vulnerability"]["score"]["base"])}},
                                                    "package": {"name": v["package"]["name"], "version": v["package"]["version"]}, "reference": v["vulnerability"]["reference"]}},
                            compliance={"pci_dss": ["11.2.1", "11.2.3"], "nist_800_53": ["RA.5"], "tsc": ["CC7.1", "CC7.2"]})]

    # ------------------------------------------------------------ scheduling
    CAMPAIGNS = [("ev_ssh_bruteforce", 0.20), ("ev_web_attack", 0.18), ("ev_windows_auth", 0.12), ("ev_fim", 0.14),
                 ("ev_miner", 0.06), ("ev_beacon", 0.05), ("ev_vuln_detector", 0.25)]

    def _campaign(self, ts):
        r = self.rng.random()
        acc = 0.0
        for name, w in self.CAMPAIGNS:
            acc += w
            if r <= acc:
                return getattr(self, name)(ts)
        return []

    def _backfill(self, days: int):
        now = time.time()
        start = now - days * 86400
        rng = self.rng
        t = start
        hour = 3600
        while t < now - 60:
            dt = datetime.fromtimestamp(t, tz=timezone.utc)
            weekday = dt.weekday() < 5
            business = 7 <= dt.hour <= 19
            rate = (26 if business else 11) if weekday else (13 if business else 8)
            for _ in range(rate):
                self.ev_noise(t + rng.uniform(0, hour))
            campaigns = 2 if weekday else 1
            if rng.random() < 0.6:
                campaigns += 1
            for _ in range(campaigns):
                self._campaign(t + rng.uniform(0, hour))
            t += hour
        # keep ring sorted by time (campaign bursts can interleave)
        ordered = sorted(self.alerts, key=lambda a: a["_ts"])
        self.alerts.clear()
        self.alerts.extend(a for a in ordered if a["_ts"] <= now)
        self._log("INFO", "wazuh-analysisd", f"Backfilled {len(self.alerts)} alerts covering {days} days")

    def tick(self):
        """One live step: mostly noise, sometimes a campaign burst compressed into a few seconds."""
        with self.lock:
            now = time.time()
            if self.rng.random() < 0.10:
                burst = self._campaign(now)
                # compress burst timestamps so it doesn't land in the future
                if burst:
                    base = burst[0]["_ts"]
                    span = max(a["_ts"] for a in burst) - base or 1
                    for a in burst:
                        a["_ts"] = now - 5 + (a["_ts"] - base) / span * 5
                        a["timestamp"] = fmt_ts(a["_ts"])
            else:
                self.ev_noise(now)
            if self.rng.random() < 0.02:
                self._log("WARNING", "wazuh-remoted", "Agent key already in use: agent ID '012'")

    def _log(self, level, tag, msg):
        self.manager_logs.append({"timestamp": iso(time.time()), "tag": tag, "level": level.lower(), "description": msg})

    def active_response_alert(self, agent_id, command, srcip=None, extra_desc=""):
        rid, desc = {
            "firewall-drop": (651, "Host Blocked by firewall-drop Active Response"),
            "host-deny": (652, "Host Blocked by host-deny Active Response"),
            "host-isolation": (657, "Active response: host isolated"),
            "kill-process": (657, "Active response: process killed"),
            "disable-account": (657, "Active response: account disabled"),
            "quarantine-file": (657, "Active response: file quarantined"),
        }.get(command, (657, f"Active response: {command}"))
        data = {"srcip": srcip} if srcip else {}
        data["command"] = command
        return self._alert(time.time(), agent_id, rid, 3, desc + (f" ({extra_desc})" if extra_desc else ""), ["ossec", "active_response"], "ar_log_json",
                           "/var/ossec/logs/active-responses.log", f"active-response/bin/{command} add {srcip or ''} {extra_desc}".strip(), data=data)

    # -------------------------------------------------------------- queries
    def snapshot(self):
        with self.lock:
            return list(self.alerts)


def strip_private(alert: dict) -> dict:
    a = copy.deepcopy(alert)
    a.pop("_ts", None)
    return a


def parse_time(value: str | None, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    v = str(value).strip()
    now = time.time()
    if v == "now":
        return now
    if v.startswith("now-"):
        n, unit = v[4:-1], v[-1]
        mult = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}.get(unit)
        if mult and n.isdigit():
            return now - int(n) * mult
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
    except ValueError:
        raise ValueError(f"invalid timestamp '{value}' — use ISO 8601 or now-24h style")


RANGE_SECONDS = {"1h": 3600, "6h": 21600, "12h": 43200, "1d": 86400, "24h": 86400, "7d": 604800, "30d": 2592000}


def since_range(r: str | None, default="24h") -> float:
    return time.time() - RANGE_SECONDS.get(r or default, 86400)


def run_generator(env: Environment, stop: threading.Event, min_s=2.0, max_s=5.0):
    rng = random.Random()
    while not stop.wait(rng.uniform(min_s, max_s)):
        try:
            env.tick()
        except Exception as e:  # never let the generator die
            print(f"[mock-wazuh] generator error: {e}", flush=True)
