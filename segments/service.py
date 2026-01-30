"""
Business logic for segments operations.
"""

import logging
from typing import List, Dict, Any
from shared.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class SegmentService:
    """Service class for segment operations."""
    
    def __init__(self):
        self.client = get_supabase_client()
    
    async def list_segments(self, grouped: bool = True) -> Any:
        """
        List all trade segments.
        
        Args:
            grouped: If True, return segments grouped by phase. If False, return flat list.
            
        Returns:
            If grouped: Dict with phases array containing segments
            If not grouped: List of all segments
        """
        result = self.client.table("segments") \
            .select("*") \
            .order("phase_order", desc=False) \
            .order("name", desc=False) \
            .execute()
        
        segments = result.data or []
        
        if not grouped:
            return segments
        
        # Group by phase
        phases_dict: Dict[str, Dict[str, Any]] = {}
        
        for segment in segments:
            phase = segment.get("phase", "Other")
            phase_order = segment.get("phase_order", 99)
            
            if phase not in phases_dict:
                phases_dict[phase] = {
                    "name": phase,
                    "order": phase_order,
                    "segments": []
                }
            
            phases_dict[phase]["segments"].append({
                "id": segment.get("id"),
                "name": segment.get("name"),
                "benchmark_low": float(segment.get("benchmark_low") or 0),
                "benchmark_high": float(segment.get("benchmark_high") or 0),
                "benchmark_unit": segment.get("benchmark_unit", "$/sf"),
                "notes": segment.get("notes")
            })
        
        # Convert to sorted list
        phases = sorted(phases_dict.values(), key=lambda p: p["order"])
        
        return {"phases": phases}
    
    async def get_segment(self, segment_id: str) -> Dict[str, Any]:
        """
        Get a single segment by ID.
        
        Args:
            segment_id: The segment's ID (e.g., "windows_exterior_doors")
            
        Returns:
            Segment data with benchmark info
            
        Raises:
            ValueError: If segment not found
        """
        result = self.client.table("segments") \
            .select("*") \
            .eq("id", segment_id) \
            .execute()
        
        if not result.data:
            raise ValueError(f"Segment '{segment_id}' not found")
        
        segment = result.data[0]
        
        return {
            "id": segment.get("id"),
            "name": segment.get("name"),
            "phase": segment.get("phase"),
            "phase_order": segment.get("phase_order"),
            "benchmark_low": float(segment.get("benchmark_low") or 0),
            "benchmark_high": float(segment.get("benchmark_high") or 0),
            "benchmark_unit": segment.get("benchmark_unit", "$/sf"),
            "notes": segment.get("notes")
        }
    
    def calculate_benchmark(self, segment_id: str, project_sqft: int) -> Dict[str, Any]:
        """
        Calculate IIVY benchmark totals for a segment and project size.
        
        This is synchronous since it's a simple calculation.
        
        Args:
            segment_id: The segment's ID
            project_sqft: Project size in square feet
            
        Returns:
            Benchmark calculation with per-sf rates and totals
        """
        # Get segment synchronously for benchmark calculation
        result = self.client.table("segments") \
            .select("*") \
            .eq("id", segment_id) \
            .execute()
        
        if not result.data:
            raise ValueError(f"Segment '{segment_id}' not found")
        
        segment = result.data[0]
        
        benchmark_low = float(segment.get("benchmark_low") or 0)
        benchmark_high = float(segment.get("benchmark_high") or 0)
        
        return {
            "segment_id": segment_id,
            "segment_name": segment.get("name"),
            "benchmark_unit": segment.get("benchmark_unit", "$/sf"),
            "range_per_sf": {
                "low": benchmark_low,
                "high": benchmark_high
            },
            "range_total": {
                "low": round(benchmark_low * project_sqft, 2),
                "high": round(benchmark_high * project_sqft, 2)
            },
            "project_sqft": project_sqft,
            "notes": segment.get("notes")
        }
