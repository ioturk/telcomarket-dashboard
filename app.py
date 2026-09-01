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

# 1. Custom CSS for Contrast, Pagination & iPhone/Mobile Alignment
st.markdown("""
<style>
/* High-contrast pagination buttons */
div[data-testid="stHorizontalBlock"] button {
    padding: 0.25rem 0.4rem !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
}

div[data-testid="stHorizontalBlock"] button[kind="primary"] {
    color: #FFFFFF !important;
    background-color: #FF4B4B !important;
    border-color: #FF4B4B !important;
}

/* Action button scaling for mobile viewports (e.g. iPhone 17 Pro) */
div[data-testid="column"] button {
    width: 100% !important;
    font-size: 0.85rem !important;
    padding-left: 0.2rem !important;
    padding-right: 0.2rem !important;
    white-space: nowrap !important;
}
</style>
""", unsafe_allow_html=True)

# 2. Simple Password Protection
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "default_secret")
user_pass = st.text_input("Enter Admin Password", type="password")

if user_pass != ADMIN_PASSWORD:
    if user_pass:
        st.error("Incorrect password.")
    st.stop()

st.title("📲 Telco Market Admin")

# 3. Firestore Initialization
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

# Helper function for high-contrast, responsive pagination controls
def render_pagination_controls(current_page, total_pages, state_key):
    if total_pages <= 1:
        return

    st.write("")
    
    # Visible numbered buttons limit for mobile alignment
    max_visible_buttons = 5
    half_range = max_visible_buttons // 2

    start_page = max(0, current_page - half_range)
    end_page = min(total_pages, start_page + max_visible_buttons)

    if end_page - start_page < max_visible_buttons:
        start_page = max(0, end_page - max_visible_buttons)

    page_numbers = list(range(start_page, end_page))
    
    # Layout structure: Prev + Page Numbers + Next
    num_cols = 1 + len(page_numbers) + 1
    cols = st.columns(num_cols)

    # 1. Previous Button
    with cols[0]:
        if st.button("⬅️", key=f"prev_{state_key}", disabled=(current_page == 0)):
            st.session_state[state_key] -= 1
            st.rerun()

    # 2. Page Number Buttons
    for idx, page_num in enumerate(page_numbers):
        with cols[idx + 1]:
            is_current = (page_num == current_page)
            btn_type = "primary" if is_current else "secondary"
            
            if st.button(f"{page_num + 1}", key=f"page_{state_key}_{page_num}", type=btn_type):
                if not is_current:
                    st.session_state[state_key] = page_num
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

# Dynamic Tab Headers
tab_pending, tab_posted = st.tabs([
    f"⏳ Pending ({len(pending_articles)})",
    f"✅ Posted ({len(posted_articles)})"
])

ITEMS_PER_PAGE = 20

# ==========================================
# TAB 1: PENDING REVIEW
# ==========================================
with tab_pending:
    if not pending_articles:
        st.info("🎉 No articles currently pending review.")
    else:
        if "pending_page" not in st.session_state:
            st.session_state.pending_page = 0

        total_pending_pages = max(1, (len(pending_articles) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        
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
                
                source_url = article.get("url", "#")
                created_str = format_timestamp(article.get("created_at"))
                st.caption(f"🔗 [Source Link]({source_url}) | 📅 Added: **{created_str}**")

                image_url = article.get("image_url")
                if image_url:
                    st.image(image_url, use_container_width=True)

                edited_content = st.text_area(
                    "Edit Post Draft",
                    value=article.get("draft_content", ""),
                    height=130,
                    key=f"text_{doc_id}"
                )

                char_count = len(edited_content)
                if char_count > 280:
                    st.warning(f"⚠️ Character count: {char_count}/280")
                else:
                    st.caption(f"📏 Character count: {char_count}/280")

                # Mobile-Optimized 2x2 Grid Layout for Action Buttons
                row1_col1, row1_col2 = st.columns(2)
                with row1_col1:
                    if st.button("💾 Save", key=f"save_{doc_id}"):
                        db.collection("draft_news").document(doc_id).update({"draft_content": edited_content})
                        st.toast("Draft updated!", icon="✅")

                with row1_col2:
                    if st.button("🚀 Post to X", key=f"post_{doc_id}", type="primary"):
                        try:
                            tweet_id = publish_to_x(edited_content)
                            db.collection("draft_news").document(doc_id).update({
                                "approved": True,
                                "draft_content": edited_content,
                                "posted_to_x": True,
                                "tweet_id": tweet_id
                            })
                            st.success("Posted to X!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to post: {e}")

                row2_col1, row2_col2 = st.columns(2)
                with row2_col1:
                    if st.button("🚫 Discard", key=f"discard_{doc_id}"):
                        db.collection("draft_news").document(doc_id).update({
                            "approved": True,
                            "status": "discarded"
                        })
                        st.toast("Marked as discarded.", icon="🚫")
                        st.rerun()

                with row2_col2:
                    if st.button("🗑️ Delete", key=f"delete_{doc_id}"):
                        db.collection("draft_news").document(doc_id).delete()
                        st.toast("Entry deleted.", icon="🗑️")
                        st.rerun()

                st.divider()

        render_pagination_controls(current_pending_page, total_pending_pages, "pending_page")

# ==========================================
# TAB 2: POSTED TO X
# ==========================================
with tab_posted:
    if not posted_articles:
        st.info("No articles posted to X yet.")
    else:
        if "posted_page" not in st.session_state:
            st.session_state.posted_page = 0

        total_posted_pages = max(1, (len(posted_articles) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        
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
                st.caption(f"🔗 [Source Link]({source_url}) | 📅 Date: **{created_str}**")

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

        render_pagination_controls(current_posted_page, total_posted_pages, "posted_page")
