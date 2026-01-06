"""
Business logic for user info operations.
"""

import logging
from typing import Optional, Dict
from datetime import datetime
from shared.supabase_client import get_supabase_client
from shared.permissions import NotFoundError

logger = logging.getLogger(__name__)


class UserInfoService:
    """Service class for user info operations."""
    
    def __init__(self):
        self.client = get_supabase_client()
    
    async def get_user_info(self, user_email: str) -> Dict:
        """
        Get user info for the authenticated user.
        Creates a new record if one doesn't exist.
        
        Args:
            user_email: The authenticated user's email
            
        Returns:
            User info with connection status
        """
        result = self.client.table("user_info") \
            .select("*") \
            .eq("email", user_email.lower()) \
            .execute()
        
        if result.data:
            user_info = result.data[0]
        else:
            # Create new user info record
            user_info = await self._create_user_info(user_email)
        
        # Add computed fields
        return self._format_user_info(user_info)
    
    async def update_user_info(self, user_email: str, data: Dict) -> Dict:
        """
        Update user info for the authenticated user.
        Creates a new record if one doesn't exist.
        
        Args:
            user_email: The authenticated user's email
            data: Data to update
            
        Returns:
            Updated user info with connection status
        """
        # Check if record exists
        existing = self.client.table("user_info") \
            .select("email") \
            .eq("email", user_email.lower()) \
            .execute()
        
        update_data = {
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Only update allowed fields
        if "user_company_info" in data:
            update_data["user_company_info"] = data["user_company_info"]
        
        if existing.data:
            # Update existing record
            result = self.client.table("user_info") \
                .update(update_data) \
                .eq("email", user_email.lower()) \
                .execute()
        else:
            # Create new record with the update data
            update_data["email"] = user_email.lower()
            result = self.client.table("user_info") \
                .insert(update_data) \
                .execute()
        
        if result.data:
            return self._format_user_info(result.data[0])
        
        raise Exception("Failed to update user info")
    
    async def connect_gmail(self, user_email: str, gmail_email: str, gmail_token: Dict) -> Dict:
        """
        Connect Gmail account for the user.
        
        Args:
            user_email: The authenticated user's email
            gmail_email: The Gmail email address
            gmail_token: The Gmail OAuth token data
            
        Returns:
            Updated user info
        """
        await self._ensure_user_info_exists(user_email)
        
        result = self.client.table("user_info") \
            .update({
                "gmail_email": gmail_email,
                "gmail_token": gmail_token,
                "updated_at": datetime.utcnow().isoformat()
            }) \
            .eq("email", user_email.lower()) \
            .execute()
        
        if result.data:
            return self._format_user_info(result.data[0])
        
        raise Exception("Failed to connect Gmail")
    
    async def disconnect_gmail(self, user_email: str) -> Dict:
        """
        Disconnect Gmail account for the user.
        
        Args:
            user_email: The authenticated user's email
            
        Returns:
            Updated user info
        """
        await self._ensure_user_info_exists(user_email)
        
        result = self.client.table("user_info") \
            .update({
                "gmail_email": None,
                "gmail_token": None,
                "updated_at": datetime.utcnow().isoformat()
            }) \
            .eq("email", user_email.lower()) \
            .execute()
        
        if result.data:
            return self._format_user_info(result.data[0])
        
        raise Exception("Failed to disconnect Gmail")
    
    async def connect_outlook(self, user_email: str, outlook_email: str, outlook_token: Dict) -> Dict:
        """
        Connect Outlook account for the user.
        
        Args:
            user_email: The authenticated user's email
            outlook_email: The Outlook email address
            outlook_token: The Outlook OAuth token data
            
        Returns:
            Updated user info
        """
        await self._ensure_user_info_exists(user_email)
        
        result = self.client.table("user_info") \
            .update({
                "outlook_email": outlook_email,
                "outlook_token": outlook_token,
                "updated_at": datetime.utcnow().isoformat()
            }) \
            .eq("email", user_email.lower()) \
            .execute()
        
        if result.data:
            return self._format_user_info(result.data[0])
        
        raise Exception("Failed to connect Outlook")
    
    async def disconnect_outlook(self, user_email: str) -> Dict:
        """
        Disconnect Outlook account for the user.
        
        Args:
            user_email: The authenticated user's email
            
        Returns:
            Updated user info
        """
        await self._ensure_user_info_exists(user_email)
        
        result = self.client.table("user_info") \
            .update({
                "outlook_email": None,
                "outlook_token": None,
                "updated_at": datetime.utcnow().isoformat()
            }) \
            .eq("email", user_email.lower()) \
            .execute()
        
        if result.data:
            return self._format_user_info(result.data[0])
        
        raise Exception("Failed to disconnect Outlook")
    
    async def _create_user_info(self, user_email: str) -> Dict:
        """Create a new user info record."""
        user_info_data = {
            "email": user_email.lower(),
        }
        
        result = self.client.table("user_info") \
            .insert(user_info_data) \
            .execute()
        
        if result.data:
            return result.data[0]
        
        raise Exception("Failed to create user info")
    
    async def _ensure_user_info_exists(self, user_email: str) -> None:
        """Ensure a user info record exists for the user."""
        existing = self.client.table("user_info") \
            .select("email") \
            .eq("email", user_email.lower()) \
            .execute()
        
        if not existing.data:
            await self._create_user_info(user_email)
    
    def _format_user_info(self, user_info: Dict) -> Dict:
        """Format user info with computed connection status fields."""
        # Don't expose tokens to the client
        formatted = {
            "email": user_info.get("email"),
            "user_company_info": user_info.get("user_company_info"),
            "gmail_email": user_info.get("gmail_email"),
            "gmail_connected": bool(user_info.get("gmail_token")),
            "outlook_email": user_info.get("outlook_email"),
            "outlook_connected": bool(user_info.get("outlook_token")),
            "created_at": user_info.get("created_at"),
            "updated_at": user_info.get("updated_at"),
        }
        
        return formatted
