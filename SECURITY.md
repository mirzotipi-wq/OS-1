# Security Policy

## Supported Versions

| Version | Security Support Status |
|---|---|
| `OS-1 1.0-rc2` (`master`) | Active release-candidate development and automated security qualification |
| Earlier `1.0-rc1` / pre-release snapshots | Unsupported — upgrade to `1.0-rc2` or latest `master` |

## Security Architecture

See [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) for OS-1's runtime security baseline:
- Active `ufw.service` (`nftables` backend) with default-deny inbound policy (`DROP`), verified behaviorally in CI.
- Locked `root` account (`passwd -l root`) with password-authenticated `sudo`.
- Credential-safe installer (`os1-install` accepts passwords only via `--password-stdin` or `--password-fd`, never on `argv` or interpolated into shell scripts).
- GPG-signed APT repository metadata (`InRelease` / `Release.gpg`) with verified keyring (`os1-keyring`).
- Redacted hardware diagnostic utility (`os1-hw-diag`) that strips MACs, IPs, SSIDs, UUIDs, and serial numbers.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for suspected security vulnerabilities (including installer privilege escalation, credential leakage, firewall bypass, package-signing flaws, or kernel vulnerabilities).

Instead:
1. Use GitHub's **Private Vulnerability Reporting** ("Security" → "Advisories" → "Report a vulnerability") on `mirzotipi-wq/OS-1`.
2. Include the affected component, OS-1 version (`cat /usr/share/os1/VERSION`), kernel release (`uname -r`), reproduction steps, and expected vs. observed impact.
3. For upstream Linux kernel vulnerabilities that are not OS-1-specific, also consult [`Documentation/process/security-bugs.rst`](Documentation/process/security-bugs.rst).
