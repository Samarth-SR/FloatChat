# backend.py
print("Backend script is starting...")
import sqlite3
import pandas as pd
import ollama
import re
import uuid
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS # Import CORS

# --- Database Setup (Runs once at startup) ---
# Using a file-based database is better for persistence than in-memory for a real app
conn = sqlite3.connect('ocean_data.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME NOT NULL, sensor_id TEXT NOT NULL,
    parameter_name TEXT NOT NULL, depth_m INTEGER, value REAL NOT NULL
);
''')

# Check if the table is empty before populating
cursor.execute("SELECT COUNT(*) FROM sensor_data")
if cursor.fetchone()[0] == 0:
    print("Database is empty. Populating with sample data...")
    def generate_data(sensor_id, param_name, depth, start_val, days):
        data = []
        current_time = datetime.now()
        for i in range(days * 24):
            timestamp = current_time - timedelta(hours=i)
            value = start_val + (i % 10) * 0.1 - 0.5 + (-1)**i * 0.2
            data.append((timestamp.isoformat(), sensor_id, param_name, depth, round(value, 2)))
        return data
    
    sensor_data = []
    sensor_data.extend(generate_data('BD10', 'Salinity', 30, 35, 10))
    sensor_data.extend(generate_data('BD10', 'Water Temperature', 30, 15, 10))
    sensor_data.extend(generate_data('CB02', 'Air Pressure', None, 1012, 10))
    sensor_data.extend(generate_data('AD08', 'Salinity', 30, 34, 10))
    cursor.executemany('INSERT INTO sensor_data (timestamp, sensor_id, parameter_name, depth_m, value) VALUES (?, ?, ?, ?, ?)', sensor_data)
    conn.commit()
    print("Sample data inserted.")
else:
    print("Database already contains data.")

# --- Data Dictionary (Runs once at startup) ---
params_df = pd.read_sql_query("SELECT DISTINCT parameter_name FROM sensor_data", conn)
available_parameters = params_df['parameter_name'].tolist()
sensors_df = pd.read_sql_query("SELECT DISTINCT sensor_id FROM sensor_data", conn)
available_sensors = sensors_df['sensor_id'].tolist()
parameter_list_str = ", ".join(f"'{p}'" for p in available_parameters)
sensor_list_str = ", ".join(f"'{s}'" for s in available_sensors)
db_schema = "Table: sensor_data, Columns: id, timestamp, sensor_id, parameter_name, depth_m, value"
print("✅ Database and Data Dictionary are ready.")


# --- Core AI and Logic Classes ---

class ConversationState:
    def __init__(self):
        self.conversation_history = []
        self.last_df = None
    def add_message(self, role, content): self.conversation_history.append({"role": role, "content": content})
    def get_history_string(self): return "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in self.conversation_history])

class OllamaLLM:
    def __init__(self, sql_model='sqlqwen3:4b', reasoning_model='gemma3:4b'):
        self.sql_model = sql_model
        self.reasoning_model = reasoning_model
    def classify_intent(self, history, new_query):
        prompt = f"Conversation history:\n{history}\n\nNew user query: \"{new_query}\"\n\nClassify the user's intent into ONE of the following categories: NEW_QUERY, REFINE_QUERY, ANALYZE_DATA.\n\nIntent:"
        response = ollama.chat(model=self.reasoning_model, messages=[{'role': 'user', 'content': prompt}])
        return response['message']['content'].strip()
    def generate_sql(self, history, schema, available_params, available_sensors):
        prompt = f"""You are an expert SQLite generation bot. Your sole purpose is to convert a user's request into a single, valid SQLite query.
### Database Schema
{schema}
### Available Data Values
- `parameter_name` can contain: {available_params}
- `sensor_id` can contain: {available_sensors}
### Conversation History
{history}
### STRICT Rules:
1.  **Map to Available Values:** Map the user's request (e.g., "saltiness") to the official `parameter_name` (e.g., 'Salinity').
2.  **Case-Insensitive WHERE:** All string comparisons MUST be case-insensitive using `LOWER()`.
3.  **Column Selection:** The query MUST select `timestamp` and `value`.
4.  **Output Format:** Your final output MUST ONLY be the raw SQL query, ending in a semicolon.
### Final SQLite Query:"""
        response = ollama.chat(model=self.sql_model, messages=[{'role': 'user', 'content': prompt}])
        raw_output = response['message']['content']
        matches = re.findall(r"(SELECT .*?;)", raw_output, re.IGNORECASE | re.DOTALL)
        if matches: return matches[-1].strip()
        raise ValueError("Could not extract a valid SQL query from the LLM's response.")
    def answer_from_data(self, df, question, conversation_history):
        """
        Uses the reasoning LLM to answer a question with a structured, scientific interpretation.
        """
        if df is None or df.empty:
            return "There is no data to analyze. Please ask for a new graph first."
    
        original_query = ""
        for msg in reversed(conversation_history):
            if msg.get("role") == "assistant" and "[GRAPH]" in msg.get("content", ""):
                original_query = msg["content"].replace("[GRAPH]", "").strip()
                break

        stats = ""
        if 'value' in df.columns:
            stats = f"""
            - Average (mean): {df['value'].mean():.2f}
            - Maximum value: {df['value'].max():.2f}
            - Minimum value: {df['value'].min():.2f}
            - Range (Max - Min): {df['value'].max() - df['value'].min():.2f}
            """

    # --- THIS IS THE NEW, "PRESENTATION-READY" PROMPT ---
        prompt = f"""
        You are an expert Oceanographer AI assistant. Your task is to provide a structured, scientific interpretation of a dataset in response to a user's question.

        ### Context
        - The user was originally shown a graph for the query: "{original_query}"
        - The user's current follow-up question is: "{question}"

        ### Provided Data Statistics
        {stats}

        ### Your Task
        Your response MUST be in Markdown format and follow this structure EXACTLY:

        ### Key Observation
        (A one-sentence summary of the most obvious pattern in the data. If it's cyclical, state that clearly.)

        ### Data Insights
        (A bulleted list of the most important statistics from the provided data.)

        ### Scientific Interpretation
        (A short paragraph explaining the likely real-world cause of the observed pattern. Based on your knowledge as an oceanographer, what could cause this? Mention the most probable cause first, like tidal cycles for salinity, and then other possibilities.)

        ### Next Steps
        (A one-sentence suggestion for what the user could ask next to investigate your interpretation. For example, "To confirm this, you could ask me to find data for 'Tidal Height' from the same sensor.")
        """
        response = ollama.chat(model=self.reasoning_model, messages=[{'role': 'user', 'content': prompt}])
        return response['message']['content']

def execute_query(sql_query):
    try:
        df = pd.read_sql_query(sql_query, conn)
        if df.empty: return None
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df.sort_values(by='timestamp')
    except Exception as e:
        print(f"SQL Error: {e}")
        return None

# --- Flask API Server ---

app = Flask(__name__)
CORS(app) # This is important to allow the Streamlit frontend to connect
SESSIONS = {}
llm = OllamaLLM()

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    data = request.get_json()
    user_message = data.get('message')
    session_id = data.get('session_id')

    if not session_id or session_id not in SESSIONS:
        session_id = str(uuid.uuid4())
        SESSIONS[session_id] = ConversationState()
    
    state = SESSIONS[session_id]
    state.add_message("user", user_message)

    # If this is the first message from the user in the session,
    # we can be 100% certain the intent is a NEW_QUERY.
    # This avoids any potential AI misclassification on the first turn.
    if len(state.conversation_history) == 1:
        intent = "NEW_QUERY"
    else:
        # For all subsequent messages, we use the AI to classify the intent.
        intent = llm.classify_intent(state.get_history_string(), user_message)
    # --- END OF FIX ---

    print(f"Session {session_id}: Intent={intent}, Message='{user_message}'")

    response_data = {}
    try:
        if intent in ["NEW_QUERY", "REFINE_QUERY"]:
            sql_query = llm.generate_sql(state.get_history_string(), db_schema, parameter_list_str, sensor_list_str)
            
            # Add the SQL query to the response for debugging
            print(f"  -> Generated SQL: {sql_query}")
            
            data_df = execute_query(sql_query)
            state.last_df = data_df
            
            if data_df is not None:
                y_label = "Value"
                match = re.search(r"LOWER\(parameter_name\) = '([^']*)'", sql_query, re.IGNORECASE)
                if match:
                    y_label = match.group(1).capitalize()

                response_data = { # type: ignore
                    "type": "graph", "graph_type": "line",
                    "x": data_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M').tolist(),
                    "y": data_df['value'].tolist(), "title": user_message,
                    "xlabel": "Timestamp", "ylabel": y_label
                }
                state.add_message("assistant", f"[GRAPH] {user_message}")
            else:
                response_data = {"type": "text", "content": "I couldn't find any data for that request. The database might not have records for that specific sensor and parameter."}
                state.add_message("assistant", response_data["content"])

        elif intent == "ANALYZE_DATA":
            answer = llm.answer_from_data(state.last_df, user_message,state.conversation_history)
            response_data = {"type": "text", "content": answer}
            state.add_message("assistant", answer)
            
        else:
            response_data = {"type": "text", "content": "I'm not sure how to handle that. Can you rephrase your question?"}

    except Exception as e:
        print(f"An error occurred in session {session_id}: {e}")
        return jsonify({"type": "text", "content": f"An internal error occurred: {e}"}), 500

    response_data['session_id'] = session_id
    return jsonify(response_data)

if __name__ == '__main__':
    print("✅ Script is being run directly. Starting Flask server...")
    # Use host='0.0.0.0' to make it accessible on your local network
    app.run(host='0.0.0.0', port=5000)