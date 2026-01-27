"""
OAuth2 helper functions for Gmail and Outlook.
Handles OAuth flows for email integration.
"""
import os
import requests
import urllib.parse
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

def get_frontend_url() -> str:
    """Get frontend URL for redirects."""
    return os.environ.get("FRONTEND_URL", "http://localhost:3000")

def get_backend_url() -> str:
    """Get backend URL for OAuth callbacks."""
    return os.environ.get("BACKEND_URL", "http://localhost:7072")

# ============================================================
# GOOGLE OAUTH
# ============================================================

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]


def get_google_client_id() -> Optional[str]:
    """Get Google Client ID from environment."""
    return os.environ.get("GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_WEB_CLIENT_ID")


def get_google_client_secret() -> Optional[str]:
    """Get Google Client Secret from environment."""
    return os.environ.get("GOOGLE_CLIENT_SECRET") or os.environ.get("GOOGLE_WEB_CLIENT_SECRET")


def get_google_redirect_uri() -> str:
    """Get Google OAuth redirect URI."""
    # For local dev, use frontend callback
    # For production, this should match what's configured in Google Console
    return f"{get_frontend_url()}/api/email/gmail/callback"


def get_google_auth_url(state: Optional[str] = None) -> str:
    """Generate Google Login URL."""
    client_id = get_google_client_id()
    
    if not client_id:
        logger.error("Missing GOOGLE_CLIENT_ID environment variable")
        return "#error-missing-google-client-id"
    
    params = {
        "client_id": client_id,
        "redirect_uri": get_google_redirect_uri(),
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # Force consent to get refresh token
    }
    
    if state:
        params["state"] = state
    
    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    logger.info(f"Generated Google auth URL with redirect: {get_google_redirect_uri()}")
    return auth_url


def exchange_google_code(code: str) -> Optional[Dict[str, Any]]:
    """Exchange authorization code for tokens."""
    client_id = get_google_client_id()
    client_secret = get_google_client_secret()
    
    if not client_id or not client_secret:
        logger.error("Missing Google Client ID or Secret")
        return None
    
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": get_google_redirect_uri()
    }
    
    try:
        response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=30)
        response.raise_for_status()
        tokens = response.json()
        logger.info("Successfully exchanged Google authorization code for tokens")
        return tokens
    except requests.exceptions.RequestException as e:
        logger.error(f"Google Token Exchange Failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response Body: {e.response.text}")
        return None


def get_google_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get user info from Google using access token."""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(GOOGLE_USERINFO_URL, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get Google user info: {e}")
        return None


def build_gmail_credentials(tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Build Gmail credentials object from OAuth tokens."""
    return {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "token_uri": GOOGLE_TOKEN_URL,
        "client_id": get_google_client_id(),
        "client_secret": get_google_client_secret(),
        "scopes": GOOGLE_SCOPES,
    }


# ============================================================
# MICROSOFT OAUTH
# ============================================================

MICROSOFT_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MICROSOFT_GRAPH_URL = "https://graph.microsoft.com/v1.0/me"

MICROSOFT_SCOPES = [
    "User.Read",
    "Mail.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "Contacts.Read",
    "People.Read",
    "offline_access"
]


def get_microsoft_client_id() -> Optional[str]:
    """Get Microsoft Client ID from environment."""
    return os.environ.get("MICROSOFT_CLIENT_ID")


def get_microsoft_client_secret() -> Optional[str]:
    """Get Microsoft Client Secret from environment."""
    return os.environ.get("MICROSOFT_CLIENT_SECRET")


def get_microsoft_redirect_uri() -> str:
    """Get Microsoft OAuth redirect URI."""
    return f"{get_frontend_url()}/api/email/outlook/callback"


def get_microsoft_auth_url(state: Optional[str] = None) -> str:
    """Generate Microsoft Login URL."""
    client_id = get_microsoft_client_id()
    
    if not client_id:
        logger.error("Missing MICROSOFT_CLIENT_ID environment variable")
        return "#error-missing-microsoft-client-id"
    
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": get_microsoft_redirect_uri(),
        "response_mode": "query",
        "scope": " ".join(MICROSOFT_SCOPES),
    }
    
    if state:
        params["state"] = state
    
    auth_url = f"{MICROSOFT_AUTH_URL}?{urllib.parse.urlencode(params)}"
    logger.info(f"Generated Microsoft auth URL with redirect: {get_microsoft_redirect_uri()}")
    return auth_url


def exchange_microsoft_code(code: str) -> Optional[Dict[str, Any]]:
    """Exchange authorization code for tokens."""
    client_id = get_microsoft_client_id()
    client_secret = get_microsoft_client_secret()
    
    if not client_id or not client_secret:
        logger.error("Missing Microsoft Client ID or Secret")
        return None
    
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": " ".join(MICROSOFT_SCOPES),
        "code": code,
        "redirect_uri": get_microsoft_redirect_uri(),
        "grant_type": "authorization_code"
    }
    
    try:
        response = requests.post(MICROSOFT_TOKEN_URL, data=data, timeout=30)
        response.raise_for_status()
        tokens = response.json()
        logger.info("Successfully exchanged Microsoft authorization code for tokens")
        return tokens
    except requests.exceptions.RequestException as e:
        logger.error(f"Microsoft Token Exchange Failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response Body: {e.response.text}")
        return None


def get_microsoft_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get user info from Microsoft Graph using access token."""
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(MICROSOFT_GRAPH_URL, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get Microsoft user info: {e}")
        return None


def build_outlook_credentials(tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Build Outlook credentials object from OAuth tokens."""
    return {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "token_uri": MICROSOFT_TOKEN_URL,
        "client_id": get_microsoft_client_id(),
        "client_secret": get_microsoft_client_secret(),
        "scopes": MICROSOFT_SCOPES,
    }
