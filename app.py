import streamlit as st
import os
import time
from llama_parse import LlamaParse
import pandas as pd
import json
import re
from PIL import Image # For image handling with Streamlit

# Assuming imgEnchance.py is in the same directory
try:
    from imgEnchance import enhance_table_image
except ImportError:
    st.error("Error: imgEnchance.py not found. Make sure it's in the same directory as app.py.")
    enhance_table_image = None # Placeholder if import fails

# === CONFIGURATION ===
# These will be set dynamically or are fixed for the app
SHARPNESS_FACTOR_FOR_ENHANCEMENT = 2.0
APP_TEMP_DIR = "streamlit_temp" # For storing temporary files for this app session
ENHANCED_IMAGE_DIR_NAME = "enhanced_image_output"
PARSED_OUTPUT_DIR_NAME = "parsed_output"

# Create base temporary directories if they don't exist
os.makedirs(APP_TEMP_DIR, exist_ok=True)
ENHANCED_IMAGE_BASE_DIR = os.path.join(APP_TEMP_DIR, ENHANCED_IMAGE_DIR_NAME)
PARSED_OUTPUT_BASE_DIR = os.path.join(APP_TEMP_DIR, PARSED_OUTPUT_DIR_NAME)
os.makedirs(ENHANCED_IMAGE_BASE_DIR, exist_ok=True)
os.makedirs(PARSED_OUTPUT_BASE_DIR, exist_ok=True)


