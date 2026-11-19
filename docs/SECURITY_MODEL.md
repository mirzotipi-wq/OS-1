# OS-1 Security Model

## 1. Host Firewall (Default-Deny Incoming)

- **Mechanism:** `ufw.service` backed by Linux kernel `nf_tables` (`iptables-nft`).
- **Default Policy:** Deny all unsolicited incoming connections (`DROP`); allow outgoing connections (`ACCEPT`) and established/related return traffic; allow loopback (`lo`).
- **Verification:** Enforced by mandatory runtime behavioral tests (`distro/tests/qemu-firewall-test.py` and `distro/tests/qemu-install-test.py`) verifying `systemctl is-active ufw.service`, active `nft list ruleset`, default incoming packet drop from an external peer, temporary allow, rule removal, and persistence across reboots.

## 2. Account & Privilege Model

- The `root` account password is locked by default (`passwd -l root`).
- Administrative actions require an explicitly created non-root administrator user in the `sudo` group authenticating with their password.
- No plaintext passwords are passed via command-line arguments, interpolated into shell source, or written to logs (enforced in Phase 18).

## 3. Package & Update Trust (Phase 20)

- OS-1 packages are distributed via a GPG-signed Debian APT repository (`InRelease` / `Release.gpg`).
- The public repository verification key is installed via `os1-keyring`; `trusted=yes` is forbidden in production configurations.
- Private signing keys are never committed to the repository.

## 4. Kernel & Runtime Isolation

- Kernel built with `CONFIG_SECCOMP=y`, `CONFIG_SECCOMP_FILTER=y`, full namespaces, and cgroups v2 for systemd service sandboxing.
- Software-verifiable security controls are tested in QEMU/OVMF; hardware-specific security features (Secure Boot enrollment, physical TPM2 measured boot) are documented as hardware-gated until verified on Tier 1 physical systems.
