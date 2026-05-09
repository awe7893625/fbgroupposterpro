"""
Real estate listing scrapers (591, HouseBox).

Ported from FBGroupPoster v1 (Chrome MV3 extension) to Python+Selenium. We
inject the same JS extractors that proved reliable in v1, but run them via
selenium_engine.execute_script inside the user's logged-in Chrome profile.

Public API:
    scrape_realestate(account_id, url) -> dict
    generate_professional_post(data) -> str
    process_spintax(text) -> str
    smart_delay(group_count) -> int  (seconds, with jitter)
"""

from __future__ import annotations

import asyncio
import random
import re
import time
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# JS extractors — keep these as plain strings so we can inject them verbatim
# via Selenium's execute_script. They mirror v1's scrape591Page / scrapeHouseboxPage.
# ─────────────────────────────────────────────────────────────────────────────

SCRAPE_591_JS = r"""
return (function(){
  var data = {
    title: '', price: '', priceUnit: '', address: '', description: '',
    images: [], area: '', rooms: '', floor: '', type: '', source: window.location.href,
    platform: '591', unitPrice: '', mainArea: '', subArea: '', totalFloors: '',
    buildingType: '', agent: '', agentPhone: '', company: '', propertyId: ''
  };

  var url = window.location.href;
  data.type = (url.indexOf('sale.591') >= 0 || url.indexOf('home/house') >= 0) ? '出售'
            : (url.indexOf('rent.591') >= 0 || url.indexOf('rentDetail') >= 0) ? '出租'
            : '房屋';

  var ogTitle = document.querySelector('meta[property="og:title"]');
  if (ogTitle && ogTitle.content) {
    data.title = ogTitle.content.replace(/\s*-\s*591.*$/, '').trim();
  }
  if (!data.title && document.title) {
    data.title = document.title.replace(/\s*-\s*591.*$/, '').trim();
  }
  if (!data.title) {
    var titleSels = ['h1.detail-title-box', '.detail-title h1', 'h1'];
    for (var i=0; i<titleSels.length; i++) {
      var el = document.querySelector(titleSels[i]);
      if (el && el.textContent.trim()) { data.title = el.textContent.trim(); break; }
    }
  }

  var priceSels = ['.info-price .price', '.detail-price .price', '.price-current', '.price'];
  for (var j=0; j<priceSels.length; j++) {
    var pel = document.querySelector(priceSels[j]);
    if (pel && pel.textContent.trim()) {
      var raw = pel.textContent.trim().replace(/\s+/g, '');
      var pm = raw.match(/([\d,]+)\s*萬/);
      if (pm) { data.price = pm[1]; data.priceUnit = '萬'; }
      else { data.price = raw; }
      break;
    }
  }
  if (!data.price) {
    var bm = document.body.textContent.match(/總價\s*[:：]?\s*([\d,]+)\s*萬/);
    if (bm) { data.price = bm[1]; data.priceUnit = '萬'; }
  }

  var addrSels = ['.info-addr-value', '.detail-addr', '.house-addr', '[class*="addr"]'];
  for (var k=0; k<addrSels.length; k++) {
    var ael = document.querySelector(addrSels[k]);
    if (ael && ael.textContent.trim()) { data.address = ael.textContent.trim(); break; }
  }

  var allText = document.body.textContent;
  var areaM = allText.match(/(\d+\.?\d*)\s*坪/);
  if (areaM) data.area = areaM[1] + '坪';
  var roomM = allText.match(/(\d+)\s*房\s*(\d+)\s*廳\s*(\d+)\s*衛/);
  if (roomM) data.rooms = roomM[1] + '房' + roomM[2] + '廳' + roomM[3] + '衛';
  var floorM = allText.match(/(\d+)\/(\d+)\s*樓/);
  if (floorM) {
    data.floor = floorM[1] + '樓';
    data.totalFloors = floorM[2];
  }
  var btM = allText.match(/(?:型\s*態|建物型態|類型)[：:\s]*(公寓|電梯大樓|透天|華廈|套房|別墅|店面|辦公)/);
  if (btM) data.buildingType = btM[1];

  var descParts = [];
  var nodes = document.querySelectorAll('.house-pattern .pattern li, .info-detail li, .detail-info li');
  for (var n=0; n<nodes.length; n++) {
    var t = nodes[n].textContent.trim();
    if (t) descParts.push(t);
  }
  var descSels = ['.house-pattern .pattern', '.info-detail-message', '.remark'];
  for (var d=0; d<descSels.length; d++) {
    var del = document.querySelector(descSels[d]);
    if (del && del.textContent.trim().length > 20) { descParts.push(del.textContent.trim()); break; }
  }
  data.description = descParts.join('\n');

  var seenUrls = {};
  var ogImg = document.querySelector('meta[property="og:image"]');
  if (ogImg && ogImg.content) {
    var s = ogImg.content;
    if (s.indexOf('//') === 0) s = 'https:' + s;
    seenUrls[s] = 1;
    data.images.push(s);
  }
  var imgSels = ['img[src*="img1.591"]', 'img[src*="img2.591"]', 'img[src*="img.591"]', '.swiper-slide img'];
  for (var ii=0; ii<imgSels.length; ii++) {
    var imgs = document.querySelectorAll(imgSels[ii]);
    for (var iii=0; iii<imgs.length; iii++) {
      var src = imgs[iii].getAttribute('data-src') || imgs[iii].getAttribute('data-original') || imgs[iii].src;
      if (src && src.indexOf('placeholder') < 0 && src.indexOf('logo') < 0 && src.indexOf('icon') < 0) {
        if (src.indexOf('//') === 0) src = 'https:' + src;
        if (!seenUrls[src]) { seenUrls[src] = 1; data.images.push(src); }
      }
    }
  }
  data.images = data.images.slice(0, 10);

  return data;
})();
"""


