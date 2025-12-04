"""
RAG Integration Example - Excel Agent in a Retrieval-Augmented Generation Pipeline

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

from excel_agent_orchestrator import (
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
        
        # In a real RAG system, this would use semantic search to determine:
        # 1. What data to load
        # 2. What operations are needed
        # 3. How to format results
        
        # For this example, we'll do simple pattern matching
        query_lower = user_query.lower()
        
        # Detect operation types
        if any(keyword in query_lower for keyword in ['add', 'create', 'new column']):
            # Adding columns
            operation = f"Process this request: {user_query}"
            return self.simple_operation(operation, excel_file)
        
        elif any(keyword in query_lower for keyword in ['filter', 'where', 'only show']):
            # Filtering data
            operation = f"Filter the data according to: {user_query}"
            return self.simple_operation(operation, excel_file)
        
        elif any(keyword in query_lower for keyword in ['analyze', 'check', 'look at']):
            # Analysis - might need multiple steps
            operations = [
                f"Add analysis columns based on: {user_query}",
                "Ensure all relevant columns are populated"
            ]
            return self.multi_step_operation(operations, excel_file)
        
        else:
            # Generic operation
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
# Example Usage Scenarios
# ============================================================================

def example_1_simple_column_addition():
    """Example 1: Add a single column to existing data."""
    print("\n" + "="*80)
    print("Example 1: Simple Column Addition")
    print("="*80)
    
    rag = RAGExcelIntegration()
    
    result = rag.simple_operation(
        prompt='Add a column called "Priority" with values: "High" for Quantity > 3, "Low" for others',
        excel_file="base.xlsx"
    )
    
    if result['success']:
        print(f"\nOutput: {result['output_file']}")
        print(f"\nData preview:")
        print(result['dataframe'].to_string())


def example_2_multi_step_enrichment():
    """Example 2: Multi-step data enrichment workflow."""
    print("\n" + "="*80)
    print("Example 2: Multi-Step Data Enrichment")
    print("="*80)
    
    rag = RAGExcelIntegration()
    
    operations = [
        'Add column "SnapLogic" with "Present" for Bob/Sara, "Not present" for others',
        'Add column "Role" with "Data Engineer" for Bob/Sara, "Ex-developers" for others',
        'Add column "Team" with "Engineering" for Engineering department, "Other" for others'
    ]
    
    result = rag.multi_step_operation(
        operations=operations,
        excel_file="base.xlsx"
    )
    
    if result.get('success'):
        print(f"\nOutput: {result['output_file']}")
        print(f"\nFinal data shape: {result['dataframe'].shape}")
        print(f"\nData preview:")
        print(result['dataframe'].to_string())
        print(f"\nSummary: {rag.get_summary()}")


def example_3_intelligent_routing():
    """Example 3: Intelligent query routing."""
    print("\n" + "="*80)
    print("Example 3: Intelligent Query Routing")
    print("="*80)
    
    rag = RAGExcelIntegration()
    
    # User queries that would come from a chatbot/RAG system
    queries = [
        "Add a Verification status for each employee",
        "Show me only the Engineering department employees",
        "Analyze which employees are active"
    ]
    
    for query in queries:
        print(f"\nUser Query: {query}")
        result = rag.intelligent_routing(
            user_query=query,
            excel_file="base.xlsx"
        )
        print(f"Status: {'✓ Success' if result.get('success') else '✗ Failed'}")


def example_4_rag_pipeline():
    """Example 4: Full RAG pipeline simulation."""
    print("\n" + "="*80)
    print("Example 4: Full RAG Pipeline")
    print("="*80)
    
    print("""
    Simulated RAG Pipeline:
    
    1. User provides query: "Who are the Data Engineers?"
    2. RAG System:
       - Retrieves relevant documents (employee list in Excel)
       - Determines operations needed (filter + add columns)
       - Routes to Excel Agent
    3. Excel Agent:
       - Adds "Role" column
       - Filters for "Data Engineer"
    4. Results returned to user
    """)
    
    rag = RAGExcelIntegration()
    
    # Simulate a RAG response that determined these operations
    rag_determined_operations = [
        'Add column "Role" with "Data Engineer" for employees with Engineering department, "Other" for others',
        'Keep only rows where Role is "Data Engineer"'
    ]
    
    result = rag.multi_step_operation(
        operations=rag_determined_operations,
        excel_file="base.xlsx",
        output_file="rag_query_result.xlsx"
    )
    
    if result.get('success'):
        print(f"\n[RAG Result] Found {len(result['dataframe'])} matching records")
        print(result['dataframe'].to_string())


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
    
    This function is the main entry point for integrating Excel Agent
    with a RAG system.
    
    Args:
        user_prompt: Original user query/request
        data_file: Path to Excel data file
        operations: Optional list of specific operations (if RAG pre-determined them)
        model: LLM model to use
        
    Returns:
        Dictionary containing:
        - success: bool
        - output_file: Path to result
        - dataframe: Processed data as DataFrame
        - summary: Summary of operations
        
    Example:
        result = rag_process_excel(
            user_prompt="Add engineer roles to our dataset",
            data_file="employees.xlsx"
        )
        processed_data = result['dataframe']
    """
    rag = RAGExcelIntegration(model=model)
    
    if operations:
        # Use pre-determined operations from RAG
        return rag.multi_step_operation(
            operations=operations,
            excel_file=data_file
        )
    else:
        # Let orchestrator determine operations from prompt
        return rag.simple_operation(
            prompt=user_prompt,
            excel_file=data_file
        )


if __name__ == "__main__":
    # Run all examples
    example_1_simple_column_addition()
    example_2_multi_step_enrichment()
    example_3_intelligent_routing()
    example_4_rag_pipeline()
    
    print("\n" + "="*80)
    print("Integration Examples Complete")
    print("="*80)
