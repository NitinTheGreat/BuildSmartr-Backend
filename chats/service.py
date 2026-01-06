"""
Business logic for chat operations.
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime
from shared.supabase_client import get_supabase_client
from shared.permissions import (
    check_project_access, check_chat_access,
    NotFoundError, ForbiddenError
)

logger = logging.getLogger(__name__)


class ChatService:
    """Service class for chat CRUD operations."""
    
    VALID_CHAT_TYPES = ["project", "general"]
    
    def __init__(self):
        self.client = get_supabase_client()
    
    async def list_general_chats(self, user_id: str) -> List[Dict]:
        """
        List all general chats owned by the user.
        
        Args:
            user_id: The authenticated user's ID
            
        Returns:
            List of general chat records
        """
        result = self.client.table("chats") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("chat_type", "general") \
            .order("updated_at", desc=True) \
            .execute()
        
        return result.data
    
    async def list_project_chats(self, user_id: str, project_id: str) -> List[Dict]:
        """
        List all chats for a project.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            
        Returns:
            List of project chat records
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user doesn't have access
        """
        # Check project access (view permission is sufficient)
        await check_project_access(user_id, project_id, "view")
        
        result = self.client.table("chats") \
            .select("*") \
            .eq("project_id", project_id) \
            .eq("chat_type", "project") \
            .order("updated_at", desc=True) \
            .execute()
        
        return result.data
    
    async def get_chat(self, user_id: str, chat_id: str, include_messages: bool = True) -> Dict:
        """
        Get a single chat with optional messages.
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            include_messages: Whether to include messages
            
        Returns:
            Chat data with optional messages
            
        Raises:
            NotFoundError: If chat doesn't exist
            ForbiddenError: If user doesn't have access
        """
        # Check access and get chat
        access = await check_chat_access(user_id, chat_id, "view")
        chat = access["chat"]
        chat["is_owner"] = access["is_owner"]
        chat["permission"] = access["permission"]
        
        if include_messages:
            messages_result = self.client.table("messages") \
                .select("*") \
                .eq("chat_id", chat_id) \
                .order("timestamp", desc=False) \
                .execute()
            chat["messages"] = messages_result.data
        
        return chat
    
    async def create_general_chat(self, user_id: str, title: Optional[str] = None) -> Dict:
        """
        Create a new general chat.
        
        Args:
            user_id: The authenticated user's ID
            title: Optional chat title
            
        Returns:
            Created chat record
        """
        chat_data = {
            "user_id": user_id,
            "title": title or "New Chat",
            "chat_type": "general",
            "project_id": None,
        }
        
        result = self.client.table("chats") \
            .insert(chat_data) \
            .execute()
        
        if result.data:
            chat = result.data[0]
            chat["is_owner"] = True
            chat["permission"] = "owner"
            chat["messages"] = []
            return chat
        
        raise Exception("Failed to create chat")
    
    async def create_project_chat(
        self,
        user_id: str,
        project_id: str,
        title: Optional[str] = None
    ) -> Dict:
        """
        Create a new project chat.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            title: Optional chat title
            
        Returns:
            Created chat record
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user doesn't have edit access
        """
        # Check edit access to project
        access = await check_project_access(user_id, project_id, "edit")
        
        chat_data = {
            "user_id": user_id,
            "project_id": project_id,
            "title": title or "New Chat",
            "chat_type": "project",
        }
        
        result = self.client.table("chats") \
            .insert(chat_data) \
            .execute()
        
        if result.data:
            chat = result.data[0]
            chat["is_owner"] = True
            chat["permission"] = "owner"
            chat["messages"] = []
            return chat
        
        raise Exception("Failed to create chat")
    
    async def update_chat(self, user_id: str, chat_id: str, title: str) -> Dict:
        """
        Update a chat's title (owner only).
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            title: New chat title
            
        Returns:
            Updated chat record
            
        Raises:
            NotFoundError: If chat doesn't exist
            ForbiddenError: If user is not the owner
        """
        # Check ownership
        access = await check_chat_access(user_id, chat_id)
        if not access["is_owner"]:
            raise ForbiddenError("Only the chat owner can update the chat")
        
        update_data = {
            "title": title,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = self.client.table("chats") \
            .update(update_data) \
            .eq("id", chat_id) \
            .execute()
        
        if result.data:
            chat = result.data[0]
            chat["is_owner"] = True
            chat["permission"] = "owner"
            return chat
        
        raise Exception("Failed to update chat")
    
    async def delete_chat(self, user_id: str, chat_id: str) -> bool:
        """
        Delete a chat (owner only).
        All related messages will be deleted via CASCADE.
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundError: If chat doesn't exist
            ForbiddenError: If user is not the owner
        """
        # Check ownership
        access = await check_chat_access(user_id, chat_id)
        if not access["is_owner"]:
            raise ForbiddenError("Only the chat owner can delete the chat")
        
        # Delete the chat (CASCADE will handle messages)
        self.client.table("chats") \
            .delete() \
            .eq("id", chat_id) \
            .execute()
        
        return True
