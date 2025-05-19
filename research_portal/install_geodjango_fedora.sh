#!/bin/bash

# Install system dependencies for GeoDjango
sudo dnf update -y

# Install GDAL and related packages
sudo dnf install -y \
    binutils \
    gdal \
    gdal-devel \
    geos \
    geos-devel \
    proj \
    proj-devel \
    python3-gdal

# Verify GDAL is installed
echo "Checking GDAL installation..."
if command -v gdal-config &> /dev/null; then
    echo "Installed GDAL version: $(gdal-config --version)"
    GDAL_VERSION=$(gdal-config --version)
else
    echo "ERROR: gdal-config not found. GDAL installation failed."
    exit 1
fi

# Set GDAL variables
export CPLUS_INCLUDE_PATH=/usr/include/gdal
export C_INCLUDE_PATH=/usr/include/gdal
export GDAL_CONFIG=/usr/bin/gdal-config

# Make these environment variables persistent
echo 'export CPLUS_INCLUDE_PATH=/usr/include/gdal' >> ~/.bashrc
echo 'export C_INCLUDE_PATH=/usr/include/gdal' >> ~/.bashrc
echo 'export GDAL_CONFIG=/usr/bin/gdal-config' >> ~/.bashrc

# Update pip to latest version
pip install --upgrade pip

# Install compatible versions of Django and DRF-GIS
pip install django==4.2.* djangorestframework-gis==1.0.*

# Create a temporary requirements file with the correct GDAL version
grep -v "GDAL\|django\|djangorestframework-gis" research_portal/requirements.txt > temp_requirements.txt
echo "GDAL==${GDAL_VERSION}" >> temp_requirements.txt

# Install Python packages using the system GDAL
pip install --no-binary gdal -r temp_requirements.txt

# Cleanup
rm temp_requirements.txt

echo "Installation complete. You may need to restart your terminal for environment variables to take effect."