"""
PhysioNet MCP Server - Lean BigQuery-only MCP server for PhysioNet datasets
"""

import os
import pandas as pd  # Used for BigQuery result formatting (.head(), .to_string())
import sqlparse
from fastmcp import FastMCP

# Create FastMCP server instance
mcp = FastMCP("physionet-mcp")

# Global variables for BigQuery configuration
_bq_client = None
_project_id = None

# Note: Dataset discovery now uses efficient BigQuery client API instead of hardcoded lists


def _validate_limit(limit: int) -> bool:
    """Validate limit parameter to prevent resource exhaustion."""
    return isinstance(limit, int) and 0 < limit <= 1000


def _is_safe_query(sql_query: str) -> tuple[bool, str]:
    """Secure SQL validation - blocks injection attacks, allows legitimate queries."""
    try:
        if not sql_query or not sql_query.strip():
            return False, "Empty query"

        # Parse SQL to validate structure
        parsed = sqlparse.parse(sql_query.strip())
        if not parsed:
            return False, "Invalid SQL syntax"

        # Block multiple statements (main injection vector)
        if len(parsed) > 1:
            return False, "Multiple statements not allowed"

        statement = parsed[0]
        statement_type = statement.get_type()

        # Only allow SELECT statements
        if statement_type not in ("SELECT",):
            return False, "Only SELECT queries allowed"

        # Block dangerous write operations within SELECT
        sql_upper = sql_query.strip().upper()
        dangerous_keywords = {
            "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", 
            "TRUNCATE", "REPLACE", "MERGE", "EXEC", "EXECUTE"
        }

        for keyword in dangerous_keywords:
            if f" {keyword} " in f" {sql_upper} ":
                return False, f"Write operation not allowed: {keyword}"

        # Block common injection patterns
        injection_patterns = [
            ("1=1", "Classic injection pattern"),
            ("OR 1=1", "Boolean injection pattern"),
            ("AND 1=1", "Boolean injection pattern"),
            ("OR '1'='1'", "String injection pattern"),
            ("AND '1'='1'", "String injection pattern"),
            ("WAITFOR", "Time-based injection"),
            ("SLEEP(", "Time-based injection"),
            ("BENCHMARK(", "Time-based injection"),
        ]

        for pattern, description in injection_patterns:
            if pattern in sql_upper:
                return False, f"Injection pattern detected: {description}"

        return True, "Safe"

    except Exception as e:
        return False, f"Validation error: {e}"


def _init_backend():
    """Initialize BigQuery backend based on environment variables."""
    global _bq_client, _project_id

    try:
        from google.cloud import bigquery
    except ImportError:
        raise ImportError(
            "BigQuery dependencies not found. Install with: pip install google-cloud-bigquery"
        )

    # Get project ID from environment
    _project_id = os.getenv("BIGQUERY_PROJECT_ID")
    if not _project_id:
        raise ValueError(
            "BIGQUERY_PROJECT_ID environment variable is required. "
            "Set it to your Google Cloud project ID that has access to PhysioNet datasets."
        )

    try:
        _bq_client = bigquery.Client(project=_project_id)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize BigQuery client: {e}")


def _execute_bigquery_query(sql_query: str) -> str:
    """Execute BigQuery query - internal function."""
    try:
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig()
        query_job = _bq_client.query(sql_query, job_config=job_config)
        df = query_job.to_dataframe()

        if df.empty:
            return "No results found"

        # Limit output size
        if len(df) > 50:
            result = df.head(50).to_string(index=False)
            result += f"\n... ({len(df)} total rows, showing first 50)"
        else:
            result = df.to_string(index=False)

        return result

    except Exception as e:
        raise e


