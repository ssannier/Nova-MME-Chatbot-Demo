# Lambda Layers

This directory contains Lambda Layers for shared dependencies.

## Structure

```
lambda/layers/
├── pdf-processing/          # PyMuPDF for PDF processing
│   └── python/
│       └── (packages installed here)
├── docx-processing/         # python-docx for DOCX processing
│   └── python/
│       └── (packages installed here)
└── numpy/                   # NumPy for MRL truncation
    └── python/
        └── (packages installed here)
```

## Installation

Run the installation script to build all layers:

```bash
# Windows
scripts\install-lambda-layers.bat

# Linux/Mac
./scripts/install-lambda-layers.sh
```

## Layer Structure

Lambda Layers must follow this directory structure:
- `python/` - Python packages go here
- Packages are imported normally in Lambda code (e.g., `import numpy`)

## Why Layers?

- **Clean separation**: Dependencies separate from code
- **Reusable**: Share layers across multiple Lambdas
- **Smaller deployments**: Code-only updates are faster
- **No Docker required**: Just pip install locally
