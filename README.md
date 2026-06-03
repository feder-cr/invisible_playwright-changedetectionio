# invisible_playwright-changedetectionio

[changedetection.io](https://github.com/dgtlmoon/changedetection.io) fetcher plugin that uses [invisible_playwright](https://github.com/feder-cr/invisible_playwright) — a Playwright wrapper around a patched Firefox 150 binary with fingerprint patches applied at the C++ source code level. No JavaScript shims, so anti-bot scripts have nothing to detect.

Useful for watches where the standard Playwright fetcher hits Cloudflare, Akamai, Datadome, or hCaptcha walls. Drop-in alternative to the Chromium-based `changedetection.io-cloak-browser` plugin, on the Firefox side.

Backend repo: [feder-cr/invisible_playwright](https://github.com/feder-cr/invisible_playwright)
Backend binary: [feder-cr/invisible_firefox](https://github.com/feder-cr/invisible_firefox) (MPL-2.0, same license as Firefox upstream)

## Install

Add to your changedetection.io `EXTRA_PACKAGES` (works for the Docker image, pip install, and the systemd setup):

```
EXTRA_PACKAGES="https://github.com/feder-cr/invisible_playwright-changedetectionio/archive/refs/heads/main.tar.gz"
```

This installs over plain HTTPS, so it works on the stock changedetection.io Docker image, which does not ship `git`. (A `git+https://...` reference would fail there with "Cannot find command 'git'".)

The plugin pulls in `invisible_playwright` automatically (also over HTTPS, no git needed). On first use the patched Firefox 150 binary is auto-downloaded to your cache (`~/.cache/invisible-playwright/firefox-7/` on Linux, `%LOCALAPPDATA%\invisible-playwright\Cache\firefox-7\` on Windows) and SHA256-verified.

After restart, "Invisible Firefox - Stealth (patched FF 150)" appears in the per-watch Fetch Method dropdown.

## System packages (Linux)

Firefox needs the standard set of Linux shared libraries. On the base changedetection.io Docker image they're not all preinstalled. The plugin's `is_ready()` check tells you exactly what's missing the first time you try the fetcher, but for convenience:

```
apt-get install -y libgtk-3-0 libdbus-glib-1-2 libxcomposite1 libxdamage1 \
                   libxrandr2 libxss1 libxtst6 libnss3 libcups2 \
                   libpangocairo-1.0-0 libasound2 libatk1.0-0 libatk-bridge2.0-0
```

(Windows binaries ship everything inside the archive — no system packages needed.)

## Supported features

Same as the standard Playwright fetcher:
- Browser steps (recorded interactions)
- Full-page screenshots
- xpath / CSS selector content extraction
- Custom JS execution
- Proxy configuration via `playwright_proxy_*` env vars

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `playwright_proxy_server` | unset | Standard Playwright proxy URL |
| `playwright_proxy_username` | unset | Proxy auth |
| `playwright_proxy_password` | unset | Proxy auth |
| `playwright_proxy_bypass` | unset | Host bypass list |
| `WEBDRIVER_DELAY_BEFORE_CONTENT_READY` | `5` | Seconds to wait before grabbing content |
| `PLAYWRIGHT_SERVICE_WORKERS` | `allow` | `allow` or `block` |
| `SCREENSHOT_MAX_HEIGHT` | (changedetection default) | Max screenshot height |

## How this compares to other fetcher plugins

| Plugin | Engine | Patch level | Use when |
|---|---|---|---|
| `playwright` (built-in) | Chromium | None | Default for most sites |
| `changedetection.io-cloak-browser` | Chromium | C++ source | Cloudflare / Akamai on Chromium-friendly targets |
| **this plugin** | **Firefox 150** | **C++ source** | **Same goal as cloak-browser, on sites that flag Chromium UA** |

The Firefox engine matters when target sites behave differently with Firefox than with Chrome — some anti-bot stacks weight Chromium-shaped traffic as higher risk because most residential-proxy bot traffic is Chromium-based.

## License

MIT — see [LICENSE](LICENSE).

The patched Firefox binary is distributed under MPL-2.0 (Firefox upstream license).
