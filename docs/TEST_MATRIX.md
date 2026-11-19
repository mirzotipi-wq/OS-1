# OS-1 Test & Verification Matrix

Every test assertion is classified by what it actually proves:

- **Syntax check:** Parses shell/Python/YAML/JSON syntax only.
- **Static configuration check:** Verifies file existence or config text; does **not** prove runtime behavior.
- **Package/content check:** Verifies `.deb` metadata, FHS paths, `lintian`, ownership, or binary presence.
- **Process check:** Verifies a daemon or process is running (`pgrep`, `systemctl is-active`).
- **Functional behavior check:** Exercises real runtime behavior and asserts the resulting state or output.
- **End-to-end user journey:** Exercises a multi-step user workflow across reboots or session boundaries.
- **Physical-hardware check:** Requires bare-metal PCs outside cloud QEMU/OVMF virtualization.

Unrun checks are marked `NOT TESTED` or `HARDWARE-GATED` — never `PASS`.

## Automated CI Verification Gates (OS-1 1.0-rc2)

| Gate ID | Workflow / Command | Assertion Strength | What It Actually Proves |
|---|---|---|---|
| `T0-AUDIT` | `./distro/tools/os1.sh audit` (all 6 workflows) | Syntax + Functional behavior check | Bash/Python syntax, `ci-integrity-test.py` (no `continue-on-error: true`, no `|| true` test suppression, bounded timeouts, explicit `permissions:`, 40-char SHA action pinning), `installer-safety-test.py` (27 negative/credential/special-char cases), `package-verify-test.py` (8 `.deb`s FHS/conffiles/md5sums/secret-scan), `firstboot-state-test.py` (preference preservation, corrupt recovery, `os1-shell-init` retry/idempotency), `sbom-verify-test.py --self-test`, and `reproducibility-check.py` (byte-for-byte dual-build `.deb` determinism). |
| `T1-KBUILD` / `T22-DRIVERS` / `T1-QEMU-BOOT` | `phase1-kernel-boot.yml` | Package/content + Functional behavior check | Out-of-tree `x86_64` kernel + modules (`--with-modules`), `kernel-driver-audit.py --check-modules` (69 driver symbols + `.ko` verification → `driver-manifest.json`), and QEMU serial boot (`uname -a`, `/proc`, `/tmp` write, clean poweroff). |
| `T2-ROOTFS` / `T17-FIREWALL` | `phase2-userspace.yml` | End-to-end user journey + Functional behavior check | Debian 12 rootfs assembled via native OS-1 `.deb`s, NetworkManager DHCPv4, APT install, 2-boot persistence, plus behavioral `qemu-firewall-test.py` (active `ufw.service`/`nftables`, inbound HTTP DROP, explicit ALLOW, re-DROP, loopback, outbound, reboot persistence). |
| `T3-ISO-UEFI` | `phase3-live-iso.yml` | End-to-end user journey | Fresh UEFI Live ISO boots via OVMF in both Live (OverlayFS) and Recovery modes without host bind mounts. |
| `T4-INSTALL` | `phase4-installer.yml` | End-to-end user journey | Clean GPT+ESP+ext4 install with special-character password (`O'Brien $100 "safe" & clean!`) via `--password-stdin`, zero credential log leakage, live `os1` user & SDDM `[Autologin]` removal, detached ISO UEFI boot, 2 reboots, active UFW/nftables. |
| `T20-UPDATE-ROLLBACK` | `phase4-installer.yml` | End-to-end user journey | Unsigned APT repo rejection, signed APT repo upgrade of OS-1 packages, versioned `linux-image-os1-<krel>` A→B kernel upgrade, running-kernel removal guard, and broken-kernel B→A GRUB rollback recovery. |
| `T5-WAYLAND` | `phase5-wayland-desktop.yml` | Process + Functional behavior check | KDE Plasma / KWin Wayland session, `pipewire`, `konsole`, `os1-fs-test`, `notify-send` D-Bus readiness, `nmcli`/`upower`, `os1-accessibility reduced-motion` roundtrip, Light & Dark `1440×900` screenshots, reboot persistence. |
| `T14-DEBS` / `T19-PKG` / `T23-SBOM` | `phase14-15-release-qualification.yml` | Package/content + Functional behavior check | GPG-signed 8 native `.deb`s + versioned kernel `.deb`, `lintian` 0-error pass, chroot `dpkg -S`/`dpkg -V`/upgrade/conffile/remove/purge/reinstall lifecycle, and CycloneDX 1.5 SBOM strictly validated by `sbom-verify-test.py --require-iso` (real kernel/package/ISO SHA-256 hashes). |
| `T15-ISO-BOOT` / `T15-DESKTOP-INSTALL` / `T21-INSTALLED-GUI` | `phase14-15-release-qualification.yml` | End-to-end user journey | Full Desktop UEFI Live ISO boot + Recovery, clean install to 10 GiB disk, SDDM greeter (no autologin), genuine graphical login as installer-created user `alice` via QEMU monitor `sendkey`, Wayland/KWin/Plasma/PipeWire/UFW/NM, `os1-shell-init` stamp, Light & Dark screenshots, app launches (`konsole`, `dolphin`, `kate`, `systemsettings`, `okular`), `os1-firstboot` preference preservation, and reboot persistence + 2nd SDDM login. |

## Non-Automated / Gated Verification

| Gate ID | Assertion Strength | Scope | Status |
|---|---|---|---|
| `T22-TIER1-HW` | Physical-hardware check | Real Intel & AMD x86-64 UEFI bare-metal checklist ([`docs/SUPPORTED_HARDWARE.md`](SUPPORTED_HARDWARE.md)) | `HARDWARE-GATED` |
| `T24-HUMAN-GATES` | Human review | Accessibility usability review, legal/trade-dress review, offline production GPG key custody | `HUMAN-GATED` |
