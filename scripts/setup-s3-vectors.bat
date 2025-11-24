@echo off
REM Setup S3 Vector indexes after CDK deployment
REM Usage: scripts\setup-s3-vectors.bat [environment]

setlocal enabledelayedexpansion

set ENVIRONMENT=%1
if "%ENVIRONMENT%"=="" set ENVIRONMENT=dev

set CONFIG_FILE=config\%ENVIRONMENT%.json

REM Check if config file exists
if not exist "%CONFIG_FILE%" (
    echo Error: Config file not found: %CONFIG_FILE%
    exit /b 1
)

REM Extract bucket name from config (requires Python)
for /f "delims=" %%i in ('python -c "import json; print(json.load(open('%CONFIG_FILE%'))['buckets']['vector_bucket'])"') do set BUCKET_NAME=%%i
for /f "delims=" %%i in ('python -c "import json; print(json.load(open('%CONFIG_FILE%')).get('region', 'us-east-1'))"') do set REGION=%%i

echo Setting up S3 Vectors for bucket: %BUCKET_NAME% in region: %REGION%

REM Create S3 Vector bucket (if not already created)
echo Creating S3 Vector bucket...
aws s3vectors create-vector-bucket --vector-bucket-name %BUCKET_NAME% --region %REGION%
if errorlevel 1 (
    echo Note: Bucket creation failed - may already exist
)

REM Wait a bit for bucket to be ready
echo Waiting for bucket to be ready...
timeout /t 10 /nobreak >nul

REM Create vector indexes for each dimension
for %%D in (256 384 1024 3072) do (
    set INDEX_NAME=embeddings-%%Dd
    echo.
    echo Creating vector index: !INDEX_NAME! (dimension: %%D^)
    
    aws s3vectors create-index --vector-bucket-name %BUCKET_NAME% --index-name !INDEX_NAME! --data-type float32 --dimension %%D --distance-metric cosine --region %REGION%
    if errorlevel 1 (
        echo ERROR: Failed to create index !INDEX_NAME!
    ) else (
        echo SUCCESS: Created index !INDEX_NAME!
    )
)

echo.
echo ========================================
echo Verifying setup...
echo ========================================
echo.
echo Listing indexes:
aws s3vectors list-indexes --vector-bucket-name %BUCKET_NAME% --region %REGION%
echo.
echo ========================================
echo Setup complete!
echo ========================================

endlocal
