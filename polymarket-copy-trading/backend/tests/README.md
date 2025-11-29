# Test Suite Documentation

## Overview

Comprehensive test suite for the Polymarket Copy Trading Platform with >80% code coverage target.

## Test Structure

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── factories.py             # Test data factories
├── unit/                    # Unit tests
│   ├── test_security.py     # JWT and password hashing tests
│   ├── test_auth_service.py # Authentication service tests
│   └── test_encryption.py   # API key encryption tests
└── integration/             # Integration tests
    ├── test_auth_api.py     # Auth endpoints tests
    └── test_traders_api.py  # Traders endpoints tests
```

## Running Tests

### All Tests
```bash
cd backend
./run_tests.sh
```

### Unit Tests Only
```bash
pytest tests/unit -v
```

### Integration Tests Only
```bash
pytest tests/integration -v
```

### With Coverage
```bash
pytest --cov=app --cov-report=html
```

### Specific Test File
```bash
pytest tests/unit/test_security.py -v
```

### Specific Test Function
```bash
pytest tests/unit/test_security.py::TestJWTTokens::test_create_access_token -v
```

## Test Coverage

Target: **>80%**

Current coverage includes:
- ✅ Authentication (JWT, passwords, registration, login)
- ✅ API key encryption/decryption
- ✅ User management
- ✅ API endpoints (auth, traders)
- ⏳ Trading logic (to be added)
- ⏳ Copy relationship management (to be added)
- ⏳ Dashboard services (to be added)

### View Coverage Report
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Test Database

Tests use a separate database: `polymarket_test`

**Setup:**
```bash
createdb polymarket_test
```

**Cleanup:**
```bash
dropdb polymarket_test
```

## Fixtures

### `db_session`
Provides an async database session with automatic rollback.

```python
async def test_something(db_session: AsyncSession):
    # Your test code
    pass
```

### `client`
Provides an async HTTP client for API testing.

```python
async def test_api(client: AsyncClient):
    response = await client.get("/api/v1/endpoint")
    assert response.status_code == 200
```

### `auth_headers`
Provides authentication headers with a test JWT.

```python
async def test_protected(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/protected", headers=auth_headers)
    assert response.status_code == 200
```

## Test Factories

Use factories to generate test data:

```python
from tests.factories import UserFactory, TraderFactory

# Create a user
user = UserFactory()

# Create a trader with specific values
trader = TraderFactory(pnl_7d=1000.0, win_rate=75.0)
```

## CI/CD Integration

Tests run automatically on:
- Push to `main` or `develop`
- Pull requests to `main` or `develop`

**GitHub Actions workflow:** `.github/workflows/tests.yml`

### Required Secrets
None required for tests (uses test config).

### Coverage Reporting
Coverage reports are uploaded to Codecov automatically.

## Writing New Tests

### Unit Test Template
```python
import pytest

class TestMyFeature:
    """Test my feature"""
    
    def test_basic_functionality(self):
        """Test basic functionality"""
        result = my_function()
        assert result == expected_value
    
    async def test_async_functionality(self, db_session):
        """Test async functionality"""
        result = await my_async_function(db_session)
        assert result is not None
```

### Integration Test Template
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
class TestMyAPI:
    """Test my API endpoints"""
    
    async def test_get_endpoint(self, client: AsyncClient):
        """Test GET endpoint"""
        response = await client.get("/api/v1/my-endpoint")
        
        assert response.status_code == 200
        data = response.json()
        assert "key" in data
```

## Mocking

### Mock External APIs
```python
from unittest.mock import patch, MagicMock

@patch('app.services.external_api.make_request')
def test_with_mock(mock_request):
    mock_request.return_value = {"status": "success"}
    
    result = my_function_that_calls_api()
    assert result["status"] == "success"
```

### Mock Database
Already handled by `db_session` fixture.

## Performance Tests

Coming soon: Load testing with Locust.

## Troubleshooting

### Database Connection Errors
Ensure PostgreSQL is running and test database exists:
```bash
createdb polymarket_test
```

### ImportError
Install test dependencies:
```bash
pip install -r requirements-test.txt
```

### Async Warnings
Add `asyncio` marker:
```python
@pytest.mark.asyncio
async def test_async_function():
    pass
```

## Best Practices

1. ✅ Use descriptive test names
2. ✅ One assertion per test (when possible)
3. ✅ Use fixtures for setup/teardown
4. ✅ Mock external dependencies
5. ✅ Test edge cases and error conditions
6. ✅ Keep tests independent
7. ✅ Use factories for test data
8. ✅ Maintain >80% coverage

## Next Steps

- [ ] Add trade execution tests
- [ ] Add P&L calculation tests
- [ ] Add WebSocket tests
- [ ] Add E2E tests with Playwright
- [ ] Add performance tests
- [ ] Add frontend component tests
