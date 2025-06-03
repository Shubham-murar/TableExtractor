import os
import time
from llama_parse import LlamaParse
import pandas as pd
import json
import re
from imgEnchance import enhance_table_image # Import the enhancement function
from dotenv import load_dotenv

# === CONFIGURATION ===
load_dotenv()
LLAMA_API_KEY = os.getenv('LLAMA_API_KEY')

if not LLAMA_API_KEY:
    print("Error: LLAMA_API_KEY not found in environment variables.")
    exit(1) # Your LlamaParse API Key
ORIGINAL_IMAGE_PATH = r'C:\Users\ACER\OneDrive\Desktop\TableMaker\Screenshot 2025-06-02 165116.png' # Path to your original image

# === ENHANCED IMAGE CONFIGURATION ===
# Directory where the enhanced image will be saved
ENHANCED_IMAGE_DIR = "enhanced_image_output"
# Filename for the enhanced image
ENHANCED_IMAGE_FILENAME = "enhanced_table_for_parsing.png"
# Full path to the enhanced image
ENHANCED_IMAGE_PATH = os.path.join(ENHANCED_IMAGE_DIR, ENHANCED_IMAGE_FILENAME)
# Sharpness factor for the enhancement
SHARPNESS_FACTOR_FOR_ENHANCEMENT = 2.0

# === OUTPUT FOLDER SETUP (for LlamaParse results like CSVs/JSON) ===
# Directory for the final parsed output files
PARSED_OUTPUT_DIR = os.path.join(os.getcwd(), "parsed_output")
os.makedirs(PARSED_OUTPUT_DIR, exist_ok=True)

# === STEP 1: ENHANCE THE IMAGE ===
print(f"Attempting to enhance image: {ORIGINAL_IMAGE_PATH}...")
try:
    enhance_table_image(
        image_path=ORIGINAL_IMAGE_PATH,
        output_dir=ENHANCED_IMAGE_DIR,
        output_name=ENHANCED_IMAGE_FILENAME,
        sharpness_factor=SHARPNESS_FACTOR_FOR_ENHANCEMENT
    )
    print(f"Image enhancement successful. Enhanced image saved at: {ENHANCED_IMAGE_PATH}")
    # Check if the enhanced file was actually created
    if not os.path.exists(ENHANCED_IMAGE_PATH):
        print(f"Error: Enhanced image file was not found at {ENHANCED_IMAGE_PATH} after enhancement call.")
        print("Please check the imgEnchance.py script and its output.")
        exit(1)
    # The image path for LlamaParse will now be the enhanced image
    IMAGE_TO_PARSE_PATH = ENHANCED_IMAGE_PATH
except Exception as e:
    print(f"An error occurred during image enhancement: {e}")
    print("Skipping enhancement and attempting to parse the original image.")
    IMAGE_TO_PARSE_PATH = ORIGINAL_IMAGE_PATH


# === INITIALIZE PARSER ===
parser = LlamaParse(
    api_key=LLAMA_API_KEY,
    result_type="markdown",  # Use markdown for table extraction
    parsing_instruction="Extract all tables with their headers and rows",
    max_timeout=300, # As per your original script
    verbose=True,
    preset="premium" # As per your original script
)

print(f"Initializing LlamaParse to parse image: {IMAGE_TO_PARSE_PATH}...")

# === PARSE WITH RETRY LOGIC ===
document = None # Initialize document to None
try:
    print(f"Loading and parsing data from: {IMAGE_TO_PARSE_PATH}")
    document = parser.load_data(IMAGE_TO_PARSE_PATH)
except Exception as e:
    print(f"Initial parsing attempt failed: {e}")
    for i in range(3): # Retry logic
        print(f"Retrying... Attempt {i + 1}/3")
        time.sleep(5)
        try:
            document = parser.load_data(IMAGE_TO_PARSE_PATH)
            print(f"Parsing successful on attempt {i + 1}.")
            break # Exit loop on success
        except Exception as e_retry:
            print(f"Attempt {i + 1} failed: {e_retry}")
            if i == 2: # Last attempt
                print("All parsing attempts failed for the image.")
                exit(1) # Exit if all retries fail

