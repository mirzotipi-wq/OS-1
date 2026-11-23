# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-23
- **Branch:** `master`
- **Canonical Release Version:** `1.0-rc3` (`distro/VERSION`, Debian package version `1.0.0~rc3-1`)
- **Upstream Kernel Baseline:** Pinned, SHA-256-verified **Linux `6.12.119` LTS** (`6.12.119-os1`, zero `-rc` suffix)
- **Current Release Status:** **OS-1 1.0-rc3 — All 1.0 GA Software & Engineering Requirements Implemented (Awaiting Final CI Verification & Human/Hardware GA Sign-Off)**
- **Baseline Audit:** See [`docs/audits/PHASE16_BASELINE_AUDIT.md`](audits/PHASE16_BASELINE_AUDIT.md)

## Production Readiness Milestones (Phases 16–25)

- [x] **Phase 16 — CI Truthfulness & Test-Harness Repair:** Baseline audit, `ci-integrity-test.py`, bounded D-Bus/Wayland timeouts.
- [x] **Phase 17 — Firewall & Network-Security Correction:** Kernel `nf_tables`/`nft_compat`, `ufw.service`, behavioral QEMU traffic-probe test (`T17-FIREWALL`).
- [x] **Phase 18 — Installer Safety, Credential Handling & System Identity:** 13-stage Python `os1-install`, stdin/fd credentials, reserved-user/target-disk guards, live autologin/`os1` user removal.
- [x] **Phase 19 — Package Correctness & Package-Owned System Assembly:** Canonical `distro/VERSION`, 8 native `.deb` packages, `lintian` 0-error pass, authoritative `dpkg -i` assembly & `package-verify-test.py`.
- [x] **Phase 20 — Signed Updates, Versioned Kernel Packages & Rollback:** Signed APT repo, versioned `linux-image-os1-<krel>`, atomic `os1-update-boot`, `T20-UPDATE-ROLLBACK` QEMU test.
- [x] **Phase 21 — Installed Graphical Session, First-Boot State & Desktop Journeys:** `os1-shell-init`, `os1-firstboot`, `T21-INSTALLED-GUI` real SDDM graphical login as `alice`.
- [x] **Phase 22 — Stable LTS Kernel Baseline, Driver Coverage, Modules & Hardware Policy:** Pinned SHA-256-verified upstream **Linux `6.12.119` LTS** (`KERNEL_LTS.env`, zero `-rc` enforced), 80 audited symbols, Debian `non-free-firmware` + Intel/AMD CPU microcode preinstalled on Desktop ISO.
- [x] **Phase 23 — Reproducibility, Supply-Chain Security, SBOM & Release Engineering:** Byte-for-byte `.deb` reproducibility, CycloneDX 1.5 SBOM strict verification, `OS1_GPG_PRIVATE_KEY` CI signing, offline signing helper (`os1-sign-release.sh`), GitHub Pages signed APT repo deployment, and 1-step GA cutover (`os1-cutover-ga.sh`).
- [x] **Phase 24–25 — Production Desktop Hardening, Graphical Installer, LUKS2 Encryption & App Ecosystem:** AppArmor LSM + balanced `sysctl` hardening + `unattended-upgrades` + `zram` swap, PyQt5 graphical installer (`os1-install-gui`) wrapping `os1-install`, opt-in LUKS2 full-disk encryption + QEMU E2E test (`T25-LUKS`), Flatpak/Flathub + Plasma Discover, and MOK Secure Boot helper (`os1-mok-sign`).

## Gated Items Outside Automated CI (Before Running `os1-cutover-ga.sh` for `v1.0.0`)

- **Hardware-Gated:** Physical bare-metal x86-64 UEFI testing on Intel & AMD laptops/desktops (see [`docs/SUPPORTED_HARDWARE.md`](SUPPORTED_HARDWARE.md)).
- **Human / Legal-Gated:** Human accessibility usability review, human legal/trade-dress review, and production release GPG key custody (`OS1_GPG_PRIVATE_KEY` secret or offline `os1-sign-release.sh`).
