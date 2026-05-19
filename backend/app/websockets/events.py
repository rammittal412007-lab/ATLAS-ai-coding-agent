"""
WebSocket Event Schemas
Typed event payloads for all real-time streaming events.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ─── Base event ───────────────────────────────────────────────────────────────

class BaseEvent(BaseModel):
    task_id:    Optional[str] = None
    timestamp:  str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    agent_type: Optional[str] = None


# ─── Agent events ─────────────────────────────────────────────────────────────

class AgentThoughtData(BaseModel):
    message: str


class AgentThoughtEvent(BaseEvent):
    type: Literal["agent_thought"] = "agent_thought"
    data: AgentThoughtData


class AgentActionData(BaseModel):
    action:      str
    description: Optional[str] = None
    params:      Optional[Dict[str, Any]] = None


class AgentActionEvent(BaseEvent):
    type: Literal["agent_action"] = "agent_action"
    data: AgentActionData


class AgentResultData(BaseModel):
    summary:      Optional[str]       = None
    tokens:       Optional[int]       = None
    plan:         Optional[Dict]      = None
    steps_count:  Optional[int]       = None
    complexity:   Optional[str]       = None
    relevant_files: Optional[List[str]] = None
    chunks_found: Optional[int]       = None
    changes_applied: Optional[int]   = None
    files:        Optional[List[str]] = None
    review:       Optional[Dict]      = None
    score:        Optional[int]       = None
    approved:     Optional[bool]      = None
    issues:       Optional[int]       = None
    root_cause:   Optional[str]       = None
    fix_strategy: Optional[str]       = None
    error_type:   Optional[str]       = None
    should_retry: Optional[bool]      = None
    retry_number: Optional[int]       = None


class AgentResultEvent(BaseEvent):
    type: Literal["agent_result"] = "agent_result"
    data: AgentResultData


# ─── File change event ────────────────────────────────────────────────────────

class FileChangedData(BaseModel):
    file_path:     str
    action:        str  # modify | create | delete
    explanation:   Optional[str] = None
    diff:          Optional[str] = None
    lines_added:   int = 0
    lines_removed: int = 0


class FileChangedEvent(BaseEvent):
    type: Literal["file_changed"] = "file_changed"
    data: FileChangedData


# ─── Execution log event ──────────────────────────────────────────────────────

class ExecutionLogData(BaseModel):
    command:   Optional[str] = None
    log:       Optional[str] = None
    message:   Optional[str] = None
    stdout:    Optional[str] = None
    stderr:    Optional[str] = None
    exit_code: Optional[int] = None
    status:    Optional[str] = None  # starting | success | failed | timeout


class ExecutionLogEvent(BaseEvent):
    type: Literal["execution_log"] = "execution_log"
    data: ExecutionLogData


# ─── Task status event ────────────────────────────────────────────────────────

class TaskStatusData(BaseModel):
    status:  str
    details: Optional[Any] = None


class TaskStatusEvent(BaseEvent):
    type: Literal["task_status"] = "task_status"
    data: TaskStatusData


# ─── Repository indexing events ───────────────────────────────────────────────

class RepoIndexProgressData(BaseModel):
    processed:    int
    total:        int
    current_file: Optional[str] = None
    chunks:       int = 0
    pct:          float = 0.0


class RepoIndexProgressEvent(BaseModel):
    type:          Literal["repo_index_progress"] = "repo_index_progress"
    repository_id: str
    data:          RepoIndexProgressData
    timestamp:     str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class RepoStatusData(BaseModel):
    status:       str  # cloning | indexing | ready | error
    total_files:  Optional[int]   = None
    total_chunks: Optional[int]   = None
    error:        Optional[str]   = None


class RepoStatusEvent(BaseModel):
    type:          Literal["repo_status"] = "repo_status"
    repository_id: str
    data:          RepoStatusData
    timestamp:     str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ─── System events ────────────────────────────────────────────────────────────

class PingEvent(BaseModel):
    type:      Literal["ping"] = "ping"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class PongEvent(BaseModel):
    type:      Literal["pong"] = "pong"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ConnectedEvent(BaseModel):
    type:      Literal["connected"] = "connected"
    task_id:   Optional[str] = None
    repo_id:   Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ErrorEvent(BaseModel):
    type:      Literal["error"] = "error"
    message:   str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ─── Union type ──────────────────────────────────────────────────────────────

AnyEvent = Union[
    AgentThoughtEvent,
    AgentActionEvent,
    AgentResultEvent,
    FileChangedEvent,
    ExecutionLogEvent,
    TaskStatusEvent,
    RepoIndexProgressEvent,
    RepoStatusEvent,
    PingEvent,
    PongEvent,
    ConnectedEvent,
    ErrorEvent,
]


# ─── Factory helpers ─────────────────────────────────────────────────────────

def make_agent_thought(
    task_id: str,
    agent_type: str,
    message: str,
) -> Dict[str, Any]:
    return AgentThoughtEvent(
        task_id=task_id,
        agent_type=agent_type,
        data=AgentThoughtData(message=message),
    ).model_dump()


def make_execution_log(
    task_id: str,
    message: str = "",
    command: Optional[str] = None,
    exit_code: Optional[int] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    return ExecutionLogEvent(
        task_id=task_id,
        data=ExecutionLogData(
            message=message,
            command=command,
            exit_code=exit_code,
            status=status,
        ),
    ).model_dump()


def make_task_status(
    task_id: str,
    status: str,
    details: Any = None,
) -> Dict[str, Any]:
    return TaskStatusEvent(
        task_id=task_id,
        data=TaskStatusData(status=status, details=details),
    ).model_dump()


def make_file_changed(
    task_id: str,
    agent_type: str,
    file_path: str,
    action: str,
    diff: str = "",
    lines_added: int = 0,
    lines_removed: int = 0,
) -> Dict[str, Any]:
    return FileChangedEvent(
        task_id=task_id,
        agent_type=agent_type,
        data=FileChangedData(
            file_path=file_path,
            action=action,
            diff=diff,
            lines_added=lines_added,
            lines_removed=lines_removed,
        ),
    ).model_dump()
