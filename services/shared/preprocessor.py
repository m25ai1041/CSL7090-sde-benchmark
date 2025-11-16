import re

def clean_text(text: str) -> str:
    """
    A simple pure-Python text cleaning function.
    
    Input:  text (str)
    Output: cleaned text (str)
    """
    text = text.lower()
    text = re.sub(r'\d+', '', text) # Remove numbers
    text = re.sub(r'[^\w\s]', '', text) # Remove punctuation
    text = text.strip()
    return text