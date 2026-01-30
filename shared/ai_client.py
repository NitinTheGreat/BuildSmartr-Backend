"""
AI Backend Client for BuildSmartr.

This module handles all communication with the AI Backend (IIVY-AI-Backend).
The AI backend handles:
- Email indexing and vectorization (Pinecone)
- RAG search with LLM answers
- Vector cleanup on project deletion

The BuildSmartr backend is the only caller - frontend never calls AI backend directly.
"""

import os
import json
import logging
import aiohttp
from typing import Dict, Optional, AsyncGenerator

logger = logging.getLogger(__name__)


def get_ai_backend_url() -> str:
    """Get the AI backend URL from environment variables."""
    url = os.environ.get("AI_BACKEND_URL")
    if not url:
        raise ValueError("AI_BACKEND_URL environment variable not set")
    return url.rstrip('/')


class AIBackendClient:
    """
    HTTP client for communicating with the AI Backend.
    
    All methods are async for non-blocking operation.
    """
    
    def __init__(self):
        self.base_url = get_ai_backend_url()
    
    async def start_indexing(
        self,
        project_name: str,
        user_email: str,
        gmail_credentials: Dict
    ) -> Dict:
        """
        Start indexing a project.
        
        Calls AI backend's /api/index_and_vectorize endpoint.
        This is a long-running operation - use get_indexing_status to poll progress.
        
        Args:
            project_name: Name of the project (used in email search)
            user_email: User's email address
            gmail_credentials: OAuth credentials for Gmail API
            
        Returns:
            dict with:
                - status: "completed" | "cancelled" | "error"
                - project_id: AI project ID (e.g., "microsoft_azure_a1b2c3d4")
                - stats: indexing statistics
                
        Raises:
            Exception: If indexing fails
        """
        url = f"{self.base_url}/api/index_and_vectorize"
        
        payload = {
            "project_name": project_name,
            "user_email": user_email,
            "gmail_credentials": gmail_credentials
        }
        
        logger.info(f"Starting indexing for project: {project_name}")
        
        async with aiohttp.ClientSession() as session:
            # Long timeout for indexing (can take several minutes)
            timeout = aiohttp.ClientTimeout(total=600)  # 10 minutes
            
            async with session.post(url, json=payload, timeout=timeout) as response:
                result = await response.json()
                
                if response.status != 200:
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"Indexing failed: {error_msg}")
                    raise Exception(f"Indexing failed: {error_msg}")
                
                logger.info(f"Indexing completed: {result.get('project_id')}")
                return result
    
    async def get_indexing_status(self, ai_project_id: str) -> Dict:
        """
        Get the current status of an indexing operation.
        
        Calls AI backend's /api/get_project_status endpoint.
        
        Args:
            ai_project_id: The AI project ID (e.g., "microsoft_azure_a1b2c3d4")
            
        Returns:
            dict with:
                - project_id: AI project ID
                - status: "indexing" | "completed" | "not_found" | "error"
                - percent: Progress percentage (0-100)
                - phase: Current phase name
                - step: Current step description
                - details: Additional stats (thread_count, message_count, pdf_count)
        """
        url = f"{self.base_url}/api/get_project_status"
        params = {"project_id": ai_project_id}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                result = await response.json()
                return result
    
    async def cancel_indexing(self, ai_project_id: str) -> Dict:
        """
        Cancel an in-progress indexing operation.
        
        Calls AI backend's /api/cancel_project_indexing endpoint.
        
        Args:
            ai_project_id: The AI project ID to cancel
            
        Returns:
            dict with:
                - status: "cancel_requested"
                - message: Status message
        """
        url = f"{self.base_url}/api/cancel_project_indexing"
        params = {"project_id": ai_project_id}
        
        logger.info(f"Cancelling indexing for: {ai_project_id}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params) as response:
                result = await response.json()
                
                if response.status != 200:
                    error_msg = result.get("error", "Unknown error")
                    logger.warning(f"Cancel request issue: {error_msg}")
                
                return result
    
    async def search(
        self,
        ai_project_id: str,
        question: str,
        top_k: Optional[int] = None
    ) -> Dict:
        """
        Search a project (non-streaming).
        
        Calls AI backend's /api/search_project endpoint.
        
        Args:
            ai_project_id: The AI project ID to search
            question: User's question
            top_k: Optional number of chunks to retrieve
            
        Returns:
            dict with:
                - answer: Generated answer
                - sources: List of source chunks
                - search_time_ms, llm_time_ms, total_time_ms: Timing info
        """
        url = f"{self.base_url}/api/search_project"
        
        payload = {
            "project_id": ai_project_id,
            "question": question
        }
        if top_k:
            payload["top_k"] = top_k
        
        logger.info(f"Searching project {ai_project_id}: {question[:50]}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                result = await response.json()
                
                if response.status != 200:
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"Search failed: {error_msg}")
                    raise Exception(f"Search failed: {error_msg}")
                
                return result
    
    async def search_stream(
        self,
        ai_project_id: str,
        question: str,
        top_k: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Search a project with streaming response.
        
        Calls AI backend's /api/search_project_stream endpoint.
        Yields Server-Sent Events as they arrive.
        
        Args:
            ai_project_id: The AI project ID to search
            question: User's question
            top_k: Optional number of chunks to retrieve
            
        Yields:
            SSE event strings (e.g., "event: chunk\ndata: {...}\n\n")
        """
        url = f"{self.base_url}/api/search_project_stream"
        
        payload = {
            "project_id": ai_project_id,
            "question": question
        }
        if top_k:
            payload["top_k"] = top_k
        
        logger.info(f"Streaming search for {ai_project_id}: {question[:50]}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Stream search failed: {error_text}")
                    yield f"event: error\ndata: {json.dumps({'message': 'Search failed'})}\n\n"
                    return
                
                # Stream the response
                async for line in response.content:
                    if line:
                        yield line.decode('utf-8')
    
    async def delete_project(
        self,
        ai_project_id: str,
        user_email: Optional[str] = None
    ) -> Dict:
        """
        Delete a project's vectors from Pinecone.
        
        Calls AI backend's /api/delete_project endpoint.
        Should be called BEFORE deleting from Supabase.
        
        Args:
            ai_project_id: The AI project ID to delete
            user_email: Optional user email for Supabase storage cleanup
            
        Returns:
            dict with:
                - status: "deleted"
                - vectors_deleted: bool
                - storage_deleted: bool
        """
        url = f"{self.base_url}/api/delete_project"
        
        params = {"project_id": ai_project_id}
        if user_email:
            params["user_email"] = user_email
        
        logger.info(f"Deleting AI project: {ai_project_id}")
        
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, params=params) as response:
                result = await response.json()
                
                if response.status != 200:
                    error_msg = result.get("error", "Unknown error")
                    logger.warning(f"Delete warning: {error_msg}")
                    # Don't raise - we still want to delete from Supabase
                
                logger.info(f"AI project deleted: {ai_project_id}")
                return result
    
    async def generate_quotes(
        self,
        segment: str,
        segment_name: str,
        project_sqft: int,
        city: Optional[str],
        region: str,
        country: str,
        options: Dict,
        vendors: list
    ) -> Dict:
        """
        Generate vendor quotes using LLM.
        
        Calls AI backend's /api/generate_quotes endpoint.
        The LLM parses each vendor's pricing rules and calculates quotes.
        
        Args:
            segment: Segment ID (e.g., "windows_exterior_doors")
            segment_name: Human-readable segment name
            project_sqft: Project size in square feet
            city: City name (for location-based adjustments)
            region: Region/state code (e.g., "BC", "WA")
            country: Country code (e.g., "CA", "US")
            options: Quote options (e.g., {"finish": "premium"})
            vendors: List of vendor dicts with pricing_rules
            
        Returns:
            dict with:
                - vendor_quotes: Array of calculated quotes per vendor
        """
        url = f"{self.base_url}/api/generate_quotes"
        
        payload = {
            "segment": segment,
            "segment_name": segment_name,
            "project_sqft": project_sqft,
            "city": city,
            "region": region,
            "country": country,
            "options": options,
            "vendors": vendors
        }
        
        logger.info(f"Generating quotes for {segment} ({len(vendors)} vendors)")
        
        async with aiohttp.ClientSession() as session:
            timeout = aiohttp.ClientTimeout(total=60)  # 1 minute timeout
            
            async with session.post(url, json=payload, timeout=timeout) as response:
                result = await response.json()
                
                if response.status != 200:
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"Quote generation failed: {error_msg}")
                    raise Exception(f"Quote generation failed: {error_msg}")
                
                logger.info(f"Generated {len(result.get('vendor_quotes', []))} quotes")
                return result


# Singleton instance
_ai_client: Optional[AIBackendClient] = None


def get_ai_client() -> AIBackendClient:
    """Get the AI backend client singleton."""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIBackendClient()
    return _ai_client
