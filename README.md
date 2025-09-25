# physionet-mcp

Lean MCP server for PhysioNet datasets - works with any PhysioNet dataset you have access to.

📺 **This is a lean version of m3 with similar BigQuery and PhysioNet setup. Check out detailed videos here:** [https://rafiattrach.github.io/m3/](https://rafiattrach.github.io/m3/)

## Quick Setup

### Production (After PyPI release)
```json
{
  "mcpServers": {
    "physionet-mcp": {
      "command": "uvx",
      "args": ["physionet-mcp"],
      "env": {
        "BIGQUERY_PROJECT_ID": "your-project-id"
      }
    }
  }
}
```

### Local Development
```json
{
  "mcpServers": {
    "physionet-mcp": {
      "command": "/path/to/physionet-mcp/venv/bin/python",
      "args": ["-m", "physionet_mcp.mcp_server"],
      "cwd": "/path/to/physionet-mcp",
      "env": {
        "BIGQUERY_PROJECT_ID": "your-project-id"
      }
    }
  }
}
```

Replace `your-project-id` with your Google Cloud project ID.

## 4 Simple Tools

1. **list_accessible_datasets** → See what you can access
2. **get_database_schema** → Find tables in a dataset  
3. **get_table_info** → Check structure & sample data
4. **execute_query** → Run your analysis

## Usage Examples

- "What PhysioNet datasets can I access?"
- "Show me MIMIC-IV hospital tables"
- "What's in the patients table?"
- "How many patients are in MIMIC-IV?"

## Future Enhancements

Potential improvements for enterprise use:

- **Dataset filtering** - Restrict access to specific datasets for security
- **Query optimization** - Add result caching and query cost tracking  
- **Rate limiting** - Implement query throttling for shared environments
- **Enhanced metadata** - Add column descriptions and data quality metrics

## License

MIT