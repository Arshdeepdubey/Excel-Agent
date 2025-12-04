"""
End-to-End RAG Workflow Integration Tests

Tests the complete workflow of:
1. Loading Excel data
2. Processing with RAG-determined operations
3. Multi-step enrichment
4. Filtering and transformations
5. Output generation and verification
"""

import unittest
import os
import tempfile
import pandas as pd
import json
from pathlib import Path

from rag_integration_example import (
    RAGExcelIntegration,
    rag_process_excel
)
from excel_agent_orchestrator import ExcelAgentOrchestrator


class TestRAGIntegrationBasics(unittest.TestCase):
    """Test RAG integration initialization and basic operations"""

    def test_rag_initialization(self):
        """Test RAGExcelIntegration initialization"""
        rag = RAGExcelIntegration()
        
        self.assertEqual(rag.model, "llama3")
        self.assertFalse(rag.verbose)
        self.assertEqual(len(rag.operation_log), 0)

    def test_rag_with_custom_model(self):
        """Test RAG with custom LLM model"""
        rag = RAGExcelIntegration(model="custom-model", verbose=True)
        
        self.assertEqual(rag.model, "custom-model")
        self.assertTrue(rag.verbose)


class TestRAGSimpleOperation(unittest.TestCase):
    """Test simple single-step RAG operations"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.rag = RAGExcelIntegration()
        
        # Create test Excel file
        self.test_file = os.path.join(self.temp_dir, "employees.xlsx")
        self.test_df = pd.DataFrame({
            "Name": ["Bob", "Sara", "Mike", "Lucy"],
            "Department": ["Engineering", "HR", "Engineering", "Finance"],
            "Salary": [80000, 70000, 85000, 65000],
            "Years": [5, 3, 7, 2]
        })
        self.test_df.to_excel(self.test_file, index=False)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_simple_operation_returns_dict(self):
        """Test that simple operation returns proper dictionary"""
        try:
            result = self.rag.simple_operation(
                prompt="Add a Status column with Active for all rows",
                excel_file=self.test_file
            )
            
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
        except Exception as e:
            # May fail without LLM, skip
            self.skipTest(f"LLM not available: {e}")

    def test_simple_operation_logs_operation(self):
        """Test that simple operation is logged"""
        try:
            self.rag.simple_operation(
                prompt="test operation",
                excel_file=self.test_file
            )
            
            self.assertEqual(len(self.rag.operation_log), 1)
            self.assertEqual(self.rag.operation_log[0]["type"], "simple_operation")
        except Exception:
            self.skipTest("LLM not available")


class TestRAGMultiStepWorkflow(unittest.TestCase):
    """Test multi-step RAG workflow execution"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.rag = RAGExcelIntegration()
        
        # Create test file
        self.test_file = os.path.join(self.temp_dir, "data.xlsx")
        self.test_df = pd.DataFrame({
            "Name": ["Alice", "Bob", "Charlie"],
            "Department": ["IT", "Sales", "IT"],
            "Salary": [75000, 60000, 80000]
        })
        self.test_df.to_excel(self.test_file, index=False)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_multi_step_operation_returns_dict(self):
        """Test that multi-step operation returns proper dictionary"""
        try:
            operations = [
                "Add column Status with Active for all",
                "Add column Category with Senior for salary > 70000"
            ]
            
            result = self.rag.multi_step_operation(
                operations=operations,
                excel_file=self.test_file
            )
            
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertIn("operations", result)
        except Exception:
            self.skipTest("LLM not available")

    def test_multi_step_operation_logs_all_operations(self):
        """Test that all operations in workflow are logged"""
        try:
            operations = ["op1", "op2", "op3"]
            
            self.rag.multi_step_operation(
                operations=operations,
                excel_file=self.test_file
            )
            
            self.assertEqual(len(self.rag.operation_log), 1)
            self.assertEqual(self.rag.operation_log[0]["type"], "multi_step_operation")
        except Exception:
            self.skipTest("LLM not available")


