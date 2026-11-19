# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Branch:** `master`
- **Last Fully CI-Tested Revision:** `45eea09537d5e93f7917ae8ef27ae9bd175dd1e4`
- **Canonical Release Version:** `1.0-rc2` (`distro/VERSION`, Debian package version `1.0.0~rc2-1`)
- **Upstream Kernel Baseline:** Linux `7.4.0-rc3` (`7.4.0-rc3-os1`) — release-candidate kernel; stable/LTS policy pending Phase 22
- **Current Release Status:** **In Progress — OS-1 1.0-rc2 Qualification (Phase 21: Installed Graphical Session, First-Boot State & Desktop Journeys)**
- **Baseline Audit:** See [`docs/audits/PHASE16_BASELINE_AUDIT.md`](audits/PHASE16_BASELINE_AUDIT.md)

## Latest Workflow Status (Commit `45eea0953`)

| Workflow | Latest Run ID | Status | Truthful Assessment |
|---|---|---|---|
| `phase1-kernel-boot.yml` | `44509746653` | `GREEN` | Verified QEMU serial boot of `7.4.0-rc3-os1` with `nf_tables`/`nft_compat`/modules enabled. |
| `phase2-userspace.yml` | `44509746630` | `GREEN` | Verified Debian 12 userspace, native `.deb` assembly, NetworkManager, APT, 2-boot persistence, and Phase 17 `T17-FIREWALL` behavioral traffic drop/allow/re-drop/loopback/outbound/reboot persistence. |
| `phase3-live-iso.yml` | `44509746842` | `GREEN` | Verified UEFI Live ISO + Recovery mode in OVMF. |
| `phase4-installer.yml` | `44509746767` | `RED` *(repaired in Phase 21 commit)* | `T4-INSTALL` PASSED; `T20-UPDATE-ROLLBACK` hit `#UD` in OVMF due to `-cpu qemu64` instead of KVM/`-cpu Haswell` (fixed). |
| `phase5-wayland-desktop.yml` | `44509746595` | `GREEN` | Verified KDE Plasma/KWin Wayland session, Light/Dark screenshots, `notify-send` D-Bus readiness, apps, audio, accessibility, and reboot persistence. |
| `phase14-15-release-qualification.yml` | `44509746584` | `RED` *(repaired in Phase 21 commit)* | `lintian` (0 errors) + `build-rootfs.sh` (`dpkg -i` + `dpkg -V`) PASSED; `package-verify-test.py` `dpkg -S /etc/os-release` needed multi-line `dpkg-divert` parsing (fixed). |

## Phases 16–24 Mission Tracker

- [x] **Phase 16 — CI Truthfulness & Test-Harness Repair (`54e10b3d2`):** Baseline audit written, `ci-integrity-test.py` enforced in `audit`, `os1-accessibility` DBus timeout bounded, `qemu-wayland-test.py` split into bounded steps with full failure diagnostics. Verified CI: `44501470669`, `44501470566`, `44501470642`, `44501470555`.
- [x] **Phase 17 — Firewall & Network-Security Correction (`962c03892`, `7ce4f62e9`):** Kernel `nf_tables`/`nft_compat`/`nf_conntrack`/xtables + modules enabled, `ufw.service` enabled on all profiles, behavioral QEMU traffic-probe test (`qemu-firewall-test.py`) passing on minimal (`44509746630`) and desktop (`44505854636`), `ADR-firewall-backend.md` & `docs/SECURITY_MODEL.md` published.
- [x] **Phase 18 — Installer Safety, Credential Handling & System Identity (`e0a0cab39`):** 13-stage Python `os1-install` with `--plan`/`--dry-run`/`--json-plan`, stdin/fd password handling (zero argv/shell interpolation), reserved-username & `/etc/passwd` rejection, target-disk guards, live SDDM `[Autologin]` & `os1` user cleanup, `installer-safety-test.py` (27/27 PASS), `docs/INSTALLER_SAFETY.md`, and QEMU special-char install passing on minimal (`44509746767`) and desktop (`44505854636`).
- [ ] **Phase 19 — Package Correctness & Package-Owned System Assembly:** Canonical `distro/VERSION`, 8 native `.deb` packages with FHS paths, `conffiles`, `md5sums`, `copyright`, `lintian` 0-error pass, authoritative `dpkg -i` assembly in `build-rootfs.sh`, and `package-verify-test.py` chroot lifecycle test *(diversion parsing fixed, awaiting CI verification)*.
- [ ] **Phase 20 — Signed Updates, Versioned Kernel Packages & Rollback:** Signed APT repo (`InRelease`/`Release.gpg`/`os1-archive-keyring.gpg`), versioned `linux-image-os1-<krel>` package with running-kernel removal guard, atomic `os1-update-boot` GRUB generator with previous-kernel retention, dynamic `BOOTX64.EFI` stub, and `T20-UPDATE-ROLLBACK` QEMU test *(CPU/KVM fixed, awaiting CI verification)*.
- [ ] **Phase 21 — Installed Graphical Session, First-Boot State & Desktop Journeys:** Idempotent `flock`-serialized `os1-shell-init` (atomic stamp only on full success), Python `os1-firstboot` preserving unspecified preferences + corrupt-state recovery, `firstboot-state-test.py`, and `T21-INSTALLED-GUI` (`qemu-installed-desktop-test.py`) qualifying real SDDM graphical login as installer-created user `alice` *(awaiting CI verification)*.
- [ ] **Phase 22 — Stable Kernel Baseline, Driver Coverage, Modules & Hardware Policy:** Pending.
- [ ] **Phase 23 — Reproducibility, Supply-Chain Security, SBOM & Release Engineering:** Pending.
- [ ] **Phase 24 — Full OS-1 1.0-rc2 Release Qualification:** Pending.

## Gated Items Outside Automated CI

- **Hardware-Gated:** Physical bare-metal x86-64 UEFI testing (Intel/AMD GPU acceleration, Wi-Fi, Bluetooth, audio, webcam, touchpad, external display, suspend/resume, battery, bare-metal update/rollback).
- **Human / Legal-Gated:** Human accessibility usability review, human legal/trade-dress review, and production release GPG key custody.
