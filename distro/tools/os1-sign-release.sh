#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# OS-1 Offline / Air-Gapped Release Signing Helper
# Re-signs an OS-1 release bundle (APT Release + SHA256SUMS) with an offline
# maintainer GPG key and verifies every signature.
set -euo pipefail

BUNDLE_DIR="${1:-}"
GPG_KEY="${2:-${OS1_GPG_SIGN_KEY:-}}"

usage() {
    cat <<EOF
Usage: $(basename "$0") <release-bundle-dir> <gpg-key-id-or-fingerprint>

Signs:
  - <dir>/Release      -> InRelease (clearsigned) & Release.gpg (detached)
  - <dir>/SHA256SUMS   -> SHA256SUMS.asc (detached)
Exports:
  - <dir>/os1-archive-keyring.gpg (public archive signing key)
Verifies all generated signatures before exiting 0.
EOF
}

if [[ -z "${BUNDLE_DIR}" || -z "${GPG_KEY}" ]]; then
    usage >&2
    exit 2
fi

if [[ ! -d "${BUNDLE_DIR}" || ! -f "${BUNDLE_DIR}/Release" ]]; then
    echo "ERROR: Expected Release file in bundle directory: ${BUNDLE_DIR}" >&2
    exit 1
fi

for tool in gpg sha256sum; do
    command -v "${tool}" >/dev/null 2>&1 || { echo "ERROR: missing ${tool}" >&2; exit 1; }
done

echo "[os1-sign-release] Exporting public keyring -> ${BUNDLE_DIR}/os1-archive-keyring.gpg"
gpg --batch --yes --export "${GPG_KEY}" > "${BUNDLE_DIR}/os1-archive-keyring.gpg"
chmod 0644 "${BUNDLE_DIR}/os1-archive-keyring.gpg"

echo "[os1-sign-release] Signing APT Release -> InRelease & Release.gpg"
gpg --yes --digest-algo SHA256 --local-user "${GPG_KEY}" \
    --clearsign -o "${BUNDLE_DIR}/InRelease" "${BUNDLE_DIR}/Release"
gpg --yes --digest-algo SHA256 --local-user "${GPG_KEY}" \
    --armor --detach-sign -o "${BUNDLE_DIR}/Release.gpg" "${BUNDLE_DIR}/Release"

echo "[os1-sign-release] Regenerating & signing SHA256SUMS"
(
    cd "${BUNDLE_DIR}"
    rm -f SHA256SUMS SHA256SUMS.asc
    sha256sum * > SHA256SUMS
)
gpg --yes --digest-algo SHA256 --local-user "${GPG_KEY}" \
    --armor --detach-sign -o "${BUNDLE_DIR}/SHA256SUMS.asc" "${BUNDLE_DIR}/SHA256SUMS"

echo "[os1-sign-release] Verifying signatures against exported os1-archive-keyring.gpg..."
TMP_GNUPG="$(mktemp -d "${TMPDIR:-/tmp}/os1-verify-gpg.XXXXXX")"
trap 'rm -rf "${TMP_GNUPG}"' EXIT
chmod 0700 "${TMP_GNUPG}"
GNUPGHOME="${TMP_GNUPG}" gpg --batch --quiet --import "${BUNDLE_DIR}/os1-archive-keyring.gpg"
GNUPGHOME="${TMP_GNUPG}" gpg --batch --verify "${BUNDLE_DIR}/InRelease"
GNUPGHOME="${TMP_GNUPG}" gpg --batch --verify "${BUNDLE_DIR}/Release.gpg" "${BUNDLE_DIR}/Release"
GNUPGHOME="${TMP_GNUPG}" gpg --batch --verify "${BUNDLE_DIR}/SHA256SUMS.asc" "${BUNDLE_DIR}/SHA256SUMS"

echo "[os1-sign-release] SUCCESS: All release signatures generated and verified."
