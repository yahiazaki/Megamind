# Networks — Supplement

> Added by Megamind. This is not from your original notes. Quick-reference tables plus Spanning Tree Protocol, which the notes don't cover.

## OSI vs TCP/IP at a glance

| OSI layer | TCP/IP layer | PDU | Devices | Example protocols |
|---|---|---|---|---|
| 7 Application | Application | Data | — | HTTP, DNS, SMTP, FTP, SSH |
| 6 Presentation | Application | Data | — | TLS (encryption), JPEG, ASCII |
| 5 Session | Application | Data | — | NetBIOS, RPC, session setup |
| 4 Transport | Transport | Segment (TCP) / Datagram (UDP) | Firewall (L4) | TCP, UDP |
| 3 Network | Internet | Packet | Router, L3 switch | IPv4, IPv6, ICMP, OSPF |
| 2 Data Link | Network Access | Frame | Switch, bridge, AP | Ethernet, 802.11, ARP*, STP |
| 1 Physical | Network Access | Bits | Hub, repeater, cable | 1000BASE-T, fibre |

*ARP sits between L2 and L3: it maps an IP address to a MAC address.

Memory aid (7→1): **A**ll **P**eople **S**eem **T**o **N**eed **D**ata **P**rocessing.

## Subnetting cheat sheet (IPv4)

| CIDR | Mask | Addresses | Usable hosts |
|---|---|---|---|
| /24 | 255.255.255.0 | 256 | 254 |
| /25 | 255.255.255.128 | 128 | 126 |
| /26 | 255.255.255.192 | 64 | 62 |
| /27 | 255.255.255.224 | 32 | 30 |
| /28 | 255.255.255.240 | 16 | 14 |
| /29 | 255.255.255.248 | 8 | 6 |
| /30 | 255.255.255.252 | 4 | 2 (point-to-point links) |
| /31 | 255.255.255.254 | 2 | 2 (RFC 3021 point-to-point only) |
| /16 | 255.255.0.0 | 65,536 | 65,534 |

- Usable hosts = 2^(32 − prefix) − 2 (network + broadcast addresses are reserved).
- **Block size** trick: 256 − last non-255 mask octet. For /26 the mask ends in 192, so block = 64 and subnets start at .0, .64, .128, .192.
- Worked example — 192.168.10.77/27: block 32 → subnet 192.168.10.64, hosts .65–.94, broadcast .95.

**Private ranges (RFC 1918):** 10.0.0.0/8, 172.16.0.0/12 (172.16–172.31), 192.168.0.0/16.
**Other special ranges:** 127.0.0.0/8 loopback, 169.254.0.0/16 APIPA/link-local (DHCP failed), 100.64.0.0/10 carrier-grade NAT.

## Common ports

| Port | Protocol | Port | Protocol |
|---|---|---|---|
| 20/21 TCP | FTP data/control | 389 TCP | LDAP |
| 22 TCP | SSH / SFTP / SCP | 443 TCP | HTTPS |
| 23 TCP | Telnet | 445 TCP | SMB |
| 25 TCP | SMTP | 465/587 TCP | SMTP over TLS / submission |
| 53 TCP/UDP | DNS | 636 TCP | LDAPS |
| 67/68 UDP | DHCP server/client | 993 / 995 TCP | IMAPS / POP3S |
| 69 UDP | TFTP | 1433 TCP | MS SQL Server |
| 80 TCP | HTTP | 3306 TCP | MySQL |
| 88 TCP/UDP | Kerberos | 3389 TCP | RDP |
| 110 TCP | POP3 | 5432 TCP | PostgreSQL |
| 123 UDP | NTP | 5900 TCP | VNC |
| 143 TCP | IMAP | 6379 TCP | Redis |
| 161/162 UDP | SNMP / SNMP trap | 8080 TCP | HTTP alternate / proxies |
| 514 UDP | Syslog | 27017 TCP | MongoDB |

Ranges: 0–1023 well-known, 1024–49151 registered, 49152–65535 dynamic/ephemeral.

## Spanning Tree Protocol (STP, IEEE 802.1D)

**Problem:** redundant links between switches create Layer-2 loops. Ethernet frames have no TTL, so broadcasts loop forever (a *broadcast storm*), MAC tables flap, and the network goes down.

**Solution:** STP logically blocks some ports so exactly one loop-free path exists, while keeping the redundant links ready as backups.

How the tree is built:

1. **Elect the Root Bridge** — the switch with the lowest Bridge ID (priority, default 32768, + MAC address). Lower priority wins; lowest MAC breaks ties.
2. **Root Port** on every non-root switch — the port with the lowest path cost to the root (cost by speed: 10 Mbps = 100, 100 Mbps = 19, 1 Gbps = 4, 10 Gbps = 2).
3. **Designated Port** on every segment — the port closest to the root on that link forwards.
4. All other ports become **Blocking** (alternate).

Switches exchange **BPDUs** (Bridge Protocol Data Units) every 2 s to elect the root and detect failures.

Port states in classic STP: Blocking → Listening (15 s) → Learning (15 s) → Forwarding. Convergence can take 30–50 s.

**Rapid STP (802.1w)** converges in about a second using port roles Root / Designated / Alternate / Backup. **PVST+ / Rapid-PVST+** (Cisco) run one tree per VLAN.

Security features: **PortFast** (skip listening/learning on access ports to end devices), **BPDU Guard** (shut down a PortFast port that receives a BPDU, stopping rogue switches), **Root Guard** (stop a port from becoming a path to a new root). An attacker who sends superior BPDUs can become the root bridge and sit in the middle of traffic, which is why BPDU Guard matters.
