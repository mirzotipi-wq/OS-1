# OS-1 Native Debian Packages (`distro/packages/`)

`distro/packages/build-debs.sh` builds the authoritative native `.deb` packages that assemble OS-1 systems from the single canonical version file [`distro/VERSION`](../VERSION):

| Package | Arch | Responsibility |
| --- | --- | --- |
| `os1-release` | `all` | Canonical `/etc/os-release` (via `dpkg-divert` of `base-files`) and `/usr/share/os1/VERSION` |
| `os1-keyring` | `all` | OS-1 APT archive keyring (`/usr/share/keyrings/os1-archive-keyring.gpg`) and `signed-by` APT source (`/etc/apt/sources.list.d/os1.list`) |
| `os1-branding` | `all` | Original OS-1 wallpapers, SVG emblem, `OS1Sequoia` Aurorae theme, Light/Dark color schemes, Look-and-Feel metadata, and design tokens under `/usr/share/` |
| `os1-shell` | `all` | Plasma Wayland layout, XDG desktop defaults, Wayland GPU environment, `os1-appearance`, `os1-shell-init`, and `os1-accessibility` |
| `os1-firstboot` | `all` | First-run onboarding and preference helper (`/usr/bin/os1-firstboot`) |
| `os1-installer` | `all` | Preflight-complete, credential-safe UEFI GPT installer (`/usr/sbin/os1-install`) |
| `os1-tools` | `all` | System verification and diagnostic tools (`/usr/bin/os1-fs-test`) |
| `os1-desktop-meta` | `amd64` | Complete OS-1 Wayland desktop metapackage tying all OS-1 packages and Debian desktop dependencies together |

`distro/build/build-rootfs.sh` installs these `.deb` packages directly via `dpkg -i` and verifies `dpkg --audit` and `dpkg -V` rather than copying loose files into the root filesystem.

Verification is enforced by `distro/tests/package-verify-test.py` (`./distro/tools/os1.sh pkg-verify`).
