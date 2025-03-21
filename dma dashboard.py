import streamlit as st
import pandas as pd
import os

# Display available files to debug missing files
st.write("Available Files in Directory:", os.listdir("."))

# Function to load CSV safely
def load_csv(filename):
    if os.path.exists(filename):
        return pd.read_csv(filename)
    else:
        st.error(f"🚨 File not found: {filename}. Please upload it.")
        return None

# Load Data
dma_df = load_csv("dma_data.csv")
pipe_network_df = load_csv("pipe_network.csv")
pressure_df = load_csv("pressure_data.csv")
assets_df = load_csv("assets_data.csv")

# If any files are missing, stop execution
if None in [dma_df, pipe_network_df, pressure_df, assets_df]:
    st.stop()

# Normalize column names
for df in [dma_df, pipe_network_df, pressure_df, assets_df]:
    df.columns = df.columns.str.strip().str.lower()

st.success("✅ All files loaded successfully!")
