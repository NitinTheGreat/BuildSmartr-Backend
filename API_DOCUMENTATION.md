# BuildSmartr Backend - API Documentation

## Overview

BuildSmartr Backend is the **database backend** for the IIVY construction research platform. It handles all CRUD operations, user management, and acts as the gateway to the AI backend.

### Responsibilities

- **User Authentication** - Validates Supabase JWT tokens
- **Project Management** - CRUD for projects, files, shares
- **Chat & Messages** - Store conversation history
- **User Info** - Gmail/Outlook token storage, company info
- **AI Gateway** - Proxies requests to AI backend (the frontend never calls AI backend directly)

### Architecture

```
┌──────────────┐         ┌─────────────────────┐         ┌──────────────┐
│   Frontend   │ ──────► │  BuildSmartr-Backend │ ──────► │  AI Backend  │
│   (Next.js)  │         │   (This Backend)     │         │  (Pinecone)  │
└──────────────┘         └─────────────────────┘         └──────────────┘
                                   │
                                   ▼
                         ┌─────────────────────┐
                         │      Supabase       │
                         │  (Database/Storage) │
                         └─────────────────────┘
```

---

## Authentication

All endpoints (except `/api/health`) require a valid Supabase JWT token.

**Header:**
```
Authorization: Bearer <supabase_access_token>
```

**Error Response (401):**
```json
{
  "error": true,
  "message": "Missing or invalid Authorization header"
}
```

---

## Base URL

- **Local Development:** `http://localhost:7071`
- **Production:** Your Azure Functions URL

---

## Endpoints

### Health Check

#### `GET /api/health`

Check if the backend is running.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "service": "BuildSmartr Backend",
  "version": "1.0.0",
  "environment": "Development"
}
```

---

## Projects

### List Projects

#### `GET /api/projects`

List all projects the user has access to (owned + shared).

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Microsoft Azure",
    "description": "Cloud infrastructure project",
    "company_address": "123 Main St",
    "tags": ["cloud", "infrastructure"],
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z",
    "ai_project_id": "microsoft_azure_a1b2c3d4",
    "indexing_status": "completed",
    "is_owner": true,
    "permission": "owner"
  }
]
```

---

### Get Project

#### `GET /api/projects/{project_id}`

Get a single project with files, chats, and shares.

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Microsoft Azure",
  "description": "Cloud infrastructure project",
  "company_address": "123 Main St",
  "tags": ["cloud", "infrastructure"],
  "ai_project_id": "microsoft_azure_a1b2c3d4",
  "indexing_status": "completed",
  "is_owner": true,
  "permission": "owner",
  "files": [
    {
      "id": "file-uuid",
      "name": "proposal.pdf",
      "size": 1024000,
      "type": "application/pdf",
      "category": "documents",
      "url": "https://signed-url..."
    }
  ],
  "chats": [
    {
      "id": "chat-uuid",
      "title": "Initial Discussion",
      "message_count": 5,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "shares": [
    {
      "id": "share-uuid",
      "shared_with_email": "colleague@company.com",
      "permission": "view"
    }
  ]
}
```

---

### Create Project

#### `POST /api/projects`

Create a new project.

**Request Body:**
```json
{
  "name": "Microsoft Azure",
  "description": "Cloud infrastructure project",
  "company_address": "123 Main St",
  "tags": ["cloud", "infrastructure"]
}
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Microsoft Azure",
  "description": "Cloud infrastructure project",
  "indexing_status": "not_started",
  "is_owner": true,
  "permission": "owner"
}
```

---

### Update Project

#### `PUT /api/projects/{project_id}`

Update project details (owner only).

**Request Body:**
```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "tags": ["new", "tags"]
}
```

---

### Delete Project

#### `DELETE /api/projects/{project_id}`

Delete a project (owner only). Also deletes vectors from AI backend.

**Response:** `204 No Content`

---

## AI Integration (Project Indexing & Search)

### Start Indexing

#### `POST /api/projects/{project_id}/index`

Start indexing a project's emails with the AI backend.

**Prerequisites:**
- User must have Gmail connected (see `/api/user/connect/gmail`)

**Response:**
```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "ai_project_id": "microsoft_azure_a1b2c3d4",
  "status": "completed",
  "stats": {
    "thread_count": 45,
    "message_count": 120,
    "pdf_count": 8,
    "indexed_at": "2024-01-15T10:30:00Z"
  },
  "vectorization": {
    "namespace": "microsoft_azure_a1b2c3d4",
    "vectors_created": 450,
    "message_chunks": 380,
    "attachment_chunks": 70
  }
}
```

**Error Responses:**
- `400` - Gmail not connected
- `400` - Project is already being indexed

---

### Get Indexing Status

#### `GET /api/projects/{project_id}/index/status`

Get the current indexing progress.

**Response:**
```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "ai_project_id": "microsoft_azure_a1b2c3d4",
  "status": "indexing",
  "percent": 45,
  "phase": "Processing PDFs",
  "step": "Extracting information from documents...",
  "details": {
    "thread_count": 30,
    "message_count": 85,
    "pdf_count": 3
  }
}
```

**Status Values:**
| Status | Description |
|--------|-------------|
| `not_started` | Never indexed |
| `indexing` | Currently indexing |
| `completed` | Successfully indexed |
| `failed` | Indexing failed |
| `cancelled` | User cancelled |

---

### Cancel Indexing

#### `POST /api/projects/{project_id}/index/cancel`

Cancel an in-progress indexing operation.

**Response:**
```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "ai_project_id": "microsoft_azure_a1b2c3d4",
  "status": "cancel_requested",
  "message": "Cancellation requested. The indexing will stop shortly."
}
```

---

### Search Project

#### `POST /api/projects/{project_id}/search`

Search a project using RAG (non-streaming).

**Request Body:**
```json
{
  "question": "What is the quoted price for the project?",
  "top_k": 50
}
```

**Response:**
```json
{
  "project_id": "microsoft_azure_a1b2c3d4",
  "question": "What is the quoted price?",
  "answer": "Based on the emails, the total quoted price is $45,000...",
  "sources": [
    {
      "chunk_id": "msg_abc123_chunk_0",
      "chunk_type": "email_body",
      "text": "The total quote for the project is $45,000...",
      "score": 0.92,
      "metadata": {
        "sender_name": "Bob Smith",
        "sender_email": "bob@contractor.com",
        "timestamp": "2024-01-15T14:30:00Z"
      }
    }
  ],
  "chunks_retrieved": 50,
  "search_time_ms": 120,
  "llm_time_ms": 2500,
  "total_time_ms": 2620
}
```

---

### Search Project (Streaming)

#### `POST /api/projects/{project_id}/search/stream`

Search with Server-Sent Events streaming.

**Request Body:**
```json
{
  "question": "What is the quoted price?",
  "top_k": 50
}
```

**Response:** `text/event-stream`

**Events:**
```
event: thinking
data: {"status": "🔍 Searching project data..."}

