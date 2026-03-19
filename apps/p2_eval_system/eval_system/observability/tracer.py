from langfuse import get_client

class AnalysisTracer:
    def __init__(self):
        self._lf = get_client()

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

    def update_trace(self, user_query: str, company_name: str, chunks_count: int):
        self._lf.update_current_trace(
            input=user_query,
            metadata={
                "company": company_name,
                "chunks_retrieved": chunks_count,
            }
        )

    def flush(self):
        self._lf.flush()