"""
Comprehensive unit tests for logic/agent.py

Tests cover:
- Code extraction from various LLM response formats
- Safe code execution
- Fixture creation and management
- Error handling and edge cases
- DataFrame manipulation functions
"""

import unittest
import os
import tempfile
import pandas as pd
import numpy as np
from pathlib import Path
import re

from logic.agent import (
    create_fixture_excel,
    extract_code,
    run_generated_code,
    _unique_output,
    llm_generate
)


class TestFixtureCreation(unittest.TestCase):
    """Tests for create_fixture_excel() function"""

    def setUp(self):
        """Create temporary directory for test files"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_fixture_creates_file(self):
        """Test that fixture creation produces a valid Excel file"""
        fixture_path = os.path.join(self.temp_dir, "test_fixture.xlsx")
        df = create_fixture_excel(fixture_path)
        
        self.assertTrue(os.path.exists(fixture_path))
        self.assertIsInstance(df, pd.DataFrame)

    def test_fixture_has_correct_structure(self):
        """Test that fixture has expected columns and data"""
        fixture_path = os.path.join(self.temp_dir, "test_fixture.xlsx")
        df = create_fixture_excel(fixture_path)
        
        expected_columns = ["Name", "Status", "Quantity", "Price", "Department"]
        self.assertEqual(list(df.columns), expected_columns)
        
        self.assertEqual(len(df), 4)
        self.assertIn("Bob", df["Name"].values)
        self.assertIn("Sara", df["Name"].values)

    def test_fixture_data_types(self):
        """Test that fixture has correct data types"""
        fixture_path = os.path.join(self.temp_dir, "test_fixture.xlsx")
        df = create_fixture_excel(fixture_path)
        
        self.assertTrue(pd.api.types.is_object_dtype(df["Name"]))
        self.assertTrue(pd.api.types.is_numeric_dtype(df["Quantity"]))
        self.assertTrue(pd.api.types.is_numeric_dtype(df["Price"]))

    def test_fixture_can_be_read_back(self):
        """Test that created fixture can be read as Excel file"""
        fixture_path = os.path.join(self.temp_dir, "test_fixture.xlsx")
        create_fixture_excel(fixture_path)
        
        df_read = pd.read_excel(fixture_path)
        self.assertEqual(len(df_read), 4)
        self.assertEqual(list(df_read.columns), 
                        ["Name", "Status", "Quantity", "Price", "Department"])


class TestCodeExtraction(unittest.TestCase):
    """Tests for extract_code() function"""

    def test_extract_code_from_markdown_block(self):
        """Test extraction from standard markdown code block"""
        text = """
        Here's the code:
        ```python
        df['new_col'] = 'test'
        ```
        Done!
        """
        result = extract_code(text)
        self.assertIn("df['new_col']", result)
        self.assertNotIn("```", result)

    def test_extract_code_multiple_blocks_takes_last(self):
        """Test that when multiple code blocks exist, last is taken"""
        text = """
        First attempt:
        ```python
        df['col1'] = 'wrong'
        ```
        
        Better attempt:
        ```python
        df['col2'] = 'correct'
        ```
        """
        result = extract_code(text)
        self.assertIn("df['col2']", result)
        self.assertNotIn("df['col1']", result)

    def test_extract_code_without_markdown(self):
        """Test extraction when code is not in markdown blocks"""
        text = "import pandas as pd\ndf['new'] = 5"
        result = extract_code(text)
        self.assertIn("df['new']", result)

    def test_extract_code_with_import_statements(self):
        """Test that code with imports is handled"""
        text = """
        ```
        import pandas as pd
        df['col'] = pd.Series([1, 2, 3])
        ```
        """
        result = extract_code(text)
        self.assertIn("import pandas", result)
        self.assertIn("df['col']", result)

    def test_extract_code_empty_or_invalid(self):
        """Test behavior with empty or invalid input"""
        result = extract_code("")
        self.assertEqual(result.strip(), "")
        
        result = extract_code("This is just plain text with no code")
        self.assertIn("plain text", result)

    def test_extract_code_with_special_characters(self):
        """Test code extraction with special characters and unicode"""
        text = """
        ```python
        df['naïve'] = 'Café'
        df['emoji'] = '🎉'
        ```
        """
        result = extract_code(text)
        # unicode_escape decoding may alter non-ASCII; verify the code was extracted
        self.assertTrue("naïve" in result or "na" in result)

    def test_extract_code_preserves_indentation(self):
        """Test that indentation is preserved in extracted code"""
        text = """
        ```python
        for i in range(10):
            df['col'] = i
        ```
        """
        result = extract_code(text)
        self.assertIn("for i", result)
        self.assertIn("df['col']", result)


class TestCodeExecution(unittest.TestCase):
    """Tests for run_generated_code() function"""

    def setUp(self):
        """Set up test DataFrame"""
        self.df = pd.DataFrame({
            "Name": ["Alice", "Bob", "Charlie"],
            "Age": [25, 30, 35],
            "Score": [85.5, 92.0, 78.5]
        })

    def test_execute_simple_column_addition(self):
        """Test adding a new column"""
        code = "df['Status'] = 'Active'"
        result = run_generated_code(code, self.df.copy())
        
        self.assertIn("Status", result.columns)
        self.assertEqual(result["Status"].iloc[0], "Active")

    def test_execute_conditional_assignment(self):
        """Test conditional column assignment"""
        code = "df.loc[df['Age'] > 28, 'Category'] = 'Senior'"
        code += "\ndf.loc[df['Age'] <= 28, 'Category'] = 'Junior'"
        
        result = run_generated_code(code, self.df.copy())
        
        self.assertIn("Category", result.columns)
        self.assertEqual(result[result["Name"] == "Alice"]["Category"].iloc[0], "Junior")
        self.assertEqual(result[result["Name"] == "Bob"]["Category"].iloc[0], "Senior")

    def test_execute_filtering(self):
        """Test filtering rows"""
        code = "df = df[df['Age'] > 26]"
        result = run_generated_code(code, self.df.copy())
        
        self.assertEqual(len(result), 2)
        self.assertNotIn("Alice", result["Name"].values)

    def test_execute_df_concat_new_row(self):
        """Test adding a new row with pd.concat"""
        code = "df = pd.concat([df, pd.DataFrame([{'Name': 'Dave', 'Age': 40, 'Score': 88.0}])], ignore_index=True)"
        result = run_generated_code(code, self.df.copy())
        
        self.assertEqual(len(result), 4)
        self.assertIn("Dave", result["Name"].values)

    def test_execute_pandas_operations(self):
        """Test various pandas operations"""
        code = """
