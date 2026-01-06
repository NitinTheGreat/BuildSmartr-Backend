"""
Business logic for project operations.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from shared.supabase_client import get_supabase_client
from shared.permissions import check_project_access, get_user_email, NotFoundError, ForbiddenError

logger = logging.getLogger(__name__)


class ProjectService:
    """Service class for project CRUD operations."""
    
    def __init__(self):
        self.client = get_supabase_client()
    
    async def list_projects(self, user_id: str) -> List[Dict]:
        """
        List all projects the user has access to (owned + shared).
        
        Args:
            user_id: The authenticated user's ID
            
        Returns:
            List of projects with access information
        """
        # 1. Get projects owned by user
        owned_result = self.client.table("projects") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("updated_at", desc=True) \
            .execute()
        
        owned_projects = []
        for project in owned_result.data:
            project["is_owner"] = True
            project["permission"] = "owner"
            owned_projects.append(project)
        
        # 2. Get projects shared with user
        user_email = await get_user_email(user_id)
        shared_projects = []
        
        if user_email:
            shares_result = self.client.table("project_shares") \
                .select("project_id, permission") \
                .eq("shared_with_email", user_email) \
                .execute()
            
            if shares_result.data:
                project_ids = [s["project_id"] for s in shares_result.data]
                permission_map = {s["project_id"]: s["permission"] for s in shares_result.data}
                
                shared_result = self.client.table("projects") \
                    .select("*") \
                    .in_("id", project_ids) \
                    .order("updated_at", desc=True) \
                    .execute()
                
                for project in shared_result.data:
                    project["is_owner"] = False
                    project["permission"] = permission_map.get(project["id"], "view")
                    shared_projects.append(project)
        
        # 3. Combine and return
        all_projects = owned_projects + shared_projects
        return all_projects
    
    async def get_project(self, user_id: str, project_id: str, include_related: bool = True) -> Dict:
        """
        Get a single project with optional related data.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            include_related: Whether to include files, chats, and shares
            
        Returns:
            Project data with access information and optional related data
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user doesn't have access
        """
        # Check access and get project
        access = await check_project_access(user_id, project_id)
        project = access["project"]
        project["is_owner"] = access["is_owner"]
        project["permission"] = access["permission"]
        
        if include_related:
            # Get files
            files_result = self.client.table("project_files") \
                .select("*") \
                .eq("project_id", project_id) \
                .order("created_at", desc=True) \
                .execute()
            project["files"] = files_result.data
            
            # Get chats
            chats_result = self.client.table("chats") \
                .select("*") \
                .eq("project_id", project_id) \
                .order("updated_at", desc=True) \
                .execute()
            project["chats"] = chats_result.data
            
            # Get shares (owner only)
            if access["is_owner"]:
                shares_result = self.client.table("project_shares") \
                    .select("*") \
                    .eq("project_id", project_id) \
                    .execute()
                project["shares"] = shares_result.data
            else:
                project["shares"] = []
        
        return project
    
    async def create_project(self, user_id: str, data: Dict) -> Dict:
        """
        Create a new project.
        
        Args:
            user_id: The authenticated user's ID
            data: Project data (name, description, company_address, tags)
            
        Returns:
            Created project data
        """
        project_data = {
            "user_id": user_id,
            "name": data.get("name"),
            "description": data.get("description"),
            "company_address": data.get("company_address"),
            "tags": data.get("tags", []),
        }
        
        result = self.client.table("projects") \
            .insert(project_data) \
            .execute()
        
        if result.data:
            project = result.data[0]
            project["is_owner"] = True
            project["permission"] = "owner"
            return project
        
        raise Exception("Failed to create project")
    
    async def update_project(self, user_id: str, project_id: str, data: Dict) -> Dict:
        """
        Update an existing project (owner only).
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            data: Updated project data
            
        Returns:
            Updated project data
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user is not the owner
        """
        # Check ownership
        access = await check_project_access(user_id, project_id)
        if not access["is_owner"]:
            raise ForbiddenError("Only the project owner can update the project")
        
        update_data = {
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if "name" in data:
            update_data["name"] = data["name"]
        if "description" in data:
            update_data["description"] = data["description"]
        if "company_address" in data:
            update_data["company_address"] = data["company_address"]
        if "tags" in data:
            update_data["tags"] = data["tags"]
        
        result = self.client.table("projects") \
            .update(update_data) \
            .eq("id", project_id) \
            .execute()
        
        if result.data:
            project = result.data[0]
            project["is_owner"] = True
            project["permission"] = "owner"
            return project
        
        raise Exception("Failed to update project")
    
    async def delete_project(self, user_id: str, project_id: str) -> bool:
        """
        Delete a project (owner only).
        All related data (files, chats, messages, shares) will be deleted via CASCADE.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user is not the owner
        """
        # Check ownership
        access = await check_project_access(user_id, project_id)
        if not access["is_owner"]:
            raise ForbiddenError("Only the project owner can delete the project")
        
        # Delete the project (CASCADE will handle related records)
        self.client.table("projects") \
            .delete() \
            .eq("id", project_id) \
            .execute()
        
        return True
