import json
import os
from PIL import Image
import numpy as np
from surya.detection import DetectionPredictor
from surya.layout import LayoutPredictor
from surya.table_rec import TableRecPredictor
from surya.recognition import RecognitionPredictor
import requests
import pdf2image
import logging
from datetime import datetime
import torch
from multiprocessing import Pool, cpu_count
from functools import partial
import gc

# Configuration
os.environ["TABLE_REC_BATCH_SIZE"] = "16"
os.environ["LAYOUT_BATCH_SIZE"] = "8"
os.environ["DETECTOR_BATCH_SIZE"] = "8"
os.environ["RECOGNITION_BATCH_SIZE"] = "32"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def ocr_worker(image_lang, det_predictor=None, rec_predictor=None):
    """Worker function for parallel OCR processing on CPU."""
    image, lang = image_lang
    try:
        det_preds = det_predictor([image])[0]
        rec_preds = rec_predictor([image], [lang], det_predictor=det_predictor)[0]
        ocr_result = {
            "text_lines": [
                {
                    "text": rec_preds.text_lines[i].text,
                    "bbox": det_preds.bboxes[i].bbox,
                    "confidence": rec_preds.text_lines[i].confidence
                }
                for i in range(min(len(rec_preds.text_lines), len(det_preds.bboxes)))
            ]
        }
        return ocr_result
    except Exception as e:
        logger.error(f"Error processing image in worker: {e}")
        return None

