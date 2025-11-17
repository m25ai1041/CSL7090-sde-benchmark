# This is the Cython source file: optimizer.pyx
# It will be compiled into 'optimizer.c' and then 'optimizer.so'
# which Python can import.

import re
from cpython cimport unicode

# cython: language_level=3

# --- Pre-compile regex patterns at the C module level ---
# This is much faster than compiling them in a Python function
cdef object RE_NUMBERS = re.compile(r'\d+')
cdef object RE_PUNCTUATION = re.compile(r'[^\w\s]')

# 'cpdef' makes this function available to Python (like 'def')
# but also creates a fast C-level version.
cpdef str clean_text(str text_in):
    """
    Cython-optimized version of the text cleaning function.
    This is the function your gRPC server will call.
    """
    
    cdef str text
    
    # 1. Lowercase
    text = text_in.lower()

    # 2. Use the pre-compiled C-level regex objects
    text = RE_NUMBERS.sub('', text)
    text = RE_PUNCTUATION.sub('', text)

    # 3. Strip whitespace
    text = " ".join(text.split()) # Normalize whitespace
    text = text.strip()

    return text