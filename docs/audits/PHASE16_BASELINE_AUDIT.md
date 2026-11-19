# OS-1 Phase 16 Baseline Forensic Audit

- **Audit Date (UTC):** 2026-11-19
- **Repository:** `https://github.com/mirzotipi-wq/OS-1.git`
- **Audited Branch / Commit:** `master` @ `391fe7dc64480a821859b420050790b298fb59f8`
- **Last CI-Tested Commit:** `6a8fdcfe2c138eef708ba46f56c1b2136b5d9e8b` (commit `391fe7dc6` used `[skip ci]`)
- **Kernel Source Version:** Linux `7.4.0-rc3` (`VERSION=7`, `PATCHLEVEL=4`, `SUBLEVEL=0`, `EXTRAVERSION=-rc3`, `NAME=Baby Opossum Posse`), built as `7.4.0-rc3-os1`
- **Debian Userspace Base:** Debian 12 (`bookworm`, unpinned moving `http://deb.debian.org/debian`)
- **Open Pull Requests:** None
- **GitHub Releases / Tags:** None
- **Active Workflows:**
  1. `phase1-kernel-boot.yml` (Run `44493992761`: `success`)
  2. `phase2-userspace.yml` (Run `44493992931`: `success`)
  3. `phase3-live-iso.yml` (Run `44493992785`: `success`)
  4. `phase4-installer.yml` (Run `44493992839`: `success`)
  5. `phase5-wayland-desktop.yml` (Run `44493993181`: **`failure`**)
  6. `phase14-15-release-qualification.yml` (Run `44493992921`: `success` — with hidden `ufw.service` failure)

---

## 1. Verified Working Behavior (QEMU/OVMF x86-64 Only)

- **Kernel build & serial boot (`Phase 1`):** Out-of-tree `x86_64` build of `7.4.0-rc3-os1` boots in QEMU with minimal BusyBox initramfs, zero kernel panic.
- **Debian `bookworm` userspace & persistence (`Phase 2`):** `mmdebstrap` rootfs boots via systemd, non-root `os1` serial login, NetworkManager DHCPv4, live `apt-get`, and 2-boot persistence pass.
- **UEFI Live ISO & Recovery Mode (`Phase 3`):** `xorriso` + standalone `BOOTX64.EFI` + SquashFS/OverlayFS boots via OVMF UEFI in Live and Recovery modes.
- **Basic clean-disk UEFI install (`Phase 4`):** `os1-install` partitions a blank QEMU virtio disk (GPT + 256 MiB FAT32 ESP + ext4 root), installs standalone GRUB, boots detached from ISO, and persists across 2 reboots via serial login.
- **Original OS-1 visual assets:** `distro/branding/generate-assets.py` deterministically generates original wallpapers, logo SVG, and `OS1Sequoia` Aurorae theme with zero proprietary Apple assets.
- **Filesystem operations test (`os1-fs-test`):** Create/copy/move/rename, FreeDesktop Trash move/restore, symlinks, Unicode filenames, 16 MiB SHA-256 integrity, and `EACCES` handling pass inside the guest.

---

## 2. Verified Defects (Reproduced Against Code & CI Evidence)

