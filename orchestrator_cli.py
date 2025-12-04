#!/usr/bin/env python3
"""
Excel Agent Orchestrator CLI

Command-line interface for the Excel Agent Orchestrator.
Allows processing Excel files with natural language prompts integrated in RAG workflows.

Usage Examples:
    python orchestrator_cli.py --prompt "Add columns ..." --input base.xlsx
    python orchestrator_cli.py --prompt "Filter rows where ..." --input data.xlsx --inplace
    python orchestrator_cli.py --workflow file_with_operations.json --input base.xlsx
"""

import argparse
import json
import sys
from pathlib import Path

from excel_agent_orchestrator import (
    ExcelAgentOrchestrator,
    process_excel_with_prompt
)


def main():
    parser = argparse.ArgumentParser(
        description="Excel Agent Orchestrator - Process Excel files with natural language",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single operation
  python orchestrator_cli.py --prompt "Add column called Active with value Yes for all rows" \\
                             --input data.xlsx --output result.xlsx

  # Workflow with multiple operations
  python orchestrator_cli.py --workflow operations.json --input data.xlsx

  # Dry-run to see generated code
  python orchestrator_cli.py --prompt "Filter rows where Status is Active" \\
                             --input data.xlsx --dry-run

  # In-place modification
  python orchestrator_cli.py --prompt "Add column Status with value Active" \\
                             --input data.xlsx --inplace
        """
    )

    parser.add_argument(
        "--prompt",
        type=str,
        help="Natural language prompt describing the operation to perform"
    )
    parser.add_argument(
        "--workflow",
        type=str,
        help="JSON file containing list of operations to perform sequentially"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="base.xlsx",
        help="Input Excel file (default: base.xlsx)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="modified_output.xlsx",
        help="Output Excel file prefix (default: modified_output.xlsx)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="llama3",
        help="LLM model to use (default: llama3)"
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Overwrite input file instead of creating new file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show generated code without executing"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.prompt and not args.workflow:
        parser.error("Either --prompt or --workflow must be provided")

    if args.prompt and args.workflow:
        parser.error("Cannot use both --prompt and --workflow")

    try:
        if args.prompt:
            # Single operation
            print(f"Processing prompt: {args.prompt[:80]}...")
            result = process_excel_with_prompt(
                prompt=args.prompt,
                input_file=args.input,
                output_file=args.output,
                model=args.model,
                inplace=args.inplace,
                dry_run=args.dry_run
            )
        else:
            # Workflow with multiple operations
            with open(args.workflow, 'r') as f:
                workflow_data = json.load(f)
            
            if isinstance(workflow_data, dict) and 'operations' in workflow_data:
                operations = workflow_data['operations']
            else:
                operations = workflow_data

            print(f"Loading workflow with {len(operations)} operations...")

            orchestrator = ExcelAgentOrchestrator(model=args.model, verbose=args.verbose)
            orchestrator.load_excel(args.input)
            
            workflow_result = orchestrator.execute_workflow(operations, dry_run=args.dry_run)
            
            if not args.dry_run and workflow_result['success']:
                output_file = orchestrator.save_output(args.output, inplace=args.inplace)
                result = {
                    "success": True,
                    "output_file": output_file,
                    "workflow": workflow_result,
                    "summary": orchestrator.get_summary()
                }
            else:
                result = workflow_result

        # Output results
        if args.output_json:
            # Prepare for JSON serialization
            if 'dataframe' in result and hasattr(result['dataframe'], 'to_dict'):
                result['dataframe'] = result['dataframe'].to_dict(orient='records')
            print(json.dumps(result, indent=2, default=str))
        else:
            # Pretty print results
            if result.get('success'):
                print("\n✓ Operation completed successfully!")
                if 'output_file' in result:
                    print(f"Output file: {result['output_file']}")
                if 'summary' in result:
                    print(f"\nSummary:")
                    summary = result['summary']
                    if isinstance(summary, dict):
                        for key, value in summary.items():
                            if key != 'operations':
                                print(f"  {key}: {value}")
                    else:
                        print(f"  Rows: {summary['rows_before']} → {summary['rows_after']}")
                        print(f"  Columns: {summary['columns_before']} → {summary['columns_after']}")
                if 'dataframe' in result:
                    print(f"\nResult DataFrame:")
                    print(result['dataframe'].to_string())
            else:
                print("\n✗ Operation failed!")
                if 'error' in result:
                    print(f"Error: {result['error']}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
