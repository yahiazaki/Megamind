# Security — Supplement

> Added by Megamind. This is not from your original notes. It fills gaps and updates items that are commonly asked in SOC / pentest interviews. Edit or delete freely.

## OWASP Top 10 — 2025 update

Your notes follow the 2021 list. OWASP published the 2025 edition, which reorders and merges several categories:

| # | 2025 category | What changed vs 2021 |
|---|---|---|
| A01 | Broken Access Control | Still #1. SSRF (2021 A10) is now folded into this category. |
| A02 | Security Misconfiguration | Moved up from A05. |
| A03 | Software Supply Chain Failures | New. Expands "Vulnerable and Outdated Components" to the whole build/dependency/distribution chain. |
| A04 | Cryptographic Failures | Down from A02. |
| A05 | Injection | Down from A03 (SQLi, XSS, command injection...). |
| A06 | Insecure Design | Down from A04. |
| A07 | Authentication Failures | Renamed from "Identification and Authentication Failures". |
| A08 | Software or Data Integrity Failures | Same idea as 2021 A08. |
| A09 | Security Logging and Alerting Failures | Renamed: emphasis on alerting, not only logging. |
| A10 | Mishandling of Exceptional Conditions | New: error handling that fails open, leaks info, or crashes. |

## Cyber Kill Chain (Lockheed Martin)

Seven stages an attacker goes through. Defenders try to break the chain as early as possible.

1. **Reconnaissance** — gather info (OSINT, scanning, employee emails).
2. **Weaponization** — build the payload (exploit + backdoor, malicious document).
3. **Delivery** — send it (phishing email, USB, compromised website).
4. **Exploitation** — the vulnerability is triggered and code runs.
5. **Installation** — persistence is installed (backdoor, scheduled task, service).
6. **Command and Control (C2)** — the implant calls home for instructions.
7. **Actions on Objectives** — data theft, encryption (ransomware), lateral movement.

## MITRE ATT&CK

A knowledge base of real adversary behaviour, organised as a matrix:

- **Tactics** = the *why* (the goal of a step). Enterprise tactics: Reconnaissance, Resource Development, Initial Access, Execution, Persistence, Privilege Escalation, Defense Evasion, Credential Access, Discovery, Lateral Movement, Collection, Command and Control, Exfiltration, Impact.
- **Techniques / sub-techniques** = the *how* (e.g. T1566 Phishing, T1059 Command and Scripting Interpreter, T1003 OS Credential Dumping).
- **Procedures** = how a specific group actually implemented the technique.

SOC use: map alerts and detections to technique IDs, measure detection coverage, and describe incidents in a common language. Kill Chain = high-level phases; ATT&CK = detailed behaviours.

## Diamond Model of Intrusion Analysis

Every intrusion event has four connected vertices: **Adversary**, **Capability** (malware/tools), **Infrastructure** (IPs, domains, C2 servers), and **Victim**. Pivoting from one vertex reveals the others (e.g. a known C2 domain → other victims using the same infrastructure).

## Incident Response Lifecycle

**NIST SP 800-61** phases:

1. **Preparation** — policies, playbooks, tools, training, logging in place.
2. **Detection & Analysis** — triage alerts, determine scope and severity, collect evidence.
3. **Containment, Eradication & Recovery** — isolate hosts, remove malware/persistence, restore from clean backups, monitor.
4. **Post-Incident Activity** — lessons learned, update detections and playbooks.

**SANS (PICERL)** splits the same work into six steps: Preparation, Identification, Containment, Eradication, Recovery, Lessons Learned.

Order of volatility when collecting evidence (most volatile first): CPU registers/cache → RAM → network state/connections → running processes → disk → remote logs/backups.

## Windows Security Event IDs worth memorising

| Event ID | Meaning |
|---|---|
| 4624 | Successful logon (check Logon Type: 2 interactive, 3 network, 10 RDP) |
| 4625 | Failed logon (brute force indicator) |
| 4634 / 4647 | Logoff |
| 4648 | Logon with explicit credentials (runas, lateral movement) |
| 4672 | Special privileges assigned to new logon (admin logon) |
| 4688 | New process created (enable command-line auditing) |
| 4720 | User account created |
| 4728 / 4732 / 4756 | Member added to a security-enabled group |
| 4740 | Account locked out |
| 4768 / 4769 | Kerberos TGT / service ticket requested (Kerberoasting hunts on 4769) |
| 4776 | NTLM credential validation |
| 1102 | Security audit log cleared |
| 7045 | New service installed (System log, common persistence) |

## Network Penetration Testing — methodology outline

Your "Network Pen Testing" heading is still empty; this is a skeleton you can fill in.

1. **Pre-engagement** — written authorization, scope (IP ranges, exclusions), rules of engagement, testing windows.
2. **Reconnaissance** — passive (WHOIS, DNS, OSINT) then active host discovery: `nmap -sn 10.0.0.0/24`.
3. **Scanning & enumeration** — ports and services: `nmap -sC -sV -p- target`; UDP top ports `nmap -sU --top-ports 100`; enumerate SMB (`enum4linux-ng`, `smbclient -L`), SNMP (`snmpwalk`), LDAP, HTTP.
4. **Vulnerability analysis** — match versions to CVEs (searchsploit, Nessus/OpenVAS), check default credentials and misconfigurations.
5. **Exploitation** — gain a foothold (Metasploit, public exploits, credential attacks), staying in scope.
6. **Post-exploitation** — privilege escalation (linPEAS/winPEAS), credential harvesting, pivoting/lateral movement, proving impact.
7. **Reporting** — executive summary, findings with severity (CVSS), evidence, reproduction steps, remediation.

## CVSS in one paragraph

CVSS scores vulnerabilities 0.0–10.0. v3.1 base metrics: Attack Vector (Network/Adjacent/Local/Physical), Attack Complexity, Privileges Required, User Interaction, Scope, and impact on Confidentiality / Integrity / Availability. Ratings: 0.1–3.9 Low, 4.0–6.9 Medium, 7.0–8.9 High, 9.0–10.0 Critical. CVSS v4.0 (2023) adds supplemental metrics and splits Scope into vulnerable-system vs subsequent-system impact.