| ID | Severity | Component | Evidence | Root Cause | Target Phase |
|---|---|---|---|---|---|
| `D-01` | **Critical** | `phase5-wayland-desktop.yml` / `qemu-wayland-test.py` | CI run `44493993181` failed with `TimeoutError: Timed out after 30.0s waiting for 'CONTROLS_A11Y_RC='`. Serial log shows `kwin_wayland[416]: segfault ... in libQt5Gui.so.5.15.8` during `SHELL_LAYOUT`, followed by hang in `CONTROLS_A11Y`. | 6 commands chained under a single 30s timeout; `XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS` only passed to `notify-send` (not `os1-accessibility`); `os1-accessibility` runs unbounded `qdbus org.kde.KWin /KWin reconfigure` (25s DBus timeout per call); zero failure diagnostics captured. | Phase 16 / 21 |
| `D-02` | **Critical** | `ufw.service` / kernel netfilter | `qemu-phase4-installed-boot1.log:691` shows `[FAILED] Failed to start ufw.service - Uncomplicated firewall.` Yet `phase14-15-release-qualification.yml` (`44493992921`) passed! | `distro/kernel/os1_x86_64.fragment` omits `CONFIG_NETFILTER`, `CONFIG_NF_TABLES`, `CONFIG_NF_CONNTRACK`, IPv4/IPv6 nftables/xtables rules. `qemu-install-test.py:265-266` only greps `/etc/ufw/ufw.conf` and `/etc/default/ufw` instead of testing runtime firewall state or traffic. | Phase 16 / 17 |
| `D-03` | **Critical** | `distro/installer/os1-install:197` | Direct code inspection: `chroot ... bash -euo pipefail -c "... echo '${USERNAME}:${PASSWORD}' | chpasswd ..."` | Plaintext password is interpolated into single-quoted shell source inside double-quoted `bash -c` AFTER destructive `parted`/`mkfs`. Any apostrophe (`'`), `$`, or `"` breaks install or injects shell commands; `--password` also exposes credentials in `argv`. | Phase 18 |
| `D-04` | **High** | `distro/installer/os1-install:67` | Regex `^[a-z_][a-z0-9_-]{0,31}$` accepts `root`, `daemon`, `sddm`, `nobody`, `os1`, and existing service accounts. | Missing reserved-account and `/etc/passwd` collision checks. | Phase 18 |
| `D-05` | **High** | `distro/installer/os1-install:62-115` | Only checks `[ -b "$DISK" ]` and live media files before `parted mklabel gpt`. | Missing preflight checks for whole-disk vs partition, mounted filesystems, active root/live disk, read-only status, minimum disk size, and target stability. | Phase 18 |
| `D-06` | **High** | `distro/packages/build-debs.sh:31` | Reproduced locally via `dpkg-deb --contents os1-branding_1.0.0_all.deb`: installs `./aurorae/`, `./icons/`, `./pixmaps/`, `./wallpapers/` at filesystem root `/`! | Passes `"${BRAND_ROOT}"` instead of `"${BRAND_ROOT}/usr/share"` to `generate-assets.py`. | Phase 19 |
| `D-07` | **High** | `distro/build/build-rootfs.sh:331-378` | Direct code inspection: `build-rootfs.sh` runs `generate-assets.py` and `install` directly into `${ROOTFS_DIR}` instead of installing the built `.deb` packages. | Split assembly path: ISO/rootfs files are not owned by `dpkg` and diverge from end-user `.deb` packages. | Phase 19 |
| `D-08` | **High** | `distro/packages/build-debs.sh` | `Release` is unsigned (no `InRelease` / `Release.gpg`, no `os1-keyring`). | No signed APT update lifecycle or signature-rejection verification. | Phase 20 |
| `D-09` | **High** | `distro/installer/os1-install:147-148` | Copies kernel to fixed `/boot/vmlinuz-os1` and `/boot/efi/EFI/os1/vmlinuz-os1`. | No versioned kernel `.deb` package, no previous-kernel retention, no boot rollback mechanism. | Phase 20 |
| `D-10` | **High** | `distro/kernel/os1_x86_64.fragment` | Direct inspection: lacks `CONFIG_DRM_AMDGPU`, `CONFIG_IWLWIFI`, `CONFIG_DRM_I915`, Realtek/Intel NICs, HDA audio, USB HID/Bluetooth/UVC, ACPI battery/backlight, netfilter/nftables. | Fragment was scoped only to minimal QEMU virtio bring-up. | Phase 17 / 22 |
| `D-11` | **High** | `distro/kernel/build-kernel.sh:14` | `BUILD_MODULES=0` by default; workflows run `./distro/tools/os1.sh kernel` without `--with-modules`. | Kernel modules are not built, packaged, or installed consistently. | Phase 17 / 20 / 22 |
| `D-12` | **High** | `distro/installer/os1-install:198-200` & `build-rootfs.sh:287-295` | `build-rootfs.sh` writes `[Autologin] User=os1` into `/etc/sddm.conf.d/10-os1-wayland.conf`; `os1-install` deletes user `os1` (`userdel -r os1`) without removing live autologin. Also `os1-install:156` hardcodes `PRETTY_NAME="OS-1 0.4-dev (Installed)"`. | Live-session SDDM autologin leaks into installed system referencing a deleted account; version metadata diverges. | Phase 18 / 19 |
| `D-13` | **High** | `distro/tests/qemu-install-test.py` | Only logs in via `ttyS0` serial console (`vm_inst1.login(...)`). | Never verifies installed graphical login (SDDM -> Wayland -> Plasma) as the newly created user. | Phase 21 |
| `D-14` | **Medium** | `distro/shell/bin/os1-shell-init:23-34` | Every command ends with `|| true` and line 34 unconditionally runs `touch "${STAMP}"`. | Partial or total initialization failure is silently hidden and permanently blocks retries. | Phase 21 |
| `D-15` | **Medium** | `distro/installer/os1-firstboot:72-77` | Unconditionally writes `appearance=${APPEARANCE:-light}`, `reduced_motion=${REDUCED_MOTION:-off}`, `reduced_transparency=${REDUCED_TRANSPARENCY:-off}`. | Changing one preference clobbers all unspecified previously saved preferences. | Phase 21 |
| `D-16` | **High** | `.github/workflows/*.yml` | Cache key is `os1-kernel-x86_64-${{ hashFiles('Makefile', 'distro/kernel/os1_x86_64.fragment', 'distro/kernel/build-kernel.sh') }}`. | Does not include kernel source tree commit or compiler version; stale `bzImage` can be restored across kernel source changes. | Phase 23 |
| `D-17` | **Medium** | `distro/build/generate-sbom.py:48` | Verified in `os1-sbom.cdx.json` from run `44493992921`: `"os1:bzImage_sha256": "unknown"`. | Reads `kp.get("bzImage_sha256")` instead of `kp["artifacts"]["bzImage"]["sha256"]`. | Phase 23 |
| `D-18` | **Medium** | `.github/workflows/phase14-15-release-qualification.yml` | Only uploads 7-day ephemeral workflow artifacts (metadata + logs, not even the ISO or `.deb`s). | No durable GitHub Release asset publication tied to the exact qualified ISO/packages. | Phase 23 / 24 |
| `D-19` | **Low** | Repository root | Only upstream Linux `README` exists; no `README.md` presenting OS-1. | Repository appears to be a bare Linux kernel mirror on GitHub. | Phase 23 |
| `D-20` | **Medium** | `docs/STATUS.md`, `docs/TEST_MATRIX.md` | `STATUS.md` claims Phases 0–15 `COMPLETE & CI-VERIFIED` despite red Phase 5 run `44493993181` and failed `ufw.service`; `TEST_MATRIX.md` still lists Phases 2–15 as `*Planned*`. | Stale documentation and conflation of static config checks with functional verification. | Phase 16 |

