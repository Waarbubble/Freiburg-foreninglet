import streamlit as st
import importlib.util
import sys
import os

# Helper to import user-info.py module since it has a hyphen
def import_bifrost_client():
    module_name = "user_info"
    file_path = "user-info.py"
    if os.path.exists(file_path):
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module.BifrostClient
    return None

try:
    BifrostClient = import_bifrost_client()
except Exception as e:
    st.error(f"Failed to import BifrostClient from user-info.py: {e}")
    st.stop()

st.set_page_config(page_title="Jean Le Fier: Freiburg Member Portal", page_icon="⚓")
st.title("⚓ Jean Le Fier: Freiburg Member Portal")

# Initialize session state
if 'client' not in st.session_state:
    st.session_state.client = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def handle_login():
    if not st.session_state.email or not st.session_state.password:
        st.error("Please enter both email and password.")
        return

    client = BifrostClient()
    with st.spinner("Logging in..."):
        if client.login(st.session_state.email, st.session_state.password):
            st.session_state.client = client
            st.session_state.logged_in = True
            st.success("Logged in successfully!")
        else:
            st.error("Login failed. Please check your credentials.")

def handle_logout():
    st.session_state.client = None
    st.session_state.logged_in = False
    st.rerun()

if not st.session_state.logged_in:
    st.subheader("Login")
    with st.form("login_form"):
        st.text_input("Email", key="email")
        st.text_input("Password", type="password", key="password")
        st.form_submit_button("Login", on_click=handle_login)
    
    st.markdown("---")
    st.write("Har du ikke en bruger?")
    st.link_button("Bliv medlem", "https://www.freiburglarp.dk/foreningen/medlemskab")

else:
    client = st.session_state.client
    
    # 1. Memberships
    st.header("📝 Medlemskabs Status")
    with st.spinner("Checking memberships..."):
        try:
            memberships = client.fetch_memberships()
            if memberships:
                success = []
                for sub in memberships:
                    if sub['paid']:
                        success.append(sub)
                if(len(success) > 0):
                    for sub in success:
                        st.success(f"Active membership: {success[0]['name']}")
                else:
                    st.warning("No active memberships found.")
                    st.link_button("Bliv medlem", "https://www.freiburglarp.dk/foreningen/medlemskab")
            else:
                st.info("No membership information found.")
        except Exception as e:
            st.error(f"Error fetching memberships: {e}")

    # 2. User Info
    st.header("👤 Bruger Information")
    with st.spinner("Fetching profile..."):
        try:
            user_info = client.fetch_user_info()
            if user_info:
                # Display as a clean table or list
                for key, value in user_info.items():
                    st.text(f"{key}: {value}")
            else:
                st.info("No detailed user information available.")
        except Exception as e:
            st.error(f"Error fetching user info: {e}")

    # 3. Enrolled Events
    st.header("📅 Tilmeldte Events")
    with st.spinner("Fetching events..."):
        try:
            events = client.fetch_enrolled_events()
            if events:
                for event in events:
                    with st.expander(f"{event['name']} ({event['date']})"):
                        st.write(f"**Event ID:** {event['id']}")
                        st.write(f"**Name:** {event['name']}")
                        st.write(f"**Date:** {event['date']}")
            else:
                st.info("No upcoming events found.")
        except Exception as e:
            st.error(f"Error fetching events: {e}")

    # 4. Upcoming Freiburg Events
    st.header("🎟️ Andre Fremtidige Freiburg Events")
    with st.spinner("Searching for Freiburg events..."):
         try:
             freiburg_events = client.fetch_upcoming_freiburg_events()
             if freiburg_events:
                 for fe in freiburg_events:
                     with st.expander(f"{fe['title']} ({fe['date']})"):
                         st.write(f"**Title:** {fe['title']}")
                         st.write(f"**Date:** {fe['date']}")
                         if fe['url']:
                             st.markdown(f"[Link to Event]({fe['url']})")
             else:
                 st.info("No upcoming 'Freiburg' events found.")
         except Exception as e:
             st.error(f"Error fetching Freiburg events: {e}")

    st.markdown("---")
    st.button("Logout", on_click=handle_logout)
