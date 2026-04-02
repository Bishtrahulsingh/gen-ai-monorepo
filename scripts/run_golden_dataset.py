from dotenv import load_dotenv

from diligence_analyst.evaluation.goldendataset import dataset

load_dotenv()
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from diligence_analyst.prompts.p1_memo.load_prompt import (
    replace_input_values, load_prompt, chunk_to_str
)
from diligence_core.llm import LLMWrapper
from diligence_core.reranker.commonreranker import async_reranker
from diligence_core.supabaseconfig.supabaseconfig import init_supabase


token = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjI2OGU0NDViLTM4ODAtNDJlOC1hMTY3LTdlYTA0NmY4MDEzZCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3hjZGR6ZHJscGJnZnJkc2p5cGV0LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI1MDYzNDQ2Ni1lOTQwLTRhOWYtODY2NS01ZGJlZTI1ODc1MGQiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzc1MTA2OTI5LCJpYXQiOjE3NzUxMDMzMjksImVtYWlsIjoiYmlzaHRyYWh1bHNpbmdoLmRldkBnbWFpbC5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsIjoiYmlzaHRyYWh1bHNpbmdoLmRldkBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwicGhvbmVfdmVyaWZpZWQiOmZhbHNlLCJzdWIiOiI1MDYzNDQ2Ni1lOTQwLTRhOWYtODY2NS01ZGJlZTI1ODc1MGQifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc3NTEwMzMyOX1dLCJzZXNzaW9uX2lkIjoiNGUzNDk3NzYtNGYzMC00M2YwLTkwZjUtZTg2YjliOWIxN2EyIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.89lGY1AlZf7D6nsEuJO3DhAYFjVqqQXvGddtDkDNEE3n_WhWO_mgWkxAHtwdqkkKeVJMHujWysLJvrX-7bsfYA"

COLLECTION_NAME     = os.environ.get("COLLECTION_NAME","sec_filings")
AUTH_TOKEN          = token          # Supabase JWT / service key
TICKER              = os.environ.get("TICKER", "AAPL")
FISCAL_YEAR         = int(os.environ.get("FISCAL_YEAR", "2025"))
COMPANY_NAME        = "Apple"

RETRIEVAL_THRESHOLD = 0.30
FAITHFULNESS_MIN    = 0.60
RELEVANCE_MIN       = 0.60
# ─────────────────────────────────────────────────────────────────────────────


