"""
HTTP route handlers for project file endpoints.
"""

import logging
import azure.functions as func
from shared.auth import get_user_from_token, UnauthorizedError
from shared.responses import (
    success_response, created_response, no_content_response,
    error_response, not_found_response, forbidden_response, validation_error_response
)
from shared.permissions import NotFoundError, ForbiddenError
from .service import ProjectFileService

logger = logging.getLogger(__name__)


def register_project_file_routes(app: func.FunctionApp):
    """Register all project file-related routes with the function app."""
    
    @app.route(
        route="projects/{project_id}/files",
        methods=["GET"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def list_project_files(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/projects/{project_id}/files
        List all files in a project.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            
            service = ProjectFileService()
            files = await service.list_files(user_id, project_id)
            
            return success_response(files)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Project", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error listing project files: {str(e)}")
            return error_response("Failed to list files", 500)
    
    @app.route(
        route="projects/{project_id}/files",
        methods=["POST"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def upload_project_file(req: func.HttpRequest) -> func.HttpResponse:
        """
        POST /api/projects/{project_id}/files
        Upload a file to a project (multipart/form-data).
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            
            # Parse multipart form data
            content_type = req.headers.get("Content-Type", "")
            
            if "multipart/form-data" in content_type:
                # Handle multipart upload
                files = req.files
                
                if not files or "file" not in files:
                    return validation_error_response(
                        [{"field": "file", "message": "File is required"}]
                    )
                
                uploaded_file = files["file"]
                file_name = uploaded_file.filename
                file_data = uploaded_file.read()
                file_content_type = uploaded_file.content_type or "application/octet-stream"
                
                # Get category from form data
                category = req.form.get("category", "other")
                
            elif "application/json" in content_type:
                # Handle JSON with base64 encoded file
                try:
                    body = req.get_json()
                except ValueError:
                    return error_response("Invalid JSON body", 400)
                
                import base64
                
                if not body.get("file_data") or not body.get("file_name"):
                    return validation_error_response(
                        [{"field": "file_data", "message": "file_data and file_name are required"}]
                    )
                
                file_name = body["file_name"]
                file_data = base64.b64decode(body["file_data"])
                file_content_type = body.get("content_type", "application/octet-stream")
                category = body.get("category", "other")
                
            else:
                return error_response(
                    "Content-Type must be multipart/form-data or application/json", 
                    400
                )
            
            service = ProjectFileService()
            file_record = await service.upload_file(
                user_id,
                project_id,
                file_name,
                file_data,
                file_content_type,
                category
            )
            
            return created_response(file_record)
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("Project", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            return error_response(f"Failed to upload file: {str(e)}", 500)
    
    @app.route(
        route="projects/{project_id}/files/{file_id}",
        methods=["DELETE"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def delete_project_file(req: func.HttpRequest) -> func.HttpResponse:
        """
        DELETE /api/projects/{project_id}/files/{file_id}
        Delete a file from a project.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            file_id = req.route_params.get("file_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            if not file_id:
                return error_response("File ID is required", 400)
            
            service = ProjectFileService()
            await service.delete_file(user_id, project_id, file_id)
            
            return no_content_response()
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("File", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return error_response("Failed to delete file", 500)
    
    @app.route(
        route="projects/{project_id}/files/{file_id}/download",
        methods=["GET"],
        auth_level=func.AuthLevel.ANONYMOUS
    )
    async def get_file_download_url(req: func.HttpRequest) -> func.HttpResponse:
        """
        GET /api/projects/{project_id}/files/{file_id}/download
        Get a signed download URL for a file.
        """
        try:
            user = get_user_from_token(req)
            user_id = user["id"]
            project_id = req.route_params.get("project_id")
            file_id = req.route_params.get("file_id")
            
            if not project_id:
                return error_response("Project ID is required", 400)
            if not file_id:
                return error_response("File ID is required", 400)
            
            # Optional: custom expiry time
            expires_in = int(req.params.get("expires_in", 3600))
            if expires_in < 60 or expires_in > 86400:  # 1 minute to 24 hours
                expires_in = 3600
            
            service = ProjectFileService()
            download_url = await service.get_download_url(
                user_id, project_id, file_id, expires_in
            )
            
            return success_response({
                "download_url": download_url,
                "expires_in": expires_in
            })
            
        except UnauthorizedError as e:
            return error_response(str(e), 401)
        except NotFoundError as e:
            return not_found_response("File", str(e))
        except ForbiddenError as e:
            return forbidden_response(str(e))
        except Exception as e:
            logger.error(f"Error getting download URL: {str(e)}")
            return error_response("Failed to get download URL", 500)
