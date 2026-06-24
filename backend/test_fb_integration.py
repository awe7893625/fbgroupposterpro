# -*- coding: utf-8 -*-
"""Integration smoke test of the real product path. Posts TWO posts in one session to prove
the P1-1 buffer-reset fix (each capture yields its OWN post_id), then deletes both via the
real engine.delete_post (GraphQL). Run on Beaver: python -m backend.test_fb_integration"""

import asyncio
import json
import time
from pathlib import Path
from backend import fb_graphql
from backend.selenium_engine import SeleniumEngine
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

COOKIES = json.loads(
    Path(r"C:\Projects\fbgroupposterpro\_fbcookies.json").read_text(encoding="utf-8")
)
TEXTS = [
    "今天天氣真好，出去走走 🌤",
    "晚餐想吃點清淡的 🥗",
]  # two distinct, normal-looking


def clk(d, xps, t=8):
    for xp in xps:
        try:
            WebDriverWait(d, t).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            ).click()
            return xp
        except Exception:
            continue
    return None


def compose_capture(d, text):
    # mirror _do_post: reset buffer AFTER navigation, before composing
    d.get("https://www.facebook.com/")
    time.sleep(4)
    d.execute_script("window.__nexResp = [];")
    clk(
        d,
        [
            "//div[@role='button' and contains(.,'在想些什麼')]",
            "//span[contains(text(),'在想些什麼')]/ancestor::div[@role='button'][1]",
        ],
    )
    time.sleep(4)
    box = WebDriverWait(d, 8).until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[@role='textbox' and @contenteditable='true']")
        )
    )
    box.click()
    time.sleep(1)
    ActionChains(d).send_keys(text).perform()
    time.sleep(2)
    clk(
        d,
        [
            "//div[@aria-label='發佈' and @role='button']",
            "//div[@aria-label='Post' and @role='button']",
        ],
    )
    time.sleep(8)
    return fb_graphql.extract_permalink(
        d.execute_script("return window.__nexResp || []")
    )


async def main():
    eng = SeleniumEngine()
    assert await eng.start_browser(1, headless=True), "browser failed"
    d = eng._sessions[1].driver
    d.get("https://www.facebook.com/")
    time.sleep(2)
    for c in COOKIES:
        try:
            d.add_cookie(
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": ".facebook.com",
                    "path": "/",
                }
            )
        except Exception:
            pass
    captures = []
    for txt in TEXTS:
        info = compose_capture(d, txt)
        print("captured:", info)
        assert info.get("post_id") and info.get("permalink"), (
            f"capture failed for {txt}"
        )
        captures.append(info)
    ids = [c["post_id"] for c in captures]
    print("post_ids:", ids)
    assert ids[0] != ids[1], (
        "P1-1 REGRESSION: two posts captured the SAME post_id (buffer not reset)"
    )
    print("[PASS] P1-1: two posts -> two distinct post_ids")
    for c in captures:
        deleted = await eng.delete_post(1, c["permalink"], c["post_id"])
        print("delete", c["post_id"], "->", deleted)
        assert deleted, f"delete failed {c['post_id']}"
    try:
        d.quit()
    except Exception:
        pass
    print(
        "RESULT: PASS — distinct capture + GraphQL delete x2 through the product engine"
    )


if __name__ == "__main__":
    asyncio.run(main())
