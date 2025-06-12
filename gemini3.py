import json
from pathlib import Path
import google.generativeai as genai
from PyPDF2 import PdfReader, PdfWriter
import os

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

def get_table_page_ranges(pdf_path: str) -> list[dict[str, int]]:
    """
    Use Gemini API to identify page ranges containing tables in the PDF.
    
    Args:
        pdf_path (str): Path to the PDF file.
    
    Returns:
        list[dict[str, int]]: List of dictionaries with 'start_page' and 'end_page' for each table range.
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
    
    # Define the prompt to identify table page ranges
    prompt = """
    Analyze the provided PDF and identify the page ranges that contain tables.i want page ranges for all the tables in the pdf.
    A single table may span multiple consecutive pages.
    Return the result in JSON format with the following structure:
    [
      {"start_page": <integer>, "end_page": <integer>},
      ...
    ]
    - "start_page" and "end_page" are integers (1-based indexing) indicating the range of pages for each table.
    - If a table spans multiple pages, include all pages in the range (e.g., {"start_page": 1, "end_page": 3}).
    - If no tables are found, return an empty list [].
    - Ensure the output is valid JSON.
    """
    
    # Create model instance
    model = genai.GenerativeModel(
        model_name=MODEL_ID,
        generation_config={"response_mime_type": "application/json"}
    )
    
    try:
        response = model.generate_content(
            [prompt, uploaded_file]
        )
        
        # Check for valid response and finish_reason
        if not response.candidates or not response.candidates[0].content.parts:
            finish_reason = response.candidates[0].finish_reason if response.candidates else "Unknown"
            raise ValueError(f"""
No valid content returned. Finish reason: {finish_reason}.
Response details: {response.__dict__}
The finish_reason values are:
- 1: FINISH_REASON_UNSPECIFIED - The default value, meaning the model reached a natural stopping point, e.g., because it generated the maximum number of tokens or generated a stop token.
- 2: FINISH_REASON_MAX_TOKENS - Generation stopped because the generated response reached the maximum number of tokens specified in the request (max_output_tokens).
- 3: FINISH_REASON_SAFETY - Generation stopped because the content was flagged by safety filters.
- 4: FINISH_REASON_RECITATION - Generation stopped because the content was flagged for recitation of copyrighted material.
- 5: FINISH_REASON_BLOCKED - Generation stopped because the content was blocked by platform policy or terms of use.
- 6: FINISH_REASON_PROHIBITED_CONTENT - Generation stopped because the content contained prohibited material.
- 7: FINISH_REASON_SPNR - Generation stopped for reasons related to sensitive personally identifiable information (SPII).
For more details, see the [Content filtering](https://ai.google.dev/docs/content_filtering) guide.
            """)
        
        # Parse the JSON response
        try:
            return json.loads(response.text)
        except Exception as e:
            print(f"JSON parsing error for table ranges: {str(e)}")
            print(f"Raw API response: {response.text}")
            raise
    
    finally:
        # Delete the uploaded file to clean up
        genai.delete_file(uploaded_file.name)

def split_pdf(pdf_path: str, page_ranges: list[dict[str, int]], output_dir: str) -> list[str]:
    """
    Split the PDF into smaller PDFs based on the provided page ranges.
    
    Args:
        pdf_path (str): Path to the input PDF file.
        page_ranges (list[dict]): List of page ranges with 'start_page' and 'end_page'.
        output_dir (str): Directory to save the split PDFs.
    
    Returns:
        list[str]: List of paths to the split PDF files.
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read the input PDF
    pdf_reader = PdfReader(pdf_path)
    
    split_pdf_paths = []
    for idx, page_range in enumerate(page_ranges):
        start_page = page_range["start_page"]
        end_page = page_range["end_page"]
        
        # Validate page range
        if start_page < 1 or end_page > len(pdf_reader.pages) or start_page > end_page:
            print(f"Skipping invalid page range: {page_range}")
            continue
        
        # Create a new PDF writer for this range
        pdf_writer = PdfWriter()
        for page_num in range(start_page - 1, end_page):  # Convert to 0-based indexing
            pdf_writer.add_page(pdf_reader.pages[page_num])
        
        # Save the split PDF
        output_pdf_path = os.path.join(output_dir, f"split_{start_page}_to_{end_page}.pdf")
        with open(output_pdf_path, "wb") as f:
            pdf_writer.write(f)
        split_pdf_paths.append(output_pdf_path)
        print(f"Created split PDF: {output_pdf_path}")
    
    return split_pdf_paths

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
            raise ValueError(f"""
No valid content returned. Finish reason: {finish_reason}.
Response details: {response.__dict__}
The finish_reason values are:
- 1: FINISH_REASON_UNSPECIFIED - The default value, meaning the model reached a natural stopping point, e.g., because it generated the maximum number of tokens or generated a stop token.
- 2: FINISH_REASON_MAX_TOKENS - Generation stopped because the generated response reached the maximum number of tokens specified in the request (max_output_tokens).
- 3: FINISH_REASON_SAFETY - Generation stopped because the content was flagged by safety filters.
- 4: FINISH_REASON_RECITATION - Generation stopped because the content was flagged for recitation of copyrighted material.
- 5: FINISH_REASON_BLOCKED - Generation stopped because the content was blocked by platform policy or terms of use.
- 6: FINISH_REASON_PROHIBITED_CONTENT - Generation stopped because the content contained prohibited material.
- 7: FINISH_REASON_SPNR - Generation stopped for reasons related to sensitive personally identifiable information (SPII).
For more details, see the [Content filtering](https://ai.google.dev/docs/content_filtering) guide.
            """)
        
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
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Table data saved to {output_path}")

def main():
    # Define input PDF path
    pdf_path = "11. Rate Notification - CGST-DMS.pdf"  # Your PDF file path
    
    try:
        # Check the number of pages in the PDF
        pdf_reader = PdfReader(pdf_path)
        num_pages = len(pdf_reader.pages)
        print(f"Total pages in PDF: {num_pages}")

        # Define output directories
        pdf_dir = os.path.dirname(pdf_path)
        split_pdfs_dir = os.path.join(pdf_dir, "split_pdfs")
        json_outputs_dir = os.path.join(pdf_dir, "json_outputs")

        if num_pages <= 23:
            # If the PDF has 23 or fewer pages, process it directly
            print("PDF has 23 or fewer pages. Processing directly...")
            table_data = extract_table_from_pdf(pdf_path)
            output_json_path = os.path.join(json_outputs_dir, "table_data.json")
            save_to_json(table_data, output_json_path)
            print("\nExtracted Table Data:")
            print(json.dumps(table_data, indent=2))
        else:
            # If the PDF has more than 23 pages, split it based on table ranges
            print("PDF has more than 23 pages. Identifying table page ranges...")
            page_ranges = get_table_page_ranges(pdf_path)
            print(f"Table page ranges: {page_ranges}")

            if not page_ranges:
                print("No tables found in the PDF.")
                return

            # Split the PDF into the identified ranges
            split_pdf_paths = split_pdf(pdf_path, page_ranges, split_pdfs_dir)

            # Process each split PDF and save the JSON output
            for split_pdf_path in split_pdf_paths:
                print(f"\nProcessing split PDF: {split_pdf_path}")
                table_data = extract_table_from_pdf(split_pdf_path)
                # Generate JSON filename based on the split PDF name
                split_filename = os.path.basename(split_pdf_path).replace(".pdf", ".json")
                output_json_path = os.path.join(json_outputs_dir, split_filename)
                save_to_json(table_data, output_json_path)
                print(f"Extracted Table Data for {split_pdf_path}:")
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