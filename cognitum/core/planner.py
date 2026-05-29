import os
import json
import asyncio
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from cognitum.config import settings

class PlanStep(BaseModel):
    step_number: int = Field(..., description="1-indexed sequence number of this step")
    description: str = Field(..., description="Action description of what to perform")
    tool_recommendation: Optional[str] = Field(None, description="Optional recommended tool or command")
    expected_outcome: str = Field(..., description="The criteria for verifying success of this step")

class Plan(BaseModel):
    goal: str = Field(..., description="The refined goal that the agent is working towards")
    steps: List[PlanStep] = Field(..., description="Sequential steps to achieve the goal")
    reasoning: str = Field(..., description="Reasoning and explanation for the proposed plan")
    required_contexts: List[str] = Field(..., description="Information or files needed before executing the steps")

_client = None

def get_genai_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY") or settings.gemini_api_key
        if not api_key:
            raise ValueError("GEMINI_API_KEY missing in environment / configuration settings")
        _client = genai.Client(api_key=api_key)
    return _client

async def generate_content_with_backoff(
    contents: Any,
    config: Optional[types.GenerateContentConfig] = None,
    model: Optional[str] = None
) -> Any:
    """Executes a text generation query against Gemini with exponential backoff on rate limits."""
    client = get_genai_client()
    target_model = model or settings.gemini_model
    delay = 2
    max_retries = 5
    
    # Run in executor since the official SDK call is blocking
    loop = asyncio.get_running_loop()
    
    for i in range(max_retries):
        try:
            # We call the blocking genai client inside run_in_executor to avoid blocking the event loop
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=target_model,
                    contents=contents,
                    config=config
                )
            )
            return response
        except ClientError as e:
            if getattr(e, 'code', None) == 429 or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if i == max_retries - 1:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
            else:
                raise
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if i == max_retries - 1:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
            else:
                raise
    raise RuntimeError("Max retries exceeded for Gemini API.")

async def generate_plan(
    goal: str,
    context: Optional[str] = None,
    profile_data: Optional[Dict[str, Any]] = None,
    policies_data: Optional[Dict[str, Any]] = None
) -> Plan:
    """Uses Gemini 2.5 Flash to generate a structured execution plan based on goal, context, user profile and policies."""
    
    prompt = f"Goal: {goal}\n\n"
    if context:
        prompt += f"Active Context:\n{context}\n\n"
    if profile_data:
        prompt += f"User Profile Details:\n{json.dumps(profile_data, indent=2)}\n\n"
    if policies_data:
        prompt += f"Operational Safety Policies:\n{json.dumps(policies_data, indent=2)}\n\n"
        
    prompt += (
        "Generate a step-by-step action plan to achieve the goal. "
        "The plan must satisfy safety policies (e.g. no prohibited actions, restricted hours warnings if applicable). "
        "Recommend specific tools where appropriate (e.g. read_file, run_command, call_mcp_tool)."
    )

    response = await generate_content_with_backoff(
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Plan,
            temperature=0.2
        )
    )
    
    return Plan.model_validate_json(response.text)
