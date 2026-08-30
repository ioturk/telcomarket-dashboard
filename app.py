import streamlit as st
import os
import json
import tweepy
from google.cloud import firestore
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

# Navigation Tabs
tab_pending, tab_posted = st.tabs(["⏳ Pending Review", "✅ Posted to X"])

# ==========================================
# TAB 1: PENDING REVIEW (approved == False)
# ==========================================
with tab_pending:
    pending_ref = db.collection("draft_news").where("approved", "==", False).stream()
    pending_articles = [doc.to_dict() | {"id": doc.id} for doc in pending_ref]

    if not pending_articles:
        st.info("🎉 No articles currently pending review.")

    for article in pending_articles:
        doc_id = article["id"]
        with st.container():
            st.subheader(article.get("title", "No Title"))
            source_url = article.get("url", "#")
            st.caption(f"🔗 Source: [{source_url}]({source_url})")

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
                # 1. Save Button
                if st.button("💾 Save", key=f"save_{doc_id}"):
                    db.collection("draft_news").document(doc_id).update({"draft_content": edited_content})
                    st.toast("Draft updated successfully!", icon="✅")

            with col2:
                # 2. Delete Button (removes entry completely from database)
                if st.button("🗑️ Delete", key=f"delete_{doc_id}"):
                    db.collection("draft_news").document(doc_id).delete()
                    st.toast("Entry deleted from database.", icon="🗑️")
                    st.rerun()

            with col3:
                # 3. Discard Button (reverts approved field to True)
                if st.button("🚫 Discard", key=f"discard_{doc_id}"):
                    db.collection("draft_news").document(doc_id).update({
                        "approved": True,
                        "status": "discarded"
                    })
                    st.toast("Article marked as discarded.", icon="🚫")
                    st.rerun()

            with col4:
                # 4. Post to X Button
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

# ==========================================
# TAB 2: POSTED TO X (posted_to_x == True)
# ==========================================
with tab_posted:
    posted_ref = db.collection("draft_news").where("posted_to_x", "==", True).stream()
    posted_articles = [doc.to_dict() | {"id": doc.id} for doc in posted_ref]

    if not posted_articles:
        st.info("No articles posted to X yet.")

    for article in posted_articles:
        doc_id = article["id"]
        with st.container():
            st.subheader(article.get("title", "No Title"))
            source_url = article.get("url", "#")
            st.caption(f"🔗 Source: [{source_url}]({source_url})")

            st.code(article.get("draft_content", ""), language="markdown")
            
            tweet_id = article.get("tweet_id")
            if tweet_id:
                st.caption(f"📱 Tweet ID: `{tweet_id}`")

            if st.button("🗑️ Delete Record", key=f"del_posted_{doc_id}"):
                db.collection("draft_news").document(doc_id).delete()
                st.rerun()

            st.divider()
