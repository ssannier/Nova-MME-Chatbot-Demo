#!/bin/bash
# Install Lambda Layer dependencies
# Layers must have a python/ subdirectory for Python packages

set -e

echo "========================================"
echo "Installing Lambda Layer Dependencies"
echo "========================================"
echo ""

# Create layer directories if they don't exist
mkdir -p lambda/layers/pdf-processing/python
mkdir -p lambda/layers/docx-processing/python
mkdir -p lambda/layers/numpy/python

echo "[1/3] Installing PyMuPDF layer (for PDF processing)..."
echo "Note: Installing for Linux x86_64 platform (Lambda runtime)"
pip install "PyMuPDF>=1.23.0" -t lambda/layers/pdf-processing/python --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --only-binary=:all: --upgrade --no-deps
echo "Done!"
echo ""

echo "[2/3] Installing python-docx layer (for DOCX processing)..."
echo "Note: Installing for Linux x86_64 platform (Lambda runtime)"
echo "Installing python-docx and its dependencies..."
pip install "python-docx>=1.1.0" lxml typing_extensions -t lambda/layers/docx-processing/python --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --only-binary=:all: --upgrade
echo "Done!"
echo ""

echo "[3/3] Installing NumPy layer (for MRL truncation)..."
echo "Note: Installing for Linux x86_64 platform (Lambda runtime)"
pip install "numpy>=1.24.0" -t lambda/layers/numpy/python --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --only-binary=:all: --upgrade --no-deps
echo "Done!"

echo ""
echo "========================================"
echo "All Lambda Layers installed!"
echo "========================================"
echo ""
echo "Layer locations:"
echo "  - lambda/layers/pdf-processing/python/"
echo "  - lambda/layers/docx-processing/python/"
echo "  - lambda/layers/numpy/python/"
echo ""
echo "You can now run: cdk deploy NovaMMEEmbedderStack"
