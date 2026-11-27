"""One function per platform. Each reads its own secrets from environment variables.

A platform is "configured" when all its required variables are set; unconfigured
platforms are skipped, so you can turn them on one at a time.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

TIMEOUT = 60
GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
ALT_TEXT = "This week's DFW Pauper event schedule"

REQUIRED = {
    "discord": ["DISCORD_WEBHOOK_URL"],
    "bluesky": ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"],
    "x": ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"],
    "facebook": ["META_PAGE_ID", "META_PAGE_TOKEN"],
    "instagram": ["META_PAGE_ID", "META_PAGE_TOKEN", "INSTAGRAM_USER_ID"],
}


def configured(platform: str) -> bool:
    return all(os.environ.get(k) for k in REQUIRED[platform])


def _check(r: requests.Response) -> dict:
    if not r.ok:
        raise RuntimeError(f"{r.request.method} {r.url.split('?')[0]} -> {r.status_code}: {r.text[:500]}")
    return r.json() if r.content else {}


# ---------- Discord ----------

def discord(text: str, image: Path, webhook_url: str | None = None) -> str:
    url = webhook_url or os.environ["DISCORD_WEBHOOK_URL"]
    if len(text) > 2000:
        text = text[:1990] + "\n…"
    payload = {"content": text, "allowed_mentions": {"parse": []}}
    with image.open("rb") as f:
        r = requests.post(url + "?wait=true", data={"payload_json": json.dumps(payload)},
                          files={"files[0]": (image.name, f, "image/png")}, timeout=TIMEOUT)
    return _check(r).get("id", "sent")


# ---------- Bluesky ----------

def _facets(text: str) -> list[dict]:
    facets = []
    def span(m: re.Match) -> dict:
        start = len(text[:m.start()].encode())
        return {"byteStart": start, "byteEnd": start + len(m.group(0).encode())}
    for m in re.finditer(r"https?://\S+", text):
        facets.append({"index": span(m), "features": [
            {"$type": "app.bsky.richtext.facet#link", "uri": m.group(0)}]})
    for m in re.finditer(r"(?<!\w)#(\w+)", text):
        facets.append({"index": span(m), "features": [
            {"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}]})
    return facets


def bluesky(text: str, image: Path) -> str:
    pds = os.environ.get("BLUESKY_PDS", "https://bsky.social")
    s = _check(requests.post(f"{pds}/xrpc/com.atproto.server.createSession", timeout=TIMEOUT, json={
        "identifier": os.environ["BLUESKY_HANDLE"], "password": os.environ["BLUESKY_APP_PASSWORD"]}))
    auth = {"Authorization": f"Bearer {s['accessJwt']}"}
    blob = _check(requests.post(f"{pds}/xrpc/com.atproto.repo.uploadBlob", data=image.read_bytes(),
                                headers={**auth, "Content-Type": "image/png"}, timeout=TIMEOUT))["blob"]
    record = {
        "$type": "app.bsky.feed.post", "text": text, "facets": _facets(text),
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "embed": {"$type": "app.bsky.embed.images", "images": [
            {"alt": ALT_TEXT, "image": blob, "aspectRatio": {"width": 1080, "height": 1080}}]},
    }
    r = _check(requests.post(f"{pds}/xrpc/com.atproto.repo.createRecord", headers=auth, timeout=TIMEOUT,
                             json={"repo": s["did"], "collection": "app.bsky.feed.post", "record": record}))
    return r.get("uri", "sent")


# ---------- X ----------

def x(text: str, image: Path) -> str:
    from requests_oauthlib import OAuth1

    auth = OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                  os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_TOKEN_SECRET"])
    with image.open("rb") as f:
        media = _check(requests.post("https://api.x.com/2/media/upload", auth=auth, timeout=TIMEOUT,
                                     data={"media_category": "tweet_image"},
                                     files={"media": (image.name, f, "image/png")}))
    media_id = media.get("data", media).get("id") or media.get("media_id_string")
    r = _check(requests.post("https://api.x.com/2/tweets", auth=auth, timeout=TIMEOUT,
                             json={"text": text, "media": {"media_ids": [str(media_id)]}}))
    return r["data"]["id"]


# ---------- Facebook Page + Instagram (Meta Graph API) ----------

def _page_photo(image: Path, message: str | None, published: bool) -> dict:
    data = {"access_token": os.environ["META_PAGE_TOKEN"], "published": str(published).lower()}
    if message:
        data["message"] = message
    with image.open("rb") as f:
        return _check(requests.post(f"{GRAPH}/{os.environ['META_PAGE_ID']}/photos", data=data,
                                    files={"source": (image.name, f, "image/png")}, timeout=TIMEOUT))


def _photo_url(photo_id: str) -> str:
    r = _check(requests.get(f"{GRAPH}/{photo_id}", timeout=TIMEOUT, params={
        "fields": "images", "access_token": os.environ["META_PAGE_TOKEN"]}))
    return max(r["images"], key=lambda i: i["width"])["source"]


_fb_photo_id: str | None = None  # reused by instagram() so the image is uploaded once


def facebook(text: str, image: Path) -> str:
    global _fb_photo_id
    r = _page_photo(image, text, published=True)
    _fb_photo_id = r["id"]
    return r.get("post_id", r["id"])


def instagram(text: str, image: Path) -> str:
    # Instagram needs a public image URL. Use the Facebook photo if we just posted one,
    # otherwise upload an unpublished (hidden) photo to the Page to get a URL.
    photo_id = _fb_photo_id or _page_photo(image, None, published=False)["id"]
    image_url = os.environ.get("IMAGE_PUBLIC_URL") or _photo_url(photo_id)
    token = os.environ["META_PAGE_TOKEN"]
    ig = os.environ["INSTAGRAM_USER_ID"]
    container = _check(requests.post(f"{GRAPH}/{ig}/media", timeout=TIMEOUT, data={
        "image_url": image_url, "caption": text, "alt_text": ALT_TEXT, "access_token": token}))["id"]
    for _ in range(20):
        status = _check(requests.get(f"{GRAPH}/{container}", timeout=TIMEOUT, params={
            "fields": "status_code", "access_token": token})).get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("Instagram could not process the image")
        time.sleep(3)
    r = _check(requests.post(f"{GRAPH}/{ig}/media_publish", timeout=TIMEOUT,
                             data={"creation_id": container, "access_token": token}))
    return r["id"]


PUBLISHERS = {"discord": discord, "bluesky": bluesky, "x": x, "facebook": facebook, "instagram": instagram}
ORDER = ["discord", "bluesky", "x", "facebook", "instagram"]  # facebook before instagram (image reuse)
