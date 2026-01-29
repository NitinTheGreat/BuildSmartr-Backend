"""
Business logic for chat operations.

Includes conversation memory support:
- Chat context loading (summary + recent messages)
- Summary generation and updates
- Intelligent re-summarization triggers
"""

import logging
import os
import httpx
from typing import Optional, List, Dict
from datetime import datetime
from shared.supabase_client import get_supabase_client
from shared.permissions import (
    check_project_access, check_chat_access,
    NotFoundError, ForbiddenError
)

logger = logging.getLogger(__name__)

# AI Backend URL for summary generation
AI_BACKEND_URL = os.environ.get("AI_BACKEND_URL", "http://localhost:7071")

# Conversation memory settings
RECENT_MESSAGES_LIMIT = 10  # Number of recent messages to include in context
SUMMARY_MESSAGE_INTERVAL = 8  # Regenerate summary every N messages
SUMMARY_TOKEN_THRESHOLD = 2000  # Or when estimated tokens exceed this
BOOT_SUMMARY_THRESHOLD = 4  # Generate first summary at N messages


class ChatService:
    """Service class for chat CRUD operations."""
    
    VALID_CHAT_TYPES = ["project", "general"]
    
    def __init__(self):
        self.client = get_supabase_client()
    
    def _add_message_count(self, chat: Dict) -> Dict:
        """
        Add message_count to a chat object.
        
        Args:
            chat: Chat record
            
        Returns:
            Chat record with message_count added
        """
        chat_id = chat.get("id")
        
        # Count messages for this chat
        result = self.client.table("messages") \
            .select("id", count="exact") \
            .eq("chat_id", chat_id) \
            .execute()
        
        chat["message_count"] = result.count if result.count is not None else 0
        return chat
    
    def _add_message_counts(self, chats: List[Dict]) -> List[Dict]:
        """
        Add message_count to multiple chat objects efficiently.
        
        Args:
            chats: List of chat records
            
        Returns:
            List of chat records with message_count added
        """
        if not chats:
            return chats
        
        # Get all chat IDs
        chat_ids = [chat["id"] for chat in chats]
        
        # Query message counts for all chats at once
        message_counts = {}
        for chat_id in chat_ids:
            result = self.client.table("messages") \
                .select("id", count="exact") \
                .eq("chat_id", chat_id) \
                .execute()
            message_counts[chat_id] = result.count if result.count is not None else 0
        
        # Add message_count to each chat
        for chat in chats:
            chat["message_count"] = message_counts.get(chat["id"], 0)
        
        return chats
    
    async def list_general_chats(self, user_id: str) -> List[Dict]:
        """
        List all general chats owned by the user.
        
        Args:
            user_id: The authenticated user's ID
            
        Returns:
            List of general chat records with message_count
        """
        result = self.client.table("chats") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("chat_type", "general") \
            .order("updated_at", desc=True) \
            .execute()
        
        chats = self._add_message_counts(result.data)
        return chats
    
    async def list_project_chats(self, user_id: str, project_id: str) -> List[Dict]:
        """
        List all chats for a project.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            
        Returns:
            List of project chat records with message_count
            
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
        
        chats = self._add_message_counts(result.data)
        return chats
    
    async def get_chat(self, user_id: str, chat_id: str, include_messages: bool = True) -> Dict:
        """
        Get a single chat with optional messages and message_count.
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            include_messages: Whether to include messages
            
        Returns:
            Chat data with optional messages and message_count
            
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
            chat["message_count"] = len(messages_result.data)
        else:
            # Still add message_count even if not including messages
            chat = self._add_message_count(chat)
        
        return chat
    
    async def create_general_chat(self, user_id: str, title: Optional[str] = None) -> Dict:
        """
        Create a new general chat.
        
        Args:
            user_id: The authenticated user's ID
            title: Optional chat title
            
        Returns:
            Created chat record with message_count
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
            chat["message_count"] = 0
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
            Created chat record with message_count
            
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
            chat["message_count"] = 0
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
            Updated chat record with message_count
            
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
            chat = self._add_message_count(chat)
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
    
    # ================================================================
    # CONVERSATION MEMORY METHODS
    # ================================================================
    
    async def get_chat_context(self, user_id: str, chat_id: str) -> Dict:
        """
        Get conversation context for a chat (summary + recent messages).
        
        This is used by the AI backend to understand follow-up questions.
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            
        Returns:
            Dict with:
            - chat_id: Chat UUID
            - project_id: Project UUID (for project chats)
            - ai_project_id: Pinecone namespace
            - project_name: Human-readable project name
            - summary: Conversation summary (may be None)
            - recent_messages: Last N messages
            - message_count: Total message count
            - should_resummarize: Whether summary needs update
        """
        # Check access
        access = await check_chat_access(user_id, chat_id, "view")
        chat = access["chat"]
        
        # Get recent messages
        messages_result = self.client.table("messages") \
            .select("role, content") \
            .eq("chat_id", chat_id) \
            .order("timestamp", desc=False) \
            .execute()
        
        all_messages = messages_result.data or []
        message_count = len(all_messages)
        recent_messages = all_messages[-RECENT_MESSAGES_LIMIT:]
        
        # Get project info if this is a project chat
        project_id = chat.get("project_id")
        ai_project_id = None
        project_name = None
        
        if project_id:
            project_result = self.client.table("projects") \
                .select("ai_project_id, name") \
                .eq("id", project_id) \
                .single() \
                .execute()
            
            if project_result.data:
                ai_project_id = project_result.data.get("ai_project_id")
                project_name = project_result.data.get("name")
        
        # Determine if we should regenerate summary
        summary = chat.get("summary")
        message_count_at_summary = chat.get("message_count_at_summary") or 0
        should_resummarize = self._should_resummarize(
            message_count=message_count,
            message_count_at_summary=message_count_at_summary,
            summary=summary,
            recent_messages=recent_messages
        )
        
        return {
            "chat_id": chat_id,
            "project_id": project_id,
            "ai_project_id": ai_project_id,
            "project_name": project_name,
            "summary": summary,
            "recent_messages": recent_messages,
            "message_count": message_count,
            "should_resummarize": should_resummarize
        }
    
    def _should_resummarize(
        self,
        message_count: int,
        message_count_at_summary: int,
        summary: Optional[str],
        recent_messages: List[Dict]
    ) -> bool:
        """
        Determine if we should regenerate the summary.
        
        Triggers:
        1. No summary exists and we have 4+ messages (boot summary)
        2. 8+ messages since last summary
        3. Token count exceeds threshold
        """
        # Boot summary at message 4
        if not summary and message_count >= BOOT_SUMMARY_THRESHOLD:
            logger.info(f"Should resummarize: boot summary (messages={message_count})")
            return True
        
        # Regular interval check
        messages_since_summary = message_count - message_count_at_summary
        if messages_since_summary >= SUMMARY_MESSAGE_INTERVAL:
            logger.info(f"Should resummarize: interval ({messages_since_summary} since last)")
            return True
        
        # Token threshold check (rough: 4 chars per token)
        if summary and recent_messages:
            summary_tokens = len(summary) // 4
            messages_tokens = sum(len(m.get("content", "")) // 4 for m in recent_messages)
            total_tokens = summary_tokens + messages_tokens
            
            if total_tokens > SUMMARY_TOKEN_THRESHOLD:
                logger.info(f"Should resummarize: token threshold (~{total_tokens} tokens)")
                return True
        
        return False
    
    async def update_chat_summary(
        self,
        user_id: str,
        chat_id: str,
        force: bool = False
    ) -> Optional[Dict]:
        """
        Generate or update the conversation summary for a chat.
        
        Calls the AI Backend to generate the summary, then stores it.
        
        Args:
            user_id: The authenticated user's ID
            chat_id: The chat's UUID
            force: Force regeneration even if not needed
            
        Returns:
            Dict with summary info, or None if no update needed
        """
        # Check access
        access = await check_chat_access(user_id, chat_id, "view")
        chat = access["chat"]
        
        # Get all messages
        messages_result = self.client.table("messages") \
            .select("role, content") \
            .eq("chat_id", chat_id) \
            .order("timestamp", desc=False) \
            .execute()
        
        messages = messages_result.data or []
        message_count = len(messages)
        
        # Check if we should summarize
        summary = chat.get("summary")
        message_count_at_summary = chat.get("message_count_at_summary") or 0
        
        should_update = force or self._should_resummarize(
            message_count=message_count,
            message_count_at_summary=message_count_at_summary,
            summary=summary,
            recent_messages=messages[-RECENT_MESSAGES_LIMIT:]
        )
        
        if not should_update:
            logger.info(f"Summary update not needed for chat {chat_id}")
            return None
        
        # Get project name for context
        project_name = ""
        if chat.get("project_id"):
            project_result = self.client.table("projects") \
                .select("name") \
                .eq("id", chat.get("project_id")) \
                .single() \
                .execute()
            if project_result.data:
                project_name = project_result.data.get("name", "")
        
        # Call AI Backend to generate summary
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{AI_BACKEND_URL}/api/summarize_chat",
                    json={
                        "messages": messages,
                        "existing_summary": summary,
                        "project_name": project_name
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Summary generation failed: {response.text}")
                    return None
                
                result = response.json()
                new_summary = result.get("summary")
                
        except Exception as e:
            logger.error(f"Failed to call AI Backend for summary: {e}")
            return None
        
        # Store the new summary
        update_data = {
            "summary": new_summary,
            "summary_updated_at": datetime.utcnow().isoformat(),
            "message_count_at_summary": message_count,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        self.client.table("chats") \
            .update(update_data) \
            .eq("id", chat_id) \
            .execute()
        
        logger.info(f"Updated summary for chat {chat_id}: {result.get('word_count')} words")
        
        return {
            "summary": new_summary,
            "word_count": result.get("word_count"),
            "entities_preserved": result.get("entities_preserved"),
            "message_count": message_count
        }