"""
Business logic for vendor services operations.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from shared.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class VendorServiceService:
    """Service class for vendor service operations."""
    
    def __init__(self):
        self.client = get_supabase_client()
    
    async def list_services(self, user_email: str) -> List[Dict[str, Any]]:
        """
        List all vendor services for the current user.
        
        Args:
            user_email: The authenticated user's email
            
        Returns:
            List of vendor service offerings
        """
        result = self.client.table("vendor_services") \
            .select("*, segments(name, phase, benchmark_low, benchmark_high)") \
            .eq("user_email", user_email.lower()) \
            .order("created_at", desc=True) \
            .execute()
        
        services = []
        for service in result.data or []:
            segment_data = service.pop("segments", {}) or {}
            services.append({
                "id": service.get("id"),
                "company_name": service.get("company_name"),
                "segment": service.get("segment"),
                "segment_name": segment_data.get("name"),
                "segment_phase": segment_data.get("phase"),
                "benchmark_low": float(segment_data.get("benchmark_low") or 0),
                "benchmark_high": float(segment_data.get("benchmark_high") or 0),
                "countries_served": service.get("countries_served", []),
                "regions_served": service.get("regions_served", []),
                "pricing_rules": service.get("pricing_rules"),
                "lead_time": service.get("lead_time"),
                "notes": service.get("notes"),
                "is_active": service.get("is_active", True),
                "created_at": service.get("created_at"),
                "updated_at": service.get("updated_at"),
            })
        
        return services
    
    async def create_service(self, user_email: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new vendor service offering.
        
        Args:
            user_email: The authenticated user's email
            data: Service data (segment, company_name, pricing_rules, etc.)
            
        Returns:
            Created vendor service
            
        Raises:
            ValueError: If validation fails or segment already exists
        """
        segment = data.get("segment")
        company_name = data.get("company_name")
        
        if not segment:
            raise ValueError("Segment is required")
        if not company_name:
            raise ValueError("Company name is required")
        
        # Verify segment exists
        segment_result = self.client.table("segments") \
            .select("id, name") \
            .eq("id", segment) \
            .execute()
        
        if not segment_result.data:
            raise ValueError(f"Invalid segment: {segment}")
        
        # Check if user already has this segment
        existing = self.client.table("vendor_services") \
            .select("id") \
            .eq("user_email", user_email.lower()) \
            .eq("segment", segment) \
            .execute()
        
        if existing.data:
            raise ValueError(f"You already have a service offering for this segment")
        
        service_data = {
            "user_email": user_email.lower(),
            "company_name": company_name,
            "segment": segment,
            "countries_served": data.get("countries_served", ["CA"]),
            "regions_served": data.get("regions_served", []),
            "pricing_rules": data.get("pricing_rules"),
            "lead_time": data.get("lead_time"),
            "notes": data.get("notes"),
            "company_description": data.get("company_description"),
            "is_active": data.get("is_active", True),
        }
        
        result = self.client.table("vendor_services") \
            .insert(service_data) \
            .execute()
        
        if not result.data:
            raise Exception("Failed to create vendor service")
        
        # Also update company_name in user_info if not set
        user_info_result = self.client.table("user_info") \
            .select("company_name") \
            .eq("email", user_email.lower()) \
            .execute()
        
        if user_info_result.data and not user_info_result.data[0].get("company_name"):
            self.client.table("user_info") \
                .update({"company_name": company_name}) \
                .eq("email", user_email.lower()) \
                .execute()
        
        service = result.data[0]
        segment_info = segment_result.data[0]
        
        return {
            "id": service.get("id"),
            "company_name": service.get("company_name"),
            "segment": service.get("segment"),
            "segment_name": segment_info.get("name"),
            "countries_served": service.get("countries_served", []),
            "regions_served": service.get("regions_served", []),
            "pricing_rules": service.get("pricing_rules"),
            "lead_time": service.get("lead_time"),
            "notes": service.get("notes"),
            "is_active": service.get("is_active", True),
            "created_at": service.get("created_at"),
            "updated_at": service.get("updated_at"),
        }
    
    async def update_service(
        self, 
        user_email: str, 
        service_id: str, 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a vendor service offering.
        
        Args:
            user_email: The authenticated user's email
            service_id: The service's UUID
            data: Updated service data
            
        Returns:
            Updated vendor service
            
        Raises:
            ValueError: If service not found or not owned by user
        """
        # Verify ownership
        existing = self.client.table("vendor_services") \
            .select("*") \
            .eq("id", service_id) \
            .eq("user_email", user_email.lower()) \
            .execute()
        
        if not existing.data:
            raise ValueError("Vendor service not found")
        
        update_data = {
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Only update provided fields
        allowed_fields = [
            "company_name", "countries_served", "regions_served", 
            "pricing_rules", "lead_time", "notes", "company_description", "is_active"
        ]
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        result = self.client.table("vendor_services") \
            .update(update_data) \
            .eq("id", service_id) \
            .execute()
        
        if not result.data:
            raise Exception("Failed to update vendor service")
        
        service = result.data[0]
        
        # Get segment info
        segment_result = self.client.table("segments") \
            .select("name, phase") \
            .eq("id", service.get("segment")) \
            .execute()
        
        segment_info = segment_result.data[0] if segment_result.data else {}
        
        return {
            "id": service.get("id"),
            "company_name": service.get("company_name"),
            "segment": service.get("segment"),
            "segment_name": segment_info.get("name"),
            "segment_phase": segment_info.get("phase"),
            "countries_served": service.get("countries_served", []),
            "regions_served": service.get("regions_served", []),
            "pricing_rules": service.get("pricing_rules"),
            "lead_time": service.get("lead_time"),
            "notes": service.get("notes"),
            "is_active": service.get("is_active", True),
            "created_at": service.get("created_at"),
            "updated_at": service.get("updated_at"),
        }
    
    async def delete_service(self, user_email: str, service_id: str) -> bool:
        """
        Delete a vendor service offering.
        
        Args:
            user_email: The authenticated user's email
            service_id: The service's UUID
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If service not found or not owned by user
        """
        # Verify ownership
        existing = self.client.table("vendor_services") \
            .select("id") \
            .eq("id", service_id) \
            .eq("user_email", user_email.lower()) \
            .execute()
        
        if not existing.data:
            raise ValueError("Vendor service not found")
        
        self.client.table("vendor_services") \
            .delete() \
            .eq("id", service_id) \
            .execute()
        
        return True
    
    async def find_matching_vendors(
        self, 
        segment: str, 
        country: str, 
        region: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find vendors that match a segment and location.
        
        Used for quote matching.
        
        Args:
            segment: The segment ID (e.g., "windows_exterior_doors")
            country: Country code (e.g., "CA", "US")
            region: Optional region/state code (e.g., "BC", "WA")
            
        Returns:
            List of matching vendor services with pricing info and contact details
        """
        # Query vendors for this segment that serve this country
        # Using raw SQL-like query since Supabase Python doesn't support array contains well
        result = self.client.table("vendor_services") \
            .select("*, user_info(email, company_name)") \
            .eq("segment", segment) \
            .eq("is_active", True) \
            .execute()
        
        vendors = []
        for service in result.data or []:
            countries = service.get("countries_served", [])
            regions = service.get("regions_served", [])
            
            # Check country match
            if country not in countries:
                continue
            
            # Check region match (empty regions_served means "all regions")
            if region and regions and region not in regions:
                continue
            
            user_info = service.get("user_info", {}) or {}
            
            vendors.append({
                "vendor_service_id": service.get("id"),
                "user_email": service.get("user_email"),
                "company_name": service.get("company_name") or user_info.get("company_name"),
                "company_description": service.get("company_description"),
                "contact_email": service.get("user_email"),
                "segment": service.get("segment"),
                "pricing_rules": service.get("pricing_rules"),
                "lead_time": service.get("lead_time"),
                "notes": service.get("notes"),
                "countries_served": countries,
                "regions_served": regions,
            })
        
        return vendors
