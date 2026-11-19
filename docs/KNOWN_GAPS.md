# OS-1 Known Gaps, Limitations & Human-Gated Items

In accordance with OS-1's honesty and engineering discipline, this file records every known limitation, platform difference, and item requiring physical hardware or human review outside automated cloud CI.

## 1. Hardware-Gated Items (Require Physical PCs Outside Cloud VM)

- **Physical Intel / AMD GPU Acceleration:** CI verifies `virtio-gpu` + Mesa `llvmpipe` software fallback (`10-os1-gpu-env` activates software rendering only when `/dev/dri/renderD*` is absent). Bare-metal validation on physical Intel (`i915`) and AMD (`amdgpu`) laptops/desktops (including Wi-Fi, Bluetooth, webcam, external HDMI/DP hotplug, lid suspend/resume, and battery drain) requires physical hardware.
- **HiDPI (`200%`) & Multi-Monitor Physical Testing:** CI verifies `1440×900` Light and Dark Wayland rendering in QEMU; physical Retina/4K HiDPI scaling and multi-monitor hotplug require physical display testing.
- **ARM64:** Explicitly deferred per ADR-0001 until an ARM64 support plan and test hardware exist.

## 2. Human Release & Legal Gates

- **Kernel Release Candidate Policy:** The repository kernel is upstream Linux `7.4.0-rc3` (`7.4.0-rc3-os1`). Before a public end-user "Stable" release, a human maintainer should decide whether to rebase onto a final stable Linux release tag or maintain an LTS kernel option alongside `7.4.0-rc3-os1`.
- **GPG Key Signing for Public APT Repo & GitHub Releases:** `distro/packages/build-debs.sh` generates standards-compliant APT `Packages`, `Packages.gz`, `Release`, and `SHA256SUMS`. Signing `InRelease`/`Release.gpg` with a private GPG release key is intentionally left to a human release manager (never store private signing keys in Git).
- **Legal / Trade-Dress Review:** All OS-1 assets (`OS1Horizon` wallpapers, `os1-logo.svg`, `OS1Sequoia` Aurorae theme, color schemes, shell configs) are 100% independently created with zero Apple IP, and open fonts (`Noto`, `DejaVu`, `Liberation`) are used. A human legal review is recommended before public marketing or distribution.

## 3. Platform Scope Realities

- OS-1 is a genuine GNU/Linux desktop distribution (`Debian 12 bookworm` userspace + `7.4.0-rc3-os1` kernel + KDE Plasma 5.27 / KWin Wayland). It does not natively execute proprietary macOS `.app` bundles, Apple frameworks, iMessage, FaceTime, AirDrop, or Apple ID services.
- Installer UX: `os1-install` provides a deterministic, nondestructive-by-default UEFI GPT installer verified end-to-end in CI. A graphical Calamares frontend can be layered on top of `os1-install` in a future minor release if desired.
