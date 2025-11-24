"""
Embedder Stack - Async processing pipeline for Nova MME with MRL

This stack creates:
- S3 bucket for source files
- S3 Vector bucket with multi-dimensional indexes
- Three Lambda functions (processor, check_status, store_embeddings)
- Step Functions state machine for orchestration
- S3 event trigger
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_s3_notifications as s3n,
    aws_logs as logs,
)
from constructs import Construct
import json

# NOTE: S3 Vectors construct (cdk-s3-vectors) has critical bugs and is not production-ready.
# We use regular S3 buckets and create vector indexes manually via AWS CLI after deployment.


class EmbedderStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Load configuration
        config = self._load_config()

        # Create S3 bucket for source files
        self.source_bucket = s3.Bucket(
            self,
            "SourceBucket",
            bucket_name=config["buckets"]["source_bucket"],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
            lifecycle_rules=[
                # Note: pdf-pages/ are kept permanently for chatbot access
                # Only truly temporary processing files should go in temp locations
            ],
        )

        # Reference manually-created S3 Vector bucket
        # The S3 Vector bucket and indexes must be created manually via AWS CLI:
        #   aws s3vectors create-vector-bucket --vector-bucket-name <name> --region us-east-1
        #   aws s3vectors create-index --vector-bucket-name <name> --index-name embeddings-256d --dimension 256 --distance-metric cosine
        #   aws s3vectors create-index --vector-bucket-name <name> --index-name embeddings-384d --dimension 384 --distance-metric cosine
        #   aws s3vectors create-index --vector-bucket-name <name> --index-name embeddings-1024d --dimension 1024 --distance-metric cosine
        #   aws s3vectors create-index --vector-bucket-name <name> --index-name embeddings-3072d --dimension 3072 --distance-metric cosine
        vector_bucket_name = config["buckets"]["vector_bucket"]
        
        self.vector_bucket = s3.Bucket.from_bucket_name(
            self,
            "VectorBucket",
            bucket_name=vector_bucket_name
        )
        
        # Define vector index names (must match manually-created indexes)
        self.vector_indexes = {
            dim: f"embeddings-{dim}d" for dim in config["embedding"]["dimensions"]
        }

        # Create S3 bucket for async job outputs
        # Note: pdf-pages/ and docx-text/ are kept permanently for chatbot access
        # Only the Nova MME async output folders (with invocation IDs) are auto-deleted
        self.output_bucket = s3.Bucket(
            self,
            "OutputBucket",
            bucket_name=f"{config['buckets']['source_bucket']}-outputs",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
        )

        # Create IAM role for Lambda functions with Bedrock access
        lambda_role = self._create_lambda_role(config)

        # Lambda 1: Nova MME Processor
        self.processor_lambda = self._create_processor_lambda(lambda_role, config)

        # Lambda 2: Check Job Status
        self.check_status_lambda = self._create_check_status_lambda(lambda_role, config)

        # Lambda 3: Store Embeddings
        self.store_embeddings_lambda = self._create_store_embeddings_lambda(
            lambda_role, config
        )

        # Create Step Functions state machine
        self.state_machine = self._create_state_machine(config)

        # Add S3 event notification to trigger Step Functions
        self._setup_s3_trigger()

    def _load_config(self) -> dict:
        """Load configuration from context or use defaults"""
        env = self.node.try_get_context("environment") or "dev"
        config_path = f"config/{env}.json"

        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            # Return default config
            return {
                "embedding": {
                    "dimensions": [256, 384, 1024, 3072],
                    "model_id": "amazon.nova-2-multimodal-embeddings-v1:0",
                },
                "buckets": {
                    "source_bucket": "cic-multimedia-test",
                    "vector_bucket": "nova-mme-demo-embeddings",
                },
            }

    def _create_lambda_role(self, config: dict) -> iam.Role:
        """Create IAM role with permissions for Bedrock, S3, and S3 Vector"""
        role = iam.Role(
            self,
            "EmbedderLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Bedrock permissions for synchronous and asynchronous invocations
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:StartAsyncInvoke",
                    "bedrock:GetAsyncInvoke",
                    "bedrock:ListAsyncInvokes",
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/*",
                    f"arn:aws:bedrock:{self.region}:{self.account}:async-invoke/*"
                ],
            )
        )

        # Bedrock async invocation permissions
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:StartAsyncInvoke",
                    "bedrock:GetAsyncInvoke",
                    "bedrock:ListAsyncInvokes",
                ],
                resources=["*"],
            )
        )

        # S3 Vectors permissions for storing embeddings
        # Note: S3 Vectors uses a different ARN format than regular S3
        vector_bucket_name = config['buckets']['vector_bucket']
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3vectors:PutVectors",
                    "s3vectors:GetVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:DescribeIndex",
                    "s3vectors:ListIndexes",
                ],
                resources=[
                    # Bucket-level permissions
                    f"arn:aws:s3vectors:{self.region}:{self.account}:bucket/{vector_bucket_name}",
                    # Object-level permissions (vectors within indexes)
                    f"arn:aws:s3vectors:{self.region}:{self.account}:bucket/{vector_bucket_name}/*",
                ],
            )
        )

        # S3 permissions for regular buckets (source, output, and vector bucket for metadata)
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:DeleteObject",
                ],
                resources=[
                    self.source_bucket.bucket_arn,
                    f"{self.source_bucket.bucket_arn}/*",
                    self.output_bucket.bucket_arn,
                    f"{self.output_bucket.bucket_arn}/*",
                ],
            )
        )

        return role

    def _create_processor_lambda(
        self, role: iam.Role, config: dict
    ) -> lambda_.Function:
        """Create Lambda 1: Nova MME Processor"""
        
        # Create Lambda Layers for PDF and DOCX processing
        pymupdf_layer = lambda_.LayerVersion(
            self,
            "PyMuPDFLayer",
            code=lambda_.Code.from_asset("lambda/layers/pdf-processing"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="PyMuPDF for PDF to image conversion",
        )
        
        docx_layer = lambda_.LayerVersion(
            self,
            "DocxLayer",
            code=lambda_.Code.from_asset("lambda/layers/docx-processing"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="python-docx for DOCX text extraction",
        )
        
        return lambda_.Function(
            self,
            "ProcessorFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/embedder/processor"),
            layers=[pymupdf_layer, docx_layer],
            role=role,
            timeout=Duration.minutes(5),
            memory_size=1024,  # Increased for PDF processing
            log_retention=logs.RetentionDays.THREE_DAYS,  # Auto-delete logs after 3 days
            environment={
                "EMBEDDING_DIMENSION": "3072",  # Always use max for MRL
                "MODEL_ID": config["embedding"]["model_id"],
                "OUTPUT_BUCKET": self.output_bucket.bucket_name,
                "SOURCE_BUCKET": self.source_bucket.bucket_name,
            },
        )

    def _create_check_status_lambda(
        self, role: iam.Role, config: dict
    ) -> lambda_.Function:
        """Create Lambda 2: Check Job Status"""
        return lambda_.Function(
            self,
            "CheckStatusFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/embedder/check_status"),
            role=role,
            timeout=Duration.seconds(30),
            memory_size=256,
            log_retention=logs.RetentionDays.THREE_DAYS,  # Auto-delete logs after 3 days
        )

    def _create_store_embeddings_lambda(
        self, role: iam.Role, config: dict
    ) -> lambda_.Function:
        """Create Lambda 3: Store Embeddings with MRL truncation"""
        
        # Create Lambda Layer for NumPy
        numpy_layer = lambda_.LayerVersion(
            self,
            "NumpyLayer",
            code=lambda_.Code.from_asset("lambda/layers/numpy"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="NumPy for MRL truncation and normalization",
        )
        
        return lambda_.Function(
            self,
            "StoreEmbeddingsFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/embedder/store_embeddings"),
            layers=[numpy_layer],
            role=role,
            timeout=Duration.minutes(15),
            memory_size=2048,  # Need memory for numpy operations
            log_retention=logs.RetentionDays.THREE_DAYS,  # Auto-delete logs after 3 days
            environment={
                "VECTOR_BUCKET": self.vector_bucket.bucket_name,
                "EMBEDDING_DIMENSIONS": ",".join(
                    str(d) for d in config["embedding"]["dimensions"]
                ),
            },
        )

    def _create_state_machine(self, config: dict) -> sfn.StateMachine:
        """Create Step Functions state machine for orchestration"""

        # Task: Invoke processor Lambda
        process_task = tasks.LambdaInvoke(
            self,
            "ProcessFile",
            lambda_function=self.processor_lambda,
            output_path="$.Payload",
        )

        # Check if this is a PDF with multiple pages
        is_pdf_check = sfn.Choice(self, "IsPDF?")

        # For PDFs: Process all pages in parallel using Map state
        # Map state iterates over pdfPages array
        
        # Task: Check job status (for use in Map)
        check_status_task_map = tasks.LambdaInvoke(
            self,
            "CheckJobStatusMap",
            lambda_function=self.check_status_lambda,
            output_path="$.Payload",
        )

        # Wait state for Map (30 seconds between status checks)
        wait_state_map = sfn.Wait(
            self,
            "WaitForJobMap",
            time=sfn.WaitTime.duration(Duration.seconds(30)),
        )

        # Task: Store embeddings (for use in Map)
        store_task_map = tasks.LambdaInvoke(
            self,
            "StoreEmbeddingsMap",
            lambda_function=self.store_embeddings_lambda,
            output_path="$.Payload",
        )

        # Success state for individual page
        page_success = sfn.Succeed(self, "PageComplete")

        # Failure state for individual page
        page_failure = sfn.Fail(
            self,
            "PageFailed",
            cause="Page processing failed",
            error="PageJobFailed",
        )

        # Storage check for individual page
        page_storage_check = sfn.Choice(self, "PageStorageSucceeded?")
        page_storage_check.when(
            sfn.Condition.string_equals("$.status", "SUCCESS"),
            page_success
        ).otherwise(page_failure)

        # Define page processing workflow (used in Map)
        page_workflow = (
            wait_state_map
            .next(check_status_task_map)
            .next(
                sfn.Choice(self, "PageJobComplete?")
                .when(
                    sfn.Condition.string_equals("$.status", "COMPLETED"),
                    store_task_map.next(page_storage_check),
                )
                .when(
                    sfn.Condition.string_equals("$.status", "FAILED"),
                    page_failure,
                )
                .otherwise(wait_state_map)
            )
        )

        # Map state to process all PDF pages in parallel
        pdf_map_state = sfn.Map(
            self,
            "ProcessAllPages",
            items_path="$.pdfPages",
            max_concurrency=10,  # Process up to 10 pages concurrently
        )
        pdf_map_state.iterator(page_workflow)

        # Success state for PDF (all pages complete)
        pdf_success = sfn.Succeed(self, "AllPagesComplete")

        # For non-PDFs: Use original single-job workflow
        
        # Task: Check job status (for single files)
        check_status_task = tasks.LambdaInvoke(
            self,
            "CheckJobStatus",
            lambda_function=self.check_status_lambda,
            output_path="$.Payload",
        )

        # Wait state (30 seconds between status checks)
        wait_state = sfn.Wait(
            self,
            "WaitForJob",
            time=sfn.WaitTime.duration(Duration.seconds(30)),
        )

        # Task: Store embeddings
        store_task = tasks.LambdaInvoke(
            self,
            "StoreEmbeddings",
            lambda_function=self.store_embeddings_lambda,
            output_path="$.Payload",
        )

        # Success state
        success_state = sfn.Succeed(self, "ProcessingComplete")

        # Failure state
        failure_state = sfn.Fail(
            self,
            "ProcessingFailed",
            cause="Job processing failed",
            error="JobFailed",
        )

        # Check if storage succeeded
        storage_check = sfn.Choice(self, "StorageSucceeded?")
        storage_check.when(
            sfn.Condition.string_equals("$.status", "SUCCESS"),
            success_state
        ).otherwise(failure_state)

        # Single file workflow
        single_file_workflow = (
            wait_state
            .next(check_status_task)
            .next(
                sfn.Choice(self, "JobComplete?")
                .when(
                    sfn.Condition.string_equals("$.status", "COMPLETED"),
                    store_task.next(storage_check),
                )
                .when(
                    sfn.Condition.string_equals("$.status", "FAILED"),
                    failure_state,
                )
                .otherwise(wait_state)
            )
        )

        # Main workflow: Check if PDF, then branch
        is_pdf_check.when(
            sfn.Condition.is_present("$.pdfPages"),
            pdf_map_state.next(pdf_success)
        ).otherwise(single_file_workflow)

        # Define the complete workflow
        definition = process_task.next(is_pdf_check)

        return sfn.StateMachine(
            self,
            "EmbedderStateMachine",
            definition=definition,
            timeout=Duration.hours(2),
        )

    def _setup_s3_trigger(self):
        """Setup S3 event notification to trigger state machine"""
        # Create Lambda to trigger Step Functions
        trigger_lambda = lambda_.Function(
            self,
            "TriggerFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline(
                f"""
import json
import boto3
from urllib.parse import unquote_plus

sfn = boto3.client('stepfunctions')

def handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        # URL-decode the key (S3 events URL-encode special characters)
        key = unquote_plus(key)
        
        # Skip derived files to avoid infinite loop
        if key.startswith('pdf-pages/'):
            print(f"Skipping PDF page image: {{key}}")
            continue
        if key.startswith('docx-text/'):
            print(f"Skipping extracted DOCX text: {{key}}")
            continue
        
        # Start state machine execution
        sfn.start_execution(
            stateMachineArn='{self.state_machine.state_machine_arn}',
            input=json.dumps({{
                'bucket': bucket,
                'key': key
            }})
        )
    
    return {{'statusCode': 200}}
"""
            ),
            timeout=Duration.seconds(30),
            log_retention=logs.RetentionDays.THREE_DAYS,  # Auto-delete logs after 3 days
        )

        # Grant permissions
        self.state_machine.grant_start_execution(trigger_lambda)
        self.source_bucket.grant_read(trigger_lambda)

        # Add S3 notification
        self.source_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(trigger_lambda),
        )
