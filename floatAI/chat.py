import streamlit as st
from graph import render_graph
from map_display import render_map
import pandas as pd

def chat_ui():
    st.set_page_config(page_title="FloatChat AI")
    col1, col2 = st.columns([8, 2])
    with col1:
        st.title("FloatChat AI")
    with col2:
        if "messages" in st.session_state and st.session_state.messages:
            # chat history to dataframe
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
                label="⬇️ Download",
                data=csv_bytes,
                file_name="floatchat_history.csv",
                mime="text/csv",
                use_container_width=True
            )


    if "messages" not in st.session_state:
        st.session_state.messages = []

    # past messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("raw"):  # graph/map
                if msg["raw"]["type"] == "graph":
                    render_graph(msg["raw"])
                elif msg["raw"]["type"] == "map":
                    render_map(msg["raw"])
            else:
                st.write(msg["content"])

    # input box at bottom
    if user_input := st.chat_input("Type your message here..."):
        # show user message 
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        # get backend response
        response = dummy_backend(user_input)

        # show AI response 
        if response["type"] == "text":
            st.session_state.messages.append({"role": "assistant", "content": response["content"]})
            with st.chat_message("assistant"):
                st.write(response["content"])
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"[{response['type'].upper()} OUTPUT]",
                "raw": response
            })
            with st.chat_message("assistant"):
                if response["type"] == "graph":
                    render_graph(response)
                elif response["type"] == "map":
                    render_map(response)

def dummy_backend(user_input):
    # dummy
    if "ocean" in user_input:
        return {
            "type": "graph",
            "graph_type": "hist",
            "y": [5, 7, 8, 5, 6, 9, 10, 10, 8, 6, 5, 7, 6, 8, 9],
            "bin": 5,
            "title": "Temperature Frequency Distribution",
            "xlabel": "Temperature Ranges"
        }
    
    return {"type": "text", "content": "This is a normal chat response."}
