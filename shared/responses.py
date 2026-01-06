"""
Standard HTTP response helpers for consistent API responses.
"""

import json
from typing import Any, Optional, Dict, List, Union
import azure.functions as func


def json_serialize(obj: Any) -> str:
    """
    Serialize object to JSON, handling datetime and UUID types.
    """
    import datetime
    import uuid
    
    def default_serializer(o):
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        if isinstance(o, uuid.UUID):
            return str(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
    
    return json.dumps(obj, default=default_serializer)


def success_response(
    data: Union[Dict, List, Any],
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None
) -> func.HttpResponse:
    """
    Create a successful JSON response.
    
    Args:
        data: Response data to serialize
        status_code: HTTP status code (default: 200)
        headers: Optional additional headers
        
    Returns:
        Azure Functions HttpResponse
    """
    response_headers = {
        "Content-Type": "application/json",
        **(headers or {})
    }
    
    return func.HttpResponse(
        json_serialize(data),
        status_code=status_code,
        mimetype="application/json",
        headers=response_headers
    )


def created_response(
    data: Union[Dict, List, Any],
    headers: Optional[Dict[str, str]] = None
) -> func.HttpResponse:
    """
    Create a 201 Created response.
    
    Args:
        data: Created resource data
        headers: Optional additional headers
        
    Returns:
        Azure Functions HttpResponse with 201 status
    """
    return success_response(data, status_code=201, headers=headers)


def no_content_response() -> func.HttpResponse:
    """
    Create a 204 No Content response.
    
    Returns:
        Azure Functions HttpResponse with 204 status
    """
    return func.HttpResponse(
        status_code=204
    )


def error_response(
    message: str,
    status_code: int = 400,
    errors: Optional[List[Dict]] = None,
    headers: Optional[Dict[str, str]] = None
) -> func.HttpResponse:
    """
    Create an error JSON response.
    
    Args:
        message: Error message
        status_code: HTTP status code (default: 400)
        errors: Optional list of detailed errors
        headers: Optional additional headers
        
    Returns:
        Azure Functions HttpResponse with error details
    """
    error_body = {
        "error": True,
        "message": message,
    }
    
    if errors:
        error_body["errors"] = errors
    
    response_headers = {
        "Content-Type": "application/json",
        **(headers or {})
    }
    
    return func.HttpResponse(
        json_serialize(error_body),
        status_code=status_code,
        mimetype="application/json",
        headers=response_headers
    )


def not_found_response(
    resource: str = "Resource",
    message: Optional[str] = None
) -> func.HttpResponse:
    """
    Create a 404 Not Found response.
    
    Args:
        resource: Name of the resource that wasn't found
        message: Optional custom message
        
    Returns:
        Azure Functions HttpResponse with 404 status
    """
    return error_response(
        message or f"{resource} not found",
        status_code=404
    )


def forbidden_response(
    message: str = "You don't have permission to access this resource"
) -> func.HttpResponse:
    """
    Create a 403 Forbidden response.
    
    Args:
        message: Error message
        
    Returns:
        Azure Functions HttpResponse with 403 status
    """
    return error_response(message, status_code=403)


def unauthorized_response(
    message: str = "Authentication required"
) -> func.HttpResponse:
    """
    Create a 401 Unauthorized response.
    
    Args:
        message: Error message
        
    Returns:
        Azure Functions HttpResponse with 401 status
    """
    return error_response(message, status_code=401)


def validation_error_response(
    errors: List[Dict[str, Any]],
    message: str = "Validation failed"
) -> func.HttpResponse:
    """
    Create a 422 Validation Error response.
    
    Args:
        errors: List of validation errors
        message: Overall error message
        
    Returns:
        Azure Functions HttpResponse with 422 status
    """
    return error_response(message, status_code=422, errors=errors)


def internal_error_response(
    message: str = "Internal server error"
) -> func.HttpResponse:
    """
    Create a 500 Internal Server Error response.
    
    Args:
        message: Error message
        
    Returns:
        Azure Functions HttpResponse with 500 status
    """
    return error_response(message, status_code=500)
