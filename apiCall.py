import google.generativeai as genai

class GenAI:
    def __init__(self, api_key):
        genai.configure(api_key = api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    def generate_content(self, prompt):
        return self.model.generate_content(prompt)