def _execute_query_internal(sql_query: str) -> str:
    """Internal query execution function with security validation."""
    # Security check
    is_safe, message = _is_safe_query(sql_query)
    if not is_safe:
        return f"❌ **Security Error:** {message}\n\n💡 **Tip:** Only SELECT statements are allowed for data analysis."

    try:
        return _execute_bigquery_query(sql_query)
    except Exception as e:
        error_msg = str(e).lower()
        suggestions = []

        if "table not found" in error_msg or "dataset not found" in error_msg:
            suggestions.append(
                "🔍 **Table name issue:** Use `get_database_schema()` to see exact table names"
            )
            suggestions.append(
                "💡 **Quick fix:** Check if the table name matches exactly (case-sensitive)"
            )

        if "column not found" in error_msg:
            suggestions.append(
                "🔍 **Column name issue:** Use `get_table_info('table_name')` to see available columns"
            )
            suggestions.append(
                "📝 **Common issue:** Column might be named differently than expected"
            )

        if "syntax error" in error_msg:
            suggestions.append(
                "📝 **SQL syntax issue:** Check quotes, commas, and parentheses"
            )
            suggestions.append(
                "💭 **Try simpler:** Start with `SELECT * FROM table_name LIMIT 5`"
            )

        if not suggestions:
            suggestions.append(
                "🔍 **Start exploration:** Use `get_database_schema()` to see available tables"
            )
            suggestions.append(
                "📋 **Check structure:** Use `get_table_info('table_name')` to understand the data"
            )

        suggestion_text = "\n".join(f"   {s}" for s in suggestions)

        return f"""❌ **Query Failed:** {e}

🛠️ **How to fix this:**
{suggestion_text}

🎯 **Quick Recovery Steps:**
1. `get_database_schema()` ← See what tables exist
2. `get_table_info('your_table')` ← Check exact column names
3. Retry your query with correct names"""


# Initialize backend when module is imported
_init_backend()


