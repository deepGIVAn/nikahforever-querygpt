async def format_response(query_result: dict, llm_data: dict) -> dict:
    """
    Formats the SQLite execution results along with LLM metadata to instruct
    the frontend how to render (e.g. as a single number metric, a table, or a chart).
    """
    rows = query_result.get("rows", [])
    columns = query_result.get("columns", [])
    
    result_type = llm_data.get("result_type", "table")
    chart_config = llm_data.get("chart_config") or {}
    
    formatted_data = {
        "type": result_type,
        "columns": columns,
        "rows": rows,
        "value": None,
        "label": None,
        "chart_config": None
    }
    
    # Handle single number metric format
    if result_type == "number":
        if rows and columns:
            # Pick first column of the first row
            metric_col = columns[0]
            metric_val = rows[0].get(metric_col)
            formatted_data["value"] = metric_val
            formatted_data["label"] = metric_col
        else:
            formatted_data["value"] = 0
            formatted_data["label"] = "count"
            
    # Handle chart format
    elif result_type == "chart":
        x_col = chart_config.get("x")
        y_col = chart_config.get("y")
        
        # If columns specified in LLM metadata are missing, fallback to first two columns
        if (not x_col or x_col not in columns) and len(columns) > 0:
            x_col = columns[0]
        if (not y_col or y_col not in columns) and len(columns) > 1:
            y_col = columns[1]
        elif (not y_col or y_col not in columns) and len(columns) == 1:
            y_col = columns[0]  # default to single column plot if only 1 exists
            
        formatted_data["chart_config"] = {
            "type": chart_config.get("type", "bar"),
            "x": x_col,
            "y": y_col
        }
        
    return formatted_data
