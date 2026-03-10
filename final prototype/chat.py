# chat_ui.py

import streamlit as st
from graph import render_graph
from map_display import render_map
import pandas as pd
import requests # Import the requests library

# --- Configuration ---
BACKEND_URL = "http://localhost:5000/chat"

# --- Backend Communication ---
def get_backend_response(user_input):
    """Sends the user's message to the Flask backend and gets the response."""
    
    # Get the session_id from Streamlit's session state
    session_id = st.session_state.get("session_id", None)
    
    payload = {
        "message": user_input,
        "session_id": session_id
    }
    
    try:
        response = requests.post(BACKEND_URL, json=payload)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        # The backend response is the JSON we need
        backend_data = response.json()
        
        # Store the new session_id for future requests
        st.session_state.session_id = backend_data.get("session_id")
        
        return backend_data
        
    except requests.exceptions.RequestException as e:
        # Handle connection errors, timeouts, etc.
        return {"type": "text", "content": f"Error connecting to the backend: {e}"}


# --- Main UI ---
def chat_ui():
    st.set_page_config(page_title="FloatChat AI")
    col1, col2 = st.columns([8, 2])
    with col1:
        st.title("FloatChat AI")
    with col2:
        if "messages" in st.session_state and st.session_state.messages:
            export_data = []
            for msg in st.session_state.messages:
                export_data.append({
                    "role": msg["role"],
                    "content": msg.get("content", ""),
                    "extra": str(msg.get("raw", "")) if msg.get("raw") else ""
                })
            df = pd.DataFrame(export_data)
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download", data=csv_bytes, file_name="floatchat_history.csv",
                mime="text/csv", use_container_width=True
            )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("raw"):
                if msg["raw"]["type"] == "graph":
                    render_graph(msg["raw"])
                elif msg["raw"]["type"] == "map":
                    render_map(msg["raw"])
            else:
                st.write(msg["content"])

    if user_input := st.chat_input("Type your message here..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        # --- THIS IS THE CRITICAL CHANGE ---
        # Replace the dummy backend with the real one
        with st.spinner("Thinking..."):
            response = get_backend_response(user_input)

        if response.get("type") == "text":
            st.session_state.messages.append({"role": "assistant", "content": response["content"]})
            with st.chat_message("assistant"):
                st.write(response["content"])
        elif response.get("type") == "graph":
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"[GRAPH] {response.get('title', 'Here is the graph you requested.')}",
                "raw": response
            })
            with st.chat_message("assistant"):
                render_graph(response)
        else:
            # Handle errors or unknown types
            error_content = response.get("content", "An unknown error occurred.")
            st.session_state.messages.append({"role": "assistant", "content": error_content})
            with st.chat_message("assistant"):
                st.error(error_content)