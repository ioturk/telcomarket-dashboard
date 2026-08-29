import streamlit as st
import os
import json
from google.cloud import firestore
from google.oauth2 import service_account

# Page setup
st.set_page_config(page_title="Telco News Admin", layout="centered", initial_sidebar_state="collapsed")

# 1. Simple Password Protection
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "default_secret")
user_pass = st.text_input("Enter Admin Password", type="password")

if user_pass != ADMIN_PASSWORD:
    if user_pass:
        st.error("Incorrect password.")
    st.stop()

st.title("📲 Telecom News Admin")

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
    st.info("No articles currently pending review.")

for article in articles:
    with st.container():
        st.subheader(article.get("title", "No Title"))
        st.write(article.get("summary", "No summary available."))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Discard", key=f"discard_{article['id']}"):
                # Set approved to "discarded" so it leaves the pending queue
                db.collection("draft_news").document(article["id"]).update({"approved": "discarded"})
                st.rerun()
                
        with col2:
            if st.button("🚀 Approve & Send", key=f"send_{article['id']}"):
                # Mark as approved so your backend publisher picks it up
                db.collection("draft_news").document(article["id"]).update({"approved": True})
                st.rerun()
        st.divider()
