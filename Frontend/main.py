import time
import streamlit as st
import streamlit.components.v1 as components
from streamlit_javascript import st_javascript
import json
import requests

import requests

from user_client import AuthClient, AuthException
from env import EnvConfig

st.set_page_config(page_title="Scenario Builder", layout="wide")

LOCAL_STORAGE_KEY = "safetoken"
API_AUTH = EnvConfig.BASE_AUTH

# --------------------------
# here the initialization of 
# the state valieables is done
# --------------------------
if "is_authenticated" not in st.session_state:
    st.session_state.is_authenticated = False

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None

if "created_scenario" not in st.session_state:
    st.session_state.created_scenario = None

if "user_scenarios" not in st.session_state:
    st.session_state.user_scenarios = None

if "selected_scenario" not in st.session_state:
    st.session_state.selected_scenario = None

if "first_token_check" not in st.session_state:
    st.session_state.first_token_check = None


LOCAL_STORAGE_KEY = "safetoken"
API_AUTH = EnvConfig.BASE_AUTH

# ''' Here we add helpers methods about the session managmenet'''
# --------------------------
# Helpers - Using st_javascript
# These run in the top-level browser context,
# so localStorage persists across reloads ---> this solves the problem in contrast to
# to HTML.component that has access to the iframe storage.
# --------------------------
def _save_refresh_token_to_browser(refresh_token: str):
    script = f"window.localStorage.setItem('{LOCAL_STORAGE_KEY}', {json.dumps(refresh_token)}); true;"
    st_javascript(script)
    st.write("Token saved to localStorage (browser).")


def _clear_refresh_token_in_browser():
    script = f"window.localStorage.removeItem('{LOCAL_STORAGE_KEY}'); true;"
    st_javascript(script)
    st.write("Token cleared from localStorage.")


# this method is the core for the session management:
# 1. in the case user enters the page for first time, is not authenticated so -> goes at login page
# 2. in case is not authenticated:
#     a. try to get the token from local storage
#         1. if is none return and go at the login page
#         2. else do a refresh and update session state ->
#            (is_authenticated,access_token,refresh_token)
# 

