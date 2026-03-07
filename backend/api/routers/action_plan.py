import logging
from fastapi import APIRouter, HTTPException

from api.config import get_settings
from api.schemas import ActionPlanRequest, ActionPlanResponse

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(tags=["action-plan"])


@router.post("/action-plan", response_model=ActionPlanResponse)
def generate_action_plan(request: ActionPlanRequest) -> ActionPlanResponse:
    settings = get_settings()

    if not GENAI_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="google-generativeai package not installed."
        )

    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured on the server."
        )

    # Initialize SDK
    genai.configure(api_key=settings.gemini_api_key)

    # Prepare prompt
    prompt = f"""You are an expert forestry consultant. Based on the following metrics for a forest region, provide a concise, actionable set of guidelines and steps for Forest Officers to take.

Metrics:
- Total Tree Count: {request.tree_count}
- Tree Density (trees/km²): {request.tree_density}
- Health Score (0-100): {request.health_score}
- Deforestation Risk Level: {request.risk_level}
- Species Distribution: {request.species_distribution}

Output your response in Markdown format. Focus only on actionable steps and guidelines. Be extremely specific and assume the audience are technical forest officers. Do not output anything outside of the markdown.
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        
        return ActionPlanResponse(guidelines_markdown=response.text)
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate action plan.")
