# OS-1 Legal, Licensing, and Attribution Inventory

## 1. Linux Kernel License Obligations

- The upstream Linux kernel in this repository is licensed under **`GPL-2.0-only` WITH `Linux-syscall-note`** (see [`COPYING`](../COPYING) and `LICENSES/preferred/GPL-2.0`).
- Any distribution of compiled OS-1 kernel binaries (in ISOs, `.deb` packages, or VM images) MUST preserve GPL-2.0-only notices and provide corresponding complete source code (exact Git commit SHA, kernel config, and build scripts).
- Any AI-assisted contributions touching the kernel tree MUST comply with:
  - [`Documentation/process/coding-assistants.rst`](../Documentation/process/coding-assistants.rst)
  - [`Documentation/process/generated-content.rst`](../Documentation/process/generated-content.rst)
  - **Rule:** AI coding assistants MUST NEVER fabricate or add a human `Signed-off-by` / DCO certification tag.

## 2. Intellectual Property & Brand Policy (macOS Reference)

- **Zero Apple Assets:** Do NOT copy, extract, or redistribute Apple source code, macOS binaries, SF Pro/San Francisco fonts, Apple icons, wallpapers, sound effects, cursors, or trademarks.
- **Distinct Brand:** This distribution is branded **OS-1**. It must never be marketed as Apple-made, Apple-affiliated, or Apple-endorsed.
- **Original & Open Assets:** All OS-1 themes, icons, wallpapers, sounds, and typography must be independently created or sourced under OSI/CC/OFL-compatible licenses (e.g., Inter / IBM Plex / Noto / JetBrains Mono under OFL-1.1, original SVG icons under CC-BY-4.0 or Apache-2.0/MIT).
- **Human Legal Review Gate:** Any visual design, naming, or compatibility shim with trademark or trade-dress ambiguity must be flagged for human legal review before public release.

## 3. OS-1 Component License Inventory

| Path / Component | License | Origin | Notes |
|---|---|---|---|
| Upstream Linux Kernel (`/`) | `GPL-2.0-only WITH Linux-syscall-note` | Upstream Linux `7.4.0-rc3` (`666539eecd`) | Unmodified kernel source tree |
| `distro/kernel/`, `distro/build/`, `distro/tests/`, `distro/tools/` | `GPL-2.0-only` | Original OS-1 build & test scripts | Compatible with host repository license |
| `docs/` | `GPL-2.0-only` | Original OS-1 project documentation | Includes tool-generation transparency |
| Debian stable userspace (Phase 2+) | Mixed DFSG-free (GPL, LGPL, MIT, BSD, Apache-2.0) | Upstream Debian | Full SBOM & copyright manifests to be exported per image in Phase 2/14 |
| KDE Plasma / KWin / Qt (Phase 5+) | GPL-2.0 / GPL-3.0 / LGPL-2.1 / LGPL-3.0 | Upstream KDE & Qt | Tracked via Debian package metadata |
| OS-1 Branding & Assets (Phase 6+) | TBD (OFL-1.1 / CC-BY-4.0 / MIT / GPL-2.0) | Original OS-1 | Every asset file must be registered here before merging |
