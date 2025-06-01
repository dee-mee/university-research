#!/bin/bash
# Script to run the test data generator with proper parameters

# Make the script executable if needed
chmod +x data_repository/test_data_script.py

# Set default number of datasets
if [ -z "$1" ]; then
    NUM_DATASETS=10
else
    NUM_DATASETS=$1
fi

# Show what we're doing
echo "Generating $NUM_DATASETS test datasets..."

# Check for required packages
pip install -q faker pandas numpy netCDF4 tqdm

# Run the test data generator
python data_repository/test_data_script.py $NUM_DATASETS

# Check result
if [ $? -eq 0 ]; then
    echo "Test data generation completed successfully!"
    echo "You can now access the data through the web interface."
else
    echo "There was an error during data generation."
    echo "Please check the error messages above."
fi
