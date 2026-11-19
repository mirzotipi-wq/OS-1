# OS-1 Live Project Status & Acceptance Scorecard

- **Last Updated (UTC):** 2026-11-19
- **Branch:** `master`
- **Last Fully CI-Tested Revision:** `e0a0cab393139fc83405fe1189b4b85e42be5d4c`
- **Canonical Release Version:** `1.0-rc2` (`distro/VERSION`, Debian package version `1.0.0~rc2-1`)
- **Upstream Kernel Baseline:** Linux `7.4.0-rc3` (`7.4.0-rc3-os1`) — release-candidate kernel; stable/LTS policy pending Phase 22
- **Current Release Status:** **In Progress — OS-1 1.0-rc2 Qualification (Phase 19: Package Correctness & Package-Owned System Assembly)**
- **Baseline Audit:** See [`docs/audits/PHASE16_BASELINE_AUDIT.md`](audits/PHASE16_BASELINE_AUDIT.md)

## Latest Workflow Status (Commit `e0a0cab39`)

| Workflow | Latest Run ID | Status | Truthful Assessment |
|---|---|---|---|
| `phase1-kernel-boot.yml` | `44505854873` | `GREEN` | Verified QEMU serial boot of `7.4.0-rc3-os1` with `nf_tables`/`nft_compat`/modules enabled. |
| `phase2-userspace.yml` | `44505854846` | `GREEN` | Verified Debian 12 userspace, NetworkManager, APT, 2-boot persistence, and Phase 17 `T17-FIREWALL` behavioral traffic drop/allow/re-drop/loopback/outbound/reboot persistence. |
| `phase3-live-iso.yml` | `44505854776` | `GREEN` | Verified UEFI Live ISO + Recovery mode in OVMF. |
| `phase4-installer.yml` | `44505854820` | `GREEN` | Verified Phase 18 credential-safe installer (`--password-stdin`, special-character password `O'Brien $100 "safe" & clean!`, zero log leakage, reserved username rejection, live user + SDDM `[Autologin]` removal, 2 reboots, active UFW/nftables). |
| `phase5-wayland-desktop.yml` | `44505854922` | `RED` *(repaired in Phase 19)* | Passed `54e10b3d2` (`44501470555`), timed out on `NOTIFY` on `e0a0cab39` because `notify-send` raced with `plasmashell` re-registering `org.freedesktop.Notifications` after `os1-shell-init`; bounded D-Bus wait added in Phase 19. |
| `phase14-15-release-qualification.yml` | `44505854636` | `GREEN` | Verified native `.deb`s, Full Desktop UEFI Live ISO, `T17-FIREWALL`, SBOM, ISO boot + Recovery, and Phase 18 Desktop clean-install + 2 reboots + active UFW/nftables/Orca/fs. |

## Phases 16–24 Mission Tracker

- [x] **Phase 16 — CI Truthfulness & Test-Harness Repair (`54e10b3d2`):** Baseline audit written, `ci-integrity-test.py` enforced in `audit`, `os1-accessibility` DBus timeout bounded, `qemu-wayland-test.py` split into bounded steps with full failure diagnostics. Verified CI: `44501470669`, `44501470566`, `44501470642`, `44501470555`.
- [x] **Phase 17 — Firewall & Network-Security Correction (`962c03892`, `7ce4f62e9`):** Kernel `nf_tables`/`nft_compat`/`nf_conntrack`/xtables + modules enabled, `ufw.service` enabled on all profiles, behavioral QEMU traffic-probe test (`qemu-firewall-test.py`) passing on minimal (`44505854846`) and desktop (`44505854636`), `ADR-firewall-backend.md` & `docs/SECURITY_MODEL.md` published.
- [x] **Phase 18 — Installer Safety, Credential Handling & System Identity (`e0a0cab39`):** 13-stage Python `os1-install` with `--plan`/`--dry-run`/`--json-plan`, stdin/fd password handling (zero argv/shell interpolation), reserved-username & `/etc/passwd` rejection, target-disk guards, live SDDM `[Autologin]` & `os1` user cleanup, `installer-safety-test.py` (27/27 PASS), `docs/INSTALLER_SAFETY.md`, and QEMU special-char install passing on minimal (`44505854820`) and desktop (`44505854636`).
- [ ] **Phase 19 — Package Correctness & Package-Owned System Assembly:** Canonical `distro/VERSION`, 8 native `.deb` packages (`os1-release`, `os1-keyring`, `os1-branding`, `os1-shell`, `os1-firstboot`, `os1-installer`, `os1-tools`, `os1-desktop-meta`) with proper FHS `/usr/share` & `/usr/bin`/`/usr/sbin` paths, `conffiles`, `md5sums`, `copyright`, authoritative `dpkg -i` assembly in `build-rootfs.sh`, and `package-verify-test.py` + `lintian` + chroot lifecycle tests. *(Awaiting CI verification)*
- [ ] **Phase 20 — Signed Updates, Versioned Kernel Packages & Rollback:** Pending.
- [ ] **Phase 21 — Installed Graphical Session, First-Boot State & Desktop Journeys:** Pending.
- [ ] **Phase 22 — Stable Kernel Baseline, Driver Coverage, Modules & Hardware Policy:** Pending.
- [ ] **Phase 23 — Reproducibility, Supply-Chain Security, SBOM & Release Engineering:** Pending.
- [ ] **Phase 24 — Full OS-1 1.0-rc2 Release Qualification:** Pending.

## Gated Items Outside Automated CI

- **Hardware-Gated:** Physical bare-metal x86-64 UEFI testing (Intel/AMD GPU acceleration, Wi-Fi, Bluetooth, audio, webcam, touchpad, external display, suspend/resume, battery, bare-metal update/rollback).
- **Human / Legal-Gated:** Human accessibility usability review, human legal/trade-dress review, and production release GPG key custody.
