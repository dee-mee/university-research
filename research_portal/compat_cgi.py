"""
Compatibility module for Python 3.13+ that provides a minimal cgi module implementation
to support Django running on newer Python versions.
"""

import warnings
import html
import io
import tempfile
from collections import defaultdict
from urllib.parse import parse_qs

# The constants that were in the cgi module
__all__ = [
    "parse", "parse_multipart", "parse_header", "parse_qs", "parse_qsl",
    "escape", "FieldStorage"
]

# Replicate the constants from the old cgi module
maxlen = 0  # No max length enforced
logfile = None
valid_boundary = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789\'()+_,-./:=? ')

# Replicate the escape function
escape = html.escape

def parse_header(line):
    """Parse a Content-type header.
    Return the main content-type and a dictionary of parameters.
    """
    if not line:
        return '', {}
    
    parts = line.split(';')
    key = parts[0].strip().lower()
    params = {}
    
    for part in parts[1:]:
        if '=' not in part:
            continue
        name, value = part.strip().split('=', 1)
        name = name.strip().lower()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        params[name] = value
    
    return key, params

def _parseparam(s):
    """Parse parameter values with their attributes."""
    while s[:1] == ';':
        s = s[1:]
        end = s.find(';')
        if end > 0:
            param, s = s[:end], s[end:]
        else:
            param, s = s, ''
        if '=' in param:
            a, v = param.split('=', 1)
            if v and v[0] == v[-1] == '"':
                v = v[1:-1]
            yield a.strip(), v.strip()

def parse_multipart(fp, boundary, environ=None, keep_blank_values=False):
    """Parse multipart input.

    Arguments:
    fp   : input file
    boundary : boundary string
    environ : environment dictionary (used for maxlen)
    keep_blank_values: flag indicating whether blank values in
        percent-encoded forms should be treated as blank strings.

    Returns a dictionary mapping field names to lists of values.
    """
    if environ is None:
        environ = {}
    
    result = {}
    
    # For compatibility with older code
    if isinstance(boundary, str):
        boundary = boundary.encode('ascii')
    
    nextpart = b'--' + boundary
    
    # Skip the opening boundary
    line = fp.readline()
    if not line.startswith(nextpart):
        return result
    
    # Process each part
    while True:
        # Get part headers
        headers = {}
        while True:
            line = fp.readline()
            if not line or line.strip() == b'':
                break
            
            # Parse header line
            try:
                key, value = line.decode('iso-8859-1').strip().split(':', 1)
                headers[key.strip().lower()] = value.strip()
            except ValueError:
                # Handle malformed headers
                continue
        
        # Check if we hit the end
        line = fp.readline().strip()
        if line.startswith(b'--' + boundary + b'--'):
            break
        
        # Parse the content disposition to get field name
        disp_header = headers.get('content-disposition', '')
        disp_value, disp_params = parse_header(disp_header)
        
        field_name = disp_params.get('name', '')
        filename = disp_params.get('filename')
        
        # Read the field value
        field_value = b''
        while True:
            line = fp.readline()
            if not line or line.startswith(nextpart):
                break
            field_value += line
        
        # Strip CRLF from end
        if field_value.endswith(b'\r\n'):
            field_value = field_value[:-2]
        elif field_value.endswith(b'\n'):
            field_value = field_value[:-1]
        
        # Add to result
        if field_name:
            if field_name in result:
                result[field_name].append(field_value.decode('iso-8859-1'))
            else:
                result[field_name] = [field_value.decode('iso-8859-1')]
    
    return result

class MiniFieldStorage:
    """Minimal FieldStorage items for form data."""
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.filename = None
        self.headers = {}
        self.type = None
        self.type_options = {}
        self.disposition = None
        self.disposition_options = {}
        self.file = io.BytesIO(value.encode('utf-8') if isinstance(value, str) else value)

