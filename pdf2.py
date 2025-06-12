import camelot
import json

pdf_path = "2024-08-01-ACT-Compensation.pdf"
tables = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")  # Use "stream" if no lines

final_output = []

for table in tables:
    df = table.df
    headers = df.iloc[0].tolist()
    data_rows = df.iloc[1:].values.tolist()
    
    # Convert to JSON format
    table_json = [dict(zip(headers, row)) for row in data_rows]
    final_output.append({
        "page": table.page,
        "table": table_json
    })

# Save to file
with open("clean_tables_output.json", "w", encoding="utf-8") as f:
    json.dump(final_output, f, indent=2)
