import streamlit as st
import os
import json
import tweepy
from datetime import datetime
from google.cloud import firestore
from google.cloud.firestore_v1.query import Query
from google.oauth2 import service_account

# Page setup
st.set_page_config(page_title="Telco Market Admin", layout="centered", initial_sidebar_state="collapsed")

# 1. Simple Password Protection
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "default_secret")
user_pass = st.text_input("Enter Admin Password", type="password")

if user_pass != ADMIN_PASSWORD:
    if user_pass:
        st.error("Incorrect password.")
    st.stop()

st.title("📲 Telco Market Admin")

# 2. Firestore Initialization
@st.cache_resource
def get_db():
    service_account_info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
    credentials = service_account.Credentials.from_service_account_info(service_account_info)
    return firestore.Client(credentials=credentials)

db = get_db()

# Helper function to post text directly to X (Twitter)
def publish_to_x(text_content):
    api_key = os.getenv("X_API_KEY")
    api_secret = os.getenv("X_API_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
    
    if not all([api_key, api_secret, access_token, access_token_secret]):
        raise ValueError("Missing X API environment credentials.")
        
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    response = client.create_tweet(text=text_content)
    return response.data["id"]

# Helper function to format timestamp safely
def format_timestamp(dt):
    if not dt:
        return "Unknown Date"
    if isinstance(dt, datetime):
        return dt.strftime("%b %d, %Y • %H:%M UTC")
    try:
        return str(dt)
    except Exception:
        return "Unknown Date"

# Helper function for rendering numbered pagination controls
def render_pagination_controls(current_page, total_pages, state_key):
    if total_pages <= 1:
        return

    st.write("")
    # Build column widths: Prev button, numbered buttons, Next button
    col_widths = [1] + [1] * total_pages + [1]
    cols = st.columns(col_widths)

    # 1. Previous Button
    with cols[0]:
        if st.button("⬅️", key=f"prev_{state_key}", disabled=(current_page == 0)):
            st.session_state[state_key] -= 1
            st.rerun()

    # 2. Page Number Buttons (1, 2, 3, 4...)
    for i in range(total_pages):
        with cols[i + 1]:
            is_current = (i == current_page)
            # Active page is highlighted with a primary-style label indicator
            btn_label = f"[{i + 1}]" if is_current else f"{i + 1}"
            if st.button(btn_label, key=f"page_{state_key}_{i}", disabled=is_current):
                st.session_state[state_key] = i
                st.rerun()

    # 3. Next Button
    with cols[-1]:
        if st.button("➡️", key=f"next_{state_key}", disabled=(current_page >= total_pages - 1)):
            st.session_state[state_key] += 1
            st.rerun()

# ==========================================
# DATA FETCHING & SORTING (Newest to Oldest)
# ==========================================
pending_ref = db.collection("draft_news")\
    .where("approved", "==", False)\
    .order_by("created_at", direction=Query.DESCENDING)\
    .stream()
pending_articles = [doc.to_dict() | {"id": doc.id} for doc in pending_ref]

posted_ref = db.collection("draft_news")\
    .where("posted_to_x", "==", True)\
    .order_by("created_at", direction=Query.DESCENDING)\
    .stream()
posted_articles = [doc.to_dict() | {"id": doc.id} for doc in posted_ref]

# Dynamic Tab Headers with Highlighted Counts
tab_pending, tab_posted = st.tabs([
    f"⏳ Pending Review ({len(pending_articles)})",
    f"✅ Posted to X ({len(posted_articles)})"
])

ITEMS_PER_PAGE = 20

# ==========================================
# TAB 1: PENDING REVIEW
# ==========================================
with tab_pending:
    if not pending_articles:
        st.info("🎉 No articles currently pending review.")
    else:
        # Session state initialization for Pending tab
        if "pending_page" not in st.session_state:
            st.session_state.pending_page = 0

        total_pending_pages = max(1, (len(pending_articles) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        
        # Guard against index overflow after document deletions
        if st.session_state.pending_page >= total_pending_pages:
            st.session_state.pending_page = total_pending_pages - 1

        current_pending_page = st.session_state.pending_page

        start_idx = current_pending_page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_pending_articles = pending_articles[start_idx:end_idx]

        for article in page_pending_articles:
            doc_id = article["id"]
            with st.container():
                st.subheader(article.get("title", "No Title"))
                
                # Metadata row: Source link + Timestamp
                source_url = article.get("url", "#")
                created_str = format_timestamp(article.get("created_at"))
                st.caption(f"🔗 [Source Link]({source_url}) | 📅 Added: **{created_str}**")

                # Article image preview (if extracted)
                image_url = article.get("image_url")
                if image_url:
                    st.image(image_url, use_container_width=True)

                # Editable draft content text area
                edited_content = st.text_area(
                    "Edit Post Draft",
                    value=article.get("draft_content", ""),
                    height=130,
                    key=f"text_{doc_id}"
                )

                # Character counter
                char_count = len(edited_content)
                if char_count > 280:
                    st.warning(f"⚠️ Character count: {char_count}/280 (Exceeds standard limit)")
                else:
                    st.caption(f"📏 Character count: {char_count}/280")

                # Action Buttons Row
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    if st.button("💾 Save", key=f"save_{doc_id}"):
                        db.collection("draft_news").document(doc_id).update({"draft_content": edited_content})
                        st.toast("Draft updated successfully!", icon="✅")

                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{doc_id}"):
                        db.collection("draft_news").document(doc_id).delete()
                        st.toast("Entry deleted from database.", icon="🗑️")
                        st.rerun()

                with col3:
                    if st.button("🚫 Discard", key=f"discard_{doc_id}"):
                        db.collection("draft_news").document(doc_id).update({
                            "approved": True,
                            "status": "discarded"
                        })
                        st.toast("Article marked as discarded.", icon="🚫")
                        st.rerun()

                with col4:
                    if st.button("🚀 Post to X", key=f"post_{doc_id}"):
                        try:
                            tweet_id = publish_to_x(edited_content)
                            db.collection("draft_news").document(doc_id).update({
                                "approved": True,
                                "draft_content": edited_content,
                                "posted_to_x": True,
                                "tweet_id": tweet_id
                            })
                            st.success("Successfully posted to X!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to post to X: {e}")

                st.divider()

        # Render Numbered Pagination Controls for Pending Tab
        render_pagination_controls(current_pending_page, total_pending_pages, "pending_page")

# ==========================================
# TAB 2: POSTED TO X
# ==========================================
with tab_posted:
    if not posted_articles:
        st.info("No articles posted to X yet.")
    else:
        # Session state initialization for Posted tab
        if "posted_page" not in st.session_state:
            st.session_state.posted_page = 0

        total_posted_pages = max(1, (len(posted_articles) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        
        # Guard against index overflow after document deletions
        if st.session_state.posted_page >= total_posted_pages:
            st.session_state.posted_page = total_posted_pages - 1

        current_posted_page = st.session_state.posted_page

        p_start_idx = current_posted_page * ITEMS_PER_PAGE
        p_end_idx = p_start_idx + ITEMS_PER_PAGE
        page_posted_articles = posted_articles[p_start_idx:p_end_idx]

        for article in page_posted_articles:
            doc_id = article["id"]
            with st.container():
                st.subheader(article.get("title", "No Title"))
                
                source_url = article.get("url", "#")
                created_str = format_timestamp(article.get("created_at"))
                st.caption(f"🔗 [Source Link]({source_url}) | 📅 Posted Entry Date: **{created_str}**")

                image_url = article.get("image_url")
                if image_url:
                    st.image(image_url, use_container_width=True)

                st.code(article.get("draft_content", ""), language="markdown")
                
                tweet_id = article.get("tweet_id")
                if tweet_id:
                    st.caption(f"📱 Tweet ID: `{tweet_id}`")

                if st.button("🗑️ Delete Record", key=f"del_posted_{doc_id}"):
                    db.collection("draft_news").document(doc_id).delete()
                    st.rerun()

                st.divider()

        # Render Numbered Pagination Controls for Posted Tab
        render_pagination_controls(current_posted_page, total_posted_pages, "posted_page")