class FieldStorage:
    """Storage class for HTML form data.
    
    This is a simplified version that provides just enough functionality
    to support Django's use of it.
    """
    filename = None
    file = None
    type = None
    type_options = {}
    disposition = None
    disposition_options = {}
    headers = {}
    encoding = 'utf-8'
    
    def __init__(self, fp=None, headers=None, outerboundary=None,
                 environ=None, keep_blank_values=False, strict_parsing=False,
                 limit=None, encoding='utf-8', errors='replace', max_num_fields=None):
        
        self.keep_blank_values = keep_blank_values
        self.strict_parsing = strict_parsing
        self.limit = limit
        self.encoding = encoding
        self.errors = errors
        self.max_num_fields = max_num_fields
        
        self.bytes_read = 0
        self.list = []
        self.name = None
        self.filename = None
        self.value = None
        
        if environ is None:
            environ = {}
        
        self.environ = environ
        
        if fp is not None:
            self.fp = fp
            if headers is None:
                headers = {}
            self.headers = headers
            
            # Get content-type header
            content_type = self.headers.get('content-type', '')
            if isinstance(content_type, bytes):
                content_type = content_type.decode('iso-8859-1')
            
            self.type, self.type_options = parse_header(content_type)
            
            # Get content-disposition header
            content_disp = self.headers.get('content-disposition')
            if content_disp:
                if isinstance(content_disp, bytes):
                    content_disp = content_disp.decode('iso-8859-1')
                self.disposition, self.disposition_options = parse_header(content_disp)
            
            # Determine if request is multipart
            if self.type.startswith('multipart/'):
                self.parse_multipart(fp, outerboundary)
            else:
                # Form data - parse from environment
                self.parse_form_data()
        
        elif environ:
            self.parse_form_data()
    
    def parse_multipart(self, fp, boundary):
        """Parse a multipart/form-data body.
        
        This method is simplified and doesn't fully implement the spec.
        """
        boundary = boundary or self.type_options.get('boundary', '').encode('ascii')
        if not boundary:
            return
        
        data = parse_multipart(fp, boundary, self.environ, self.keep_blank_values)
        
        for key, values in data.items():
            if len(values) == 1:
                self.list.append(MiniFieldStorage(key, values[0]))
            else:
                for value in values:
                    self.list.append(MiniFieldStorage(key, value))
    
    def parse_form_data(self):
        """Parse form data from the environment."""
        method = self.environ.get('REQUEST_METHOD', '').upper()
        query_string = self.environ.get('QUERY_STRING', '')
        
        if method == 'POST':
            # Parse POST data
            content_type = self.environ.get('CONTENT_TYPE', '')
            content_length = int(self.environ.get('CONTENT_LENGTH', 0))
            
            if content_type == 'application/x-www-form-urlencoded':
                data = self.environ.get('wsgi.input').read(content_length).decode(self.encoding)
                parsed_data = parse_qs(data, keep_blank_values=self.keep_blank_values)
                
                for key, values in parsed_data.items():
                    for value in values:
                        self.list.append(MiniFieldStorage(key, value))
        
        # Parse GET data
        if query_string:
            parsed_data = parse_qs(query_string, keep_blank_values=self.keep_blank_values)
            
            for key, values in parsed_data.items():
                for value in values:
                    self.list.append(MiniFieldStorage(key, value))
    
    def getvalue(self, key, default=None):
        """Return the first value received."""
        for item in self.list:
            if item.name == key:
                return item.value
        return default
    
    def getlist(self, key):
        """Return list of received values."""
        result = []
        for item in self.list:
            if item.name == key:
                result.append(item.value)
        return result
    
    def keys(self):
        """Return list of field names."""
        return list(set(item.name for item in self.list))
    
    def __contains__(self, key):
        """Return true if field 'key' exists."""
        for item in self.list:
            if item.name == key:
                return True
        return False
    
    def __getitem__(self, key):
        """Return the first value received."""
        for item in self.list:
            if item.name == key:
                return item
        raise KeyError(key)
    
    def __iter__(self):
        """Iterate over field names."""
        for item in self.list:
            yield item.name

def parse(fp, environ=None, keep_blank_values=False, strict_parsing=False):
    """Parse a form data into a FieldStorage object."""
    return FieldStorage(fp=fp, environ=environ, keep_blank_values=keep_blank_values, 
                        strict_parsing=strict_parsing)
