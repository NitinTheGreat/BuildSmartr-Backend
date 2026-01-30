"""
Business logic for quote operations.

Includes:
- Quote request creation
- Vendor matching
- Impression tracking (for billing)
- Email notifications to vendors
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from shared.supabase_client import get_supabase_client
from shared.permissions import check_project_access, get_user_email, NotFoundError, ForbiddenError
from shared.ai_client import get_ai_client
from segments.service import SegmentService
from vendor_services.service import VendorServiceService
from emails.service import get_email_service

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
                    
                    # Enrich vendor quotes with contact info from matched_vendors
                    for vq in vendor_quotes:
                        # Find the matching vendor to get contact info
                        for mv in matched_vendors:
                            if mv.get("user_email") == vq.get("user_email"):
                                vq["contact_email"] = mv.get("contact_email")
                                vq["company_description"] = mv.get("company_description")
                                vq["vendor_service_id"] = mv.get("vendor_service_id")
                                break
                    
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
            
            # Step 8: Track impressions and send notifications for each vendor quote shown
            # This is the billing trigger - $250 per project+segment+vendor (first time only)
            if vendor_quotes:
                await self._track_impressions_and_notify(
                    quote_request_id=quote_request_id,
                    project_id=project_id,
                    project=project,
                    segment=segment,
                    segment_name=segment_info["name"],
                    project_sqft=project_sqft,
                    address_snapshot=address_snapshot,
                    options=options,
                    vendor_quotes=vendor_quotes,
                    customer_user_id=user_id
                )
            
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
    
    async def _track_impressions_and_notify(
        self,
        quote_request_id: str,
        project_id: str,
        project: Dict[str, Any],
        segment: str,
        segment_name: str,
        project_sqft: int,
        address_snapshot: Dict[str, Any],
        options: Dict[str, Any],
        vendor_quotes: List[Dict[str, Any]],
        customer_user_id: str
    ) -> None:
        """
        Track impressions for billing and send email notifications to vendors.
        
        This is called when vendor quotes are displayed to a customer.
        Each unique project+segment+vendor combination is charged $250 (first time only).
        
        Args:
            quote_request_id: The quote request's UUID
            project_id: The project's UUID
            project: The project data (for customer info)
            segment: The segment ID
            segment_name: The segment's display name
            project_sqft: The project size in sqft
            address_snapshot: The project's address at request time
            options: Quote request options
            vendor_quotes: List of vendor quotes being shown
            customer_user_id: The customer's user ID
        """
        email_service = get_email_service()
        
        # Get customer info for vendor notifications
        customer_email = await get_user_email(customer_user_id)
        customer_info = self.client.table("user_info") \
            .select("full_name, company_name") \
            .eq("email", customer_email.lower()) \
            .execute()
        
        customer_name = None
        if customer_info.data:
            customer_name = customer_info.data[0].get("full_name") or customer_info.data[0].get("company_name")
        
        # Build project location string
        project_location = ", ".join(filter(None, [
            address_snapshot.get("city"),
            address_snapshot.get("region"),
            address_snapshot.get("country")
        ]))
        
        # Get additional requirements from options
        additional_requirements = options.get("additional_requirements")
        
        for vq in vendor_quotes:
            vendor_service_id = vq.get("vendor_service_id")
            vendor_email = vq.get("user_email")
            vendor_company_name = vq.get("company_name")
            quoted_rate = vq.get("final_rate_per_sf", 0)
            quoted_total = vq.get("total", 0)
            
            if not vendor_service_id or not vendor_email:
                logger.warning(f"Skipping impression for quote without vendor_service_id or email")
                continue
            
            try:
                # Try to insert impression (will fail silently on duplicate due to UNIQUE constraint)
                impression_data = {
                    "quote_request_id": quote_request_id,
                    "project_id": project_id,
                    "segment": segment,
                    "vendor_service_id": vendor_service_id,
                    "vendor_email": vendor_email,
                    "vendor_company_name": vendor_company_name,
                    "customer_user_id": customer_user_id,
                    "customer_email": customer_email,
                    "customer_name": customer_name,
                    "project_name": project.get("name", "Unnamed Project"),
                    "project_location": project_location,
                    "project_sqft": project_sqft,
                    "quoted_rate_per_sf": quoted_rate,
                    "quoted_total": quoted_total,
                    "amount_charged": 250.00,
                    "billing_status": "pending",
                    "email_status": "pending"
                }
                
                result = self.client.table("quote_impressions") \
                    .insert(impression_data) \
                    .execute()
                
                if result.data:
                    impression_id = result.data[0].get("id")
                    logger.info(f"Created impression {impression_id} for vendor {vendor_email}")
                    
                    # Send email notification to vendor (async, don't wait)
                    try:
                        email_result = await email_service.send_vendor_lead_notification(
                            vendor_email=vendor_email,
                            vendor_company_name=vendor_company_name,
                            customer_name=customer_name,
                            customer_email=customer_email,
                            segment_name=segment_name,
                            project_sqft=project_sqft,
                            project_location=project_location,
                            project_name=project.get("name", "Unnamed Project"),
                            quoted_rate=quoted_rate,
                            quoted_total=quoted_total,
                            additional_requirements=additional_requirements
                        )
                        
                        # Update email status
                        email_status = "sent" if email_result.get("status") == "sent" else "failed"
                        self.client.table("quote_impressions") \
                            .update({
                                "email_status": email_status,
                                "email_sent_at": datetime.utcnow().isoformat() if email_status == "sent" else None
                            }) \
                            .eq("id", impression_id) \
                            .execute()
                            
                    except Exception as email_error:
                        logger.error(f"Failed to send notification to {vendor_email}: {str(email_error)}")
                        self.client.table("quote_impressions") \
                            .update({"email_status": "failed"}) \
                            .eq("id", impression_id) \
                            .execute()
                
            except Exception as e:
                # Check if it's a unique constraint violation (duplicate impression)
                if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.info(f"Impression already exists for project {project_id}, segment {segment}, vendor {vendor_email}")
                else:
                    logger.error(f"Failed to create impression: {str(e)}")
    
    async def get_vendor_impressions(self, vendor_email: str) -> List[Dict[str, Any]]:
        """
        Get all impressions (leads) for a vendor.
        
        This is what the vendor sees in their dashboard - all leads they've received.
        
        Args:
            vendor_email: The vendor's email address
            
        Returns:
            List of impressions with customer and project details
        """
        result = self.client.table("quote_impressions") \
            .select("*, segments(name)") \
            .eq("vendor_email", vendor_email.lower()) \
            .order("created_at", desc=True) \
            .execute()
        
        impressions = []
        for imp in result.data or []:
            segment_data = imp.pop("segments", {}) or {}
            impressions.append({
                "id": imp.get("id"),
                "segment": imp.get("segment"),
                "segment_name": segment_data.get("name"),
                "customer_name": imp.get("customer_name"),
                "customer_email": imp.get("customer_email"),
                "project_name": imp.get("project_name"),
                "project_location": imp.get("project_location"),
                "project_sqft": imp.get("project_sqft"),
                "quoted_rate_per_sf": float(imp.get("quoted_rate_per_sf") or 0),
                "quoted_total": float(imp.get("quoted_total") or 0),
                "amount_charged": float(imp.get("amount_charged") or 0),
                "billing_status": imp.get("billing_status"),
                "email_status": imp.get("email_status"),
                "created_at": imp.get("created_at"),
            })
        
        return impressions
    
    async def get_vendor_billing_summary(self, vendor_email: str) -> Dict[str, Any]:
        """
        Get billing summary for a vendor.
        
        Args:
            vendor_email: The vendor's email address
            
        Returns:
            Summary with total leads, amount owed, and payment status
        """
        result = self.client.table("quote_impressions") \
            .select("amount_charged, billing_status") \
            .eq("vendor_email", vendor_email.lower()) \
            .execute()
        
        total_leads = len(result.data or [])
        total_charged = sum(float(imp.get("amount_charged") or 0) for imp in result.data or [])
        total_paid = sum(
            float(imp.get("amount_charged") or 0) 
            for imp in result.data or [] 
            if imp.get("billing_status") == "paid"
        )
        balance_due = total_charged - total_paid
        
        return {
            "total_leads": total_leads,
            "total_charged": total_charged,
            "total_paid": total_paid,
            "balance_due": balance_due,
            "leads_by_status": {
                "pending": sum(1 for imp in result.data or [] if imp.get("billing_status") == "pending"),
                "invoiced": sum(1 for imp in result.data or [] if imp.get("billing_status") == "invoiced"),
                "paid": sum(1 for imp in result.data or [] if imp.get("billing_status") == "paid"),
            }
        }
