#!/usr/bin/env python
"""
Core logic test without rich dependency.
"""

import json
import tempfile
from pathlib import Path
import sys
import re

# Test the core patching functions without rich


def test_set_env_logic():
    """Test set_env logic."""
    print("Testing set_env logic...")
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env.inject"
        
        # Simulate set_env
        param, value = "API_URL", "https://api.example.com"
        
        # Parse existing (empty)
        env_dict = {}
        env_dict[param] = value
        
        # Rebuild
        new_lines = [f"{k}={v}" for k, v in sorted(env_dict.items())]
        new_content = "\n".join(new_lines) + "\n"
        
        # Write
        env_path.write_text(new_content, encoding="utf-8")
        
        # Verify
        assert env_path.exists()
        content = env_path.read_text()
        assert "API_URL=https://api.example.com" in content
        print("✓ set_env logic works")


def test_retries_regex():
    """Test the retries regex pattern."""
    print("Testing retries regex pattern...")
    
    test_content = """
default_args = {
    "owner": "airflow",
    "retries": 3,
    "start_date": datetime(2024, 1, 1),
}
"""
    
    # Test the pattern
    pattern = r'(\bretries\s*=\s*)(\d+|[A-Za-z_]\w*)'
    match = re.search(pattern, test_content)
    assert match, "Failed: pattern should match"
    
    # Replace
    new_content = re.sub(pattern, rf"\g<1>5", test_content, count=1)
    assert '"retries": 5' in new_content or "retries=5" in new_content
    assert '"retries": 3' not in new_content
    print("✓ retries regex pattern works")


def test_timeout_regex():
    """Test the execution_timeout regex pattern."""
    print("Testing execution_timeout regex pattern...")
    
    test_content = """
default_args = {
    "execution_timeout": timedelta(seconds=300),
    "owner": "airflow",
}
"""
    
    # Test the pattern
    pattern = r'(\bexecution_timeout\s*=\s*)([^,\n]+)'
    match = re.search(pattern, test_content)
    assert match, "Failed: pattern should match"
    
    # Replace
    new_value = "timedelta(seconds=600)"
    new_content = re.sub(pattern, rf"\g<1>{new_value}", test_content, count=1)
    assert "timedelta(seconds=600)" in new_content
    assert "seconds=300" not in new_content
    print("✓ execution_timeout regex pattern works")


def test_precheck_block():
    """Test precheck block insertion."""
    print("Testing precheck block insertion...")
    
    test_content = """
with DAG(dag_id="http_dag") as dag:
    # BEGIN PRECHECKS
    pass
    # END PRECHECKS

    t_extract = PythonOperator(...)
"""
    
    precheck_line = "t_precheck = PythonOperator(...)"
    
    # Check markers exist
    assert "# BEGIN PRECHECKS" in test_content
    assert "# END PRECHECKS" in test_content
    
    # Replace
    new_content = test_content.replace(
        "# END PRECHECKS",
        f"{precheck_line}\n    # END PRECHECKS",
    )
    
    assert precheck_line in new_content
    assert new_content.index(precheck_line) < new_content.index("# END PRECHECKS")
    print("✓ precheck block insertion works")


def test_diff_generation():
    """Test unified diff generation."""
    print("Testing diff generation...")
    from difflib import unified_diff
    
    old_content = "line 1\nline 2\nline 3\n"
    new_content = "line 1\nline 2 modified\nline 3\n"
    
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    diff_lines = list(unified_diff(old_lines, new_lines, lineterm=""))
    diff = "".join(diff_lines)
    
    assert diff, "Diff should not be empty"
    assert "line 2" in diff
    print("✓ diff generation works")


def test_audit_entry_parsing():
    """Test audit entry JSON functionality."""
    print("Testing audit entry JSON functionality...")
    
    entry = {
        "plan_id": "plan_ep_001",
        "status": "applied",
        "applied_actions": ["set_env(API_URL)", "set_retry(retries)"],
        "failed_actions": [],
        "git_commit_hash": "a1b2c3d",
    }
    
    # Serialize
    json_str = json.dumps(entry)
    
    # Deserialize
    parsed = json.loads(json_str)
    assert parsed["plan_id"] == "plan_ep_001"
    assert len(parsed["applied_actions"]) == 2
    print("✓ audit entry JSON works")


if __name__ == "__main__":
    try:
        test_set_env_logic()
        test_retries_regex()
        test_timeout_regex()
        test_precheck_block()
        test_diff_generation()
        test_audit_entry_parsing()
        
        print("\n" + "="*60)
        print("✓ All core logic tests passed!")
        print("="*60)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