def _restore_session_from_browser():
    if st.session_state.is_authenticated:
        return

    # Read token directly from browser
    refresh_token = st_javascript(f"window.localStorage.getItem('{LOCAL_STORAGE_KEY}');")

    # If no token saved, nothing to do
    if not refresh_token or refresh_token == "null":
        return

    try:
        with st.spinner("Restoring your session..."):
            resp = requests.post(
                f"{API_AUTH}/refresh",
                json={"refresh_token": refresh_token},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.access_token = data["access_token"]
                st.session_state.refresh_token = data["refresh_token"]
                st.session_state.is_authenticated = True
                _save_refresh_token_to_browser(st.session_state.refresh_token)
                st.success("✅ Session restored successfully!")
                time.sleep(0.5)
                st.rerun()
            else:
                # if something goes wrong clear token and go into the login page:
                _clear_refresh_token_in_browser()
                st.warning("Session expired, please log in again.")
                st.rerun()
    except Exception as e:
        print(f"Session restore error: {e}")
        _clear_refresh_token_in_browser()



def get_client(username: str | None = None, password: str | None = None) -> AuthClient:
    """Get or create AuthClient with current session tokens"""
    if st.session_state.access_token and st.session_state.refresh_token:
        # Use existing tokens, in case the access token is 
        # expired client does autorefresh # TODO THIS IS PROBLEMATIC
        c = AuthClient()
        c.access_token = st.session_state.access_token
        c.refresh_token = st.session_state.refresh_token
        return c
    else:
        # New login required
        if not username or not password:
            raise RuntimeError("Username and password required")
        c = AuthClient(username=username, password=password)
        c.login()
        # Save tokens to session - here the tokens are update:
        st.session_state.access_token = c.access_token
        st.session_state.refresh_token = c.refresh_token
        # Save refresh token to browser
        _save_refresh_token_to_browser(c.refresh_token)
        return c


# --------------------------
# Callbacks
# --------------------------
def clear_selection_callback():
    st.session_state.selected_scenario = None
    st.session_state.created_scenario = None


def create_scenario_callback():
    title = st.session_state.new_scenario_title
    prompt = st.session_state.new_scenario_prompt
    try:
        with st.spinner("Generating scenario..."):
            new_scenario = get_client().create_scenario(
                    scenario_name=title,
                    instructions=prompt)
            
        st.session_state.new_scenario_title = ""
        st.session_state.new_scenario_prompt = ""
        st.session_state.created_scenario = new_scenario
        st.success("Scenario created successfully!")
    
    except AuthException as e:
        _clear_refresh_token_in_browser()
        st.session_state.clear()
        st.warning(f"⏰ {e.message} - Please login again")
        st.rerun()
    except Exception:
        st.error("Error: Please try to create the scenario again")
        st.stop()


def update_scenario_for_feedback_callback(context, scenario_id: str):
    try:
        get_client().update_feedback_scenario(
            context=context,
            scenario_id=scenario_id
        )
        st.session_state.user_scenarios = None
        st.session_state.created_scenario = None
        st.success("✅ Scenario updated!")
    except AuthException as e:
        _clear_refresh_token_in_browser()
        st.session_state.clear()
        st.warning(f"⏰ {e.message} - Please login again")
        st.rerun()
    except Exception:
        st.error("Update failed. Please try again.")
        raise


# --------------------------
# Pages
# --------------------------
def login_page():
    st.title("Scenario Builder Login")
    username = st.text_input("Username", key="username")
    password = st.text_input("Password", type="password", key="password")

    if st.button("Login"):
        try:
            # Login and save tokens
            get_client(username, password)
            st.session_state.is_authenticated = True
            st.success("✅ Login successful!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")


def app_page():
    # lazy fetch scenarios
    if st.session_state.user_scenarios is None:
        with st.spinner("Loading your scenarios..."):
            try:
                st.session_state.user_scenarios = get_client().get_scenario()
            except AuthException as e:
                _clear_refresh_token_in_browser()
                st.session_state.clear()
                st.warning(f"⏰ {e.message} - Please login again")
                st.rerun()
    st.sidebar.title("📚 Your Scenarios")
    st.sidebar.button("➕ Create scenario", key="create_new_scenario", on_click=clear_selection_callback)

    scenario_names = {}
    for index, s in enumerate(st.session_state.user_scenarios or []):
        scenario_names[f"{index}. {s['scenario_name']}"] = s["_id"]

    st.sidebar.selectbox(
        "Select a scenario:",
        options=list(scenario_names.keys()),
        key="selected_scenario",
        index=None,
        placeholder="Choose an existing scenario or create a new one",
    )
    st.sidebar.divider()

    # Selected scenario editor
    if st.session_state.get("selected_scenario"):
        scenario_id = scenario_names[st.session_state.selected_scenario]
        scenario_data = next(s for s in st.session_state.user_scenarios if s["_id"] == scenario_id)

        st.header(f"📄 Scenario: {scenario_data['scenario_name']}")
        st.caption(f"scenario ID: `{scenario_data['_id']}`")

        for idx, item in enumerate(scenario_data["context"]):
            with st.expander(f"{idx+1}. {item['title']} — {item['message_timestamp']}", expanded=False):
                item["title"] = st.text_input("Title", value=item["title"], key=f"title_{idx}")
                item["message_timestamp"] = st.text_input("Timestamp", value=item["message_timestamp"], key=f"time_{idx}")
                item["description"] = st.text_area("Description", value=item["description"], key=f"desc_{idx}")
                item["inject"] = st.text_area("Inject", value=item["inject"], key=f"inject_{idx}")

                st.subheader("Expected Actions")
                for a_idx, action in enumerate(item["expected_actions"]):
                    item["expected_actions"][a_idx] = st.text_area(
                        f"Action {a_idx+1}",
                        value=action,
                        key=f"action_{idx}_{a_idx}"
                    )

    # Create scenario flow
    else:
        if st.session_state.created_scenario is None:
            st.title("🛡️ Create a new Cyber Attack Scenario")
            st.text_input("Scenario Title", key="new_scenario_title", value="")
            st.divider()
            st.text_area(
                "Scenario Description",
                placeholder="Chat create a DDoS cyber attack",
                key="new_scenario_prompt",
                value=""
            )
            st.button("🚀 Generate Scenario", key="generate_new", on_click=create_scenario_callback)
        else:
            incidents = []
            for idx, item in enumerate(st.session_state.created_scenario["context"]):
                with st.expander(f"{idx+1}. {item['title']} — {item['message_timestamp']}", expanded=False):
                    item["title"] = st.text_input("Title", value=item["title"], key=f"new_title_{idx}")
                    item["message_timestamp"] = st.text_input("Timestamp", value=item["message_timestamp"], key=f"new_time_{idx}")
                    item["description"] = st.text_area("Description", value=item["description"], key=f"new_desc_{idx}")
                    item["inject"] = st.text_area("Inject", value=item["inject"], key=f"new_inject_{idx}")

                    st.subheader("Expected Actions")
                    for a_idx, action in enumerate(item["expected_actions"]):
                        item["expected_actions"][a_idx] = st.text_area(
                            "",
                            value=action,
                            key=f"new_action_{idx}_{a_idx}"
                        )
                incidents.append(item)

            st.button(
                "💾 Save Changes",
                key="save",
                on_click=update_scenario_for_feedback_callback,
                args=(incidents, st.session_state.created_scenario["_id"])
            )

    # Logout
    if st.sidebar.button("Logout", key="logout"):
        _clear_refresh_token_in_browser()
        st.session_state.clear()
        st.success("Logged out successfully!")
        time.sleep(1)
        st.rerun()


# --------------------------
# Router
# --------------------------

# first thing is to try to restore
# the session from browser and inform
# streamlit session:
_restore_session_from_browser()

# in case there is not stored session:
if not st.session_state.is_authenticated:
    login_page()
# in case there is stored session:
else:
    app_page()