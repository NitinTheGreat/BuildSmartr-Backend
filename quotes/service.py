"""
Business logic for quote operations.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from shared.supabase_client import get_supabase_client
from shared.permissions import check_project_access, NotFoundError, ForbiddenError
from shared.ai_client import get_ai_client
from segments.service import SegmentService
from vendor_services.service import VendorServiceService

logger = logging.getLogger(__name__)


class QuoteService:
    """Service class for quote operations."""
    
    def __init__(self):
        self.client = get_supabase_client()
        self.segment_service = SegmentService()
        self.vendor_service = VendorServiceService()
    
    async def create_quote_request(
        self,
        user_id: str,
        project_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new quote request.
        
        This is the main quote flow:
        1. Validate project access and load address
        2. Create quote_request row
        3. Find matching vendors
        4. Call AI backend to generate quotes (if vendors found)
        5. Calculate IIVY benchmark
        6. Return complete results
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            data: Quote request data (segment, project_sqft, options)
            
        Returns:
            Complete quote response with vendor quotes and benchmark
        """
        # Step 1: Validate project access and load address
        access = await check_project_access(user_id, project_id)
        project = access["project"]
        
        segment = data.get("segment")
        project_sqft = data.get("project_sqft")
        options = data.get("options", {})
        chat_id = data.get("chat_id")
        
        if not segment:
            raise ValueError("Segment is required")
        if not project_sqft or project_sqft <= 0:
            raise ValueError("Valid project size (sqft) is required")
        
        # Build address snapshot from project
        address_snapshot = {
            "street": project.get("address_street"),
            "city": project.get("address_city"),
            "region": project.get("address_region"),
            "country": project.get("address_country", "CA"),
            "postal": project.get("address_postal"),
        }
        
        # Validate we have enough address info
        if not address_snapshot.get("region") or not address_snapshot.get("country"):
            raise ValueError("Project must have region and country set to get quotes")
        
        # Step 2: Create quote_request row
        quote_request_data = {
            "project_id": project_id,
            "chat_id": chat_id,
            "requested_by_user_id": user_id,
            "segment": segment,
            "project_sqft": project_sqft,
            "options": options,
            "address_snapshot": address_snapshot,
            "status": "matching_vendors",
        }
        
        result = self.client.table("quote_requests") \
            .insert(quote_request_data) \
            .execute()
        
        if not result.data:
            raise Exception("Failed to create quote request")
        
        quote_request = result.data[0]
        quote_request_id = quote_request["id"]
        
        try:
            # Step 3: Find matching vendors
            matched_vendors = await self.vendor_service.find_matching_vendors(
                segment=segment,
                country=address_snapshot["country"],
                region=address_snapshot.get("region")
            )
            
            # Update status
            self.client.table("quote_requests") \
                .update({
                    "status": "generating_quotes",
                    "matched_vendors": [
                        {"user_email": v["user_email"], "company_name": v["company_name"]}
                        for v in matched_vendors
                    ]
                }) \
                .eq("id", quote_request_id) \
                .execute()
            
            # Step 4: Get segment info for benchmark
            segment_info = await self.segment_service.get_segment(segment)
            
            # Step 5: Calculate IIVY benchmark (no LLM needed)
            iivy_benchmark = {
                "segment_id": segment,
                "segment_name": segment_info["name"],
                "benchmark_unit": segment_info["benchmark_unit"],
                "range_per_sf": {
                    "low": segment_info["benchmark_low"],
                    "high": segment_info["benchmark_high"]
                },
                "range_total": {
                    "low": round(segment_info["benchmark_low"] * project_sqft, 2),
                    "high": round(segment_info["benchmark_high"] * project_sqft, 2)
                },
                "project_sqft": project_sqft,
                "notes": segment_info.get("notes")
            }
            
            # Step 6: Generate vendor quotes via AI backend (if vendors found)
            vendor_quotes = []
            
            if matched_vendors:
                try:
                    ai_client = get_ai_client()
                    ai_response = await ai_client.generate_quotes(
                        segment=segment,
                        segment_name=segment_info["name"],
                        project_sqft=project_sqft,
                        city=address_snapshot.get("city"),
                        region=address_snapshot.get("region"),
                        country=address_snapshot.get("country"),
                        options=options,
                        vendors=matched_vendors
                    )
                    vendor_quotes = ai_response.get("vendor_quotes", [])
                except Exception as e:
                    logger.error(f"AI quote generation failed: {str(e)}")
                    # Continue without AI quotes - we'll still return benchmark
            
            # Step 7: Update quote_request with results
            self.client.table("quote_requests") \
                .update({
                    "status": "completed",
                    "vendor_quotes": vendor_quotes,
                    "iivy_benchmark": iivy_benchmark,
                    "completed_at": datetime.utcnow().isoformat()
                }) \
                .eq("id", quote_request_id) \
                .execute()
            
            return {
                "id": quote_request_id,
                "project_id": project_id,
                "segment": segment,
                "segment_name": segment_info["name"],
                "project_sqft": project_sqft,
                "address": address_snapshot,
                "options": options,
                "status": "completed",
                "matched_vendors_count": len(matched_vendors),
                "vendor_quotes": vendor_quotes,
                "iivy_benchmark": iivy_benchmark,
                "created_at": quote_request["created_at"],
                "completed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            # Update status to failed
            self.client.table("quote_requests") \
                .update({
                    "status": "failed",
                    "error_message": str(e)
                }) \
                .eq("id", quote_request_id) \
                .execute()
            raise
    
    async def list_project_quotes(
        self, 
        user_id: str, 
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        List all quote requests for a project.
        
        Args:
            user_id: The authenticated user's ID
            project_id: The project's UUID
            
        Returns:
            List of quote requests with summary info
        """
        # Verify project access
        await check_project_access(user_id, project_id)
        
        result = self.client.table("quote_requests") \
            .select("*, segments(name)") \
            .eq("project_id", project_id) \
            .order("created_at", desc=True) \
            .execute()
        
        quotes = []
        for quote in result.data or []:
            segment_data = quote.pop("segments", {}) or {}
            vendor_quotes = quote.get("vendor_quotes") or []
            iivy_benchmark = quote.get("iivy_benchmark") or {}
            
            quotes.append({
                "id": quote.get("id"),
                "segment": quote.get("segment"),
                "segment_name": segment_data.get("name"),
                "project_sqft": quote.get("project_sqft"),
                "status": quote.get("status"),
                "vendor_quotes_count": len(vendor_quotes),
                "benchmark_range": {
                    "low": iivy_benchmark.get("range_total", {}).get("low"),
                    "high": iivy_benchmark.get("range_total", {}).get("high")
                },
                "created_at": quote.get("created_at"),
                "completed_at": quote.get("completed_at"),
            })
        
        return quotes
    
    async def get_quote(self, user_id: str, quote_id: str) -> Dict[str, Any]:
        """
        Get a single quote request with full details.
        
        Args:
            user_id: The authenticated user's ID
            quote_id: The quote request's UUID
            
        Returns:
            Full quote request with vendor quotes and benchmark
            
        Raises:
            NotFoundError: If quote not found
            ForbiddenError: If user doesn't have access
        """
        result = self.client.table("quote_requests") \
            .select("*, segments(name, phase)") \
            .eq("id", quote_id) \
            .execute()
        
        if not result.data:
            raise NotFoundError(f"Quote request not found")
        
        quote = result.data[0]
        
        # Verify user has access (either requested it or owns the project)
        if quote.get("requested_by_user_id") != user_id:
            # Check if user owns the project
            project_result = self.client.table("projects") \
                .select("user_id") \
                .eq("id", quote.get("project_id")) \
                .execute()
            
            if not project_result.data or project_result.data[0].get("user_id") != user_id:
                raise ForbiddenError("You don't have access to this quote")
        
        segment_data = quote.pop("segments", {}) or {}
        
        return {
            "id": quote.get("id"),
            "project_id": quote.get("project_id"),
            "chat_id": quote.get("chat_id"),
            "segment": quote.get("segment"),
            "segment_name": segment_data.get("name"),
            "segment_phase": segment_data.get("phase"),
            "project_sqft": quote.get("project_sqft"),
            "options": quote.get("options"),
            "address": quote.get("address_snapshot"),
            "status": quote.get("status"),
            "matched_vendors": quote.get("matched_vendors"),
            "vendor_quotes": quote.get("vendor_quotes") or [],
            "iivy_benchmark": quote.get("iivy_benchmark"),
            "error_message": quote.get("error_message"),
            "created_at": quote.get("created_at"),
            "completed_at": quote.get("completed_at"),
        }
