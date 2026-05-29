"""changedetection.io fetcher backed by invisible_playwright (patched Firefox).

Mirrors the changedetection.io-cloak-browser plugin shape but swaps the
Chromium-side CloakBrowser for the Firefox-side invisible_playwright.

All `changedetectionio.content_fetchers.*` imports are deferred to inside
`register_content_fetcher()` to avoid the circular import documented in
pluggy_interface (load_setuptools_entrypoints loads this module before
content_fetchers is fully initialised).
"""
import asyncio
import ctypes.util
import gc
import json
import os
import sys
from urllib.parse import urlparse

from loguru import logger
from changedetectionio.pluggy_interface import hookimpl

_STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

# Linux shared libraries required by Firefox. Probed by `is_ready()` so the
# operator gets a clear message at startup instead of a cryptic Firefox crash
# on first navigation. Empty on non-Linux (Windows ships its own DLLs in the
# binary archive).
_LINUX_FIREFOX_LIBS = [
    "libgtk-3.so.0",
    "libdbus-glib-1.so.2",
    "libxcomposite",
    "libxdamage",
    "libxrandr",
    "libxss",
    "libxtst",
    "libnss3",
    "libcups",
    "libpangocairo-1.0",
    "libasound",
    "libatk-1.0",
    "libatk-bridge-2.0",
]


@hookimpl
def plugin_static_path():
    """Return this plugin's static files directory (logo etc)."""
    return _STATIC_DIR


