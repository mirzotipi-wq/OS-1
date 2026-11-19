# OS-1 Architecture

## 1. Repository Audit Summary (Baseline `666539eecd`)

Initial forensic inspection of `mirzotipi-wq/OS-1` at `master` (`666539eecdf4db623f5e3c3e55cf9f2dfad24aa4`) confirmed:
- The repository is a pure upstream Linux kernel source tree (`Makefile`: `VERSION=7`, `PATCHLEVEL=4`, `SUBLEVEL=0`, `EXTRAVERSION=-rc3`, with post-rc3 merge commits heading toward `7.4-rc4`).
- No userspace, rootfs builder, ISO generator, installer, Wayland/X11 desktop, macOS-like shell, branding assets, packaging metadata, or CI workflows existed prior to Phase 0.
- `AGENTS.md` is a symlink to `README` and mandates compliance with `Documentation/process/coding-assistants.rst` and `Documentation/process/generated-content.rst`.

## 2. Adopted Baseline Architecture

See [`decisions/ADR-0001-baseline-architecture.md`](decisions/ADR-0001-baseline-architecture.md) and [`decisions/ADR-0002-kernel-rc-strategy.md`](decisions/ADR-0002-kernel-rc-strategy.md) for full rationale.

| Layer | Selection | Rationale |
|---|---|---|
| **Kernel** | In-repo OS-1 Linux kernel (`7.4.0-rc3-os1`), out-of-tree Kbuild (`distro/kernel/`) | Preserves exact source SHA provenance and standard kernel tree while layering deterministic `x86_64` QEMU/UEFI/desktop config fragments. |
| **Userspace Base** | Pinned Debian stable (`bookworm` / `trixie` once pinned in Phase 2) via `debootstrap` / `mmdebstrap` + `systemd`, `glibc`, `APT`, `NetworkManager`, `PipeWire` | Mature, reproducible, security-maintained GNU/Linux base with standard `.deb` packaging and broad hardware support. |
| **Graphics & Compositor** | Wayland-first KDE Plasma / KWin + Qt/QML + KDE Frameworks + XWayland | Best-in-class Wayland compositor extension support (blur, rounded corners, window rules, global menus via `appmenu`, virtual desktops/overview, HiDPI scaling) without fragile GNOME Shell monkey-patching. |
| **OS-1 Shell & Apps** | Modular Qt/QML panels (top menu bar, Dock, Launchpad grid, Spotlight search) + curated/adapted native apps under `distro/shell/` and `distro/apps/` | Maintainable upstream-aligned APIs; real OS service integration (DBus, systemd, NetworkManager, PipeWire, UPower). |
| **Packaging** | Native `.deb` packages built from `distro/packages/` into a signed local/release APT repository | Reproducible upgrades, clean uninstall/rollback, zero `curl | bash` in images. |
| **Live ISO & Installer** | x86-64 UEFI bootable live ISO (`grub-efi` + SquashFS + `os1` kernel/initramfs) with Calamares installer | Nondestructive defaults, GPT/ESP/ext4 (+ optional LUKS2) partitioning, reproducible CI-verifiable builds. |
| **Target Hardware Order** | 1. x86-64 UEFI QEMU/KVM VMs → 2. Selected Intel/AMD UEFI PCs → 3. ARM64 (future, hardware-gated) | Fast automated testability first; hardware support added only with real test evidence. |

## 3. Repository Layout

```text
/ (upstream Linux kernel tree — kept clean)
├── .github/workflows/      # Automated CI gates (kernel build, QEMU boot, future ISO/UI tests)
├── distro/
│   ├── .gitignore          # Ignores out/, work/, cache/, ISOs, disk images, logs
│   ├── kernel/             # Kconfig fragments, out-of-tree build script, provenance manifest
│   ├── build/              # Initramfs, rootfs, live ISO build orchestration
│   ├── packages/           # Native .deb packaging manifests for OS-1 components
│   ├── shell/              # Menu bar, Dock, launcher, search, settings integration
│   ├── apps/               # Custom/adapted native applications
│   ├── branding/           # Original, permissively/compatibly licensed OS-1 visual identity
│   ├── installer/          # Calamares configuration and first-run onboarding
│   ├── tests/              # QEMU serial/UEFI boot, smoke, installer, UI regression suites
│   └── tools/              # Unified CLI (`os1.sh`) for audit, build, boot, test, clean
└── docs/                   # Durable mission, architecture, roadmap, status, handoff, ADRs
```

## 4. Documented Modern macOS Reference Target

To prevent inconsistent mixing of macOS generations, OS-1 targets a single documented reference baseline (to be captured with legally usable comparative design specs before Phase 6):
- **Reference Baseline:** **macOS Sequoia 15.x** (light and dark appearances).
- **Target Display Matrix:** `1440×900` (100%), `1920×1080` (100%), and `2560×1600` (200% HiDPI scaling).
- **Legal Boundary:** Reference observations inform layout geometry, spacing, elevation, motion curves, and interaction workflows only. All OS-1 icons, fonts, sounds, wallpapers, window chrome assets, and brand marks are independently created or sourced under OSI/CC/OFL-compatible licenses.

## 5. Key Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Kernel `-rc3` instability:** Upstream `7.4.0-rc3` is a release candidate, not an LTS/stable release. | High | Build and test OS-1 kernel explicitly in Phase 1+; track regressions in `KNOWN_GAPS.md`; maintain an optional documented Debian stable fallback *only* for isolated bring-up debugging (never counted as OS-1 kernel pass). Plan rebase/merge to `7.4` final or LTS when ready. |
| **Sandbox / CI resource limits:** Kernel + rootfs + ISO builds require significant disk (10–25 GB) and QEMU/KVM. | High | Out-of-tree builds (`distro/out/`), disk-space preflight checks, shallow CI checkouts, bounded 7-day CI artifact retention, and modular build stages. |
| **Toolkit / Wayland gaps:** Not all GTK/XWayland apps export global menus or identical macOS shortcuts. | Medium | Document per-app behavior in Phase 7 & 12 comparison matrices; never claim 1:1 where upstream toolkits diverge. |
| **IP / Trademark infringement:** Copying Apple visual assets or branding creates legal liability. | Critical | Enforce strict original-asset policy and license inventory in `docs/LEGAL_AND_LICENSES.md`; flag any borderline design for human review before public distribution. |