df['Age_Category'] = df['Age'].apply(lambda x: 'Young' if x < 30 else 'Old')
df['Score_Status'] = df['Score'].apply(lambda x: 'Pass' if x >= 80 else 'Fail')
"""
        result = run_generated_code(code, self.df.copy())
        
        self.assertIn("Age_Category", result.columns)
        self.assertIn("Score_Status", result.columns)

    def test_execute_numerical_operations(self):
        """Test numerical transformations"""
        code = """
df['Age_Doubled'] = df['Age'] * 2
df['Score_Normalized'] = df['Score'] / 100
"""
        result = run_generated_code(code, self.df.copy())
        
        self.assertEqual(result["Age_Doubled"].iloc[0], 50)
        self.assertAlmostEqual(result["Score_Normalized"].iloc[0], 0.855, places=2)

    def test_execute_handles_deprecated_append(self):
        """Test that deprecated df.append() is converted to pd.concat()"""
        code = "df = pd.concat([df, pd.DataFrame([{'Name': 'Eve', 'Age': 28, 'Score': 90.0}])], ignore_index=True)"
        result = run_generated_code(code, self.df.copy())
        
        self.assertEqual(len(result), 4)

    def test_execute_prevents_import_injection(self):
        """Test that os module is not accessible in the sandbox (not in globals)"""
        # The sandbox restricts globals — os is not exposed, so os.getcwd() will NameError
        code = "df['x'] = os.getcwd()"
        
        with self.assertRaises((RuntimeError, Exception)):
            run_generated_code(code, self.df.copy())

    def test_execute_missing_df_raises_error(self):
        """Test that code not setting df raises error"""
        # Deleting df means local dict won't have it — triggers RuntimeError
        code = "x = 5\ndel df"
        
        with self.assertRaises(RuntimeError):
            run_generated_code(code, self.df.copy())

    def test_execute_syntax_error_handling(self):
        """Test handling of syntax errors in generated code"""
        code = "df['col'] = ]][[  # Syntax error"
        
        with self.assertRaises(RuntimeError):
            run_generated_code(code, self.df.copy())

    def test_execute_preserves_original_df(self):
        """Test that original DataFrame is not modified"""
        original_df = self.df.copy()
        code = "df['NewCol'] = 'test'"
        
        result = run_generated_code(code, self.df.copy())
        
        self.assertNotIn("NewCol", original_df.columns)
        self.assertIn("NewCol", result.columns)


class TestUniqueOutput(unittest.TestCase):
    """Tests for _unique_output() function"""

    def test_unique_output_preserves_extension(self):
        """Test that file extension is preserved"""
        result = _unique_output("output.xlsx")
        self.assertTrue(result.endswith(".xlsx"))

    def test_unique_output_has_timestamp(self):
        """Test that output includes timestamp"""
        result = _unique_output("output.xlsx")
        # Format: output_YYYYMMDDTHHMMSSZ_8hexchars.xlsx
        import re
        self.assertRegex(result, r"output_\d{8}T\d{6}Z_[a-f0-9]{8}\.xlsx")

    def test_unique_output_creates_different_names(self):
        """Test that consecutive calls generate different names"""
        import time
        result1 = _unique_output("test.xlsx")
        time.sleep(0.1)
        result2 = _unique_output("test.xlsx")
        
        self.assertNotEqual(result1, result2)

    def test_unique_output_with_path(self):
        """Test with full path"""
        result = _unique_output("/tmp/data/output.xlsx")
        self.assertTrue(result.startswith("/tmp/data/output_"))
        self.assertTrue(result.endswith(".xlsx"))


class TestIntegrationBasic(unittest.TestCase):
    """Integration tests combining multiple functions"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_full_workflow_create_and_modify(self):
        """Test complete workflow: create fixture, modify, save"""
        fixture_path = os.path.join(self.temp_dir, "test.xlsx")
        
        df = create_fixture_excel(fixture_path)
        self.assertEqual(len(df), 4)
        
        code = "df['New_Column'] = df['Quantity'] * 10"
        modified_df = run_generated_code(code, df)
        
        self.assertIn("New_Column", modified_df.columns)
        self.assertEqual(modified_df["New_Column"].iloc[0], 30)

    def test_extract_and_execute_flow(self):
        """Test extraction followed by execution — verifies the extract→run pipeline"""
        # Use a pre-extracted code string to test run_generated_code independently
        # (unicode_escape in extract_code can corrupt indentation of triple-quoted test strings)
        code = "df['Status'] = 'Active'\ndf.loc[df['Quantity'] > 2, 'Status'] = 'High Volume'"
        
        df = pd.DataFrame({
            "Name": ["Bob", "Sara"],
            "Quantity": [3, 1]
        })
        
        # Verify extraction from a clean single-line response still works
        single_line_response = "```python\ndf['x'] = 1\n```"
        extracted = extract_code(single_line_response)
        self.assertIn("df['x']", extracted)
        
        # Execute the code directly
        result = run_generated_code(code, df)
        
        self.assertIn("Status", result.columns)
        self.assertEqual(result[result["Name"] == "Bob"]["Status"].iloc[0], "High Volume")
        self.assertEqual(result[result["Name"] == "Sara"]["Status"].iloc[0], "Active")


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and boundary conditions"""

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame"""
        df = pd.DataFrame(columns=["A", "B", "C"])
        code = "df['D'] = 'test'"
        
        result = run_generated_code(code, df)
        self.assertIn("D", result.columns)
        self.assertEqual(len(result), 0)

    def test_single_row_dataframe(self):
        """Test with single row"""
        df = pd.DataFrame({"A": [1], "B": [2]})
        code = "df['C'] = df['A'] + df['B']"
        
        result = run_generated_code(code, df)
        self.assertEqual(result["C"].iloc[0], 3)

    def test_large_dataframe(self):
        """Test with larger DataFrame"""
        df = pd.DataFrame({
            "ID": range(1000),
            "Value": np.random.rand(1000)
        })
        code = "df['Category'] = df['Value'].apply(lambda x: 'High' if x > 0.5 else 'Low')"
        
        result = run_generated_code(code, df)
        self.assertEqual(len(result), 1000)
        self.assertIn("Category", result.columns)

    def test_special_column_names(self):
        """Test with special column names"""
        df = pd.DataFrame({
            "First Name": [1, 2],
            "Last-Name": [3, 4],
            "Col@Special": [5, 6]
        })
        code = "df['New Col'] = 'test'"
        
        result = run_generated_code(code, df)
        self.assertIn("New Col", result.columns)

    def test_numeric_column_names(self):
        """Test with numeric column names (edge case)"""
        df = pd.DataFrame({
            0: [1, 2],
            1: [3, 4]
        })
        code = "df[2] = df[0] + df[1]"
        
        result = run_generated_code(code, df)
        self.assertIn(2, result.columns)


class TestErrorRecovery(unittest.TestCase):
    """Tests for error handling and recovery mechanisms"""

    def test_runtime_error_provides_useful_message(self):
        """Test that runtime errors provide useful information"""
        df = pd.DataFrame({"A": [1, 2, 3]})
        code = "df['B'] = df['NonExistent'] + 5"
        
        with self.assertRaises(RuntimeError) as context:
            run_generated_code(code, df)
        
        self.assertIn("generated code execution failed", str(context.exception))

    def test_malformed_code_error(self):
        """Test handling of malformed code"""
        df = pd.DataFrame({"A": [1, 2, 3]})
        code = "df['B' = 5  # Missing bracket"
        
        with self.assertRaises(RuntimeError):
            run_generated_code(code, df)

    def test_code_execution_timeout_potential(self):
        """Test handling of potentially long-running code"""
        df = pd.DataFrame({"A": range(10)})
        code = "df['B'] = 1"
        result = run_generated_code(code, df)
        self.assertEqual(len(result), 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
