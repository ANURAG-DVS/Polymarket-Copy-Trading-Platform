#!/usr/bin/env python3
"""
Environment configuration validator
Ensures all required environment variables are present and valid
"""

import os
import sys
from typing import Dict, List, Optional
from dotenv import load_dotenv
import re

class ConfigValidator:
    """Validate environment configuration"""
    
    REQUIRED_VARS = {
        # Application
        "NODE_ENV": {"type": "string", "values": ["development", "staging", "production"]},
        "PORT": {"type": "int", "min": 1000, "max": 65535},
        "FRONTEND_URL": {"type": "url"},
        "API_URL": {"type": "url"},
        
        # Database
        "DATABASE_URL": {"type": "string", "min_length": 10},
        "DB_HOST": {"type": "string"},
        "DB_PORT": {"type": "int"},
        "DB_NAME": {"type": "string"},
        "DB_USER": {"type": "string"},
        "DB_PASSWORD": {"type": "string", "min_length": 8, "secret": True},
        
        # Redis
        "REDIS_URL": {"type": "string"},
        
        # Auth
        "JWT_SECRET": {"type": "string", "min_length": 32, "secret": True},
        "JWT_REFRESH_SECRET": {"type": "string", "min_length": 32, "secret": True},
        
        # Encryption
        "MASTER_ENCRYPTION_KEY": {"type": "string", "min_length": 32, "secret": True},
        
        # Blockchain
        "POLYGON_RPC_URL": {"type": "url"},
    }
    
    OPTIONAL_VARS = {
        "TELEGRAM_BOT_TOKEN": {"type": "string"},
        "SMTP_HOST": {"type": "string"},
        "STRIPE_SECRET_KEY": {"type": "string", "secret": True},
        "SENTRY_DSN": {"type": "url"},
    }
    
    def __init__(self, env_file: Optional[str] = None):
        """Initialize validator"""
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
    
    def validate_all(self) -> tuple[bool, List[str]]:
        """Validate all environment variables"""
        errors = []
        
        # Check required vars
        for var_name, rules in self.REQUIRED_VARS.items():
            error = self._validate_var(var_name, rules, required=True)
            if error:
                errors.append(error)
        
        # Check optional vars (if present)
        for var_name, rules in self.OPTIONAL_VARS.items():
            if os.getenv(var_name):
                error = self._validate_var(var_name, rules, required=False)
                if error:
                    errors.append(error)
        
        return len(errors) == 0, errors
    
    def _validate_var(self, var_name: str, rules: Dict, required: bool) -> Optional[str]:
        """Validate a single variable"""
        value = os.getenv(var_name)
        
        # Check if present
        if value is None:
            if required:
                return f"❌ {var_name}: MISSING (required)"
            return None
        
        # Check type and constraints
        var_type = rules.get("type")
        
        if var_type == "int":
            try:
                int_value = int(value)
                if "min" in rules and int_value < rules["min"]:
                    return f"❌ {var_name}: Value {int_value} below minimum {rules['min']}"
                if "max" in rules and int_value > rules["max"]:
                    return f"❌ {var_name}: Value {int_value} above maximum {rules['max']}"
            except ValueError:
                return f"❌ {var_name}: Must be an integer"
        
        elif var_type == "url":
            if not value.startswith(("http://", "https://", "redis://")):
                return f"❌ {var_name}: Must be a valid URL"
        
        elif var_type == "string":
            if "min_length" in rules and len(value) < rules["min_length"]:
                return f"❌ {var_name}: Length {len(value)} below minimum {rules['min_length']}"
            if "values" in rules and value not in rules["values"]:
                return f"❌ {var_name}: Must be one of {rules['values']}"
        
        return None
    
    def print_summary(self):
        """Print configuration summary"""
        print("\n" + "="*60)
        print("🔧 ENVIRONMENT CONFIGURATION SUMMARY")
        print("="*60 + "\n")
        
        print(f"Environment: {os.getenv('NODE_ENV', 'unknown')}")
        print(f"Port: {os.getenv('PORT', 'unknown')}")
        print(f"Database: {os.getenv('DB_NAME', 'unknown')}")
        print(f"Frontend URL: {os.getenv('FRONTEND_URL', 'unknown')}")
        print(f"API URL: {os.getenv('API_URL', 'unknown')}")
        
        print("\n" + "-"*60)
        print("🔐 SECRETS STATUS")
        print("-"*60 + "\n")
        
        secrets_status = {
            "JWT Secret": bool(os.getenv("JWT_SECRET")) and len(os.getenv("JWT_SECRET", "")) >= 32,
            "Encryption Key": bool(os.getenv("MASTER_ENCRYPTION_KEY")),
            "DB Password": bool(os.getenv("DB_PASSWORD")),
            "Polygon RPC": bool(os.getenv("POLYGON_RPC_URL")),
        }
        
        for secret, configured in secrets_status.items():
            status = "✅ Configured" if configured else "❌ Missing"
            print(f"{secret}: {status}")
        
        print("\n" + "-"*60)
        print("🎛️  FEATURES")
        print("-"*60 + "\n")
        
        features = {
            "Telegram Bot": os.getenv("ENABLE_TELEGRAM_BOT", "false") == "true",
            "Email Notifications": os.getenv("ENABLE_EMAIL_NOTIFICATIONS", "false") == "true",
            "WebSocket": os.getenv("ENABLE_WEBSOCKET", "true") == "true",
            "Auto Trading": os.getenv("ENABLE_AUTO_TRADING", "false") == "true",
        }
        
        for feature, enabled in features.items():
            status = "✅ Enabled" if enabled else "⏸️  Disabled"
            print(f"{feature}: {status}")
        
        print("\n" + "="*60 + "\n")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate environment configuration")
    parser.add_argument("--env-file", help="Path to .env file", default=None)
    parser.add_argument("--summary", action="store_true", help="Show configuration summary")
    
    args = parser.parse_args()
    
    validator = ConfigValidator(args.env_file)
    
    if args.summary:
        validator.print_summary()
        return 0
    
    print("\n🔍 Validating environment configuration...\n")
    
    is_valid, errors = validator.validate_all()
    
    if is_valid:
        print("✅ All required environment variables are valid!\n")
        validator.print_summary()
        return 0
    else:
        print("❌ Environment validation FAILED:\n")
        for error in errors:
            print(f"  {error}")
        print(f"\n💡 Found {len(errors)} error(s). Please fix and try again.\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