def process_and_extract(uploaded_file, llama_api_key):
    """
    Main function to enhance image, parse tables, and return paths to CSVs.
    """
    if uploaded_file is None or not llama_api_key:
        return []

    # Create unique subdirectories for this run to avoid clashes if multiple users run (less critical for local)
    run_id = str(int(time.time())) # Simple unique ID for this processing run
    current_enhanced_dir = os.path.join(ENHANCED_IMAGE_BASE_DIR, run_id)
    current_parsed_dir = os.path.join(PARSED_OUTPUT_BASE_DIR, run_id)
    os.makedirs(current_enhanced_dir, exist_ok=True)
    os.makedirs(current_parsed_dir, exist_ok=True)

    # Save uploaded file temporarily
    original_image_filename = uploaded_file.name
    original_image_path = os.path.join(current_enhanced_dir, original_image_filename)
    with open(original_image_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.info(f"Uploaded image saved to: {original_image_path}")

    # --- STEP 1: ENHANCE THE IMAGE ---
    enhanced_image_filename = f"enhanced_{original_image_filename}"
    enhanced_image_path = os.path.join(current_enhanced_dir, enhanced_image_filename)
    image_to_parse_path = original_image_path # Default to original

    if enhance_table_image: # Check if function was imported successfully
        st.write(f"Attempting to enhance image: {original_image_path}...")
        try:
            enhance_table_image(
                image_path=original_image_path,
                output_dir=current_enhanced_dir, # Save in run-specific enhanced dir
                output_name=enhanced_image_filename,
                sharpness_factor=SHARPNESS_FACTOR_FOR_ENHANCEMENT
            )
            if os.path.exists(enhanced_image_path):
                st.success(f"Image enhancement successful. Enhanced image: {enhanced_image_path}")
                image_to_parse_path = enhanced_image_path
            else:
                st.warning(f"Enhanced image file not found at {enhanced_image_path}. Using original.")
        except Exception as e:
            st.error(f"An error occurred during image enhancement: {e}")
            st.info("Skipping enhancement and attempting to parse the original image.")
    else:
        st.warning("Image enhancement function not available. Using original image for parsing.")


    # --- INITIALIZE PARSER ---
    try:
        parser = LlamaParse(
            api_key=llama_api_key,
            result_type="markdown",
            parsing_instruction="Extract all tables with their headers and rows",
            max_timeout=300,
            verbose=True,
            preset="premium"
        )
    except Exception as e:
        st.error(f"Failed to initialize LlamaParse. Ensure API key is valid. Error: {e}")
        return [], None # Return empty list of csvs and no raw markdown

    st.info(f"Initializing LlamaParse to parse image: {image_to_parse_path}...")

    # --- PARSE WITH RETRY LOGIC ---
    document = None
    raw_markdown_content = None
    with st.spinner(f"Parsing image: {os.path.basename(image_to_parse_path)}... This may take a moment."):
        try:
            st.write(f"Loading and parsing data from: {os.path.basename(image_to_parse_path)}")
            document = parser.load_data(image_to_parse_path)
        except Exception as e:
            st.error(f"Initial parsing attempt failed: {e}")
            for i in range(3): # Retry logic
                st.warning(f"Retrying... Attempt {i + 1}/3")
                time.sleep(5)
                try:
                    document = parser.load_data(image_to_parse_path)
                    st.success(f"Parsing successful on attempt {i + 1}.")
                    break
                except Exception as e_retry:
                    st.error(f"Attempt {i + 1} failed: {e_retry}")
                    if i == 2:
                        st.error("All parsing attempts failed for the image.")
                        return [], None # Return empty list of csvs and no raw markdown

    # --- PROCESS RESULTS ---
    csv_paths = []
    if document and len(document) > 0:
        st.success("Document parsed successfully. Processing results...")

        raw_markdown_content = document[0].text
        # Save raw markdown output for debugging (optional, could be a download button too)
        raw_output_path = os.path.join(current_parsed_dir, "raw_markdown_output.md")
        with open(raw_output_path, "w", encoding="utf-8") as f:
            f.write(raw_markdown_content)
        st.info(f"Saved raw markdown output to server at: {raw_output_path}") # For server-side log

        markdown_content = document[0].text
        tables_md = [] # Renamed from 'tables' to avoid conflict
        table_lines = []
        in_table = False

        for line in markdown_content.split('\n'):
            if line.strip().startswith('|') and line.strip().endswith('|') and '---' not in line:
                if not in_table:
                    table_lines = []
                in_table = True
                table_lines.append(line)
            elif in_table and (not line.strip().startswith('|') or not line.strip()):
                in_table = False
                if table_lines:
                    tables_md.append('\n'.join(table_lines))
                    table_lines = []
        if in_table and table_lines:
            tables_md.append('\n'.join(table_lines))

        if tables_md:
            st.write(f"Found {len(tables_md)} table(s) in markdown. Converting to CSV...")
            for i, table_md_content in enumerate(tables_md):
                try:
                    header_and_rows = [
                        [cell.strip() for cell in row.strip('|').split('|')]
                        for row in table_md_content.split('\n') if row.strip() and row.strip().count('|') > 0
                    ]

                    if not header_and_rows:
                        st.warning(f"Table {i+1} is empty or malformed after splitting. Skipping.")
                        continue

                    headers = header_and_rows[0]
                    data_rows = header_and_rows[1:]
                    
                    df = pd.DataFrame(data_rows, columns=headers)

                    def protect_brackets(value):
                        if isinstance(value, str):
                            value = value.strip()
                            if re.match(r'^\(\s*\d[\d,\.]*\s*\)$', value):
                                return f"'{value}"
                        return value

                    df = df.applymap(protect_brackets)

                    csv_filename = f"table_{i + 1}.csv"
                    csv_path = os.path.join(current_parsed_dir, csv_filename)
                    df.to_csv(csv_path, index=False)
                    csv_paths.append({"path": csv_path, "name": csv_filename, "df": df})
                    st.success(f"Processed and saved table {i + 1} as {csv_filename}")

                except Exception as e_table:
                    st.error(f"Error processing table {i + 1}: {e_table}")
                    problematic_table_path = os.path.join(current_parsed_dir, f"problematic_table_{i + 1}.md")
                    with open(problematic_table_path, "w", encoding="utf-8") as f:
                        f.write(table_md_content)
                    st.warning(f"Saved problematic table markdown to {problematic_table_path}")
        else:
            st.warning("No tables found in markdown content using primary extraction method.")
            # Fallback for structured output (optional)
            # You might want to add a button or checkbox to enable this explicitly
            # as it involves another API call. For now, it's skipped for brevity
            # but the logic from your original script can be adapted here.

    elif document and len(document) == 0:
        st.warning("Parser returned an empty document list. No data to process.")
    else:
        st.error("No document was successfully parsed after all attempts.")

    return csv_paths, raw_markdown_content


# --- STREAMLIT UI ---
st.set_page_config(layout="wide")
st.title("🖼️ Image Table Extractor 📊")

st.sidebar.header("Configuration")
llama_api_key_input = st.sidebar.text_input("Enter your LlamaParse API Key (llx-...)", type="password")

st.sidebar.markdown("---")
st.sidebar.header("Upload Image")
uploaded_file = st.sidebar.file_uploader("Choose an image file (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"])

