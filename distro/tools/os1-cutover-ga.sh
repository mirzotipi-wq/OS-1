#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# OS-1 1-Step General Availability (GA) Cutover Script
# Verifies pre-GA software gates (zero -rc LTS kernel, clean audit), bumps
# distro/VERSION to the target GA version (default: 1.0 / 1.0.0-1), and prints
# exact signed tag & release push commands.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VERSION_FILE="${REPO_ROOT}/distro/VERSION"
LTS_ENV="${REPO_ROOT}/distro/kernel/KERNEL_LTS.env"

TARGET_VERSION="${1:-1.0}"
TARGET_DEB_VERSION="${2:-1.0.0-1}"
DRY_RUN=0

if [[ "${TARGET_VERSION}" == "--dry-run" ]]; then
    DRY_RUN=1
    TARGET_VERSION="${2:-1.0}"
    TARGET_DEB_VERSION="${3:-1.0.0-1}"
fi

# shellcheck source=../kernel/KERNEL_LTS.env
source "${LTS_ENV}"

echo "=== OS-1 General Availability (GA) Cutover ==="
echo "  Pinned Kernel: Linux ${OS1_KERNEL_VERSION} (${OS1_KERNEL_CHANNEL})"
echo "  Target Version: ${TARGET_VERSION} (Debian pkg: ${TARGET_DEB_VERSION})"

if [[ "${OS1_KERNEL_VERSION}" == *"-rc"* ]]; then
    echo "ERROR: Cannot promote to GA while KERNEL_LTS.env references an -rc kernel (${OS1_KERNEL_VERSION})." >&2
    exit 1
fi
if [[ "${OS1_KERNEL_CHANNEL}" != "longterm" && "${OS1_KERNEL_CHANNEL}" != "stable" ]]; then
    echo "ERROR: Unexpected kernel channel '${OS1_KERNEL_CHANNEL}' (expected longterm or stable)." >&2
    exit 1
fi
if [[ ! "${OS1_KERNEL_SHA256}" =~ ^[0-9a-f]{64}$ ]]; then
    echo "ERROR: Invalid OS1_KERNEL_SHA256 in ${LTS_ENV}." >&2
    exit 1
fi

if (( DRY_RUN == 1 )); then
    echo "[os1-cutover-ga] --dry-run PASSED: Pre-GA kernel & manifest gates satisfied."
    exit 0
fi

sed -i "s/^OS1_VERSION=.*/OS1_VERSION=\"${TARGET_VERSION}\"/" "${VERSION_FILE}"
sed -i "s/^OS1_DEB_VERSION=.*/OS1_DEB_VERSION=\"${TARGET_DEB_VERSION}\"/" "${VERSION_FILE}"

echo "[os1-cutover-ga] Updated ${VERSION_FILE}:"
grep -E '^OS1_(VERSION|DEB_VERSION)=' "${VERSION_FILE}"

echo "[os1-cutover-ga] Running full repository audit..."
"${REPO_ROOT}/distro/tools/os1.sh" audit

cat <<EOF

=== OS-1 GA Cutover Ready ===
Before tagging v${TARGET_VERSION}.0, confirm the two human/hardware gates are complete:
  1. Bare-metal Tier 1 UEFI checklist signed off on Intel & AMD x86-64 hardware (docs/SUPPORTED_HARDWARE.md).
  2. Production GPG key configured in GitHub Secrets (OS1_GPG_PRIVATE_KEY / OS1_GPG_PASSPHRASE) OR ready for offline signing via distro/tools/os1-sign-release.sh.

Next commands to publish GA release:
  git add distro/VERSION
  git commit -m "release: promote OS-1 ${TARGET_VERSION} General Availability"
  git tag -s "v${TARGET_VERSION}.0" -m "OS-1 ${TARGET_VERSION} General Availability"
  git push origin master --follow-tags
EOF
