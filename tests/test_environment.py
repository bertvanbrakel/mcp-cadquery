import subprocess
import sys
import os
import pytest

VENV_DIR = ".venv-cadquery"
PYTHON_EXE = os.path.join(VENV_DIR, "bin", "python") # Adjust for Windows if needed

import shutil
from unittest.mock import patch, call # Import necessary mocking tools
from pathlib import Path # Import Path
# Import the function to test and related items
# Need to adjust import path if server.py is not directly importable
# Assuming server.py is in the parent directory relative to tests/
# This might need adjustment based on actual project structure/PYTHONPATH
try:
    # This assumes server.py is in the root and tests/ is a subdir
    # If server.py is in src/, the import needs adjustment
    import server
    prepare_workspace_env = server.prepare_workspace_env
    _run_command_helper = server._run_command_helper
    workspace_reqs_mtime_cache = server.workspace_reqs_mtime_cache
except ImportError:
     # Fallback if the above structure is wrong - adjust as needed
     # This might happen if running pytest from the root directory
     sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
     import server
     prepare_workspace_env = server.prepare_workspace_env
     _run_command_helper = server._run_command_helper
     workspace_reqs_mtime_cache = server.workspace_reqs_mtime_cache


# Note: Environment setup is now handled by prepare_workspace_env per workspace.
# These tests focus on that function.
def test_cadquery_import():
    """Test if cadquery can be imported within the virtual environment."""
    assert os.path.isfile(PYTHON_EXE), f"Python executable '{PYTHON_EXE}' does not exist. Setup failed?"

    command = [PYTHON_EXE, "-c", "import cadquery; print(cadquery.__version__)"]
    print(f"\nRunning test command: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            check=True, # Fail if import fails
            capture_output=True,
            text=True,
            timeout=30
        )
        print(f"Import test stdout: {result.stdout.strip()}")
        if result.stderr:
             print(f"Import test stderr: {result.stderr.strip()}")
        assert result.returncode == 0 # Check if import succeeded
        print("cadquery imported successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Import test stdout: {e.stdout}")
        print(f"Import test stderr: {e.stderr}")
        pytest.fail(f"Importing cadquery failed with exit code {e.returncode}: {e.stderr}")
    except subprocess.TimeoutExpired:
        pytest.fail("Import test timed out.")
    except FileNotFoundError:
         pytest.fail(f"Could not run python executable at '{PYTHON_EXE}'. Check venv setup.")


# --- Tests for prepare_workspace_env ---

@patch('server._run_command_helper') # Mock the helper that runs uv
@patch('shutil.which') # Mock the check for uv command
def test_prepare_workspace_env_creation(mock_which, mock_run_helper, tmp_path):
    """Test creating a new workspace environment."""
    mock_which.return_value = "/path/to/uv" # Simulate uv command exists
    workspace_path = tmp_path / "new_workspace"
    # Don't create workspace_path here, the function should do it implicitly via uv

    # Define expected paths
    venv_dir = workspace_path / ".venv"
    bin_subdir = "Scripts" if sys.platform == "win32" else "bin"
    expected_python_exe = venv_dir / bin_subdir / ("python.exe" if sys.platform == "win32" else "python")

    # Simulate _run_command_helper success and create the dummy exe on the venv call
    def side_effect_run_helper(*args, **kwargs):
        cmd = args[0]
        print(f"Mock _run_command_helper called with: {cmd}") # Debug print
        # If it's the venv creation command, create the dummy structure
        if cmd[0] == "uv" and cmd[1] == "venv":
            venv_path_in_cmd = cmd[2]
            # Use Path object for consistency
            exe_path = Path(venv_path_in_cmd) / bin_subdir / ("python.exe" if sys.platform == "win32" else "python")
            exe_path.parent.mkdir(parents=True, exist_ok=True)
            exe_path.touch()
            print(f"Simulated venv creation, touched: {exe_path}")
            # Return a dummy CompletedProcess for success
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="venv created", stderr="")
        elif cmd[0] == "uv" and cmd[1] == "pip" and "cadquery" in cmd:
             # Return dummy success for cadquery install
             return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="cadquery installed", stderr="")
        # Raise error for unexpected calls
        raise ValueError(f"Unexpected call to mock_run_helper: {cmd}")

    mock_run_helper.side_effect = side_effect_run_helper

    # Clear cache for this path if it exists from previous failed runs
    if str(workspace_path) in workspace_reqs_mtime_cache:
        del workspace_reqs_mtime_cache[str(workspace_path)]

    workspace_path.mkdir(parents=True, exist_ok=True) # Create the dir before calling
    # --- Action ---
    returned_python_exe = prepare_workspace_env(str(workspace_path))

    # --- Assertions ---
    assert returned_python_exe == str(expected_python_exe)
    assert os.path.isdir(venv_dir) # Check venv dir exists (implicitly created by mock side effect)
    assert os.path.isfile(expected_python_exe) # Check python exe exists (created by mock side effect)

    # Check that uv was checked
    mock_which.assert_called_once_with("uv")

    # Check that _run_command_helper was called for venv creation and cadquery install
    expected_venv_call = call(["uv", "venv", str(venv_dir), "-p", server.PYTHON_VERSION], log_prefix=f"WorkspaceEnv({workspace_path.name})")
    expected_cq_install_call = call(["uv", "pip", "install", "cadquery", "--python", str(expected_python_exe)], log_prefix=f"WorkspaceEnv({workspace_path.name})")

    # Check calls - order might vary slightly depending on implementation details, focus on presence
    mock_run_helper.assert_has_calls([expected_venv_call, expected_cq_install_call], any_order=False) # Ensure venv before install
    assert mock_run_helper.call_count == 2 # Ensure no extra calls (like requirements install)

    # Ensure requirements install wasn't attempted
    for mock_call in mock_run_helper.call_args_list:
        assert "-r" not in mock_call.args[0], "Requirements install should not have been called"

    # Ensure cache wasn't touched for requirements
    assert str(workspace_path) not in workspace_reqs_mtime_cache

    print(f"\nTest test_prepare_workspace_env_creation passed for {workspace_path}")


