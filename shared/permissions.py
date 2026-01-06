"""
Permission checking utilities for project and chat access control.
"""

import logging
from typing import Optional, Dict
from .supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class ForbiddenError(Exception):
    """Raised when a user doesn't have permission to access a resource."""
    pass


class NotFoundError(Exception):
    """Raised when a resource is not found."""
    pass


async def get_user_email(user_id: str) -> Optional[str]:
    """
    Get a user's email from their ID using the auth.users table.
    
    Args:
        user_id: The user's UUID
        
    Returns:
        User's email address or None if not found
    """
    try:
        client = get_supabase_client()
        # Query from auth.users via service role
        result = client.auth.admin.get_user_by_id(user_id)
        if result and result.user:
            return result.user.email
        return None
    except Exception as e:
        logger.error(f"Error getting user email: {str(e)}")
        return None


async def check_project_access(
    user_id: str,
    project_id: str,
    required_permission: str = "view"
) -> Dict:
    """
    Check if a user has access to a project.
    
    Args:
        user_id: The user's UUID
        project_id: The project's UUID
        required_permission: Required permission level ("view" or "edit")
        
    Returns:
        dict: {"access": True, "permission": "owner|edit|view", "is_owner": bool}
        
    Raises:
        NotFoundError: If project doesn't exist
        ForbiddenError: If user doesn't have required access
    """
    client = get_supabase_client()
    
    # 1. Fetch the project
    result = client.table("projects").select("*").eq("id", project_id).execute()
    
    if not result.data:
        raise NotFoundError(f"Project not found")
    
    project = result.data[0]
    
    # 2. Check if user is owner
    if project["user_id"] == user_id:
        return {
            "access": True,
            "permission": "owner",
            "is_owner": True,
            "project": project
        }
    
    # 3. Check if project is shared with user
    user_email = await get_user_email(user_id)
    if not user_email:
        raise ForbiddenError("Could not verify user email")
    
    share_result = client.table("project_shares") \
        .select("*") \
        .eq("project_id", project_id) \
        .eq("shared_with_email", user_email) \
        .execute()
    
    if share_result.data:
        share = share_result.data[0]
        share_permission = share["permission"]
        
        # Check if permission is sufficient
        if required_permission == "edit" and share_permission == "view":
            raise ForbiddenError("Edit permission required")
        
        return {
            "access": True,
            "permission": share_permission,
            "is_owner": False,
            "project": project
        }
    
    raise ForbiddenError("You don't have access to this project")


async def check_chat_access(
    user_id: str,
    chat_id: str,
    required_permission: str = "view"
) -> Dict:
    """
    Check if a user has access to a chat.
    User must either own the chat or have access to its associated project.
    
    Args:
        user_id: The user's UUID
        chat_id: The chat's UUID
        required_permission: Required permission level ("view" or "edit")
        
    Returns:
        dict: {"access": True, "permission": "owner|edit|view", "is_owner": bool, "chat": dict}
        
    Raises:
        NotFoundError: If chat doesn't exist
        ForbiddenError: If user doesn't have required access
    """
    client = get_supabase_client()
    
    # 1. Fetch the chat
    result = client.table("chats").select("*").eq("id", chat_id).execute()
    
    if not result.data:
        raise NotFoundError("Chat not found")
    
    chat = result.data[0]
    
    # 2. Check if user owns the chat
    if chat["user_id"] == user_id:
        return {
            "access": True,
            "permission": "owner",
            "is_owner": True,
            "chat": chat
        }
    
    # 3. If chat belongs to a project, check project access
    if chat.get("project_id"):
        try:
            project_access = await check_project_access(
                user_id,
                chat["project_id"],
                required_permission
            )
            return {
                "access": True,
                "permission": project_access["permission"],
                "is_owner": False,
                "chat": chat
            }
        except ForbiddenError:
            pass  # Fall through to the final error
    
    raise ForbiddenError("You don't have access to this chat")


async def check_is_project_owner(user_id: str, project_id: str) -> bool:
    """
    Check if a user is the owner of a project.
    
    Args:
        user_id: The user's UUID
        project_id: The project's UUID
        
    Returns:
        True if user is owner, False otherwise
    """
    client = get_supabase_client()
    
    result = client.table("projects") \
        .select("user_id") \
        .eq("id", project_id) \
        .execute()
    
    if not result.data:
        return False
    
    return result.data[0]["user_id"] == user_id


async def check_is_chat_owner(user_id: str, chat_id: str) -> bool:
    """
    Check if a user is the owner of a chat.
    
    Args:
        user_id: The user's UUID
        chat_id: The chat's UUID
        
    Returns:
        True if user is owner, False otherwise
    """
    client = get_supabase_client()
    
    result = client.table("chats") \
        .select("user_id") \
        .eq("id", chat_id) \
        .execute()
    
    if not result.data:
        return False
    
    return result.data[0]["user_id"] == user_id
