"""
Free cloud LLM client for FBGroupPosterPro.

串免費雲端 AI 模型產生房仲文案 — 成本 ≈ $0。
Fallback chain (fastest free first):
    1. Groq   (llama-3.3-70b-versatile)  ~1-2s, OpenAI-compatible
    2. Gemini (2.5-flash)                fallback
    3. OpenRouter free                   last resort

Keys are read from the environment (GROQ_API_KEY / GEMINI_API_KEY /
OPENROUTER_API_KEY). The desktop product never ships keys: on a customer
machine these are absent and ai.py falls back to the central proxy.

Public API:
    free_llm_available() -> bool
    await generate_listing_copy(product, style, variant_count) -> list[str]
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Optional 簡→繁(台灣用語) post-process. Some free models (e.g. llama-3.3-70b)
# occasionally leak Simplified characters; OpenCC s2twp normalises them.
try:
    from opencc import OpenCC

    _CC: Optional["OpenCC"] = OpenCC("s2twp")
except Exception:  # noqa: BLE001 - opencc optional; degrade gracefully
    _CC = None


# Free models occasionally leak a stray Korean (Hangul) character mid-word
# (e.g. "投資" → "투資"). Taiwan real-estate copy never legitimately contains Hangul,
# so stripping the Hangul block is safe and removes that noise.
_HANGUL_RE = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏ꥠ-꥿]")


def _to_traditional(text: str) -> str:
    if not text:
        return text
    if _CC is not None:
        try:
            text = _CC.convert(text)
        except Exception:  # noqa: BLE001
            pass
    return _HANGUL_RE.sub("", text)


_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

_GROQ_MODEL = os.getenv("FBP_GROQ_MODEL", "llama-3.3-70b-versatile")
_GEMINI_MODEL = os.getenv("FBP_GEMINI_MODEL", "gemini-2.5-flash")
_OPENROUTER_MODEL = os.getenv(
    "FBP_OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"
)

_TIMEOUT = aiohttp.ClientTimeout(total=25)

_STYLE_GUIDE = {
    "professional": "專業、可信、條理分明，像資深房仲。",
    "warm": "溫暖、生活感，讓人想像入住後的畫面。",
    "punchy": "短句、有節奏、emoji 點綴，吸引滑手機的人停下來。",
    "investment": "強調增值、收租、地段紅利，對投資客說話。",
}


def free_llm_available() -> bool:
    """True if at least one free provider key is configured."""
    return bool(_GROQ_API_KEY or _GEMINI_API_KEY or _OPENROUTER_API_KEY)


def _build_prompt(product: dict, style: str, variant_count: int) -> str:
    style_hint = _STYLE_GUIDE.get(style, _STYLE_GUIDE["professional"])
    facts = json.dumps(product, ensure_ascii=False, indent=2)
    contact = product.get("agent") or product.get("agentName") or ""
    phone = product.get("agentPhone") or product.get("phone") or ""
    contact_line = (f"{contact} {phone}").strip() or "私訊預約看屋"
    return f"""你是台灣頂尖房仲社群小編，專門寫 Facebook 房屋買賣社團的貼文。

物件資料（JSON，可能有缺漏，缺的別亂編）：
{facts}

寫作風格：{style_hint}

規則：
- 用台灣口語繁體中文，不要中國用語。
- 開頭一句要能在動態牆上抓住眼球（痛點 / 亮點 / 數字）。
- 中段條列 3-5 個賣點（坪數、格局、樓層、生活機能、學區、交通），只用資料裡有的事實。
- 結尾務必帶看屋行動呼籲 + 聯絡資訊：{contact_line}。
- 不得誇大不實、不得保證增值、不得寫資料裡沒有的設施（廣告不實會吃罰單）。
- 每篇 120-220 字，可用換行與少量 emoji，但別洗版。
- 產生 {variant_count} 個「明顯不同」的版本（不同開頭、不同切角），不要只改幾個字。

只輸出 JSON：{{"variants": ["第一版全文", "第二版全文", ...]}}，不要任何其他文字。"""


def _parse_variants(text: str, want: int) -> List[str]:
    """Extract variants from a model reply that should be JSON but may be dirty."""
    if not text:
        return []
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        v = json.loads(text).get("variants")
        if isinstance(v, list) and v:
            return [str(x).strip() for x in v if str(x).strip()][:want]
    except (json.JSONDecodeError, AttributeError):
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            v = json.loads(m.group(0)).get("variants")
            if isinstance(v, list) and v:
                return [str(x).strip() for x in v if str(x).strip()][:want]
        except (json.JSONDecodeError, AttributeError):
            pass
    return [text.strip()] if text.strip() else []


async def _call_groq(session: aiohttp.ClientSession, prompt: str) -> Optional[str]:
    if not _GROQ_API_KEY:
        return None
    async with session.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {_GROQ_API_KEY}"},
        json={
            "model": _GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "response_format": {"type": "json_object"},
        },
        timeout=_TIMEOUT,
    ) as r:
        if r.status != 200:
            logger.warning("groq %s: %s", r.status, (await r.text())[:160])
            return None
        data = await r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content")


async def _call_gemini(session: aiohttp.ClientSession, prompt: str) -> Optional[str]:
    if not _GEMINI_API_KEY:
        return None
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_GEMINI_MODEL}:generateContent?key={_GEMINI_API_KEY}"
    )
    async with session.post(
        url,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.9,
                "responseMimeType": "application/json",
            },
        },
        timeout=_TIMEOUT,
    ) as r:
        if r.status != 200:
            logger.warning("gemini %s: %s", r.status, (await r.text())[:160])
            return None
        data = await r.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return None


async def _call_openrouter(
    session: aiohttp.ClientSession, prompt: str
) -> Optional[str]:
    if not _OPENROUTER_API_KEY:
        return None
    async with session.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {_OPENROUTER_API_KEY}"},
        json={
            "model": _OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
        },
        timeout=_TIMEOUT,
    ) as r:
        if r.status != 200:
            logger.warning("openrouter %s: %s", r.status, (await r.text())[:160])
            return None
        data = await r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content")


async def generate_listing_copy(
    product: dict, style: str = "professional", variant_count: int = 3
) -> List[str]:
    """
    Generate N FB listing copy variants from product data using free models.
    Returns [] if every free provider fails (caller should fall back to proxy).
    """
    variant_count = max(1, min(int(variant_count or 3), 5))
    prompt = _build_prompt(product, style, variant_count)

    async with aiohttp.ClientSession() as session:
        for name, fn in (
            ("groq", _call_groq),
            ("gemini", _call_gemini),
            ("openrouter", _call_openrouter),
        ):
            try:
                raw = await fn(session, prompt)
            except (aiohttp.ClientError, KeyError, IndexError, TypeError) as e:
                logger.warning("free_llm %s error: %s", name, e)
                raw = None
            if raw:
                variants = _parse_variants(raw, variant_count)
                if variants:
                    variants = [_to_traditional(v) for v in variants]
                    logger.info(
                        "free_llm: %s produced %d variants", name, len(variants)
                    )
                    return variants
    logger.warning("free_llm: all providers failed")
    return []
