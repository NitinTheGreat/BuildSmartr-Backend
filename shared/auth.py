"""
JWT validation and user extraction utilities for Supabase Auth.
Supports both HS256 (legacy) and ES256 (JWKS) token verification.
"""

import os
import jwt
from jwt import PyJWKClient
import logging
from functools import wraps
from typing import Optional, Callable, Any
import azure.functions as func

logger = logging.getLogger(__name__)

# Cache the JWKS client to avoid repeated fetches
_jwks_client: Optional[PyJWKClient] = None


class UnauthorizedError(Exception):
    """Raised when authentication fails."""
    pass


def get_supabase_url() -> str:
    """Get the Supabase URL from environment variables."""
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise ValueError("SUPABASE_URL environment variable not set")
    return url.rstrip('/')


def get_jwks_client() -> PyJWKClient:
    """
    Get or create the JWKS client for Supabase token verification.
    Uses the Supabase JWKS endpoint for ES256 token verification.
    """
    global _jwks_client
    if _jwks_client is None:
        supabase_url = get_supabase_url()
        jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
        logger.info(f"Initializing JWKS client with URL: {jwks_url}")
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def get_user_from_token(req: func.HttpRequest) -> dict:
    """
    Extract and validate user from Authorization header.
    Supports both ES256 (JWKS) and HS256 (legacy) tokens.
    
    Args:
        req: The HTTP request object
        
    Returns:
        dict with user info: {"id": str, "email": str, "role": str}
        
    Raises:
        UnauthorizedError: If token is missing, expired, or invalid
    """
    auth_header = req.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    
    token = auth_header[7:]
    
    try:
        # First decode without verification to check the algorithm
        try:
            unverified_header = jwt.get_unverified_header(token)
            token_alg = unverified_header.get('alg')
            logger.info(f"Token algorithm: {token_alg}")
        except jwt.exceptions.DecodeError as e:
            logger.warning(f"Could not read token header: {e}")
            raise UnauthorizedError("Invalid token format")
        
        # Use appropriate verification method based on algorithm
        if token_alg == "ES256":
            # New Supabase tokens use ES256 with JWKS
            payload = _verify_es256_token(token)
        elif token_alg == "HS256":
            # Legacy Supabase tokens use HS256 with static secret
            payload = _verify_hs256_token(token)
        else:
            logger.error(f"Unsupported algorithm: {token_alg}")
            raise UnauthorizedError(f"Unsupported token algorithm: {token_alg}")
        
        logger.info(f"Token validated for user: {payload.get('sub')}")
        
        return {
            "id": payload["sub"],
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated")
        }
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise UnauthorizedError("Token expired")
    except jwt.InvalidAudienceError:
        logger.warning("Invalid audience in token")
        raise UnauthorizedError("Invalid token audience")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise UnauthorizedError("Invalid token")
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise UnauthorizedError("Token verification failed")


def _verify_es256_token(token: str) -> dict:
    """Verify an ES256 token using JWKS."""
    jwks_client = get_jwks_client()
    
    # Get the signing key from JWKS
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    
    # Decode and verify the token
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256"],
        audience="authenticated",
        options={
            "verify_signature": True,
            "verify_aud": True,
            "verify_exp": True,
            "require": ["sub", "exp", "aud"]
        }
    )
    return payload


def _verify_hs256_token(token: str) -> dict:
    """Verify an HS256 token using the static JWT secret (legacy)."""
    import base64
    
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise ValueError("SUPABASE_JWT_SECRET not set for HS256 verification")
    
    # Handle base64-encoded secrets
    try:
        if secret.endswith('==') or secret.endswith('='):
            jwt_secret = base64.b64decode(secret)
        else:
            jwt_secret = secret.encode('utf-8')
    except Exception:
        jwt_secret = secret.encode('utf-8')
    
    # Decode and verify the token
    payload = jwt.decode(
        token,
        jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
        options={
            "verify_signature": True,
            "verify_aud": True,
            "verify_exp": True,
            "require": ["sub", "exp", "aud"]
        }
    )
    return payload


def require_auth(func: Callable) -> Callable:
    """
    Decorator for authenticated endpoints.
    Extracts user from token and adds to request context.
    
    Usage:
        @require_auth
        async def my_endpoint(req: func.HttpRequest) -> func.HttpResponse:
            user = req.user  # Access the authenticated user
            ...
    """
    @wraps(func)
    async def wrapper(req: func.HttpRequest, *args, **kwargs) -> func.HttpResponse:
        try:
            user = get_user_from_token(req)
            # Store user in request for later access
            req.user = user
            return await func(req, *args, **kwargs)
        except UnauthorizedError as e:
            from .responses import error_response
            return error_response(str(e), 401)
    return wrapper


def get_user_id_from_request(req: func.HttpRequest) -> str:
    """
    Get the user ID from an authenticated request.
    Must be called after require_auth decorator.
    """
    if hasattr(req, 'user'):
        return req.user.get('id')
    raise UnauthorizedError("User not authenticated")


def get_user_email_from_request(req: func.HttpRequest) -> Optional[str]:
    """
    Get the user email from an authenticated request.
    Must be called after require_auth decorator.
    """
    if hasattr(req, 'user'):
        return req.user.get('email')
    return None
