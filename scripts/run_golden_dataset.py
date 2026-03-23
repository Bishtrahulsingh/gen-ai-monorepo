from dotenv import load_dotenv
load_dotenv()
import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from diligence_analyst.evaluation.goldendataset import dataset
from diligence_analyst.prompts.p1_memo.load_prompt import (
    replace_input_values, load_prompt, chunk_to_str
)
from diligence_core.llm import LLMWrapper
from diligence_core.reranker.commonreranker import async_reranker

COMPANY_ID          = uuid.UUID(os.environ["COMPANY_ID"])
COLLECTION_NAME     = os.environ["COLLECTION_NAME"]
COMPANY_NAME        = "Accenture"
RETRIEVAL_THRESHOLD = 0.70
FAITHFULNESS_MIN    = 0.70
RELEVANCE_MIN       = 0.70


async def run_single(llm: LLMWrapper, item: dict, sem: asyncio.Semaphore) -> dict:
    async with sem:
        question    = item["question"]
        expected    = item["answer"]
        category    = item["category"]
        question_id = item["id"]

        result = {
            "id":                question_id,
            "category":          category,
            "question":          question,
            "expected_answer":   expected,
            "generated_answer":  None,
            "polished_answer":   None,
            "retrieval_score":   None,
            "chunks_retrieved":  None,
            "hallucinated_claims": [],
            "faithfulness":      None,
            "answer_relevance":  None,
            "context_precision": None,
            "verdict":           None,
            "issues":            [],
            "retrieval_failed":  False,
            "status":            "success",
            "error":             None,
        }

        try:
            # --- Retrieval ---
            context = await llm.hyde_based_context_retrival(
                query=question,
                company_id=COMPANY_ID,
                collection_name=COLLECTION_NAME,
            )
            top_score = context.points[0].score if (context and context.points) else 0.0
            result["retrieval_score"] = round(top_score, 4)

            top_k_chunks = await async_reranker(context, question, top_k=5)
            result["chunks_retrieved"] = len(top_k_chunks)
            context_str = chunk_to_str(top_k_chunks)

            # --- Generation ---
            # non_streamed_response calls make_llm_call internally,
            # so raw_response is already a parsed dict (not a string)
            user_prompt = replace_input_values(
                load_prompt("input_template.md"),
                COMPANY_NAME,
                context_str,
                question,
            )
            generator_messages = [
                {"role": "system", "content": load_prompt("system_template_model1.md")},
                {"role": "user",   "content": user_prompt},
            ]
            judge_model, raw_response = await llm.non_streamed_response(
                messages=generator_messages
            )
            # raw_response is a dict — serialise for storage and judge inputs
            raw_response_str = json.dumps(raw_response) if isinstance(raw_response, dict) else str(raw_response)
            result["generated_answer"] = raw_response_str

            # --- Judge 1: hallucination detection + polish ---
            # make_llm_call now returns a parsed dict directly
            judge1_scores = await llm.make_llm_call(
                messages=[
                    {"role": "system", "content": load_prompt("system_template_judge1.md")},
                    {"role": "user",   "content": (
                        f"Question: {question}\n\n"
                        f"Retrieved context:\n{context_str}\n\n"
                        f"Generated answer:\n{raw_response_str}"
                    )},
                ],
                model=judge_model,
                stream=False,
            )

            polished_answer = judge1_scores.get("polished_answer", raw_response)
            result["polished_answer"] = (
                json.dumps(polished_answer)
                if isinstance(polished_answer, dict)
                else str(polished_answer)
            )
            result["hallucinated_claims"] = judge1_scores.get("hallucinated_claims", [])

            await asyncio.sleep(3)  # breathing room between judge1 and judge2

            # --- Judge 2: score the polished answer ---
            # make_llm_call now returns a parsed dict directly
            scores = await llm.make_llm_call(
                messages=[
                    {"role": "system", "content": load_prompt("system_template_judge2.md")},
                    {"role": "user",   "content": (
                        f"Question: {question}\n\n"
                        f"Retrieved context:\n{context_str}\n\n"
                        f"Generated answer:\n{result['polished_answer']}"
                    )},
                ],
                model=judge_model,
                stream=False,
            )

            result["faithfulness"]      = scores.get("faithfulness")
            result["answer_relevance"]  = scores.get("answer_relevance")
            result["context_precision"] = scores.get("context_precision")
            result["issues"]            = scores.get("issues", [])

            faith  = result["faithfulness"]    or 0
            relev  = result["answer_relevance"] or 0
            passed = faith >= FAITHFULNESS_MIN and relev >= RELEVANCE_MIN
            result["verdict"] = "pass" if passed else "fail"

        except json.JSONDecodeError as e:
            result["status"]  = "judge_parse_error"
            result["error"]   = f"Could not parse judge JSON: {e}"
            result["verdict"] = "fail"

        except Exception as e:
            result["status"]  = "error"
            result["error"]   = str(e)
            result["verdict"] = "fail"

        return result


