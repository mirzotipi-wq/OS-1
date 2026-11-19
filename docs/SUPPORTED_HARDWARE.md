# OS-1 Supported Hardware Policy & Qualification Matrix

- **Release Target:** `OS-1 1.0-rc2`
- **Architecture:** `x86_64` (UEFI 64-bit, GPT)
- **Kernel Policy:** See [`docs/decisions/ADR-kernel-release-policy.md`](decisions/ADR-kernel-release-policy.md)

OS-1 strictly separates **automated CI-verified virtual platforms** from **driver-compiled, bare-metal hardware-gated platforms**. Drivers being compiled into the kernel or modules never constitute bare-metal hardware certification.

---

## Tier 0 — Automated CI-Verified (PASSING)

| Platform | Firmware | Graphics | Storage / Net / Audio | Qualification Status |
|---|---|---|---|---|
| **QEMU/KVM & QEMU/TCG x86-64** | OVMF UEFI (`q35`) | `virtio-gpu` DRM/KMS + Mesa `llvmpipe` fallback | `virtio-blk`, `virtio-net`, `intel-hda` + PipeWire | **CI-VERIFIED** (Live ISO, Recovery, Clean GPT Install, SDDM Graphical Login, Wayland/KWin/Plasma, UFW/nftables, Signed APT Update, Kernel Rollback) |

---

## Tier 1 — Target Physical x86-64 UEFI Hardware (HARDWARE-GATED)

The following device classes have kernel drivers enabled in `distro/kernel/os1_x86_64.fragment` and verified compiled by `distro/tests/kernel-driver-audit.py` (`driver-manifest.json`), with Debian `non-free-firmware` enabled for userspace firmware packages. **All physical-hardware runtime behavior remains HARDWARE-GATED until verified on real machines.**

| Subsystem | Kernel Drivers Enabled | Qualification Status |
|---|---|---|
| **Graphics (DRM/KMS)** | `i915` (Intel), `amdgpu` (AMD, incl. SI/CIK), `nouveau` (NVIDIA open), `simpledrm` | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Wired Ethernet** | `e1000e`, `igb`, `igc` (Intel), `r8169` (Realtek), USB `cdc_ether`, `rndis_host`, `r8152` | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Wi-Fi (802.11)** | `iwlwifi`/`iwlmvm` (Intel), `ath10k_pci`/`ath11k_pci` (Qualcomm), `rtw88_pci` (Realtek) | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Storage & USB** | `nvme`, `ahci`, `xhci_hcd`, `ehci_hcd`, `usb_storage`, `uas` | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Audio** | `snd_hda_intel` (Realtek/HDMI/Generic codecs), `snd_usb_audio` + PipeWire | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Bluetooth** | `btusb`, `rfcomm`, `bnep`, `hidp` | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Input & Touchpads** | `usbhid`, `hid_multitouch`, `i2c_hid_acpi`, `i2c_designware`, PS/2 Synaptics/Elantech | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Webcam** | `uvcvideo` (USB Video Class) | **DRIVER-COMPILED / HARDWARE-GATED** |
| **Power, ACPI & TPM** | `acpi` (AC/Battery/Video), `backlight`, `intel_pstate`/`amd_pstate`, `tpm_tis`/`tpm_crb` | **DRIVER-COMPILED / HARDWARE-GATED** |

---

## Unsupported / Out of Scope for OS-1 1.0-rc2

- **ARM64 / Apple Silicon (`aarch64`)**: Not targeted for `1.0-rc2` (per ADR-0001).
- **Legacy BIOS-only (non-UEFI) systems**: Not targeted; OS-1 targets UEFI x86-64 GPT.
- **Proprietary NVIDIA out-of-tree DKMS driver**: Not bundled in `1.0-rc2` (open `nouveau` module only).
- **Secure Boot with third-party shim signing**: Not yet signed with a Microsoft/UEFI CA shim.

---

## Physical-Hardware Qualification Checklist (Required Before `OS-1 1.0` GA)

Before claiming bare-metal readiness for any physical machine class (minimum: 1 Intel iGPU laptop, 1 AMD GPU desktop/laptop):

1. Boot `os1-1.0-rc2-x86_64.iso` from USB on UEFI bare metal.
2. Run `os1-hw-diag --json` and attach the redacted report to the qualification record.
3. Verify native display resolution, refresh rate, and Wayland hardware acceleration (`glxinfo`/`vulkaninfo` or KWin DRM backend, not `llvmpipe`).
4. Verify wired Ethernet and Wi-Fi association + DHCP + DNS via NetworkManager.
5. Verify Bluetooth pairing, internal speakers/headphones, microphone, and UVC webcam.
6. Verify touchpad multi-finger gestures, brightness keys, battery reporting, and suspend/resume (S0ix/S3).
7. Perform clean GPT installation via `os1-install`, reboot without USB, log in via SDDM, verify active `ufw.service`, and verify signed APT update + kernel rollback on bare metal.
