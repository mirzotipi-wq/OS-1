# OS-1 Known Gaps, Defects, Limitations & Gated Items

In accordance with OS-1's honesty and engineering discipline, this file records every verified software defect, architectural gap, and item requiring physical hardware or human review outside automated cloud CI.

## 1. Active Verified Software Defects (Tracked in Phases 16–23)

See [`docs/audits/PHASE16_BASELINE_AUDIT.md`](audits/PHASE16_BASELINE_AUDIT.md) for full forensic evidence.

- **Wayland CI Instability (`D-01`, Phase 16/21):** Run `44493993181` failed on `CONTROLS_A11Y_RC=` timeout after a `kwin_wayland` segfault in `libQt5Gui.so.5.15.8` and unbounded `qdbus` calls. Bounded timeouts and failure diagnostics added in Phase 16; installed graphical session qualification scheduled in Phase 21.
- **UFW Firewall Inactive at Runtime (`D-02`, Phase 17):** `ufw.service` fails to start on boot because `distro/kernel/os1_x86_64.fragment` omits required netfilter/nftables kernel options. Runtime traffic tests will be added and enforced in Phase 17.
- **Installer Credential & Preflight Safety (`D-03`, `D-04`, `D-05`, `D-12`, Phase 18):** `os1-install` interpolates passwords into shell source, accepts reserved usernames (`root`), performs incomplete target-disk preflight before partitioning, leaves live SDDM autologin targeting deleted `os1` user, and writes stale `0.4-dev` `/etc/os-release`.
- **Packaging Path & Split Assembly (`D-06`, `D-07`, Phase 19):** `os1-branding` currently installs `/aurorae`, `/icons`, `/pixmaps`, `/wallpapers` at root `/` instead of `/usr/share/*`, and `build-rootfs.sh` copies files directly instead of installing OS-1 `.deb` packages.
- **Unsigned Updates & Unversioned Kernel (`D-08`, `D-09`, Phase 20):** Local APT metadata is unsigned (no `InRelease`/`Release.gpg` or `os1-keyring`), and the kernel is installed as a fixed `/boot/vmlinuz-os1` file with no previous-kernel retention or rollback.
- **First-Login & Onboarding State Defects (`D-13`, `D-14`, `D-15`, Phase 21):** Installed graphical login is untested; `os1-shell-init` suppresses errors with `|| true` and writes its stamp unconditionally; `os1-firstboot` clobbers unspecified saved preferences.
- **Kernel RC Baseline & Driver/Module Coverage (`D-10`, `D-11`, Phase 22):** Kernel is still `7.4.0-rc3-os1` (release candidate), modules are not built/installed by default, and baseline x86-64 desktop drivers (e.g. `amdgpu`, `i915`, `iwlwifi`, HDA audio) are missing from the config fragment.
- **Cache Key, SBOM Hash & Release Publication (`D-16`, `D-17`, `D-18`, `D-19`, Phase 23):** Kernel CI cache key omits full source commit; SBOM reports `os1:bzImage_sha256: unknown`; release workflow does not publish durable GitHub Release assets; root lacks an OS-1 `README.md`.

## 2. Hardware-Gated Items (Require Physical PCs Outside Cloud VM)

- **Physical Intel / AMD GPU Acceleration:** Cloud CI runs on QEMU (`virtio-gpu` + Mesa `llvmpipe`). Bare-metal validation on physical Intel (`i915`) and AMD (`amdgpu`) laptops/desktops (Wi-Fi, Bluetooth, audio, webcam, external HDMI/DP, lid suspend/resume, battery reporting, and bare-metal update/rollback) requires physical Tier 1 test hardware.
- **Physical HiDPI & Multi-Monitor Hotplug:** Physical Retina/4K scaling and display hotplug require physical display hardware.
- **ARM64:** Explicitly deferred per ADR-0001 until an ARM64 support plan and test hardware exist.

## 3. Human Release & Legal Gates

- **Human Accessibility Review:** Automated checks can verify Orca startup, AT-SPI DBus reachability, and reduced-motion/high-contrast settings, but full assistive-technology usability requires human review.
- **Legal / Trade-Dress Review:** All OS-1 assets are independently created with zero Apple IP, and open fonts (`Noto`, `DejaVu`, `Liberation`) are used; a human legal review is required before declaring a stable public 1.0 release.
- **Production Release Key Custody:** CI uses ephemeral test signing keys; production signing key custody and rotation require human release-manager governance.

## 4. Platform Scope Realities

- OS-1 is a GNU/Linux desktop distribution. It does not execute proprietary macOS applications, Apple frameworks, iMessage, FaceTime, AirDrop, or Apple ID services.