async def main():
    llm = LLMWrapper()
    sem = asyncio.Semaphore(1)
    qa_pairs = dataset["qa_pairs"]

    results = []
    for item in qa_pairs:
        print(f"\nQ{item['id']}: {item['question'][:65]}...")
        result = await run_single(llm, item, sem)
        results.append(result)
        print(f"  verdict  : {result['verdict']}")
        print(f"  faith    : {result['faithfulness']}")
        print(f"  relevance: {result['answer_relevance']}")
        print(f"  status   : {result['status']}")
        if result['error']:
            print(f"  error    : {result['error'][:120]}")
        if result['hallucinated_claims']:
            print(f"  halluc   : {result['hallucinated_claims']}")
        await asyncio.sleep(5)  # pause between questions to avoid rate limits

    passed           = [r for r in results if r["verdict"] == "pass"]
    failed           = [r for r in results if r["verdict"] == "fail"]
    retrieval_failed = [r for r in results if r["retrieval_failed"]]
    errors           = [r for r in results if r["status"] not in ("success", "judge_parse_error")]

    avg_faith = _avg(results, "faithfulness")
    avg_relev = _avg(results, "answer_relevance")
    avg_prec  = _avg(results, "context_precision")

    print(f"\n{'='*50}")
    print(f"  Total      : {len(results)}")
    print(f"  Passed     : {len(passed)}")
    print(f"  Failed     : {len(failed)}")
    print(f"  Retrieval  : {len(retrieval_failed)}")
    print(f"  Errors     : {len(errors)}")
    print(f"\n  Avg faithfulness      : {avg_faith:.2f}")
    print(f"  Avg answer_relevance  : {avg_relev:.2f}")
    print(f"  Avg context_precision : {avg_prec:.2f}  (diagnostic only)\n")

    if retrieval_failed:
        print("\nRetrieval failures:")
        for r in retrieval_failed:
            print(f"  [{r['retrieval_score']:.2f}] #{r['id']} {r['question'][:70]}")

    gen_failed = [r for r in failed if not r["retrieval_failed"]]
    if gen_failed:
        print("\nGeneration/judge failures:")
        for r in gen_failed:
            print(f"  #{r['id']} faith={r['faithfulness']}  relev={r['answer_relevance']}")
            for issue in r["issues"]:
                print(f"       - {issue}")
            if r["hallucinated_claims"]:
                print(f"       hallucinated: {r['hallucinated_claims']}")

    out_dir  = Path("eval_results")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"
    output = {
        "run_date": datetime.now().isoformat(),
        "summary": {
            "total":                 len(results),
            "passed":                len(passed),
            "failed":                len(failed),
            "retrieval_failures":    len(retrieval_failed),
            "errors":                len(errors),
            "avg_faithfulness":      avg_faith,
            "avg_answer_relevance":  avg_relev,
            "avg_context_precision": avg_prec,
        },
        "results": results,
    }
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nFull results -> {out_path}\n")


def _avg(results: list, key: str) -> float:
    vals = [r[key] for r in results if r[key] is not None]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


if __name__ == "__main__":
    asyncio.run(main())