"""
HTTP route handlers for user info endpoints.
"""

import logging
import azure.functions as func
from shared.auth import get_user_from_token, UnauthorizedError
from shared.responses import (
    success_response, error_response, validation_error_response
)
from shared.permissions import NotFoundError
from .service import UserInfoService

logger = logging.getLogger(__name__)


def register_user_info_routes(app: func.FunctionApp):
    """Register all user info-related routes with the function app."""
    
    @app.route(route="user/info", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
    async def get_user_info(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/user/info
        Get current user info.
        """
        try:
            user = get_user_from_token(req)
            user_email = user.get("email")
            
            if not user_email:
                return error_response("User email not found in token", 400)
            
            service = UserInfoService()
            user_info = await service.get_user_info(user_email)
            
            return success_response(user_info)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            return error_response("Failed to get user info", 500)
    
    @app.route(route="user/info", methods=["PUT"], auth_level=func.AuthLevel.ANONYMOUS)
    async def update_user_info(req: func.HttpRequest) -> func.HttpResponse:
        """
        PUT /api/user/info
        Update current user info.
        """
        try:
            user = get_user_from_token(req)
            user_email = user.get("email")
            
            if not user_email:
                return error_response("User email not found in token", 400)
            
            # Parse request body
            try:
                body = req.get_json()
            except ValueError:
                return error_response("Invalid JSON body", 400)
            
            service = UserInfoService()
            user_info = await service.update_user_info(user_email, body)
            
            return success_response(user_info)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except Exception as e:
            logger.error(f"Error updating user info: {str(e)}")
            return error_response("Failed to update user info", 500)
    
    @app.route(
        route="user/connect/gmail",
        methods=["POST"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def connect_gmail(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/user/connect/gmail
        Connect Gmail account to user profile.
        """
        try:
            user = get_user_from_token(req)
            user_email = user.get("email")
            
            if not user_email:
                return error_response("User email not found in token", 400)
            
            # Parse request body
            try:
                body = req.get_json()
            except ValueError:
                return error_response("Invalid JSON body", 400)
            
            # Validate required fields
            errors = []
            if not body.get("gmail_email"):
                errors.append({"field": "gmail_email", "message": "Gmail email is required"})
            if not body.get("gmail_token"):
                errors.append({"field": "gmail_token", "message": "Gmail token is required"})
            
            if errors:
                return validation_error_response(errors)
            
            service = UserInfoService()
            user_info = await service.connect_gmail(
                user_email,
                body["gmail_email"],
                body["gmail_token"]
            )
            
            return success_response(user_info)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except Exception as e:
            logger.error(f"Error connecting Gmail: {str(e)}")
            return error_response("Failed to connect Gmail", 500)
    
    @app.route(
        route="user/disconnect/gmail",
        methods=["POST"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def disconnect_gmail(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/user/disconnect/gmail
        Disconnect Gmail account from user profile.
        """
        try:
            user = get_user_from_token(req)
            user_email = user.get("email")
            
            if not user_email:
                return error_response("User email not found in token", 400)
            
            service = UserInfoService()
            user_info = await service.disconnect_gmail(user_email)
            
            return success_response(user_info)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except Exception as e:
            logger.error(f"Error disconnecting Gmail: {str(e)}")
            return error_response("Failed to disconnect Gmail", 500)
    
    @app.route(
        route="user/connect/outlook",
        methods=["POST"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def connect_outlook(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/user/connect/outlook
        Connect Outlook account to user profile.
        """
        try:
            user = get_user_from_token(req)
            user_email = user.get("email")
            
            if not user_email:
                return error_response("User email not found in token", 400)
            
            # Parse request body
            try:
                body = req.get_json()
            except ValueError:
                return error_response("Invalid JSON body", 400)
            
            # Validate required fields
            errors = []
            if not body.get("outlook_email"):
                errors.append({"field": "outlook_email", "message": "Outlook email is required"})
            if not body.get("outlook_token"):
                errors.append({"field": "outlook_token", "message": "Outlook token is required"})
            
            if errors:
                return validation_error_response(errors)
            
            service = UserInfoService()
            user_info = await service.connect_outlook(
                user_email,
                body["outlook_email"],
                body["outlook_token"]
            )
            
            return success_response(user_info)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except Exception as e:
            logger.error(f"Error connecting Outlook: {str(e)}")
            return error_response("Failed to connect Outlook", 500)
    
    @app.route(
        route="user/disconnect/outlook",
        methods=["POST"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def disconnect_outlook(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/user/disconnect/outlook
        Disconnect Outlook account from user profile.
        """
        try:
            user = get_user_from_token(req)
            user_email = user.get("email")
            
            if not user_email:
                return error_response("User email not found in token", 400)
            
            service = UserInfoService()
            user_info = await service.disconnect_outlook(user_email)
            
            return success_response(user_info)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except Exception as e:
            logger.error(f"Error disconnecting Outlook: {str(e)}")
            return error_response("Failed to disconnect Outlook", 500)
