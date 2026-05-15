#!/usr/bin/env python3
"""
Excel Agent - GitHub Actions CI Runner

This script is the entrypoint for the GitHub Actions workflow.
It differs from orchestrator_cli.py in three key ways:

1. FIXED OUTPUT PATH  — always writes to the same Excel file (no timestamps)
2. EMPTY START        — creates an empty Excel on first run if none exists
3. IN-PLACE UPDATES   — on retrigger, loads the existing Excel and applies the new prompt on top

Usage:
    python run_agent_ci.py --prompt "Add employees Bob and Sara with Engineering department"
    python run_agent_ci.py --prompt "Add a Priority column" --model "gpt-oss:120b-cloud"
    python run_agent_ci.py --prompt "..." --output data/excel_output.xlsx
"""

import argparse
import os
import sys
import pandas as pd

from logic.orchestrator import ExcelAgentOrchestrator

DEFAULT_OUTPUT = "data/excel_output.xlsx"


def create_empty_excel(path: str) -> None:
    """Create a truly empty Excel file with no rows and no columns."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    pd.DataFrame().to_excel(path, index=False)
    print(f"[CI] Created empty Excel at: {path}")


def build_empty_df_hint(prompt: str) -> str:
    """
    When the DataFrame is empty, prefix the prompt with guidance so the LLM
    knows it should CREATE the structure from scratch, not just mutate existing data.
    """
    return (
        "NOTE: The Excel file is currently EMPTY (no columns, no rows). "
        "Your task is to create appropriate columns AND insert data rows based on the request below. "
        "The final 'df' must have at least one column and at least one row.\n\n"
        f"Request: {prompt}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Excel Agent CI Runner for GitHub Actions"
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Natural language instruction describing what to add/modify in the Excel file"
    )
    parser.add_argument(
        "--model",
        default="gpt-oss:120b-cloud",
        help="Ollama model to use (default: gpt-oss:120b-cloud)"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Fixed output Excel path (default: {DEFAULT_OUTPUT}). "
             "This same file is loaded and updated on every retrigger."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show generated code without executing or saving"
    )
    args = parser.parse_args()

    output_path = args.output
    is_first_run = not os.path.exists(output_path)

    # ── Step 1: Ensure Excel exists ──────────────────────────────────────────
    if is_first_run:
        print("[CI] No existing Excel found — starting fresh.")
        create_empty_excel(output_path)
    else:
        print(f"[CI] Existing Excel found at: {output_path} — will update in-place.")

    print(f"[CI] Prompt : {args.prompt}")
    print(f"[CI] Model  : {args.model}")
    print(f"[CI] Output : {output_path}")
    print()

    # ── Step 2: Load Excel ───────────────────────────────────────────────────
    orchestrator = ExcelAgentOrchestrator(model=args.model, verbose=True)
    orchestrator.load_excel(output_path)

    df = orchestrator.current_df
    df_is_empty = df.empty or (len(df.columns) == 0)

    # ── Step 3: Enrich prompt if DataFrame is empty ──────────────────────────
    effective_prompt = (
        build_empty_df_hint(args.prompt) if df_is_empty else args.prompt
    )

    # ── Step 4: Run the agent ────────────────────────────────────────────────
    result = orchestrator.execute_operation(effective_prompt, dry_run=args.dry_run)

    if args.dry_run:
        print("\n[CI] DRY RUN — Generated code (not executed):")
        print(result.get("generated_code", "(none)"))
        sys.exit(0)

    # ── Step 5: Save to the FIXED path (no timestamps) ───────────────────────
    if result["success"]:
        orchestrator.current_df.to_excel(output_path, index=False)

        print(f"\n[CI] ✅ Success — Excel updated at: {output_path}")
        print(f"[CI] Rows    : {result['rows_before']} → {result['rows_after']}")
        print(f"[CI] Columns : {result['columns_before']} → {result['columns_after']}")
        print(f"\n[CI] Current Data:\n{orchestrator.current_df.to_string()}")
        sys.exit(0)
    else:
        print(f"\n[CI] ❌ Failed after retries: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
