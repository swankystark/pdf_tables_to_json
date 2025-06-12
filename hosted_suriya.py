import requests
import json
import os
from dotenv import load_dotenv

# Load API key
load_dotenv()
api_key = os.getenv("DATALAB_API_KEY")
if not api_key:
    raise ValueError("API key not found. Set DATALAB_API_KEY in .env file.")

# Configure request
url = "https://www.datalab.to/api/v1/marker"
headers = {"X-Api-Key": api_key}
form_data = {
    'file': ('2024-08-01-ACT-Compensation.pdf', open('2024-08-01-ACT-Compensation.pdf', 'rb'), 'application/pdf'),
    'langs': (None, "English"),
    'force_ocr': (None, "false"),
    'paginate': (None, "false"),
    'output_format': (None, "json"),  # Try JSON for structured output
    'use_llm': (None, "false"),
    'strip_existing_ocr': (None, "false"),
    'disable_image_extraction': (None, "false")
}

try:
    print("Submitting PDF to /api/v1/marker...")
    response = requests.post(url, files=form_data, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Response Text: {response.text[:1000]}")
    response.raise_for_status()

    if "application/json" not in response.headers.get("Content-Type", "").lower():
        print("Error: Response is not JSON")
        print(response.text)
        exit(1)

    response_json = response.json()
    print("Response JSON:", json.dumps(response_json, indent=2))

    # Save output
    with open("marker_output.json", "w") as f:
        json.dump(response_json, f, indent=2)
    print("Output saved to marker_output.json")

except requests.exceptions.HTTPError as http_err:
    print(f"HTTP Error: {http_err}")
    print(response.text)
    exit(1)
except requests.exceptions.JSONDecodeError as json_err:
    print(f"JSON Decode Error: {json_err}")
    print(f"Raw Response: {response.text}")
    exit(1)
except Exception as e:
    print(f"Other Error: {e}")
    exit(1)
finally:
    form_data['file'][1].close()  # Close the file