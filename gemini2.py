import json
from pathlib import Path
import google.generativeai as genai

# Configure the Gemini API client
API_KEY = ""  # Your provided API key
genai.configure(api_key=API_KEY)

# Define the model
MODEL_ID = "gemini-2.0-flash"  # Using stable Gemini 1.5 Pro

def list_available_models() -> None:
    """
    List all available models that support the generateContent method.
    """
    print("Available models supporting generateContent:")
    for model in genai.list_models():
        if "generateContent" in model.supported_generation_methods:
            print(f"- {model.name}")
    print("\nUpdate MODEL_ID in the script with a model from this list if needed.")

def extract_table_from_pdf(pdf_path: str) -> dict:
    """
    Extract table data from a PDF file using Gemini API and return structured data.
    
    Args:
        pdf_path (str): Path to the PDF file.
    
    Returns:
        dict: Raw JSON response containing table data.
    """
    # Verify PDF file exists
    if not Path(pdf_path).is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Upload the PDF to Gemini File API
    uploaded_file = genai.upload_file(
        path=pdf_path,
        display_name=Path(pdf_path).stem,
        mime_type="application/pdf"
    )
    
    # Define the prompt for table extraction
    prompt = """
    Extract table data from the provided PDF file and return it in JSON format with the following structure:
    - Each object in the top-level list represents table data from a specific page.
    - "page" is an integer indicating the page number (starting from 1, relative to the input PDF).
    - "table" is a list of objects, where each object represents a row or text segment formatted like a row.
    - Keys in row objects are strings (e.g., column headers, empty string "", or "null" for missing headers).
    - Values are strings representing cell content (use null for empty or merged cells).
    - If a row's data extends across pages, include it in the row where it starts, this is merge it to the page number in which the row starts.
    - Only extract data within table structures (grid-like layouts); ignore non-table content, index pages, and text in Roman numerals.
    - If the table contains sensitive or copyrighted content, rephrase or summarize the data to avoid direct recitation.
    - Ensure the output is valid JSON. If multiple tables exist on a page, combine them if they have the same structure; otherwise, include the first table.
    - Convert all values to strings to ensure consistency.

    If the whole pdf contains only one pdf then dynamicaly create a json format suitable for the data given in that table(you can verify that if the whole pdf has only single table by checking if the serial numbers are continuous)
    """
    
    # Create model instance
    model = genai.GenerativeModel(
        model_name=MODEL_ID,
        generation_config={"response_mime_type": "application/json"}
    )
    
    # Generate content using Gemini API
    try:
        response = model.generate_content(
            [prompt, uploaded_file]
        )
        
        # Check for valid response and finish_reason
        if not response.candidates or not response.candidates[0].content.parts:
            finish_reason = response.candidates[0].finish_reason if response.candidates else "Unknown"
            raise ValueError(
                f"No valid content returned. Finish reason: {finish_reason}. "
                f"Response details: {response.__dict__}"
                f"The finish_reason values are:"
                f"- 1: FINISH_REASON_UNSPECIFIED - The default value, meaning the model reached a natural stopping point, e.g., because it generated the maximum number of tokens or generated a stop token."
                f"- 2: FINISH_REASON_MAX_TOKENS - Generation stopped because the generated response reached the maximum number of tokens specified in the request (max_output_tokens)."
                f"- 3: FINISH_REASON_SAFETY - Generation stopped because the content was flagged by safety filters."
                f"- 4: FINISH_REASON_RECITATION - Generation stopped because the content was flagged for recitation of copyrighted material."
                f"- 5: FINISH_REASON_BLOCKED - Generation stopped because the content was blocked by platform policy or terms of use."
                f"- 6: FINISH_REASON_PROHIBITED_CONTENT - Generation stopped because the content contained prohibited material."
                f"- 7: FINISH_REASON_SPNR - Generation stopped for reasons related to sensitive personally identifiable information (SPII)."
                f"For more details, see the [Content filtering](https://ai.google.dev/docs/content_filtering) guide."
            )
        
        # Parse and return the raw JSON response
        try:
            return json.loads(response.text)
        except Exception as e:
            print(f"JSON parsing error: {str(e)}")
            print(f"Raw API response: {response.text}")
            raise
    
    finally:
        # Delete the uploaded file to clean up
        genai.delete_file(uploaded_file.name)

def save_to_json(data: dict, output_path: str) -> None:
    """
    Save the extracted table data to a JSON file.
    
    Args:
        data (dict): Raw JSON data containing table data.
        output_path (str): Path to save the JSON file.
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Table data saved to {output_path}")

def main():
    # Define input and output paths
    pdf_path = "11. Rate Notification - CGST-DMS.pdf"  # Your PDF file path
    output_json_path = "table_data.json"
    
    try:
        # List available models (uncomment to check available models)
        # list_available_models()
        
        # Extract table data
        table_data = extract_table_from_pdf(pdf_path)
        
        # Save to JSON
        save_to_json(table_data, output_json_path)
        
        # Print the extracted data for verification
        print("\nExtracted Table Data:")
        print(json.dumps(table_data, indent=2))
        
    except Exception as e:
        print(f"Error: {str(e)}")
        if "404" in str(e) or "not found" in str(e).lower():
            print("\nThe specified model may not be available. Run list_available_models() to check available models.")
            list_available_models()
        elif "finish_reason" in str(e).lower():
            print("\nThe PDF may contain copyrighted material. Try using a different PDF or modifying the prompt to avoid sensitive content.")

if __name__ == "__main__":
    main()