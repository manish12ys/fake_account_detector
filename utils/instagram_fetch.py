import json
import re
from typing import Optional, Tuple

import requests


class InstagramProfile:
    """Profile data class for Instagram user."""
    
    def __init__(self, username: str, bio: str, followers_count: int, 
                 following_count: int, media_count: int, has_profile_pic: int = 0):
        self.username = username
        self.bio = bio
        self.followers_count = followers_count
        self.following_count = following_count
        self.media_count = media_count
        self.has_profile_pic = has_profile_pic
    
    def to_dict(self) -> dict:
        """Convert profile to dictionary."""
        return {
            "username": self.username,
            "bio": self.bio,
            "followers_count": self.followers_count,
            "following_count": self.following_count,
            "media_count": self.media_count,
            "has_profile_pic": self.has_profile_pic,
        }


def parse_counts(meta: str):
    followers = "N/A"
    following = "N/A"
    posts = "N/A"

    if not meta:
        return followers, following, posts

    f1 = re.search(r"([\d,.]+)\s+Followers", meta)
    f2 = re.search(r"([\d,.]+)\s+Following", meta)
    f3 = re.search(r"([\d,.]+)\s+Posts", meta)

    if f1:
        followers = f1.group(1)
    if f2:
        following = f2.group(1)
    if f3:
        posts = f3.group(1)

    return followers, following, posts


def _to_int(value: str | int | float | None) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    cleaned = str(value).strip().lower().replace(",", "")
    if not cleaned or cleaned == "n/a":
        return 0

    multiplier = 1
    if cleaned.endswith("k"):
        multiplier = 1_000
        cleaned = cleaned[:-1]
    elif cleaned.endswith("m"):
        multiplier = 1_000_000
        cleaned = cleaned[:-1]

    try:
        return int(float(cleaned) * multiplier)
    except Exception:
        return 0


def extract_bio_from_html(html: str):
    """
    Extract biography from embedded JSON.
    This is the most reliable source.
    """
    match = re.search(r'"biography":"(.*?)"', html)
    if not match:
        return ""

    bio = match.group(1)

    # Decode escaped characters
    try:
        bio = bytes(bio, "utf-8").decode("unicode_escape")
    except:
        pass

    # Clean up common junk
    bio = bio.strip()

    return bio


def _parse_profile_from_html(username: str, html: str) -> Optional[InstagramProfile]:
    meta_match = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html, re.IGNORECASE)
    meta_content = meta_match.group(1) if meta_match else ""
    followers_str, following_str, posts_str = parse_counts(meta_content)

    bio = extract_bio_from_html(html)

    # JSON-LD fallback if available
    if not bio:
        ld_match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if ld_match:
            try:
                ld_json = json.loads(ld_match.group(1))
                bio = str(ld_json.get("description", "")).strip()
            except Exception:
                pass

    if not bio:
        bio = "(No bio)"

    followers = _to_int(followers_str)
    following = _to_int(following_str)
    posts = _to_int(posts_str)

    # If meta parsing failed, try lightweight JSON hints used in page source
    if followers == 0 and following == 0 and posts == 0:
        followers_hint = re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)
        following_hint = re.search(r'"edge_follow"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)
        posts_hint = re.search(r'"edge_owner_to_timeline_media"\s*:\s*\{\s*"count"\s*:\s*(\d+)', html)

        followers = _to_int(followers_hint.group(1) if followers_hint else 0)
        following = _to_int(following_hint.group(1) if following_hint else 0)
        posts = _to_int(posts_hint.group(1) if posts_hint else 0)

    has_picture = 1 if "profile_pic_url" in html else 0

    # If literally nothing is available, treat as failed parse.
    if followers == 0 and following == 0 and posts == 0 and bio in {"", "(No bio)"}:
        return None

    return InstagramProfile(
        username=username,
        bio=bio,
        followers_count=followers,
        following_count=following,
        media_count=posts,
        has_profile_pic=has_picture,
    )


def _fetch_via_requests(username: str) -> Tuple[Optional[InstagramProfile], str]:
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instagram.com/",
    }

    response = requests.get(url, headers=headers, timeout=20)
    if response.status_code == 404:
        return None, "Username not found on Instagram."
    if response.status_code >= 400:
        return None, f"Instagram returned HTTP {response.status_code}."

    profile = _parse_profile_from_html(username, response.text)
    if profile is None:
        return None, "Instagram page parsing failed."

    return profile, "Requests scraper"


