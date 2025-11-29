#!/bin/bash

# Test script for Polymarket Copy Trading Platform

set -e

echo "🧪 Running Polymarket Copy Trading Tests"
echo "========================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Install test dependencies
echo -e "${YELLOW}📦 Installing test dependencies...${NC}"
pip install -r requirements-test.txt

# Create test database
echo -e "${YELLOW}🗄️  Setting up test database...${NC}"
createdb polymarket_test || echo "Test database already exists"

# Run unit tests
echo -e "${YELLOW}🔬 Running unit tests...${NC}"
pytest tests/unit -v --cov=app --cov-report=term-missing

# Run integration tests
echo -e "${YELLOW}🔗 Running integration tests...${NC}"
pytest tests/integration -v

# Generate coverage report
echo -e "${YELLOW}📊 Generating coverage report...${NC}"
pytest --cov=app --cov-report=html --cov-report=xml

# Check coverage threshold
echo -e "${YELLOW}✅ Checking coverage threshold (80%)...${NC}"
coverage report --fail-under=80

echo -e "${GREEN}✅ All tests passed!${NC}"
echo "Coverage report: htmlcov/index.html"