SCRAPE_HOUSEBOX_JS = r"""
return (function(){
  var data = {
    title: '', price: '', priceUnit: '萬', address: '', description: '',
    images: [], area: '', rooms: '', floor: '', type: '出售',
    source: window.location.href, platform: 'housebox',
    unitPrice: '', buildingType: '', mainArea: '', subArea: '',
    totalFloors: '', agent: '', agentPhone: '', company: '', propertyId: ''
  };

  var bodyText = document.body.innerText;

  var titleEl = document.querySelector('.s25b, .s19b');
  if (titleEl) data.title = titleEl.textContent.trim();

  var priceMatch = bodyText.match(/售\s*價[：:]\s*([\d,.]+)\s*萬/);
  if (priceMatch) { data.price = priceMatch[1]; data.priceUnit = '萬'; }
  if (!data.price) {
    var pm2 = bodyText.match(/([\d,.]+)\s*萬/);
    if (pm2) data.price = pm2[1];
  }

  var areaMatch = bodyText.match(/(?:權狀面積|登記坪數|總坪數)[：:\s]*([\d.]+)\s*坪/);
  if (areaMatch) data.area = areaMatch[1] + '坪';
  if (!data.area) {
    var am2 = bodyText.match(/([\d.]+)\s*坪/);
    if (am2) data.area = am2[1] + '坪';
  }

  var unitPriceMatch = bodyText.match(/單\s*價[：:]\s*([\d,.]+)\s*萬/);
  if (unitPriceMatch) data.unitPrice = unitPriceMatch[1] + '萬/坪';

  var mainAreaMatch = bodyText.match(/主建物[：:]\s*([\d.]+)\s*坪/);
  if (mainAreaMatch) data.mainArea = mainAreaMatch[1] + '坪';

  var subAreaMatch = bodyText.match(/附屬建物[：:]\s*([\d.]+)\s*坪/);
  if (subAreaMatch) data.subArea = subAreaMatch[1] + '坪';

  var roomMatch = bodyText.match(/(\d+房\d+廳\d+衛[\d陽台]*)/);
  if (roomMatch) data.rooms = roomMatch[1];

  var floorMatch = bodyText.match(/(\d+)\s*樓\s*[/／]\s*(\d+)\s*樓/);
  if (floorMatch) {
    data.floor = floorMatch[1] + '樓';
    data.totalFloors = floorMatch[2];
  }
  if (!data.floor) {
    var fm2 = bodyText.match(/(?:樓\s*層|所在樓層)[：:\s]*(\d+)/);
    if (fm2) data.floor = fm2[1] + '樓';
  }
  if (!data.totalFloors) {
    var tfM = bodyText.match(/(?:樓\s*高|總樓高|總樓層)[：:\s]*(\d+)/);
    if (tfM) data.totalFloors = tfM[1];
  }

  var buildingMatch = bodyText.match(/(?:型\s*態|建物型態|類型)[：:\s]*(公寓|電梯大樓|透天|華廈|套房|別墅|店面|辦公)/);
  if (buildingMatch) data.buildingType = buildingMatch[1];

  var addressMatch = bodyText.match(/([\u4e00-\u9fff]+[市縣][\u4e00-\u9fff]+[區鎮鄉][\u4e00-\u9fff]+[路街巷弄號樓\d]+)/);
  if (addressMatch) data.address = addressMatch[1];

  var phoneMatch = bodyText.match(/(09\d{2}[\s-]?\d{3}[\s-]?\d{3})/);
  if (phoneMatch) data.agentPhone = phoneMatch[1].replace(/[\s-]/g, '');

  var imgs = document.querySelectorAll('img[src*="house_photo"]');
  imgs.forEach(function(img){ data.images.push(img.src); });
  if (data.images.length === 0) {
    document.querySelectorAll('img').forEach(function(img){
      if (img.width > 100 && img.height > 100 &&
          img.src.indexOf('logo') < 0 && img.src.indexOf('icon') < 0) {
        data.images.push(img.src);
      }
    });
  }

  var idMatch = bodyText.match(/物件編號[：:]\s*(\S+)/);
  if (idMatch) data.propertyId = idMatch[1];

  if (bodyText.indexOf('月租') >= 0 || bodyText.indexOf('租金') >= 0) data.type = '出租';

  return data;
})();
"""