class TableExtractionPipeline:
    def __init__(self):
        # Define devices
        self.gpu_device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        self.cpu_device = torch.device("cpu")
        
        logger.info("Initializing Surya predictors...")
        self.layout_predictor = LayoutPredictor(device=self.gpu_device)
        self.table_rec_predictor = TableRecPredictor(device=self.gpu_device)
        self.det_predictor_gpu = DetectionPredictor(device=self.gpu_device)
        self.rec_predictor_gpu = RecognitionPredictor(device=self.gpu_device)
        
        self.gemini_api_key = ""
        self.gemini_endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        
    def pdf_to_images(self, pdf_path):
        """Convert PDF to list of PIL images."""
        logger.info(f"Converting PDF {pdf_path} to images...")
        images = pdf2image.convert_from_path(pdf_path)
        logger.info(f"Converted PDF to {len(images)} images.")
        return images
    
    def detect_layout(self, images):
        """Detect layout elements (tables, text, etc.) in images on GPU."""
        logger.info("Running layout detection on GPU...")
        layout_predictions = self.layout_predictor(images)
        logger.info("Layout detection completed. Clearing GPU cache and unloading model...")
        self.layout_predictor = None  # Unload model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return layout_predictions
    
    def detect_tables(self, images):
        """Detect and extract table structures on GPU."""
        logger.info("Running table detection on GPU...")
        table_predictions = self.table_rec_predictor(images)
        logger.info("Table detection completed. Clearing GPU cache and unloading model...")
        self.table_rec_predictor = None  # Unload model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return table_predictions
    
    def run_ocr(self, images, langs=["en"]):
        """Perform OCR on images using GPU, fallback to CPU with parallel processing if OOM."""
        logger.info("Running OCR on GPU...")
        ocr_predictions = []
        use_cpu = False
        
        for image, lang in zip(images, [langs]*len(images)):
            if not use_cpu:
                try:
                    # Try GPU
                    det_preds = self.det_predictor_gpu([image])[0]
                    rec_preds = self.rec_predictor_gpu([image], [lang], det_predictor=self.det_predictor_gpu)[0]
                    ocr_result = {
                        "text_lines": [
                            {
                                "text": rec_preds.text_lines[i].text,
                                "bbox": det_preds.bboxes[i].bbox,
                                "confidence": rec_preds.text_lines[i].confidence
                            }
                            for i in range(min(len(rec_preds.text_lines), len(det_preds.bboxes)))
                        ]
                    }
                    ocr_predictions.append(ocr_result)
                    if torch.cuda.is_available():
                        logger.info("Clearing GPU cache after processing page...")
                        torch.cuda.empty_cache()
                except torch.OutOfMemoryError:
                    logger.warning("GPU out of memory during OCR. Switching to CPU with parallel processing...")
                    use_cpu = True
        
            if use_cpu:
                # Switch to CPU with parallel processing
                logger.info(f"Running OCR on CPU with parallel processing using {min(6, cpu_count())} cores...")
                with Pool(processes=6) as pool:
                    # Initialize predictors for each process
                    det_predictor = DetectionPredictor(device=self.cpu_device)
                    rec_predictor = RecognitionPredictor(device=self.cpu_device)
                    worker_func = partial(ocr_worker, det_predictor=det_predictor, rec_predictor=rec_predictor)
                    image_langs = [(img, lang) for img, lang in zip(images[len(ocr_predictions):], [langs]*(len(images)-len(ocr_predictions)))]
                    results = pool.map(worker_func, image_langs)
                    pool.close()
                    pool.join()
                
                # Filter out None results and extend predictions
                valid_results = [r for r in results if r is not None]
                if len(valid_results) < len(results):
                    logger.warning(f"Some OCR tasks failed: {len(results) - len(valid_results)} pages skipped.")
                ocr_predictions.extend(valid_results)
                break  # Exit loop as parallel processing handles remaining images
        
        logger.info("OCR completed.")
        return ocr_predictions
    
    def gemini_refine(self, table_data, ocr_text):
        """Use Gemini-2.5-Flash to refine table structure and handle splits."""
        logger.info("Refining table structure with Gemini-2.5-Flash...")
        prompt = f"""
        Given the following table data and OCR text, refine the table structure. Handle cases where the table is split across pages or interrupted by text. Output a JSON representation of the table.

        Table Data: {json.dumps(table_data, indent=2)}
        OCR Text: {ocr_text}

        Ensure rows and columns are correctly aligned, and merge split tables if necessary. Return only the JSON output.
        """
        
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        
        try:
            response = requests.post(
                f"{self.gemini_endpoint}?key={self.gemini_api_key}",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            result = response.json()
            refined_json = result["candidates"][0]["content"]["parts"][0]["text"]
            logger.info("Table refinement completed.")
            return json.loads(refined_json)
        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error refining table: {e}. Falling back to original table data.")
            return table_data
    
    def merge_split_tables(self, table_predictions, layout_predictions, page_idx):
        """Merge tables split across pages or interrupted by content."""
        logger.info("Merging split tables...")
        merged_tables = []
        current_table = None
        
        for page_idx, (table_pred, layout_pred) in enumerate(zip(table_predictions, layout_predictions)):
            tables = table_pred.get("tables", [])
            
            for table in tables:
                if current_table is None:
                    current_table = table
                else:
                    last_row_bbox = current_table["rows"][-1]["bbox"]
                    first_row_bbox = table["rows"][0]["bbox"]
                    layout_bboxes = [bbox["bbox"] for bbox in layout_pred["bboxes"] if bbox["label"] != "Table"]
                    
                    if (first_row_bbox[1] - last_row_bbox[3] < 50 and
                        not any(bbox[1] > last_row_bbox[3] and bbox[3] < first_row_bbox[1] for bbox in layout_bboxes)):
                        current_table["rows"].extend(table["rows"])
                        current_table["cells"].extend(table["cells"])
                        max_row_id = max(cell["row_id"] for cell in current_table["cells"])
                        for cell in table["cells"]:
                            cell["row_id"] += max_row_id + 1
                    else:
                        merged_tables.append(current_table)
                        current_table = table
                        
        if current_table:
            merged_tables.append(current_table)
            
        logger.info(f"Merged {len(merged_tables)} tables.")
        return merged_tables
    
    def process_document(self, input_path, langs=["en"], output_dir="output"):
        """Main pipeline to process document and extract tables as JSON."""
        logger.info(f"Starting pipeline for {input_path}...")
        os.makedirs(output_dir, exist_ok=True)
        
        images = self.pdf_to_images(input_path) if input_path.endswith(".pdf") else [Image.open(input_path)]
        layout_predictions = self.detect_layout(images)
        table_predictions = self.detect_tables(images)
        ocr_predictions = self.run_ocr(images, langs)
        merged_tables = self.merge_split_tables(table_predictions, layout_predictions, page_idx=len(images))
        
        logger.info("Converting tables to JSON...")
        output_tables = []
        for table_idx, table in enumerate(merged_tables):
            logger.info(f"Processing table {table_idx + 1}/{len(merged_tables)}...")
            table_bbox = table["bbox"]
            ocr_text = []
            for page_idx, ocr_pred in enumerate(ocr_predictions):
                for line in ocr_pred["text_lines"]:
                    line_bbox = line["bbox"]
                    if (line_bbox[0] >= table_bbox[0] and line_bbox[2] <= table_bbox[2] and
                        line_bbox[1] >= table_bbox[1] and line_bbox[3] <= table_bbox[3]):
                        ocr_text.append(line["text"])
            
            refined_table = self.gemini_refine(table, "\n".join(ocr_text))
            
            table_json = {
                "table_id": table_idx,
                "page": table["page"],
                "rows": [],
                "headers": []
            }
            
            row_cells = {}
            for cell in table["cells"]:
                row_id = cell["row_id"]
                if row_id not in row_cells:
                    row_cells[row_id] = []
                row_cells[row_id].append(cell)
            
            for row_id in sorted(row_cells.keys()):
                cells = row_cells[row_id]
                row_data = [cell["text"] if cell["text"] is not None else "" for cell in sorted(cells, key=lambda x: x["col_id"])]
                if cells[0]["is_header"]:
                    table_json["headers"].append(row_data)
                else:
                    table_json["rows"].append(row_data)
            
            output_tables.append(table_json)
        
        output_path = os.path.join(output_dir, "tables.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_tables, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Pipeline completed. Extracted {len(output_tables)} tables. Results saved to {output_path}")
        return output_tables

def main():
    pipeline = TableExtractionPipeline()
    input_path = "2022-01-01-RATE-CGST_Schedule of Rates for Services-7-9.pdf"
    output_dir = "table_output"
    tables = pipeline.process_document(input_path, langs=["en"], output_dir=output_dir)

if __name__ == "__main__":
    main()