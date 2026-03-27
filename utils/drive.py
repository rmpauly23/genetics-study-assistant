"""Google Drive OAuth2 authentication and file fetching."""

import io
import json
import urllib.parse
from typing import Optional

import requests
import streamlit as st


# Google OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_API = "https://www.googleapis.com/drive/v3"
GOOGLE_DOCS_EXPORT = "https://docs.google.com/document/d/{doc_id}/export?format=txt"

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_oauth_credentials() -> tuple[str, str]:
    """Retrieve Google OAuth client credentials from st.secrets."""
    try:
        client_id = st.secrets["GOOGLE_CLIENT_ID"]
        client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]
        return client_id, client_secret
    except KeyError as e:
        st.error(f"Missing secret: {e}. Check your st.secrets configuration.")
        st.stop()


def get_redirect_uri() -> str:
    """
    Build the redirect URI. On Streamlit Cloud this should be the app URL.
    Falls back to localhost for local dev.
    """
    try:
        return st.secrets["GOOGLE_REDIRECT_URI"]
    except KeyError:
        return "http://localhost:8501"


def build_auth_url() -> str:
    """Construct the Google OAuth2 authorization URL."""
    client_id, _ = get_oauth_credentials()
    redirect_uri = get_redirect_uri()

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code_for_tokens(code: str) -> Optional[dict]:
    """Exchange an authorization code for access/refresh tokens."""
    client_id, client_secret = get_oauth_credentials()
    redirect_uri = get_redirect_uri()

    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    resp = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    st.error(f"Token exchange failed: {resp.text}")
    return None


def refresh_access_token(refresh_token: str) -> Optional[str]:
    """Use a refresh token to obtain a new access token."""
    client_id, client_secret = get_oauth_credentials()

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    resp = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=30)
    if resp.status_code == 200:
        return resp.json().get("access_token")
    return None


def get_access_token() -> Optional[str]:
    """Return a valid access token, refreshing if needed."""
    tokens = st.session_state.get("google_tokens")
    if not tokens:
        return None

    # Try a lightweight test call; if 401, refresh
    access_token = tokens.get("access_token")
    test = requests.get(
        f"{GOOGLE_DRIVE_API}/about?fields=user",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if test.status_code == 200:
        return access_token

    refresh_token = tokens.get("refresh_token")
    if refresh_token:
        new_token = refresh_access_token(refresh_token)
        if new_token:
            st.session_state["google_tokens"]["access_token"] = new_token
            return new_token

    # Tokens are invalid — clear them
    st.session_state.pop("google_tokens", None)
    return None


def list_drive_items(folder_id: str = "root", page_token: str = None) -> dict:
    """
    List files and folders in a Drive folder.
    Returns {"items": [...], "nextPageToken": ...}
    """
    access_token = get_access_token()
    if not access_token:
        return {"items": [], "nextPageToken": None}

    if folder_id == "sharedWithMe":
        query = "sharedWithMe=true and trashed=false and (mimeType='application/vnd.google-apps.folder' or mimeType='application/pdf' or mimeType='application/vnd.google-apps.document')"
    else:
        query = f"'{folder_id}' in parents and trashed=false and (mimeType='application/vnd.google-apps.folder' or mimeType='application/pdf' or mimeType='application/vnd.google-apps.document')"
    params = {
        "q": query,
        "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,size)",
        "orderBy": "folder,name",
        "pageSize": 100,
        "includeItemsFromAllDrives": "true",
        "supportsAllDrives": "true",
    }
    if page_token:
        params["pageToken"] = page_token

    resp = requests.get(
        f"{GOOGLE_DRIVE_API}/files",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=30,
    )
    if resp.status_code != 200:
        st.error(f"Drive API error: {resp.text}")
        return {"items": [], "nextPageToken": None}

    data = resp.json()
    return {
        "items": data.get("files", []),
        "nextPageToken": data.get("nextPageToken"),
    }


def fetch_pdf_content(file_id: str) -> bytes:
    """Download a PDF file from Drive as bytes."""
    access_token = get_access_token()
    if not access_token:
        return b""

    resp = requests.get(
        f"{GOOGLE_DRIVE_API}/files/{file_id}?alt=media&supportsAllDrives=true",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=60,
    )
    if resp.status_code == 200:
        return resp.content
    st.error(f"Failed to fetch PDF: {resp.status_code}")
    return b""


def fetch_gdoc_content(file_id: str) -> str:
    """Export a Google Doc as plain text."""
    access_token = get_access_token()
    if not access_token:
        return ""

    resp = requests.get(
        f"{GOOGLE_DRIVE_API}/files/{file_id}/export?mimeType=text/plain&supportsAllDrives=true",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=60,
    )
    if resp.status_code == 200:
        return resp.text
    st.error(f"Failed to export Google Doc: {resp.status_code}")
    return ""


def handle_oauth_callback() -> bool:
    """
    Detect an OAuth callback code in query params and exchange it for tokens.
    Returns True if tokens were successfully obtained.
    """
    params = st.query_params
    code = params.get("code")
    if code and "google_tokens" not in st.session_state:
        tokens = exchange_code_for_tokens(code)
        if tokens:
            st.session_state["google_tokens"] = tokens
            # Clear code from URL
            st.query_params.clear()
            return True
    return False
