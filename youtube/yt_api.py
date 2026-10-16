"""Minimal YouTube Data API v3 client (stdlib only).

The API key is never stored in code or data. It is read from the
YOUTUBE_API_KEY environment variable when set; otherwise requests go out
without a key and rely on the environment's network secret to add it.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://www.googleapis.com/youtube/v3/"

# Quota cost per call, from the YouTube Data API docs.
COSTS = {"search": 100, "videos": 1, "channels": 1, "playlistItems": 1}


class YouTubeError(RuntimeError):
    pass


class YouTubeClient:
    def __init__(self, api_key=None, timeout=30):
        self.api_key = api_key if api_key is not None else os.environ.get("YOUTUBE_API_KEY")
        self.timeout = timeout
        self.quota_used = 0

    def get(self, endpoint, **params):
        params = {k: v for k, v in params.items() if v is not None}
        if self.api_key:
            params["key"] = self.api_key
        url = API_ROOT + endpoint + "?" + urllib.parse.urlencode(params)
        self.quota_used += COSTS.get(endpoint, 1)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            try:
                msg = json.load(e)["error"]["message"]
            except Exception:
                msg = str(e)
            # Never echo the request URL: it may carry the key.
            raise YouTubeError(f"{endpoint}: HTTP {e.code}: {msg}") from None

    # --- helpers -------------------------------------------------------

    def videos(self, ids, parts="snippet,statistics,contentDetails"):
        out = []
        ids = list(dict.fromkeys(ids))
        for i in range(0, len(ids), 50):
            data = self.get("videos", part=parts, id=",".join(ids[i:i + 50]), maxResults=50)
            out.extend(data.get("items", []))
        return out

    def channels(self, ids, parts="snippet,statistics"):
        out = []
        ids = list(dict.fromkeys(ids))
        for i in range(0, len(ids), 50):
            data = self.get("channels", part=parts, id=",".join(ids[i:i + 50]), maxResults=50)
            out.extend(data.get("items", []))
        return out
