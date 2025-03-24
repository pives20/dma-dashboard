import streamlit as st
from llama_index import VectorStoreIndex, SimpleDirectoryReader, ServiceContext
from llama_index.llms import OpenAI
import os
import tempfile

st.set_page_config(page_title="Leakage & NRW Chatbot", layout="centered")
st.title("💧 Leakage & NRW Chatbot")
st.markdown("Ask anything about leakage detection, NRW strategies, DMA management, and more.")

openai_api_key = st.secrets["OPENAI_API_KEY"] if "OPENAI_API_KEY" in st.secrets else st.text_input("Enter your OpenAI API Key", type="password")

if openai_api_key:
    uploaded_files = st.file_uploader("Upload relevant documents (PDF or TXT)", type=["pdf", "txt"], accept_multiple_files=True)

    if uploaded_files:
        with tempfile.TemporaryDirectory() as temp_dir:
            for uploaded_file in uploaded_files:
                with open(os.path.join(temp_dir, uploaded_file.name), "wb") as f:
                    f.write(uploaded_file.getbuffer())

            st.info("Indexing documents, please wait...")
            reader = SimpleDirectoryReader(temp_dir)
            docs = reader.load_data()

            service_context = ServiceContext.from_defaults(
                llm=OpenAI(model="gpt-3.5-turbo", api_key=openai_api_key)
            )
            index = VectorStoreIndex.from_documents(docs, service_context=service_context)
            chatbot = index.as_chat_engine()

            st.success("Documents indexed! You can now ask your questions.")

            user_question = st.text_input("Your question:", placeholder="e.g., What is the best way to size a DMA for leak detection?")

            if user_question:
                with st.spinner("Thinking..."):
                    response = chatbot.chat(user_question)
                    st.markdown(response.response)
else:
    st.warning("Please enter your OpenAI API key to continue.")
