"""
Tests for SQL injection protection and security validation
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mcp_server_module():
    """Import mcp_server module with mocked BigQuery client."""
    # Patch before importing
    with patch('google.cloud.bigquery.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        import physionet_mcp.mcp_server as server
        return server


class TestIsSafeQuery:
    """Test suite for _is_safe_query SQL injection protection."""

    def test_valid_select_query(self, mcp_server_module):
        """Test that valid SELECT queries are allowed."""
        query = "SELECT * FROM patients WHERE age > 50"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is True
        assert message == "Safe"

    def test_valid_select_with_joins(self, mcp_server_module):
        """Test that SELECT with JOINs are allowed."""
        query = """
            SELECT p.subject_id, a.hadm_id
            FROM patients p
            JOIN admissions a ON p.subject_id = a.subject_id
            WHERE p.anchor_age > 50
        """
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is True

    def test_valid_select_with_aggregates(self, mcp_server_module):
        """Test that SELECT with aggregates are allowed."""
        query = "SELECT gender, COUNT(*) FROM patients GROUP BY gender"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is True

    def test_empty_query(self, mcp_server_module):
        """Test that empty queries are rejected."""
        is_safe, message = mcp_server_module._is_safe_query("")
        assert is_safe is False
        assert "Empty query" in message

    def test_whitespace_only_query(self, mcp_server_module):
        """Test that whitespace-only queries are rejected."""
        is_safe, message = mcp_server_module._is_safe_query("   \n  \t  ")
        assert is_safe is False
        assert "Empty query" in message

    def test_multiple_statements(self, mcp_server_module):
        """Test that multiple statements are blocked."""
        query = "SELECT * FROM patients; DROP TABLE patients;"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "Multiple statements" in message

    def test_insert_statement(self, mcp_server_module):
        """Test that INSERT statements are blocked."""
        query = "INSERT INTO patients VALUES (1, 'M', 50)"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "Only SELECT queries allowed" in message

    def test_update_statement(self, mcp_server_module):
        """Test that UPDATE statements are blocked."""
        query = "UPDATE patients SET age = 100 WHERE subject_id = 1"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "Only SELECT queries allowed" in message

    def test_delete_statement(self, mcp_server_module):
        """Test that DELETE statements are blocked."""
        query = "DELETE FROM patients WHERE subject_id = 1"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "Only SELECT queries allowed" in message

    def test_drop_statement(self, mcp_server_module):
        """Test that DROP statements are blocked."""
        query = "DROP TABLE patients"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "Only SELECT queries allowed" in message

    def test_create_statement(self, mcp_server_module):
        """Test that CREATE statements are blocked."""
        query = "CREATE TABLE new_table (id INT)"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "Only SELECT queries allowed" in message

    def test_alter_statement(self, mcp_server_module):
        """Test that ALTER statements are blocked."""
        query = "ALTER TABLE patients ADD COLUMN new_col VARCHAR(255)"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "Only SELECT queries allowed" in message

    def test_truncate_statement(self, mcp_server_module):
        """Test that TRUNCATE statements are blocked."""
        query = "TRUNCATE TABLE patients"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "Only SELECT queries allowed" in message

    def test_exec_statement(self, mcp_server_module):
        """Test that EXEC statements are blocked."""
        query = "EXEC sp_executesql N'SELECT * FROM patients'"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "Only SELECT queries allowed" in message

    def test_injection_pattern_1_equals_1(self, mcp_server_module):
        """Test that '1=1' injection pattern is blocked."""
        query = "SELECT * FROM patients WHERE 1=1"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "injection pattern" in message.lower()

    def test_injection_pattern_or_1_equals_1(self, mcp_server_module):
        """Test that 'OR 1=1' injection pattern is blocked."""
        query = "SELECT * FROM patients WHERE age > 50 OR 1=1"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "injection pattern" in message.lower()

    def test_injection_pattern_and_1_equals_1(self, mcp_server_module):
        """Test that 'AND 1=1' injection pattern is blocked."""
        query = "SELECT * FROM patients WHERE age > 50 AND 1=1"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "injection pattern" in message.lower()

    def test_injection_pattern_string_equality(self, mcp_server_module):
        """Test that string injection patterns are blocked."""
        query = "SELECT * FROM patients WHERE name = 'test' OR '1'='1'"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "injection pattern" in message.lower()

    def test_injection_pattern_waitfor(self, mcp_server_module):
        """Test that WAITFOR injection pattern is blocked."""
        query = "SELECT * FROM patients; WAITFOR DELAY '00:00:05'"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        # Will be caught by either multiple statements or injection pattern

    def test_injection_pattern_sleep(self, mcp_server_module):
        """Test that SLEEP injection pattern is blocked."""
        query = "SELECT * FROM patients WHERE SLEEP(5)"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "injection pattern" in message.lower()

    def test_injection_pattern_benchmark(self, mcp_server_module):
        """Test that BENCHMARK injection pattern is blocked."""
        query = "SELECT * FROM patients WHERE BENCHMARK(1000000, MD5('test'))"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False
        assert "injection pattern" in message.lower()

    def test_select_with_insert_keyword_in_string(self, mcp_server_module):
        """Test that SELECT with INSERT in string literal is allowed (not a keyword)."""
        query = "SELECT * FROM patients WHERE notes LIKE '%INSERT%'"
        is_safe, message = mcp_server_module._is_safe_query(query)
        # This should be safe - INSERT is inside a string literal, not a SQL keyword
        assert is_safe is True

    def test_select_with_actual_insert_statement(self, mcp_server_module):
        """Test that actual INSERT statements embedded are blocked."""
        query = "SELECT * FROM patients; INSERT INTO logs VALUES (1)"
        is_safe, message = mcp_server_module._is_safe_query(query)
        # This should be blocked by multiple statements check
        assert is_safe is False

    def test_case_insensitive_validation(self, mcp_server_module):
        """Test that validation is case-insensitive."""
        query = "select * from patients where Age > 50"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is True

    def test_case_insensitive_injection_detection(self, mcp_server_module):
        """Test that injection detection is case-insensitive."""
        query = "SELECT * FROM patients WHERE age > 50 or 1=1"
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is False

    def test_valid_complex_query(self, mcp_server_module):
        """Test a complex but valid analytical query."""
        query = """
            SELECT
                p.gender,
                AVG(a.los) as avg_length_of_stay,
                COUNT(DISTINCT a.hadm_id) as admission_count
            FROM `physionet-data.mimiciv_3_1_hosp.patients` p
            JOIN `physionet-data.mimiciv_3_1_hosp.admissions` a
                ON p.subject_id = a.subject_id
            WHERE p.anchor_age BETWEEN 30 AND 65
                AND a.admission_type = 'EMERGENCY'
            GROUP BY p.gender
            HAVING COUNT(DISTINCT a.hadm_id) > 10
            ORDER BY avg_length_of_stay DESC
            LIMIT 100
        """
        is_safe, message = mcp_server_module._is_safe_query(query)
        assert is_safe is True

    def test_invalid_sql_syntax(self, mcp_server_module):
        """Test that invalid SQL syntax is caught."""
        query = "SELECT * FROMM patients"  # Typo in FROM
        is_safe, message = mcp_server_module._is_safe_query(query)
        # Should still parse as SELECT, but might fail in other ways
        # This test ensures we don't crash on bad syntax
        assert isinstance(is_safe, bool)

    def test_null_query(self, mcp_server_module):
        """Test that None query is handled safely."""
        is_safe, message = mcp_server_module._is_safe_query(None)
        assert is_safe is False


class TestValidateLimit:
    """Test suite for _validate_limit parameter validation."""

    def test_valid_limit(self, mcp_server_module):
        """Test that valid limits are accepted."""
        assert mcp_server_module._validate_limit(10) is True
        assert mcp_server_module._validate_limit(100) is True
        assert mcp_server_module._validate_limit(1000) is True

    def test_limit_too_low(self, mcp_server_module):
        """Test that zero and negative limits are rejected."""
        assert mcp_server_module._validate_limit(0) is False
        assert mcp_server_module._validate_limit(-1) is False

    def test_limit_too_high(self, mcp_server_module):
        """Test that limits over 1000 are rejected."""
        assert mcp_server_module._validate_limit(1001) is False
        assert mcp_server_module._validate_limit(10000) is False

    def test_non_integer_limit(self, mcp_server_module):
        """Test that non-integer limits are rejected."""
        assert mcp_server_module._validate_limit("100") is False
        assert mcp_server_module._validate_limit(100.5) is False
        assert mcp_server_module._validate_limit(None) is False
