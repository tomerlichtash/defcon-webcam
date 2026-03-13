"""Descope authentication for admin routes — backend OAuth flow."""

from lib.config import load_admin_config

_descope_client = None


def _get_client():
    global _descope_client
    if _descope_client is None:
        try:
            from descope import DescopeClient

            cfg = load_admin_config()
            project_id = cfg.get("descope_project_id", "")
            if not project_id:
                print("Warning: DESCOPE_PROJECT_ID not set", flush=True)
                return None
            _descope_client = DescopeClient(
                project_id=project_id, jwt_validation_leeway=300
            )
        except ImportError:
            print(
                "Warning: descope package not installed (pip install descope)",
                flush=True,
            )
            return None
        except Exception as e:
            print(f"Descope init error: {e}", flush=True)
            return None
    return _descope_client


def start_oauth(provider, return_url):
    """Start an OAuth flow. Returns the redirect URL or None."""
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.oauth.start(provider=provider, return_url=return_url)
        return resp.get("url")
    except Exception as e:
        print(f"OAuth start error: {e}", flush=True)
        return None


def exchange_oauth(code):
    """Exchange an OAuth code for session + refresh tokens. Returns (session_jwt, refresh_jwt) or (None, None)."""
    client = _get_client()
    if client is None:
        return None, None
    try:
        from descope import SESSION_TOKEN_NAME, REFRESH_SESSION_TOKEN_NAME

        resp = client.oauth.exchange_token(code)
        session_jwt = resp.get(SESSION_TOKEN_NAME, {}).get("jwt")
        refresh_jwt = resp.get(REFRESH_SESSION_TOKEN_NAME, {}).get("jwt")
        return session_jwt, refresh_jwt
    except Exception as e:
        print(f"OAuth exchange error: {e}", flush=True)
        return None, None


def validate_session(session_token):
    """Validate a Descope session token. Returns user info dict or None."""
    if not session_token:
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        jwt = client.validate_session(session_token)
        return jwt
    except Exception:
        return None


def refresh_session(refresh_token):
    """Use a refresh token to get a new session token. Returns new session JWT or None."""
    if not refresh_token:
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.refresh_session(refresh_token)
        return resp.get("sessionJwt") or resp.get("sessionToken")
    except Exception:
        return None


def is_authenticated(headers):
    """Check Authorization header or cookies for a valid Descope session.

    Tries session token first, then auto-refreshes using the refresh token.
    Returns (authed: bool, new_session_jwt: str|None).
    new_session_jwt is set when a refresh occurred, so the caller can update the cookie.
    """
    # Check Authorization: Bearer <token> header first
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        if validate_session(token) is not None:
            return True, None

    # Try admin_session cookie
    cookie_header = headers.get("Cookie", "")
    session_token = None
    refresh_token = None
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith("admin_session="):
            session_token = part[len("admin_session="):]
        elif part.startswith("admin_refresh="):
            refresh_token = part[len("admin_refresh="):]

    if session_token and validate_session(session_token) is not None:
        return True, None

    # Session expired — try refresh
    if refresh_token:
        new_session = refresh_session(refresh_token)
        if new_session:
            return True, new_session

    return False, None
