"""
Chatbot Stack - Query interface with hierarchical search

This stack creates:
- Query handler Lambda function
- API Gateway REST API
- Amplify app hosting (placeholder)
- IAM roles for Bedrock and S3 Vector access
"""

from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_apigateway as apigw,
    aws_s3 as s3,
    CfnOutput,
)
from constructs import Construct
import json


class ChatbotStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vector_bucket: s3.Bucket,
        source_bucket: s3.Bucket,
        vector_indexes: dict,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vector_bucket = vector_bucket
        self.source_bucket = source_bucket
        self.vector_indexes = vector_indexes

        # Load configuration
        config = self._load_config()

        # Create IAM role for Lambda
        lambda_role = self._create_lambda_role()

        # Create Query Handler Lambda
        self.query_handler = self._create_query_handler_lambda(lambda_role, config)

        # Create API Gateway
        self.api = self._create_api_gateway()

        # Output API endpoint
        CfnOutput(
            self,
            "ApiEndpoint",
            value=self.api.url,
            description="API Gateway endpoint for chatbot queries",
        )

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
                    "default_dimension": 1024,
                    "model_id": "amazon.nova-2-multimodal-embeddings-v1:0",
                },
                "search": {
                    "default_k": 5,
                    "hierarchical_enabled": True,
                    "hierarchical_config": {
                        "first_pass_dimension": 256,
                        "first_pass_k": 20,
                        "second_pass_dimension": 1024,
                        "second_pass_k": 5,
                    },
                },
                "llm": {
                    "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                    "max_tokens": 2048,
                    "temperature": 0.7,
                },
            }

    def _create_lambda_role(self) -> iam.Role:
        """Create IAM role with permissions for Bedrock, S3 Vector"""
        role = iam.Role(
            self,
            "ChatbotLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Bedrock permissions for embeddings and LLM
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

        # S3 Vector permissions for querying
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3vector:QueryVectors",
                    "s3vector:DescribeIndex",
                ],
                resources=["*"],
            )
        )

        # S3 read permissions for vector bucket
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=[
                    self.vector_bucket.bucket_arn,
                    f"{self.vector_bucket.bucket_arn}/*",
                ],
            )
        )

        # S3 read permissions for source bucket (to retrieve actual content)
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=[
                    self.source_bucket.bucket_arn,
                    f"{self.source_bucket.bucket_arn}/*",
                ],
            )
        )

        return role

    def _create_query_handler_lambda(
        self, role: iam.Role, config: dict
    ) -> lambda_.Function:
        """Create Query Handler Lambda"""
        return lambda_.Function(
            self,
            "QueryHandlerFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_asset("lambda/chatbot/query_handler"),
            role=role,
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment={
                "VECTOR_BUCKET": self.vector_bucket.bucket_name,
                "EMBEDDING_MODEL_ID": config["embedding"]["model_id"],
                "LLM_MODEL_ID": config["llm"]["model_id"],
                "DEFAULT_DIMENSION": str(config["embedding"]["default_dimension"]),
                "DEFAULT_K": str(config["search"]["default_k"]),
                "HIERARCHICAL_ENABLED": str(config["search"]["hierarchical_enabled"]),
                "HIERARCHICAL_CONFIG": json.dumps(
                    config["search"]["hierarchical_config"]
                ),
                "VECTOR_INDEXES": json.dumps(self.vector_indexes),
                "LLM_MAX_TOKENS": str(config["llm"]["max_tokens"]),
                "LLM_TEMPERATURE": str(config["llm"]["temperature"]),
            },
        )

    def _create_api_gateway(self) -> apigw.RestApi:
        """Create API Gateway REST API"""
        api = apigw.RestApi(
            self,
            "ChatbotApi",
            rest_api_name="Nova MME Chatbot API",
            description="API for Nova MME multimodal chatbot with MRL",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        # Create /query endpoint
        query_resource = api.root.add_resource("query")
        query_integration = apigw.LambdaIntegration(
            self.query_handler,
            proxy=True,
        )
        query_resource.add_method("POST", query_integration)

        # Create /health endpoint
        health_resource = api.root.add_resource("health")
        health_integration = apigw.MockIntegration(
            integration_responses=[
                apigw.IntegrationResponse(
                    status_code="200",
                    response_templates={
                        "application/json": '{"status": "healthy"}'
                    },
                )
            ],
            request_templates={"application/json": '{"statusCode": 200}'},
        )
        health_resource.add_method(
            "GET",
            health_integration,
            method_responses=[apigw.MethodResponse(status_code="200")],
        )

        return api
