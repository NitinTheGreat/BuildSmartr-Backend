"""
HTTP route handlers for project endpoints.
"""

import json
import logging
import azure.functions as func
from shared.auth import require_auth, get_user_id_from_request, UnauthorizedError
from shared.responses import (
    success_response, created_response, no_content_response,
    error_response, not_found_response, forbidden_response, validation_error_response
)
from shared.permissions import NotFoundError, ForbiddenError
from .service import ProjectService

logger = logging.getLogger(__name__)


def register_project_routes(app: func.FunctionApp):
    """Register all project-related routes with the function app."""
    
    @app.route(route="projects", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
    async def list_projects(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/projects
        List all projects the user has access to (owned + shared).
        """
        try:
            from shared.auth import get_user_from_token
            user = get_user_from_token(req)
            user_id = user["id"]
            
            service = ProjectService()
            projects = await service.list_projects(user_id)
            
            return success_response(projects)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except Exception as e:
            logger.error(f"Error listing projects: {str(e)}")
            return error_response("Failed to list projects", 500)
    
    @app.route(route="projects/{project_id}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
    async def get_project(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/projects/{project_id}
        Get a single project with files, chats, and shares.
        """
        try:
            from shared.auth import get_user_from_token
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            
            service = ProjectService()
            project = await service.get_project(user_id, project_id)
            
            return success_response(project)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Project", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error getting project: {str(e)}")
            return error_response("Failed to get project", 500)
    
    @app.route(route="projects", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
    async def create_project(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/projects
        Create a new project.
        """
        try:
            from shared.auth import get_user_from_token
            user = get_user_from_token(req)
            user_id = user["id"]
            
            # Parse request body
            try:
                body = req.get_json()
            except ValueError:
                return error_response("Invalid JSON body", 400)
            
            # Validate required fields
            if not body.get("name"):
                return validation_error_response(
                    [{"field": "name", "message": "Name is required"}]
                )
            
            service = ProjectService()
            project = await service.create_project(user_id, body)
            
            return created_response(project)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except Exception as e:
            logger.error(f"Error creating project: {str(e)}")
            return error_response("Failed to create project", 500)
    
    @app.route(route="projects/{project_id}", methods=["PUT"], auth_level=func.AuthLevel.ANONYMOUS)
    async def update_project(req: func.HttpRequest) -> func.HttpResponse:
        """
        PUT /api/projects/{project_id}
        Update an existing project (owner only).
        """
        try:
            from shared.auth import get_user_from_token
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
            
            service = ProjectService()
            project = await service.update_project(user_id, project_id, body)
            
            return success_response(project)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Project", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error updating project: {str(e)}")
            return error_response("Failed to update project", 500)
    
    @app.route(route="projects/{project_id}", methods=["DELETE"], auth_level=func.AuthLevel.ANONYMOUS)
    async def delete_project(req: func.HttpRequest) -> func.HttpResponse:
        """
        DELETE /api/projects/{project_id}
        Delete a project (owner only).
        """
        try:
            from shared.auth import get_user_from_token
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            
            service = ProjectService()
            await service.delete_project(user_id, project_id)
            
            return no_content_response()
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Project", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error deleting project: {str(e)}")
            return error_response("Failed to delete project", 500)