# ─────────────────────────────────────────────────────────────────────────────
# Top-level entry: scrape_realestate
# ─────────────────────────────────────────────────────────────────────────────


def _detect_platform(url: str) -> str | None:
    if "591.com.tw" in url or "591.com" in url:
        return "591"
    if "housebox.com.tw" in url:
        return "housebox"
    return None


async def scrape_realestate(account_id: int, url: str) -> dict:
    """Scrape a 591 or HouseBox listing using the account's Chrome profile.

    Returns:
        {"success": True, "data": {...listing fields..., "post_content": "..."}, "platform": "591"}
        {"success": False, "error": "..."}
    """
    from urllib.parse import urlparse

    if not url or not isinstance(url, str):
        return {"success": False, "error": "url is required"}

    # Reject non-http(s) schemes — file://, javascript:, data: would let a caller
    # exfiltrate local files or trigger arbitrary JS in the user's profile.
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {"success": False, "error": "Only http(s) URLs are supported"}

    platform = _detect_platform(url)
    if not platform:
        return {"success": False, "error": "Unsupported URL — must be 591 or HouseBox"}

    if platform == "591":
        wait_sec = 7.0 + random.uniform(1.0, 3.0)
        js = SCRAPE_591_JS
    else:
        wait_sec = 3.0 + random.uniform(0.5, 1.5)
        js = SCRAPE_HOUSEBOX_JS

    # Lazy import to avoid circular dependency at module load time.
    from ..selenium_engine import selenium_engine

    ok = await selenium_engine.start_browser(account_id, headless=True)
    if not ok:
        return {"success": False, "error": "Failed to start Chrome"}

    session = selenium_engine._sessions[account_id]
    loop = asyncio.get_running_loop()

    def _do_scrape():
        session.driver.get(url)
        time.sleep(wait_sec)
        return session.driver.execute_script(js)

    try:
        data = await loop.run_in_executor(None, _do_scrape)
    except Exception as e:
        logger.error("scrape_realestate failed: %s", e)
        return {"success": False, "error": str(e)}

    if not data or not data.get("title"):
        return {
            "success": False,
            "error": "Could not extract listing data — page may not have rendered",
        }

    data["post_content"] = generate_professional_post(data)
    return {"success": True, "platform": platform, "data": data}


# ─────────────────────────────────────────────────────────────────────────────
# Post-content generator (Python port of v1 generateProfessionalPostContent)
# ─────────────────────────────────────────────────────────────────────────────


