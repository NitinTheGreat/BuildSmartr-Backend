"""
Supabase client singleton for database and storage operations.
"""

import os
import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Singleton instances
_supabase_client: Optional[Client] = None
_supabase_admin_client: Optional[Client] = None


def get_supabase_url() -> str:
    """Get the Supabase URL from environment variables."""
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise ValueError("SUPABASE_URL environment variable not set")
    return url


def get_supabase_service_key() -> str:
    """Get the Supabase service key from environment variables."""
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not key:
        raise ValueError("SUPABASE_SERVICE_KEY environment variable not set")
    return key


def get_storage_bucket() -> str:
    """Get the Supabase storage bucket name from environment variables."""
    return os.environ.get("SUPABASE_STORAGE_BUCKET", "project-files")


def get_supabase_client() -> Client:
    """
    Get the Supabase client singleton.
    Uses service role key for full database access.
    
    Returns:
        Supabase Client instance
    """
    global _supabase_client
    
    if _supabase_client is None:
        url = get_supabase_url()
        key = get_supabase_service_key()
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized")
    
    return _supabase_client


def get_supabase_admin_client() -> Client:
    """
    Get the Supabase admin client singleton.
    Alias for get_supabase_client() using service role.
    
    Returns:
        Supabase Client instance with admin privileges
    """
    global _supabase_admin_client
    
    if _supabase_admin_client is None:
        url = get_supabase_url()
        key = get_supabase_service_key()
        _supabase_admin_client = create_client(url, key)
        logger.info("Supabase admin client initialized")
    
    return _supabase_admin_client


class SupabaseService:
    """
    Base service class for Supabase operations.
    Provides common database and storage utilities.
    """
    
    def __init__(self):
        self.client = get_supabase_client()
        self.storage_bucket = get_storage_bucket()
    
    @property
    def storage(self):
        """Get the storage client."""
        return self.client.storage
    
    def table(self, table_name: str):
        """Get a table reference for queries."""
        return self.client.table(table_name)
    
    async def upload_file(self, path: str, file_data: bytes, content_type: str) -> str:
        """
        Upload a file to Supabase Storage.
        
        Args:
            path: Storage path (e.g., "user_id/project_id/filename")
            file_data: File content as bytes
            content_type: MIME type of the file
            
        Returns:
            Public URL of the uploaded file
        """
        try:
            self.storage.from_(self.storage_bucket).upload(
                path,
                file_data,
                {"content-type": content_type}
            )
            
            # Get signed URL (valid for 1 hour)
            signed_url = self.storage.from_(self.storage_bucket).create_signed_url(
                path, 3600
            )
            return signed_url.get("signedURL", "")
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise
    
    async def delete_file(self, path: str) -> bool:
        """
        Delete a file from Supabase Storage.
        
        Args:
            path: Storage path of the file to delete
            
        Returns:
            True if successful
        """
        try:
            self.storage.from_(self.storage_bucket).remove([path])
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            raise
    
    async def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """
        Get a signed URL for a file in storage.
        
        Args:
            path: Storage path of the file
            expires_in: URL validity in seconds (default: 1 hour)
            
        Returns:
            Signed URL for the file
        """
        try:
            result = self.storage.from_(self.storage_bucket).create_signed_url(
                path, expires_in
            )
            return result.get("signedURL", "")
        except Exception as e:
            logger.error(f"Error getting signed URL: {str(e)}")
            raise