@mcp.tool()
def list_accessible_datasets() -> str:
    """🔍 Discover what PhysioNet datasets you have access to.

    **What this does:**
    - Lists your accessible datasets with descriptions
    - Shows categorized results by dataset type
    - Provides guidance for next steps

    **Perfect for:**
    - First-time setup verification
    - Seeing newly granted dataset access
    - Quick overview before deep exploration

    **Use this BEFORE** other tools to know what datasets to explore!

    Returns:
        Complete list of your accessible PhysioNet datasets
    """
    try:
        # Use BigQuery client to list accessible datasets
        datasets = list(_bq_client.list_datasets(project='physionet-data'))
        
        if not datasets:
            return """❌ **No accessible PhysioNet datasets found**

**This means:**
• You haven't requested PhysioNet access yet, OR
• You haven't starred the physionet-data project, OR  
• Your access is still being processed

**🔧 To get access:**
1. **Visit:** https://physionet.org/
2. **Find datasets:** Search for MIMIC-IV, MIMIC-III, or eICU
3. **Request access:** Click "Request access using Google BigQuery"
4. **Complete credentialing:** Follow PhysioNet's training requirements
5. **Star project:** Follow the email instructions to star physionet-data
6. **Wait:** Access can take 24-48 hours to activate

**✅ Once you have access:** This tool will show your available datasets instantly!"""

        # Categorize and describe datasets
        dataset_info = []
        for dataset in datasets:
            dataset_id = dataset.dataset_id
            
            # Smart categorization based on dataset naming patterns
            if 'mimiciv' in dataset_id and 'hosp' in dataset_id:
                category = 'MIMIC-IV Hospital'
                description = 'Hospital admissions, patients, diagnoses, procedures'
            elif 'mimiciv' in dataset_id and 'icu' in dataset_id:
                category = 'MIMIC-IV ICU'  
                description = 'ICU stays, vitals, medications, procedures'
            elif 'mimiciv' in dataset_id and 'derived' in dataset_id:
                category = 'MIMIC-IV Derived'
                description = 'Processed/derived data and concepts'
            elif 'mimiciii' in dataset_id and 'clinical' in dataset_id:
                category = 'MIMIC-III Clinical'
                description = 'MIMIC-III clinical data (legacy version)'
            elif 'mimiciii' in dataset_id and 'notes' in dataset_id:
                category = 'MIMIC-III Notes'
                description = 'Clinical notes and derived text data'
            elif 'mimiciii' in dataset_id and 'derived' in dataset_id:
                category = 'MIMIC-III Derived'
                description = 'Processed MIMIC-III concepts'
            elif 'eicu_crd' in dataset_id and 'derived' in dataset_id:
                category = 'eICU Derived'
                description = 'Processed eICU data and concepts'
            elif 'eicu_crd' in dataset_id:
                category = 'eICU Database'
                description = 'Multi-center ICU collaborative database'
            else:
                category = 'Other PhysioNet'
                description = 'Additional PhysioNet dataset'
            
            dataset_info.append({
                'id': dataset_id,
                'category': category, 
                'description': description
            })
        
        # Sort by category and then by dataset name
        dataset_info.sort(key=lambda x: (x['category'], x['id']))
        
        # Build formatted response
        result_lines = [f"✅ **Found {len(dataset_info)} accessible PhysioNet datasets:**\n"]
        
        current_category = None
        for ds in dataset_info:
            # Add category headers
            if ds['category'] != current_category:
                if current_category is not None:
                    result_lines.append("")  # Space between categories
                result_lines.append(f"**🏥 {ds['category']}:**")
                current_category = ds['category']
            
            result_lines.append(f"  📊 `{ds['id']}` - {ds['description']}")
        
        result_lines.extend([
            "",
            "**🎯 Next Steps:**",
            "• Use `get_database_schema('dataset_name')` to see tables in a specific dataset",
            "• Use `get_table_info('table_name')` to explore table structure",  
            "• Use `execute_query('SELECT ...')` to analyze the data",
            "",
            "**💡 Pro tip:** Dataset names are copy-paste ready for other tools!"
        ])
        
        return "\n".join(result_lines)
        
    except Exception as e:
        # Fallback error handling
        error_msg = str(e).lower()
        if "access denied" in error_msg or "permission" in error_msg:
            return f"""❌ **Access denied to physionet-data project**

**Error:** {e}

**Solution:** You need to star the physionet-data project:
1. Visit https://console.cloud.google.com/bigquery
2. Click "+ADD DATA" → "Star a project by name"  
3. Enter "physionet-data"
4. Restart your MCP client and try again"""
        else:
            return f"""❌ **Error discovering datasets:** {e}

**Troubleshooting:**
• Ensure you have PhysioNet access and have starred physionet-data
• Check your Google Cloud authentication: `gcloud auth list`
• Try restarting your MCP client"""


