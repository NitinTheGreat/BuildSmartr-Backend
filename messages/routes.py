"""
HTTP route handlers for message endpoints.
"""

import logging
import azure.functions as func
from shared.auth import get_user_from_token, UnauthorizedError
from shared.responses import (
    success_response, created_response, no_content_response,
    error_response, not_found_response, forbidden_response, validation_error_response
)
from shared.permissions import NotFoundError, ForbiddenError
from .service import MessageService

logger = logging.getLogger(__name__)


def register_message_routes(app: func.FunctionApp):
    """Register all message-related routes with the function app."""
    
    @app.route(
        route="chats/{chat_id}/messages",
        methods=["GET"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def list_messages(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/chats/{chat_id}/messages
        List all messages in a chat.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            chat_id = req.route_params.get("chat_id")
            
            if not chat_id:
                return error_response("Chat ID is required", 400)
            
            service = MessageService()
            messages = await service.list_messages(user_id, chat_id)
            
            return success_response(messages)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Chat", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error listing messages: {str(e)}")
            return error_response("Failed to list messages", 500)
    
    @app.route(
        route="chats/{chat_id}/messages",
        methods=["POST"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def create_message(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/chats/{chat_id}/messages
        Add a message to a chat.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            chat_id = req.route_params.get("chat_id")
            
            if not chat_id:
                return error_response("Chat ID is required", 400)
            
            # Parse request body
            try:
                body = req.get_json()
            except ValueError:
                return error_response("Invalid JSON body", 400)
            
            # Validate required fields
            errors = []
            if not body.get("role"):
                errors.append({"field": "role", "message": "Role is required"})
            if not body.get("content"):
                errors.append({"field": "content", "message": "Content is required"})
            
            if errors:
                return validation_error_response(errors)
            
            service = MessageService()
            message = await service.create_message(
                user_id,
                chat_id,
                body["role"],
                body["content"],
                body.get("search_modes"),
                body.get("sources")  # Sources for AI responses
            )
            
            return created_response(message)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Chat", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except ValueError as e:
            return validation_error_response(
                [{"field": "role", "message": str(e)}]
            )
        except Exception as e:
            logger.error(f"Error creating message: {str(e)}")
            return error_response("Failed to create message", 500)
    
    @app.route(
        route="chats/{chat_id}/messages/bulk",
        methods=["POST"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def bulk_create_messages(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/chats/{chat_id}/messages/bulk
        Add multiple messages to a chat at once.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            chat_id = req.route_params.get("chat_id")
            
            if not chat_id:
                return error_response("Chat ID is required", 400)
            
            # Parse request body
            try:
                body = req.get_json()
            except ValueError:
                return error_response("Invalid JSON body", 400)
            
            messages = body.get("messages", [])
            if not messages or not isinstance(messages, list):
                return validation_error_response(
                    [{"field": "messages", "message": "Messages array is required"}]
                )
            
            service = MessageService()
            created_messages = await service.bulk_create_messages(
                user_id,
                chat_id,
                messages
            )
            
            return created_response(created_messages)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Chat", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error bulk creating messages: {str(e)}")
            return error_response("Failed to create messages", 500)
    
    @app.route(
        route="chats/{chat_id}/messages/{message_id}",
        methods=["GET"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def get_message(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/chats/{chat_id}/messages/{message_id}
        Get a single message.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            chat_id = req.route_params.get("chat_id")
            message_id = req.route_params.get("message_id")
            
            if not chat_id:
                return error_response("Chat ID is required", 400)
            if not message_id:
                return error_response("Message ID is required", 400)
            
            service = MessageService()
            message = await service.get_message(user_id, chat_id, message_id)
            
            return success_response(message)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Message", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error getting message: {str(e)}")
            return error_response("Failed to get message", 500)
    
    @app.route(
        route="chats/{chat_id}/messages/{message_id}",
        methods=["DELETE"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def delete_message(req: func.HttpRequest) -> func.HttpResponse:
        """
        DELETE /api/chats/{chat_id}/messages/{message_id}
        Delete a message (chat owner only).
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            chat_id = req.route_params.get("chat_id")
            message_id = req.route_params.get("message_id")
            
            if not chat_id:
                return error_response("Chat ID is required", 400)
            if not message_id:
                return error_response("Message ID is required", 400)
            
            service = MessageService()
            await service.delete_message(user_id, chat_id, message_id)
            
            return no_content_response()
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Message", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error deleting message: {str(e)}")
            return error_response("Failed to delete message", 500)
