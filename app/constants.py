"""
RemoteFlash — application identity and auto-update source.

Kept in its own module so the version string has a single source of truth
(build.bat reads APP_VERSION from this file).
"""

# ─── App identity ──────────────────────────────────────────────────
APP_NAME = "RemoteFlash"
APP_VERSION = "1.2.2"
APP_TAGLINE = "Remote AVR flashing over SSH"
APP_PUBLISHER = "IDEATON"
APP_WEBSITE = "https://www.ideaton.pl"
APP_CONTACT = "p.bayle@ideaton.pl"

# ─── Auto-update source (GitHub Releases) ──────────────────────────
GITHUB_REPO = "ideaton/RemoteFlash"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
