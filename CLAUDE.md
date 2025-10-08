# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**physionet-mcp** is a lean MCP (Model Context Protocol) server that provides programmatic access to PhysioNet medical datasets stored in Google BigQuery. It exposes 4 core tools for dataset discovery and SQL-based analysis of medical data (MIMIC-IV, MIMIC-III, eICU, etc.).

### Key Architecture Concepts

1. **FastMCP Server**: Uses the `fastmcp` framework to expose tools as MCP endpoints (`src/physionet_mcp/mcp_server.py`)
2. **BigQuery Backend**: All data access goes through Google Cloud BigQuery client, accessing the `physionet-data` project
3. **Security-First**: SQL injection protection via `_is_safe_query()` - only SELECT statements allowed, blocks multiple statements and dangerous keywords
4. **Smart Discovery**: Tools auto-discover accessible datasets and tables using BigQuery API instead of hardcoded lists

### MCP Tool Architecture

The server exposes exactly 4 tools (decorated with `@mcp.tool()`):

1. **list_accessible_datasets()** - Discovers user's accessible PhysioNet datasets from `physionet-data` project
2. **get_database_schema(dataset_name)** - Lists tables in a specific PhysioNet dataset with categorization
3. **get_table_info(table_name, show_sample)** - Deep dive into table schema with sample data, supports fuzzy matching
4. **execute_query(sql_query)** - Executes validated SELECT queries with security checks and helpful error messages

All tools return formatted strings with emojis, structured information, and actionable next steps.

## Development Commands

### Setup and Installation

```bash
# Install uv if not present (required for development)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
uv pip install -e .

# Install with dev dependencies (if they exist)
uv pip install -e ".[dev]"
```

### Running the Server

```bash
# Development mode - run server directly
python -m physionet_mcp.mcp_server

# Production mode - via uvx (as end users would)
uvx physionet-mcp
```

### Testing

```bash
# Run all tests (via pre-commit hook)
pytest

# Run tests on specific file
pytest path/to/test_file.py

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Run ruff linter (auto-fix)
ruff check --fix src/

# Run ruff formatter
ruff format src/

# Run all pre-commit hooks manually
pre-commit run --all-files

# Install pre-commit hooks
pre-commit install
```

## Environment Configuration

### Required Environment Variables

- **BIGQUERY_PROJECT_ID**: Your Google Cloud project ID (for billing, NOT where data lives)

### BigQuery Authentication

The server expects Application Default Credentials (ADC):

```bash
# Set up ADC
gcloud auth application-default login

# Optionally export project ID
export BIGQUERY_PROJECT_ID=your-project-id
```

### Data Access Model

- **User's project** (`BIGQUERY_PROJECT_ID`): Handles billing and quota
- **physionet-data project**: Contains all PhysioNet datasets (users must "star" this project)
- Queries use cross-project references: `` `physionet-data.dataset.table` ``

## Code Patterns and Conventions

### Security Validation

All SQL queries MUST pass through `_is_safe_query()` before execution:

```python
is_safe, message = _is_safe_query(sql_query)
if not is_safe:
    return f"❌ **Security Error:** {message}"
```

Never bypass this validation. It blocks:
- Multiple statements (injection vector)
- Non-SELECT statements (INSERT, UPDATE, DELETE, DROP, etc.)
- Injection patterns (1=1, OR '1'='1', WAITFOR, SLEEP, etc.)

### Error Handling Pattern

Provide helpful, actionable error messages with emojis and next steps:

```python
try:
    # operation
except Exception as e:
    return f"""❌ **Error:** {e}

🛠️ **How to fix this:**
   • Specific suggestion 1
   • Specific suggestion 2

🎯 **Next Steps:**
1. Action 1
2. Action 2"""
```

### BigQuery Query Pattern

Always use `_execute_bigquery_query()` for internal queries, which:
- Limits output to 50 rows for display
- Converts results to pandas DataFrame
- Returns formatted string output

### Table Name Resolution

`get_table_info()` supports both:
- Simple names: `'patients'` - searches across accessible datasets
- Qualified names: `'physionet-data.mimiciv_3_1_hosp.patients'` - direct access

Always search user's accessible datasets first (via `_bq_client.list_datasets()`) rather than using hardcoded lists.

## Important Constraints

1. **No write operations**: Server is read-only by design (security)
2. **BigQuery-only**: No local database support, pure cloud access
3. **Cross-project access**: Queries always reference `physionet-data` project explicitly
4. **Result limits**: Queries auto-limited to 50 rows for display (prevents overwhelming output)
5. **Access control**: Relies on user's PhysioNet credentials + project starring

## Testing and Validation

- Pre-commit hooks run `pytest`, `ruff`, and formatting checks automatically
- Tests should validate SQL injection protection in `_is_safe_query()`
- Mock BigQuery client for integration tests (avoid real API calls)
- Test both simple and qualified table name resolution in `get_table_info()`

## Common Pitfalls

1. **Don't hardcode dataset names**: Use BigQuery API discovery (`list_datasets()`)
2. **Always validate SQL**: Never skip `_is_safe_query()` validation
3. **Cross-project syntax**: Remember backticks and full paths (`` `physionet-data.dataset.table` ``)
4. **Error message quality**: Medical researchers need clear guidance, not technical jargon
5. **Result size limits**: Always limit query results to prevent overwhelming output

## Publishing and Distribution

```bash
# Build package
uv build

# Package is distributed via PyPI as 'physionet-mcp'
# Users install with: uvx physionet-mcp
```

Entry point is `physionet-mcp` command (defined in `pyproject.toml` scripts section), which calls `mcp_server:main()`.
