"""
Selenium Engine with multi-account session isolation.
Uses undetected-chromedriver to avoid Facebook bot detection.
Process registry: dict[account_id, SessionState] + asyncio.Lock per account
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import undetected_chromedriver as uc

    DRIVER_CLASS = uc.Chrome
    DRIVER_OPTIONS_CLASS = uc.ChromeOptions
except ImportError:
    # Fallback to standard selenium if undetected-chromedriver not installed
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    DRIVER_CLASS = webdriver.Chrome
    DRIVER_OPTIONS_CLASS = Options

logger = logging.getLogger(__name__)

PROFILES_DIR = Path.home() / ".fbgroupposter" / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SessionState:
    account_id: int
    driver: object = None
    status: str = "idle"  # idle | posting | error | closed
    started_at: float = field(default_factory=time.time)
    current_post_id: Optional[int] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def profile_dir(self) -> Path:
        return PROFILES_DIR / f"account_{self.account_id}"


class SeleniumEngine:
    """Manages multiple Chrome sessions, one per FB account."""

    def __init__(self):
        self._sessions: dict[int, SessionState] = {}
        self._ws_callbacks: list = []  # WebSocket screenshot callbacks

    def register_ws_callback(self, cb):
        """Register callback for screenshot streaming."""
        self._ws_callbacks.append(cb)

    def unregister_ws_callback(self, cb):
        """Remove a WebSocket callback to prevent memory leaks."""
        try:
            self._ws_callbacks.remove(cb)
        except ValueError:
            pass

    async def get_or_create_session(self, account_id: int) -> SessionState:
        if account_id not in self._sessions:
            self._sessions[account_id] = SessionState(account_id=account_id)
        return self._sessions[account_id]

    async def start_browser(self, account_id: int, headless: bool = False) -> bool:
        """Start Chrome for the given account. Runs in executor to avoid blocking."""
        session = await self.get_or_create_session(account_id)
        async with session.lock:
            if session.driver is not None:
                try:
                    _ = session.driver.current_url  # ping to check alive
                    return True
                except Exception:
                    session.driver = None

            profile_dir = session.profile_dir
            profile_dir.mkdir(parents=True, exist_ok=True)

            loop = asyncio.get_running_loop()
            try:
                driver = await loop.run_in_executor(
                    None, self._create_driver, str(profile_dir), headless
                )
                session.driver = driver
                session.status = "idle"
                logger.info(f"Chrome started for account {account_id}")
                return True
            except Exception as e:
                session.status = "error"
                logger.error(f"Failed to start Chrome for account {account_id}: {e}")
                return False

    def _create_driver(self, profile_dir: str, headless: bool):
        """Blocking: create Chrome driver. Call via run_in_executor."""
        options = DRIVER_OPTIONS_CLASS()
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-blink-features=AutomationControlled")
        if headless:
            options.add_argument("--headless=new")

        driver = DRIVER_CLASS(options=options)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return driver

    async def take_screenshot(self, account_id: int) -> Optional[str]:
        """Take screenshot and return as base64. Runs in executor."""
        session = self._sessions.get(account_id)
        if not session or not session.driver:
            return None
        loop = asyncio.get_running_loop()
        try:
            screenshot = await loop.run_in_executor(
                None, session.driver.get_screenshot_as_base64
            )
            return screenshot
        except Exception as e:
            logger.error(f"Screenshot failed for account {account_id}: {e}")
            return None

    async def broadcast_screenshot(self, account_id: int):
        """Take screenshot and broadcast to all WS clients."""
        data = await self.take_screenshot(account_id)
        if data:
            msg = {"type": "SCREENSHOT", "data": data, "account_id": account_id}
            for cb in self._ws_callbacks:
                try:
                    await cb(msg)
                except Exception:
                    pass

    async def post_to_group(
        self,
        account_id: int,
        group_url: str,
        content: str,
        images: list = None,
        post_record_id: int = None,
        platform: str = "fb",
    ) -> dict:
        """Post to a group/community. Returns {'success': bool, 'post_url': str, 'error': str}"""
        session = self._sessions.get(account_id)
        if not session or not session.driver:
            raise RuntimeError(f"Account {account_id} session not available")

        loop = asyncio.get_running_loop()

        _POST_HANDLERS = {
            "fb": self._do_post,
            "threads": self._do_post_threads,
            "x": self._do_post_x,
            "instagram": self._do_post_instagram,
        }
        handler = _POST_HANDLERS.get(platform, self._do_post)

        try:
            # All handlers are synchronous blocking calls — run via executor
            result = await loop.run_in_executor(
                None,
                lambda: handler(
                    session.driver, group_url, content, images or [], post_record_id
                ),
            )
            # Screenshot after post
            await self.broadcast_screenshot(account_id)
            return result
        except Exception as e:
            logger.error(
                f"Post failed for account {account_id} -> {group_url} (platform={platform}): {e}"
            )
            return {"success": False, "error": str(e)}

    def _do_post(
        self, driver, group_url: str, content: str, images: list, post_record_id=None
    ) -> dict:
        """Blocking: perform the actual Facebook post. Call via run_in_executor."""
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            driver.get(group_url)
            time.sleep(2 + (hash(group_url) % 3) * 0.5)  # randomized delay 2-3.5s

            wait = WebDriverWait(driver, 15)

            # Multiple selectors for FB post composer (FB changes these frequently)
            composer_selectors = [
                "//div[@role='button' and contains(@aria-label,'write')]",
                "//div[contains(@data-testid,'status-update')]",
                "//span[contains(text(),'Write something')]/..",
                "//span[contains(text(),'說些什麼')]/..",
            ]

            composer = None
            for sel in composer_selectors:
                try:
                    composer = wait.until(EC.element_to_be_clickable((By.XPATH, sel)))
                    break
                except Exception:
                    continue

            if not composer:
                return {"success": False, "error": "Could not find post composer"}

            composer.click()
            time.sleep(1)

            # Find textarea and type content
            text_area_selectors = [
                "//div[@role='textbox' and @contenteditable='true']",
                '//div[@aria-label="What\'s on your mind?"]',
                "//div[contains(@aria-label,'write')][@contenteditable='true']",
            ]

            text_area = None
            for sel in text_area_selectors:
                try:
                    text_area = wait.until(
                        EC.presence_of_element_located((By.XPATH, sel))
                    )
                    break
                except Exception:
                    continue

            if not text_area:
                return {"success": False, "error": "Could not find text area"}

            text_area.click()
            from selenium.webdriver.common.action_chains import ActionChains

            actions = ActionChains(driver)
            # Type with slight delays to simulate human
            for chunk in [content[i : i + 50] for i in range(0, len(content), 50)]:
                actions.send_keys(chunk)
                actions.pause(0.05 + (hash(chunk) % 10) * 0.01)
            actions.perform()
            time.sleep(1)

            # Find and click Post button
            post_btn_selectors = [
                "//div[@aria-label='Post' and @role='button']",
                "//div[@aria-label='貼文' and @role='button']",
                "//button[contains(@type,'submit')]",
            ]

            post_btn = None
            for sel in post_btn_selectors:
                try:
                    post_btn = wait.until(EC.element_to_be_clickable((By.XPATH, sel)))
                    break
                except Exception:
                    continue

            if not post_btn:
                return {"success": False, "error": "Could not find Post button"}

            post_btn.click()
            time.sleep(3)  # Wait for post to submit

            current_url = driver.current_url
            return {
                "success": True,
                "post_url": current_url if "facebook.com" in current_url else None,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_post_threads(self, driver, group_url, content, images, post_record_id=None):
        """Blocking: post to Threads. group_url is a threads.net profile or hashtag page URL."""
        import time
        import random

        try:
            driver.get("https://www.threads.net/")
            time.sleep(3)

            compose_selectors = [
                'a[aria-label="New thread"]',
                'a[href="/compose"]',
                '[aria-label="Create"]',
                '[aria-label="新貼文"]',
                'div[role="button"][aria-label*="post"]',
                'div[role="button"][aria-label*="thread"]',
            ]
            compose_btn = None
            for selector in compose_selectors:
                try:
                    compose_btn = driver.find_element("css selector", selector)
                    if compose_btn:
                        break
                except Exception:
                    continue

            if not compose_btn:
                try:
                    from selenium.webdriver.common.by import By

                    compose_btn = driver.find_element(By.XPATH, '//a[@href="/compose"]')
                except Exception:
                    return {
                        "success": False,
                        "error": "Threads compose button not found - UI may have changed",
                    }

            compose_btn.click()
            time.sleep(2)

            text_area_selectors = [
                '[aria-label="Start a thread"]',
                '[aria-label="開始討論串"]',
                '[contenteditable="true"]',
                'div[role="textbox"]',
            ]
            text_area = None
            for selector in text_area_selectors:
                try:
                    text_area = driver.find_element("css selector", selector)
                    if text_area:
                        break
                except Exception:
                    continue

            if not text_area:
                return {"success": False, "error": "Threads text area not found"}

            text_area.click()
            time.sleep(0.5)
            for char in content:
                text_area.send_keys(char)
                time.sleep(random.uniform(0.02, 0.08))
            time.sleep(1)

            post_selectors = [
                'div[role="button"][aria-label="Post"]',
                'button[type="submit"]',
                'div[role="button"][aria-label="發佈"]',
            ]
            post_btn = None
            for selector in post_selectors:
                try:
                    post_btn = driver.find_element("css selector", selector)
                    if post_btn:
                        break
                except Exception:
                    continue

            if not post_btn:
                try:
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC

                    post_btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable(
                            (
                                By.XPATH,
                                '//div[@role="button" and (text()="Post" or text()="發佈")]',
                            )
                        )
                    )
                except Exception:
                    return {"success": False, "error": "Threads post button not found"}

            post_btn.click()
            time.sleep(3)
            return {
                "success": True,
                "post_url": None,
            }  # Threads permalink not easily retrievable

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_post_x(self, driver, group_url, content, images, post_record_id=None):
        """Blocking: post to X (Twitter). group_url can be x.com/home or x.com/i/communities/xxx."""
        import time
        import random

        try:
            is_community = "communities" in (group_url or "")

            if is_community and group_url:
                driver.get(group_url)
                time.sleep(3)
                community_compose_selectors = [
                    '[data-testid="community-tweet-button"]',
                    'a[href*="/communities"][aria-label*="Tweet"]',
                ]
                for selector in community_compose_selectors:
                    try:
                        btn = driver.find_element("css selector", selector)
                        if btn:
                            btn.click()
                            time.sleep(1)
                            break
                    except Exception:
                        continue
            else:
                driver.get("https://x.com/home")
                time.sleep(3)

            compose_selectors = [
                '[data-testid="tweetTextarea_0"]',
                'div[aria-label="Tweet text"]',
                'div[aria-label="Post text"]',
                '[contenteditable="true"][aria-multiline="true"]',
            ]
            text_area = None
            for selector in compose_selectors:
                try:
                    text_area = driver.find_element("css selector", selector)
                    if text_area:
                        break
                except Exception:
                    continue

            if not text_area:
                try:
                    placeholder = driver.find_element(
                        "css selector", '[data-testid="tweetTextarea_0_label"]'
                    )
                    placeholder.click()
                    time.sleep(1)
                    text_area = driver.find_element(
                        "css selector", '[data-testid="tweetTextarea_0"]'
                    )
                except Exception:
                    return {"success": False, "error": "X compose text area not found"}

            text_area.click()
            time.sleep(0.5)
            # Longer delays — X is more sensitive to automation
            for char in content:
                text_area.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            time.sleep(2)

            post_selectors = [
                '[data-testid="tweetButtonInline"]',
                '[data-testid="tweetButton"]',
                'div[role="button"][data-testid*="tweet"]',
            ]
            post_btn = None
            for selector in post_selectors:
                try:
                    post_btn = driver.find_element("css selector", selector)
                    if post_btn and post_btn.is_enabled():
                        break
                    post_btn = None
                except Exception:
                    continue

            if not post_btn:
                return {"success": False, "error": "X post button not found"}

            post_btn.click()
            time.sleep(4)

            try:
                current_url = driver.current_url
                post_url = current_url if "status" in current_url else None
            except Exception:
                post_url = None

            return {"success": True, "post_url": post_url}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_post_instagram(
        self, driver, group_url, content, images, post_record_id=None
    ):
        """Blocking: post to Instagram. REQUIRES at least one image."""
        import time
        import os

        # Ray M3: Guard — Instagram requires image
        if not images:
            return {
                "success": False,
                "error": "Instagram requires at least one image. Please add an image to your post.",
            }

        # HIGH RISK: Instagram Selenium automation is subject to frequent UI changes.
        # Spike test required before production use.
        try:
            driver.get("https://www.instagram.com/")
            time.sleep(3)

            create_selectors = [
                'a[aria-label="New post"]',
                'svg[aria-label="New post"]',
                '[aria-label="建立"]',
                'a[href="/create/select/"]',
            ]
            create_btn = None
            for selector in create_selectors:
                try:
                    create_btn = driver.find_element("css selector", selector)
                    if create_btn:
                        break
                except Exception:
                    continue

            if not create_btn:
                return {
                    "success": False,
                    "error": "Instagram create post button not found - spike test required",
                }

            create_btn.click()
            time.sleep(2)

            image_path = images[0]
            if not os.path.exists(image_path):
                return {
                    "success": False,
                    "error": f"Image file not found: {image_path}",
                }

            try:
                file_inputs = driver.find_elements("css selector", 'input[type="file"]')
                if not file_inputs:
                    return {
                        "success": False,
                        "error": "Instagram file input not found - spike test required",
                    }
                file_input = file_inputs[0]
                driver.execute_script(
                    "arguments[0].style.display='block';"
                    "arguments[0].style.opacity='1';"
                    "arguments[0].style.position='fixed';"
                    "arguments[0].style.top='0';"
                    "arguments[0].style.left='0';"
                    "arguments[0].style.zIndex='9999';",
                    file_input,
                )
                time.sleep(0.5)
                file_input.send_keys(os.path.abspath(image_path))
                time.sleep(3)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Instagram file upload failed: {e}. Spike test required.",
                }

            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            # Click through crop → filter → caption dialogs
            for _step in range(2):
                try:
                    next_btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, '//button[text()="Next" or text()="下一步"]')
                        )
                    )
                    next_btn.click()
                    time.sleep(2)
                except Exception:
                    break

            # Add caption (optional)
            try:
                caption_area = driver.find_element(
                    "css selector",
                    '[aria-label="Write a caption..."], [aria-label="撰寫說明文字..."], div[role="textbox"][contenteditable]',
                )
                caption_area.click()
                import random

                for char in content:
                    caption_area.send_keys(char)
                    time.sleep(random.uniform(0.02, 0.08))
                time.sleep(1)
            except Exception:
                pass

            try:
                share_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, '//button[text()="Share" or text()="分享"]')
                    )
                )
                share_btn.click()
                time.sleep(4)
            except Exception:
                return {"success": False, "error": "Instagram share button not found"}

            return {
                "success": True,
                "post_url": None,
            }  # Instagram permalink not easily retrievable

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ────────────────────────────────────────────────────────────
    # Interactive login
    # ────────────────────────────────────────────────────────────

    # Cookie names that indicate a logged-in session per platform.
    _LOGIN_COOKIE_MARKERS = {
        "fb": ["c_user", "xs"],
        "threads": ["sessionid", "ig_did"],
        "instagram": ["sessionid", "ds_user_id"],
        "x": ["auth_token", "twid"],
    }

    _LOGIN_URLS = {
        "fb": "https://www.facebook.com/login",
        "threads": "https://www.threads.net/login",
        "instagram": "https://www.instagram.com/accounts/login/",
        "x": "https://x.com/login",
    }

    async def interactive_login(
        self, account_id: int, platform: str = "fb", timeout_sec: int = 600
    ) -> dict:
        """Open a visible Chrome window pointed at the platform login page, then poll for the
        login-marker cookie. When detected, snapshot the cookies and return them as a JSON
        string the caller can persist.

        Returns:
          {"success": True, "cookies_json": "...", "platform": "fb"}  on success
          {"success": False, "error": "..."}                          on failure / timeout
        """
        import json as _json

        if platform not in self._LOGIN_COOKIE_MARKERS:
            return {"success": False, "error": f"Unsupported platform: {platform}"}

        ok = await self.start_browser(account_id, headless=False)
        if not ok:
            return {"success": False, "error": "Failed to start Chrome"}

        session = self._sessions[account_id]
        loop = asyncio.get_running_loop()

        def _navigate():
            session.driver.get(self._LOGIN_URLS[platform])

        await loop.run_in_executor(None, _navigate)

        markers = self._LOGIN_COOKIE_MARKERS[platform]
        deadline = time.time() + timeout_sec

        async def _poll_for_login():
            while time.time() < deadline:
                try:
                    cookies = await loop.run_in_executor(
                        None, session.driver.get_cookies
                    )
                    names = {c["name"] for c in cookies}
                    if any(m in names for m in markers):
                        return cookies
                except Exception as e:
                    logger.warning(f"interactive_login poll error: {e}")
                await asyncio.sleep(2)
            return None

        cookies = await _poll_for_login()
        if cookies is None:
            return {
                "success": False,
                "error": f"Login not detected within {timeout_sec}s",
            }

        return {
            "success": True,
            "platform": platform,
            "cookies_json": _json.dumps(cookies),
            "cookie_count": len(cookies),
        }

    async def close_session(self, account_id: int):
        session = self._sessions.get(account_id)
        if session and session.driver:
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, session.driver.quit)
            except Exception:
                pass
            session.driver = None
            session.status = "closed"

    async def get_status(self) -> dict:
        return {
            acc_id: {
                "status": s.status,
                "started_at": s.started_at,
                "current_post_id": s.current_post_id,
            }
            for acc_id, s in self._sessions.items()
        }


# Singleton
selenium_engine = SeleniumEngine()
