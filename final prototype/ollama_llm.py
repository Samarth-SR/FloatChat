import ollama
import re

class OllamaLLM:
    """A class to interact with local Ollama models."""
    def __init__(self, sql_model='qwen3:4b', reasoning_model='gemma3:4b'):
        self.sql_model = sql_model
        self.reasoning_model = reasoning_model
        print(f"LLM handler initialized. Using '{self.sql_model}' for SQL and '{self.reasoning_model}' for reasoning.")

    def ask_for_confirmation(self, query, schema):
        # This function is stable.
        prompt = f"""
        You are an expert assistant. Your job is to paraphrase the user's request about oceanography data into a clear, single-sentence confirmation question.
        The confirmation question should be like: This is the thing you want is that correct?
        The database schema is: {schema}
        User's request: "{query}"
        Confirmation Question:
        """
        response = ollama.chat(model=self.reasoning_model, messages=[{'role': 'user', 'content': prompt}])
        return response['message']['content'].strip()

    def classify_intent(self, history, new_query):
        """Classifies the user's intent based on the conversation history."""
        prompt = f"""
        You are an expert intent classifier. Your job is to determine what the user wants to do next.

        Here is the conversation history:
        {history}

        Here is the new user query: "{new_query}"

        Based on the new query, classify the user's intent into ONE of the following categories:
        - NEW_QUERY: The user is asking for a completely new set of data to be plotted (e.g., asking about a different parameter or starting over).
        - REFINE_QUERY: The user is asking for a modification of the previous query (e.g., a different sensor, a different time range).
        - ANALYZE_DATA: The user is asking a question that can be answered by calculating something from the data that was just shown (e.g., "what is the average?", "find the max value").
        - CLARIFY: The user is asking for more explanation about the current graph or data, without needing new data.

        Your response MUST be a single word from the list above.

        Intent:
        """
        response = ollama.chat(
            model=self.reasoning_model,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content'].strip()

    def generate_sql(self, history, schema, available_params, available_sensors):
        """
        Generates SQL, now using a more robust parsing method to extract the final query.
        """
        prompt = f"""
        You are an expert SQLite generation bot. Your sole purpose is to convert a user's request into a single, valid SQLite query based on the provided context.

        ### Database Schema
        {schema}

        ### Available Data Values
        - The `parameter_name` column can contain: {available_params}
        - The `sensor_id` column can contain: {available_sensors}

        ### Conversation History
        {history}

        ### STRICT Rules for Generating the Query:
        1.  **Map to Available Values:** First, map the user's plain-language request (e.g., "saltiness") to the official `parameter_name` from the "Available Data Values" list (e.g., 'Salinity').
        2.  **Case-Insensitive WHERE Clause:** All string comparisons in the `WHERE` clause MUST be case-insensitive. Use the `LOWER()` function on the column and the lowercase version of the value from Rule #1. Example: `WHERE LOWER(parameter_name) = 'salinity'`.
        3.  **Column Selection:** The query MUST select the `timestamp` and `value` columns.
        4.  **Time Filtering Logic:**
            - If the user's time frame is measured in **days, weeks, or months** (e.g., "past 3 days", "last week"), use the `date()` function to start from the beginning of the day. Example: `WHERE timestamp >= date('now', '-3 days')`.
            - If the user's time frame is measured in **hours, minutes, or seconds** (e.g., "past 8 hours", "last 30 minutes"), use the `datetime()` function for a precise relative time. Example: `WHERE timestamp >= datetime('now', '-8 hours')`.
        5.  **Output Format:** Your final output MUST be only the raw SQLite query, ending in a semicolon. Do not include any explanations, comments, or markdown formatting.

        ### Final SQLite Query:
        """

        response = ollama.chat(model=self.sql_model, messages=[{'role': 'user', 'content': prompt}])
        raw_output = response['message']['content']

        # --- NEW, MORE ROBUST PARSING LOGIC ---
        # Find all occurrences of a complete SELECT statement ending in a semicolon.
        matches = re.findall(r"(SELECT .*?;)", raw_output, re.IGNORECASE | re.DOTALL)

        if matches:
            # The last match is the final, intended query.
            cleaned_sql = matches[-1].strip()
            return cleaned_sql
        else:
            # Fallback for safety, though the above should work.
            if "SELECT" in raw_output:
                # Take the part after the last "SELECT" as a guess
                last_part = raw_output.split("SELECT")[-1]
                cleaned_sql = "SELECT" + last_part.strip()
                if not cleaned_sql.endswith(';'):
                    cleaned_sql += ';'
                return cleaned_sql
            raise ValueError("Could not extract a valid SQL query from the LLM's response.")

    def answer_from_data(self, df, question):
        """Uses the reasoning LLM to answer a question based on existing data."""
        if df is None or df.empty:
            return "There is no data to analyze."

        # Perform basic calculations and add them to the prompt for accuracy
        stats = ""
        if 'value' in df.columns:
            stats = f"""
            Here are some pre-calculated statistics from the data:
            - Average (mean): {df['value'].mean():.2f}
            - Maximum value: {df['value'].max():.2f}
            - Minimum value: {df['value'].min():.2f}
            - Number of data points: {len(df)}
            """

        prompt = f"""
        You are a helpful data analyst. A user has been shown a dataset and has a follow-up question.
        {stats}

        User's question: "{question}"

        Based on the statistics and the user's question, provide a concise, natural language answer.
        """
        response = ollama.chat(model=self.reasoning_model, messages=[{'role': 'user', 'content': prompt}])
        return response['message']['content']

    def explain_image(self, image_bytes, query):
        # This function is stable.
        prompt = f"""
        You are a marine science expert. Analyze the provided graph, which was generated for the query: "{query}".
        Describe the key trends, patterns, or significant anomalies.
        """
        response = ollama.chat(
            model=self.reasoning_model,
            messages=[{'role': 'user', 'content': prompt, 'images': [image_bytes]}]
        )
        return response['message']['content']