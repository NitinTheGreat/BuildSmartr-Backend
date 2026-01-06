"""
HTTP route handlers for chat endpoints.
"""

import logging
import azure.functions as func
from shared.auth import get_user_from_token, UnauthorizedError
from shared.responses import (
    success_response, created_response, no_content_response,
    error_response, not_found_response, forbidden_response, validation_error_response
)
from shared.permissions import NotFoundError, ForbiddenError
from .service import ChatService

logger = logging.getLogger(__name__)


def register_chat_routes(app: func.FunctionApp):
    """Register all chat-related routes with the function app."""
    
    @app.route(route="chats", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
    async def list_general_chats(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/chats
        List all general chats owned by the user.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            
            service = ChatService()
            chats = await service.list_general_chats(user_id)
            
            return success_response(chats)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except Exception as e:
            logger.error(f"Error listing general chats: {str(e)}")
            return error_response("Failed to list chats", 500)
    
    @app.route(
        route="projects/{project_id}/chats",
        methods=["GET"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def list_project_chats(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/projects/{project_id}/chats
        List all chats for a project.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            
            service = ChatService()
            chats = await service.list_project_chats(user_id, project_id)
            
            return success_response(chats)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Project", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error listing project chats: {str(e)}")
            return error_response("Failed to list chats", 500)
    
    @app.route(route="chats/{chat_id}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
    async def get_chat(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/chats/{chat_id}
        Get a single chat with messages.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            chat_id = req.route_params.get("chat_id")
            
            if not chat_id:
                return error_response("Chat ID is required", 400)
            
            # Check if messages should be included
            include_messages = req.params.get("include_messages", "true").lower() == "true"
            
            service = ChatService()
            chat = await service.get_chat(user_id, chat_id, include_messages)
            
            return success_response(chat)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Chat", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error getting chat: {str(e)}")
            return error_response("Failed to get chat", 500)
    
    @app.route(route="chats", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
    async def create_general_chat(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/chats
        Create a new general chat.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            
            # Parse request body (optional)
            title = None
            try:
                body = req.get_json()
                title = body.get("title")
            except ValueError:
                pass  # Body is optional
            
            service = ChatService()
            chat = await service.create_general_chat(user_id, title)
            
            return created_response(chat)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except Exception as e:
            logger.error(f"Error creating general chat: {str(e)}")
            return error_response("Failed to create chat", 500)
    
    @app.route(
        route="projects/{project_id}/chats",
        methods=["POST"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def create_project_chat(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/projects/{project_id}/chats
        Create a new project chat.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            
            # Parse request body (optional)
            title = None
            try:
                body = req.get_json()
                title = body.get("title")
            except ValueError:
                pass  # Body is optional
            
            service = ChatService()
            chat = await service.create_project_chat(user_id, project_id, title)
            
            return created_response(chat)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Project", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error creating project chat: {str(e)}")
            return error_response("Failed to create chat", 500)
    
    @app.route(route="chats/{chat_id}", methods=["PUT"], auth_level=func.AuthLevel.ANONYMOUS)
    async def update_chat(req: func.HttpRequest) -> func.HttpResponse:
        """
        PUT /api/chats/{chat_id}
        Update a chat's title (owner only).
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
            
            if not body.get("title"):
                return validation_error_response(
                    [{"field": "title", "message": "Title is required"}]
                )
            
            service = ChatService()
            chat = await service.update_chat(user_id, chat_id, body["title"])
            
            return success_response(chat)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Chat", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error updating chat: {str(e)}")
            return error_response("Failed to update chat", 500)
    
    @app.route(route="chats/{chat_id}", methods=["DELETE"], auth_level=func.AuthLevel.ANONYMOUS)
    async def delete_chat(req: func.HttpRequest) -> func.HttpResponse:
        """
        DELETE /api/chats/{chat_id}
        Delete a chat (owner only).
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            chat_id = req.route_params.get("chat_id")
            
            if not chat_id:
                return error_response("Chat ID is required", 400)
            
            service = ChatService()
            await service.delete_chat(user_id, chat_id)
            
            return no_content_response()
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Chat", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error deleting chat: {str(e)}")
            return error_response("Failed to delete chat", 500)
