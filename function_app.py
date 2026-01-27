"""
BuildSmartr Backend - Azure Functions Application

A Python-based Azure Functions backend for the BuildSmartr construction 
research assistant application. Handles all CRUD operations for projects, 
files, chats, and messages with Supabase as the database and auth provider.
"""

import azure.functions as func
import datetime
import json
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the main Function App instance
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Import services
from projects.service import ProjectService
from project_files.service import ProjectFileService
from project_shares.service import ProjectShareService
from chats.service import ChatService
from messages.service import MessageService
from user_info.service import UserInfoService
from shared.auth import get_user_from_token, UnauthorizedError
from shared.responses import (
    success_response, created_response, no_content_response,
    error_response, not_found_response, forbidden_response, validation_error_response
)
from shared.permissions import NotFoundError, ForbiddenError

# =============================================================================
# Health Check Endpoint
# =============================================================================

@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint to verify the Azure Function is running."""
    logger.info("Health check endpoint called.")
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "service": "BuildSmartr Backend",
        "version": "1.0.0",
        "environment": os.environ.get("AZURE_FUNCTIONS_ENVIRONMENT", "Development")
    }
    
    return func.HttpResponse(
        json.dumps(health_status),
        status_code=200,
        mimetype="application/json"
    )

# =============================================================================
# Projects Endpoints
# =============================================================================

@app.route(route="projects", methods=["GET"])
async def list_projects(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/projects - List all projects (owned + shared)."""
    try:
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


