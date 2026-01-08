# BuildSmartr Backend - Azure Functions

A Python-based Azure Functions backend for the BuildSmartr construction research assistant application. This backend handles all CRUD operations for projects, files, chats, and messages, with Supabase as the database and authentication provider.

## Technology Stack

- **Runtime:** Python 3.11+
- **Framework:** Azure Functions v4 (HTTP triggers)
- **Database:** Supabase (PostgreSQL)
- **Authentication:** Supabase Auth (JWT validation)
- **Storage:** Supabase Storage (for file uploads)
- **Environment:** Azure Functions consumption plan

## Project Structure

```
buildsmartr-backend/
├── function_app.py              # Main Azure Functions app entry
├── requirements.txt             # Python dependencies
├── host.json                    # Azure Functions host configuration
├── local.settings.json          # Local environment variables
├── README.md                    # This file
├── shared/
│   ├── __init__.py
│   ├── auth.py                  # JWT validation & user extraction
│   ├── supabase_client.py       # Supabase client singleton
│   ├── responses.py             # Standard HTTP response helpers
│   └── permissions.py           # Permission checking utilities
├── projects/
│   ├── __init__.py
│   ├── routes.py                # Project CRUD endpoints
│   └── service.py               # Business logic
├── project_files/
│   ├── __init__.py
│   ├── routes.py                # File CRUD endpoints
│   └── service.py               # Business logic with storage
├── project_shares/
│   ├── __init__.py
│   ├── routes.py                # Sharing endpoints
│   └── service.py               # Sharing business logic
├── chats/
│   ├── __init__.py
│   ├── routes.py                # Chat CRUD endpoints
│   └── service.py               # Business logic
├── messages/
│   ├── __init__.py
│   ├── routes.py                # Message CRUD endpoints
│   └── service.py               # Business logic
└── user_info/
    ├── __init__.py
    ├── routes.py                # User info endpoints
    └── service.py               # Business logic
```

## Setup

### Prerequisites

- Python 3.11+
- Azure Functions Core Tools v4
- Supabase project with the required database schema

### Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables in `local.settings.json`:
   ```json
   {
     "IsEncrypted": false,
     "Values": {
       "FUNCTIONS_WORKER_RUNTIME": "python",
       "AzureWebJobsStorage": "UseDevelopmentStorage=true",
       "SUPABASE_URL": "https://your-project.supabase.co",
       "SUPABASE_SERVICE_KEY": "your-service-role-key",
       "SUPABASE_JWT_SECRET": "your-jwt-secret",
       "SUPABASE_STORAGE_BUCKET": "project-files",
       "CORS_ORIGINS": "http://localhost:3000"
     }
   }
   ```

### Running Locally

```bash
func start
```

The API will be available at `http://localhost:7071/api/`

## API Endpoints

### Authentication

All endpoints (except `/api/health`) require a valid Supabase JWT token in the `Authorization: Bearer <token>` header.

### Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check (no auth required) |

### Projects

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/api/projects` | List all projects (owned + shared) | Authenticated |
| GET | `/api/projects/{id}` | Get single project with files, chats, shares | Owner or shared |
| POST | `/api/projects` | Create new project | Authenticated |
| PUT | `/api/projects/{id}` | Update project | Owner only |
| DELETE | `/api/projects/{id}` | Delete project | Owner only |

### Project Files

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/api/projects/{project_id}/files` | List project files | Owner or shared |
| POST | `/api/projects/{project_id}/files` | Upload file (multipart/form-data) | Owner or edit permission |
| DELETE | `/api/projects/{project_id}/files/{file_id}` | Delete file | Owner or edit permission |
| GET | `/api/projects/{project_id}/files/{file_id}/download` | Get signed download URL | Owner or shared |

