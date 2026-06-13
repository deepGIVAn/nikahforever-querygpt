from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class QueryRequest(BaseModel):
    question: str
    chat_history: Optional[List[Dict[str, str]]] = None

class QueryResponse(BaseModel):
    success: bool
    question: Optional[str] = None
    sql: Optional[str] = None
    explanation: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    needs_clarification: Optional[bool] = False
    clarification: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
