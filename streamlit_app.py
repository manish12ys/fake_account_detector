from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import joblib
import streamlit as st

from utils.features import extract_features
from utils.image_check import check_image_originality
from utils.instagram_fetch import fetch_instagram_profile
from utils.verdict import compute_verdict


@st.cache_resource
def ensure_playwright_browsers():
    """Ensure Playwright browsers are installed before first use."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            pass
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            try:
                subprocess.run(["playwright", "install", "--with-deps", "chromium"], check=True)
            except Exception as install_err:
                st.error(f"Failed to auto-install Playwright: {install_err}")
        else:
            raise


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model" / "account_model.pkl"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"


@st.cache_resource
def load_model():
    data = joblib.load(MODEL_PATH)
    return data["model"], data["feature_columns"]


def build_feature_vector(feature_columns: list[str]) -> list[float]:
    features = extract_features(
        username=st.session_state.get("username_input", ""),
        bio=st.session_state.get("bio", ""),
        followers_count=int(st.session_state.get("followers_count", 0)),
        following_count=int(st.session_state.get("following_count", 0)),
        media_count=int(st.session_state.get("media_count", 0)),
        has_profile_pic=int(st.session_state.get("has_profile_pic", 0)),
    )
    return [features[column] for column in feature_columns]


def save_upload(uploaded_file) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(uploaded_file.name or "upload.png").suffix or ".png"
    filename = f"{uuid.uuid4().hex}{suffix}"
    save_path = UPLOAD_DIR / filename
    with save_path.open("wb") as handle:
        handle.write(uploaded_file.getbuffer())
    return save_path


def init_state() -> None:
    st.session_state.setdefault("username_input", "")
    st.session_state.setdefault("bio", "")
    st.session_state.setdefault("followers_count", 0)
    st.session_state.setdefault("following_count", 0)
    st.session_state.setdefault("media_count", 0)
    st.session_state.setdefault("has_profile_pic", 1)
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("fetched_profile", None)


st.set_page_config(page_title="Fake Account Detector", page_icon=":mag:", layout="wide")
init_state()

ensure_playwright_browsers()

st.title("Fake Account Detector")
st.caption("Minimal Streamlit UI for authenticity analysis.")

left, right = st.columns([1.1, 1])

with left:
    st.subheader("Inputs")
    username_input = st.text_input(
        "Instagram Username",
        value=st.session_state.username_input,
        key="username_input",
        placeholder="username",
    )

    fetch_col, _ = st.columns([1, 2])
    with fetch_col:
        if st.button("Fetch from Instagram"):
            if not username_input.strip():
                st.warning("Please enter a username.")
            else:
                with st.spinner("Fetching profile data..."):
                    profile, error = fetch_instagram_profile(username_input.strip())
                if profile is None:
                    st.error(error)
                else:
                    st.session_state.bio = profile.bio
                    st.session_state.followers_count = int(profile.followers_count)
                    st.session_state.following_count = int(profile.following_count)
                    st.session_state.media_count = int(profile.media_count)
                    st.session_state.has_profile_pic = int(profile.has_profile_pic)
                    st.session_state.fetched_profile = profile.to_dict()
                    st.success("Profile data loaded successfully.")

    if st.session_state.fetched_profile:
        st.caption("Fetched profile")
        profile = st.session_state.fetched_profile
        st.json(
            {
                "username": profile.get("username"),
                "followers": profile.get("followers_count"),
                "following": profile.get("following_count"),
                "posts": profile.get("media_count"),
                "has_profile_pic": bool(profile.get("has_profile_pic")),
                "bio": profile.get("bio", ""),
            }
        )

    with st.form("analysis_form"):
        st.text_area("Bio / Description", key="bio", height=120)
        col_a, col_b = st.columns(2)
        with col_a:
            st.number_input("Followers", min_value=0, step=1, key="followers_count")
            st.number_input("Following", min_value=0, step=1, key="following_count")
        with col_b:
            st.number_input("Posts", min_value=0, step=1, key="media_count")
            st.selectbox(
                "Profile Picture",
                options=[1, 0],
                format_func=lambda value: "Yes" if value == 1 else "No",
                key="has_profile_pic",
            )
        uploaded_file = st.file_uploader("Upload Profile Image", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("Analyze Account")

    if submitted:
        model, feature_columns = load_model()
        vector = build_feature_vector(feature_columns)
        probability = float(model.predict_proba([vector])[0][1])
        prediction = "Fake" if probability >= 0.5 else "Real"

        image_status = "No Image"
        similarity_score = None
        if uploaded_file is not None:
            image_path = save_upload(uploaded_file)
            image_result = check_image_originality(image_path)
            image_status = image_result["image_status"]
            similarity_score = float(image_result["similarity_score"])

        verdict_result = compute_verdict(
            account_prediction=prediction,
            account_confidence=probability,
            image_status=image_status,
            image_similarity_score=similarity_score,
        )

        st.session_state.result = {
            "prediction": prediction,
            "confidence": round(probability, 4),
            "image_status": image_status,
            "similarity_score": similarity_score,
            "verdict": verdict_result.verdict,
            "risk_score": verdict_result.risk_score,
            "reasoning": verdict_result.reasoning,
        }

    st.info("This AI prediction is a screening tool. Cross-verify details before acting.")

with right:
    st.subheader("Results")
    result = st.session_state.get("result")
    if result:
        top_left, top_right = st.columns(2)
        with top_left:
            st.metric("Prediction", result["prediction"])
        with top_right:
            st.metric("Confidence", f"{int(result['confidence'] * 100)}%")

        st.progress(min(max(result["confidence"], 0.0), 1.0))

        info_left, info_right = st.columns(2)
        with info_left:
            st.metric("Image Status", result["image_status"])
        with info_right:
            if result["similarity_score"] is not None:
                st.metric("Similarity", f"{int(result['similarity_score'] * 100)}%")
            else:
                st.metric("Similarity", "N/A")

        st.divider()

        verdict_left, verdict_right = st.columns(2)
        with verdict_left:
            st.metric("Verdict", result["verdict"])
        with verdict_right:
            st.metric("Risk Score", f"{result['risk_score']}/100")

        with st.expander("Reasoning", expanded=True):
            st.write(result["reasoning"])
    else:
        st.info("No analysis yet. Fill the form to see results.")
