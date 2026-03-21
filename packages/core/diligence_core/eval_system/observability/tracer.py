import enum
from typing import List, Union
from langfuse import get_client


class ObservationType(enum.Enum):
    span = 'span'
    generation = 'generation'
    agent = 'agent'
    tool = 'tool'
    chain = 'chain'
    retriever = 'retriever'
    evaluator = 'evaluator'
    embedding = 'embedding'
    guardrail = 'guardrail'


class Tracer:
    def __init__(self):
        self._lf = get_client()
        self._tags: List[str] = []
        self._metadata: dict = {}

    def start_observation(self, name: str, observation_type: Union[ObservationType, str] = 'span', **kwargs):
        if isinstance(observation_type, str):
            observation_type = ObservationType(observation_type)
        return self._lf.start_as_current_observation(as_type=observation_type.value, name=name, **kwargs)

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
                    value=float(value)
                )

    def flush(self):
        self._lf.flush()