@patch('server._run_command_helper')
@patch('shutil.which')
def test_prepare_workspace_env_existing_venv(mock_which, mock_run_helper, tmp_path):
    """Test prepare_workspace_env when the venv directory already exists."""
    mock_which.return_value = "/path/to/uv" # Simulate uv command exists
    workspace_path = tmp_path / "existing_workspace"
    workspace_path.mkdir() # Create the workspace dir

    # Define expected paths and create dummy venv structure
    venv_dir = workspace_path / ".venv"
    bin_subdir = "Scripts" if sys.platform == "win32" else "bin"
    expected_python_exe = venv_dir / bin_subdir / ("python.exe" if sys.platform == "win32" else "python")
    expected_python_exe.parent.mkdir(parents=True, exist_ok=True)
    expected_python_exe.touch() # Create dummy python executable
    print(f"Created dummy existing venv structure at: {venv_dir}")

    # Simulate _run_command_helper success ONLY for cadquery install
    def side_effect_run_helper(*args, **kwargs):
        cmd = args[0]
        print(f"Mock _run_command_helper called with: {cmd}") # Debug print
        if cmd[0] == "uv" and cmd[1] == "pip" and "cadquery" in cmd:
             # Return dummy success for cadquery install
             return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="cadquery installed", stderr="")
        # Any other call (like uv venv) is unexpected
        raise ValueError(f"Unexpected call to mock_run_helper in existing venv test: {cmd}")

    mock_run_helper.side_effect = side_effect_run_helper

    # Clear cache just in case
    if str(workspace_path) in workspace_reqs_mtime_cache:
        del workspace_reqs_mtime_cache[str(workspace_path)]

    # --- Action ---
    returned_python_exe = prepare_workspace_env(str(workspace_path))

    # --- Assertions ---
    assert returned_python_exe == str(expected_python_exe)
    mock_which.assert_called_once_with("uv")

    # Check that only the cadquery install command was run
    expected_cq_install_call = call(["uv", "pip", "install", "cadquery", "--python", str(expected_python_exe)], log_prefix=f"WorkspaceEnv({workspace_path.name})")
    mock_run_helper.assert_called_once_with(*expected_cq_install_call.args, **expected_cq_install_call.kwargs)

    # Ensure venv creation wasn't called
    for mock_call in mock_run_helper.call_args_list:
        assert "venv" not in mock_call.args[0], "'uv venv' should not have been called"

    # Ensure requirements install wasn't attempted
    for mock_call in mock_run_helper.call_args_list:
        assert "-r" not in mock_call.args[0], "Requirements install should not have been called"

    print(f"\nTest test_prepare_workspace_env_existing_venv passed for {workspace_path}")



