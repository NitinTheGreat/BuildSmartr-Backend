# Shared utilities for BuildSmartr Backend
from .auth import get_user_from_token, UnauthorizedError
from .supabase_client import get_supabase_client, get_supabase_admin_client
from .responses import success_response, error_response, created_response, no_content_response, not_found_response, forbidden_response, validation_error_response
from .permissions import check_project_access, check_chat_access, ForbiddenError, NotFoundError

__all__ = [
    "get_user_from_token",
    "UnauthorizedError",
    "get_supabase_client",
    "get_supabase_admin_client",
    "success_response",
    "error_response",
    "created_response",
    "no_content_response",
    "not_found_response",
    "forbidden_response",
    "validation_error_response",
    "check_project_access",
    "check_chat_access",
    "ForbiddenError",
    "NotFoundError",
]
