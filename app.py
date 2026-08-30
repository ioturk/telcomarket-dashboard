import streamlit as st
import os
import json
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

# 3. Load Pending Articles (draft_news collection where approved == False)
articles_ref = db.collection("draft_news").where("approved", "==", False).stream()
articles = [doc.to_dict() | {"id": doc.id} for doc in articles_ref]

if not articles:
    st.info("🎉 No articles currently pending review.")

for article in articles:
    with st.container():
        # Title and Source URL
        st.subheader(article.get("title", "No Title"))
        source_url = article.get("url", "#")
        st.caption(f"🔗 Source: [{source_url}]({source_url})")

        # Editable or previewable X Draft Content
        draft_text = article.get("draft_content", "No content generated.")
        st.text_area(
            "X Post Draft",
            value=draft_text,
            height=120,
            key=f"text_{article['id']}",
            disabled=True
        )

        # Character Counter Indicator for X limit
        char_count = len(draft_text)
        if char_count > 280:
            st.warning(f"⚠️ Character count: {char_count}/280 (Exceeds standard post limit)")
        else:
            st.caption(f"📏 Character count: {char_count}/280")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Discard", key=f"discard_{article['id']}"):
                db.collection("draft_news").document(article["id"]).update({"approved": "discarded"})
                st.rerun()
                
        with col2:
            if st.button("🚀 Approve & Send", key=f"send_{article['id']}"):
                db.collection("draft_news").document(article["id"]).update({"approved": True})
                st.rerun()
                
        st.divider()