event: thinking
data: {"status": "🧠 Understanding your question..."}

event: sources
data: {"sources": [...], "chunks_retrieved": 50, "search_time_ms": 120}

event: chunk
data: {"text": "Based on "}

event: chunk
data: {"text": "the emails, "}

event: chunk
data: {"text": "the total price is $45,000."}

event: done
data: {"search_time_ms": 120, "llm_time_ms": 2500, "total_time_ms": 2620}
```

---

## Project Files

### List Files

#### `GET /api/projects/{project_id}/files`

List all files in a project.

---

### Upload File

#### `POST /api/projects/{project_id}/files`

Upload a file to the project.

**Content-Type:** `multipart/form-data`

**Form Fields:**
- `file` - The file to upload
- `category` - File category (optional, default: "other")

**Or JSON:**
```json
{
  "file_data": "base64_encoded_data",
  "file_name": "document.pdf",
  "content_type": "application/pdf",
  "category": "documents"
}
```

---

### Delete File

#### `DELETE /api/projects/{project_id}/files/{file_id}`

Delete a file from the project.

---

### Get Download URL

#### `GET /api/projects/{project_id}/files/{file_id}/download`

Get a signed URL to download a file.

**Query Parameters:**
- `expires_in` - URL validity in seconds (default: 3600, max: 86400)

**Response:**
```json
{
  "download_url": "https://supabase.storage/...",
  "expires_in": 3600
}
```

---

## Project Shares

### List Shares

#### `GET /api/projects/{project_id}/shares`

List all shares for a project (owner only).

---

### Add Share

#### `POST /api/projects/{project_id}/shares`

Share a project with another user.

**Request Body:**
```json
{
  "email": "colleague@company.com",
  "permission": "view"
}
```

**Permission Values:** `view`, `edit`

---

### Update Share

#### `PUT /api/projects/{project_id}/shares/{share_id}`

Update a share's permission.

---

### Remove Share

#### `DELETE /api/projects/{project_id}/shares/{share_id}`

Remove a user's access to the project.

---

## Chats

### List General Chats

#### `GET /api/chats`

List all general (non-project) chats for the user.

---

### List Project Chats

#### `GET /api/projects/{project_id}/chats`

List all chats for a specific project.

---

### Get Chat

#### `GET /api/chats/{chat_id}`

Get a chat with messages.

**Query Parameters:**
- `include_messages` - Include messages (default: true)

---

### Create General Chat

#### `POST /api/chats`

Create a new general chat.

**Request Body:**
```json
{
  "title": "Research Discussion"
}
```

---

### Create Project Chat

#### `POST /api/projects/{project_id}/chats`

Create a new chat in a project.

---

### Update Chat

#### `PUT /api/chats/{chat_id}`

Update chat title.

---

### Delete Chat

#### `DELETE /api/chats/{chat_id}`

Delete a chat and all its messages.

---

## Messages

### List Messages

#### `GET /api/chats/{chat_id}/messages`

List all messages in a chat.

---

### Create Message

#### `POST /api/chats/{chat_id}/messages`

Add a message to a chat.

**Request Body:**
```json
{
  "role": "user",
  "content": "What is the project timeline?",
  "search_modes": ["email", "web"]
}
```

**Role Values:** `user`, `assistant`, `system`

---

### Bulk Create Messages

#### `POST /api/chats/{chat_id}/messages/bulk`

Add multiple messages at once.

**Request Body:**
```json
{
  "messages": [
    {"role": "user", "content": "Question"},
    {"role": "assistant", "content": "Answer"}
  ]
}
```

---

### Get Message

#### `GET /api/chats/{chat_id}/messages/{message_id}`

Get a specific message.

---

### Delete Message

#### `DELETE /api/chats/{chat_id}/messages/{message_id}`

Delete a message.

---

## User Info

### Get User Info

#### `GET /api/user/info`

Get current user's profile and connection status.

**Response:**
```json
{
  "email": "user@example.com",
  "user_company_info": "Construction Corp",
  "gmail_email": "user@gmail.com",
  "gmail_connected": true,
  "outlook_email": null,
  "outlook_connected": false,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### Update User Info

#### `PUT /api/user/info`

Update user profile.

**Request Body:**
```json
{
  "user_company_info": "Updated Company Name"
}
```

---

### Connect Gmail

#### `POST /api/user/connect/gmail`

Connect a Gmail account.

**Request Body:**
```json
{
  "gmail_email": "user@gmail.com",
  "gmail_token": {
    "access_token": "ya29...",
    "refresh_token": "1//04...",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "xxx.apps.googleusercontent.com",
    "client_secret": "GOCSPX-xxx"
  }
}
```

---

### Disconnect Gmail

#### `POST /api/user/disconnect/gmail`

Disconnect Gmail account.

---

### Connect Outlook

#### `POST /api/user/connect/outlook`

Connect an Outlook account.

---

### Disconnect Outlook

#### `POST /api/user/disconnect/outlook`

Disconnect Outlook account.

---

## Error Responses

All errors follow this format:

```json
{
  "error": true,
  "message": "Error description",
  "errors": [
    {"field": "name", "message": "Name is required"}
  ]
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created |
| `204` | No Content (successful delete) |
| `400` | Bad Request (validation error) |
| `401` | Unauthorized (missing/invalid token) |
| `403` | Forbidden (no permission) |
| `404` | Not Found |
| `422` | Validation Error |
| `500` | Internal Server Error |
| `503` | Service Unavailable |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `SUPABASE_STORAGE_BUCKET` | No | Storage bucket name (default: "project-files") |
| `AI_BACKEND_URL` | Yes | URL of the AI backend |

---

## Database Schema

### `projects` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | uuid | Primary key |
| `user_id` | uuid | Owner's user ID |
| `name` | text | Project name |
| `description` | text | Description |
| `company_address` | text | Company address |
| `tags` | text | Tags (stored as text) |
| `ai_project_id` | text | AI backend project ID (Pinecone namespace) |
| `indexing_status` | text | Current indexing status |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

### `user_info` Table

| Column | Type | Description |
|--------|------|-------------|
| `email` | text | Primary key (user's email) |
| `user_company_info` | text | Company information |
| `gmail_email` | text | Connected Gmail address |
| `gmail_token` | jsonb | Gmail OAuth credentials |
| `outlook_email` | text | Connected Outlook address |
| `outlook_token` | jsonb | Outlook OAuth credentials |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

---

## File Structure

```
BuildSmartr-Backend/
├── function_app.py          # Main Azure Functions app with all routes
├── projects/
│   ├── service.py           # Project business logic + AI integration
│   └── routes.py            # Route definitions (unused, in function_app.py)
├── project_files/
│   └── service.py           # File upload/download logic
├── project_shares/
│   └── service.py           # Sharing logic
├── chats/
│   └── service.py           # Chat management
├── messages/
│   └── service.py           # Message management
├── user_info/
│   └── service.py           # User profile & email connections
├── shared/
│   ├── ai_client.py         # HTTP client for AI backend
│   ├── auth.py              # JWT validation
│   ├── permissions.py       # Access control
│   ├── responses.py         # HTTP response helpers
│   └── supabase_client.py   # Supabase client singleton
├── local.settings.json      # Local environment variables
├── requirements.txt         # Python dependencies
└── SUPABASE_MIGRATION.sql   # Database migration script
```

---

## Changelog

### v2.0.0 - AI Integration
- Added AI integration endpoints for indexing and search
- Added `ai_project_id` and `indexing_status` to projects
- Created `ai_client.py` for AI backend communication
- Updated `delete_project` to clean up AI vectors
