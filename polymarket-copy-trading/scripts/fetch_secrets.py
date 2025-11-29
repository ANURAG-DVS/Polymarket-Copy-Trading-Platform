#!/usr/bin/env python3
"""
Fetch secrets from AWS Secrets Manager
Used in production to load environment variables securely
"""

import os
import sys
import json
import boto3
from botocore.exceptions import ClientError

def fetch_secrets(secret_name: str, region_name: str = "us-east-1") -> dict:
    """
    Fetch secrets from AWS Secrets Manager
    
    Args:
        secret_name: Name of the secret in Secrets Manager
        region_name: AWS region
    
    Returns:
        Dictionary of secret key-value pairs
    """
    
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"❌ Secret {secret_name} not found in {region_name}")
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            print(f"❌ Invalid request for secret {secret_name}")
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            print(f"❌ Invalid parameter for secret {secret_name}")
        elif e.response['Error']['Code'] == 'DecryptionFailure':
            print(f"❌ Failed to decrypt secret {secret_name}")
        elif e.response['Error']['Code'] == 'InternalServiceError':
            print(f"❌ Internal service error retrieving {secret_name}")
        else:
            print(f"❌ Unexpected error: {e}")
        raise e
    else:
        # Parse secret
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            return json.loads(secret)
        else:
            # Binary secret (not common for config)
            raise ValueError("Binary secrets not supported")

def write_env_file(secrets: dict, output_file: str = ".env"):
    """Write secrets to .env file"""
    
    with open(output_file, 'w') as f:
        for key, value in secrets.items():
            # Never log secret values
            f.write(f"{key}={value}\n")
    
    print(f"✅ Secrets written to {output_file}")
    print(f"📝 Loaded {len(secrets)} environment variables")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch secrets from AWS Secrets Manager")
    parser.add_argument("--secret-name", required=True, help="Secret name in AWS Secrets Manager")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--output", default=".env", help="Output file path")
    parser.add_argument("--print", action="store_true", help="Print keys (not values)")
    
    args = parser.parse_args()
    
    print(f"\n🔐 Fetching secrets from AWS Secrets Manager...")
    print(f"   Secret: {args.secret_name}")
    print(f"   Region: {args.region}\n")
    
    try:
        secrets = fetch_secrets(args.secret_name, args.region)
        
        if args.print:
            print("📋 Available secret keys:")
            for key in secrets.keys():
                print(f"  - {key}")
            print()
        
        write_env_file(secrets, args.output)
        
        print(f"\n✅ Secrets loaded successfully!")
        print(f"⚠️  Remember to add {args.output} to .gitignore\n")
        
        return 0
    
    except Exception as e:
        print(f"\n❌ Failed to fetch secrets: {e}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