async def run_single(llm: LLMWrapper, item: dict, sem: asyncio.Semaphore) -> dict:
    async with sem:
        question    = item["question"]
        expected    = item["answer"]
        category    = item["category"]
        section     = item.get("section", "")
        question_id = item["id"]

        result = {
            "id":                  question_id,
            "category":            category,
            "section":             section,
            "question":            question,
            "expected_answer":     expected,
            "generated_answer":    None,
            "polished_answer":     None,
            "retrieval_score":     None,
            "chunks_retrieved":    None,
            "hallucinated_claims": [],
            "faithfulness":        None,
            "answer_relevance":    None,
            "context_precision":   None,
            "verdict":             None,
            "issues":              [],
            "retrieval_failed":    False,
            "status":              "success",
            "error":               None,
        }

        try:
            # ── Retrieval ────────────────────────────────────────────────────
            # New signature: token + ticker + fiscal_year (no company_id)
            context = await llm.hyde_based_context_retrival(
                query=question,
                collection_name=COLLECTION_NAME,
                token=AUTH_TOKEN,
                ticker=TICKER,
                fiscal_year=FISCAL_YEAR,
            )

            top_score = context.points[0].score if (context and context.points) else 0.0
            result["retrieval_score"] = round(top_score, 4)

            if top_score < RETRIEVAL_THRESHOLD:
                result["retrieval_failed"] = True
                result["verdict"]          = "fail"
                result["status"]           = "retrieval_below_threshold"
                return result

            top_k_chunks = await async_reranker(context, question, top_k=5)
            result["chunks_retrieved"] = len(top_k_chunks)
            context_str = chunk_to_str(top_k_chunks)

            # ── Generation ───────────────────────────────────────────────────
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
            raw_response_str = (
                json.dumps(raw_response)
                if isinstance(raw_response, dict)
                else str(raw_response)
            )
            result["generated_answer"] = raw_response_str

            # ── Judge 1: hallucination detection + polish ────────────────────
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

            # ── Judge 2: score the polished answer ───────────────────────────
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
    # ── Init Supabase (required before first LLM call) ───────────────────────
    await init_supabase()

    llm = LLMWrapper()
    sem = asyncio.Semaphore(1)
    qa_pairs = dataset["qa_pairs"]

    print(f"\n{'='*65}")
    print(f"  Dataset  : {dataset['dataset_name']}")
    print(f"  Document : {dataset['document']}")
    print(f"  Company  : {COMPANY_NAME}  |  Ticker: {TICKER}  |  FY: {FISCAL_YEAR}")
    print(f"  Total Qs : {len(qa_pairs)}")
    print(f"{'='*65}\n")

    results = []
    for item in qa_pairs:
        section_label = f"[{item.get('section', item['category'])}]"
        print(f"\nQ{item['id']} {section_label}: {item['question'][:60]}...")
        result = await run_single(llm, item, sem)
        results.append(result)
        print(f"  verdict  : {result['verdict']}")
        print(f"  faith    : {result['faithfulness']}")
        print(f"  relevance: {result['answer_relevance']}")
        print(f"  retrieval: {result['retrieval_score']}")
        print(f"  status   : {result['status']}")
        if result["error"]:
            print(f"  error    : {result['error'][:120]}")
        if result["hallucinated_claims"]:
            print(f"  halluc   : {result['hallucinated_claims']}")
        await asyncio.sleep(5)  # pause between questions to avoid Groq rate limits

    # ── Summary ──────────────────────────────────────────────────────────────
    passed           = [r for r in results if r["verdict"] == "pass"]
    failed           = [r for r in results if r["verdict"] == "fail"]
    retrieval_failed = [r for r in results if r["retrieval_failed"]]
    errors           = [r for r in results if r["status"] not in ("success", "judge_parse_error")]

    avg_faith = _avg(results, "faithfulness")
    avg_relev = _avg(results, "answer_relevance")
    avg_prec  = _avg(results, "context_precision")

    # per-section breakdown
    sections = {}
    for r in results:
        sec = r.get("section") or r["category"]
        sections.setdefault(sec, {"pass": 0, "fail": 0})
        sections[sec][r["verdict"]] += 1

    print(f"\n{'='*65}")
    print(f"  AAPL FY{FISCAL_YEAR} — Eval Summary")
    print(f"{'='*65}")
    print(f"  Total      : {len(results)}")
    print(f"  Passed     : {len(passed)}")
    print(f"  Failed     : {len(failed)}")
    print(f"  Retrieval↓ : {len(retrieval_failed)}")
    print(f"  Errors     : {len(errors)}")
    print(f"\n  Avg faithfulness      : {avg_faith:.2f}")
    print(f"  Avg answer_relevance  : {avg_relev:.2f}")
    print(f"  Avg context_precision : {avg_prec:.2f}  (diagnostic only)")

    print(f"\n  Per-section results:")
    for sec, counts in sections.items():
        total_sec = counts["pass"] + counts["fail"]
        print(f"    {sec:<42} pass={counts['pass']}/{total_sec}")

    if retrieval_failed:
        print("\n  Retrieval failures:")
        for r in retrieval_failed:
            print(f"    [{r['retrieval_score']:.2f}] #{r['id']} {r['question'][:65]}")

    gen_failed = [r for r in failed if not r["retrieval_failed"]]
    if gen_failed:
        print("\n  Generation/judge failures:")
        for r in gen_failed:
            print(f"    #{r['id']} faith={r['faithfulness']}  relev={r['answer_relevance']}")
            for issue in r["issues"]:
                print(f"         - {issue}")
            if r["hallucinated_claims"]:
                print(f"         hallucinated: {r['hallucinated_claims']}")

    # ── Write results JSON ────────────────────────────────────────────────────
    out_dir  = Path("eval_results")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"aapl_{FISCAL_YEAR}_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"
    output = {
        "run_date":    datetime.now().isoformat(),
        "dataset":     dataset["dataset_name"],
        "document":    dataset["document"],
        "company":     COMPANY_NAME,
        "ticker":      TICKER,
        "fiscal_year": FISCAL_YEAR,
        "collection":  COLLECTION_NAME,
        "thresholds": {
            "retrieval":   RETRIEVAL_THRESHOLD,
            "faithfulness": FAITHFULNESS_MIN,
            "relevance":    RELEVANCE_MIN,
        },
        "summary": {
            "total":                  len(results),
            "passed":                 len(passed),
            "failed":                 len(failed),
            "retrieval_failures":     len(retrieval_failed),
            "errors":                 len(errors),
            "avg_faithfulness":       avg_faith,
            "avg_answer_relevance":   avg_relev,
            "avg_context_precision":  avg_prec,
            "per_section":            sections,
        },
        "results": results,
    }
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\n  Full results → {out_path}\n")


def _avg(results: list, key: str) -> float:
    vals = [r[key] for r in results if r[key] is not None]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


if __name__ == "__main__":
    asyncio.run(main())