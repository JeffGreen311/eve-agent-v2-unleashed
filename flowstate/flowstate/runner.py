"""Workflow execution engine for FlowState."""

import os
import sys
import importlib.util
import tempfile
import subprocess
from typing import Dict, Any, Optional
import json


class WorkflowRunner:
    """Executes generated workflow code."""
    
    def __init__(self, output_dir: str = None):
        self.temp_dir = tempfile.mkdtemp(prefix="flowstate_")
        self._output_dir = output_dir  # cwd for subprocess; defaults to os.getcwd()
        
    def execute_workflow_code(self, code: str) -> Dict[str, Any]:
        """
        Execute the generated workflow code.
        
        Args:
            code (str): The Python code to execute
            
        Returns:
            Dict[str, Any]: Results from the workflow execution
        """
        # Write code to temporary file — explicit UTF-8 to avoid cp1252 issues on Windows
        script_path = os.path.join(self.temp_dir, "workflow.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        try:
            # Run in the user's working directory so relative output paths land there
            run_cwd = self._output_dir or os.getcwd()
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=run_cwd,
            )
            
            # Return execution results
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Workflow execution timed out",
                "return_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "return_code": -1
            }
            
    def execute_workflow_file(self, file_path: str) -> Dict[str, Any]:
        """
        Execute a workflow from a Python file.
        
        Args:
            file_path (str): Path to the Python workflow file
            
        Returns:
            Dict[str, Any]: Results from the workflow execution
        """
        if not os.path.exists(file_path):
            return {
                "success": False,
                "stdout": "",
                "stderr": f"File not found: {file_path}",
                "return_code": -1
            }
            
        try:
            # Execute the script in a subprocess
            result = subprocess.run(
                [sys.executable, file_path],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            # Return execution results
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Workflow execution timed out",
                "return_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "return_code": -1
            }
            
    def execute_workflow_in_memory(self, code: str) -> Dict[str, Any]:
        """
        Execute workflow code directly in memory (less safe).
        
        Args:
            code (str): The Python code to execute
            
        Returns:
            Dict[str, Any]: Results from the workflow execution
        """
        try:
            # Create a temporary module
            spec = importlib.util.spec_from_loader("workflow", loader=None)
            module = importlib.util.module_from_spec(spec)
            
            # Capture stdout/stderr
            import io
            from contextlib import redirect_stdout, redirect_stderr
            
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            
            # Execute code with captured output
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, module.__dict__)
                
                # If there's an execute_workflow function, call it
                if hasattr(module, 'execute_workflow'):
                    result = module.execute_workflow()
                else:
                    result = "Workflow executed, but no execute_workflow function found"
                    
            return {
                "success": True,
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
                "return_code": 0,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "return_code": -1
            }
            
    def save_workflow(self, code: str, file_path: str) -> bool:
        """
        Save the generated workflow code to a file.
        
        Args:
            code (str): The Python code to save
            file_path (str): Path where to save the file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write code to file — explicit UTF-8
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            return True
        except Exception as e:
            print(f"Error saving workflow: {e}")
            return False
            
    def cleanup(self):
        """Clean up temporary files."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"Error cleaning up: {e}")


def run_pytest_tests(test_code: str, test_file_path: str) -> Dict[str, Any]:
    """
    Run pytest tests for the workflow.
    
    Args:
        test_code (str): The test code to execute
        test_file_path (str): Path where to save the test file
        
    Returns:
        Dict[str, Any]: Test results
    """
    try:
        # Write test code to file
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(test_code)
            
        # Run pytest
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file_path, "-v"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Test execution timed out",
            "return_code": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Test execution error: {str(e)}",
            "return_code": -1
        }