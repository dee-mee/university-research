"""
Compatibility module for the removed cgi module in Python 3.13+
This is just a placeholder with the minimal functionality needed by Django.
"""

import io
import tempfile
from collections import defaultdict
from urllib.parse import parse_qs

class FieldStorage:
    """Minimal implementation of cgi.FieldStorage for Django compatibility"""
    
    def __init__(self, fp=None, headers=None, outerboundary=b'',
                 environ=None, keep_blank_values=False, strict_parsing=False,
                 limit=None, encoding='utf-8', errors='replace', max_num_fields=None,
                 separator='&'):
        self.environ = environ or {}
        self.keep_blank_values = keep_blank_values
        self.strict_parsing = strict_parsing
        self.encoding = encoding
        self.errors = errors
        
        self.list = []
        self.dict = defaultdict(list)
        
        # Parse query string if available
        if environ and 'QUERY_STRING' in environ:
            self._parse_qs(environ['QUERY_STRING'])
        
        # Simple handling for file uploads
        self.file = None
        if fp:
            self.file = tempfile.TemporaryFile(mode='w+b')
            if hasattr(fp, 'read'):
                self.file.write(fp.read())
            else:
                self.file.write(fp)
            self.file.seek(0)
    
    def _parse_qs(self, qs):
        """Parse a query string into the dict and list"""
        if not qs:
            return
            
        parsed = parse_qs(qs, keep_blank_values=self.keep_blank_values, 
                         strict_parsing=self.strict_parsing)
        
        for key, values in parsed.items():
            for value in values:
                item = MiniFieldStorage(key, value)
                self.list.append(item)
                self.dict[key].append(item)
    
    def getvalue(self, key, default=None):
        """Return the first value received for the key"""
        try:
            return self.dict[key][0].value
        except (KeyError, IndexError):
            return default
    
    def getlist(self, key):
        """Return the list of values for the key"""
        try:
            return [item.value for item in self.dict[key]]
        except KeyError:
            return []
    
    def keys(self):
        """Return the keys"""
        return self.dict.keys()
    
    def __contains__(self, key):
        return key in self.dict
    
    # Additional methods needed by Django
    def read(self, *args, **kwargs):
        """Read from the file object if available"""
        if self.file:
            return self.file.read(*args, **kwargs)
        return b''
    
    def readline(self, *args, **kwargs):
        """Read a line from the file object if available"""
        if self.file:
            return self.file.readline(*args, **kwargs)
        return b''
    
    def readlines(self, *args, **kwargs):
        """Read lines from the file object if available"""
        if self.file:
            return self.file.readlines(*args, **kwargs)
        return []

class MiniFieldStorage:
    """Minimal implementation of a field storage item"""
    
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.filename = None
        self.type = None
        self.type_options = {}
        self.disposition = None
        self.disposition_options = {}
        self.headers = {}
        
    def __repr__(self):
        return f"MiniFieldStorage('{self.name}', '{self.value}')"

# Add parse_header function that Django uses
def parse_header(line):
    """Parse a Content-type header.
    Return the main content-type and a dictionary of options.
    """
    parts = line.split(';')
    key = parts[0].strip().lower()
    options = {}
    
    for part in parts[1:]:
        if '=' not in part:
            continue
        name, value = part.split('=', 1)
        name = name.strip().lower()
        value = value.strip()
        # Remove quotes if present
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        options[name] = value
            
    return key, options

# Add escape function that might be used
def escape(s, quote=None):
    """Escape special characters in string s for HTML/XML.
    
    Django might call this for escaping values.
    """
    if not isinstance(s, str):
        s = str(s)
    if "&" in s:
        s = s.replace("&", "&amp;")
    if "<" in s:
        s = s.replace("<", "&lt;")
    if ">" in s:
        s = s.replace(">", "&gt;")
    if quote and quote in s:
        s = s.replace(quote, f"&#{ord(quote)};")
    return s