@mcp.tool()
def get_database_schema(dataset_name: str = None) -> str:
    """🔍 Discover PhysioNet dataset tables - specify which dataset or get guidance.

    **Important:** You need to specify which PhysioNet dataset to explore!

    **Common datasets (if you have access):**
    - `mimiciv_3_1_hosp` - MIMIC-IV hospital data  
    - `mimiciv_3_1_icu` - MIMIC-IV ICU data
    - `mimiciii_1_4` - MIMIC-III data
    - `eicu_crd` - eICU Collaborative Research Database

    **Examples:**
    - `get_database_schema('mimiciv_3_1_hosp')` - Show MIMIC-IV hospital tables
    - `get_database_schema('eicu_crd')` - Show eICU tables
    - `get_database_schema()` - Get help choosing a dataset

    **Don't have access yet?** Visit PhysioNet.org → "Request access using Google BigQuery" → Follow email instructions to star physionet-data project.

    Args:
        dataset_name: Specific PhysioNet dataset name (e.g., 'mimiciv_3_1_hosp')

    Returns:
        Table listings for the specified dataset, or guidance on dataset selection
    """
    if dataset_name is None:
        # No dataset specified - provide guidance and discovery
            return """🏥 **PhysioNet Dataset Selection Required**

I need to know which dataset to explore! Here are the steps:

**🔍 Step 1: Choose Your Dataset**
Common PhysioNet datasets (try these):
  • `mimiciv_3_1_hosp` - MIMIC-IV hospital data (patients, admissions, diagnoses)
  • `mimiciv_3_1_icu` - MIMIC-IV ICU data (icustays, vitals, procedures)  
  • `eicu_crd` - eICU database (multi-center ICU data)
  • `mimiciii_1_4` - MIMIC-III data (older version)

**📋 Step 2: Use This Tool With Specific Dataset**
Examples:
  • `get_database_schema('mimiciv_3_1_hosp')` 
  • `get_database_schema('eicu_crd')`

**🔧 No Access Yet?**
1. Visit https://physionet.org/
2. Find your desired dataset → "Request access using Google BigQuery"
3. Complete credentialing process
4. Follow the email instructions to star physionet-data project

**💡 Tip:** Try `list_accessible_datasets()` first to see what you can currently access."""

    # User specified a dataset - show its tables
    try:
        # Use direct API call instead of INFORMATION_SCHEMA (cross-project access issue)
        dataset_ref = _bq_client.dataset(dataset_name, project='physionet-data')
        tables = list(_bq_client.list_tables(dataset_ref))
        
        if not tables:
            return f"""❌ **Dataset '{dataset_name}' not accessible**

**Possible reasons:**
  • Dataset name incorrect (case-sensitive)
  • You don't have PhysioNet access to this dataset
  • Dataset doesn't exist in physionet-data project

**✅ Try these working examples:**
  • `get_database_schema('mimiciv_3_1_hosp')`
  • `get_database_schema('eicu_crd')`
  
**🔧 Need access?** Visit https://physionet.org/ → Request access using Google BigQuery"""
        
        # Categorize tables
        table_info = []
        for table in tables:
            table_name = table.table_id
            
            # Categorization logic
            if 'patient' in table_name.lower():
                category = 'Demographics'
            elif 'admission' in table_name.lower() or 'admit' in table_name.lower():
                category = 'Admissions'
            elif 'icu' in table_name.lower() or 'stay' in table_name.lower():
                category = 'ICU Data'
            elif 'lab' in table_name.lower() or 'event' in table_name.lower():
                category = 'Clinical Events'
            elif 'med' in table_name.lower() or 'drug' in table_name.lower():
                category = 'Medications'
            elif 'diag' in table_name.lower():
                category = 'Diagnoses'
            elif 'proc' in table_name.lower():
                category = 'Procedures'
            else:
                category = 'Other'
            
            full_table_name = f"`physionet-data.{dataset_name}.{table_name}`"
            table_info.append({
                'name': table_name,
                'full_name': full_table_name,
                'category': category
            })
        
        # Sort by category then name
        table_info.sort(key=lambda x: (x['category'], x['name']))
        
        # Format output
        result_lines = [f"📊 **Dataset: physionet-data.{dataset_name}**"]
        result_lines.append(f"**📋 Available Tables ({len(table_info)} total):**")
        
        current_category = None
        for table in table_info:
            if table['category'] != current_category:
                if current_category is not None:
                    result_lines.append("")
                result_lines.append(f"**{table['category']}:**")
                current_category = table['category']
            
            result_lines.append(f"  • `{table['name']}` → {table['full_name']}")
        
        result_lines.extend([
            "",
            "**🎯 Next Steps:**",
            "  • Use `get_table_info('table_name')` to explore specific tables",
            "  • Use `execute_query('SELECT ...')` to analyze the data",
            "  • Table names are copy-paste ready for queries!"
        ])
        
        return "\n".join(result_lines)
        
    except Exception as e:
        error_msg = str(e).lower()
        
        if "not found" in error_msg or "access denied" in error_msg:
            return f"""❌ **Cannot access physionet-data project:** {e}

📋 **How PhysioNet + BigQuery works:**
   • **{_project_id}** = Your Google Cloud project (handles billing only)
   • **physionet-data** = Separate project containing all PhysioNet datasets
   • **You need to "star" physionet-data to get read access**

🔧 **To fix this:**

1. **Navigate to:** https://console.cloud.google.com/bigquery  
2. **Click:** the "+ADD DATA" button  
3. **Select:** "Star a project by name"
4. **Enter:** "physionet-data"
5. **Verify:** You see physionet-data appear in left sidebar with your approved datasets

📧 **Prerequisites:** You must have PhysioNet credentials and access approval for specific datasets.

After starring the project, restart your MCP client and try again!"""
        
        return f"""❌ **Auto-detection failed:** {e}

💡 **Try exploring manually:** Use `get_table_info('physionet-data.dataset_name.table_name')` with the specific dataset and table names you know you have access to.

🔍 **Tip:** Check your BigQuery console to see which PhysioNet datasets appear under the starred physionet-data project."""


