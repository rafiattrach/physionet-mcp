"""
Tests for MCP tools: list_accessible_datasets, get_database_schema, get_table_info, execute_query
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
import pandas as pd


@pytest.fixture
def mock_bq_client():
    """Create a mock BigQuery client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def mcp_server_with_client(mock_bq_client):
    """Import mcp_server module with mocked BigQuery client."""
    with patch('google.cloud.bigquery.Client') as mock_client_class:
        mock_client_class.return_value = mock_bq_client

        import physionet_mcp.mcp_server as server
        # Ensure the global client is our mock
        server._bq_client = mock_bq_client
        return server, mock_bq_client


class TestListAccessibleDatasets:
    """Test suite for list_accessible_datasets tool."""

    def test_list_datasets_success(self, mcp_server_with_client):
        """Test successful dataset listing."""
        server, mock_client = mcp_server_with_client

        # Mock datasets
        mock_ds1 = Mock()
        mock_ds1.dataset_id = "mimiciv_3_1_hosp"
        mock_ds2 = Mock()
        mock_ds2.dataset_id = "mimiciv_3_1_icu"
        mock_ds3 = Mock()
        mock_ds3.dataset_id = "eicu_crd"

        mock_client.list_datasets.return_value = [mock_ds1, mock_ds2, mock_ds3]

        # Access the underlying function via .fn attribute
        result = server.list_accessible_datasets.fn()

        assert "Found 3 accessible PhysioNet datasets" in result
        assert "mimiciv_3_1_hosp" in result
        assert "mimiciv_3_1_icu" in result
        assert "eicu_crd" in result
        assert "MIMIC-IV Hospital" in result
        assert "MIMIC-IV ICU" in result
        mock_client.list_datasets.assert_called_once_with(project='physionet-data')

    def test_list_datasets_empty(self, mcp_server_with_client):
        """Test when no datasets are accessible."""
        server, mock_client = mcp_server_with_client
        mock_client.list_datasets.return_value = []

        result = server.list_accessible_datasets.fn()

        assert "No accessible PhysioNet datasets found" in result
        assert "Request access" in result
        assert "physionet.org" in result

    def test_list_datasets_access_denied(self, mcp_server_with_client):
        """Test when access is denied."""
        server, mock_client = mcp_server_with_client
        mock_client.list_datasets.side_effect = Exception("Access denied")

        result = server.list_accessible_datasets.fn()

        assert "Access denied" in result or "Error discovering datasets" in result

    def test_list_datasets_categorization(self, mcp_server_with_client):
        """Test that datasets are properly categorized."""
        server, mock_client = mcp_server_with_client

        # Create varied dataset mocks
        datasets = [
            ("mimiciv_3_1_hosp", "MIMIC-IV Hospital"),
            ("mimiciv_3_1_icu", "MIMIC-IV ICU"),
            ("mimiciv_3_1_derived", "MIMIC-IV Derived"),
            ("mimiciii_clinical", "MIMIC-III Clinical"),
            ("eicu_crd", "eICU Database"),
        ]

        mock_datasets = []
        for ds_id, expected_category in datasets:
            mock_ds = Mock()
            mock_ds.dataset_id = ds_id
            mock_datasets.append(mock_ds)

        mock_client.list_datasets.return_value = mock_datasets

        result = server.list_accessible_datasets.fn()

        # Check all categories appear
        for ds_id, category in datasets:
            assert ds_id in result
            assert category in result


