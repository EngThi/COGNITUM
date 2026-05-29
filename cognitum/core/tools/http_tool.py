import requests

def call_http_api(method: str, url: str, headers: dict = None, json_data: dict = None) -> str:
    """Executes a synchronous HTTP request and returns status code and response payload."""
    try:
        method = method.upper()
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            timeout=60.0
        )
        output = f"Status Code: {resp.status_code}\n"
        output += f"Response:\n{resp.text}"
        return output
    except Exception as e:
        return f"Error executing HTTP API request: {e}"
