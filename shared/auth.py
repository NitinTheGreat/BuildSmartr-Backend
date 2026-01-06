"""
JWT validation and user extraction utilities for Supabase Auth.
"""

import os
import jwt
import logging
from functools import wraps
from typing import Optional, Callable, Any
import azure.functions as func

logger = logging.getLogger(__name__)


class UnauthorizedError(Exception):
    """Raised when authentication fails."""
    pass


def get_jwt_secret() -> str:
    """Get the Supabase JWT secret from environment variables."""
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise ValueError("SUPABASE_JWT_SECRET environment variable not set")
    return secret


def get_user_from_token(req: func.HttpRequest) -> dict:
    """
    Extract and validate user from Authorization header.
    
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
        jwt_secret = get_jwt_secret()
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated"
        )
        
        return {
            "id": payload["sub"],
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated")
        }
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise UnauthorizedError("Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise UnauthorizedError("Invalid token")


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