# === PROCESS RESULTS ===
if document and len(document) > 0:
    print("Processing parsed document...")

    # Save raw markdown output for debugging
    raw_output_path = os.path.join(PARSED_OUTPUT_DIR, "raw_markdown_output.txt")
    with open(raw_output_path, "w", encoding="utf-8") as f:
        f.write(document[0].text)
    print(f"Saved raw markdown output to {raw_output_path}")

    markdown_content = document[0].text
    tables = []
    table_lines = []
    in_table = False

    # Extract tables from markdown content
    for line in markdown_content.split('\n'):
        # A line is part of a table if it starts and ends with '|' and is not a separator
        if line.strip().startswith('|') and line.strip().endswith('|') and '---' not in line:
            if not in_table: # Start of a new table
                 table_lines = [] # Reset for new table
            in_table = True
            table_lines.append(line)
        elif in_table and (not line.strip().startswith('|') or not line.strip()): # End of current table
            in_table = False
            if table_lines:
                tables.append('\n'.join(table_lines))
                table_lines = [] # Prepare for next potential table
    
    if in_table and table_lines: # Catch table if it's the last content
        tables.append('\n'.join(table_lines))


    if tables:
        print(f"Found {len(tables)} table(s) in markdown. Converting to CSV...")
        for i, table_md in enumerate(tables):
            try:
                # Split rows and then split each row by '|', removing empty strings from start/end
                header_and_rows = [
                    [cell.strip() for cell in row.strip('|').split('|')]
                    for row in table_md.split('\n') if row.strip() and row.strip().count('|') > 0
                ]

                if not header_and_rows:
                    print(f"Table {i+1} is empty or malformed after splitting. Skipping.")
                    continue

                # The first list is headers, subsequent lists are data rows
                headers = header_and_rows[0]
                data_rows = header_and_rows[1:]
                
                df = pd.DataFrame(data_rows, columns=headers)

                # Function to protect accounting-style bracket values
                def protect_brackets(value):
                    if isinstance(value, str):
                        value = value.strip()
                        if re.match(r'^\(\s*\d[\d,\.]*\s*\)$', value): # e.g., (123), (1,234.56), ( 123 )
                            return f"'{value}" # Prefix with single quote
                    return value

                df = df.applymap(protect_brackets)

                csv_path = os.path.join(PARSED_OUTPUT_DIR, f"table_{i + 1}.csv")
                df.to_csv(csv_path, index=False)
                print(f"Saved table {i + 1} as {csv_path}")

            except Exception as e_table:
                print(f"Error processing table {i + 1}: {e_table}")
                problematic_table_path = os.path.join(PARSED_OUTPUT_DIR, f"problematic_table_{i + 1}.md")
                with open(problematic_table_path, "w", encoding="utf-8") as f:
                    f.write(table_md)
                print(f"Saved problematic table markdown to {problematic_table_path}")
    else:
        print("No tables found in markdown content using primary extraction method.")
        print("Attempting alternative approach with structured output (if LlamaParse supports it well for images)...")
        try:
            # Re-initialize parser for structured output if needed, or change result_type
            parser_structured = LlamaParse(
                api_key=LLAMA_API_KEY,
                result_type="structured", # Change to structured
                parsing_instruction="Extract all tables with their headers and rows",
                max_timeout=300,
                verbose=True,
                preset="premium"
            )
            document_structured = parser_structured.load_data(IMAGE_TO_PARSE_PATH)
            
            if document_structured and len(document_structured) > 0:
                # LlamaParse typically returns a list of Document objects.
                # The actual content might be in .text, .dict(), or specific attributes.
                # For "structured" type, it might be a dict-like object.
                # We'll try to save the .dict() representation.
                structured_data_to_save = document_structured[0].dict() if hasattr(document_structured[0], 'dict') else str(document_structured[0])

                structured_output_path = os.path.join(PARSED_OUTPUT_DIR, "structured_output.json")
                with open(structured_output_path, "w", encoding="utf-8") as f:
                    json.dump(structured_data_to_save, f, indent=2)
                print(f"Saved structured output to {structured_output_path}")
                print("Please inspect this JSON file for table data. Manual extraction might be needed from this structure.")
            else:
                print("No data returned from structured parsing attempt.")

        except Exception as e_structured:
            print(f"Structured output attempt also failed: {e_structured}")
elif document and len(document) == 0:
    print("Parser returned an empty document list. No data to process.")
else: # This case handles if document is None after retries
    print("No document was successfully parsed after all attempts.")

print("Processing complete.")
