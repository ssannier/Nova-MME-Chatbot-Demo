#!/usr/bin/env python3
"""
Nova MME Demo CDK Application

This app defines the infrastructure for the Nova Multimodal Embeddings demo,
showcasing Matryoshka Relational Learning capabilities.
"""

import aws_cdk as cdk
from lib.embedder_stack import EmbedderStack
from lib.chatbot_stack import ChatbotStack

app = cdk.App()

# Get environment configuration
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1"
)

# Deploy embedder stack first (creates S3 Vector bucket and indexes)
embedder = EmbedderStack(
    app,
    "NovaMMEEmbedderStack",
    env=env,
    description="Nova MME Embedder - Async processing pipeline with MRL"
)

# Deploy chatbot stack (references embedder's S3 Vector bucket)
chatbot = ChatbotStack(
    app,
    "NovaMMEChatbotStack",
    vector_bucket=embedder.vector_bucket,
    vector_indexes=embedder.vector_indexes,
    env=env,
    description="Nova MME Chatbot - Query interface with hierarchical search"
)

# Add dependency to ensure embedder deploys first
chatbot.add_dependency(embedder)

app.synth()
