"""
Excel Agent Orchestrator for RAG Integration

This module provides a high-level interface to the Excel Agent, allowing it to be
used as a step within a larger RAG (Retrieval-Augmented Generation) workflow.

The orchestrator:
1. Analyzes user prompts to understand the required operations
2. Manages the Excel file lifecycle (loading, modification, saving)
3. Coordinates multiple agent operations if needed
4. Returns structured results with metadata
"""

import os
import sys
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import pandas as pd

# Import from agent in same directory
from agent import (
    create_fixture_excel,
    llm_generate,
    extract_code,
    run_generated_code,
    _unique_output
)


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class ExcelAgentOrchestrator:
    """
    Orchestrates Excel Agent operations within a RAG workflow.
    
    This class manages the lifecycle of Excel modifications, handles multiple
    operations, and provides structured output suitable for integration with
    RAG systems.
    """

    def __init__(self, model: str = "llama3", verbose: bool = False):
        """
        Initialize the orchestrator.
        
        Args:
            model: LLM model to use (default: llama3)
            verbose: Enable verbose logging (default: False)
        """
        self.model = model
        self.verbose = verbose
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        self.operation_history: List[Dict[str, Any]] = []
        self.current_df: Optional[pd.DataFrame] = None
        self.input_file: Optional[str] = None
        self.output_file: Optional[str] = None

    def load_excel(self, file_path: str) -> pd.DataFrame:
        """
        Load an Excel file or create a fixture if not found.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            Loaded DataFrame
        """
        if not os.path.exists(file_path):
            logger.info(f"Input file not found: {file_path}. Creating fixture.")
            create_fixture_excel(file_path)
        
        self.input_file = file_path
        self.current_df = pd.read_excel(file_path)
        logger.info(f"Loaded Excel file: {file_path} ({len(self.current_df)} rows, {len(self.current_df.columns)} columns)")
        return self.current_df

    def _analyze_task_type(self, task: str) -> str:
        """
        Analyze the task description to determine the type of operation.
        
        Args:
            task: Natural language task description
            
        Returns:
            Task type: 'add_rows', 'add_columns', 'filter', 'transform', 'custom'
        """
        task_lower = task.lower()
        
        if any(keyword in task_lower for keyword in ['add row', 'insert row', 'new row', 'create.*row']):
            return 'add_rows'
        elif any(keyword in task_lower for keyword in ['add column', 'new column', 'create.*column']):
            return 'add_columns'
        elif any(keyword in task_lower for keyword in ['filter', 'remove', 'delete', 'where']):
            return 'filter'
        elif any(keyword in task_lower for keyword in ['update', 'modify', 'change', 'rename', 'replace']):
            return 'transform'
        else:
            return 'custom'

    def _enhance_prompt_for_task(self, task: str, task_type: str, df: pd.DataFrame) -> str:
        """
        Create an enhanced prompt tailored to the specific task type.
        
        Args:
            task: Original task description
            task_type: Identified task type
            df: Current DataFrame
            
        Returns:
            Enhanced prompt for the LLM
        """
        base_prompt = (
            "You are a data manipulation expert. You have a pandas DataFrame named 'df' with the following structure:\n\n"
            f"Columns: {', '.join(df.columns.astype(str))}\n"
            f"Data types: {df.dtypes.to_dict()}\n"
            f"Number of rows: {len(df)}\n\n"
            f"Data preview:\n{df.to_string()}\n\n"
            "================================================================================\n"
        )

        if task_type == 'add_rows':
            task_specific = (
                "TASK: Add new rows to the DataFrame\n"
                f"Requirement: {task}\n\n"
                "For each new row, include all columns. Use:\n"
                "df = pd.concat([df, pd.DataFrame([{col1: val1, col2: val2, ...}])], ignore_index=True)\n"
            )
        elif task_type == 'add_columns':
            task_specific = (
                "TASK: Add new columns to the DataFrame\n"
                f"Requirement: {task}\n\n"
                "IMPORTANT: Create ALL new columns FIRST, then assign values.\n"
                "Example pattern:\n"
                "# Step 1: Initialize columns with default values\n"
                "df['ColumnA'] = ''\n"
                "df['ColumnB'] = ''\n"
                "# Step 2: Assign conditional values\n"
                "df.loc[condition, 'ColumnA'] = 'value1'\n"
                "df.loc[condition, 'ColumnB'] = 'value2'\n"
                "OR use list comprehension for initialization:\n"
                "df['NewCol'] = ['val1' if condition else 'val2' for idx, row in df.iterrows()]\n"
            )
        elif task_type == 'filter':
            task_specific = (
                "TASK: Filter or remove rows from the DataFrame\n"
                f"Requirement: {task}\n\n"
                "Use boolean indexing:\n"
                "df = df[condition]\n"
            )
        elif task_type == 'transform':
            task_specific = (
                "TASK: Transform or update existing data\n"
                f"Requirement: {task}\n\n"
                "Use appropriate pandas operations (str, apply, loc, etc.)\n"
            )
        else:
            task_specific = f"TASK: {task}\n"

        instructions = (
            "\nCRITICAL REQUIREMENTS FOR CODE GENERATION:\n"
            "1. Generate ONLY valid, executable Python code - no explanations or markdown\n"
            "2. The code must be syntactically correct and runnable\n"
            "3. Always assign the result back to variable 'df' (e.g., df = ... or df[...] = ...)\n"
            "4. Use proper pandas operations only\n"
            "5. Do NOT use deprecated methods like df.append()\n"
            "6. Handle data types correctly (strings, numbers, booleans)\n"
            "7. Do NOT print anything, write files, or import modules\n"
            "8. Return ONLY the Python code - no additional text\n"
            "9. Preserve all existing columns and data unless explicitly asked to remove\n"
            "10. Be precise with string values and data types\n\n"
            "Generate the Python code now:"
        )

        return base_prompt + task_specific + instructions

    def execute_operation(self, task: str, dry_run: bool = False, max_retries: int = 2) -> Dict[str, Any]:
        """
        Execute a single operation on the DataFrame.
        
        Args:
            task: Natural language task description
            dry_run: If True, only show generated code without executing
            max_retries: Maximum number of retries if code execution fails
            
        Returns:
            Dictionary with operation results and metadata
        """
        if self.current_df is None:
            raise ValueError("No DataFrame loaded. Call load_excel() first.")

        task_type = self._analyze_task_type(task)
        
        result = {
            "task": task,
            "task_type": task_type,
            "generated_code": None,
            "success": False,
            "error": None,
            "rows_before": len(self.current_df),
            "rows_after": None,
            "columns_before": list(self.current_df.columns),
            "columns_after": None,
            "timestamp": datetime.utcnow().isoformat(),
            "retry_count": 0
        }

        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{max_retries}...")
                task = f"{task}\n\nPrevious attempt failed with: {result['error']}. Please fix the code and ensure all columns are created before assignment."
            
            result["retry_count"] = attempt
            enhanced_prompt = self._enhance_prompt_for_task(task, task_type, self.current_df)

            if attempt == 0:
                logger.info(f"Executing {task_type} operation...")
                logger.debug(f"Task: {task}")

            # Generate code
            resp = llm_generate(enhanced_prompt, self.model)
            code = extract_code(resp)
            result["generated_code"] = code

            if dry_run:
                logger.info("DRY RUN - Code generated but not executed")
                return result

            # Execute code
            try:
                new_df = run_generated_code(code, self.current_df)
                self.current_df = new_df
                
                result["success"] = True
                result["rows_after"] = len(self.current_df)
                result["columns_after"] = list(self.current_df.columns)
                
                logger.info(f"✓ Operation successful ({result['rows_before']} → {result['rows_after']} rows)")
                break
                
            except RuntimeError as e:
                result["error"] = str(e)
                if attempt < max_retries:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                else:
                    logger.error(f"✗ Operation failed after {max_retries + 1} attempts: {e}")

        self.operation_history.append(result)
        return result

    def execute_workflow(self, operations: List[str], dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute multiple operations in sequence (workflow).
        
        Args:
            operations: List of task descriptions
            dry_run: If True, only show generated code without executing
            
        Returns:
            Dictionary with workflow results and all operation metadata
        """
        if self.current_df is None:
            raise ValueError("No DataFrame loaded. Call load_excel() first.")

        workflow_results = {
            "workflow_id": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
            "total_operations": len(operations),
            "operations": [],
            "final_df": None,
            "success": True,
        }

        for i, operation in enumerate(operations, 1):
            logger.info(f"\n[Step {i}/{len(operations)}] Processing operation...")
            result = self.execute_operation(operation, dry_run)
            workflow_results["operations"].append(result)
            
            if not result["success"]:
                workflow_results["success"] = False
                logger.warning("Workflow stopped due to operation failure")
                break

        if self.current_df is not None:
            workflow_results["final_df"] = self.current_df.copy()

        return workflow_results

    def save_output(self, output_path: str = "modified_output.xlsx", inplace: bool = False) -> str:
        """
        Save the modified DataFrame to a file.
        
        Args:
            output_path: Base path for output file
            inplace: If True, overwrite the input file
            
        Returns:
            Path to the saved file
        """
        if self.current_df is None:
            raise ValueError("No DataFrame to save.")

        if inplace and self.input_file:
            save_path = self.input_file
            backup_path = f"{self.input_file}.bak"
            if os.path.exists(self.input_file):
                os.replace(self.input_file, backup_path)
            logger.info(f"Saving to input file (backup at {backup_path})")
        else:
            save_path = _unique_output(output_path)
            logger.info(f"Saving to {save_path}")

        self.current_df.to_excel(save_path, index=False)
        self.output_file = save_path
        return save_path

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all operations performed.
        
        Returns:
            Dictionary with operation summary
        """
        return {
            "input_file": self.input_file,
            "output_file": self.output_file,
            "total_operations": len(self.operation_history),
            "successful_operations": sum(1 for op in self.operation_history if op["success"]),
            "failed_operations": sum(1 for op in self.operation_history if not op["success"]),
            "operations": self.operation_history,
            "current_shape": self.current_df.shape if self.current_df is not None else None,
            "current_columns": list(self.current_df.columns) if self.current_df is not None else None,
        }


def process_excel_with_prompt(
    prompt: str,
    input_file: str = "base.xlsx",
    output_file: str = "modified_output.xlsx",
    model: str = "llama3",
    inplace: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    High-level function to process Excel files with a single natural language prompt.
    
    This function:
    1. Analyzes the prompt to determine required operations
    2. Loads the Excel file
    3. Executes the operation
    4. Saves the result
    5. Returns structured output
    
    Args:
        prompt: Natural language description of the required operation
        input_file: Path to input Excel file (default: base.xlsx)
        output_file: Path for output Excel file (default: modified_output.xlsx)
        model: LLM model to use (default: llama3)
        inplace: If True, overwrite input file (default: False)
        dry_run: If True, only show generated code without executing (default: False)
        
    Returns:
        Dictionary with results containing:
        - success: bool indicating if operation succeeded
        - output_file: Path to generated Excel file
        - operation_details: Details about the operation
        - dataframe: The final DataFrame
        - summary: Summary of changes
    """
    logger.info(f"Processing prompt: {prompt[:100]}...")
    
    orchestrator = ExcelAgentOrchestrator(model=model, verbose=False)
    orchestrator.load_excel(input_file)
    
    # Execute the operation
    operation_result = orchestrator.execute_operation(prompt, dry_run=dry_run)
    
    if dry_run:
        return {
            "success": True,
            "generated_code": operation_result["generated_code"],
            "task_type": operation_result["task_type"],
            "dry_run": True,
        }
    
    # Save the output
    if operation_result["success"]:
        output_path = orchestrator.save_output(output_file, inplace=inplace)
        
        return {
            "success": True,
            "output_file": output_path,
            "operation_details": operation_result,
            "dataframe": orchestrator.current_df,
            "summary": {
                "rows_before": operation_result["rows_before"],
                "rows_after": operation_result["rows_after"],
                "columns_before": operation_result["columns_before"],
                "columns_after": operation_result["columns_after"],
            }
        }
    else:
        return {
            "success": False,
            "error": operation_result["error"],
            "operation_details": operation_result,
            "dataframe": orchestrator.current_df,
        }


if __name__ == "__main__":
    # Example usage
    print("Excel Agent Orchestrator - Example Usage\n")
    
    # Example 1: Single operation
    print("=" * 80)
    print("Example 1: Add columns to Excel file")
    print("=" * 80)
    
    result = process_excel_with_prompt(
        prompt='Add a column called "SnapLogic" with values: "Present" for Bob and Sara, "Not present" for others. Add a column called "Role" with values: "Data Engineer" for Bob and Sara, "Ex-developers" for others.',
        input_file="/Users/arshdeepdubey/tmp/excel-agent/base.xlsx",
        output_file="/Users/arshdeepdubey/tmp/excel-agent/modified_output.xlsx",
    )
    
    print(f"\nOperation Success: {result['success']}")
    if result['success']:
        print(f"Output File: {result['output_file']}")
        print(f"Summary: {result['summary']}")
        print(f"\nDataFrame:\n{result['dataframe'].to_string()}")
