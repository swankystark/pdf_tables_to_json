import json
from pathlib import Path

import google.generativeai as genai



# Configure the Gemini API client
API_KEY = ""  # Replace with your actual API key
genai.configure(api_key=API_KEY)

# Define the model
MODEL_ID = "gemini-2.0-pro-exp"  

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
        TableResponse: Pydantic model containing table data.
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
    I want json format for table data, that is, the data within the table structure which looks like grid, do not include any other data.
    if data of one row extends to another page, then include it in the same row in which it starts.
    The JSON data is structured as a list (array) of objects.
    Each object in this top-level list contains two key-value pairs:
    "page": An integer representing the page number from which the data was extracted.
    "table": A list (array) containing the actual table data extracted from that page.
    The "table" list itself contains zero or more objects. Each object within the "table" list represents a row (or sometimes a text segment formatted like a row) from the original source.
    The structure of these inner objects (within the "table" array) is variable:
    They consist of key-value pairs.
    Keys: Are strings. These strings often represent column headers or the first part of a split text entry. Keys can sometimes be an empty string ("") or even the string "null" (likely indicating a missing header during extraction).
    Values: Are typically strings containing the cell content or the second part of a split text entry. Values can also be null, often representing empty cells or merged cells.
    The number and names of keys within these inner objects are not consistent across different table entries or even sometimes within the same table, reflecting the varied nature of the extracted tables (headers, data rows, footnotes, multi-line text, etc.). Some inner objects might only have one key-value pair, while others (like actual data tables) have multiple.    
    Ensure the output is valid JSON. Include only table data found in the PDF.I want json format for table data, do not include any other data.Also ignore the contents from the index pages and points in roman.
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
        
        try:
            # Return the raw JSON response
            return json.loads(response.text)
        except Exception as e:
            print(f"Validation error: {str(e)}")
            print(f"Response text: {response.text}")
            print(f"Raw API response: {response.text}")
            raise
        
    finally:
        # Delete the uploaded file to clean up
        genai.delete_file(uploaded_file.name)

def save_to_json(data: dict, output_path: str) -> None:
    """
    Save the extracted table data to a JSON file.
    
    Args:
        data (TableResponse): Pydantic model containing table data.
        output_path (str): Path to save the JSON file.
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Table data saved to {output_path}")

def main():
    # Define input and output paths
    pdf_path = "11. Rate Notification - CGST-DMS.pdf"  # Replace with your PDF file path
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

if __name__ == "__main__":
    main()