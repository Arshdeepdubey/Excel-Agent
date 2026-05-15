"""
RAG Integration - Excel Agent in a Retrieval-Augmented Generation Pipeline

This module demonstrates how to integrate the Excel Agent as a step within a RAG workflow.
It shows how to:
1. Accept user prompts
2. Route to appropriate processing (RAG + Excel processing)
3. Combine results
4. Return processed Excel files

Example Use Case:
User: "Give me the list of Data Engineers who are active in our Engineering department"
RAG Flow:
  1. Parse requirement (identify this needs data from Excel)
  2. Load Excel data
  3. Process with Excel Agent (add/filter columns as needed)
  4. Return filtered results
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

from logic.orchestrator import (
    ExcelAgentOrchestrator,
    process_excel_with_prompt
)


class RAGExcelIntegration:
    """
    RAG-Excel Integration Pipeline
    
    Manages the integration of Excel Agent within a RAG workflow.
    """
    
    def __init__(self, model: str = "llama3", verbose: bool = False):
        """Initialize the RAG-Excel integration."""
        self.model = model
        self.verbose = verbose
        self.operation_log: List[Dict] = []
    
    def simple_operation(
        self,
        prompt: str,
        excel_file: str,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a simple single-step Excel operation.
        
        Args:
            prompt: Natural language description of operation
            excel_file: Path to input Excel file
            output_file: Path for output (optional)
            
        Returns:
            Dictionary with results and metadata
        """
        print(f"\n[RAG] Processing Excel operation...")
        print(f"  Prompt: {prompt[:80]}...")
        
        result = process_excel_with_prompt(
            prompt=prompt,
            input_file=excel_file,
            output_file=output_file or "rag_output.xlsx",
            model=self.model
        )
        
        self.operation_log.append({
            "type": "simple_operation",
            "prompt": prompt,
            "success": result.get("success", False)
        })
        
        return result
    
    def multi_step_operation(
        self,
        operations: List[str],
        excel_file: str,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute multiple operations in sequence (workflow).
        
        Args:
            operations: List of operation prompts
            excel_file: Path to input Excel file
            output_file: Path for output (optional)
            
        Returns:
            Dictionary with results for all operations
        """
        print(f"\n[RAG] Processing {len(operations)}-step workflow...")
        
        orchestrator = ExcelAgentOrchestrator(model=self.model, verbose=self.verbose)
        orchestrator.load_excel(excel_file)
        
        results = orchestrator.execute_workflow(operations, dry_run=False)
        
        if results["success"]:
            output_path = orchestrator.save_output(
                output_file or "rag_workflow_output.xlsx",
                inplace=False
            )
            results["output_file"] = output_path
            results["dataframe"] = orchestrator.current_df
            
            print(f"  ✓ Workflow completed successfully")
        else:
            print(f"  ✗ Workflow failed")
        
        self.operation_log.append({
            "type": "multi_step_operation",
            "operations": operations,
            "success": results.get("success", False)
        })
        
        return results
    
    def intelligent_routing(
        self,
        user_query: str,
        excel_file: str
    ) -> Dict[str, Any]:
        """
        Intelligent routing - determines what type of Excel operation is needed.
        
        This is where RAG would analyze the user query and determine:
        - Whether Excel processing is needed
        - What operations are required
        - How to structure the workflow
        
        Args:
            user_query: User's natural language request
            excel_file: Path to data file
            
        Returns:
            Processed results
        """
        print(f"\n[RAG] Analyzing query: '{user_query}'")
        
        query_lower = user_query.lower()
        
        # Detect operation types
        if any(keyword in query_lower for keyword in ['add', 'create', 'new column']):
            operation = f"Process this request: {user_query}"
            return self.simple_operation(operation, excel_file)
        
        elif any(keyword in query_lower for keyword in ['filter', 'where', 'only show']):
            operation = f"Filter the data according to: {user_query}"
            return self.simple_operation(operation, excel_file)
        
        elif any(keyword in query_lower for keyword in ['analyze', 'check', 'look at']):
            operations = [
                f"Add analysis columns based on: {user_query}",
                "Ensure all relevant columns are populated"
            ]
            return self.multi_step_operation(operations, excel_file)
        
        else:
            return self.simple_operation(user_query, excel_file)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all operations performed."""
        successful = sum(1 for op in self.operation_log if op.get("success"))
        return {
            "total_operations": len(self.operation_log),
            "successful": successful,
            "failed": len(self.operation_log) - successful,
            "operations": self.operation_log
        }


# ============================================================================
# Integration Interface - Use this in your RAG system
# ============================================================================

def rag_process_excel(
    user_prompt: str,
    data_file: str,
    operations: Optional[List[str]] = None,
    model: str = "llama3"
) -> Dict[str, Any]:
    """
    High-level function for RAG systems to process Excel files.
    
    Args:
        user_prompt: Original user query/request
        data_file: Path to Excel data file
        operations: Optional list of specific operations (if RAG pre-determined them)
        model: LLM model to use
        
    Returns:
        Dictionary containing success, output_file, dataframe, summary
    """
    rag = RAGExcelIntegration(model=model)
    
    if operations:
        return rag.multi_step_operation(
            operations=operations,
            excel_file=data_file
        )
    else:
        return rag.simple_operation(
            prompt=user_prompt,
            excel_file=data_file
        )
