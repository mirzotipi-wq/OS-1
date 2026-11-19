# OS-1 Hardware, Performance, Power & Accessibility Baseline (Phase 13)

## 1. Supported & Verified Targets

| Target Platform | Graphics / Display | Networking & Audio | Power & Input | Verification Status |
|---|---|---|---|---|
| **QEMU/KVM & QEMU/TCG (x86-64 UEFI OVMF)** | `virtio-gpu` DRM/KMS + Mesa `llvmpipe` fallback (`10-os1-gpu-env` activates software rendering only when `/dev/dri/renderD*` is absent) | `virtio-net-pci` (NetworkManager), PipeWire (`pipewire-pulse`, `pipewire-alsa`) | `upower`, `power-profiles-daemon`, USB/PS2 pointer & keyboard | **CI-VERIFIED** (1440×900 Light & Dark Wayland screenshots, OVMF Live ISO + Clean Install) |
| **Physical Intel / AMD x86-64 UEFI PCs** | `i915` / `amdgpu` DRM/KMS + Mesa Vulkan/OpenGL (`libgl1-mesa-dri`, `mesa-vulkan-drivers`) | NetworkManager + `non-free-firmware` APT component enabled | `upower`, `power-profiles-daemon`, `libinput` touchpad | **HARDWARE-GATED** (Requires physical Intel/AMD laptop/desktop outside cloud VM) |
| **ARM64** | Out of scope for 1.0-rc1 | — | — | **NOT TARGETED** (Per ADR-0001 until explicit ARM64 hardware plan exists) |

## 2. Accessibility Baseline

- **Screen Reader:** `orca` is preinstalled in `OS1_PROFILE=desktop` and verified present on installed systems.
- **Reduced Motion:** `os1-accessibility reduced-motion on|off` sets KWin `AnimationDurationFactor=0` (and is configurable via `os1-firstboot`). Verified in CI.
- **Reduced Transparency:** `os1-accessibility reduced-transparency on|off` toggles KWin blur/translucency effects for high-legibility/low-GPU environments.
- **Keyboard-Only Navigation:** Full keyboard shortcut parity documented in [`docs/INTERACTION_MATRIX.md`](INTERACTION_MATRIX.md).

## 3. Security & Privacy Baseline (Phase 14)

- **Firewall:** `ufw` preinstalled and configured with `ENABLED=yes`, `DEFAULT_INPUT_POLICY="DROP"`, `DEFAULT_OUTPUT_POLICY="ACCEPT"`, and `ufw.service` enabled.
- **Least Privilege:** `root` account is locked (`passwd -l root`); administration uses password-authenticated `sudo` for `%sudo`.
- **Search Privacy:** Local-first KRunner (`distro/shell/xdg/krunnerrc`) disables web search plugins by default.
- **Supply Chain:** Native `.deb` packages (`os1-branding`, `os1-shell`, `os1-desktop-meta`), local APT `Release` metadata, `SHA256SUMS`, and CycloneDX 1.5 JSON SBOM (`os1-sbom.cdx.json`) generated per release build.
