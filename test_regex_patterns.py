#!/usr/bin/env python
"""Test regex patterns for DAG editing."""

import re

# Test 1: Standard retries in dict
test1 = '''default_args = {
    "owner": "airflow",
    "retries": 3,
}'''

# Pattern 1: Match quoted key with colon
pattern1 = r'("retries"\s*:\s*)(\d+)'
match1 = re.search(pattern1, test1)
print(f"Test 1 (quoted key with colon): {'✓' if match1 else '✗'}")
if match1:
    result1 = re.sub(pattern1, r'\g<1>5', test1)
    print(f"Result: {result1}\n")

# Test 2: Unquoted key with equals
test2 = '''default_args = {
    owner = "airflow",
    retries = 3,
}'''

pattern2 = r'(\bretries\s*=\s*)(\d+)'
match2 = re.search(pattern2, test2)
print(f"Test 2 (unquoted key with equals): {'✓' if match2 else '✗'}")
if match2:
    result2 = re.sub(pattern2, r'\g<1>5', test2)
    print(f"Result: {result2}\n")

# Test 3: Quoted key with equals (Airflow style)
test3 = '''default_args = {
    "owner": "airflow",
    "retries": 3,
}'''

# This should match both quoted and unquoted
pattern3 = r'(["\']?retries["\']?\s*[:=]\s*)(\d+)'
match3 = re.search(pattern3, test3)
print(f"Test 3 (flexible quoted): {'✓' if match3 else '✗'}")
if match3:
    result3 = re.sub(pattern3, r'\g<1>5', test3)
    print(f"Result: {result3}\n")

# Test 4: execution_timeout
test4 = '''default_args = {
    "execution_timeout": timedelta(seconds=300),
}'''

pattern4 = r'("execution_timeout"\s*:\s*)(timedelta\([^)]+\))'
match4 = re.search(pattern4, test4)
print(f"Test 4 (execution_timeout with timedelta): {'✓' if match4 else '✗'}")
if match4:
    result4 = re.sub(pattern4, r'\g<1>timedelta(seconds=600)', test4)
    print(f"Result: {result4}\n")