---

## 3. Suspected Defects Requiring Further Reproduction

- **`kwin_wayland` segfault in `libQt5Gui.so.5.15.8` under TCG (`qemu-phase5-wayland.log`):** Observed during `os1-shell-init` in run `44493993181`. Needs full user journal and compositor liveness verification in Phase 16/21 to determine if it is triggered by `plasma-apply-lookandfeel` / `evaluateScript` under Mesa `llvmpipe` and whether KWin recovers cleanly or crashes the session.

---

## 4. Missing Tests

- CI integrity test (verifying no `continue-on-error: true` or hidden failures in required workflows).
- Runtime firewall behavioral traffic test (blocked by default, temporary allow, rule removal, reboot persistence).
- Installer negative preflight test suite (special-character passwords, reserved usernames, mounted/small/read-only targets, before/after disk checksum equality).
- Package verification suite (`dpkg-deb`, `lintian`, clean-rootfs install, `dpkg -V`, upgrade, remove, purge, reinstall).
- Signed APT update and versioned kernel upgrade + bad-kernel rollback QEMU tests.
- Installed graphical login (SDDM -> Wayland as created user), real application window launch verification, and `os1-firstboot` state preservation tests.
- Kernel driver presence manifest verification and reproducibility diff job.

---

## 5. Hardware-Gated & Human/Legal-Gated Items

- **Hardware-Gated:** Bare-metal UEFI boot, Intel `i915` / AMD `amdgpu` acceleration, physical Wi-Fi (`iwlwifi`/Atheros), Bluetooth, audio, webcam, touchpad, external HDMI/DP, suspend/resume, battery reporting, and physical update/rollback on Tier 1 systems.
- **Human/Legal-Gated:** Human accessibility usability review (Orca/AT-SPI end-to-end UX), human legal/trade-dress review, and production release GPG key custody & rotation approval.