def _fetch_via_instaloader(username: str) -> Tuple[Optional[InstagramProfile], str]:
    try:
        import instaloader
    except Exception:
        return None, "Instaloader unavailable."

    try:
        loader = instaloader.Instaloader(download_pictures=False, download_videos=False)
        profile = instaloader.Profile.from_username(loader.context, username)
        result = InstagramProfile(
            username=profile.username,
            bio=profile.biography or "(No bio)",
            followers_count=int(profile.followers),
            following_count=int(profile.followees),
            media_count=int(profile.mediacount),
            has_profile_pic=1,
        )
        return result, "Instaloader"
    except Exception as exc:
        return None, f"Instaloader failed: {exc}"


def _fetch_via_playwright(username: str) -> Tuple[Optional[InstagramProfile], str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None, "Playwright unavailable."

    try:
        url = f"https://www.instagram.com/{username}/"
        user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": user_agent})

            response = page.goto(url, timeout=60000, wait_until="domcontentloaded")
            if response is not None and response.status >= 400:
                browser.close()
                return None, f"Instagram returned HTTP {response.status}."

            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()

        profile = _parse_profile_from_html(username, html)
        if profile is None:
            return None, "Playwright page parsing failed."

        return profile, "Playwright scraper"
    except Exception as exc:
        return None, f"Playwright failed: {exc}"


def fetch_instagram_user(username):
    url = f"https://www.instagram.com/{username}/"

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # set False for demo
        page = browser.new_page()

        page.goto(url, timeout=60000)
        page.wait_for_timeout(5000)

        # Meta description for counts
        meta = page.locator('meta[name="description"]').get_attribute("content")

        # Full HTML for bio
        html = page.content()
        bio = extract_bio_from_html(html)

        browser.close()

    followers, following, posts = parse_counts(meta)

    if not bio:
        bio = "(No bio)"

    return {
        "username": username,
        "followers": followers,
        "following": following,
        "posts": posts,
        "bio": bio
    }


def fetch_instagram_profile(username: str) -> Tuple[Optional[InstagramProfile], str]:
    """
    Fetch Instagram profile data for a given username.
    Tries requests first (no deps), then Playwright if available.
    
    Args:
        username: Instagram username to fetch
        
    Returns:
        Tuple of (profile_object, method/error_message)
    """
    cleaned_username = (username or "").strip().lstrip("@")
    if not cleaned_username:
        return None, "Please enter a valid username."

    errors: list[str] = []

    for fetcher in (_fetch_via_requests, _fetch_via_instaloader, _fetch_via_playwright):
        profile, message = fetcher(cleaned_username)
        if profile is not None:
            return profile, message
        errors.append(message)

    compact_errors = " | ".join(error for error in errors if error)
    return None, f"Unable to fetch from Instagram. Please enter account details manually. ({compact_errors})"



if __name__ == "__main__":
    user = input("Enter Instagram username: ").strip()
    profile, method_or_error = fetch_instagram_profile(user)

    if profile is None:
        print(f"\n❌ Failed to fetch profile: {method_or_error}")
    else:
        print("\n✅ Instagram User Data (Live)")
        print("-----------------------------")
        print("Username  :", profile.username)
        print("Followers :", profile.followers_count)
        print("Following :", profile.following_count)
        print("Posts     :", profile.media_count)
        print("Bio       :", profile.bio)
