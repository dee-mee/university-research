import re
from django.http import multipartparser

# Define our own valid_boundary function since it's missing in Python 3.13
def valid_boundary(boundary):
    """
    Verify that the boundary string is valid according to RFC 2046.
    
    Replacement for cgi.valid_boundary which was removed in Python 3.13.
    """
    # RFC 2046 section 5.1.1
    if not boundary:
        return False
    # Boundary must be 1-70 characters long
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

class CGICompatibilityMiddleware:
    """
    Middleware to patch Django's multipartparser for Python 3.13 compatibility.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Patch Django's multipartparser to use our valid_boundary function
        # This is the key fix - monkeypatching Django's internal function
        try:
            # Only patch if the module has no valid_boundary or if it's using compat_cgi
            if not hasattr(multipartparser.cgi, 'valid_boundary'):
                multipartparser.cgi.valid_boundary = valid_boundary
                print("Successfully patched Django's multipartparser for Python 3.13 compatibility")
        except Exception as e:
            print(f"Failed to patch Django's multipartparser: {e}")

    def __call__(self, request):
        return self.get_response(request)
