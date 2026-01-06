"""
HTTP route handlers for project sharing endpoints.
"""

import logging
import azure.functions as func
from shared.auth import get_user_from_token, UnauthorizedError
from shared.responses import (
    success_response, created_response, no_content_response,
    error_response, not_found_response, forbidden_response, validation_error_response
)
from shared.permissions import NotFoundError, ForbiddenError
from .service import ProjectShareService

logger = logging.getLogger(__name__)


def register_project_share_routes(app: func.FunctionApp):
    """Register all project sharing-related routes with the function app."""
    
    @app.route(
        route="projects/{project_id}/shares",
        methods=["GET"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def list_project_shares(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/projects/{project_id}/shares
        List all users a project is shared with (owner only).
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            
            service = ProjectShareService()
            shares = await service.list_shares(user_id, project_id)
            
            return success_response(shares)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Project", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error listing shares: {str(e)}")
            return error_response("Failed to list shares", 500)
    
    @app.route(
        route="projects/{project_id}/shares",
        methods=["POST"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def add_project_share(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/projects/{project_id}/shares
        Share a project with a user (owner only).
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            
            # Parse request body
            try:
                body = req.get_json()
            except ValueError:
                return error_response("Invalid JSON body", 400)
            
            # Validate required fields
            if not body.get("email"):
                return validation_error_response(
                    [{"field": "email", "message": "Email is required"}]
                )
            
            service = ProjectShareService()
            share = await service.add_share(
                user_id,
                project_id,
                body["email"],
                body.get("permission", "view")
            )
            
            return created_response(share)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Project", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except ValueError as e:
            return validation_error_response(
                [{"field": "email", "message": str(e)}]
            )
        except Exception as e:
            logger.error(f"Error adding share: {str(e)}")
            return error_response("Failed to add share", 500)
    
    @app.route(
        route="projects/{project_id}/shares/{share_id}",
        methods=["PUT"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def update_project_share(req: func.HttpRequest) -> func.HttpResponse:
        """
        PUT /api/projects/{project_id}/shares/{share_id}
        Update a share's permission (owner only).
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            share_id = req.route_params.get("share_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            if not share_id:
                return error_response("Share ID is required", 400)
            
            # Parse request body
            try:
                body = req.get_json()
            except ValueError:
                return error_response("Invalid JSON body", 400)
            
            # Validate required fields
            if not body.get("permission"):
                return validation_error_response(
                    [{"field": "permission", "message": "Permission is required"}]
                )
            
            service = ProjectShareService()
            share = await service.update_share(
                user_id,
                project_id,
                share_id,
                body["permission"]
            )
            
            return success_response(share)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Share", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except ValueError as e:
            return validation_error_response(
                [{"field": "permission", "message": str(e)}]
            )
        except Exception as e:
            logger.error(f"Error updating share: {str(e)}")
            return error_response("Failed to update share", 500)
    
    @app.route(
        route="projects/{project_id}/shares/{share_id}",
        methods=["DELETE"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def delete_project_share(req: func.HttpRequest) -> func.HttpResponse:
        """
        DELETE /api/projects/{project_id}/shares/{share_id}
        Remove a share (owner only).
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            share_id = req.route_params.get("share_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            if not share_id:
                return error_response("Share ID is required", 400)
            
            service = ProjectShareService()
            await service.delete_share(user_id, project_id, share_id)
            
            return no_content_response()
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Share", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error deleting share: {str(e)}")
            return error_response("Failed to delete share", 500)