@patch('server._run_command_helper')
@patch('shutil.which')
def test_prepare_workspace_env_with_requirements(mock_which, mock_run_helper, tmp_path):
    """Test creating env and installing dependencies from requirements.txt."""
    mock_which.return_value = "/path/to/uv"
    workspace_path = tmp_path / "reqs_workspace"
    workspace_path.mkdir()
    requirements_file = workspace_path / "requirements.txt"
    requirements_file.write_text("numpy\npandas")
    reqs_mtime = requirements_file.stat().st_mtime

    # Define expected paths
    venv_dir = workspace_path / ".venv"
    bin_subdir = "Scripts" if sys.platform == "win32" else "bin"
    expected_python_exe = venv_dir / bin_subdir / ("python.exe" if sys.platform == "win32" else "python")

    # Simulate _run_command_helper success for all steps
    def side_effect_run_helper(*args, **kwargs):
        cmd = args[0]
        print(f"Mock _run_command_helper called with: {cmd}")
        if cmd[0] == "uv" and cmd[1] == "venv":
            exe_path = Path(cmd[2]) / bin_subdir / ("python.exe" if sys.platform == "win32" else "python")
            exe_path.parent.mkdir(parents=True, exist_ok=True)
            exe_path.touch()
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="venv created", stderr="")
        elif cmd[0] == "uv" and cmd[1] == "pip" and "cadquery" in cmd:
             return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="cadquery installed", stderr="")
        elif cmd[0] == "uv" and cmd[1] == "pip" and "-r" in cmd:
             # Check if the correct requirements file is being used
             assert cmd[cmd.index("-r") + 1] == str(requirements_file)
             return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="reqs installed", stderr="")
        raise ValueError(f"Unexpected call to mock_run_helper: {cmd}")

    mock_run_helper.side_effect = side_effect_run_helper

    # Clear cache
    if str(workspace_path) in workspace_reqs_mtime_cache:
        del workspace_reqs_mtime_cache[str(workspace_path)]

    # --- Action ---
    returned_python_exe = prepare_workspace_env(str(workspace_path))

    # --- Assertions ---
    assert returned_python_exe == str(expected_python_exe)
    mock_which.assert_called_once_with("uv")

    # Check calls
    expected_venv_call = call(["uv", "venv", str(venv_dir), "-p", server.PYTHON_VERSION], log_prefix=f"WorkspaceEnv({workspace_path.name})")
    expected_cq_install_call = call(["uv", "pip", "install", "cadquery", "--python", str(expected_python_exe)], log_prefix=f"WorkspaceEnv({workspace_path.name})")
    expected_reqs_install_call = call(["uv", "pip", "install", "-r", str(requirements_file), "--python", str(expected_python_exe)], log_prefix=f"WorkspaceEnv({workspace_path.name})")

    mock_run_helper.assert_has_calls([
        expected_venv_call,
        expected_cq_install_call,
        expected_reqs_install_call
    ], any_order=False) # Ensure correct order
    assert mock_run_helper.call_count == 3

    # Check mtime cache was updated
    assert str(workspace_path) in workspace_reqs_mtime_cache
    assert workspace_reqs_mtime_cache[str(workspace_path)] == reqs_mtime

    print(f"\nTest test_prepare_workspace_env_with_requirements passed for {workspace_path}")



@patch('server._run_command_helper')
@patch('shutil.which')
def test_prepare_workspace_env_requirements_unchanged(mock_which, mock_run_helper, tmp_path):
    """Test that requirements install is skipped if mtime hasn't changed."""
    mock_which.return_value = "/path/to/uv"
    workspace_path = tmp_path / "reqs_unchanged_workspace"
    workspace_path.mkdir()
    requirements_file = workspace_path / "requirements.txt"
    requirements_file.write_text("numpy\npandas")
    reqs_mtime = requirements_file.stat().st_mtime

    # Define expected paths and create dummy venv structure
    venv_dir = workspace_path / ".venv"
    bin_subdir = "Scripts" if sys.platform == "win32" else "bin"
    expected_python_exe = venv_dir / bin_subdir / ("python.exe" if sys.platform == "win32" else "python")
    expected_python_exe.parent.mkdir(parents=True, exist_ok=True)
    expected_python_exe.touch()

    # Simulate _run_command_helper success ONLY for cadquery install
    def side_effect_run_helper(*args, **kwargs):
        cmd = args[0]
        print(f"Mock _run_command_helper called with: {cmd}")
        if cmd[0] == "uv" and cmd[1] == "pip" and "cadquery" in cmd:
             return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="cadquery installed", stderr="")
        # Requirements install should NOT be called
        if "-r" in cmd:
             raise ValueError("Requirements install should have been skipped!")
        # Venv creation should also be skipped
        if "venv" in cmd:
             raise ValueError("Venv creation should have been skipped!")
        raise ValueError(f"Unexpected call to mock_run_helper: {cmd}")

    mock_run_helper.side_effect = side_effect_run_helper

    # --- Setup Cache --- 
    # Pre-populate the cache with the current mtime
    workspace_reqs_mtime_cache.clear() # Ensure clean cache for test
    workspace_reqs_mtime_cache[str(workspace_path)] = reqs_mtime
    print(f"Pre-populated cache for {workspace_path} with mtime {reqs_mtime}")

    # --- Action --- 
    returned_python_exe = prepare_workspace_env(str(workspace_path))

    # --- Assertions --- 
    assert returned_python_exe == str(expected_python_exe)
    mock_which.assert_called_once_with("uv")

    # Check that only the cadquery install command was run
    expected_cq_install_call = call(["uv", "pip", "install", "cadquery", "--python", str(expected_python_exe)], log_prefix=f"WorkspaceEnv({workspace_path.name})")
    mock_run_helper.assert_called_once_with(*expected_cq_install_call.args, **expected_cq_install_call.kwargs)

    # Ensure cache value hasn't changed
    assert workspace_reqs_mtime_cache[str(workspace_path)] == reqs_mtime

    print(f"\nTest test_prepare_workspace_env_requirements_unchanged passed for {workspace_path}")



