#!/bin/bash

# Install system dependencies for GeoDjango
sudo apt-get update
sudo apt-get install -y \
    binutils \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    python3-gdal

# Set GDAL version
export CPLUS_INCLUDE_PATH=/usr/include/gdal
export C_INCLUDE_PATH=/usr/include/gdal

# Install Python packages
pip3 install -r requirements.txt
