import camelot
import json
from pathlib import Path
from typing import List, Dict, Any
import re
import pandas as pd

def is_valid_table(df: pd.DataFrame) -> bool:
    """
    Check if a DataFrame represents a valid table by ensuring it has multiple non-empty rows
    and columns with meaningful content.
    
    Args:
        df (pd.DataFrame): Table DataFrame from camelot.
    
    Returns:
        bool: True if valid table, False otherwise.
    """
    if df.empty or len(df) < 2:  # Require at least 2 rows (header + data)
        return False
    # Check if at least 2 columns have non-empty values
    non_empty_cols = sum(df.apply(lambda col: any(str(x).strip() for x in col)))
    if non_empty_cols < 2:
        return False
    # Check if rows have varied content (not repetitive text)
    unique_rows = len(df.drop_duplicates())
    return unique_rows > 1

def extract_table_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Extract table data from a PDF file using camelot and return structured data.
    
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

    try:
        # Try lattice mode first for grid-based tables
        tables = camelot.read_pdf(pdf_path, flavor='lattice', pages='all', suppress_stdout=False)
        print(f"Found {len(tables)} tables in lattice mode.")
        
        # If no tables found, try stream mode for non-grid tables
        if not tables:
            print("No tables found in lattice mode. Trying stream mode...")
            tables = camelot.read_pdf(pdf_path, flavor='stream', pages='all', suppress_stdout=False)
            print(f"Found {len(tables)} tables in stream mode.")

    except Exception as e:
        raise RuntimeError(f"Failed to read PDF with camelot: {str(e)}")

    if not tables:
        print("Warning: No tables found in the PDF.")
        return []

    for table in tables:
        page_num = table.page
        df = table.df  # Get table as pandas DataFrame

        # Validate table
        if not is_valid_table(df):
            print(f"Skipping invalid table on page {page_num}: {df.to_string()}")
            continue

        # Process table rows
        processed_table = []
        headers = None
        for index, row in df.iterrows():
            # Clean row data: convert to strings, handle None/empty
            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
            
            # Detect headers (first row with at least 2 non-empty cells)
            if not headers and sum(1 for cell in cleaned_row if cell) >= 2:
                headers = cleaned_row
                continue
            
            # Skip empty rows
            if not any(cleaned_row):
                continue

            # Create row dictionary
            if headers and len(headers) == len(cleaned_row):
                row_dict = {header: value for header, value in zip(headers, cleaned_row)}
            else:
                continue  # Skip rows that don't match header length

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
            print(f"Extracted valid table on page {page_num} with {len(processed_table)} rows.")

        # If multiple tables on the same page, mark as not single table
        if len(tables) > 1 and any(t.page == page_num for t in tables if t != table):
            has_single_table = False

    # Check for single continuous table
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
            print("Merged tables into a single continuous table.")
        elif is_continuous and len(all_tables) == 1:
            print("Single continuous table detected.")
        else:
            has_single_table = False

    # Return appropriate JSON structure
    if has_single_table and all_tables:
        return all_tables[0]["table"]  # Flat list for single table
    elif all_tables:
        return all_tables  # Page-wise tables
    else:
        return []  # No valid tables

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
    pdf_path = "2024-08-01-ACT-Compensation.pdf"  # Update with full path if needed
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
        elif "camelot" in str(e).lower():
            print("\nCamelot library issue. Ensure camelot-py and Ghostscript are installed correctly.")
            print("Run: pip install camelot-py[cv] pandas")
            print("Ensure Ghostscript is installed and added to PATH.")
        else:
            print("\nAn error occurred during table extraction. Ensure the PDF contains valid tables.")
            print("Check debug output above for details.")

if __name__ == "__main__":
    main()