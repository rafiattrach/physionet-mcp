"""
Pytest configuration and shared fixtures for physionet-mcp tests
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch
import pytest


@pytest.fixture(scope="function", autouse=True)
def setup_test_env():
    """Set up test environment and mock BigQuery for every test."""
    # Set environment variable
    os.environ['BIGQUERY_PROJECT_ID'] = 'test-project-id'

    # Remove module from cache if it exists
    if 'physionet_mcp.mcp_server' in sys.modules:
        del sys.modules['physionet_mcp.mcp_server']

    yield

    # Cleanup
    if 'BIGQUERY_PROJECT_ID' in os.environ:
        del os.environ['BIGQUERY_PROJECT_ID']
    if 'physionet_mcp.mcp_server' in sys.modules:
        del sys.modules['physionet_mcp.mcp_server']


@pytest.fixture
def mock_bigquery_client():
    """Mock BigQuery client for testing without real API calls."""
    mock_client = MagicMock()

    # Mock dataset listing
    mock_dataset = Mock()
    mock_dataset.dataset_id = "mimiciv_3_1_hosp"
    mock_client.list_datasets.return_value = [mock_dataset]

    # Mock table listing
    mock_table = Mock()
    mock_table.table_id = "patients"
    mock_client.list_tables.return_value = [mock_table]

    # Mock get_table for schema info
    mock_table_ref = Mock()
    mock_field = Mock()
    mock_field.name = "subject_id"
    mock_field.field_type = "INTEGER"
    mock_field.mode = "NULLABLE"
    mock_table_ref.schema = [mock_field]
    mock_client.get_table.return_value = mock_table_ref

    return mock_client


@pytest.fixture
def mock_query_job():
    """Mock BigQuery query job for testing query execution."""
    mock_job = MagicMock()

    # Mock DataFrame result
    import pandas as pd
    mock_df = pd.DataFrame({
        'subject_id': [1, 2, 3],
        'gender': ['M', 'F', 'M'],
        'anchor_age': [50, 65, 30]
    })
    mock_job.to_dataframe.return_value = mock_df

    return mock_job