class TestGetDatabaseSchema:
    """Test suite for get_database_schema tool."""

    def test_get_schema_no_dataset_provided(self, mcp_server_with_client):
        """Test when no dataset name is provided."""
        server, mock_client = mcp_server_with_client

        result = server.get_database_schema.fn(None)

        assert "PhysioNet Dataset Selection Required" in result
        assert "mimiciv_3_1_hosp" in result
        assert "Step 1" in result

    def test_get_schema_success(self, mcp_server_with_client):
        """Test successful schema retrieval."""
        server, mock_client = mcp_server_with_client

        # Mock tables
        mock_table1 = Mock()
        mock_table1.table_id = "patients"
        mock_table2 = Mock()
        mock_table2.table_id = "admissions"

        mock_dataset_ref = Mock()
        mock_client.dataset.return_value = mock_dataset_ref
        mock_client.list_tables.return_value = [mock_table1, mock_table2]

        result = server.get_database_schema.fn("mimiciv_3_1_hosp")

        assert "mimiciv_3_1_hosp" in result
        assert "patients" in result
        assert "admissions" in result
        assert "Available Tables" in result
        mock_client.dataset.assert_called_once_with("mimiciv_3_1_hosp", project='physionet-data')

    def test_get_schema_no_tables(self, mcp_server_with_client):
        """Test when dataset has no accessible tables."""
        server, mock_client = mcp_server_with_client

        mock_dataset_ref = Mock()
        mock_client.dataset.return_value = mock_dataset_ref
        mock_client.list_tables.return_value = []

        result = server.get_database_schema.fn("mimiciv_3_1_hosp")

        assert "not accessible" in result
        assert "mimiciv_3_1_hosp" in result

    def test_get_schema_access_error(self, mcp_server_with_client):
        """Test when access to dataset is denied."""
        server, mock_client = mcp_server_with_client

        mock_client.dataset.side_effect = Exception("Access denied to physionet-data")

        result = server.get_database_schema.fn("mimiciv_3_1_hosp")

        assert "Cannot access physionet-data project" in result or "Auto-detection failed" in result

    def test_get_schema_table_categorization(self, mcp_server_with_client):
        """Test that tables are properly categorized."""
        server, mock_client = mcp_server_with_client

        # Mock tables with different categories
        table_names = ["patients", "admissions", "icustays", "labevents", "prescriptions", "diagnoses_icd", "procedures_icd"]
        mock_tables = []
        for name in table_names:
            mock_table = Mock()
            mock_table.table_id = name
            mock_tables.append(mock_table)

        mock_dataset_ref = Mock()
        mock_client.dataset.return_value = mock_dataset_ref
        mock_client.list_tables.return_value = mock_tables

        result = server.get_database_schema.fn("mimiciv_3_1_hosp")

        # Check that category headers appear
        assert "Demographics" in result or "patients" in result
        assert "Admissions" in result or "admissions" in result


