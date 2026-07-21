"""KG evaluation harness: computes recall + precision against golden.json (D0-6).

Per analysis/02 §七:
  - Recall = (true callers/deps/exports found by KG) / (total expected)
  - Precision = (KG results that match expected) / (total KG results)
  - Calibration: recall → Confidence (>0.9 HIGH, 0.7-0.9 MEDIUM, <0.7 LOW)

Usage:
    python -m sddp.kg.evaluate --gold tests/kg/golden.json --db /path/to/kg.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from .query_api import Confidence, KnowledgeGraphQueryAPI


def _resolve_symbol_id(api: KnowledgeGraphQueryAPI, name: str) -> str | None:
    r = api.lookup_symbol(name)
    matches = r.answer.get("matches", [])
    return matches[0]["symbol_id"] if matches else None


def _resolve_module_id(db_path: str | Path, module_name: str) -> str | None:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT id FROM nodes WHERE kind='Module' AND name=? ORDER BY scan_version DESC LIMIT 1",
            (module_name,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _resolve_file_path(db_path: str | Path, basename: str) -> str | None:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT file_path FROM nodes WHERE kind='File' AND file_path LIKE ? ORDER BY scan_version DESC LIMIT 1",
            (f"%/{basename}",),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _extract_names(result: Any, method: str) -> set[str]:
    """Extract the set of relevant names from a query result, depending on method."""
    answer = result.answer if hasattr(result, "answer") else result
    if method == "find_callers":
        return {c["caller_name"] for c in answer.get("callers", [])}
    if method == "find_file_impact":
        return {Path(f["file_path"]).name for f in answer.get("impacted_files", [])}
    if method == "get_module_api":
        return {e["name"] for e in answer.get("exports", [])}
    if method == "find_dependencies":
        return {d["dep_name"] for d in answer.get("dependencies", [])}
    return set()


def evaluate(api: KnowledgeGraphQueryAPI, db_path: str | Path, gold: dict) -> dict[str, Any]:
    """Run all golden queries; compute per-query + aggregate recall/precision."""
    per_query: list[dict[str, Any]] = []
    total_expected = 0
    total_found_expected = 0  # true positives
    total_kg_results = 0
    total_kg_correct = 0

    for q in gold.get("queries", []):
        method = q["method"]
        args = q.get("args", {})
        expected_spec = q.get("expected", {})
        expected_names = set(expected_spec.get("caller_names_contains") or
                             expected_spec.get("impacted_basenames_contains") or
                             expected_spec.get("export_names_contains") or
                             expected_spec.get("dep_names_contains") or
                             [])

        # Resolve args
        if "symbol_name" in args:
            sym_id = _resolve_symbol_id(api, args["symbol_name"])
            if sym_id is None:
                per_query.append({
                    "method": method, "args": args, "status": "symbol_not_found",
                    "expected_count": len(expected_names), "found_count": 0,
                    "recall": 0.0, "precision": 0.0,
                })
                total_expected += len(expected_names)
                continue
            if method == "find_callers":
                result = api.find_callers(sym_id, depth=args.get("depth", 1))
            elif method == "find_dependencies":
                result = api.find_dependencies(sym_id)
            else:
                per_query.append({"method": method, "args": args, "status": "unknown_method"})
                continue
        elif "file_basename" in args:
            fp = _resolve_file_path(db_path, args["file_basename"])
            if fp is None:
                per_query.append({
                    "method": method, "args": args, "status": "file_not_found",
                    "expected_count": len(expected_names), "found_count": 0,
                    "recall": 0.0, "precision": 0.0,
                })
                total_expected += len(expected_names)
                continue
            result = api.find_file_impact(fp)
        elif "module_name" in args:
            mod_id = _resolve_module_id(db_path, args["module_name"])
            if mod_id is None:
                per_query.append({
                    "method": method, "args": args, "status": "module_not_found",
                    "expected_count": len(expected_names), "found_count": 0,
                    "recall": 0.0, "precision": 0.0,
                })
                total_expected += len(expected_names)
                continue
            result = api.get_module_api(mod_id)
        else:
            per_query.append({"method": method, "args": args, "status": "no_resolvable_args"})
            continue

        found_names = _extract_names(result, method)
        true_positives = expected_names & found_names
        false_negatives = expected_names - found_names
        false_positives = found_names - expected_names

        recall = len(true_positives) / len(expected_names) if expected_names else 1.0
        precision = len(true_positives) / len(found_names) if found_names else (1.0 if not expected_names else 0.0)

        per_query.append({
            "method": method,
            "args": args,
            "expected_count": len(expected_names),
            "found_count": len(found_names),
            "true_positives": sorted(true_positives),
            "false_negatives": sorted(false_negatives),
            "false_positives": sorted(false_positives),
            "recall": round(recall, 4),
            "precision": round(precision, 4),
        })
        total_expected += len(expected_names)
        total_found_expected += len(true_positives)
        total_kg_results += len(found_names)
        total_kg_correct += len(true_positives)

    aggregate_recall = (total_found_expected / total_expected) if total_expected else 1.0
    aggregate_precision = (total_kg_correct / total_kg_results) if total_kg_results else 1.0

    def _to_confidence(r: float) -> str:
        if r >= 0.9:
            return Confidence.HIGH.value
        if r >= 0.7:
            return Confidence.MEDIUM.value
        return Confidence.LOW.value

    return {
        "per_query": per_query,
        "aggregate": {
            "total_queries": len(per_query),
            "recall": round(aggregate_recall, 4),
            "precision": round(aggregate_precision, 4),
            "total_expected": total_expected,
            "total_true_positives": total_found_expected,
            "total_kg_results": total_kg_results,
        },
        "confidence_calibration": {
            "recall_to_confidence": {
                ">=0.90": Confidence.HIGH.value,
                "0.70-0.90": Confidence.MEDIUM.value,
                "<0.70": Confidence.LOW.value,
            },
            "calibrated_confidence": _to_confidence(aggregate_recall),
        },
        "dod_d0_6_pass": aggregate_recall >= 0.70,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sddp.kg.evaluate")
    parser.add_argument("--gold", required=True, help="Path to golden.json")
    parser.add_argument("--db", required=True, help="Path to KG SQLite database")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)

    with open(args.gold) as f:
        gold = json.load(f)

    api = KnowledgeGraphQueryAPI(args.db)
    try:
        report = evaluate(api, args.db, gold)
    finally:
        api.close()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        agg = report["aggregate"]
        print(f"[eval] recall={agg['recall']:.4f} precision={agg['precision']:.4f}")
        print(f"       true positives: {agg['total_true_positives']}/{agg['total_expected']}")
        print(f"       calibrated confidence: {report['confidence_calibration']['calibrated_confidence']}")
        print(f"       D0-6 pass (recall ≥ 0.70): {report['dod_d0_6_pass']}")

    return 0 if report["dod_d0_6_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
