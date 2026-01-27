"""
Business logic for project operations.
"""

import logging
import asyncio
import re
import hashlib
from typing import Optional, List, Dict, Any, AsyncGenerator
from datetime import datetime
from shared.supabase_client import get_supabase_client, get_storage_bucket
from shared.permissions import check_project_access, get_user_email, NotFoundError, ForbiddenError
from shared.ai_client import get_ai_client

logger = logging.getLogger(__name__)


def generate_ai_project_id(project_name: str, user_email: str) -> str:
    """
    Generate a unique AI project ID.
    
    This MUST match the algorithm in IIVY-AI-Backend/project_indexer.py
    Format: {normalized_name}_{user_hash}
    Example: "my_project_a1b2c3d4" for user@example.com project "My Project"
    
    Args:
        project_name: Human-readable project name
        user_email: User's email address for isolation
        
    Returns:
        Unique project ID safe for use as Pinecone namespace
    """
    # Normalize project name (lowercase, replace non-alphanumeric with underscore)
    normalized_name = re.sub(r'[^a-z0-9]+', '_', project_name.lower()).strip('_')
    
    # Create 8-character hash from user email for uniqueness
    email_hash = hashlib.sha256(user_email.lower().strip().encode()).hexdigest()[:8]
    
    return f"{normalized_name}_{email_hash}"


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
            
            # Get chats (with message counts)
            chats_result = self.client.table("chats") \
                .select("*") \
                .eq("project_id", project_id) \
                .order("updated_at", desc=True) \
                .execute()
            
            # Add message counts to chats
            from chats.service import ChatService
            chat_service = ChatService()
            chats_with_counts = chat_service._add_message_counts(chats_result.data)
            project["chats"] = chats_with_counts
            
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
        
        This method:
        1. Calls AI backend to delete vectors from Pinecone
        2. Deletes from Supabase (CASCADE handles related records)
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user is not the owner
        """
        # Check ownership and get project
        access = await check_project_access(user_id, project_id)
        if not access["is_owner"]:
            raise ForbiddenError("Only the project owner can delete the project")
        
        project = access["project"]
        ai_project_id = project.get("ai_project_id")
        
        # Step 1: Delete from AI backend (Pinecone) if indexed
        if ai_project_id:
            try:
                user_email = await get_user_email(user_id)
                ai_client = get_ai_client()
                await ai_client.delete_project(ai_project_id, user_email)
                logger.info(f"Deleted AI project: {ai_project_id}")
            except Exception as e:
                # Log but don't fail - still delete from Supabase
                logger.warning(f"Failed to delete from AI backend: {str(e)}")
        
        # Step 2: Delete from Supabase (CASCADE will handle related records)
        self.client.table("projects") \
            .delete() \
            .eq("id", project_id) \
            .execute()
        
        return True
    
    # =========================================================================
    # AI Integration Methods
    # =========================================================================
    
    async def _get_gmail_credentials(self, user_id: str) -> Dict:
        """
        Get Gmail OAuth credentials for a user.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Gmail credentials dict (access_token, refresh_token, etc.)
            
        Raises:
            ValueError: If Gmail is not connected
        """
        user_email = await get_user_email(user_id)
        if not user_email:
            raise ValueError("Could not get user email")
        
        result = self.client.table("user_info") \
            .select("gmail_token, gmail_email") \
            .eq("email", user_email.lower()) \
            .execute()
        
        if not result.data or not result.data[0].get("gmail_token"):
            raise ValueError("Gmail not connected. Please connect your Gmail account first.")
        
        return result.data[0]["gmail_token"]
    
    async def start_indexing(self, user_id: str, project_id: str) -> Dict:
        """
        Start indexing a project with the AI backend.
        
        This method:
        1. Gets the project and validates access
        2. Gets Gmail credentials from user_info
        3. Generates ai_project_id BEFORE calling AI backend (so frontend can poll)
        4. Updates project status to 'indexing' with ai_project_id
        5. Calls AI backend to start indexing
        6. Updates status when complete
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            
        Returns:
            dict with indexing result and project info
            
        Raises:
            NotFoundError: If project doesn't exist
            ForbiddenError: If user doesn't have access
            ValueError: If Gmail is not connected
        """
        # Check access
        access = await check_project_access(user_id, project_id)
        project = access["project"]
        
        # Check if already indexing
        current_status = project.get("indexing_status", "not_started")
        if current_status == "indexing":
            raise ValueError("Project is already being indexed")
        
        # Get user email and Gmail credentials
        user_email = await get_user_email(user_id)
        gmail_credentials = await self._get_gmail_credentials(user_id)
        
        # Generate ai_project_id BEFORE calling AI backend
        # This allows the frontend to immediately start polling for progress
        ai_project_id = generate_ai_project_id(project["name"], user_email)
        logger.info(f"Generated ai_project_id: {ai_project_id} for project: {project['name']}")
        
        # Update status to 'indexing' AND store ai_project_id immediately
        # This is critical - frontend needs ai_project_id to poll AI backend for progress
        self.client.table("projects") \
            .update({
                "ai_project_id": ai_project_id,
                "indexing_status": "indexing",
                "updated_at": datetime.utcnow().isoformat()
            }) \
            .eq("id", project_id) \
            .execute()
        
        # Fire AI backend call in background (don't wait for it)
        # This allows frontend to start polling immediately
        async def _run_indexing():
            try:
                ai_client = get_ai_client()
                logger.info(f"Starting indexing for project: {project['name']}")
                result = await ai_client.start_indexing(
                    project_name=project["name"],
                    user_email=user_email,
                    gmail_credentials=gmail_credentials
                )
                
                # Update status when complete
                status = result.get("status", "completed")
                self.client.table("projects") \
                    .update({
                        "indexing_status": status,
                        "updated_at": datetime.utcnow().isoformat()
                    }) \
                    .eq("id", project_id) \
                    .execute()
                logger.info(f"Indexing completed for project {project_id}: {status}")
                
            except Exception as e:
                # Update status to 'failed'
                self.client.table("projects") \
                    .update({
                        "indexing_status": "failed",
                        "updated_at": datetime.utcnow().isoformat()
                    }) \
                    .eq("id", project_id) \
                    .execute()
                logger.error(f"Indexing failed for project {project_id}: {str(e)}")
        
        # Start background task
        asyncio.create_task(_run_indexing())
        
        # Return immediately so frontend can start polling
        return {
            "project_id": project_id,
            "ai_project_id": ai_project_id,
            "status": "indexing",
            "message": "Indexing started in background"
        }
    
    async def get_indexing_status(self, user_id: str, project_id: str) -> Dict:
        """
        Get the indexing status for a project.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            
        Returns:
            dict with indexing status and progress
        """
        # Check access and get project
        access = await check_project_access(user_id, project_id)
        project = access["project"]
        
        ai_project_id = project.get("ai_project_id")
        db_status = project.get("indexing_status", "not_started")
        
        # If not indexing or no ai_project_id, return DB status
        if db_status != "indexing" or not ai_project_id:
            return {
                "project_id": project_id,
                "ai_project_id": ai_project_id,
                "status": db_status,
                "percent": 100 if db_status == "completed" else 0,
                "phase": db_status.title(),
                "step": "",
                "details": {}
            }
        
        # Get status from AI backend
        try:
            ai_client = get_ai_client()
            ai_status = await ai_client.get_indexing_status(ai_project_id)
            
            # If AI backend says completed, update our DB
            if ai_status.get("percent") == 100 or ai_status.get("status") == "completed":
                self.client.table("projects") \
                    .update({
                        "indexing_status": "completed",
                        "updated_at": datetime.utcnow().isoformat()
                    }) \
                    .eq("id", project_id) \
                    .execute()
            
            return {
                "project_id": project_id,
                "ai_project_id": ai_project_id,
                "status": ai_status.get("status", db_status),
                "percent": ai_status.get("percent", 0),
                "phase": ai_status.get("phase", ""),
                "step": ai_status.get("step", ""),
                "details": ai_status.get("details", {})
            }
            
        except Exception as e:
            logger.warning(f"Could not get AI status: {str(e)}")
            return {
                "project_id": project_id,
                "ai_project_id": ai_project_id,
                "status": db_status,
                "percent": 0,
                "phase": "Unknown",
                "step": "Could not get status from AI backend",
                "details": {}
            }
    
    async def cancel_indexing(self, user_id: str, project_id: str) -> Dict:
        """
        Cancel an in-progress indexing operation.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            
        Returns:
            dict with cancellation status
        """
        # Check access and get project
        access = await check_project_access(user_id, project_id)
        project = access["project"]
        
        ai_project_id = project.get("ai_project_id")
        db_status = project.get("indexing_status", "not_started")
        
        if db_status != "indexing":
            raise ValueError(f"Cannot cancel - project is not indexing (status: {db_status})")
        
        if not ai_project_id:
            # Update status and return
            self.client.table("projects") \
                .update({
                    "indexing_status": "cancelled",
                    "updated_at": datetime.utcnow().isoformat()
                }) \
                .eq("id", project_id) \
                .execute()
            
            return {
                "project_id": project_id,
                "status": "cancelled",
                "message": "Indexing cancelled"
            }
        
        # Call AI backend to cancel
        try:
            ai_client = get_ai_client()
            result = await ai_client.cancel_indexing(ai_project_id)
            
            # Update status
            self.client.table("projects") \
                .update({
                    "indexing_status": "cancelled",
                    "updated_at": datetime.utcnow().isoformat()
                }) \
                .eq("id", project_id) \
                .execute()
            
            return {
                "project_id": project_id,
                "ai_project_id": ai_project_id,
                "status": "cancel_requested",
                "message": result.get("message", "Cancellation requested")
            }
            
        except Exception as e:
            logger.warning(f"Cancel request failed: {str(e)}")
            return {
                "project_id": project_id,
                "status": "error",
                "message": str(e)
            }
    
    async def search(
        self,
        user_id: str,
        project_id: str,
        question: str,
        top_k: Optional[int] = None
    ) -> Dict:
        """
        Search a project (non-streaming).
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            question: User's question
            top_k: Optional number of chunks to retrieve
            
        Returns:
            dict with answer and sources
            
        Raises:
            ValueError: If project is not indexed
        """
        # Check access and get project
        access = await check_project_access(user_id, project_id)
        project = access["project"]
        
        ai_project_id = project.get("ai_project_id")
        if not ai_project_id:
            raise ValueError("Project is not indexed. Please index the project first.")
        
        indexing_status = project.get("indexing_status", "not_started")
        if indexing_status != "completed":
            raise ValueError(f"Project indexing is not complete (status: {indexing_status})")
        
        # Call AI backend
        ai_client = get_ai_client()
        result = await ai_client.search(ai_project_id, question, top_k)
        
        return result
    
    async def search_stream(
        self,
        user_id: str,
        project_id: str,
        question: str,
        top_k: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Search a project with streaming response.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            question: User's question
            top_k: Optional number of chunks to retrieve
            
        Yields:
            SSE event strings
            
        Raises:
            ValueError: If project is not indexed
        """
        # Check access and get project
        access = await check_project_access(user_id, project_id)
        project = access["project"]
        
        ai_project_id = project.get("ai_project_id")
        if not ai_project_id:
            yield 'event: error\ndata: {"message": "Project is not indexed. Please index the project first."}\n\n'
            return
        
        indexing_status = project.get("indexing_status", "not_started")
        if indexing_status != "completed":
            yield f'event: error\ndata: {{"message": "Project indexing is not complete (status: {indexing_status})"}}\n\n'
            return
        
        # Stream from AI backend
        ai_client = get_ai_client()
        async for chunk in ai_client.search_stream(ai_project_id, question, top_k):
            yield chunk