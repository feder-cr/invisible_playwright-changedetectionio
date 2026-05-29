"""changedetection.io plugin: Firefox-based stealth fetcher.

Backend: invisible_playwright (https://github.com/feder-cr/invisible_playwright)
which drives a patched Firefox 150 binary with fingerprint patches at the
C++ source code level (https://github.com/feder-cr/invisible_firefox, MPL-2.0,
same license as Firefox upstream).

Useful for watches where the standard playwright fetcher hits Cloudflare,
Akamai, Datadome, or hCaptcha walls. Selected per-watch via the Fetch Method
dropdown once this package is installed.

Install via changedetection.io's EXTRA_PACKAGES env:

    EXTRA_PACKAGES=git+https://github.com/feder-cr/invisible_playwright-changedetectionio.git
"""
__version__ = "0.1.0"
