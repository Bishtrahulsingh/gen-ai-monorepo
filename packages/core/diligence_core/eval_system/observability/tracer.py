import enum
from typing import Any, List, Union
from langfuse import get_client
from pydantic import BaseModel


class ObservationType(enum.Enum):
    span = "span"
    generation = "generation"
    agent = "agent"
    tool = "tool"
    chain = "chain"
    retriever = "retriever"
    evaluator = "evaluator"
    embedding = "embedding"
    guardrail = "guardrail"

class TraceParams(BaseModel):
    name: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    version: str | None = None
    input: Any | None = None
    output: Any | None = None
    metadata: Any | None = None
    tags: list[str] | None = None

class Tracer:
    def __init__(self):
        self._lf = get_client()
        self._tags: List[str] = []
        self._metadata: dict = {}

    def start_observation(
        self,
        name: str,
        observation_type: Union[ObservationType, str] = ObservationType.span,
        **kwargs,
    ):
        if isinstance(observation_type, str):
            observation_type = ObservationType(observation_type)
        return self._lf.start_as_current_observation(
            as_type=observation_type.value, name=name, **kwargs
        )

    def add_tags(self, tags: List[str], **metadata):
        self._tags = list(set(self._tags + tags))
        self._metadata.update(metadata)
        self._lf.update_current_trace(
            tags=self._tags,
            metadata=self._metadata,
        )

    def score_evaluation(self, scores: dict):
        trace_id = self._lf.get_current_trace_id()
        if not trace_id:
            return
        for name, value in scores.items():
            if isinstance(value, (int, float)):
                self._lf.create_score(
                    trace_id=trace_id,
                    name=name,
                    value=float(value),
                )

    def update_trace(self, params: TraceParams | None = None, **kwargs):
        if params:
            kwargs = {**params.model_dump(exclude_none=True), **kwargs}
        self._lf.update_current_trace(**kwargs)

    def flush(self):
        self._lf.flush()