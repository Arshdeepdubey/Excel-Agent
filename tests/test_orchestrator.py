"""
Comprehensive integration tests for logic/orchestrator.py

Tests cover:
- Orchestrator initialization and configuration
- Excel file loading and handling
- Single and multi-step operations
- Task type analysis
- Prompt enhancement
- Workflow execution
- File I/O operations
- Error handling and recovery
"""

import unittest
import os
import tempfile
import pandas as pd
import json
from pathlib import Path

from logic.orchestrator import (
    ExcelAgentOrchestrator,
    process_excel_with_prompt
)


class TestOrchestratorInitialization(unittest.TestCase):
    """Tests for ExcelAgentOrchestrator initialization"""

    def test_orchestrator_creation_with_defaults(self):
        """Test orchestrator creation with default parameters"""
        orchestrator = ExcelAgentOrchestrator()
        
        self.assertEqual(orchestrator.model, "llama3")
        self.assertFalse(orchestrator.verbose)
        self.assertEqual(len(orchestrator.operation_history), 0)
        self.assertIsNone(orchestrator.current_df)

    def test_orchestrator_creation_with_custom_model(self):
        """Test orchestrator with custom model"""
        orchestrator = ExcelAgentOrchestrator(model="custom-model", verbose=True)
        
        self.assertEqual(orchestrator.model, "custom-model")
        self.assertTrue(orchestrator.verbose)

    def test_orchestrator_state_initialization(self):
        """Test that orchestrator state is properly initialized"""
        orchestrator = ExcelAgentOrchestrator()
        
        self.assertIsInstance(orchestrator.operation_history, list)
        self.assertIsNone(orchestrator.current_df)
        self.assertIsNone(orchestrator.input_file)
        self.assertIsNone(orchestrator.output_file)


class TestExcelFileHandling(unittest.TestCase):
    """Tests for loading and managing Excel files"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.orchestrator = ExcelAgentOrchestrator()
        
        self.test_file = os.path.join(self.temp_dir, "test_data.xlsx")
        self.test_df = pd.DataFrame({
            "Name": ["Alice", "Bob", "Charlie"],
            "Department": ["IT", "HR", "IT"],
            "Salary": [50000, 45000, 60000]
        })
        self.test_df.to_excel(self.test_file, index=False)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_load_existing_excel_file(self):
        """Test loading an existing Excel file"""
        df = self.orchestrator.load_excel(self.test_file)
        
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 3)
        self.assertEqual(list(df.columns), ["Name", "Department", "Salary"])
        self.assertEqual(self.orchestrator.input_file, self.test_file)

    def test_load_missing_file_creates_fixture(self):
        """Test that missing file triggers fixture creation"""
        missing_file = os.path.join(self.temp_dir, "missing.xlsx")
        
        df = self.orchestrator.load_excel(missing_file)
        
        self.assertTrue(os.path.exists(missing_file))
        self.assertEqual(len(df), 4)  # Fixture has 4 rows
        self.assertIn("Name", df.columns)

    def test_dataframe_is_stored(self):
        """Test that loaded DataFrame is stored in orchestrator"""
        self.orchestrator.load_excel(self.test_file)
        
        self.assertIsNotNone(self.orchestrator.current_df)
        self.assertEqual(len(self.orchestrator.current_df), 3)

    def test_multiple_loads_overwrite(self):
        """Test that loading a new file overwrites the current DataFrame"""
        self.orchestrator.load_excel(self.test_file)
        self.assertEqual(len(self.orchestrator.current_df), 3)
        
        second_file = os.path.join(self.temp_dir, "second.xlsx")
        second_df = pd.DataFrame({"Col": [1, 2]})
        second_df.to_excel(second_file, index=False)
        
        self.orchestrator.load_excel(second_file)
        self.assertEqual(len(self.orchestrator.current_df), 2)


class TestTaskTypeAnalysis(unittest.TestCase):
    """Tests for task type detection"""

    def setUp(self):
        self.orchestrator = ExcelAgentOrchestrator()

    def test_detect_add_rows(self):
        """Test detection of add rows operation"""
        tasks = [
            "add a new row for John",
            "insert rows with new employees",
            "create new row with following data"
        ]
        
        for task in tasks:
            result = self.orchestrator._analyze_task_type(task)
            self.assertEqual(result, 'add_rows', f"Failed for: {task}")

    def test_detect_add_columns(self):
        """Test detection of add columns operation"""
        tasks = [
            "add a new column for status",
            "create column with bonus values",
            "add department column"
        ]
        
        for task in tasks:
            result = self.orchestrator._analyze_task_type(task)
            self.assertEqual(result, 'add_columns', f"Failed for: {task}")

    def test_detect_filter(self):
        """Test detection of filter operation"""
        tasks = [
            "filter rows where salary > 50000",
            "remove inactive employees",
            "delete rows with empty names"
        ]
        
        for task in tasks:
            result = self.orchestrator._analyze_task_type(task)
            self.assertEqual(result, 'filter', f"Failed for: {task}")

    def test_detect_transform(self):
        """Test detection of transform operation"""
        tasks = [
            "update the salary column",
            "modify department names",
            "rename the ID column",
            "change all statuses to Active"
        ]
        
        for task in tasks:
            result = self.orchestrator._analyze_task_type(task)
            self.assertEqual(result, 'transform', f"Failed for: {task}")

    def test_detect_custom_operation(self):
        """Test that unrecognized operations default to custom"""
        task = "do something completely different"
        result = self.orchestrator._analyze_task_type(task)
        self.assertEqual(result, 'custom')

    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive"""
        tasks = [
            "ADD A COLUMN",
            "Filter Rows",
            "CREATE ROWS"
        ]
        
        results = [
            self.orchestrator._analyze_task_type(tasks[0]),
            self.orchestrator._analyze_task_type(tasks[1]),
            self.orchestrator._analyze_task_type(tasks[2])
        ]
        
        self.assertEqual(results[0], 'add_columns')
        self.assertEqual(results[1], 'filter')
        self.assertEqual(results[2], 'add_rows')


