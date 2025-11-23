import boto3
import json

client = boto3.client('s3vectors')

# Get the service model
service_model = client._service_model
operation_model = service_model.operation_model('QueryVectors')

# Get the input shape
input_shape = operation_model.input_shape._shape_resolver._shape_map

print("=== QueryVectors Input Parameters ===")
query_input = input_shape.get('QueryVectorsInput', {})
print(json.dumps(query_input, indent=2, default=str))

print("\n=== Filter Parameter Details ===")
if 'filter' in query_input.get('members', {}):
    filter_shape_name = query_input['members']['filter'].get('shape')
    filter_shape = input_shape.get(filter_shape_name, {})
    print(json.dumps(filter_shape, indent=2, default=str))
else:
    print("No filter parameter found")