class TestGetTableInfo:
    """Test suite for get_table_info tool."""

    def test_get_table_info_simple_name_single_match(self, mcp_server_with_client):
        """Test table lookup with simple name that has one match."""
        server, mock_client = mcp_server_with_client

        # Mock accessible datasets
        mock_ds = Mock()
        mock_ds.dataset_id = "mimiciv_3_1_hosp"
        mock_client.list_datasets.return_value = [mock_ds]

        # Mock schema query result
        mock_job = Mock()
        mock_df = pd.DataFrame({
            'column_name': ['subject_id', 'gender', 'anchor_age'],
            'data_type': ['INTEGER', 'STRING', 'INTEGER'],
            'is_nullable': ['YES', 'YES', 'YES']
        })
        mock_job.to_dataframe.return_value = mock_df
        mock_client.query.return_value = mock_job

        # Mock table reference for get_table API
        mock_table_ref = Mock()
        mock_field1 = Mock()
        mock_field1.name = "subject_id"
        mock_field1.field_type = "INTEGER"
        mock_field1.mode = "NULLABLE"
        mock_table_ref.schema = [mock_field1]
        mock_client.get_table.return_value = mock_table_ref

        result = server.get_table_info.fn("patients", show_sample=False)

        assert "patients" in result
        assert "subject_id" in result
        assert "Column Information" in result

    def test_get_table_info_fully_qualified_name(self, mcp_server_with_client):
        """Test table lookup with fully qualified name."""
        server, mock_client = mcp_server_with_client

        # Mock table reference
        mock_table_ref = Mock()
        mock_field = Mock()
        mock_field.name = "subject_id"
        mock_field.field_type = "INTEGER"
        mock_field.mode = "NULLABLE"
        mock_table_ref.schema = [mock_field]
        mock_client.get_table.return_value = mock_table_ref

        # Mock sample query
        mock_job = Mock()
        mock_df = pd.DataFrame({'subject_id': [1, 2, 3]})
        mock_job.to_dataframe.return_value = mock_df
        mock_client.query.return_value = mock_job

        result = server.get_table_info.fn("physionet-data.mimiciv_3_1_hosp.patients", show_sample=True)

        assert "patients" in result
        assert "subject_id" in result
        assert "Sample Data" in result

    def test_get_table_info_with_sample(self, mcp_server_with_client):
        """Test that sample data is included when requested."""
        server, mock_client = mcp_server_with_client

        # Mock table reference
        mock_table_ref = Mock()
        mock_field = Mock()
        mock_field.name = "subject_id"
        mock_field.field_type = "INTEGER"
        mock_field.mode = "NULLABLE"
        mock_table_ref.schema = [mock_field]
        mock_client.get_table.return_value = mock_table_ref

        # Mock sample query
        mock_job = Mock()
        mock_df = pd.DataFrame({
            'subject_id': [10000032, 10000033, 10000034],
            'gender': ['M', 'F', 'M']
        })
        mock_job.to_dataframe.return_value = mock_df
        mock_client.query.return_value = mock_job

        result = server.get_table_info.fn("physionet-data.mimiciv_3_1_hosp.patients", show_sample=True)

        assert "Sample Data" in result
        assert "10000032" in result

    def test_get_table_info_not_found(self, mcp_server_with_client):
        """Test when table is not found."""
        server, mock_client = mcp_server_with_client

        # Mock accessible datasets
        mock_ds = Mock()
        mock_ds.dataset_id = "mimiciv_3_1_hosp"
        mock_client.list_datasets.return_value = [mock_ds]

        # Mock query that returns no results
        mock_job = Mock()
        mock_df = pd.DataFrame()
        mock_job.to_dataframe.return_value = mock_df
        mock_client.query.return_value = mock_job

        result = server.get_table_info.fn("nonexistent_table", show_sample=False)

        assert "not found" in result

    def test_get_table_info_multiple_matches(self, mcp_server_with_client):
        """Test when simple name matches multiple tables."""
        server, mock_client = mcp_server_with_client

        # Mock multiple datasets
        mock_ds1 = Mock()
        mock_ds1.dataset_id = "mimiciv_3_1_hosp"
        mock_ds2 = Mock()
        mock_ds2.dataset_id = "mimiciii_clinical"
        mock_client.list_datasets.return_value = [mock_ds1, mock_ds2]

        # Mock queries that return results for both
        call_count = [0]

        def mock_query_side_effect(*args, **kwargs):
            mock_job = Mock()
            call_count[0] += 1
            # Return results for both datasets
            mock_df = pd.DataFrame({
                'column_name': ['subject_id'],
                'data_type': ['INTEGER'],
                'is_nullable': ['YES']
            })
            mock_job.to_dataframe.return_value = mock_df
            return mock_job

        mock_client.query.side_effect = mock_query_side_effect

        result = server.get_table_info.fn("patients", show_sample=False)

        # Should indicate multiple matches found
        assert "Multiple" in result or "specify which one" in result or "patients" in result


