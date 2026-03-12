import re

class TextCleaner:
    def __init__(self):
        # Common Hinglish and English verbal fillers
        self.filler_pattern = re.compile(
            r'\b(theek hai|matlab|basically|um|uh|actually|you know|so|right|like)\b', 
            re.IGNORECASE
        )

    def clean_hinglish(self, text):
        # 1. Basic Cleaning: Remove brackets and timestamps
        text = re.sub(r'\[.*?\]', '', text)
        
        # 2. Text Normalization
        text = text.replace("\n", " ")
        text = " ".join(text.split())
        
        # 3. Filler Removal: Strip out the noise words
        text = self.filler_pattern.sub('', text)
        
        # 4. Final Polish: Clean up any double spaces created by removal
        text = " ".join(text.split())
        
        return text.strip()