@hookimpl
def register_content_fetcher():
    """Register the Invisible Firefox fetcher with changedetection.io.

    All content_fetchers imports are deferred to here to avoid the
    pluggy_interface circular import (load_setuptools_entrypoints loads
    this module before content_fetchers is fully initialised).
    """
    from changedetectionio.content_fetchers import (
        FAVICON_FETCHER_JS,
        INSTOCK_DATA_JS,
        SCREENSHOT_MAX_HEIGHT_DEFAULT,
        XPATH_ELEMENT_JS,
        visualselector_xpath_selectors,
    )
    from changedetectionio.content_fetchers.base import Fetcher, manage_user_agent
    from changedetectionio.content_fetchers.exceptions import (
        BrowserStepsStepException,
        EmptyReply,
        Non200ErrorCodeReceived,
        PageUnloadable,
        ScreenshotUnavailable,
    )
    from changedetectionio.content_fetchers.playwright import capture_full_page_async

    class fetcher(Fetcher):
        fetcher_description = "Invisible Firefox - Stealth (patched FF 150)"

        # The Invisible Firefox page is a standard Playwright Firefox page —
        # all browser-step / screenshot / xpath features work unchanged.
        supports_browser_steps = True
        supports_screenshots = True
        supports_xpath_element_data = True

        proxy = None

        def __init__(self, proxy_override=None, custom_browser_connection_url=None, **kwargs):
            super().__init__(**kwargs)

            # We launch a local browser per fetch. Remote CDP URLs aren't
            # applicable to Firefox (no CDP). Accepted for API compatibility.
            if custom_browser_connection_url:
                logger.warning(
                    "Invisible Firefox fetcher: custom_browser_connection_url is ignored — "
                    "Firefox is launched locally per fetch"
                )

            # Reuse the same playwright_proxy_* env var convention so users
            # don't have to learn a new one.
            proxy_args = {}
            for k in ('bypass', 'server', 'username', 'password'):
                v = os.getenv('playwright_proxy_' + k, False)
                if v:
                    proxy_args[k] = v.strip('"')
            if proxy_args:
                self.proxy = proxy_args

            if proxy_override:
                self.proxy = {'server': proxy_override}

            if self.proxy:
                parsed = urlparse(self.proxy.get('server', ''))
                if parsed.username:
                    self.proxy['username'] = parsed.username
                    self.proxy['password'] = parsed.password

        @classmethod
        def get_status_icon_data(cls):
            return {
                'group': 'plugin',
                'filename': 'invisible-firefox-logo.svg',
                'alt': 'Using Invisible Firefox (stealth)',
                'title': 'Invisible Firefox — Stealth Firefox 150',
            }

        @classmethod
        async def get_browsersteps_browser(cls, proxy=None, keepalive_ms=None):
            """Launch a local Invisible Firefox instance for the browser steps UI.

            Returns (browser, playwright_ctx). The playwright context is returned
            so the caller can close it cleanly; CloakBrowser returns None there
            because cloakbrowser owns its own playwright lifecycle, but
            invisible_playwright lets the caller drive vanilla Playwright.
            """
            from invisible_playwright import ensure_binary, get_default_stealth_prefs
            from playwright.async_api import async_playwright

            playwright_ctx = await async_playwright().start()
            launch_kwargs = {
                'executable_path': str(ensure_binary()),
                'firefox_user_prefs': get_default_stealth_prefs(),
                # headless=False keeps Firefox in real headed mode (coherent
                # fingerprint). The Docker image used to run changedetection
                # already provides a virtual display (Xvfb) so no extra
                # display management is needed.
                'headless': False,
            }
            if proxy:
                launch_kwargs['proxy'] = proxy
            browser = await playwright_ctx.firefox.launch(**launch_kwargs)
            return (browser, playwright_ctx)

        async def run(
            self,
            fetch_favicon=True,
            current_include_filters=None,
            empty_pages_are_a_change=False,
            ignore_status_codes=False,
            is_binary=False,
            request_body=None,
            request_headers=None,
            request_method=None,
            screenshot_format=None,
            timeout=None,
            url=None,
            watch_uuid=None,
        ):
            from invisible_playwright import ensure_binary, get_default_stealth_prefs
            from playwright.async_api import async_playwright
            import time

            self.delete_browser_steps_screenshots()
            self.watch_uuid = watch_uuid

            playwright_ctx = None
            browser = None
            context = None
            response = None

            try:
                playwright_ctx = await async_playwright().start()

                launch_kwargs = {
                    'executable_path': str(ensure_binary()),
                    'firefox_user_prefs': get_default_stealth_prefs(),
                    'headless': False,  # see get_browsersteps_browser comment
                }
                if self.proxy:
                    launch_kwargs['proxy'] = self.proxy

                browser = await playwright_ctx.firefox.launch(**launch_kwargs)

                # Standard Playwright BrowserContext — all features apply
                context = await browser.new_context(
                    accept_downloads=False,
                    bypass_csp=True,
                    extra_http_headers=request_headers or {},
                    ignore_https_errors=True,
                    service_workers=os.getenv('PLAYWRIGHT_SERVICE_WORKERS', 'allow'),
                    user_agent=manage_user_agent(headers=request_headers or {}),
                )

                self.page = await context.new_page()
                self.page.on(
                    "console",
                    lambda msg: logger.debug(
                        f"Invisible Firefox console: {url} {msg.type}: {msg.text} {msg.args}"
                    ),
                )

                from changedetectionio.browser_steps.browser_steps import (
                    steppable_browser_interface,
                )
                browsersteps_interface = steppable_browser_interface(start_url=url)
                browsersteps_interface.page = self.page

                response = await browsersteps_interface.action_goto_url(value=url)
                if response is None:
                    raise EmptyReply(url=url, status_code=None)

                try:
                    self.headers = await response.all_headers()
                except TypeError:
                    self.headers = response.all_headers()

                try:
                    if self.webdriver_js_execute_code and len(self.webdriver_js_execute_code):
                        await browsersteps_interface.action_execute_js(
                            value=self.webdriver_js_execute_code, selector=None
                        )
                except Exception as e:
                    logger.debug(f"Invisible Firefox > Error executing custom JS: {e}")
                    raise PageUnloadable(url=url, status_code=None, message=str(e))

                extra_wait = (
                    int(os.getenv("WEBDRIVER_DELAY_BEFORE_CONTENT_READY", 5))
                    + self.render_extract_delay
                )
                await self.page.wait_for_timeout(extra_wait * 1000)

                try:
                    self.status_code = response.status
                except Exception as e:
                    logger.critical(f"Invisible Firefox > Response had no status_code: {e}")
                    raise PageUnloadable(url=url, status_code=None, message=str(e))

                if fetch_favicon:
                    try:
                        self.favicon_blob = await self.page.evaluate(FAVICON_FETCHER_JS)
                    except Exception as e:
                        logger.error(
                            f"Invisible Firefox > Error fetching favicon: {e}, continuing."
                        )

                if self.status_code != 200 and not ignore_status_codes:
                    screenshot = await capture_full_page_async(
                        self.page,
                        screenshot_format=self.screenshot_format,
                        watch_uuid=watch_uuid,
                        lock_viewport_elements=self.lock_viewport_elements,
                    )
                    raise Non200ErrorCodeReceived(
                        url=url, status_code=self.status_code, screenshot=screenshot
                    )

                if not empty_pages_are_a_change and len((await self.page.content()).strip()) == 0:
                    raise EmptyReply(url=url, status_code=response.status)

                try:
                    if self.browser_steps:
                        try:
                            await self.iterate_browser_steps(start_url=url)
                        except BrowserStepsStepException:
                            raise
                        await self.page.wait_for_timeout(extra_wait * 1000)

                    now = time.time()
                    MAX_TOTAL_HEIGHT = int(
                        os.getenv("SCREENSHOT_MAX_HEIGHT", SCREENSHOT_MAX_HEIGHT_DEFAULT)
                    )

                    if current_include_filters is not None:
                        await self.page.evaluate(
                            f"var include_filters={json.dumps(current_include_filters)}"
                        )
                    else:
                        await self.page.evaluate("var include_filters=''")

                    self.xpath_data = await self.page.evaluate(
                        XPATH_ELEMENT_JS,
                        {
                            "visualselector_xpath_selectors": visualselector_xpath_selectors,
                            "max_height": MAX_TOTAL_HEIGHT,
                        },
                    )

                    self.instock_data = await self.page.evaluate(INSTOCK_DATA_JS)
                    self.content = await self.page.content()

                    logger.debug(
                        f"Invisible Firefox > Scraped xPath/instock data in {time.time() - now:.2f}s"
                    )

                    self.screenshot = await capture_full_page_async(
                        page=self.page,
                        screenshot_format=self.screenshot_format,
                        watch_uuid=watch_uuid,
                        lock_viewport_elements=self.lock_viewport_elements,
                    )
                    gc.collect()

                except ScreenshotUnavailable:
                    raise ScreenshotUnavailable(url=url, status_code=self.status_code)

            finally:
                # Triple cleanup with timeout — mirrors Cloak pattern. Each
                # close is wrapped so a hang at one layer doesn't block teardown
                # of the others.
                try:
                    if hasattr(self, 'page') and self.page:
                        await asyncio.wait_for(self.page.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Invisible Firefox > Timed out closing page for {url}")
                except Exception as e:
                    logger.warning(f"Invisible Firefox > Error closing page for {url}: {e}")
                finally:
                    self.page = None

                try:
                    if context:
                        await asyncio.wait_for(context.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Invisible Firefox > Timed out closing context for {url}")
                except Exception as e:
                    logger.warning(f"Invisible Firefox > Error closing context for {url}: {e}")

                try:
                    if browser:
                        await asyncio.wait_for(browser.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Invisible Firefox > Timed out closing browser for {url}")
                except Exception as e:
                    logger.warning(f"Invisible Firefox > Error closing browser for {url}: {e}")

                try:
                    if playwright_ctx:
                        await asyncio.wait_for(playwright_ctx.stop(), timeout=5.0)
                except Exception as e:
                    logger.warning(f"Invisible Firefox > Error stopping playwright: {e}")

                gc.collect()

        async def quit(self, watch=None):
            # Already cleaned up in run()'s finally. Idempotent no-op.
            pass

        def get_error(self):
            return self.error

        def get_last_status_code(self):
            return self.status_code

        def is_ready(self):
            """Verify both the Python package and the binary's system deps.

            Differentiates from the cloak-browser fetcher (which only does
            an import check) by also probing for the Linux shared libraries
            Firefox needs — exactly the operator footgun dgtlmoon flagged
            in dgtlmoon/changedetection.io discussion #4187.
            """
            # 1. Python package + binary cache marker
            try:
                from invisible_playwright import ensure_binary  # noqa: F401
            except ImportError:
                logger.error(
                    "Invisible Firefox fetcher: 'invisible_playwright' package is not installed. "
                    "Install via EXTRA_PACKAGES=git+https://github.com/feder-cr/invisible_playwright.git"
                )
                return False

            # 2. Probe system libs on Linux. Skipped on Windows (the binary
            # archive ships everything it needs) and macOS (not supported yet).
            if sys.platform.startswith("linux"):
                missing = [
                    lib for lib in _LINUX_FIREFOX_LIBS if not ctypes.util.find_library(lib.replace("lib", "").split(".")[0])
                ]
                if missing:
                    logger.error(
                        f"Invisible Firefox fetcher: missing Linux libraries: {missing}. "
                        f"Add to your Docker image / system packages: "
                        f"apt-get install -y libgtk-3-0 libdbus-glib-1-2 libxcomposite1 "
                        f"libxdamage1 libxrandr2 libxss1 libxtst6 libnss3 libcups2 "
                        f"libpangocairo-1.0-0 libasound2 libatk1.0-0 libatk-bridge2.0-0"
                    )
                    return False

            return True

    return ('html_invisible_firefox', fetcher)
