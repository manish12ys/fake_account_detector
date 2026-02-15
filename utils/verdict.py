from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class VerdictResult:
    verdict: Literal["High Risk Fake", "Suspicious", "Likely Genuine", "Needs Review"]
    risk_score: int
    reasoning: str


def compute_verdict(
    account_prediction: str,
    account_confidence: float,
    image_status: str,
    image_similarity_score: float | None,
) -> VerdictResult:
    """
    Combine account prediction and image status to produce a final verdict and risk score.
    
    Args:
        account_prediction: "Fake" or "Real"
        account_confidence: Confidence from model (0.0 to 1.0)
        image_status: "Original", "Possibly Reused", or "No Image"
        image_similarity_score: 0.0 to 1.0, or None if no image
    
    Returns:
        VerdictResult with verdict, risk_score (0-100), and reasoning
    """
    if image_similarity_score is None:
        image_similarity_score = 0.5

    account_risk = account_confidence if account_prediction == "Fake" else (1.0 - account_confidence)
    image_risk = image_similarity_score if image_status == "Possibly Reused" else 0.0

    combined_risk = (account_risk * 0.6 + image_risk * 0.4) * 100
    risk_score = int(round(combined_risk))

    if account_prediction == "Fake" and image_status == "Possibly Reused":
        return VerdictResult(
            verdict="High Risk Fake",
            risk_score=min(100, risk_score + 20),
            reasoning="Account behavior suggests fake AND profile image appears reused.",
        )

    if account_prediction == "Fake" and image_status == "Original":
        return VerdictResult(
            verdict="Suspicious",
            risk_score=max(50, risk_score + 10),
            reasoning="Account behavior suggests fake but profile image appears original.",
        )

    if account_prediction == "Real" and image_status == "Original":
        return VerdictResult(
            verdict="Likely Genuine",
            risk_score=max(0, risk_score - 20),
            reasoning="Account behavior suggests real AND profile image appears original.",
        )

    if account_prediction == "Real" and image_status == "Possibly Reused":
        return VerdictResult(
            verdict="Needs Review",
            risk_score=risk_score + 5,
            reasoning="Account behavior suggests real but profile image appears reused.",
        )

    return VerdictResult(
        verdict="Needs Review",
        risk_score=risk_score,
        reasoning="Unable to determine verdict with available data.",
    )
