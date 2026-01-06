"""
BuildSmartr Backend - Minimal Azure Functions Application
"""

import azure.functions as func
import json

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return func.HttpResponse(
        json.dumps({"status": "healthy", "service": "BuildSmartr Backend"}),
        status_code=200,
        mimetype="application/json"
    )
