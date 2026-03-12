import os
import json
from google import genai
from utils.config import GEMINI_API_KEY

class ConceptExtractor:
    def __init__(self):
        # The new SDK uses a unified Client object
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def extract_and_standardize(self, cleaned_text, error_feedback=None):
        base_prompt = f"""
        You are an expert Pedagogical Engineer. 
        Analyze this technical transcript and:
        1. Identify core technical concepts.
        2. Map colloquial Hinglish terms to standard English.
        3. Determine prerequisite relationships.
        4. Assign a 'relative_importance' (1-10) based on how much time/depth the teacher spends on it.
        
        Output strictly as a JSON object:
        {{
          "video_summary": "1-sentence overview",
          "concepts": [
            {{
              "id": 1,
              "standard_term": "Term",
              "colloquial_context": "Hinglish used",
              "description": "Definition",
              "relative_importance": 5, // Score 1-10 based on explanation depth
              "prerequisites": [] 
            }}
          ]
        }}

        Transcript: {cleaned_text}
        """

        if error_feedback:
            # Injecting specific instructions to fix the loop
            base_prompt += f"""\n\nCRITICAL ERROR: Your previous output contained a circular dependency: {error_feedback}.
            Please re-evaluate the pedagogical flow and ensure the 'prerequisites' list forms a valid Directed Acyclic Graph (DAG) with no loops."""

        try:
            # We use gemini-2.0-flash for high-speed, accurate extraction
            response = self.client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=base_prompt,
                config={
                    "response_mime_type": "application/json" # Enforces JSON mode
                }
            )
            # response text ==> now directly accessible
            return json.loads(response.text)
        except Exception as e:
            print(f"Error during Gemini extraction: {e}")
            return None