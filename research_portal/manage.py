#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import warnings

# Suppress the cgi deprecation warning
warnings.filterwarnings("ignore", category=DeprecationWarning, module="cgi")

# Add the Python 3.13 compatibility patch BEFORE anything else
try:
    import cgi
except ImportError:
    print("Python 3.13 detected: Loading cgi compatibility layer")
    # Get the directory this file is in
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Make sure our directory is in the path so Python can find our modules
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Import our compatibility patch
    try:
        import compat_cgi
        # Replace missing cgi module with our compatibility implementation
        sys.modules['cgi'] = compat_cgi
        print("Successfully loaded cgi compatibility layer")
    except Exception as e:
        print(f"Warning: Failed to load cgi compatibility layer: {e}")

# Add the Python 3.13 compatibility patch BEFORE anything else
try:
    import cgi
except ImportError:
    print("Python 3.13 detected: Loading cgi compatibility layer")
    # Get the directory this file is in
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Make sure our directory is in the path so Python can find our modules
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Import our compatibility patch
    try:
        import compat_cgi
        # Replace missing cgi module with our compatibility implementation
        sys.modules['cgi'] = compat_cgi
        print("Successfully loaded cgi compatibility layer")
    except Exception as e:
        print(f"Warning: Failed to load cgi compatibility layer: {e}")


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
