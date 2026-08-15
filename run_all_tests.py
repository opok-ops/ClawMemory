"""
Master test runner - runs all 12 test scripts and aggregates results
"""
import subprocess
import sys
import os
import time

PYTHON = "/c/Users/SMDS/.venv-html-to-docx/Scripts/python.exe"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_SCRIPTS = [
    "test_01_core_init.py",
    "test_02_storage_engine.py",
    "test_03_encryption.py",
    "test_04_query_engine.py",
    "test_05_modules_kg_recall_privacy.py",
    "test_06_modules_intent_conflict_hybrid.py",
    "test_07_adapters.py",
    "test_08_edge_cases.py",
    "test_09_race_conditions.py",
    "test_10_memory_leaks.py",
    "test_11_db_corruption_batch.py",
    "test_12_indexer.py",
]

def main():
    print("=" * 70)
    print("MindForge Comprehensive Test Suite")
    print("=" * 70)

    total_pass = 0
    total_fail = 0
    script_results = []

    for script in TEST_SCRIPTS:
        script_path = os.path.join(BASE_DIR, script)
        print(f"\n{'>'*70}")
        print(f"Running: {script}")
        print(f"{'>'*70}")

        start = time.time()
        try:
            result = subprocess.run(
                [PYTHON, script_path],
                capture_output=True,
                text=True,
                cwd=BASE_DIR,
                timeout=120,
                encoding='utf-8',
                errors='replace',
            )
            elapsed = time.time() - start

            print(result.stdout)
            if result.stderr:
                print(f"STDERR: {result.stderr[:500]}")

            # Parse results from output
            for line in result.stdout.split('\n'):
                if 'Results:' in line and 'PASS' in line:
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == 'PASS,':
                            try:
                                total_pass += int(parts[i-1])
                            except:
                                pass
                        if p == 'FAIL':
                            try:
                                total_fail += int(parts[i-1])
                            except:
                                pass

            script_results.append((script, "OK", elapsed, result.returncode))

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            print(f"TIMEOUT after {elapsed:.1f}s")
            script_results.append((script, "TIMEOUT", elapsed, -1))
        except Exception as e:
            print(f"ERROR: {e}")
            script_results.append((script, "ERROR", 0, -1))

    # Summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    for script, status, elapsed, rc in script_results:
        print(f"  {script:45s} {status:8s} {elapsed:6.1f}s  rc={rc}")

    print(f"\nTotal: {total_pass} PASS, {total_fail} FAIL")
    print("=" * 70)

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
