from __future__ import annotations

from typing import Dict, List


FEATURE_COLUMNS = [
    "followers_count",
    "following_count",
    "media_count",
    "has_profile_pic",
    "bio_length",
    "username_length",
    "digit_count_in_username",
    "followers_following_ratio",
]


def extract_features(
    *,
    username: str,
    bio: str,
    followers_count: int,
    following_count: int,
    media_count: int,
    has_profile_pic: int,
) -> Dict[str, float]:
    cleaned_username = (username or "").strip()
    cleaned_bio = (bio or "").strip()

    username_length = len(cleaned_username)
    digit_count = sum(char.isdigit() for char in cleaned_username)
    bio_length = len(cleaned_bio)
    ratio = float(followers_count) / (float(following_count) + 1.0)

    return {
        "followers_count": float(followers_count),
        "following_count": float(following_count),
        "media_count": float(media_count),
        "has_profile_pic": float(has_profile_pic),
        "bio_length": float(bio_length),
        "username_length": float(username_length),
        "digit_count_in_username": float(digit_count),
        "followers_following_ratio": float(ratio),
    }


def features_to_vector(features: Dict[str, float]) -> List[float]:
    return [features[column] for column in FEATURE_COLUMNS]