@patch('server._run_command_helper')
@patch('shutil.which')
def test_prepare_workspace_env_requirements_changed(mock_which, mock_run_helper, tmp_path):
    """Test that requirements install is triggered if mtime has changed."""
    mock_which.return_value = "/path/to/uv"
    workspace_path = tmp_path / "reqs_changed_workspace"
    workspace_path.mkdir()
    requirements_file = workspace_path / "requirements.txt"
    requirements_file.write_text("numpy\npandas") # Initial content
    initial_mtime = requirements_file.stat().st_mtime

    # Define expected paths and create dummy venv structure
    venv_dir = workspace_path / ".venv"
    bin_subdir = "Scripts" if sys.platform == "win32" else "bin"
    expected_python_exe = venv_dir / bin_subdir / ("python.exe" if sys.platform == "win32" else "python")
    expected_python_exe.parent.mkdir(parents=True, exist_ok=True)
    expected_python_exe.touch()

    # Simulate _run_command_helper success for all steps
    def side_effect_run_helper(*args, **kwargs):
        cmd = args[0]
        print(f"Mock _run_command_helper called with: {cmd}")
        if cmd[0] == "uv" and cmd[1] == "pip" and "cadquery" in cmd:
             return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="cadquery installed", stderr="")
        elif cmd[0] == "uv" and cmd[1] == "pip" and "-r" in cmd:
             assert cmd[cmd.index("-r") + 1] == str(requirements_file)
             return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="reqs installed", stderr="")
        # Venv creation should be skipped
        if "venv" in cmd:
             raise ValueError("Venv creation should have been skipped!")
        raise ValueError(f"Unexpected call to mock_run_helper: {cmd}")

    mock_run_helper.side_effect = side_effect_run_helper

    # --- Setup Cache with OLD mtime --- 
    workspace_reqs_mtime_cache.clear()
    old_mtime = initial_mtime - 10 # Simulate an older timestamp in cache
    workspace_reqs_mtime_cache[str(workspace_path)] = old_mtime
    print(f"Pre-populated cache for {workspace_path} with OLD mtime {old_mtime}")

    # --- Action --- 
    returned_python_exe = prepare_workspace_env(str(workspace_path))

    # --- Assertions --- 
    assert returned_python_exe == str(expected_python_exe)
    mock_which.assert_called_once_with("uv")

    # Check that cadquery install AND requirements install were called
    expected_cq_install_call = call(["uv", "pip", "install", "cadquery", "--python", str(expected_python_exe)], log_prefix=f"WorkspaceEnv({workspace_path.name})")
    expected_reqs_install_call = call(["uv", "pip", "install", "-r", str(requirements_file), "--python", str(expected_python_exe)], log_prefix=f"WorkspaceEnv({workspace_path.name})")

    mock_run_helper.assert_has_calls([
        expected_cq_install_call,
        expected_reqs_install_call
    ], any_order=False) # Ensure correct order
    assert mock_run_helper.call_count == 2

    # Check mtime cache was updated to the NEW mtime
    current_mtime = requirements_file.stat().st_mtime # Get the actual current mtime
    assert str(workspace_path) in workspace_reqs_mtime_cache
    assert workspace_reqs_mtime_cache[str(workspace_path)] == current_mtime
    assert current_mtime != old_mtime # Verify it actually updated

    print(f"\nTest test_prepare_workspace_env_requirements_changed passed for {workspace_path}")



