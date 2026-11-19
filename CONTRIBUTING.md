# Contributing to OS-1

Thank you for your interest in contributing to OS-1 GNU/Linux.

## Repository Layout

- `distro/` — OS-1 kernel config fragment, build scripts, native Debian packaging, installer, desktop shell, branding, tools, and automated QEMU/unit tests.
- `docs/` — Architecture, ADRs, security model, hardware policy, test matrix, and release process.
- All other top-level directories (`arch/`, `drivers/`, `kernel/`, `Documentation/`, etc.) — Upstream Linux kernel source tree. Preserve upstream licensing and attribution.

## Engineering Rules

1. **Run the local audit before pushing:**
   ```bash
   ./distro/tools/os1.sh audit
   ```
2. **Truthful testing:** Never weaken tests, add `continue-on-error: true` to required CI jobs, or mask failures with `|| true`.
3. **Credential safety:** Never pass plaintext passwords in command-line arguments, shell interpolation, or logs, and never commit private signing keys.
4. **Disk safety:** Automated installer tests must target only disposable sparse disk images or QEMU virtual disks.
5. **Original branding & licensing:** Never commit proprietary Apple assets, fonts, icons, sounds, or trademarks. Record all assets in [`docs/LEGAL_AND_LICENSES.md`](docs/LEGAL_AND_LICENSES.md).
6. **AI coding assistants:** Must comply with [`Documentation/process/coding-assistants.rst`](Documentation/process/coding-assistants.rst).
