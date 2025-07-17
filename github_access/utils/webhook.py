import hmac
import hashlib
import json

from fastapi import HTTPException, Request, status

from config import get_settings
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def verify_signature(request: Request, body: bytes):
    """
    Verifies the signature of the GitHub webhook request.
    This ensures that the request genuinely came from GitHub and hasn't been tampered with.
    """
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        logger.warning("X-Hub-Signature-256 header missing in webhook request.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Hub-Signature-256 header missing. Webhook not authenticated.",
        )

    try:
        secret_bytes = get_settings().WEBHOOK_SECRET.encode("utf-8")
        mac = hmac.new(secret_bytes, body, hashlib.sha256)
        expected_signature = "sha256=" + mac.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate webhook signature: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate signature for verification.",
        )

    if not hmac.compare_digest(expected_signature, signature_header):
        logger.warning("Webhook signature verification failed. Mismatch between expected and received signature.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature verification failed. Request not authorized.",
        )
    logger.debug("Webhook signature verified successfully.")


def parse_webhook_payload(body: bytes) -> Dict[str, Any]:
    """
    Parses the webhook payload from bytes to a JSON dictionary.
    """
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON payload received in webhook: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload. Could not parse webhook body."
        )


def get_event_type(request: Request) -> str:
    """
    Returns the event type of the GitHub webhook request (e.g., 'pull_request', 'push', 'ping').
    """
    event_type = request.headers.get("X-GitHub-Event")
    if not event_type:
        logger.warning("X-GitHub-Event header missing in webhook request.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-GitHub-Event header missing. Cannot determine event type.",
        )
    return event_type

