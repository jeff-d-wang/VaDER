"""
Run every test module in the project, from the repo root.

    python run_tests.py            # everything
    python run_tests.py eval       # only packages matching "eval"
    python run_tests.py -v         # show each module's own output

Exists because the test files here are deliberately stdlib-only with no
framework: some use `unittest`, some are hand-rolled `check(name, cond)`
scripts that print and return an exit code. `unittest discover` sees only
half of them. This runner treats every test module the same way the shell
does, by its exit code, which is the one thing all of them agree on.

Test modules are found by convention: any `test_*.py` under a package's
`tests/` directory, plus `eval/benchmarks/test_loader.py`, which sits next
to the data loader it tests rather than in a tests/ directory.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def discover() -> list[str]:
    modules = set()
    for path in ROOT.glob("*/tests/test_*.py"):
        modules.add(".".join(path.relative_to(ROOT).with_suffix("").parts))
    for path in ROOT.glob("*/*/test_*.py"):
        if "tests" not in path.parts:
            modules.add(".".join(path.relative_to(ROOT).with_suffix("").parts))
    for path in ROOT.glob("*/test_*.py"):
        modules.add(".".join(path.relative_to(ROOT).with_suffix("").parts))
    return sorted(modules)


def main(argv: list[str]) -> int:
    verbose = "-v" in argv
    patterns = [a for a in argv if not a.startswith("-")]

    modules = discover()
    if patterns:
        modules = [m for m in modules if any(p in m for p in patterns)]
    if not modules:
        print("No test modules matched.", file=sys.stderr)
        return 1

    failed = []
    for module in modules:
        result = subprocess.run([sys.executable, "-m", module], cwd=ROOT,
                                capture_output=not verbose, text=True)
        status = "ok  " if result.returncode == 0 else "FAIL"
        print(f"  {status}  {module}")
        if result.returncode != 0:
            failed.append(module)
            if not verbose:
                tail = (result.stdout or "") + (result.stderr or "")
                for line in tail.strip().splitlines()[-8:]:
                    print(f"          {line}")

    print(f"\n{len(modules) - len(failed)}/{len(modules)} test modules passed.")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
