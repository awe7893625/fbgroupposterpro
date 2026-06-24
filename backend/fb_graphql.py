# -*- coding: utf-8 -*-
"""
FB internal GraphQL engine — pure-requests post deletion + permalink capture.

Reverse-engineered and validated end-to-end on 2026-06-24 against a live logged-in
session (replaces the fragile mbasic/DOM delete that broke on modern React FB).

Mechanism (all empirically confirmed):
  * A logged-in www.facebook.com page exposes `fb_dtsg` / `lsd` tokens (DTSGInitialData / LSD).
  * Deleting a post = POST https://www.facebook.com/api/graphql/ with friendly-name
    `useCometFeedStoryDeleteMutation` (doc_id below). On success FB returns
    `{"data":{"story_delete":{"deleted_story_id":"..."}}}`.
  * The mutation's `story_id` is base64("S:_I{actor_id}:{post_id}:{post_id}") — so it can be
    constructed purely from actor_id + the numeric post_id captured at compose time.
  * Composing via the DOM still fires `ComposerStoryCreateMutation`; its JSON *response*
    carries the new numeric `post_id` and the `/posts/...` permalink — captured via an
    injected fetch/XHR hook (COMPOSE_CAPTURE_HOOK) rather than scraped from the DOM.

doc_ids ROTATE over time. They are module constants + `delete_post_graphql` returns a
structured result so callers can health-check and fall back to a DOM delete.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# --- doc_ids captured 2026-06-24 (rotate-aware: see health check in delete_post_graphql) ---
COMPOSE_DOC_ID = "27638478529090712"  # ComposerStoryCreateMutation
DELETE_DOC_ID = "36213403264942057"  # useCometFeedStoryDeleteMutation
TIMELINE_DOC_ID = (
    "27592098867143956"  # ProfileCometTimelineFeedRefetchQuery (read posts)
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Injected on every navigation (Page.addScriptToEvaluateOnNewDocument) so we can read the
# ComposerStoryCreateMutation *response* (which holds the new post_id + permalink) after a
# DOM compose, without scraping the async-rendered React feed.
COMPOSE_CAPTURE_HOOK = """
(function(){
  if(window.__nexHook) return; window.__nexHook=1; window.__nexResp=[];
  function isG(u){ return typeof u==='string' && u.indexOf('/api/graphql')>=0; }
  var of=window.fetch;
  window.fetch=function(i,n){
    var u=(typeof i==='string')?i:(i&&i.url);
    if(isG(u)){
      var p=of.apply(this,arguments);
      try{ p.then(function(r){ try{ r.clone().text().then(function(t){ window.__nexResp.push(t); }).catch(function(){}); }catch(e){} }); }catch(e){}
      return p;
    }
    return of.apply(this,arguments);
  };
  var oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open=function(m,u){ this.__nu=u; return oo.apply(this,arguments); };
  XMLHttpRequest.prototype.send=function(b){
    try{ if(isG(this.__nu)){ this.addEventListener('load', function(){ try{ window.__nexResp.push(this.responseText); }catch(e){} }); } }catch(e){}
    return os.apply(this,arguments);
  };
})();
"""


def build_story_id(actor_id: str, post_id: str) -> str:
    """story_id used by the delete mutation = base64('S:_I{actor}:{post}:{post}')."""
    raw = f"S:_I{actor_id}:{post_id}:{post_id}"
    return base64.b64encode(raw.encode()).decode()


def make_session(cookies: list) -> requests.Session:
    """Build a requests session from Selenium-style cookie dicts ({name,value,...})."""
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": _UA,
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "sec-ch-ua": '"Chromium";v="126", "Google Chrome";v="126"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "upgrade-insecure-requests": "1",
        }
    )
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=".facebook.com")
        except Exception:  # noqa: BLE001
            continue
    return s


def fetch_tokens(session: requests.Session) -> dict:
    """GET www.facebook.com and extract fb_dtsg / lsd / jazoest / actor_id.

    Returns {} (empty) if not logged in or tokens missing — caller must handle.
    """
    try:
        html = session.get("https://www.facebook.com/", timeout=30).text
    except Exception as e:  # noqa: BLE001
        logger.warning("fetch_tokens GET failed: %s", e)
        return {}
    dtsg = re.search(r'"DTSGInitialData",\[\],\{"token":"([^"]+)"', html)
    lsd = re.search(r'"LSD",\[\],\{"token":"([^"]+)"', html)
    actor = re.search(r'"actorID":"(\d+)"', html) or re.search(
        r'"USER_ID":"(\d+)"', html
    )
    dtsg = dtsg.group(1) if dtsg else None
    if not dtsg:
        return {}
    lsd_v = lsd.group(1) if lsd else None
    jaz = re.search(r"jazoest=(\d+)", html)
    jazoest = jaz.group(1) if jaz else "2" + str(sum(ord(c) for c in dtsg))
    return {
        "fb_dtsg": dtsg,
        "lsd": lsd_v,
        "jazoest": jazoest,
        "actor_id": actor.group(1) if actor else None,
    }


def extract_permalink(resp_texts: list) -> dict:
    """From captured GraphQL response bodies, pull the new post's numeric id + permalink.

    post_id and permalink are paired from the SAME response body (the create mutation),
    so a multi-graphql navigation can't mix one post's id with another's link.
    Returns {"post_id": str|None, "permalink": str|None}.
    """
    perma_re = re.compile(
        r'"(https:\\?/\\?/www\.facebook\.com\\?/[^"]*?posts\\?/[^"]+)"'
    )
    pid_re = re.compile(r'"post_id":"(\d+)"')
    # Prefer the create-mutation response; fall back to any body carrying a /posts/ link.
    for require_create in (True, False):
        for t in resp_texts:
            is_create = "ComposerStoryCreate" in t or "creation_story" in t
            if require_create and not is_create:
                continue
            if not require_create and "/posts/" not in t:
                continue
            mp = pid_re.search(t)
            ml = perma_re.search(t)
            if mp and ml:
                return {
                    "post_id": mp.group(1),
                    "permalink": ml.group(1).replace("\\/", "/").replace("\\", ""),
                }
    return {"post_id": None, "permalink": None}


def resolve_post_id(session: requests.Session, url: str) -> Optional[str]:
    """Best-effort: derive the numeric post_id from a stored permalink.

    Handles numeric `/posts/123:...` URLs directly, else GETs the page and pulls the
    embedded `post_id`. Used as a fallback for records saved before fb_post_id existed.
    """
    if not url:
        return None
    m = re.search(r"/posts/(\d{6,})", url) or re.search(r"story_fbid=(\d{6,})", url)
    if m:
        return m.group(1)
    try:
        html = session.get(url, timeout=30).text
    except Exception:  # noqa: BLE001
        return None
    m = re.search(r'"post_id":"(\d+)"', html) or re.search(
        r'"top_level_post_id":"(\d+)"', html
    )
    return m.group(1) if m else None


def delete_post_graphql(
    session: requests.Session,
    post_id: str,
    actor_id: str,
    tokens: dict,
) -> dict:
    """POST the delete mutation. Returns a structured result:

    {"ok": bool, "deleted_story_id": str|None, "status": int, "doc_id_stale": bool,
     "error": str|None}
    `doc_id_stale` is True when FB rejects the persisted query (rotation) so the caller
    can refresh the doc_id / fall back to a DOM delete.
    """
    fb_dtsg = tokens.get("fb_dtsg")
    if not (fb_dtsg and post_id and actor_id):
        return {
            "ok": False,
            "error": "missing fb_dtsg/post_id/actor_id",
            "status": 0,
            "deleted_story_id": None,
            "doc_id_stale": False,
        }
    lsd = tokens.get("lsd")
    variables = {
        "input": {
            "story_id": build_story_id(actor_id, post_id),
            "story_location": "PERMALINK",
            "actor_id": actor_id,
            "client_mutation_id": "1",
        },
        "groupID": None,
        "inviteShortLinkKey": None,
        "renderLocation": None,
        "scale": 1,
        "__relay_internal__pv__groups_comet_use_glvrelayprovider": False,
    }
    body = {
        "av": actor_id,
        "__user": actor_id,
        "__a": "1",
        "fb_dtsg": fb_dtsg,
        "jazoest": tokens.get("jazoest", ""),
        "lsd": lsd or "",
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "useCometFeedStoryDeleteMutation",
        "variables": json.dumps(variables, separators=(",", ":")),
        "server_timestamps": "true",
        "doc_id": DELETE_DOC_ID,
    }
    try:
        r = session.post(
            "https://www.facebook.com/api/graphql/",
            data=body,
            timeout=30,
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "x-fb-friendly-name": "useCometFeedStoryDeleteMutation",
                "x-fb-lsd": lsd or "",
                "origin": "https://www.facebook.com",
                "referer": "https://www.facebook.com/",
            },
        )
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(e),
            "status": 0,
            "deleted_story_id": None,
            "doc_id_stale": False,
        }

    text = r.text or ""
    deleted = None
    m = re.search(r'"deleted_story_id":"([^"]+)"', text)
    if m:
        deleted = m.group(1)
    # Authoritative success = HTTP 200 + FB echoed the deleted story id. We deliberately do
    # NOT reject on a bare "errors" substring (success bodies can carry `"errors":null` /
    # extensions), which would otherwise false-fail and trigger a needless DOM fallback.
    ok = r.status_code == 200 and deleted is not None
    # Persisted-query rotation: 200 but no deletion + a query/lookup error in the body.
    stale = (
        r.status_code == 200
        and deleted is None
        and any(k in text for k in ("errorSummary", "not found", "Query", "doc_id"))
    )
    if not ok:
        logger.warning(
            "delete_post_graphql not ok: status=%s stale=%s head=%s",
            r.status_code,
            stale,
            text[:200],
        )
    return {
        "ok": ok,
        "deleted_story_id": deleted,
        "status": r.status_code,
        "doc_id_stale": bool(stale),
        "error": None if ok else text[:300],
    }
