# app.py
import streamlit as st
import gspread
import pandas as pd
import re
import io

from gspread.exceptions import WorksheetNotFound
from datetime import datetime
from google.oauth2.service_account import Credentials
from gspread_formatting import format_cell_range, cellFormat, NumberFormat

# -----------------------------
# CONFIG
# -----------------------------
SPREADSHEET_ID = "183otH2UiDwu7K4ZQmPDF2Xce4C94epilkWbexvXf18Q"

# -----------------------------
# Authenticate Google Sheets via Streamlit Secrets
# -----------------------------
creds_dict = st.secrets["google"]
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.Client(auth=creds)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)

st.set_page_config(page_title="ROAS & Lead Sheet Builder")
st.title("📊 ROAS Automation Dashboard")

# -----------------------------
# Helpers
# -----------------------------
def normalize_phone(phone):
    if not phone:
        return ""
    d = re.sub(r"\D", "", str(phone))
    if d.startswith("92") and len(d) == 12:
        d = "0" + d[2:]
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    if len(d) == 10:
        return f"({d[:3]}) {d[3:6]}-{d[6:]}"
    return d

def parse_date(val):
    if not val:
        return None
    try:
        return pd.to_datetime(val)
    except Exception:
        return None

# -----------------------------
# Global detection state
# -----------------------------
if "input_type" not in st.session_state:
    st.session_state.input_type = None  # "MCAI" or "WHATCONVERTS"

# -----------------------------
# Upload function (auto-detect)
# -----------------------------
def upload_to_sheet(sheet_name, file, mode="replace"):
    try:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file, dtype=str, keep_default_na=False, header=None)
        else:
            df = pd.read_excel(file, dtype=str, engine="openpyxl", keep_default_na=False, header=None)

        header = df.iloc[0].tolist()

        is_mcai = all(x in header for x in ["Date Created (PST)", "Final AI Attribution", "Potential Lead?"])
        is_wc = all(x in header for x in ["Account", "Profile", "Quotable"])

        if is_mcai:
            mandatory_fields = ["Date Created (PST)", "Lead ID", "Lead Type", "Answered?", "Sales Call Score"]
            st.session_state.input_type = "MCAI"
        elif is_wc:
            mandatory_fields = ["Lead ID", "Account", "Profile"]
            st.session_state.input_type = "WHATCONVERTS"
        else:
            st.error("❌ Unknown file format. Must be MCAI or WhatConverts export.")
            return

        missing_fields = [f for f in mandatory_fields if f not in header]
        if missing_fields:
            st.error(f"❌ Mandatory Fields Missing: {', '.join(missing_fields)}")
            return

        if mode == "replace":
            try:
                old_ws = spreadsheet.worksheet(sheet_name)
                spreadsheet.del_worksheet(old_ws)
            except WorksheetNotFound:
                pass

            rows, cols = df.shape
            ws = spreadsheet.add_worksheet(title=sheet_name, rows=str(rows + 10), cols=str(cols + 5))
            ws.update(df.values.tolist(), value_input_option="USER_ENTERED")
            st.success(f"✅ {sheet_name} replaced successfully.")

        elif mode == "append":
            ws = spreadsheet.worksheet(sheet_name)
            append_rows = df.values.tolist()[1:]
            ws.append_rows(append_rows, value_input_option="USER_ENTERED")
            st.success(f"✅ Rows appended to {sheet_name}.")

    except Exception as e:
        st.error(f"❌ Failed to upload to {sheet_name}: {e}")

# -----------------------------
# UI badge for detection
# -----------------------------
def show_input_type_badge():
    if st.session_state.input_type == "MCAI":
        st.success("🧠 Detected Input Type: MCAI Export")
    elif st.session_state.input_type == "WHATCONVERTS":
        st.info("📞 Detected Input Type: WhatConverts Export")
    else:
        st.warning("⚠ Input type not detected yet")
# -----------------------------
# PROCESS UPLOADED FILE
# -----------------------------
if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    st.write("Preview of uploaded file:")
    st.dataframe(df.head())

    # Detect file type by column names
    is_mcai = "Final AI Attribution" in df.columns
    is_whatconverts = "Quotable" in df.columns

    if not (is_mcai or is_whatconverts):
        st.error("Unknown file format. Must be MCAI or WhatConverts export.")
        st.stop()

    # -----------------------------
    # STANDARDIZE DATA
    # -----------------------------
    if is_mcai:
        st.info("Detected MCAI file")

        # Create missing WhatConverts columns
        if "Quotable" not in df.columns:
            df["Quotable"] = ""

        if "Notes" not in df.columns:
            df["Notes"] = ""

        # Move MCAI fields into WhatConverts fields
        df["Quotable"] = df["Potential Lead?"]
        df["Notes"] = df["Final AI Attribution"]

        # Optional: rename Date field
        if "Date Created (PST)" in df.columns:
            df["Date"] = df["Date Created (PST)"]

    if is_whatconverts:
        st.info("Detected WhatConverts file")

        # Make sure required columns exist
        if "Quotable" not in df.columns:
            df["Quotable"] = ""

        if "Notes" not in df.columns:
            df["Notes"] = ""

    # -----------------------------
    # CLEAN DATA (OPTIONAL)
    # -----------------------------
    df["Quotable"] = df["Quotable"].astype(str).str.strip()
    df["Notes"] = df["Notes"].astype(str).str.strip()

    st.success("Data processed successfully!")
# -----------------------------
# UPLOAD TO GOOGLE SHEETS
# -----------------------------
if uploaded_file is not None and 'df' in locals():

    if st.button("Upload to Google Sheet"):

        # Clear old data
        try:
            worksheet = sh.worksheet("WhatConvertsExport")
            worksheet.clear()
        except WorksheetNotFound:
            worksheet = sh.add_worksheet(title="WhatConvertsExport", rows="1000", cols="50")

        # Write headers + data
        data = [df.columns.tolist()] + df.values.tolist()
        worksheet.update("A1", data)

        # -----------------------------
        # FORMAT HEADER ROW
        # -----------------------------
        header_format = cellFormat(
            backgroundColor={"red": 0.85, "green": 0.85, "blue": 0.85},
            textFormat={"bold": True}
        )

        format_cell_range(worksheet, "A1:Z1", header_format)

        # Auto resize columns
        worksheet.format("A:Z", {
            "horizontalAlignment": "LEFT"
        })

        st.success("✅ Data uploaded successfully to 'WhatConvertsExport' sheet!")
