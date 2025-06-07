import os
import time
import streamlit as st
import pandas as pd
import re
from llama_parse import LlamaParse
from imgEnchance import enhance_multiple_images
import tempfile

# === STREAMLIT LAYOUT & API KEY INPUT ===
st.set_page_config(page_title="🧾 Image-to-Table Extractor", layout="wide")
st.title("Image-to-Table Extractor")
st.markdown("Enter your LlamaParse API key, choose a parsing preset, then upload table images to extract and display each table separately, and combine into a CSV with separate sections.")

# API Key Input
api_key = st.text_input(
    "LlamaParse API Key",
    type="password",
    placeholder="Enter your API key"
)
if not api_key:
    st.warning("Please provide your LlamaParse API key.")
    st.stop()

# Preset Selection
preset_choice = st.radio(
    "Select Parsing Preset (credits per image)",
    options=["Balanced (3 credits)", "Premium (45 credits)"],
    index=1
)
preset_map = {"Balanced (3 credits)": "balanced", "Premium (45 credits)": "premium"}
selected_preset = preset_map[preset_choice]

# Directories
ENHANCED_IMAGE_DIR = "enhanced_image_output"
PARSED_OUTPUT_DIR = os.path.join(os.getcwd(), "parsed_output")
os.makedirs(ENHANCED_IMAGE_DIR, exist_ok=True)
os.makedirs(PARSED_OUTPUT_DIR, exist_ok=True)

st.markdown("---")
st.markdown("### 1. Upload Images of Tables")
uploaded_files = st.file_uploader(
    "Select PNG/JPG images containing tables",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True
)
if not uploaded_files:
    st.info("Awaiting image uploads...")
    st.stop()

st.markdown("### 2. Enhance, Parse & Display")
if st.button("Run Extraction"):
    # Save uploads
    tmp_dir = tempfile.mkdtemp(prefix="uploaded_")
    image_paths = []
    for up in uploaded_files:
        path = os.path.join(tmp_dir, up.name)
        with open(path, "wb") as f:
            f.write(up.getbuffer())
        image_paths.append(path)

    st.info("Enhancing images...")
    enhanced_paths = enhance_multiple_images(
        image_paths=image_paths,
        output_dir=ENHANCED_IMAGE_DIR,
        sharpness_factor=2.0
    )
    if not enhanced_paths:
        st.error("Enhancement failed. Please retry.")
        st.stop()

    all_tables = []  # list of (section_title, df)

    def parse_tables(md):
        return re.findall(r"\|.*\|(?:\n\|.*\|)+", md)

    # Process each enhanced image with its own index
    for img_index, img in enumerate(enhanced_paths, start=1):
        section_base = f"enhanced_image_{img_index}.png"
        st.header(f"Image: {section_base} | Preset: {preset_choice}")
        parser = LlamaParse(
            api_key=api_key,
            result_type="markdown",
            parsing_instruction="Extract all tables with their headers and rows",
            max_timeout=300,
            verbose=False,
            preset=selected_preset
        )
        markdown_text = None
        for _ in range(3):
            try:
                docs = parser.load_data(img)
                if docs and docs[0].text:
                    markdown_text = docs[0].text
                    break
            except Exception:
                time.sleep(1)
        if not markdown_text:
            st.error(f"Skipping {section_base}")
            continue
        tables_md = parse_tables(markdown_text)
        if not tables_md:
            st.warning("No tables found.")
            continue
        for tbl_index, tbl in enumerate(tables_md, start=1):
            lines = [ln.strip() for ln in tbl.split("\n") if ln.strip() and not re.match(r"^\|[- :]+\|$", ln.strip())]
            raw_headers = [h.strip() for h in lines[0].strip("|").split("|")]
            headers = []
            counts = {}
            headers = []
            counts = {}
            for h in raw_headers:
                if not h:
                    h = "Unnamed"
                if h in counts:
                    counts[h] += 1
                    headers.append(f"{h} ({counts[h]})")
                else:
                    counts[h] = 1
                    headers.append(h)
            rows = [[c.strip() for c in row.strip("|").split("|")] for row in lines[1:]]
            df = pd.DataFrame(rows, columns=headers)
            df = df.applymap(lambda v: f"'{v}" if isinstance(v, str) and re.match(r"^\(\s*\d", v.strip()) else v)
            st.subheader(f"Table {tbl_index}")
            st.dataframe(df)
            section_title = f"# {section_base} - Table {tbl_index}"
            all_tables.append((section_title, df))

    # Combine tables into CSV with refined titles
    if all_tables:
        csv_path = os.path.join(PARSED_OUTPUT_DIR, "combined_table.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            for title, df in all_tables:
                f.write(f"{title}\n")
                df.to_csv(f, index=False)
                f.write("\n")
        st.success("Extraction complete. Combined CSV ready.")
        with open(csv_path, 'rb') as f:
            st.download_button(
                "Download Combined CSV",
                data=f,
                file_name="combined_table.csv",
                mime='text/csv'
            )
    else:
        st.warning("No tables extracted.")
else:
    st.info("Click 'Run Extraction' to process the uploaded images.")



















































