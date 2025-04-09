import re
from django.http import multipartparser

# Define valid_boundary function
def valid_boundary(boundary):
    """
    Verify that the boundary string is valid according to RFC 2046.
    """
    if not boundary:
        return False
    if len(boundary) > 70:
        return False
    
    # Check if boundary is bytes and handle accordingly
    if isinstance(boundary, bytes):
        # For bytes objects, use a bytes regex pattern
        valid_chars = re.compile(rb'^[ -~]+$')
    else:
        # For string objects, use a string regex pattern
        valid_chars = re.compile(r'^[ -~]+$')
    
    return bool(valid_chars.match(boundary))

# Apply the patch at import time
try:
    # Check if we need to patch
    if not hasattr(multipartparser.cgi, 'valid_boundary'):
        multipartparser.cgi.valid_boundary = valid_boundary
        print("Successfully patched multipartparser.cgi.valid_boundary")
except Exception as e:
    print(f"Error patching multipartparser: {e}")