if 'processed_csvs' not in st.session_state:
    st.session_state.processed_csvs = []
if 'raw_markdown' not in st.session_state:
    st.session_state.raw_markdown = None


if st.sidebar.button("Extract Tables from Image", disabled=(not uploaded_file or not llama_api_key_input)):
    if uploaded_file and llama_api_key_input:
        with st.spinner("Processing image and extracting tables..."):
            st.session_state.processed_csvs, st.session_state.raw_markdown = process_and_extract(uploaded_file, llama_api_key_input)
        if not st.session_state.processed_csvs and not st.session_state.raw_markdown:
            st.error("Processing failed to produce any downloadable results.")
        elif not st.session_state.processed_csvs and st.session_state.raw_markdown:
            st.warning("No tables were extracted into CSVs, but raw markdown is available.")
        else:
            st.success("Processing complete! See results below.")
    elif not llama_api_key_input:
        st.sidebar.error("Please enter your LlamaParse API Key.")
    elif not uploaded_file:
        st.sidebar.error("Please upload an image file.")


# --- Display Results ---
if st.session_state.processed_csvs:
    st.header("Extracted Tables")
    for i, csv_info in enumerate(st.session_state.processed_csvs):
        st.subheader(f"Table {i+1} ({csv_info['name']})")
        
        # Display DataFrame
        if csv_info['df'] is not None and not csv_info['df'].empty:
            st.dataframe(csv_info['df'])
        else:
            st.write("Preview not available or table is empty.")

        # Download button for CSV
        try:
            with open(csv_info['path'], "rb") as fp:
                st.download_button(
                    label=f"Download {csv_info['name']}",
                    data=fp,
                    file_name=csv_info['name'],
                    mime="text/csv",
                    key=f"download_csv_{i}"
                )
        except FileNotFoundError:
            st.error(f"Could not find {csv_info['name']} for download. It might have been cleaned up or not generated correctly.")
        st.markdown("---")

elif st.session_state.raw_markdown and not st.session_state.processed_csvs: # Only show if no CSVs but markdown exists
    st.header("Raw Markdown Output (No Tables Converted to CSV)")
    st.text_area("Markdown Content", st.session_state.raw_markdown, height=300)
    
    # Allow download of raw markdown
    st.download_button(
        label="Download Raw Markdown (.md)",
        data=st.session_state.raw_markdown,
        file_name="raw_markdown_output.md",
        mime="text/markdown",
        key="download_raw_md"
    )

if uploaded_file:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Uploaded Image Preview:")
    try:
        img = Image.open(uploaded_file)
        st.sidebar.image(img, caption="Uploaded Image", use_column_width=True)
    except Exception as e:
        st.sidebar.error(f"Could not display image preview: {e}")

st.markdown("---")
st.markdown("Built with [Streamlit](https://streamlit.io/) & [LlamaParse](https://github.com/run-llama/llama_parse)")