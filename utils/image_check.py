from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image
import imagehash


DEFAULT_THRESHOLD = 8


def _compute_hash(image_path: Path, hash_size: int) -> imagehash.ImageHash:
    with Image.open(image_path) as image:
        return imagehash.phash(image, hash_size=hash_size)


def check_image_originality(
    image_path: Path,
    known_dir: Optional[Path] = None,
    threshold: int = DEFAULT_THRESHOLD,
    hash_size: int = 8,
) -> Dict[str, object]:
    """Check whether an image appears to be reused using perceptual hashing."""
    if known_dir is None:
        known_dir = Path(__file__).resolve().parents[1] / "static" / "uploads" / "known"

    known_dir.mkdir(parents=True, exist_ok=True)

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image_hash = _compute_hash(image_path, hash_size)
    closest_distance = None
    closest_match = None

    for candidate in known_dir.iterdir():
        if not candidate.is_file():
            continue
        try:
            candidate_hash = _compute_hash(candidate, hash_size)
        except Exception:
            continue
        distance = image_hash - candidate_hash
        if closest_distance is None or distance < closest_distance:
            closest_distance = distance
            closest_match = candidate

    if closest_distance is None:
        closest_distance = hash_size * hash_size

    similarity = max(0.0, 1.0 - (closest_distance / float(hash_size * hash_size)))
    status = "Possibly Reused" if closest_distance <= threshold else "Original"

    return {
        "image_status": status,
        "similarity_score": round(similarity, 4),
        "closest_distance": int(closest_distance),
        "closest_match": str(closest_match) if closest_match else None,
    }
