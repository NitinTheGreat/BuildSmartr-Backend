"""
Business logic for project operations.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from shared.supabase_client import get_supabase_client, get_storage_bucket
from shared.permissions import check_project_access, get_user_email, NotFoundError, ForbiddenError

logger = logging.getLogger(__name__)


class ProjectService:
    """Service class for project CRUD operations."""
    
    def __init__(self):
        self.client = get_supabase_client()
        self.storage_bucket = get_storage_bucket()
    
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
            
            # Generate signed URLs for each file
            files_with_urls = []
            for file_record in files_result.data:
                file_record["url"] = self._get_signed_url_for_file(file_record)
                files_with_urls.append(file_record)
            project["files"] = files_with_urls
            
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
    
    def _get_signed_url_for_file(self, file_record: Dict, expires_in: int = 3600) -> Optional[str]:
        """
        Generate a signed URL for a file record.
        
        Args:
            file_record: The file metadata from database
            expires_in: URL validity in seconds (default: 1 hour)
            
        Returns:
            Signed URL or None if unable to generate
        """
        storage_path = file_record.get("url", "")
        
        if not storage_path:
            return None
        
        # If it's already a signed URL, reconstruct the path
        if storage_path.startswith("http"):
            storage_path = self._extract_path_from_url(storage_path, file_record)
        
        try:
            signed_url_result = self.client.storage.from_(self.storage_bucket).create_signed_url(
                storage_path, expires_in
            )
            return signed_url_result.get("signedURL", None)
        except Exception as e:
            logger.warning(f"Failed to generate signed URL for {storage_path}: {str(e)}")
            return None
    
    def _extract_path_from_url(self, url: str, file_record: Dict) -> str:
        """Extract storage path from a signed URL or reconstruct from file record."""
        project_id = file_record.get("project_id")
        file_name = file_record.get("name")
        
        # Get the project to find the user_id
        project_result = self.client.table("projects") \
            .select("user_id") \
            .eq("id", project_id) \
            .execute()
        
        if project_result.data:
            owner_id = project_result.data[0]["user_id"]
            return f"{owner_id}/{project_id}/{file_name}"
        
        raise NotFoundError("Could not determine file storage path")
    
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