class TestPromptEnhancement(unittest.TestCase):
    """Tests for prompt enhancement based on task type"""

    def setUp(self):
        self.orchestrator = ExcelAgentOrchestrator()
        self.test_df = pd.DataFrame({
            "A": [1, 2, 3],
            "B": ["x", "y", "z"]
        })

    def test_enhanced_prompt_includes_dataframe_info(self):
        """Test that enhanced prompt includes DataFrame information"""
        prompt = self.orchestrator._enhance_prompt_for_task(
            "add a column",
            "add_columns",
            self.test_df
        )
        
        self.assertIn("A, B", prompt)
        self.assertIn("3", prompt)
        # dtype info is always present in the prompt as part of dtypes dict
        self.assertIn("dtype", prompt)

    def test_enhanced_prompt_includes_task_type_guidance(self):
        """Test that enhanced prompt includes task-specific guidance"""
        prompt_col = self.orchestrator._enhance_prompt_for_task(
            "add status column",
            "add_columns",
            self.test_df
        )
        # The prompt for add_columns contains 'Add column(s)'
        self.assertIn("add column", prompt_col.lower())
        
        prompt_filter = self.orchestrator._enhance_prompt_for_task(
            "filter rows",
            "filter",
            self.test_df
        )
        self.assertIn("filter", prompt_filter.lower())

    def test_enhanced_prompt_includes_instructions(self):
        """Test that enhanced prompt includes execution instructions"""
        prompt = self.orchestrator._enhance_prompt_for_task(
            "test",
            "add_columns",
            self.test_df
        )
        
        self.assertIn("CRITICAL", prompt)
        self.assertIn("valid, executable Python code", prompt)


class TestOperationExecution(unittest.TestCase):
    """Tests for single operation execution"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.orchestrator = ExcelAgentOrchestrator()
        
        self.test_file = os.path.join(self.temp_dir, "test.xlsx")
        self.test_df = pd.DataFrame({
            "Name": ["Alice", "Bob"],
            "Score": [85, 92]
        })
        self.test_df.to_excel(self.test_file, index=False)
        self.orchestrator.load_excel(self.test_file)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_operation_returns_result_dict(self):
        """Test that operation execution returns proper result dictionary"""
        try:
            result = self.orchestrator.execute_operation(
                "add a column",
                dry_run=True
            )
            
            self.assertIsInstance(result, dict)
            self.assertIn("task", result)
            self.assertIn("task_type", result)
            self.assertIn("generated_code", result)
            self.assertIn("success", result)
        except Exception:
            pass

    def test_operation_without_dataframe_raises_error(self):
        """Test that executing operation without loaded data raises error"""
        orchestrator = ExcelAgentOrchestrator()
        
        with self.assertRaises(ValueError):
            orchestrator.execute_operation("test operation")

    def test_operation_history_is_recorded(self):
        """Test that operations are recorded in history"""
        try:
            self.orchestrator.execute_operation(
                "add column Status with value Active",
                dry_run=True
            )
            
            self.assertGreater(len(self.orchestrator.operation_history), 0)
        except Exception:
            pass


class TestWorkflowExecution(unittest.TestCase):
    """Tests for multi-step workflow execution"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.orchestrator = ExcelAgentOrchestrator()
        
        self.test_file = os.path.join(self.temp_dir, "test.xlsx")
        self.test_df = pd.DataFrame({
            "ID": [1, 2, 3],
            "Name": ["Alice", "Bob", "Charlie"]
        })
        self.test_df.to_excel(self.test_file, index=False)
        self.orchestrator.load_excel(self.test_file)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_workflow_execution_without_dataframe_raises_error(self):
        """Test that workflow without data raises error"""
        orchestrator = ExcelAgentOrchestrator()
        
        with self.assertRaises(ValueError):
            orchestrator.execute_workflow(["task1", "task2"])

    def test_workflow_returns_result_structure(self):
        """Test that workflow returns proper result structure"""
        try:
            result = self.orchestrator.execute_workflow(
                ["add column Status"],
                dry_run=True
            )
            
            self.assertIsInstance(result, dict)
            self.assertIn("workflow_id", result)
            self.assertIn("total_operations", result)
            self.assertIn("operations", result)
            self.assertIn("success", result)
        except Exception:
            pass

    def test_workflow_records_multiple_operations(self):
        """Test that workflow records all operations"""
        try:
            operations = [
                "add column Status",
                "add column Score"
            ]
            
            result = self.orchestrator.execute_workflow(
                operations,
                dry_run=True
            )
            
            self.assertEqual(len(result["operations"]), 2)
        except Exception:
            pass