class TestExecuteQuery:
    """Test suite for execute_query tool."""

    def test_execute_valid_query(self, mcp_server_with_client):
        """Test execution of a valid SELECT query."""
        server, mock_client = mcp_server_with_client

        # Mock query result
        mock_job = Mock()
        mock_df = pd.DataFrame({
            'gender': ['M', 'F'],
            'count': [500, 450]
        })
        mock_job.to_dataframe.return_value = mock_df
        mock_client.query.return_value = mock_job

        query = "SELECT gender, COUNT(*) as count FROM `physionet-data.mimiciv_3_1_hosp.patients` GROUP BY gender"
        result = server.execute_query.fn(query)

        assert "gender" in result
        assert "500" in result
        assert "450" in result

    def test_execute_query_blocked_injection(self, mcp_server_with_client):
        """Test that injection attempts are blocked."""
        server, mock_client = mcp_server_with_client

        query = "SELECT * FROM patients WHERE 1=1"
        result = server.execute_query.fn(query)

        assert "Security Error" in result
        assert "injection pattern" in result.lower()

    def test_execute_query_blocked_multiple_statements(self, mcp_server_with_client):
        """Test that multiple statements are blocked."""
        server, mock_client = mcp_server_with_client

        query = "SELECT * FROM patients; DROP TABLE patients;"
        result = server.execute_query.fn(query)

        assert "Security Error" in result
        assert "Multiple statements" in result

    def test_execute_query_blocked_insert(self, mcp_server_with_client):
        """Test that INSERT is blocked."""
        server, mock_client = mcp_server_with_client

        query = "INSERT INTO patients VALUES (1, 'M', 50)"
        result = server.execute_query.fn(query)

        assert "Security Error" in result
        assert "Only SELECT queries allowed" in result

    def test_execute_query_empty_result(self, mcp_server_with_client):
        """Test query that returns no results."""
        server, mock_client = mcp_server_with_client

        mock_job = Mock()
        mock_df = pd.DataFrame()
        mock_job.to_dataframe.return_value = mock_df
        mock_client.query.return_value = mock_job

        query = "SELECT * FROM `physionet-data.mimiciv_3_1_hosp.patients` WHERE subject_id = -1"
        result = server.execute_query.fn(query)

        assert "No results found" in result

    def test_execute_query_large_result_truncated(self, mcp_server_with_client):
        """Test that large results are truncated."""
        server, mock_client = mcp_server_with_client

        # Create a DataFrame with more than 50 rows
        mock_job = Mock()
        mock_df = pd.DataFrame({
            'subject_id': range(100),
            'gender': ['M'] * 100
        })
        mock_job.to_dataframe.return_value = mock_df
        mock_client.query.return_value = mock_job

        query = "SELECT * FROM `physionet-data.mimiciv_3_1_hosp.patients`"
        result = server.execute_query.fn(query)

        assert "100 total rows" in result
        assert "showing first 50" in result

    def test_execute_query_table_not_found_error(self, mcp_server_with_client):
        """Test helpful error message for table not found."""
        server, mock_client = mcp_server_with_client

        mock_client.query.side_effect = Exception("table not found: nonexistent_table")

        query = "SELECT * FROM `physionet-data.mimiciv_3_1_hosp.nonexistent_table`"
        result = server.execute_query.fn(query)

        assert "Query Failed" in result
        assert "Table name issue" in result or "table not found" in result.lower()
        assert "get_database_schema" in result

    def test_execute_query_column_not_found_error(self, mcp_server_with_client):
        """Test helpful error message for column not found."""
        server, mock_client = mcp_server_with_client

        mock_client.query.side_effect = Exception("column not found: invalid_column")

        query = "SELECT invalid_column FROM `physionet-data.mimiciv_3_1_hosp.patients`"
        result = server.execute_query.fn(query)

        assert "Query Failed" in result
        assert "Column name issue" in result or "column not found" in result.lower()
        assert "get_table_info" in result

    def test_execute_query_syntax_error(self, mcp_server_with_client):
        """Test helpful error message for SQL syntax error."""
        server, mock_client = mcp_server_with_client

        mock_client.query.side_effect = Exception("syntax error at position 10")

        query = "SELECT * FROMM patients"  # Typo
        result = server.execute_query.fn(query)

        assert "Query Failed" in result
        assert "syntax error" in result.lower()


class TestBigQueryHelpers:
    """Test suite for internal BigQuery helper functions."""

    def test_execute_bigquery_query(self, mcp_server_with_client):
        """Test _execute_bigquery_query internal function."""
        server, mock_client = mcp_server_with_client

        mock_job = Mock()
        mock_df = pd.DataFrame({'test': [1, 2, 3]})
        mock_job.to_dataframe.return_value = mock_df
        mock_client.query.return_value = mock_job

        result = server._execute_bigquery_query("SELECT * FROM test")

        assert "test" in result
        assert "1" in result

    def test_execute_query_internal_security_check(self, mcp_server_with_client):
        """Test that _execute_query_internal performs security checks."""
        server, mock_client = mcp_server_with_client

        # Test with unsafe query
        result = server._execute_query_internal("DROP TABLE patients")

        assert "Security Error" in result
        mock_client.query.assert_not_called()  # Should not reach query execution
