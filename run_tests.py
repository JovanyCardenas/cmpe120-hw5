#!/usr/bin/env python3
"""Run your simulator against the public test cases.

    python run_tests.py                  # all public test cases
    python run_tests.py 01 04            # only cases whose name matches

This uses the same comparison as the autograder: it parses the values out of
your output files, so blank lines, comments, extra spacing and numbers written
in several different ways are all fine.

RFResult.txt and DMEMResult.txt are compared value by value. TraceResult.txt
is compared by the sequence of PCs that retire from WB, so a legitimate
BTB/gshare implementation may place bubbles differently without failing.
Performance counts are exact; CPI, IPC and Total Cycles are allowed 2% error;
Branch Prediction Accuracy and BTB Hit Rate are allowed 5 percentage points.

Numbers may be written as

    0b00000011    0b-prefixed binary, any width
    0x03          0x-prefixed hex
    00000011      bare binary, but only at the full field width
    3             decimal

The full field width is 32 characters for a register (RFResult.txt) and 8
characters for a memory byte (DMEMResult.txt). A bare run of 0s and 1s that is
not the full width is ambiguous and is read as decimal, so either prefix
binary with 0b or write it at full width.

Exit status is 0 when every test case passes.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
TESTS_DIR = os.path.join(HERE, "tests")

OUTPUT_FILES = [
    "RFResult.txt",
    "DMEMResult.txt",
    "TraceResult.txt",
    "PerformanceMetrics.txt",
]
INPUT_FILES = ["imem.txt", "dmem.txt"]

# Field widths, matching the writers in main.py.
REGISTER_WIDTH = 32
BYTE_WIDTH = 8
TRACE_COLUMNS = ("cycle", "IF.PC", "ID.PC", "EX.PC", "MEM.PC", "WB.PC")
TRACE_WIDTH = 6

PERFORMANCE_RELATIVE_TOLERANCE = 0.02
BRANCH_ACCURACY_ABSOLUTE_TOLERANCE = 5.0
BRANCH_ACCURACY_RELATIVE_TOLERANCE = 0.05

TIMEOUT_SECONDS = 10.0


class BadNumber(ValueError):
    """A token could not be read as a number."""


def content_lines(text):
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            yield stripped


_HEX_DIGITS = set("0123456789abcdef")


def to_int(token, binary_width=None):
    text = token.strip().replace("_", "")
    if not text:
        raise BadNumber("empty number")

    sign = 1
    if text[0] in "+-":
        if text[0] == "-":
            sign = -1
        text = text[1:]
    if not text:
        raise BadNumber("cannot read %r as a number" % token)

    lowered = text.lower()

    if lowered.startswith("0b"):
        digits = lowered[2:]
        if digits and set(digits) <= {"0", "1"}:
            return sign * int(digits, 2)
        raise BadNumber("cannot read %r as binary" % token)

    if lowered.startswith("0x"):
        digits = lowered[2:]
        if digits and set(digits) <= _HEX_DIGITS:
            return sign * int(digits, 16)
        raise BadNumber("cannot read %r as hexadecimal" % token)

    if lowered.isdigit():
        if (
            binary_width is not None
            and len(lowered) == binary_width
            and set(lowered) <= {"0", "1"}
        ):
            return sign * int(lowered, 2)
        return sign * int(lowered, 10)

    if set(lowered) <= _HEX_DIGITS:
        return sign * int(lowered, 16)

    raise BadNumber("cannot read %r as a number" % token)


def as_numbers(text, binary_width=None):
    return [to_int(token, binary_width) for line in content_lines(text)
            for token in line.replace(",", " ").split()]


def as_rows(text):
    rows = []
    for line in content_lines(text):
        tokens = line.replace(",", " ").split()
        # Tolerate a text header, with or without a leading '#', whatever
        # number of columns it has.
        if tokens and tokens[0].lower().startswith("cycle"):
            continue
        if len(tokens) < TRACE_WIDTH:
            raise BadNumber(
                "trace line has %d columns, expected %d" % (len(tokens), TRACE_WIDTH)
            )
        rows.append(tuple(to_int(tokens[i], None) for i in range(TRACE_WIDTH)))
    return rows


def as_metrics(text):
    metrics = {}
    for line in content_lines(text):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        metrics[key.strip().lower()] = value.strip()
    return metrics


def metric_number(metrics, key):
    if key not in metrics:
        raise BadNumber("missing %r" % key)
    text = metrics[key].replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        raise BadNumber("%r is not a number: %r" % (key, metrics[key]))


def retired_pcs(rows):
    return [row[5] for row in rows if row[5] != -1]


def compare(filename, got_text, want_text):
    """Return None when the file is correct, or a one-line explanation."""
    try:
        if filename == "TraceResult.txt":
            got, want = as_rows(got_text), as_rows(want_text)
            if not got:
                return "has no cycles"
            for index, row in enumerate(got):
                if row[0] != index:
                    return "row %d has cycle %d, expected %d" % (
                        index, row[0], index)
                for name, pc in zip(TRACE_COLUMNS[1:], row[1:]):
                    if pc != -1 and (pc < 0 or pc % 4 != 0):
                        return "row %d: %s is %r, expected -1 or a non-negative multiple of 4" % (
                            index, name, pc)
            got_retired, want_retired = retired_pcs(got), retired_pcs(want)
            if len(got_retired) != len(want_retired):
                return "retires %d instructions, expected %d" % (
                    len(got_retired), len(want_retired))
            for index, (actual, expected) in enumerate(zip(got_retired, want_retired)):
                if actual != expected:
                    return ("retires PC %d at position %d, expected %d "
                            "(wrong-path instruction executed or missing instruction)"
                            % (actual, index, expected))

        elif filename == "PerformanceMetrics.txt":
            got, want = as_metrics(got_text), as_metrics(want_text)
            # Counts that depend on the program, not the timing.
            for key, display in (
                ("instructions executed", "Instructions Executed"),
                ("conditional branches", "Conditional Branches"),
                ("btb lookups", "BTB Lookups"),
            ):
                if key not in want:
                    continue
                expected = metric_number(want, key)
                actual = metric_number(got, key)
                if int(actual) != int(expected):
                    return "%s is %d, expected %d" % (
                        display, int(actual), int(expected))
            # Cycle-derived values: 2% relative tolerance.
            for key, display in (
                ("total cycles", "Total Cycles"),
                ("cpi", "CPI"),
                ("ipc", "IPC"),
            ):
                if key not in want:
                    continue
                expected = metric_number(want, key)
                actual = metric_number(got, key)
                if abs(actual - expected) > max(
                    1e-9, PERFORMANCE_RELATIVE_TOLERANCE * abs(expected)
                ):
                    return "%s is %g, expected %g (allowed error 2%%)" % (
                        display, actual, expected)
            # Branch accuracy and BTB hit rate: 5 percentage points (or 5%
            # relative).
            expected_branches = 0
            if "conditional branches" in want:
                expected_branches = int(metric_number(want, "conditional branches"))
            if expected_branches and "branch prediction accuracy" in want:
                expected = metric_number(want, "branch prediction accuracy")
                actual = metric_number(got, "branch prediction accuracy")
                if actual <= 1.0 and expected > 1.0 and "%" not in got.get(
                        "branch prediction accuracy", ""):
                    actual *= 100.0
                if abs(actual - expected) > max(
                    BRANCH_ACCURACY_ABSOLUTE_TOLERANCE,
                    BRANCH_ACCURACY_RELATIVE_TOLERANCE * abs(expected),
                ):
                    return ("Branch Prediction Accuracy is %g%%, expected %g%% "
                            "(allowed error 5 percentage points)"
                            % (actual, expected))

            expected_lookups = 0
            if "btb lookups" in want:
                expected_lookups = int(metric_number(want, "btb lookups"))
            if expected_lookups and "btb hit rate" in want:
                expected = metric_number(want, "btb hit rate")
                actual = metric_number(got, "btb hit rate")
                if actual <= 1.0 and expected > 1.0 and "%" not in got.get(
                        "btb hit rate", ""):
                    actual *= 100.0
                if abs(actual - expected) > max(
                    BRANCH_ACCURACY_ABSOLUTE_TOLERANCE,
                    BRANCH_ACCURACY_RELATIVE_TOLERANCE * abs(expected),
                ):
                    return ("BTB Hit Rate is %g%%, expected %g%% "
                            "(allowed error 5 percentage points)"
                            % (actual, expected))

        else:
            width = REGISTER_WIDTH if filename == "RFResult.txt" else BYTE_WIDTH
            got, want = as_numbers(got_text, width), as_numbers(want_text, width)
            if len(got) != len(want):
                return "has %d values, expected %d" % (len(got), len(want))
            for index, (a, b) in enumerate(zip(got, want)):
                if a != b:
                    return "value %d is %d, expected %d" % (index, a, b)

        return None
    except BadNumber as error:
        return "could not be read (%s)" % error
    except (ValueError, KeyError) as error:
        return "could not be compared (%s)" % error


def run_case(path):
    """Return (ok, [problem strings])."""
    input_dir = os.path.join(path, "input")
    expected_dir = os.path.join(path, "expected")

    work_dir = tempfile.mkdtemp(prefix="hw5_")
    try:
        io_dir = os.path.join(work_dir, "io")
        os.makedirs(io_dir)
        for filename in INPUT_FILES:
            shutil.copy(os.path.join(input_dir, filename),
                        os.path.join(io_dir, filename))

        try:
            result = subprocess.run(
                [sys.executable, MAIN, "--iodir", io_dir],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return False, ["timed out after %gs -- does it stop at HALT?"
                           % TIMEOUT_SECONDS]

        if result.returncode != 0:
            tail = (result.stderr or "").strip().splitlines()
            return False, ["exited with status %d: %s"
                           % (result.returncode, tail[-1] if tail else "")]

        problems = []
        for filename in OUTPUT_FILES:
            produced = os.path.join(io_dir, filename)
            if not os.path.isfile(produced):
                problems.append("%s was not produced" % filename)
                continue
            try:
                with open(produced) as fh:
                    got = fh.read()
                with open(os.path.join(expected_dir, filename)) as fh:
                    want = fh.read()
            except OSError as error:
                problems.append("%s could not be opened (%s)" % (filename, error))
                continue
            problem = compare(filename, got, want)
            if problem:
                problems.append("%s %s" % (filename, problem))
        return (not problems), problems
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def main(argv):
    if not os.path.isfile(MAIN):
        print("error: %s does not exist" % MAIN)
        return 2

    if not os.path.isdir(TESTS_DIR):
        print("error: %s does not exist" % TESTS_DIR)
        return 2

    names = sorted(
        name for name in os.listdir(TESTS_DIR)
        if os.path.isdir(os.path.join(TESTS_DIR, name))
    )
    if argv:
        names = [name for name in names if any(arg in name for arg in argv)]
    if not names:
        print("no test cases matched")
        return 2

    passed = 0
    for name in names:
        ok, problems = run_case(os.path.join(TESTS_DIR, name))
        if ok:
            passed += 1
            print("PASS  %s" % name)
        else:
            print("FAIL  %s" % name)
            for problem in problems:
                print("        %s" % problem)

    print()
    print("%d/%d test cases passed" % (passed, len(names)))
    if passed < len(names):
        print("Read tests/<case>/input/code.asm to see the program one "
              "instruction at a time.")
    return 0 if passed == len(names) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
