"""changedetection.io plugin: Firefox-based stealth fetcher.

Backend: invisible_playwright (https://github.com/feder-cr/invisible_playwright)
which drives a patched Firefox binary whose fingerprint changes are made in the
browser's own C++ source (https://github.com/feder-cr/firefox_antidetect_patch,
MPL-2.0, the same licence as Firefox upstream).

Useful for watches where the standard playwright fetcher is turned away by a
site's bot protection. Selected per-watch via the Fetch Method dropdown
once this package is installed.

Install via changedetection.io's EXTRA_PACKAGES env:

    EXTRA_PACKAGES=git+https://github.com/feder-cr/invisible_playwright-changedetectionio.git
"""
__version__ = "0.1.0"
