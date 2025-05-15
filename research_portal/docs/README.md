# Field Data Collection System Documentation

This document provides comprehensive documentation for the Field Data Collection System, including system architecture, installation, configuration, usage, and development guidelines.

## Table of Contents

1. [System Overview](docs/system_overview.md)
2. [Architecture](docs/architecture.md)
3. [Installation Guide](docs/installation.md)
4. [Configuration](docs/configuration.md)
5. [User Guide](docs/user_guide.md)
6. [Developer Guide](docs/developer_guide.md)
7. [API Documentation](docs/api_documentation.md)
8. [Security](docs/security.md)
9. [Troubleshooting](docs/troubleshooting.md)
10. [FAQ](docs/faq.md)

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Node.js 14+
- Redis (for WebSocket support)

### Installation
```bash
# Clone the repository
git clone https://github.com/dee-mee/university-research.git
cd university-research

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

## Support

For support, please:
1. Check the [FAQ](docs/faq.md)
2. Review the [Troubleshooting Guide](docs/troubleshooting.md)
3. Open an issue in the GitHub repository

## License

This project is licensed under the MIT License - see the LICENSE file for details.