@mcp.tool()
def get_table_info(table_name: str, show_sample: bool = True) -> str:
    """📋 Deep dive into a medical table's structure and sample data.

    **When to use:** Before writing queries! This shows you exactly what's in each table.

    **Smart table discovery:**
    - Use simple names like 'patients' or 'admissions' - I'll find the right dataset
    - Or use full names like 'physionet-data.mimiciv_3_1_hosp.patients'
    - Works across MIMIC-III, MIMIC-IV, eICU, and all PhysioNet datasets

    **What you'll see:**
    - Every column name, data type, and constraints
    - Real sample data showing actual values and formats
    - Critical details like date formats, ID patterns, coding schemes

    **Examples:**
    - `get_table_info('patients')` - Find patient demographics across datasets
    - `get_table_info('icustays')` - Explore ICU admission patterns
    - `get_table_info('labevents')` - Understand lab result structure

    **Pro tip:** Always check sample data first! Medical data has many nuances.

    Args:
        table_name: Table name (simple like 'patients' or fully qualified)
        show_sample: Include sample rows (default: True, highly recommended)

    Returns:
        Complete medical table analysis with structure and real data examples
    """
    try:
        # Handle both simple names and fully qualified names
        if "." in table_name and len(table_name.split(".")) >= 2:
            # Qualified name - clean it up and use as-is
            clean_name = table_name.strip("`")
            full_table_name = f"`{clean_name}`"
            parts = clean_name.split(".")
            
            if len(parts) >= 3:
                # Full format: project.dataset.table
                project, dataset, table = parts[0], parts[1], parts[2]
            else:
                # Format: dataset.table (assume current project)
                dataset, table = parts[0], parts[1]
                project = _project_id
        else:
            # Simple name - search efficiently across user's accessible datasets
            table = table_name
            
            # Get user's accessible datasets first
            try:
                accessible_datasets = [ds.dataset_id for ds in _bq_client.list_datasets(project='physionet-data')]
            except Exception:
                # Fallback if API fails - use common patterns
                accessible_datasets = [
                    "mimiciv_3_1_hosp", "mimiciv_3_1_icu", "mimiciv_3_1_derived",
                    "mimiciii_clinical", "mimiciii_derived", "mimiciii_notes", 
                    "eicu_crd", "eicu_crd_derived"
                ]
            
            found_matches = []
            
            # Only search datasets the user actually has access to
            for dataset in accessible_datasets:
                try:
                    full_table_name = f"`physionet-data.{dataset}.{table}`"
                    
                    # Test if this table exists by trying to get column info
                    info_query = f"""
                    SELECT column_name, data_type, is_nullable
                    FROM `physionet-data.{dataset}.INFORMATION_SCHEMA.COLUMNS`
                    WHERE table_name = '{table}'
                    ORDER BY ordinal_position
                    """
                    
                    info_result = _execute_bigquery_query(info_query)
                    if ("No results found" not in info_result and 
                        "error" not in info_result.lower() and
                        len(info_result.strip()) > 0):
                        found_matches.append((dataset, full_table_name))
                        
                except Exception:
                    continue
            
            if found_matches:
                if len(found_matches) == 1:
                    # Single match found - use it
                    dataset, full_table_name = found_matches[0]
                    project = "physionet-data"
                else:
                    # Multiple matches - let user choose
                    match_list = [f"  • `{match[1]}` (dataset: {match[0]})" for match in found_matches]
                    matches_text = "\n".join(match_list)
                    return f"""🔍 **Multiple '{table}' tables found!**

**Available options:**
{matches_text}

💡 **Please specify which one:** Use the full table name like `get_table_info('physionet-data.{found_matches[0][0]}.{table}')`

🎯 **Pro tip:** Different datasets have different versions and scopes of data."""
            else:
                return f"""❌ Table '{table_name}' not found in your accessible PhysioNet datasets.

💡 **Troubleshooting:**
  • Use `list_accessible_datasets()` to see what datasets you have
  • Use `get_database_schema('dataset_name')` to see tables in a specific dataset  
  • Try fully qualified name: `physionet-data.dataset.{table_name}`
  • Common table names: patients, admissions, icustays, labevents

🔍 **Note:** Searched {len(accessible_datasets)} accessible datasets."""

        # Get column information using API (more reliable for cross-project)
        try:
            table_ref = _bq_client.get_table(f"{project}.{dataset}.{table}")
            
            # Format schema info
            result = f"📋 **Table:** {full_table_name}\n\n**Column Information:**\n"
            
            for field in table_ref.schema:
                nullable = "YES" if field.mode == "NULLABLE" else "NO"
                result += f"{field.name:<25} {field.field_type:<15} {nullable}\n"
        
        except Exception:
            # Fallback to INFORMATION_SCHEMA query
            info_query = f"""
            SELECT column_name, data_type, is_nullable
            FROM `{project}.{dataset}`.INFORMATION_SCHEMA.COLUMNS
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
            """
            
            info_result = _execute_bigquery_query(info_query)
            if "No results found" in info_result:
                return f"❌ Table '{table_name}' not found. Use `get_database_schema()` to see available tables."

            result = f"📋 **Table:** {full_table_name}\n\n**Column Information:**\n{info_result}"

        if show_sample:
            sample_query = f"SELECT * FROM {full_table_name} LIMIT 3"
            sample_result = _execute_bigquery_query(sample_query)
            result += f"\n\n📊 **Sample Data (first 3 rows):**\n{sample_result}"

        return result
        
    except Exception as e:
        return f"❌ Error examining table '{table_name}': {e}\n\n💡 Use `get_database_schema()` to see available tables."


