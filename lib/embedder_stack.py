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
)
from constructs import Construct
import json


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
        )

        # Create S3 Vector bucket for embeddings
        self.vector_bucket = s3.Bucket(
            self,
            "VectorBucket",
            bucket_name=config["buckets"]["vector_bucket"],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
        )

        # Create S3 bucket for async job outputs
        self.output_bucket = s3.Bucket(
            self,
            "OutputBucket",
            bucket_name=f"{config['buckets']['source_bucket']}-outputs",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
        )

        # Store vector indexes metadata (will be created by Lambda)
        self.vector_indexes = {
            dim: f"embeddings-{dim}d" for dim in config["embedding"]["dimensions"]
        }

        # Create IAM role for Lambda functions with Bedrock access
        lambda_role = self._create_lambda_role()

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

    def _create_lambda_role(self) -> iam.Role:
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

        # Bedrock permissions
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock-runtime:InvokeModel",
                    "bedrock-runtime:InvokeModelWithResponseStream",
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/*"
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

        # S3 permissions
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
                    self.vector_bucket.bucket_arn,
                    f"{self.vector_bucket.bucket_arn}/*",
                    self.output_bucket.bucket_arn,
                    f"{self.output_bucket.bucket_arn}/*",
                ],
            )
        )

        # S3 Vector permissions (placeholder - adjust based on actual S3 Vector API)
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3vector:CreateIndex",
                    "s3vector:PutVector",
                    "s3vector:QueryVectors",
                    "s3vector:DescribeIndex",
                ],
                resources=["*"],
            )
        )

        return role

    def _create_processor_lambda(
        self, role: iam.Role, config: dict
    ) -> lambda_.Function:
        """Create Lambda 1: Nova MME Processor"""
        return lambda_.Function(
            self,
            "ProcessorFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/embedder/processor"),
            role=role,
            timeout=Duration.minutes(5),
            memory_size=512,
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
        )

    def _create_store_embeddings_lambda(
        self, role: iam.Role, config: dict
    ) -> lambda_.Function:
        """Create Lambda 3: Store Embeddings with MRL truncation"""
        return lambda_.Function(
            self,
            "StoreEmbeddingsFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/embedder/store_embeddings"),
            role=role,
            timeout=Duration.minutes(15),
            memory_size=2048,  # Need memory for numpy operations
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

        # Task: Check job status
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

        # Define the workflow
        definition = (
            process_task.next(wait_state)
            .next(check_status_task)
            .next(
                sfn.Choice(self, "JobComplete?")
                .when(
                    sfn.Condition.string_equals("$.status", "COMPLETED"),
                    store_task.next(success_state),
                )
                .when(
                    sfn.Condition.string_equals("$.status", "FAILED"),
                    failure_state,
                )
                .otherwise(wait_state)
            )
        )

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

sfn = boto3.client('stepfunctions')

def handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
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
        )

        # Grant permissions
        self.state_machine.grant_start_execution(trigger_lambda)
        self.source_bucket.grant_read(trigger_lambda)

        # Add S3 notification
        self.source_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(trigger_lambda),
        )
