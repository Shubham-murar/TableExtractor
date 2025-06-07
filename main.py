import os
import time
from llama_parse import LlamaParse
import pandas as pd
import re
from dotenv import load_dotenv
from imgEnchance import enhance_multiple_images

# === CONFIGURATION ===
load_dotenv()
LLAMA_API_KEY = os.getenv('LLAMA_API_KEY')
if not LLAMA_API_KEY:
    print("Error: LLAMA_API_KEY not found.")
    exit(1)

# === INPUT IMAGES ===
ORIGINAL_IMAGE_PATHS = [
    r'C:\Users\ACER\OneDrive\Desktop\TableMaker\Screenshot 2025-06-02 165116.png',
    r'C:\Users\ACER\OneDrive\Desktop\TableMaker\Screenshot 2025-06-02 181926.png',
    r'C:\Users\ACER\OneDrive\Desktop\TableMaker\Screenshot 2025-06-04 152315.png'
]

# === OUTPUT CONFIGURATION ===
ENHANCED_IMAGE_DIR = "enhanced_image_output"
SHARPNESS_FACTOR_FOR_ENHANCEMENT = 2.0
PARSED_OUTPUT_DIR = os.path.join(os.getcwd(), "parsed_output")
os.makedirs(PARSED_OUTPUT_DIR, exist_ok=True)

# === ENHANCE IMAGES ===
print("Enhancing images...")
enhanced_image_paths = enhance_multiple_images(
    image_paths=ORIGINAL_IMAGE_PATHS,
    output_dir=ENHANCED_IMAGE_DIR,
    sharpness_factor=SHARPNESS_FACTOR_FOR_ENHANCEMENT
)

if not enhanced_image_paths:
    print("No images enhanced successfully. Exiting.")
    exit(1)

# === INITIALIZE PARSER ===
parser = LlamaParse(
    api_key=LLAMA_API_KEY,
    result_type="markdown",
    parsing_instruction="Extract all tables with their headers and rows",
    max_timeout=300,
    verbose=True,
    preset="premium"
)

combined_df = pd.DataFrame()

def parse_tables_from_markdown(markdown_text):
    tables = []
    table_lines = []
    in_table = False

    for line in markdown_text.split('\n'):
        if line.strip().startswith('|') and line.strip().endswith('|') and '---' not in line:
            if not in_table:
                table_lines = []
            in_table = True
            table_lines.append(line)
        elif in_table and (not line.strip().startswith('|') or not line.strip()):
            in_table = False
            if table_lines:
                tables.append('\n'.join(table_lines))
                table_lines = []
    if in_table and table_lines:
        tables.append('\n'.join(table_lines))
    return tables

for img_path in enhanced_image_paths:
    print(f"\nParsing image: {img_path}")
    document = None
    try:
        document = parser.load_data(img_path)
    except Exception as e:
        print(f"Initial parse failed: {e}")
        for i in range(3):
            print(f"Retry {i+1}/3")
            time.sleep(5)
            try:
                document = parser.load_data(img_path)
                break
            except Exception as e_retry:
                print(f"Retry {i+1} failed: {e_retry}")
        if not document:
            continue

    if document and len(document) > 0:
        markdown_content = document[0].text

        # Save raw output for each image
        base_name = os.path.basename(img_path).replace('.png', '')
        raw_output_path = os.path.join(PARSED_OUTPUT_DIR, f"{base_name}_markdown_output.txt")
        with open(raw_output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        tables = parse_tables_from_markdown(markdown_content)

        for i, table_md in enumerate(tables):
            try:
                header_and_rows = [
                    [cell.strip() for cell in row.strip('|').split('|')]
                    for row in table_md.split('\n') if row.strip() and row.strip().count('|') > 0
                ]
                if not header_and_rows:
                    continue

                headers = header_and_rows[0]
                data_rows = header_and_rows[1:]
                df = pd.DataFrame(data_rows, columns=headers)

                def protect_brackets(value):
                    if isinstance(value, str) and re.match(r'^\(\s*\d[\d,\.]*\s*\)$', value.strip()):
                        return f"'{value.strip()}"
                    return value

                df = df.applymap(protect_brackets)
                combined_df = pd.concat([combined_df, df], ignore_index=True)
            except Exception as e_table:
                print(f"Error processing table {i+1}: {e_table}")
                error_path = os.path.join(PARSED_OUTPUT_DIR, f"{base_name}_table_{i+1}_error.md")
                with open(error_path, "w", encoding="utf-8") as f:
                    f.write(table_md)

# === SAVE FINAL CSV ===
final_csv_path = os.path.join(PARSED_OUTPUT_DIR, "combined_table.csv")
combined_df.to_csv(final_csv_path, index=False)
print(f"\n✅ Combined CSV saved at: {final_csv_path}")
