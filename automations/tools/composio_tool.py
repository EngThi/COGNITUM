import os
import json

def call_composio_action(action_name: str, parameters: dict) -> str:
    try:
        from composio import Composio
        api_key = os.getenv("COMPOSIO_API_KEY")
        if not api_key:
            return "Error: COMPOSIO_API_KEY not found in environment."
        client = Composio(api_key=api_key)
        res = client.tools.execute(
            slug=action_name,
            arguments=parameters,
            user_id="default",
            dangerously_skip_version_check=True
        )
        if hasattr(res, "dict"):
            return json.dumps(res.dict(), indent=2)
        elif hasattr(res, "model_dump"):
            return json.dumps(res.model_dump(), indent=2)
        elif isinstance(res, dict):
            return json.dumps(res, indent=2)
        else:
            return str(res)
    except Exception as e:
        return f"Error executing Composio action: {e}"
