"""
Business logic for message operations.
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime
from shared.supabase_client import get_supabase_client
from shared.permissions import (
    check_chat_access, check_is_chat_owner,
    NotFoundError, ForbiddenError
)

logger = logging.getLogger(__name__)


class MessageService:
    """Service class for message CRUD operations."""
    
    VALID_ROLES = ["user", "assistant"]
    VALID_SEARCH_MODES = ["web", "email", "quotes", "pdf"]
    
    def __init__(self):
        self.client = get_supabase_client()
    
    async def list_messages(self, user_id: str, chat_id: str) -> List[Dict]:
        """
        List all messages in a chat.
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            
        Returns:
            List of message records
            
        Raises:
            NotFoundError: If chat doesn't exist
            ForbiddenError: If user doesn't have access
        """
        # Check chat access (view permission is sufficient)
        await check_chat_access(user_id, chat_id, "view")
        
        result = self.client.table("messages") \
            .select("*") \
            .eq("chat_id", chat_id) \
            .order("timestamp", desc=False) \
            .execute()
        
        return result.data
    
    async def get_message(self, user_id: str, chat_id: str, message_id: str) -> Dict:
        """
        Get a single message.
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            message_id: The message's UUID
            
        Returns:
            Message data
            
        Raises:
            NotFoundError: If message doesn't exist
            ForbiddenError: If user doesn't have access
        """
        # Check chat access
        await check_chat_access(user_id, chat_id, "view")
        
        result = self.client.table("messages") \
            .select("*") \
            .eq("id", message_id) \
            .eq("chat_id", chat_id) \
            .execute()
        
        if not result.data:
            raise NotFoundError("Message not found")
        
        return result.data[0]
    
    async def create_message(
        self,
        user_id: str,
        chat_id: str,
        role: str,
        content: str,
        search_modes: Optional[List[str]] = None
    ) -> Dict:
        """
        Add a message to a chat.
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            role: Message role (user or assistant)
            content: Message content
            search_modes: Optional list of search modes used
            
        Returns:
            Created message record
            
        Raises:
            NotFoundError: If chat doesn't exist
            ForbiddenError: If user doesn't have access
            ValueError: If role is invalid
        """
        # Check chat access
        access = await check_chat_access(user_id, chat_id, "view")
        chat = access["chat"]
        
        # For project chats with non-owner, require edit permission
        if chat.get("project_id") and not access["is_owner"]:
            if access["permission"] == "view":
                raise ForbiddenError("Edit permission required to add messages")
        
        # Validate role
        if role not in self.VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(self.VALID_ROLES)}")
        
        # Validate search modes
        if search_modes:
            search_modes = [mode for mode in search_modes if mode in self.VALID_SEARCH_MODES]
        
        message_data = {
            "chat_id": chat_id,
            "role": role,
            "content": content,
            "search_modes": search_modes or [],
        }
        
        result = self.client.table("messages") \
            .insert(message_data) \
            .execute()
        
        if result.data:
            # Update chat's updated_at timestamp
            self.client.table("chats") \
                .update({"updated_at": datetime.utcnow().isoformat()}) \
                .eq("id", chat_id) \
                .execute()
            
            return result.data[0]
        
        raise Exception("Failed to create message")
    
    async def delete_message(self, user_id: str, chat_id: str, message_id: str) -> bool:
        """
        Delete a message (chat owner only).
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            message_id: The message's UUID
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundError: If message doesn't exist
            ForbiddenError: If user is not the chat owner
        """
        # Check chat ownership
        is_owner = await check_is_chat_owner(user_id, chat_id)
        if not is_owner:
            raise ForbiddenError("Only the chat owner can delete messages")
        
        # Verify message exists
        result = self.client.table("messages") \
            .select("id") \
            .eq("id", message_id) \
            .eq("chat_id", chat_id) \
            .execute()
        
        if not result.data:
            raise NotFoundError("Message not found")
        
        # Delete the message
        self.client.table("messages") \
            .delete() \
            .eq("id", message_id) \
            .execute()
        
        return True
    
    async def bulk_create_messages(
        self,
        user_id: str,
        chat_id: str,
        messages: List[Dict]
    ) -> List[Dict]:
        """
        Add multiple messages to a chat at once.
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            messages: List of message dicts with role, content, search_modes
            
        Returns:
            List of created message records
            
        Raises:
            NotFoundError: If chat doesn't exist
            ForbiddenError: If user doesn't have access
        """
        # Check chat access
        access = await check_chat_access(user_id, chat_id, "view")
        chat = access["chat"]
        
        # For project chats with non-owner, require edit permission
        if chat.get("project_id") and not access["is_owner"]:
            if access["permission"] == "view":
                raise ForbiddenError("Edit permission required to add messages")
        
        # Prepare message data
        messages_data = []
        for msg in messages:
            role = msg.get("role", "user")
            if role not in self.VALID_ROLES:
                continue  # Skip invalid roles
            
            search_modes = msg.get("search_modes", [])
            if search_modes:
                search_modes = [m for m in search_modes if m in self.VALID_SEARCH_MODES]
            
            messages_data.append({
                "chat_id": chat_id,
                "role": role,
                "content": msg.get("content", ""),
                "search_modes": search_modes,
            })
        
        if not messages_data:
            return []
        
        result = self.client.table("messages") \
            .insert(messages_data) \
            .execute()
        
        if result.data:
            # Update chat's updated_at timestamp
            self.client.table("chats") \
                .update({"updated_at": datetime.utcnow().isoformat()}) \
                .eq("id", chat_id) \
                .execute()
            
            return result.data
        
        raise Exception("Failed to create messages")