def generate_professional_post(data: dict) -> str:
    """FB-ready post template — preserves v1 visual style verbatim."""
    lines: list[str] = []

    title = data.get("title") or ""
    listing_type = data.get("type") or "出售"
    type_emoji = "🏠" if listing_type == "出租" else "🔥"
    type_label = "急租" if listing_type == "出租" else "急售"
    lines.append(f"{type_emoji}{type_emoji}{type_emoji} {type_label}｜{title}")
    lines.append("")

    address = data.get("address") or ""
    if address:
        safe_addr = re.sub(r"\d+巷.*$", "", address)
        safe_addr = re.sub(r"\d+弄.*$", "", safe_addr)
        safe_addr = re.sub(r"\d+號.*$", "", safe_addr)
        lines.append(f"📍 {safe_addr}")

    if data.get("price"):
        price_label = "月租" if listing_type == "出租" else "售價"
        lines.append(
            f"💰 {price_label}：{data['price']} {data.get('priceUnit') or '萬'}"
        )
    if data.get("unitPrice"):
        lines.append(f"📊 單價：{data['unitPrice']}")

    lines.append("")
    lines.append("━━━━━ 物件資訊 ━━━━━")
    if data.get("area"):
        lines.append(f"📐 權狀：{data['area']}")
    if data.get("mainArea"):
        lines.append(f"🏗️ 主建物：{data['mainArea']}")
    rooms = data.get("rooms") or ""
    if rooms:
        lines.append(f"🛏️ 格局：{rooms}")
    floor = data.get("floor") or ""
    if floor:
        floor_str = (
            f"{floor}/{data['totalFloors']}層" if data.get("totalFloors") else floor
        )
        lines.append(f"🏢 樓層：{floor_str}")
    building_type = data.get("buildingType") or ""
    if building_type:
        lines.append(f"🏠 型態：{building_type}")

    lines.append("")

    highlights: list[str] = []
    if "捷運" in title or "捷運" in address:
        highlights.append("近捷運交通便利")
    if "邊間" in title:
        highlights.append("邊間採光通風佳")
    if "車位" in title or "停車" in title:
        highlights.append("含車位")
    if building_type == "電梯大樓":
        highlights.append("電梯大樓管理完善")
    if "3房" in rooms:
        highlights.append("三房格局適合小家庭")
    if "2房" in rooms:
        highlights.append("兩房格局精緻好整理")
    floor_num = None
    if floor:
        m = re.match(r"(\d+)", floor)
        if m:
            try:
                floor_num = int(m.group(1))
            except ValueError:
                floor_num = None
    if floor_num is not None and floor_num <= 3 and building_type == "公寓":
        highlights.append("低樓層進出方便")

    if highlights:
        for h in highlights:
            lines.append(f"✅ {h}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("📞 歡迎來電預約看屋")
    if data.get("agentPhone"):
        lines.append(f"📱 {data['agentPhone']}")
    if data.get("company"):
        lines.append(f"🏢 {data['company']}")
    lines.append("💬 私訊即可安排看屋時間")
    lines.append("")

    tags: list[str] = []
    if address:
        district_match = re.search(r"([\u4e00-\u9fff]+[區鎮鄉])", address)
        if district_match:
            tags.append(f"#{district_match.group(1)}")
        city_match = re.search(r"([\u4e00-\u9fff]+[市縣])", address)
        if city_match:
            tags.append(f"#{city_match.group(1)}買房")
    if listing_type == "出售":
        tags.append("#買房")
    if listing_type == "出租":
        tags.append("#租屋")
    if rooms:
        room_short = re.sub(r"\d+廳.*", "", rooms)
        tags.append(f"#{room_short}房")
    if building_type:
        tags.append(f"#{building_type}")
    tags.append("#房仲推薦")

    lines.append(" ".join(tags))
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Spintax + smart delay (used by post scheduler too)
# ─────────────────────────────────────────────────────────────────────────────

_SPINTAX_RE = re.compile(r"\{([^{}]+)\}")


def process_spintax(text: str) -> str:
    """Expand {a|b|c} options recursively (innermost first)."""
    safety = 0
    while "{" in text and "}" in text and safety < 20:
        text = _SPINTAX_RE.sub(lambda m: random.choice(m.group(1).split("|")), text)
        safety += 1
    return text


def smart_delay(group_count: int) -> int:
    """Return a delay in seconds with ±20% jitter, scaling with group count."""
    if group_count < 10:
        min_s, max_s = 60, 120
    elif group_count < 30:
        min_s, max_s = 120, 180
    elif group_count < 50:
        min_s, max_s = 180, 300
    elif group_count < 100:
        min_s, max_s = 300, 600
    else:
        min_s, max_s = 600, 1200
    base = min_s + random.random() * (max_s - min_s)
    jitter = base * 0.2 * (random.random() * 2 - 1)
    return max(min_s, round(base + jitter))
