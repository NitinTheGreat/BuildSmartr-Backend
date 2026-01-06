"""
Business logic for project file operations.
"""

import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from shared.supabase_client import get_supabase_client, get_storage_bucket
from shared.permissions import check_project_access, NotFoundError, ForbiddenError

logger = logging.getLogger(__name__)


class ProjectFileService:
    """Service class for project file CRUD operations."""
    
    VALID_CATEGORIES = ["construction", "architectural", "other"]
    
    def __init__(self):
        self.client = get_supabase_client()
        self.storage_bucket = get_storage_bucket()
    
    async def list_files(self, user_id: str, project_id: str) -> List[Dict]:
        """
        List all files in a project with signed URLs.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            
        Returns:
            List of file metadata with signed URLs
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user doesn't have access
        """
        # Check access (view permission is sufficient)
        await check_project_access(user_id, project_id, "view")
        
        result = self.client.table("project_files") \
            .select("*") \
            .eq("project_id", project_id) \
            .order("created_at", desc=True) \
            .execute()
        
        # Generate signed URLs for each file
        files = result.data
        for file_record in files:
            file_record["url"] = await self._get_signed_url_for_file(file_record)
        
        return files
    
    async def _get_signed_url_for_file(self, file_record: Dict, expires_in: int = 3600) -> Optional[str]:
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
    
    async def get_file(self, user_id: str, project_id: str, file_id: str) -> Dict:
        """
        Get a single file's metadata with signed URL.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            file_id: The file's UUID
            
        Returns:
            File metadata with signed URL
            
        Raises:
            NotFoundError: If file doesn't exist
            ForbiddenError: If user doesn't have access
        """
        # Check project access
        await check_project_access(user_id, project_id, "view")
        
        result = self.client.table("project_files") \
            .select("*") \
            .eq("id", file_id) \
            .eq("project_id", project_id) \
            .execute()
        
        if not result.data:
            raise NotFoundError("File not found")
        
        file_record = result.data[0]
        file_record["url"] = await self._get_signed_url_for_file(file_record)
        return file_record
    
    async def upload_file(
        self,
        user_id: str,
        project_id: str,
        file_name: str,
        file_data: bytes,
        content_type: str,
        category: str = "other"
    ) -> Dict:
        """
        Upload a file to a project.
        Automatically deletes any existing files in the same category before uploading.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            file_name: Original file name
            file_data: File content as bytes
            content_type: MIME type
            category: File category (construction, architectural, other)
            
        Returns:
            Created file metadata
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user doesn't have edit access
        """
        # Check edit access
        access = await check_project_access(user_id, project_id, "edit")
        
        # Validate category
        if category not in self.VALID_CATEGORIES:
            category = "other"
        
        # Delete existing files in the same category before uploading
        await self._delete_files_in_category(project_id, category, access['project']['user_id'])
        
        # Generate storage path
        storage_path = f"{access['project']['user_id']}/{project_id}/{file_name}"
        
        # Upload to storage
        try:
            self.client.storage.from_(self.storage_bucket).upload(
                storage_path,
                file_data,
                {"content-type": content_type}
            )
        except Exception as e:
            # If file exists, try to update it
            if "already exists" in str(e).lower():
                self.client.storage.from_(self.storage_bucket).update(
                    storage_path,
                    file_data,
                    {"content-type": content_type}
                )
            else:
                raise
        
        # Get signed URL
        signed_url_result = self.client.storage.from_(self.storage_bucket).create_signed_url(
            storage_path, 3600  # 1 hour
        )
        signed_url = signed_url_result.get("signedURL", "")
        
        # Store metadata in database
        file_metadata = {
            "project_id": project_id,
            "name": file_name,
            "size": len(file_data),
            "type": content_type,
            "category": category,
            "url": storage_path,  # Store path, not signed URL
        }
        
        result = self.client.table("project_files") \
            .insert(file_metadata) \
            .execute()
        
        if result.data:
            file_record = result.data[0]
            file_record["url"] = signed_url  # Return signed URL to client
            return file_record
        
        raise Exception("Failed to store file metadata")
    
    async def _delete_files_in_category(self, project_id: str, category: str, owner_id: str) -> None:
        """
        Delete all existing files in a category for a project.
        
        Args:
            project_id: The project's UUID
            category: The file category to clear
            owner_id: The project owner's user ID (for storage path)
        """
        # Get all files in this category
        existing_files = self.client.table("project_files") \
            .select("*") \
            .eq("project_id", project_id) \
            .eq("category", category) \
            .execute()
        
        if not existing_files.data:
            return
        
        logger.info(f"Deleting {len(existing_files.data)} existing file(s) in category '{category}' for project {project_id}")
        
        for file_record in existing_files.data:
            storage_path = file_record.get("url", "")
            file_id = file_record.get("id")
            
            # Delete from storage
            if storage_path and not storage_path.startswith("http"):
                try:
                    self.client.storage.from_(self.storage_bucket).remove([storage_path])
                    logger.debug(f"Deleted file from storage: {storage_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete file from storage: {str(e)}")
            
            # Delete from database
            try:
                self.client.table("project_files") \
                    .delete() \
                    .eq("id", file_id) \
                    .execute()
                logger.debug(f"Deleted file record: {file_id}")
            except Exception as e:
                logger.warning(f"Failed to delete file record: {str(e)}")
    
    async def delete_file(self, user_id: str, project_id: str, file_id: str) -> bool:
        """
        Delete a file from a project.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            file_id: The file's UUID
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundError: If file doesn't exist
            ForbiddenError: If user doesn't have edit access
        """
        # Check edit access
        await check_project_access(user_id, project_id, "edit")
        
        # Get file metadata
        result = self.client.table("project_files") \
            .select("*") \
            .eq("id", file_id) \
            .eq("project_id", project_id) \
            .execute()
        
        if not result.data:
            raise NotFoundError("File not found")
        
        file_record = result.data[0]
        storage_path = file_record.get("url", "")
        
        # Delete from storage
        if storage_path and not storage_path.startswith("http"):
            try:
                self.client.storage.from_(self.storage_bucket).remove([storage_path])
            except Exception as e:
                logger.warning(f"Failed to delete file from storage: {str(e)}")
        
        # Delete metadata from database
        self.client.table("project_files") \
            .delete() \
            .eq("id", file_id) \
            .execute()
        
        return True
    
    async def get_download_url(self, user_id: str, project_id: str, file_id: str, expires_in: int = 3600) -> str:
        """
        Get a signed download URL for a file.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            file_id: The file's UUID
            expires_in: URL validity in seconds (default: 1 hour)
            
        Returns:
            Signed download URL
            
        Raises:
            NotFoundError: If file doesn't exist
            ForbiddenError: If user doesn't have access
        """
        # Check view access
        await check_project_access(user_id, project_id, "view")
        
        # Get file metadata
        result = self.client.table("project_files") \
            .select("*") \
            .eq("id", file_id) \
            .eq("project_id", project_id) \
            .execute()
        
        if not result.data:
            raise NotFoundError("File not found")
        
        file_record = result.data[0]
        storage_path = file_record.get("url", "")
        
        if not storage_path:
            raise NotFoundError("File storage path not found")
        
        # If it's already a signed URL, return it (though it may be expired)
        if storage_path.startswith("http"):
            storage_path = self._extract_path_from_url(storage_path, file_record)
        
        # Generate new signed URL
        signed_url_result = self.client.storage.from_(self.storage_bucket).create_signed_url(
            storage_path, expires_in
        )
        
        return signed_url_result.get("signedURL", "")
    
    def _extract_path_from_url(self, url: str, file_record: Dict) -> str:
        """Extract storage path from a signed URL or reconstruct from file record."""
        # Try to reconstruct the path from file metadata
        project_id = file_record.get("project_id")
        file_name = file_record.get("name")
        
        # We need to get the project to find the user_id
        project_result = self.client.table("projects") \
            .select("user_id") \
            .eq("id", project_id) \
            .execute()
        
        if project_result.data:
            owner_id = project_result.data[0]["user_id"]
            return f"{owner_id}/{project_id}/{file_name}"
        
        raise NotFoundError("Could not determine file storage path")