@mcp.tool()
def execute_query(sql_query: str) -> str:
    """🚀 Execute powerful SQL analyses on real medical data.

    **What you can do:**
    - Patient outcome analysis across ICU stays
    - Medication effectiveness studies
    - Clinical trend analysis over time
    - Complex multi-table medical research queries

    **Example queries:**
    ```sql
    -- Count patients by gender in MIMIC-IV
    SELECT gender, COUNT(*) FROM `physionet-data.mimiciv_3_1_hosp.patients` GROUP BY gender
    
    -- ICU length of stay analysis
    SELECT AVG(los) as avg_los FROM `physionet-data.mimiciv_3_1_icu.icustays` WHERE los > 0
    
    -- Lab values over time
    SELECT * FROM `physionet-data.mimiciv_3_1_hosp.labevents` WHERE itemid = 50912 LIMIT 10
    ```

    **Smart workflow (saves time!):**
    1. `get_database_schema()` → See all your datasets
    2. `get_table_info('table_name')` → Understand structure + see sample data  
    3. `execute_query('your_sql')` → Run analysis with exact names

    **Why this matters for medical data:**
    - Patient IDs use specific naming (subject_id, hadm_id, stay_id)
    - Dates have specific formats and meanings
    - Lab values use item IDs, not names
    - Sample data shows real patterns you need to know

    Args:
        sql_query: Your SQL SELECT query (SELECT only for safety)

    Returns:
        Medical data analysis results with up to 50 rows shown
    """
    return _execute_query_internal(sql_query)


def main():
    """Main entry point for MCP server."""
    # Run the FastMCP server
    mcp.run()


if __name__ == "__main__":
    main()
