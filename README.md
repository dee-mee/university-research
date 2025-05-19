# University Research Portal

## Description
This project is a Django-based web application designed to facilitate research activities, data management, and field data collection. It provides a comprehensive platform for researchers to store, share, and analyze datasets with integrated geographical visualization capabilities.

## Core Components

### Data Repository
- Dataset management with versioning control
- Categorization and metadata management
- Download tracking and analytics
- DOI integration for academic citations

### Field Data Collection System
- Field device management and monitoring
- Weather station integration
- Manual and automated data collection
- Data validation and quality control
- Alert system for device maintenance

### Maps and Geographical Analysis
- Spatial data visualization
- Field data collection points
- Weather station mapping
- Geospatial analysis tools

### User Management
- Authentication and authorization
- Researcher profiles and collaboration tools
- Activity tracking and notifications

## Features
- User registration and authentication
- Profile management
- Dataset upload, versioning, and sharing
- Field data collection through various device types
- Automated alerts for field devices (battery, connectivity, etc.)
- Geographical visualization of research data
- Data import/export in multiple formats (CSV, JSON, Excel)
- Advanced search and filtering capabilities

## Installation Instructions
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd research_portal
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure GeoDjango (for spatial features):
   - For Linux: Use the provided installation script
     ```bash
     ./install_geodjango.sh
     ```
   - For Fedora: Use the Fedora-specific script
     ```bash
     ./install_geodjango_fedora.sh
     ```

5. Set up database:
   ```bash
   python manage.py migrate
   ```

6. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

## Usage Instructions
1. Run the Django development server:
   ```bash
   python manage.py runserver
   ```

2. Access the application at `http://127.0.0.1:8000/`.

3. Field data collection:
   - Set up field devices through the admin interface
   - Configure alert thresholds and monitoring parameters
   - Collect and upload field data through the web interface or API
   - View data on geographical maps

4. Dataset management:
   - Upload datasets with metadata
   - Create and manage dataset versions
   - Categorize and tag datasets for easy discovery
   - Track downloads and usage analytics

## System Architecture
The system uses Django with GeoDjango for spatial functionality and includes:
- Django REST framework for API endpoints
- WebSocket support for real-time alerts
- Batch processing for large dataset operations
- Automated field device monitoring

## Tools and Technologies Used
- Django and GeoDjango
- Django REST framework
- PostgreSQL with PostGIS extension
- Python for data processing
- JavaScript for frontend interactivity
- Leaflet.js for map visualization

## API Documentation
API endpoints are available for:
- Dataset access and management
- Field device monitoring
- Data collection and upload
- User authentication

## Collaborators
- [DEREK MURIUKI] - dee-mee
- [BENARD KARANJA] - n-cognto
- [KELVIN NAMBALE] - Kelvinnambale
- [FIDEL ELIUD] - phantom-kali

## License
This project is licensed under the MIT License.
