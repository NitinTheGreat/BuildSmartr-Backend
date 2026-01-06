"""
Business logic for project sharing operations.
"""

import logging
from typing import List, Dict
from shared.supabase_client import get_supabase_client
from shared.permissions import check_project_access, NotFoundError, ForbiddenError

logger = logging.getLogger(__name__)


class ProjectShareService:
    """Service class for project sharing operations."""
    
    VALID_PERMISSIONS = ["view", "edit"]
    
    def __init__(self):
        self.client = get_supabase_client()
    
    async def list_shares(self, user_id: str, project_id: str) -> List[Dict]:
        """
        List all users a project is shared with (owner only).
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            
        Returns:
            List of share records
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user is not the owner
        """
        # Check ownership
        access = await check_project_access(user_id, project_id)
        if not access["is_owner"]:
            raise ForbiddenError("Only the project owner can view shares")
        
        result = self.client.table("project_shares") \
            .select("*") \
            .eq("project_id", project_id) \
            .order("created_at", desc=True) \
            .execute()
        
        return result.data
    
    async def add_share(
        self,
        user_id: str,
        project_id: str,
        email: str,
        permission: str = "view"
    ) -> Dict:
        """
        Share a project with a user (owner only).
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            email: Email of the user to share with
            permission: Permission level (view or edit)
            
        Returns:
            Created share record
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user is not the owner
            ValueError: If email is invalid or already shared
        """
        # Check ownership
        access = await check_project_access(user_id, project_id)
        if not access["is_owner"]:
            raise ForbiddenError("Only the project owner can share the project")
        
        # Validate permission
        if permission not in self.VALID_PERMISSIONS:
            permission = "view"
        
        # Validate email
        if not email or "@" not in email:
            raise ValueError("Invalid email address")
        
        # Check if already shared
        existing = self.client.table("project_shares") \
            .select("id") \
            .eq("project_id", project_id) \
            .eq("shared_with_email", email.lower()) \
            .execute()
        
        if existing.data:
            raise ValueError("Project is already shared with this email")
        
        # Create share record
        share_data = {
            "project_id": project_id,
            "shared_with_email": email.lower(),
            "shared_by_user_id": user_id,
            "permission": permission,
        }
        
        result = self.client.table("project_shares") \
            .insert(share_data) \
            .execute()
        
        if result.data:
            return result.data[0]
        
        raise Exception("Failed to create share")
    
    async def update_share(
        self,
        user_id: str,
        project_id: str,
        share_id: str,
        permission: str
    ) -> Dict:
        """
        Update a share's permission (owner only).
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            share_id: The share record's UUID
            permission: New permission level (view or edit)
            
        Returns:
            Updated share record
            
        Raises:
            NotFoundError: If share doesn't exist
            ForbiddenError: If user is not the owner
        """
        # Check ownership
        access = await check_project_access(user_id, project_id)
        if not access["is_owner"]:
            raise ForbiddenError("Only the project owner can update shares")
        
        # Validate permission
        if permission not in self.VALID_PERMISSIONS:
            raise ValueError(f"Permission must be one of: {', '.join(self.VALID_PERMISSIONS)}")
        
        # Verify share exists for this project
        existing = self.client.table("project_shares") \
            .select("*") \
            .eq("id", share_id) \
            .eq("project_id", project_id) \
            .execute()
        
        if not existing.data:
            raise NotFoundError("Share not found")
        
        # Update the share
        result = self.client.table("project_shares") \
            .update({"permission": permission}) \
            .eq("id", share_id) \
            .execute()
        
        if result.data:
            return result.data[0]
        
        raise Exception("Failed to update share")
    
    async def delete_share(self, user_id: str, project_id: str, share_id: str) -> bool:
        """
        Remove a share (owner only).
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            share_id: The share record's UUID
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundError: If share doesn't exist
            ForbiddenError: If user is not the owner
        """
        # Check ownership
        access = await check_project_access(user_id, project_id)
        if not access["is_owner"]:
            raise ForbiddenError("Only the project owner can remove shares")
        
        # Verify share exists for this project
        existing = self.client.table("project_shares") \
            .select("id") \
            .eq("id", share_id) \
            .eq("project_id", project_id) \
            .execute()
        
        if not existing.data:
            raise NotFoundError("Share not found")
        
        # Delete the share
        self.client.table("project_shares") \
            .delete() \
            .eq("id", share_id) \
            .execute()
        
        return True
