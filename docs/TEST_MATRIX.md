# OS-1 Test & Verification Matrix

Every phase must pass automated checks on a clean state before advancing. Unrun checks are marked `NOT TESTED`—never `PASS`.

## Active & Planned Verification Gates

| Gate ID | Phase | Scope | Command | Runner / Environment | Artifact / Evidence |
|---|---|---|---|---|---|
| `T0-AUDIT` | 0 | Repo state, git integrity, script syntax (`bash -n`), doc presence | `./distro/tools/os1.sh audit` | Local VM & GitHub Actions | Audit stdout log |
| `T1-KCONFIG` | 1 | Out-of-tree `x86_64` Kconfig merge (`defconfig` + `os1_x86_64.fragment`) | `./distro/kernel/build-kernel.sh --config-only` | Local VM & GitHub Actions | `distro/out/kernel/os1_x86_64.config` |
| `T1-KBUILD` | 1 | Full x86-64 `bzImage` build + SHA-256 provenance manifest | `./distro/tools/os1.sh kernel` | GitHub Actions (`ubuntu-latest`) / Linux dev host | `bzImage`, `provenance.json` |
| `T1-INITRAMFS` | 1 | Minimal bootable userspace initramfs (`init` PID 1 + BusyBox or static init) | `./distro/tools/os1.sh initramfs` | GitHub Actions / Linux dev host | `os1-initramfs.cpio.gz` |
| `T1-QEMU-BOOT` | 1 | QEMU `x86_64` serial boot proof (`uname -a`, `/proc`, `/tmp` write, clean poweroff, zero panic) | `./distro/tools/os1.sh boot-test` | GitHub Actions / Linux dev host | `qemu-serial.log` |
| `T2-ROOTFS` | 2 | Debian stable rootfs + systemd + non-root login + networking + APT install + reboot persistence | *Planned (`distro/tests/qemu-userspace-test.sh`)* | GitHub Actions / KVM host | Serial log + ext4 image checksum |
| `T3-ISO-UEFI` | 3 | Fresh UEFI live ISO boot via QEMU + OVMF without host bind mounts | *Planned (`distro/tests/qemu-iso-uefi-test.sh`)* | GitHub Actions / KVM host | ISO SHA-256 + OVMF boot log |
| `T4-INSTALL` | 4 | Clean VM disk install from live ISO, ISO detach, reboot, APT update, second reboot | *Planned* | KVM host / CI | Installer log + post-install boot log |
| `T5-WAYLAND` | 5 | Graphical login, KDE/KWin Wayland session, terminal/browser/files, audio, resize, reboot | *Planned* | KVM + VirGL / host | Screenshots + session journal |
| `T6-UI-VIS` | 6–12 | Multi-resolution (`1440×900`, `1920×1080`, HiDPI) light/dark screenshot diffs & E2E UI flows | *Planned* | KVM / Hardware-in-the-loop | Normalized screenshots + diff report |
| `T14-SEC` | 14–15 | Signed APT repo verification, upgrade/rollback drill, SBOM & license check | *Planned* | CI + Clean VM | SBOM + compliance report |
