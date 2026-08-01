[![Sponsored](https://readmead.site/api/ad/feder-cr)](https://readmead.site/api/click/feder-cr)

# invisible_playwright-changedetectionio

A [changedetection.io](https://github.com/dgtlmoon/changedetection.io) fetcher plugin
backed by [invisible_playwright](https://github.com/feder-cr/invisible_playwright), a
Playwright wrapper around a patched Firefox whose fingerprint is set in the C++ source
instead of being injected into the page. There is no JavaScript shim, so there is no
override for a page to find.

Useful for watches where the standard fetcher comes back with a challenge page, an
interstitial, or an empty body instead of the content you asked for -
[a troubleshooting order for exactly that](https://github.com/feder-cr/invisible_playwright/blob/main/docs/playwright-detected-as-bot.md)
is written up if you want to check what's actually failing before switching fetchers.

- Backend wrapper: [feder-cr/invisible_playwright](https://github.com/feder-cr/invisible_playwright)
- Backend engine and binaries: [feder-cr/firefox_antidetect_patch](https://github.com/feder-cr/firefox_antidetect_patch) (MPL-2.0, same licence as Firefox upstream)
- How the fingerprint surfaces work: [feder-cr.github.io/invisible_playwright](https://feder-cr.github.io/invisible_playwright/)

## Install

Add this to your changedetection.io `EXTRA_PACKAGES`. It works for the Docker image,
a pip install and the systemd setup:

```
EXTRA_PACKAGES="https://github.com/feder-cr/invisible_playwright-changedetectionio/archive/refs/heads/main.tar.gz"
```

This installs over plain HTTPS, so it works on the stock changedetection.io Docker
image, which does not ship `git`. A `git+https://...` reference fails there with
"Cannot find command 'git'".

The plugin pulls in `invisible_playwright` automatically, also over HTTPS. On first use
the patched Firefox is downloaded into the local cache
(`~/.cache/invisible-playwright/` on Linux,
`%LOCALAPPDATA%\invisible-playwright\Cache\` on Windows) and verified against its
SHA256.

After a restart, the stealth entry appears in the per-watch Fetch Method dropdown.

## System packages (Linux)

Firefox needs the usual set of Linux shared libraries, and the base changedetection.io
Docker image does not carry all of them. The plugin's `is_ready()` check names exactly
what is missing the first time you select the fetcher, but for convenience:

```
apt-get install -y libgtk-3-0 libdbus-glib-1-2 libxcomposite1 libxdamage1 \
                   libxrandr2 libxss1 libxtst6 libnss3 libcups2 \
                   libpangocairo-1.0-0 libasound2 libatk1.0-0 libatk-bridge2.0-0
```

Windows archives ship everything inside, so no system packages are needed there.

## Supported features

The same set as the standard Playwright fetcher:

- Browser steps (recorded interactions)
- Full-page screenshots
- xpath and CSS selector content extraction
- Custom JS execution
- Proxy configuration through the `playwright_proxy_*` environment variables

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

If you use a proxy, leave the browser's locale and timezone alone. The wrapper resolves
both from the address the session actually leaves through, and overriding one of them
by hand is [how a browser ends up contradicting its own exit point](https://github.com/feder-cr/invisible_playwright/blob/main/docs/timezone-proxy-mismatch.md).

## How this compares to the other fetchers

| Plugin | Engine | Where the fingerprint is set | Use when |
|---|---|---|---|
| `playwright` (built-in) | Chromium | nowhere | the default, and right for most sites |
| `changedetection.io-cloak-browser` | Chromium | C++ source | the target is happier with Chromium |
| **this plugin** | **Firefox** | **C++ source** | **the same goal, where Chromium-shaped traffic is treated as higher risk** |

The engine choice matters because a lot of automated traffic is Chromium, so some
filtering stacks weight it accordingly.
[Firefox is a smaller share of automation and a normal share of real browsing](https://github.com/feder-cr/invisible_playwright/blob/main/docs/firefox-vs-chromium-antidetect.md).

## License

MIT, see [LICENSE](LICENSE).

The patched Firefox binary is distributed under MPL-2.0, the same licence as Firefox
upstream.
