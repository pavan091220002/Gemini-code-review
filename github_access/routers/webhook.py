from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from github_access.utils.webhook import verify_signature, parse_webhook_payload, get_event_type
from github_access.models.pull_request import PullRequest
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhook"])

@router.get("/demo")
async def demo() -> Dict[str, str]:
    """
    Test endpoint to verify server is running.
    """
    current_time = datetime.now().strftime('%I:%M %p IST on %B %d, %Y')
    return {"message": f"Code Analysis Pipeline is running at {current_time}"}

@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, str]:
    """
    Receives GitHub webhook events.
    Verifies the signature.
    Parses the payload.
    Identifies the event type.
    Runs the code review with static analysis if the payload action is 'opened' or 'synchronize' for a pull request.
    """
    current_time = datetime.now().strftime('%I:%M %p IST on %B %d, %Y')
    try:
        body = await request.body()
        await verify_signature(request, body)
        payload = parse_webhook_payload(body)
        event_type = get_event_type(request)

        if event_type == "pull_request":
            action = payload.get("action")
            pull_request = PullRequest.from_github_event(payload)
            
            if action in ["opened", "synchronize"]:
                logger.info(f"Executing Gemini review on pull request: {pull_request.repository['full_name']}#{pull_request.number} (action: {action}) at {current_time}")
                # Get the commit SHA from the payload
                # For 'synchronize', it should be the latest commit SHA of the PR head
                commit_sha = payload.get("after") or payload["pull_request"]["head"]["sha"]
                
                if commit_sha:
                    logger.info(f"Executing review for files under commit: {commit_sha}")
                
                background_tasks.add_task(pull_request.gemini_review_request, commit_ref=commit_sha, project_wide=False, static_analysis_enabled=True)
                return {"message": f"Pull request review initiated for {pull_request.repository['full_name']}#{pull_request.number} at {current_time}"}
            else:
                logger.info(f"Action '{action}' not handled for pull request at {current_time}")
                return {"message": f"Action '{action}' received but not handled for pull request at {current_time}"}
        
        elif event_type == "ping":
            logger.info(f"Ping received at {current_time}")
            return {"message": f"pong at {current_time}"}
        
        else:
            logger.info(f"Event type '{event_type}' received but not handled at {current_time}")
            return {"message": f"Event type '{event_type}' received but not handled at {current_time}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {str(e)} at {current_time}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")