@patch('server._run_command_helper')
@patch('shutil.which')
def test_prepare_workspace_env_install_failure(mock_which, mock_run_helper, tmp_path):
    """Test that RuntimeError is raised if requirements install fails."""
    mock_which.return_value = "/path/to/uv"
    workspace_path = tmp_path / "reqs_fail_workspace"
    workspace_path.mkdir()
    requirements_file = workspace_path / "requirements.txt"
    requirements_file.write_text("invalid-package-!@#$") # Content likely to fail
    reqs_mtime = requirements_file.stat().st_mtime

    # Define expected paths
    venv_dir = workspace_path / ".venv"
    bin_subdir = "Scripts" if sys.platform == "win32" else "bin"
    expected_python_exe = venv_dir / bin_subdir / ("python.exe" if sys.platform == "win32" else "python")

    # Simulate failure on the requirements install step
    install_error = subprocess.CalledProcessError(1, cmd=['uv', 'pip', 'install', '-r', str(requirements_file)], stderr="Install failed!")
    def side_effect_run_helper(*args, **kwargs):
        cmd = args[0]
        print(f"Mock _run_command_helper called with: {cmd}")
        if cmd[0] == "uv" and cmd[1] == "venv":
            exe_path = Path(cmd[2]) / bin_subdir / ("python.exe" if sys.platform == "win32" else "python")
            exe_path.parent.mkdir(parents=True, exist_ok=True)
            exe_path.touch()
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="venv created", stderr="")
        elif cmd[0] == "uv" and cmd[1] == "pip" and "cadquery" in cmd:
             return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="cadquery installed", stderr="")
        elif cmd[0] == "uv" and cmd[1] == "pip" and "-r" in cmd:
             print("Simulating requirements install failure...")
             raise install_error # Simulate failure
        raise ValueError(f"Unexpected call to mock_run_helper: {cmd}")

    mock_run_helper.side_effect = side_effect_run_helper

    # Clear cache
    if str(workspace_path) in workspace_reqs_mtime_cache:
        del workspace_reqs_mtime_cache[str(workspace_path)]

    # --- Action & Assertion --- 
    with pytest.raises(RuntimeError) as excinfo:
        prepare_workspace_env(str(workspace_path))
    
    assert f"Failed to install dependencies from {requirements_file}" in str(excinfo.value)
    print(f"Caught expected RuntimeError: {excinfo.value}")

    # Check that the cache was NOT populated for this failed attempt
    assert str(workspace_path) not in workspace_reqs_mtime_cache

    # Verify calls up to the point of failure
    expected_venv_call = call(["uv", "venv", str(venv_dir), "-p", server.PYTHON_VERSION], log_prefix=f"WorkspaceEnv({workspace_path.name})")
    expected_cq_install_call = call(["uv", "pip", "install", "cadquery", "--python", str(expected_python_exe)], log_prefix=f"WorkspaceEnv({workspace_path.name})")
    expected_reqs_install_call = call(["uv", "pip", "install", "-r", str(requirements_file), "--python", str(expected_python_exe)], log_prefix=f"WorkspaceEnv({workspace_path.name})")
    mock_run_helper.assert_has_calls([
        expected_venv_call,
        expected_cq_install_call,
        expected_reqs_install_call
    ], any_order=False)
    assert mock_run_helper.call_count == 3

    print(f"\nTest test_prepare_workspace_env_install_failure passed for {workspace_path}")



@patch('shutil.which') # Only need to mock which
def test_prepare_workspace_env_uv_not_found(mock_which, tmp_path):
    """Test that FileNotFoundError is raised if uv command is not found."""
    mock_which.return_value = None # Simulate uv not found
    workspace_path = tmp_path / "no_uv_workspace"
    workspace_path.mkdir()

    # --- Action & Assertion --- 
    with pytest.raises(FileNotFoundError) as excinfo:
        prepare_workspace_env(str(workspace_path))
    
    assert "'uv' is not installed or not in PATH" in str(excinfo.value)
    print(f"Caught expected FileNotFoundError: {excinfo.value}")

    # Verify shutil.which was called
    mock_which.assert_called_once_with("uv")

    print(f"\nTest test_prepare_workspace_env_uv_not_found passed for {workspace_path}")
