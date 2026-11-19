# OS-1 Test & Verification Matrix

Every test assertion is classified by what it actually proves:

- **Syntax check:** Parses shell/Python/YAML/JSON syntax only.
- **Static configuration check:** Verifies file existence or config text; does **not** prove runtime behavior.
- **Package/content check:** Verifies `.deb` metadata, paths, ownership, or binary presence.
- **Process check:** Verifies a daemon or process is running (`pgrep`, `systemctl is-active`).
- **Functional behavior check:** Exercises real runtime behavior and asserts the resulting state or output.
- **End-to-end user journey:** Exercises a multi-step user workflow across reboots or session boundaries.
- **Physical-hardware check:** Requires bare-metal PCs outside cloud QEMU/OVMF virtualization.

Unrun checks are marked `NOT TESTED` — never `PASS`.

## Active Verification Gates

| Gate ID | Workflow / Command | Assertion Strength | What It Actually Proves | Current Status |
|---|---|---|---|---|
| `T0-AUDIT` | `./distro/tools/os1.sh audit` (all workflows) | Syntax check + Static configuration check | Valid bash/Python syntax, git state, disk space, and CI integrity (`ci-integrity-test.py`: no `continue-on-error: true`, no suppressed test commands, bounded timeouts). | `PASS` |
| `T1-KBUILD` / `T1-QEMU-BOOT` | `phase1-kernel-boot.yml` | Functional behavior check | Out-of-tree `x86_64` OS-1 kernel builds cleanly and boots in QEMU with BusyBox initramfs (`uname -a`, `/proc`, `/tmp` write, clean poweroff, zero panic). | `PASS` |
| `T2-ROOTFS` | `phase2-userspace.yml` | End-to-end user journey | Debian 12 rootfs boots under systemd, non-root `os1` serial login, NetworkManager DHCPv4, live `apt-get install`, and 2-boot file/package persistence. | `PASS` |
| `T3-ISO-UEFI` | `phase3-live-iso.yml` | End-to-end user journey | Fresh UEFI Live ISO boots via OVMF in both Live (OverlayFS) and Recovery modes without host bind mounts. | `PASS` |
| `T4-INSTALL` | `phase4-installer.yml` | End-to-end user journey (serial only) | Nondestructive default gate (`rc=3`), GPT+ESP+ext4 install to blank QEMU disk, detached ISO UEFI boot, serial login as custom user, APT install, and 2-reboot persistence. Does **not** yet test graphical login (Phase 21) or special-character passwords (Phase 18). | `PASS` (serial) |
| `T5-WAYLAND` | `phase5-wayland-desktop.yml` | Process check + Static configuration check + Functional behavior check | Boots desktop disk image with SDDM autologin (`os1`), verifies `kwin_wayland`, `plasmashell`, `pipewire`, `konsole` launch, `os1-fs-test` (Functional), `notify-send`/`nmcli`/`upower` (Functional), `os1-accessibility reduced-motion` roundtrip (Functional), Light & Dark `1440×900` framebuffer screenshots (Functional), and static presence of shortcut configs & 11 app binaries (Static). | `PASS` (Run `44501470555`) |
| `T14-DEBS` / `T14-SBOM` | `phase14-15-release-qualification.yml` | Package/content check + Static configuration check | Builds `.deb`s and CycloneDX 1.5 SBOM. Known baseline defects: `os1-branding` root-level paths (Phase 19), unsigned `Release` (Phase 20), SBOM `bzImage_sha256: unknown` (Phase 23). | **Defect-tracked** |
| `T15-DESKTOP-INSTALL` | `phase14-15-release-qualification.yml` | End-to-end user journey (serial) + Functional behavior check | Installs full desktop ISO to 10 GiB disk, boots detached via serial, enforces active `ufw.service` + `nft list ruleset` on Boot 1 & Boot 2, runs `os1-fs-test` (Functional), and fails on any `ufw.service` boot error. | **Updated in Phase 17** |

## Planned / Required Gates (Phases 17–24)

| Gate ID | Target Phase | Assertion Strength | Scope | Status |
|---|---|---|---|---|
| `T17-FIREWALL` | Phase 17 | Functional behavior check | Runtime `ufw.service` active, nftables ruleset loaded, real external-peer HTTP traffic blocked by default, temporary allow reachable, removal blocks again, persists across reboot (`qemu-firewall-test.py`). | **Implemented in Phase 17 (awaiting CI)** |
| `T18-INSTALLER-SAFETY` | Phase 18 | Functional behavior check | Negative preflight suite (apostrophe/quote/`$`/space/Unicode passwords, reserved usernames, mounted/small/RO targets, unchanged disk checksums) + live autologin cleanup. | `NOT TESTED` (Phase 18) |
| `T19-PACKAGING` | Phase 19 | Package/content check + Functional behavior check | Fixed `/usr/share/*` paths, package-owned ISO/rootfs assembly, `dpkg -V`, upgrade/remove/purge/reinstall, version consistency. | `NOT TESTED` (Phase 19) |
| `T20-UPDATES-ROLLBACK` | Phase 20 | End-to-end user journey | Signed APT repo (`InRelease`/`Release.gpg` + `os1-keyring`), unsigned rejection, versioned kernel A -> B upgrade, bad-kernel B -> A boot recovery. | `NOT TESTED` (Phase 20) |
| `T21-INSTALLED-GUI` | Phase 21 | End-to-end user journey | Installed graphical login as created user (no live autologin), real window launch for required apps, idempotent `os1-shell-init`, atomic `os1-firstboot` state preservation. | `NOT TESTED` (Phase 21) |
| `T22-KERNEL-DRIVERS` | Phase 22 | Package/content check + Physical-hardware check | Final stable/LTS kernel baseline, packaged modules, automated driver presence manifest (CI), plus Tier 1 bare-metal qualification (Hardware-gated). | `NOT TESTED` (Phase 22) |
| `T23-PROVENANCE-REPRO` | Phase 23 | Functional behavior check | Exact-source kernel cache key, valid CycloneDX SBOM with real kernel hash, pinned/least-privileged workflows, clean dual-build reproducibility comparison, durable Release assets. | `NOT TESTED` (Phase 23) |
