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

# Full implementation backed up - see original function_app.py for all endpoints
