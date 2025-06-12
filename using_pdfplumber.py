import pdfplumber
import json
from pathlib import Path
from typing import List, Dict, Any
import re

def extract_table_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Extract table data from a PDF file using pdfplumber and return structured data.
    
    Args:
        pdf_path (str): Path to the PDF file.
    
    Returns:
        dict: JSON-compatible dictionary containing table data.
    """
    # Verify PDF file exists
    if not Path(pdf_path).is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    all_tables = []
    serial_numbers = []
    has_single_table = True

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Extract tables from the page
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                # Skip empty tables
                if not table or not any(row for row in table):
                    continue

                # Process table rows
                processed_table = []
                headers = None
                for row in table:
                    # Clean row data: convert to strings, handle None
                    cleaned_row = [str(cell).strip() if cell is not None else "" for cell in row]
                    
                    # Detect headers (first row with non-empty cells)
                    if not headers and any(cleaned_row):
                        headers = cleaned_row
                        continue
                    
                    # Skip empty rows
                    if not any(cleaned_row):
                        continue

                    # Create row dictionary
                    row_dict = {header: value for header, value in zip(headers, cleaned_row)}
                    
                    # Check for serial number to track table continuity
                    if "S.No" in row_dict or "Serial" in row_dict:
                        sn_key = "S.No" if "S.No" in row_dict else "Serial"
                        sn_value = row_dict.get(sn_key, "")
                        if sn_value.isdigit():
                            serial_numbers.append(int(sn_value))

                    processed_table.append(row_dict)

                if processed_table:
                    all_tables.append({
                        "page": page_num,
                        "table": processed_table
                    })

            # If multiple tables with different structures detected, mark as not single table
            if len(tables) > 1:
                has_single_table = False

    # Check if the PDF has a single continuous table (based on serial numbers)
    if serial_numbers and has_single_table:
        is_continuous = all(
            serial_numbers[i] + 1 == serial_numbers[i + 1]
            for i in range(len(serial_numbers) - 1)
        )
        if is_continuous and len(all_tables) > 1:
            # Merge tables into a single table structure
            merged_table = []
            for table_data in all_tables:
                merged_table.extend(table_data["table"])
            all_tables = [{"page": 1, "table": merged_table}]
        elif is_continuous and len(all_tables) == 1:
            # Single table already, no merge needed
            pass
        else:
            has_single_table = False

    # If single table, dynamically adjust JSON structure
    if has_single_table and all_tables:
        return all_tables[0]["table"]  # Return just the table data as a list
    elif all_tables:
        return all_tables  # Return list of page-wise tables
    else:
        return []  # No tables found

def save_to_json(data: Dict[str, Any], output_path: str) -> None:
    """
    Save the extracted table data to a JSON file.
    
    Args:
        data (dict): JSON-compatible data containing table data.
        output_path (str): Path to save the JSON file.
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Table data saved to {output_path}")

def main():
    # Define input and output paths
    pdf_path = "2024-08-01-ACT-Compensation.pdf"  # Your PDF file path
    output_json_path = "table_data.json"
    
    try:
        # Extract table data
        table_data = extract_table_from_pdf(pdf_path)
        
        # Save to JSON
        save_to_json(table_data, output_json_path)
        
        # Print the extracted data for verification
        print("\nExtracted Table Data:")
        print(json.dumps(table_data, indent=2))
        
    except Exception as e:
        print(f"Error: {str(e)}")
        if isinstance(e, FileNotFoundError):
            print("\nPlease verify the PDF file path.")
        else:
            print("\nAn error occurred during table extraction. Ensure the PDF contains valid tables.")

if __name__ == "__main__":
    main()