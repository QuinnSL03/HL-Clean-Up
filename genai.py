import requests
import json
import os
from dotenv import load_dotenv # Import load_dotenv

# Load environment variables from .env file
load_dotenv()

def send_message_to_gemini_api(api_key: str, message: str) -> dict:
    """
    Sends a message to the Gemini AI API and returns the JSON response.

    Args:
        api_key: Your Google Cloud API key for accessing the Gemini API.
        message: The text message to send to the AI model.

    Returns:
        A dictionary containing the JSON response from the API.
    """
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key
    }
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": message}
                ]
            }
        ]
    }

    try:
        # Keep verify=False for now due to your environment's SSL issues
        response = requests.post(api_url, headers=headers, json=payload, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return {"error": str(e)}

def save_response_to_file(response_data: dict, filename: str = "gemini_response.json"):
    """
    Saves the API response data to a JSON file.
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving response to file: {e}")

if __name__ == "__main__":
    # Retrieve the API key from environment variables
    YOUR_API_KEY = os.getenv("GEMINI_API_KEY")

    if YOUR_API_KEY is None:
        print("Error: GEMINI_API_KEY not found in .env file or environment variables.")
        print("Please create a .env file in the same directory with GEMINI_API_KEY=YOUR_ACTUAL_API_KEY_HERE")
    else:
        user_message = "Tell me a short story about a brave knight."

        gemini_response = send_message_to_gemini_api(YOUR_API_KEY, user_message)

        if "error" not in gemini_response:
            try:
                ai_text = gemini_response['candidates'][0]['content']['parts'][0]['text']
                print(ai_text) 
            except (KeyError, IndexError) as e:
                print(f"Could not extract AI text from response. Structure might be unexpected: {e}")
            except Exception as e:
                print(f"An unexpected error occurred while processing AI text: {e}")

            save_response_to_file(gemini_response)