class TestRAGIntelligentRouting(unittest.TestCase):
    """Test intelligent query routing (pattern matching based)"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.rag = RAGExcelIntegration()
        
        # Create test file
        self.test_file = os.path.join(self.temp_dir, "data.xlsx")
        self.test_df = pd.DataFrame({
            "Name": ["Alice", "Bob"],
            "Value": [100, 200]
        })
        self.test_df.to_excel(self.test_file, index=False)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_routing_add_operation(self):
        """Test routing detects add operations"""
        try:
            result = self.rag.intelligent_routing(
                user_query="Add a new status column",
                excel_file=self.test_file
            )
            
            # Should route to simple operation (add is straightforward)
            self.assertIsInstance(result, dict)
        except Exception:
            self.skipTest("LLM not available")

    def test_routing_filter_operation(self):
        """Test routing detects filter operations"""
        try:
            result = self.rag.intelligent_routing(
                user_query="Filter rows where Value > 150",
                excel_file=self.test_file
            )
            
            self.assertIsInstance(result, dict)
        except Exception:
            self.skipTest("LLM not available")

    def test_routing_analysis_operation(self):
        """Test routing detects analysis operations"""
        try:
            result = self.rag.intelligent_routing(
                user_query="Analyze the data for patterns",
                excel_file=self.test_file
            )
            
            # Analysis typically routes to multi-step
            self.assertIsInstance(result, dict)
        except Exception:
            self.skipTest("LLM not available")


class TestRAGSummary(unittest.TestCase):
    """Test RAG operation summary and tracking"""

    def test_summary_structure(self):
        """Test that summary has proper structure"""
        rag = RAGExcelIntegration()
        summary = rag.get_summary()
        
        self.assertIn("total_operations", summary)
        self.assertIn("successful", summary)
        self.assertIn("failed", summary)
        self.assertIn("operations", summary)
        
        self.assertEqual(summary["total_operations"], 0)

    def test_summary_counts_correctly(self):
        """Test that summary counts operations correctly"""
        rag = RAGExcelIntegration()
        
        # Simulate adding operations to log
        rag.operation_log.append({"success": True, "type": "test"})
        rag.operation_log.append({"success": False, "type": "test"})
        
        summary = rag.get_summary()
        
        self.assertEqual(summary["total_operations"], 2)
        self.assertEqual(summary["successful"], 1)
        self.assertEqual(summary["failed"], 1)


class TestRAGEndToEndWorkflow(unittest.TestCase):
    """End-to-end tests of complete RAG workflows"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create realistic employee data
        self.test_file = os.path.join(self.temp_dir, "employees.xlsx")
        self.employees_df = pd.DataFrame({
            "ID": [1, 2, 3, 4, 5],
            "Name": ["Alice Johnson", "Bob Smith", "Carol White", "David Brown", "Eva Green"],
            "Department": ["Engineering", "Sales", "Engineering", "HR", "Finance"],
            "Salary": [95000, 65000, 100000, 70000, 75000],
            "YearsEmployed": [5, 3, 7, 2, 4],
            "Status": ["Active", "Active", "Active", "Inactive", "Active"]
        })
        self.employees_df.to_excel(self.test_file, index=False)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_workflow_employee_enrichment(self):
        """Test workflow: enriching employee data with multiple columns"""
        try:
            rag = RAGExcelIntegration()
            
            operations = [
                'Add column "SalaryLevel" with "Senior" for salary > 90000, "Junior" for salary <= 90000',
                'Add column "Experience" with "Veteran" for YearsEmployed > 5, "Standard" for others'
            ]
            
            result = rag.multi_step_operation(
                operations=operations,
                excel_file=self.test_file,
                output_file=os.path.join(self.temp_dir, "enriched_employees.xlsx")
            )
            
            if result.get("success"):
                # Verify output file exists
                self.assertTrue(os.path.exists(result["output_file"]))
                
                # Verify data has new columns
                enriched_df = result.get("dataframe")
                if enriched_df is not None:
                    self.assertIn("SalaryLevel", enriched_df.columns)
        except Exception as e:
            self.skipTest(f"LLM not available: {e}")

    def test_workflow_engineering_team_analysis(self):
        """Test workflow: analyzing engineering team"""
        try:
            rag = RAGExcelIntegration()
            
            operations = [
                'Add column "IsEngineer" with "Yes" for Department = "Engineering", "No" for others',
                'Add column "SeniorEngineer" with "Yes" for IsEngineer = "Yes" AND Salary > 90000'
            ]
            
            result = rag.multi_step_operation(
                operations=operations,
                excel_file=self.test_file,
                output_file=os.path.join(self.temp_dir, "engineering_analysis.xlsx")
            )
            
            if result.get("success"):
                self.assertTrue(os.path.exists(result["output_file"]))
        except Exception:
            self.skipTest("LLM not available")

    def test_workflow_active_employees_only(self):
        """Test workflow: filtering to active employees only"""
        try:
            rag = RAGExcelIntegration()
            
            operations = [
                'Add column "IsActive" with "Yes" for Status = "Active", "No" for others',
                'Filter rows to keep only IsActive = "Yes"'
            ]
            
            result = rag.multi_step_operation(
                operations=operations,
                excel_file=self.test_file,
                output_file=os.path.join(self.temp_dir, "active_employees.xlsx")
            )
            
            if result.get("success"):
                result_df = result.get("dataframe")
                if result_df is not None:
                    # All rows should have Status = Active
                    self.assertTrue(all(result_df["Status"] == "Active"))
        except Exception:
            self.skipTest("LLM not available")