### Project Sharing

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/api/projects/{project_id}/shares` | List shared users | Owner only |
| POST | `/api/projects/{project_id}/shares` | Add user to share | Owner only |
| PUT | `/api/projects/{project_id}/shares/{share_id}` | Update permission | Owner only |
| DELETE | `/api/projects/{project_id}/shares/{share_id}` | Remove share | Owner only |

### Chats

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/api/chats` | List all general chats | Owner only |
| GET | `/api/projects/{project_id}/chats` | List project chats | Owner or shared |
| GET | `/api/chats/{id}` | Get chat with messages | Owner or project shared |
| POST | `/api/chats` | Create general chat | Authenticated |
| POST | `/api/projects/{project_id}/chats` | Create project chat | Owner or edit permission |
| PUT | `/api/chats/{id}` | Update chat title | Owner only |
| DELETE | `/api/chats/{id}` | Delete chat | Owner only |

### Messages

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/api/chats/{chat_id}/messages` | List messages in chat | Chat owner or project shared |
| POST | `/api/chats/{chat_id}/messages` | Add message to chat | Chat owner or project shared (edit) |
| POST | `/api/chats/{chat_id}/messages/bulk` | Add multiple messages | Chat owner or project shared (edit) |
| GET | `/api/chats/{chat_id}/messages/{message_id}` | Get single message | Chat owner or project shared |
| DELETE | `/api/chats/{chat_id}/messages/{message_id}` | Delete message | Chat owner only |

### User Info

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/api/user/info` | Get current user info | Authenticated |
| PUT | `/api/user/info` | Update user info | Authenticated |
| POST | `/api/user/connect/gmail` | Connect Gmail account | Authenticated |
| POST | `/api/user/disconnect/gmail` | Disconnect Gmail | Authenticated |
| POST | `/api/user/connect/outlook` | Connect Outlook account | Authenticated |
| POST | `/api/user/disconnect/outlook` | Disconnect Outlook | Authenticated |

## Request/Response Examples

### Create Project

**Request:**
```json
POST /api/projects
{
  "name": "Office Building Project",
  "description": "A new office building in downtown",
  "company_address": "123 Main St, City, State",
  "tags": ["commercial", "office", "downtown"]
}
```

**Response:**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "Office Building Project",
  "description": "A new office building in downtown",
  "company_address": "123 Main St, City, State",
  "tags": ["commercial", "office", "downtown"],
  "is_owner": true,
  "permission": "owner",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Upload File

**Request:**
```
POST /api/projects/{project_id}/files
Content-Type: multipart/form-data

file: <binary>
category: construction
```

**Response:**
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "name": "floor_plan.pdf",
  "size": 1234567,
  "type": "application/pdf",
  "category": "construction",
  "url": "signed-url-here",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Add Share

**Request:**
```json
POST /api/projects/{project_id}/shares
{
  "email": "colleague@example.com",
  "permission": "edit"
}
```

**Response:**
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "shared_with_email": "colleague@example.com",
  "permission": "edit",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Create Message

**Request:**
```json
POST /api/chats/{chat_id}/messages
{
  "role": "user",
  "content": "What are the safety requirements for this project?",
  "search_modes": ["pdf", "web"]
}
```

**Response:**
```json
{
  "id": "uuid",
  "chat_id": "uuid",
  "role": "user",
  "content": "What are the safety requirements for this project?",
  "search_modes": ["pdf", "web"],
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Error Responses

All errors return a consistent JSON format:

```json
{
  "error": true,
  "message": "Error description",
  "errors": [  // Optional, for validation errors
    {"field": "name", "message": "Name is required"}
  ]
}
```

### Status Codes

- `200` - Success
- `201` - Created
- `204` - No Content (successful deletion)
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

## Deployment

### Deploy to Azure

1. Create an Azure Function App (Python 3.11, Consumption plan)
2. Configure Application Settings with the environment variables
3. Deploy using Azure Functions Core Tools:
    ```bash
    Compress-Archive * app.zip -Force
  ```bash

  ```bash
  az functionapp deployment source config-zip `
  --name pythonfunctions `
  --resource-group azurefunctions-buildsmartr `
  --src app.zip
  ```bash
  
   ```bash
   func azure functionapp publish <function-app-name>
   ```

Or use VS Code Azure Functions extension for deployment.

## Security

- All endpoints use JWT validation via Supabase Auth
- Service role key is used for database operations (bypasses RLS)
- File uploads are stored in Supabase Storage with signed URLs
- CORS is configured via environment variables
- Sensitive data (tokens) is never exposed in API responses

## License

MIT