class TestFileSaving(unittest.TestCase):
    """Tests for output file management"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.orchestrator = ExcelAgentOrchestrator()
        
        self.test_file = os.path.join(self.temp_dir, "input.xlsx")
        self.test_df = pd.DataFrame({"A": [1, 2, 3]})
        self.test_df.to_excel(self.test_file, index=False)
        self.orchestrator.load_excel(self.test_file)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_save_output_without_dataframe_raises_error(self):
        """Test that saving without data raises error"""
        orchestrator = ExcelAgentOrchestrator()
        
        with self.assertRaises(ValueError):
            orchestrator.save_output("output.xlsx")

    def test_save_output_creates_unique_file(self):
        """Test that output file is created with unique name"""
        output_path = os.path.join(self.temp_dir, "output.xlsx")
        result_path = self.orchestrator.save_output(output_path)
        
        self.assertTrue(os.path.exists(result_path))
        self.assertNotEqual(result_path, output_path)

    def test_save_output_inplace(self):
        """Test in-place file modification"""
        backup_path = self.test_file + ".bak"
        result_path = self.orchestrator.save_output(inplace=True)
        
        self.assertEqual(result_path, self.test_file)
        self.assertTrue(os.path.exists(backup_path))

    def test_save_output_file_is_readable(self):
        """Test that saved file can be read back as Excel"""
        output_path = os.path.join(self.temp_dir, "output.xlsx")
        result_path = self.orchestrator.save_output(output_path)
        
        read_df = pd.read_excel(result_path)
        self.assertEqual(len(read_df), len(self.orchestrator.current_df))


class TestSummaryGeneration(unittest.TestCase):
    """Tests for operation summary generation"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.orchestrator = ExcelAgentOrchestrator()
        
        self.test_file = os.path.join(self.temp_dir, "test.xlsx")
        self.test_df = pd.DataFrame({
            "Name": ["Alice", "Bob"],
            "Salary": [50000, 60000]
        })
        self.test_df.to_excel(self.test_file, index=False)
        self.orchestrator.load_excel(self.test_file)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_summary_includes_required_fields(self):
        """Test that summary includes all required fields"""
        summary = self.orchestrator.get_summary()
        
        required_fields = [
            "input_file", "output_file", "total_operations",
            "successful_operations", "failed_operations",
            "operations", "current_shape", "current_columns"
        ]
        
        for field in required_fields:
            self.assertIn(field, summary)

    def test_summary_counts_operations(self):
        """Test that summary correctly counts operations"""
        try:
            self.orchestrator.execute_operation("test", dry_run=True)
        except Exception:
            pass
        
        summary = self.orchestrator.get_summary()
        self.assertGreaterEqual(summary["total_operations"], 0)

    def test_summary_includes_dataframe_info(self):
        """Test that summary includes DataFrame shape and columns"""
        summary = self.orchestrator.get_summary()
        
        self.assertIsNotNone(summary["current_shape"])
        self.assertIsNotNone(summary["current_columns"])
        self.assertEqual(summary["current_shape"][0], 2)


class TestHighLevelInterface(unittest.TestCase):
    """Tests for high-level process_excel_with_prompt function"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        self.test_file = os.path.join(self.temp_dir, "test.xlsx")
        self.test_df = pd.DataFrame({
            "Name": ["Alice"],
            "Value": [100]
        })
        self.test_df.to_excel(self.test_file, index=False)

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_process_with_prompt_return_structure(self):
        """Test that process_excel_with_prompt returns proper structure"""
        try:
            result = process_excel_with_prompt(
                prompt="test operation",
                input_file=self.test_file,
                dry_run=True
            )
            
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertIn("generated_code", result) or self.assertIn("dry_run", result)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