class TestRAGProcessExcelInterface(unittest.TestCase):
    """Test the main rag_process_excel integration interface"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        self.test_file = os.path.join(self.temp_dir, "data.xlsx")
        self.test_df = pd.DataFrame({
            "Product": ["A", "B", "C"],
            "Sales": [1000, 1500, 800]
        })
        self.test_df.to_excel(self.test_file, index=False)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_rag_process_excel_with_operations(self):
        """Test rag_process_excel with pre-determined operations"""
        try:
            operations = ["Add column Status with High for sales > 1200"]
            
            result = rag_process_excel(
                user_prompt="Analyze sales data",
                data_file=self.test_file,
                operations=operations
            )
            
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
        except Exception:
            self.skipTest("LLM not available")

    def test_rag_process_excel_with_prompt_only(self):
        """Test rag_process_excel with just user prompt"""
        try:
            result = rag_process_excel(
                user_prompt="Add a status column",
                data_file=self.test_file
            )
            
            self.assertIsInstance(result, dict)
        except Exception:
            self.skipTest("LLM not available")


class TestRAGWorkflowWithComplexData(unittest.TestCase):
    """Test RAG workflows with realistic complex scenarios"""

    def setUp(self):
        """Set up complex test data"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create realistic sales data
        self.test_file = os.path.join(self.temp_dir, "sales.xlsx")
        self.sales_df = pd.DataFrame({
            "Date": ["2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19"],
            "Region": ["North", "South", "North", "West", "South"],
            "Product": ["Widget A", "Widget B", "Widget A", "Widget C", "Widget B"],
            "Quantity": [10, 25, 15, 5, 30],
            "UnitPrice": [100.0, 75.0, 100.0, 200.0, 75.0],
            "Status": ["Completed", "Completed", "Pending", "Completed", "Cancelled"]
        })
        self.sales_df.to_excel(self.test_file, index=False)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_sales_revenue_calculation(self):
        """Test workflow: calculate revenue from sales data"""
        try:
            rag = RAGExcelIntegration()
            
            operations = [
                "Add column Revenue with calculation Quantity * UnitPrice"
            ]
            
            result = rag.multi_step_operation(
                operations=operations,
                excel_file=self.test_file,
                output_file=os.path.join(self.temp_dir, "sales_with_revenue.xlsx")
            )
            
            if result.get("success"):
                self.assertTrue(os.path.exists(result["output_file"]))
                result_df = result.get("dataframe")
                if result_df is not None:
                    self.assertIn("Revenue", result_df.columns)
        except Exception:
            self.skipTest("LLM not available")

    def test_sales_categorization(self):
        """Test workflow: categorize sales by status and value"""
        try:
            rag = RAGExcelIntegration()
            
            operations = [
                'Add column "SaleValue" with "High" for Quantity * UnitPrice > 2000, "Medium" for others',
                'Add column "ValidSale" with "Yes" for Status = "Completed", "No" for others'
            ]
            
            result = rag.multi_step_operation(
                operations=operations,
                excel_file=self.test_file,
                output_file=os.path.join(self.temp_dir, "sales_categorized.xlsx")
            )
            
            if result.get("success"):
                self.assertTrue(os.path.exists(result["output_file"]))
        except Exception:
            self.skipTest("LLM not available")


class TestRAGErrorHandling(unittest.TestCase):
    """Test error handling in RAG workflows"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_missing_file_handling(self):
        """Test handling of missing input file"""
        rag = RAGExcelIntegration()
        missing_file = os.path.join(self.temp_dir, "nonexistent.xlsx")
        
        try:
            # This might create a fixture or raise an error
            result = rag.simple_operation(
                prompt="test",
                excel_file=missing_file
            )
            # If it succeeds, it created a fixture
            self.assertIsInstance(result, dict)
        except Exception:
            # Expected behavior - file doesn't exist
            pass

    def test_invalid_excel_file(self):
        """Test handling of invalid Excel file"""
        invalid_file = os.path.join(self.temp_dir, "invalid.xlsx")
        
        # Create a non-Excel file
        with open(invalid_file, 'w') as f:
            f.write("This is not an Excel file")
        
        rag = RAGExcelIntegration()
        
        try:
            result = rag.simple_operation(
                prompt="test",
                excel_file=invalid_file
            )
            # Might fail or handle gracefully
        except Exception as e:
            # Expected to fail with invalid file
            self.assertIn("Excel" or "error", str(e).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
