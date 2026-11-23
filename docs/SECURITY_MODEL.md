# OS-1 Security Model

## 1. Host Firewall (Default-Deny Incoming)

- **Mechanism:** `ufw.service` backed by Linux kernel `nf_tables` (`iptables-nft`).
- **Default Policy:** Deny all unsolicited incoming connections (`DROP`); allow outgoing connections (`ACCEPT`) and established/related return traffic; allow loopback (`lo`).
- **Verification:** Enforced by mandatory runtime behavioral tests (`distro/tests/qemu-firewall-test.py` and `distro/tests/qemu-install-test.py`) verifying `systemctl is-active ufw.service`, active `nft list ruleset`, default incoming packet drop from an external peer, temporary allow, rule removal, and persistence across reboots.

## 2. Mandatory Access Control (AppArmor) & Kernel Hardening

- **AppArmor LSM:** Compiled into the OS-1 Linux LTS kernel (`CONFIG_SECURITY_APPARMOR=y`, `CONFIG_DEFAULT_SECURITY_APPARMOR=y`), activated via `apparmor=1 security=apparmor`, and backed by `apparmor`, `apparmor-utils`, and `apparmor-profiles` on desktop images.
- **Kernel Hardening:** Built with `CONFIG_SECCOMP=y`, `CONFIG_SECCOMP_FILTER=y`, `CONFIG_SECURITY_YAMA=y`, `CONFIG_HARDENED_USERCOPY=y`, `CONFIG_FORTIFY_SOURCE=y`, `CONFIG_STRICT_KERNEL_RWX=y`, `CONFIG_STRICT_MODULE_RWX=y`, `CONFIG_STACKPROTECTOR_STRONG=y`, `CONFIG_RANDOMIZE_BASE=y`, and `CONFIG_INIT_ON_ALLOC_DEFAULT_ON=y`.
- **Sysctl Hardening (`/etc/sysctl.d/90-os1-hardening.conf`, owned by `os1-release`):** Enforces `kernel.kptr_restrict=2`, `kernel.dmesg_restrict=1`, `kernel.yama.ptrace_scope=1`, `kernel.unprivileged_bpf_disabled=1`, `kernel.kexec_load_disabled=1`, protected links/FIFOs/regular files, `fs.suid_dumpable=0`, reverse-path filtering, ICMP redirect rejection, and TCP SYN cookies.

## 3. Full-Disk Encryption (LUKS2)

- **Opt-In LUKS2 Encryption:** Both `os1-install --encrypt` and the PyQt5 graphical wizard (`os1-install-gui`) support LUKS2 full-disk encryption (GPT `ESP` + unencrypted ext4 `/boot` + LUKS2 `dm-crypt` ext4 root).
- **Credential Safety:** Passphrases are passed strictly via private file descriptors (`--luks-passphrase-fd` / `--luks-passphrase-stdin`), never via command-line arguments or logs.
- **Early Boot Unlock:** `os1-build-luks-initramfs` produces a deterministic unlock initramfs (`/boot/initrd.img-os1-luks`) verified end-to-end in QEMU/OVMF (`distro/tests/qemu-luks-install-test.py`).

## 4. Account & Privilege Model

- The `root` account password is locked by default (`passwd -l root`).
- Administrative actions require an explicitly created non-root administrator user in the `sudo` group authenticating with their password (no passwordless `sudo` on installed systems).
- No plaintext passwords or encryption passphrases are passed via command-line arguments, interpolated into shell source, or written to logs.

## 5. Package Trust & Automatic Security Updates

- OS-1 packages and versioned LTS kernels are distributed via a GPG-signed Debian APT repository (`InRelease` / `Release.gpg`), published to GitHub Pages (`https://mirzotipi-wq.github.io/OS-1/apt`) on tagged releases.
- The public repository verification key is installed via `os1-keyring`; `trusted=yes` is forbidden in production configurations.
- `unattended-upgrades` is preconfigured (`/etc/apt/apt.conf.d/20auto-upgrades` and `50unattended-upgrades-os1`) to apply Debian security updates and signed OS-1 updates automatically without forcing automatic reboots.
- Production release signing supports `OS1_GPG_PRIVATE_KEY` / `OS1_GPG_PASSPHRASE` in CI or air-gapped offline signing via `distro/tools/os1-sign-release.sh`. Private signing keys are never committed to the repository.

## 6. UEFI Secure Boot (MOK Tooling)

- `OS-1 1.0` targets standard UEFI GPT boot (Secure Boot disabled in firmware) because OS-1 ships a custom-built upstream Linux LTS kernel rather than a Microsoft-signed shim chain.
- Users who wish to enable Secure Boot with OS-1's custom kernel can generate, enroll, and sign kernels/EFI binaries using their own local Machine Owner Key via `sudo os1-mok-sign` (`sbsigntool` + `mokutil`).
