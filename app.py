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
            st.error(f"Skipping {section_base} due to parsing error.")
            continue

        tables_md = re.findall(r"\|.*\|(?:\n\|.*\|)+", markdown_text)
        if not tables_md:
            st.warning("No tables found in the parsed markdown.")
            continue

        for tbl_index, tbl in enumerate(tables_md, start=1):
            lines = [ln.strip() for ln in tbl.split("\n") if ln.strip() and not re.match(r"^\|[- :]+\|$", ln.strip())]
            if not lines:
                st.warning(f"Table {tbl_index} in {section_base} is empty or malformed.")
                continue

            raw_headers = [h.strip() for h in lines[0].strip("|").split("|")]

            # Step 2: Smart merge for title metadata like: "Quarterly Data | Millions of US $..."
            joined_header = " | ".join(raw_headers[:2])
            non_header_keywords = ["quarterly", "millions", "us $", "except per share", "data", "$"]
            if all(any(kw in h.lower() for kw in non_header_keywords) for h in raw_headers[:2]):
                st.caption("🛠 Merging descriptive title headers into one.")
                raw_headers = [joined_header] + raw_headers[2:]

            # 🔧 Smart header merge if the first 2 columns are mistakenly split
            if len(raw_headers) > 2:
                first_data_row = lines[1].strip("|").split("|")
                if len(raw_headers) == len(first_data_row) + 1:
                    junk_candidate = raw_headers[1].strip().lower()
                    if junk_candidate in ["", "-", "n/a", "na", "—", "|"] or re.fullmatch(r"[\s\|\-\.█▁▂▃▄▅▆▇]*", junk_candidate):
                        st.caption("🛠 Merging first two headers: split title detected.")
                        raw_headers[0] = f"{raw_headers[0]} {raw_headers[1]}"
                        raw_headers.pop(1)

            # 🔁 Handle duplicate headers
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

            # 🔁 Build rows, pad/truncate mismatches
            rows = []
            mismatch_count = 0
            for row_num, row in enumerate(lines[1:], start=1):
                cols = [c.strip() for c in row.strip("|").split("|")]
                original_len = len(cols)
                if len(cols) < len(headers):
                    cols += [""] * (len(headers) - len(cols))
                elif len(cols) > len(headers):
                    cols = cols[:len(headers)]
                if original_len != len(headers):
                    mismatch_count += 1
                    st.info(f"⚠️ Row {row_num} in Table {tbl_index} had {original_len} cols; adjusted to {len(headers)}.")
                rows.append(cols)

            # 🔁 Transpose to work column-wise
            transposed = list(zip(*rows))

            # 🧠 Skip chart/junk/duplicate columns
            valid_col_indices = []
            for idx, col in enumerate(transposed):
                sample = [c.strip().lower() for c in col if c.strip()]

                # Skip visual-only/empty content
                if not sample or all(re.fullmatch(r"[.\-|\s█▁▂▃▄▅▆▇]+", val) for val in sample):
                    st.caption(f"🚫 Skipping column '{headers[idx]}' — empty or chart content.")
                    continue

                # Skip duplicate of first column
                if idx > 0:
                    col_str = "|".join(col).strip().lower()
                    first_col_str = "|".join(transposed[0]).strip().lower()
                    if col_str == first_col_str:
                        st.caption(f"🚫 Skipping column '{headers[idx]}' — duplicate of first column.")
                        continue

                valid_col_indices.append(idx)

            # Filter headers and rows
            filtered_headers = [headers[i] for i in valid_col_indices]
            filtered_rows = [[row[i] for i in valid_col_indices] for row in rows]

            # ✅ Build DataFrame
            df = pd.DataFrame(filtered_rows, columns=filtered_headers)
            df = df.applymap(lambda v: f"'{v}" if isinstance(v, str) and re.match(r"^\(\s*\d", v.strip()) else v)

            st.subheader(f"Table {tbl_index}")
            if mismatch_count > 0:
                st.caption(f"✅ Adjusted {mismatch_count} row(s) due to column mismatch.")
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












