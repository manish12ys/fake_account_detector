from playwright.sync_api import sync_playwright
import time
import re
from typing import Optional, Tuple


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


def parse_counts(meta):
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


def extract_bio_from_html(html):
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


def fetch_instagram_user(username):
    url = f"https://www.instagram.com/{username}/"

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
    
    Args:
        username: Instagram username to fetch
        
    Returns:
        Tuple of (profile_object, method/error_message)
        - profile_object: InstagramProfile instance or None if fetch failed
        - method/error_message: Description of success method or error message
    """
    # Try Playwright first
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

            # Meta description for counts
            meta = page.locator('meta[name="description"]').get_attribute("content")

            # Full HTML for bio
            html = page.content()
            bio = extract_bio_from_html(html)

            browser.close()
        
        # Parse counts
        followers_str, following_str, posts_str = parse_counts(meta)
        
        # Convert string counts to integers (remove commas)
        def to_int(s: str) -> int:
            if s == "N/A":
                return 0
            try:
                return int(s.replace(",", ""))
            except:
                return 0
        
        followers_count = to_int(followers_str)
        following_count = to_int(following_str)
        media_count = to_int(posts_str)
        
        if not bio:
            bio = "(No bio)"
        
        profile = InstagramProfile(
            username=username,
            bio=bio,
            followers_count=followers_count,
            following_count=following_count,
            media_count=media_count,
            has_profile_pic=1  # Assume has pic if page loads
        )
        
        return profile, "Playwright scraper"
        
    except Exception as playwright_error:
        # Fallback: try public web scraping without Playwright (no auth needed)
        try:
            url = f"https://www.instagram.com/{username}/"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            response = __import__("requests").get(url, headers=headers, timeout=10)
            if response.status_code >= 400:
                return None, "Unable to fetch from Instagram. Please enter details manually."
            
            html = response.text
            bio = extract_bio_from_html(html)
            meta_match = __import__("re").search(r'"edge_followed_by":{"edge_follow_list":{"count":(\d+)}}', html)
            
            # Light fallback if we can't scrape properly
            return None, "Unable to fetch from Instagram. Please enter details manually."
            
        except Exception:
            return None, "Unable to fetch from Instagram. Please enter details manually."


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
