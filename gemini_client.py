# gemini_client.py
import requests
import json
import os
from dotenv import load_dotenv
import google.auth
import google.auth.transport.requests

# Load environment variables from .env file
load_dotenv()

def _send_request_to_vertex_api(project_id: str, region: str, model_id: str, message: str) -> dict:
    """
    (Internal helper function) Sends a message to the Vertex AI API and returns the JSON response.
    """
    
    # Authenticate using Application Default Credentials
    credentials, project = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    access_token = credentials.token

    # Vertex AI Endpoint URL structure
    api_url = (
        f"https://{region}-aiplatform.googleapis.com/v1/"
        f"projects/{project_id}/locations/{region}/publishers/google/models/{model_id}:predict"
    )
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}" # OAuth token for Vertex AI
    }
    
    # Vertex AI prediction request payload
    payload = {
        "instances": [
            {
                "prompt": message # For text-bison (older), for Gemini uses 'parts' in 'contents'
            }
        ],
        "parameters": {
            "temperature": 0.2,
            "maxOutputTokens": 1000,
            "topP": 0.95,
            "topK": 40
        }
    }

    # Special handling for Gemini models within Vertex AI for 'contents' field
    if model_id.startswith("gemini"):
        payload["instances"][0] = {
            "contents": [
                {
                    "parts": [
                        {"text": message}
                    ]
                }
            ]
        }
        # Gemini does not use 'prompt'
        del payload["instances"][0]["prompt"]


    try:
        # Vertex AI typically requires proper SSL verification.
        # If you still face SSL issues in your corporate environment,
        # you might need to configure your trusted CA certificates or set verify=False (not recommended).
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Vertex AI API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"API Response status: {e.response.status_code}")
            print(f"API Response content: {e.response.text}")
        return {"error": str(e)}

def ask_gemini(question: str) -> str | None:
    """
    Sends a question to the Vertex AI Gemini model and returns the AI's textual response.

    Args:
        question: The question string to send to the AI.

    Returns:
        The AI's generated text response as a string, or None if an error occurs.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    region = os.getenv("GOOGLE_CLOUD_REGION")
    model_id = os.getenv("GEMINI_MODEL_ID", "gemini-pro") # Default to gemini-pro

    if not all([project_id, region, model_id]):
        print("Error: GOOGLE_CLOUD_PROJECT_ID, GOOGLE_CLOUD_REGION, or GEMINI_MODEL_ID "
              "not found in .env file or environment variables.")
        print("Please ensure your .env file is correctly configured.")
        return None

    vertex_response = _send_request_to_vertex_api(project_id, region, model_id, question)

    if "error" not in vertex_response:
        try:
            # Vertex AI response structure for Gemini models under 'predictions'
            ai_text = vertex_response['predictions'][0]['candidates'][0]['content']['parts'][0]['text']
            return ai_text
        except (KeyError, IndexError) as e:
            print(f"Error: Could not extract AI text from Vertex AI response. Structure might be unexpected: {e}")
            # Optionally, print the full response for debugging:
            # print(json.dumps(vertex_response, indent=2))
            return None
    else:
        # Error message already printed by _send_request_to_vertex_api
        return None

if __name__ == "__main__":
    print("--- Running gemini_client.py directly for demonstration (Vertex AI) ---")
    
    test_question = "Explain large language models in one sentence."
    print(f"\nAsking Gemini (Vertex AI): '{test_question}'")
    response_text = ask_gemini(test_question)
    
    if response_text:
        print("\nGemini's Response:")
        print(response_text)
    else:
        print("\nFailed to get a response from Gemini (Vertex AI).")