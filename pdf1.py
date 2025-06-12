import pdfplumber
import json

pdf_path = "2024-08-01-ACT-Compensation.pdf"
tables_data = []

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for table in tables:
            headers = table[0]
            data_rows = table[1:]
            table_json = [dict(zip(headers, row)) for row in data_rows]
            tables_data.append({
                "page": i + 1,
                "table": table_json
            })

# Save to JSON
with open("tables_output.json", "w", encoding='utf-8') as f:
    json.dump(tables_data, f, indent=2)