@app.route(route="projects/{project_id}", methods=["GET"])
async def get_project(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/projects/{project_id} - Get single project."""
    try:
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


@app.route(route="projects", methods=["POST"])
async def create_project(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/projects - Create new project."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        
        try:
            body = req.get_json()
        except ValueError:
            return error_response("Invalid JSON body", 400)
        
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


@app.route(route="projects/{project_id}", methods=["PUT"])
async def update_project(req: func.HttpRequest) -> func.HttpResponse:
    """PUT /api/projects/{project_id} - Update project (owner only)."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        
        if not project_id:
            return error_response("Project ID is required", 400)
        
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


@app.route(route="projects/{project_id}", methods=["DELETE"])
async def delete_project(req: func.HttpRequest) -> func.HttpResponse:
    """DELETE /api/projects/{project_id} - Delete project (owner only)."""
    try:
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

# =============================================================================
# Project AI Integration Endpoints
# =============================================================================

@app.route(route="projects/{project_id}/index", methods=["POST"])
async def start_project_indexing(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/projects/{project_id}/index
    Start indexing a project with the AI backend.
    
    Requires Gmail to be connected.
    """
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        
        if not project_id:
            return error_response("Project ID is required", 400)
        
        service = ProjectService()
        result = await service.start_indexing(user_id, project_id)
        
        return success_response(result)
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except NotFoundError as e:
        return not_found_response("Project", str(e))
    except ForbiddenError as e:
        return forbidden_response(str(e))
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Error starting indexing: {str(e)}")
        return error_response(f"Failed to start indexing: {str(e)}", 500)


@app.route(route="projects/{project_id}/index/status", methods=["GET"])
async def get_project_indexing_status(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/projects/{project_id}/index/status
    Get the indexing status for a project.
    """
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        
        if not project_id:
            return error_response("Project ID is required", 400)
        
        service = ProjectService()
        result = await service.get_indexing_status(user_id, project_id)
        
        return success_response(result)
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except NotFoundError as e:
        return not_found_response("Project", str(e))
    except ForbiddenError as e:
        return forbidden_response(str(e))
    except Exception as e:
        logger.error(f"Error getting indexing status: {str(e)}")
        return error_response("Failed to get indexing status", 500)


@app.route(route="projects/{project_id}/index/cancel", methods=["POST"])
async def cancel_project_indexing(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/projects/{project_id}/index/cancel
    Cancel an in-progress indexing operation.
    """
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        
        if not project_id:
            return error_response("Project ID is required", 400)
        
        service = ProjectService()
        result = await service.cancel_indexing(user_id, project_id)
        
        return success_response(result)
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except NotFoundError as e:
        return not_found_response("Project", str(e))
    except ForbiddenError as e:
        return forbidden_response(str(e))
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Error cancelling indexing: {str(e)}")
        return error_response("Failed to cancel indexing", 500)


@app.route(route="projects/{project_id}/search", methods=["POST"])
async def search_project(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/projects/{project_id}/search
    Search a project using RAG.
    
    Request body:
    {
        "question": "What is the quoted price?",
        "top_k": 50  // optional
    }
    
    Returns: Non-streaming answer with sources.
    """
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        
        if not project_id:
            return error_response("Project ID is required", 400)
        
        try:
            body = req.get_json()
        except ValueError:
            return error_response("Invalid JSON body", 400)
        
        question = body.get("question")
        if not question:
            return validation_error_response(
                [{"field": "question", "message": "Question is required"}]
            )
        
        top_k = body.get("top_k")
        
        service = ProjectService()
        result = await service.search(user_id, project_id, question, top_k)
        
        return success_response(result)
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except NotFoundError as e:
        return not_found_response("Project", str(e))
    except ForbiddenError as e:
        return forbidden_response(str(e))
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Error searching project: {str(e)}")
        return error_response(f"Search failed: {str(e)}", 500)


@app.route(route="projects/{project_id}/search/stream", methods=["POST"])
async def search_project_stream(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/projects/{project_id}/search/stream
    Search a project with streaming SSE response.
    
    Request body:
    {
        "question": "What is the quoted price?",
        "top_k": 50  // optional
    }
    
    Returns: Server-Sent Events stream with answer chunks.
    """
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        
        if not project_id:
            return func.HttpResponse(
                'event: error\ndata: {"message": "Project ID is required"}\n\n',
                status_code=400,
                mimetype="text/event-stream"
            )
        
        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                'event: error\ndata: {"message": "Invalid JSON body"}\n\n',
                status_code=400,
                mimetype="text/event-stream"
            )
        
        question = body.get("question")
        if not question:
            return func.HttpResponse(
                'event: error\ndata: {"message": "Question is required"}\n\n',
                status_code=400,
                mimetype="text/event-stream"
            )
        
        top_k = body.get("top_k")
        
        # Collect SSE events (Azure Functions v1 doesn't support true streaming)
        service = ProjectService()
        sse_events = ""
        async for chunk in service.search_stream(user_id, project_id, question, top_k):
            sse_events += chunk
        
        return func.HttpResponse(
            sse_events,
            status_code=200,
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
        
    except UnauthorizedError as e:
        return func.HttpResponse(
            f'event: error\ndata: {{"message": "{str(e)}"}}\n\n',
            status_code=401,
            mimetype="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Error in streaming search: {str(e)}")
        return func.HttpResponse(
            f'event: error\ndata: {{"message": "Search failed: {str(e)}"}}\n\n',
            status_code=500,
            mimetype="text/event-stream"
        )


# =============================================================================
# Project Files Endpoints
# =============================================================================

@app.route(route="projects/{project_id}/files", methods=["GET"])
async def list_project_files(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/projects/{project_id}/files - List project files."""
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


@app.route(route="projects/{project_id}/files", methods=["POST"])
async def upload_project_file(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/projects/{project_id}/files - Upload file."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        
        if not project_id:
            return error_response("Project ID is required", 400)
        
        content_type = req.headers.get("Content-Type", "")
        
        if "multipart/form-data" in content_type:
            files = req.files
            if not files or "file" not in files:
                return validation_error_response(
                    [{"field": "file", "message": "File is required"}]
                )
            
            uploaded_file = files["file"]
            file_name = uploaded_file.filename
            file_data = uploaded_file.read()
            file_content_type = uploaded_file.content_type or "application/octet-stream"
            category = req.form.get("category", "other")
            
        elif "application/json" in content_type:
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
            return error_response("Content-Type must be multipart/form-data or application/json", 400)
        
        service = ProjectFileService()
        file_record = await service.upload_file(
            user_id, project_id, file_name, file_data, file_content_type, category
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


@app.route(route="projects/{project_id}/files/{file_id}", methods=["DELETE"])
async def delete_project_file(req: func.HttpRequest) -> func.HttpResponse:
    """DELETE /api/projects/{project_id}/files/{file_id} - Delete file."""
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


@app.route(route="projects/{project_id}/files/{file_id}/download", methods=["GET"])
async def get_file_download_url(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/projects/{project_id}/files/{file_id}/download - Get signed URL."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        file_id = req.route_params.get("file_id")
        
        if not project_id:
            return error_response("Project ID is required", 400)
        if not file_id:
            return error_response("File ID is required", 400)
        
        expires_in = int(req.params.get("expires_in", 3600))
        if expires_in < 60 or expires_in > 86400:
            expires_in = 3600
        
        service = ProjectFileService()
        download_url = await service.get_download_url(user_id, project_id, file_id, expires_in)
        
        return success_response({"download_url": download_url, "expires_in": expires_in})
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except NotFoundError as e:
        return not_found_response("File", str(e))
    except ForbiddenError as e:
        return forbidden_response(str(e))
    except Exception as e:
        logger.error(f"Error getting download URL: {str(e)}")
        return error_response("Failed to get download URL", 500)

# =============================================================================
# Project Shares Endpoints
# =============================================================================

@app.route(route="projects/{project_id}/shares", methods=["GET"])
async def list_project_shares(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/projects/{project_id}/shares - List shares (owner only)."""
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


@app.route(route="projects/{project_id}/shares", methods=["POST"])
async def add_project_share(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/projects/{project_id}/shares - Add share (owner only)."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        
        if not project_id:
            return error_response("Project ID is required", 400)
        
        try:
            body = req.get_json()
        except ValueError:
            return error_response("Invalid JSON body", 400)
        
        if not body.get("email"):
            return validation_error_response(
                [{"field": "email", "message": "Email is required"}]
            )
        
        service = ProjectShareService()
        share = await service.add_share(
            user_id, project_id, body["email"], body.get("permission", "view")
        )
        
        return created_response(share)
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except NotFoundError as e:
        return not_found_response("Project", str(e))
    except ForbiddenError as e:
        return forbidden_response(str(e))
    except ValueError as e:
        return validation_error_response([{"field": "email", "message": str(e)}])
    except Exception as e:
        logger.error(f"Error adding share: {str(e)}")
        return error_response("Failed to add share", 500)


@app.route(route="projects/{project_id}/shares/{share_id}", methods=["PUT"])
async def update_project_share(req: func.HttpRequest) -> func.HttpResponse:
    """PUT /api/projects/{project_id}/shares/{share_id} - Update share."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        share_id = req.route_params.get("share_id")
        
        if not project_id:
            return error_response("Project ID is required", 400)
        if not share_id:
            return error_response("Share ID is required", 400)
        
        try:
            body = req.get_json()
        except ValueError:
            return error_response("Invalid JSON body", 400)
        
        if not body.get("permission"):
            return validation_error_response(
                [{"field": "permission", "message": "Permission is required"}]
            )
        
        service = ProjectShareService()
        share = await service.update_share(user_id, project_id, share_id, body["permission"])
        
        return success_response(share)
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except NotFoundError as e:
        return not_found_response("Share", str(e))
    except ForbiddenError as e:
        return forbidden_response(str(e))
    except ValueError as e:
        return validation_error_response([{"field": "permission", "message": str(e)}])
    except Exception as e:
        logger.error(f"Error updating share: {str(e)}")
        return error_response("Failed to update share", 500)


@app.route(route="projects/{project_id}/shares/{share_id}", methods=["DELETE"])
async def delete_project_share(req: func.HttpRequest) -> func.HttpResponse:
    """DELETE /api/projects/{project_id}/shares/{share_id} - Remove share."""
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

# =============================================================================
# Chats Endpoints
# =============================================================================

@app.route(route="chats", methods=["GET"])
async def list_general_chats(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/chats - List general chats."""
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


@app.route(route="projects/{project_id}/chats", methods=["GET"])
async def list_project_chats(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/projects/{project_id}/chats - List project chats."""
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


@app.route(route="chats/{chat_id}", methods=["GET"])
async def get_chat(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/chats/{chat_id} - Get chat with messages."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        chat_id = req.route_params.get("chat_id")
        
        if not chat_id:
            return error_response("Chat ID is required", 400)
        
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


@app.route(route="chats", methods=["POST"])
async def create_general_chat(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/chats - Create general chat."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        
        title = None
        try:
            body = req.get_json()
            title = body.get("title")
        except ValueError:
            pass
        
        service = ChatService()
        chat = await service.create_general_chat(user_id, title)
        
        return created_response(chat)
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except Exception as e:
        logger.error(f"Error creating general chat: {str(e)}")
        return error_response("Failed to create chat", 500)


@app.route(route="projects/{project_id}/chats", methods=["POST"])
async def create_project_chat(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/projects/{project_id}/chats - Create project chat."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        project_id = req.route_params.get("project_id")
        
        if not project_id:
            return error_response("Project ID is required", 400)
        
        title = None
        try:
            body = req.get_json()
            title = body.get("title")
        except ValueError:
            pass
        
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


@app.route(route="chats/{chat_id}", methods=["PUT"])
async def update_chat(req: func.HttpRequest) -> func.HttpResponse:
    """PUT /api/chats/{chat_id} - Update chat title."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        chat_id = req.route_params.get("chat_id")
        
        if not chat_id:
            return error_response("Chat ID is required", 400)
        
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


@app.route(route="chats/{chat_id}", methods=["DELETE"])
async def delete_chat(req: func.HttpRequest) -> func.HttpResponse:
    """DELETE /api/chats/{chat_id} - Delete chat."""
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

# =============================================================================
# Messages Endpoints
# =============================================================================

@app.route(route="chats/{chat_id}/messages", methods=["GET"])
async def list_messages(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/chats/{chat_id}/messages - List messages."""
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


@app.route(route="chats/{chat_id}/messages", methods=["POST"])
async def create_message(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/chats/{chat_id}/messages - Add message."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        chat_id = req.route_params.get("chat_id")
        
        if not chat_id:
            return error_response("Chat ID is required", 400)
        
        try:
            body = req.get_json()
        except ValueError:
            return error_response("Invalid JSON body", 400)
        
        errors = []
        if not body.get("role"):
            errors.append({"field": "role", "message": "Role is required"})
        if not body.get("content"):
            errors.append({"field": "content", "message": "Content is required"})
        
        if errors:
            return validation_error_response(errors)
        
        service = MessageService()
        message = await service.create_message(
            user_id, chat_id, body["role"], body["content"], body.get("search_modes")
        )
        
        return created_response(message)
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except NotFoundError as e:
        return not_found_response("Chat", str(e))
    except ForbiddenError as e:
        return forbidden_response(str(e))
    except ValueError as e:
        return validation_error_response([{"field": "role", "message": str(e)}])
    except Exception as e:
        logger.error(f"Error creating message: {str(e)}")
        return error_response("Failed to create message", 500)


@app.route(route="chats/{chat_id}/messages/bulk", methods=["POST"])
async def bulk_create_messages(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/chats/{chat_id}/messages/bulk - Add multiple messages."""
    try:
        user = get_user_from_token(req)
        user_id = user["id"]
        chat_id = req.route_params.get("chat_id")
        
        if not chat_id:
            return error_response("Chat ID is required", 400)
        
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
        created_messages = await service.bulk_create_messages(user_id, chat_id, messages)
        
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


@app.route(route="chats/{chat_id}/messages/{message_id}", methods=["GET"])
async def get_message(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/chats/{chat_id}/messages/{message_id} - Get message."""
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


@app.route(route="chats/{chat_id}/messages/{message_id}", methods=["DELETE"])
async def delete_message(req: func.HttpRequest) -> func.HttpResponse:
    """DELETE /api/chats/{chat_id}/messages/{message_id} - Delete message."""
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

# =============================================================================
# User Info Endpoints
# =============================================================================

@app.route(route="user/info", methods=["GET"])
async def get_user_info(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/user/info - Get current user info."""
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


@app.route(route="user/info", methods=["PUT"])
async def update_user_info(req: func.HttpRequest) -> func.HttpResponse:
    """PUT /api/user/info - Update current user info."""
    try:
        user = get_user_from_token(req)
        user_email = user.get("email")
        
        if not user_email:
            return error_response("User email not found in token", 400)
        
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


@app.route(route="user/connect/gmail", methods=["POST"])
async def connect_gmail(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/user/connect/gmail - Connect Gmail account."""
    try:
        user = get_user_from_token(req)
        user_email = user.get("email")
        
        if not user_email:
            return error_response("User email not found in token", 400)
        
        try:
            body = req.get_json()
        except ValueError:
            return error_response("Invalid JSON body", 400)
        
        errors = []
        if not body.get("gmail_email"):
            errors.append({"field": "gmail_email", "message": "Gmail email is required"})
        if not body.get("gmail_token"):
            errors.append({"field": "gmail_token", "message": "Gmail token is required"})
        
        if errors:
            return validation_error_response(errors)
        
        service = UserInfoService()
        user_info = await service.connect_gmail(
            user_email, body["gmail_email"], body["gmail_token"]
        )
        
        return success_response(user_info)
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except Exception as e:
        logger.error(f"Error connecting Gmail: {str(e)}")
        return error_response("Failed to connect Gmail", 500)


@app.route(route="user/disconnect/gmail", methods=["POST"])
async def disconnect_gmail(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/user/disconnect/gmail - Disconnect Gmail."""
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


@app.route(route="user/connect/outlook", methods=["POST"])
async def connect_outlook(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/user/connect/outlook - Connect Outlook account."""
    try:
        user = get_user_from_token(req)
        user_email = user.get("email")
        
        if not user_email:
            return error_response("User email not found in token", 400)
        
        try:
            body = req.get_json()
        except ValueError:
            return error_response("Invalid JSON body", 400)
        
        errors = []
        if not body.get("outlook_email"):
            errors.append({"field": "outlook_email", "message": "Outlook email is required"})
        if not body.get("outlook_token"):
            errors.append({"field": "outlook_token", "message": "Outlook token is required"})
        
        if errors:
            return validation_error_response(errors)
        
        service = UserInfoService()
        user_info = await service.connect_outlook(
            user_email, body["outlook_email"], body["outlook_token"]
        )
        
        return success_response(user_info)
        
    except UnauthorizedError as e:
        return error_response(str(e), 401)
    except Exception as e:
        logger.error(f"Error connecting Outlook: {str(e)}")
        return error_response("Failed to connect Outlook", 500)


@app.route(route="user/disconnect/outlook", methods=["POST"])
async def disconnect_outlook(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/user/disconnect/outlook - Disconnect Outlook."""
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


logger.info("BuildSmartr Backend Azure Functions initialized successfully.")