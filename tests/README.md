# PhysioNet MCP Test Suite

Comprehensive test suite for the physionet-mcp server.

## Test Coverage

**69 tests** covering **85% of the codebase**

### Test Files

1. **test_security.py** (32 tests)
   - SQL injection protection (`_is_safe_query`)
   - Parameter validation (`_validate_limit`)
   - All attack vectors (multiple statements, dangerous keywords, injection patterns)

2. **test_tools.py** (25 tests)
   - `list_accessible_datasets` - Dataset discovery
   - `get_database_schema` - Table listing with categorization
   - `get_table_info` - Schema inspection with sample data
   - `execute_query` - Query execution with validation
   - Error handling and helpful error messages

3. **test_integration.py** (12 tests)
   - BigQuery client initialization
   - Cross-project access patterns
   - FastMCP integration
   - Result limiting and formatting
   - Error message quality

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_security.py

# Run specific test
pytest tests/test_security.py::TestIsSafeQuery::test_valid_select_query

# Run without coverage (faster)
pytest --no-cov

# Generate HTML coverage report
pytest --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Structure

### Fixtures (conftest.py)

- `setup_test_env`: Auto-runs for every test, sets `BIGQUERY_PROJECT_ID` and cleans up module cache
- `mock_bigquery_client`: Provides mocked BigQuery client with common responses
- `mock_query_job`: Provides mocked query job with sample DataFrame

### Accessing MCP Tools in Tests

FastMCP decorates functions with `@mcp.tool()`, which wraps them in `FunctionTool` objects. To call these in tests:

```python
# Access the underlying function via .fn attribute
result = server.list_accessible_datasets.fn()
result = server.execute_query.fn("SELECT * FROM table")
```

## Test Categories

### Security Tests
- ✅ Valid SELECT queries (simple, joins, aggregates)
- ✅ Blocked statements (INSERT, UPDATE, DELETE, DROP, CREATE, etc.)
- ✅ Injection patterns (1=1, OR '1'='1', SLEEP, WAITFOR, BENCHMARK)
- ✅ Multiple statements
- ✅ Case-insensitive validation
- ✅ Complex analytical queries

### Tool Tests
- ✅ Success cases with proper mocked responses
- ✅ Empty/no results scenarios
- ✅ Access denied errors
- ✅ Table/column not found errors
- ✅ Data categorization and formatting
- ✅ Result truncation (50+ rows)
- ✅ Helpful error messages with actionable next steps

### Integration Tests
- ✅ Backend initialization with environment variables
- ✅ Cross-project BigQuery access (user project vs physionet-data)
- ✅ FastMCP tool registration
- ✅ Main entry point
- ✅ Error message formatting (emojis, actionable steps)

## Adding New Tests

1. Create test function with descriptive name:
```python
def test_my_new_feature(self, mcp_server_with_client):
    """Test description."""
    server, mock_client = mcp_server_with_client
    # Setup mocks
    # Call function
    # Assert results
```

2. Use fixtures for common setup:
   - `mcp_server_module` for security/helper tests
   - `mcp_server_with_client` for tool tests

3. Mock BigQuery responses as needed:
```python
mock_client.query.return_value = mock_job
mock_client.list_datasets.return_value = [mock_dataset]
```

## Coverage Goals

Current: **85%**

Uncovered areas (intentional):
- Error paths that are hard to trigger in unit tests
- Some exception handling branches
- Edge cases in error message formatting

To improve coverage, focus on:
- More edge cases in table name resolution
- Additional error scenarios
- Boundary conditions in data formatting
