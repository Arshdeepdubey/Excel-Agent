#!/usr/bin/env python3
"""
Test Suite Runner for Excel Agent

This script runs all unit tests, integration tests, and end-to-end tests
for the Excel Agent project and generates a comprehensive report.

Usage:
    python run_tests.py                  # Run all tests
    python run_tests.py --unit          # Run only unit tests
    python run_tests.py --integration   # Run only integration tests
    python run_tests.py --verbose       # Verbose output
    python run_tests.py --report        # Generate HTML report
"""

import unittest
import sys
import argparse
import os
from pathlib import Path
from io import StringIO

# Test modules (now in tests/ package)
from tests import test_agent
from tests import test_orchestrator
from tests import test_rag_workflow


def run_test_suite(verbosity=2, test_type="all"):
    """
    Run the test suite.
    
    Args:
        verbosity: Level of verbosity (0, 1, 2, etc.)
        test_type: Type of tests to run ('all', 'unit', 'integration', 'rag')
        
    Returns:
        TestResult object
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    if test_type in ["all", "unit"]:
        print("=" * 80)
        print("Loading Unit Tests (tests/test_agent.py)")
        print("=" * 80)
        suite.addTests(loader.loadTestsFromModule(test_agent))
    
    if test_type in ["all", "integration"]:
        print("\n" + "=" * 80)
        print("Loading Integration Tests (tests/test_orchestrator.py)")
        print("=" * 80)
        suite.addTests(loader.loadTestsFromModule(test_orchestrator))
    
    if test_type in ["all", "rag"]:
        print("\n" + "=" * 80)
        print("Loading RAG Workflow Tests (tests/test_rag_workflow.py)")
        print("=" * 80)
        suite.addTests(loader.loadTestsFromModule(test_rag_workflow))
    
    print("\n" + "=" * 80)
    print("RUNNING TESTS")
    print("=" * 80 + "\n")
    
    runner = unittest.TextTestRunner(verbosity=verbosity, stream=sys.stdout)
    result = runner.run(suite)
    
    return result


def print_summary(result):
    """Print test result summary"""
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Run:    {result.testsRun}")
    print(f"Passed:       {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed:       {len(result.failures)}")
    print(f"Errors:       {len(result.errors)}")
    print(f"Skipped:      {len(result.skipped)}")
    print("=" * 80)
    
    if result.failures:
        print("\nFailed Tests:")
        for test, traceback in result.failures:
            print(f"  ❌ {test}")
    
    if result.errors:
        print("\nTests with Errors:")
        for test, traceback in result.errors:
            print(f"  ⚠️  {test}")
    
    if result.skipped:
        print(f"\nSkipped Tests ({len(result.skipped)}):")
        for test, reason in result.skipped:
            print(f"  ⏭️  {test}")
            print(f"      Reason: {reason}")
    
    return result.wasSuccessful()


def generate_html_report(result):
    """Generate an HTML report of test results"""
    html_file = "test_report.html"
    
    with open(html_file, 'w') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Excel Agent - Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .header { background-color: #2c3e50; color: white; padding: 20px; border-radius: 5px; }
        .summary { background-color: white; padding: 20px; margin: 20px 0; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .summary-row { display: flex; justify-content: space-around; margin: 10px 0; }
        .summary-item { flex: 1; text-align: center; padding: 10px; border-radius: 5px; }
        .passed { background-color: #d4edda; color: #155724; }
        .failed { background-color: #f8d7da; color: #721c24; }
        .error { background-color: #fff3cd; color: #856404; }
        .skipped { background-color: #e2e3e5; color: #383d41; }
        .success { color: #28a745; font-weight: bold; }
        .failure { color: #dc3545; font-weight: bold; }
        h1, h2 { color: #2c3e50; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Excel Agent - Test Report</h1>
        <p>Comprehensive test results for Excel Agent project</p>
    </div>
    <div class="summary">
        <h2>Test Summary</h2>
        <div class="summary-row">
            <div class="summary-item"><strong>Total</strong><div style="font-size:24px">""")
        f.write(str(result.testsRun))
        f.write("""</div></div>
            <div class="summary-item passed"><strong>Passed</strong><div style="font-size:24px">""")
        f.write(str(result.testsRun - len(result.failures) - len(result.errors)))
        f.write("""</div></div>
            <div class="summary-item failed"><strong>Failed</strong><div style="font-size:24px">""")
        f.write(str(len(result.failures)))
        f.write("""</div></div>
            <div class="summary-item error"><strong>Errors</strong><div style="font-size:24px">""")
        f.write(str(len(result.errors)))
        f.write("""</div></div>
            <div class="summary-item skipped"><strong>Skipped</strong><div style="font-size:24px">""")
        f.write(str(len(result.skipped)))
        f.write("""</div></div>
        </div>
    </div>
    <div class="summary">
        <h2>Status</h2>
        <p>""")
        f.write("<span class='success'>✓ ALL TESTS PASSED</span>" if result.wasSuccessful() else "<span class='failure'>✗ SOME TESTS FAILED</span>")
        f.write("""</p>
    </div>
</body>
</html>
""")
    
    print(f"\n✓ HTML report generated: {html_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Excel Agent Test Suite Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all tests
  python run_tests.py --unit            # Run only unit tests  
  python run_tests.py --verbose         # Run with verbose output
  python run_tests.py --report          # Generate HTML report
  python run_tests.py --unit --verbose  # Unit tests with verbose output
        """
    )
    
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--rag", action="store_true", help="Run only RAG workflow tests")
    parser.add_argument("--verbose", action="store_true", help="Verbose test output")
    parser.add_argument("--report", action="store_true", help="Generate HTML test report")
    
    args = parser.parse_args()
    
    test_type = "all"
    if args.unit:
        test_type = "unit"
    elif args.integration:
        test_type = "integration"
    elif args.rag:
        test_type = "rag"
    
    verbosity = 2 if args.verbose else 1
    
    result = run_test_suite(verbosity=verbosity, test_type=test_type)
    success = print_summary(result)
    
    if args.report:
        generate_html_report(result)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
