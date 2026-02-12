"""
Integration tests for BigQuery backend initialization and configuration
"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


@pytest.fixture
def mcp_server_module():
    """Import mcp_server module with mocked BigQuery client."""
    with patch('google.cloud.bigquery.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        import physionet_mcp.mcp_server as server
        return server, mock_client


class TestBackendInitialization:
    """Test suite for BigQuery backend initialization."""

    def test_init_backend_success(self, mcp_server_module):
        """Test successful backend initialization."""
        server, mock_client = mcp_server_module

        assert server._project_id == 'test-project-id'
        assert server._bq_client is not None

    def test_module_has_required_attributes(self, mcp_server_module):
        """Test that module has expected attributes."""
        server, _ = mcp_server_module

        assert hasattr(server, 'mcp')
        assert hasattr(server, '_bq_client')
        assert hasattr(server, '_project_id')
        assert hasattr(server, 'list_accessible_datasets')
        assert hasattr(server, 'get_database_schema')
        assert hasattr(server, 'get_table_info')
        assert hasattr(server, 'execute_query')


class TestCrossProjectAccess:
    """Test cross-project BigQuery access patterns."""

    def test_physionet_data_project_access(self, mcp_server_module):
        """Test that queries properly reference physionet-data project."""
        server, mock_client = mcp_server_module

        mock_ds = MagicMock()
        mock_ds.dataset_id = "mimiciv_3_1_hosp"
        mock_client.list_datasets.return_value = [mock_ds]

        result = server.list_accessible_datasets.fn()

        # Verify list_datasets was called with physionet-data project
        mock_client.list_datasets.assert_called_with(project='physionet-data')

    def test_user_project_for_billing(self, mcp_server_module):
        """Test that user's project is used for BigQuery client (billing)."""
        server, _ = mcp_server_module

        # Client should be initialized with user's project
        assert server._project_id == 'test-project-id'


class TestMainEntryPoint:
    """Test the main() entry point function."""

    def test_main_function_exists(self, mcp_server_module):
        """Test that main() function exists and is callable."""
        server, _ = mcp_server_module

        assert hasattr(server, 'main')
        assert callable(server.main)

    def test_main_calls_mcp_run(self, mcp_server_module):
        """Test that main() calls mcp.run()."""
        server, _ = mcp_server_module

        # Mock the mcp.run() method
        server.mcp.run = MagicMock()

        # Call main
        server.main()

        # Verify mcp.run() was called
        server.mcp.run.assert_called_once()


class TestErrorMessageFormatting:
    """Test that error messages follow the expected format."""

    def test_error_messages_have_emojis(self, mcp_server_module):
        """Test that error messages include emoji formatting."""
        server, mock_client = mcp_server_module

        # Trigger error condition
        mock_client.list_datasets.return_value = []
        result = server.list_accessible_datasets.fn()

        # Check for emoji markers
        assert "❌" in result or "✅" in result or "🔧" in result

    def test_error_messages_have_actionable_steps(self, mcp_server_module):
        """Test that error messages include actionable next steps."""
        server, mock_client = mcp_server_module

        # Test with table not found error
        mock_client.query.side_effect = Exception("table not found")

        query = "SELECT * FROM nonexistent"
        result = server.execute_query.fn(query)

        # Should have helpful suggestions
        assert "get_database_schema" in result or "get_table_info" in result
        assert "Query Failed" in result


class TestDataFrameLimiting:
    """Test that query results are properly limited."""

    def test_result_limiting_over_50_rows(self, mcp_server_module):
        """Test that results over 50 rows are truncated."""
        server, mock_client = mcp_server_module

        # Create large result
        mock_job = MagicMock()
        large_df = pd.DataFrame({
            'id': range(100),
            'value': range(100)
        })
        mock_job.to_dataframe.return_value = large_df
        mock_client.query.return_value = mock_job

        result = server._execute_bigquery_query("SELECT * FROM large_table")

        # Should indicate truncation
        assert "100 total rows" in result
        assert "showing first 50" in result

    def test_result_no_limiting_under_50_rows(self, mcp_server_module):
        """Test that results under 50 rows are not truncated."""
        server, mock_client = mcp_server_module

        # Create small result
        mock_job = MagicMock()
        small_df = pd.DataFrame({
            'id': range(10),
            'value': range(10)
        })
        mock_job.to_dataframe.return_value = small_df
        mock_client.query.return_value = mock_job

        result = server._execute_bigquery_query("SELECT * FROM small_table")

        # Should not indicate truncation
        assert "total rows" not in result or "showing first" not in result


class TestFastMCPIntegration:
    """Test FastMCP server integration."""

    def test_fastmcp_instance_created(self, mcp_server_module):
        """Test that FastMCP server instance is created."""
        server, _ = mcp_server_module

        # Check MCP instance
        assert server.mcp is not None

    def test_tools_are_registered(self, mcp_server_module):
        """Test that all tools are registered with FastMCP."""
        server, _ = mcp_server_module

        # These functions should be decorated with @mcp.tool() - check they have .fn attribute
        assert hasattr(server.list_accessible_datasets, 'fn')
        assert hasattr(server.get_database_schema, 'fn')
        assert hasattr(server.get_table_info, 'fn')
        assert hasattr(server.execute_query, 'fn')

        # Verify the underlying functions are callable
        assert callable(server.list_accessible_datasets.fn)
        assert callable(server.get_database_schema.fn)
        assert callable(server.get_table_info.fn)
        assert callable(server.execute_query.fn)
