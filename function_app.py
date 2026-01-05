import azure.functions as func
import datetime
import json
import logging

app = func.FunctionApp()


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint to verify the Azure Function is running.
    Returns status, timestamp, and version information.
    """
    logging.info("Health check endpoint called.")
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "service": "Buildsmartr Backend",
        "version": "1.0.0"
    }
    
    return func.HttpResponse(
        json.dumps(health_status),
        status_code=200,
        mimetype="application/json"
    )