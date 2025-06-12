# PDF Table Extraction Automation

## Professional Task Summary

### Task:
Develop an automated pipeline to convert tabular data from provided PDFs into JSON format.

## Summary of Contributions

- Developed a Python-based automation pipeline utilizing the Gemini API to extract and convert tabular data from PDFs into structured JSON.
- Successfully processed PDFs with organized tables, achieving the required JSON output.
- Documented the process, challenges, and comparative results for multiple extraction tools.

## Technical Approach

### API Configuration:
- Set up Gemini API client with the gemini-2.0-flash model.

### Model Discovery:
- Implemented a function to list available Gemini models for content generation.

### Table Detection & PDF Splitting:
- Used Gemini API to detect table-containing page ranges.
- For PDFs exceeding 23 pages, automatically split files based on detected ranges for efficient processing.

### Table Extraction & JSON Conversion:
- Extracted table data using Gemini API and converted it into the specified JSON format:
  ```json
  [
    {
      "page": <page_number>,
      "table": [
        {
          "<column_key_1>": <value>,
          "<column_key_2>": <value>
        }
      ]
    }
  ]
  ```
- Saved results to output directory for further use.

### Error Handling:
- Managed issues such as invalid files, API errors, and content restrictions, providing clear guidance for troubleshooting.

## Tool Comparison

| Tool/Model           | Organized Tables | Unorganized Tables | Notes |
|----------------------|------------------|-------------------|-------|
| pdfplumber          | No               | No                |       |
| camelot             | No               | No                |       |
| Gemini Vision Models| Yes              | No                | Reliable for structured tables only |
| Suriya OCR          | Partial          | Partial           | Extracted markdown with high error rate, needs review |
| Llama Index         | Yes              | Yes               | Effective, but not used due to classified data |

## Outcome

- The pipeline efficiently extracts and structures tabular data from well-formatted PDFs.
- For irregular tables, Gemini and other standard tools were insufficient.
- Llama Index offered a comprehensive solution but was excluded due to data privacy restrictions.
- Source code and documentation are available on GitHub.

## Key Takeaways

- Automation is robust for organized tabular data.
- Handling unstructured tables remains a challenge with current APIs.
- Data privacy considerations may limit the use of some advanced cloud-based solutions.
