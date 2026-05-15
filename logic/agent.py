import argparse
import logging
import os
import pandas as pd
import re
from typing import Optional
from ollama import Client as OllamaClient
import uuid
from datetime import datetime
import numpy as np


# ============================================================
# FIXTURE: Creates a known test Excel file for reliable testing
# ============================================================

def create_fixture_excel(path="base.xlsx"):
    """Creates a predictable fixture Excel file for testing."""
    df = pd.DataFrame({
        "Name": ["Bob", "Sara", "Mike", "Lucy"],
        "Status": ["Active", "Closed", "Active", "Closed"],
        "Quantity": [3, 1, 5, 2],
        "Price": [10, 15, 20, 30],
        "Department": ["Engineering", "HR", "Engineering", "Finance"]
    })
    df.to_excel(path, index=False)
    print(f"[Fixture] Created fixture Excel file at: {path}")
    return df


# ============================================================
# Extract Code
# ============================================================

def extract_code(text: str) -> str:
    """Extract a code snippet from model text output."""
    blocks = re.findall(r"```(?:[a-zA-Z0-9_-]+\n)?([\s\S]*?)```", text, re.IGNORECASE)
    if blocks:
        code = blocks[-1].strip()
        code = code.encode('utf-8').decode('unicode_escape')
        code = re.sub(r'^python\s*\n', '', code, flags=re.IGNORECASE)
        return code

    if "```" in text:
        parts = text.split("```")
        candidates = [p for p in parts if any(tok in p for tok in ("df[", "df =", "import ", "pd.", "np."))]
        if candidates:
            return candidates[-1].strip()

    m = re.search(r"response\s*=\s*[\"']?```(?:python)?\s*([\s\S]+?)\s*```[\"']?", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*(import |from |df\[|df\s*=|np\.|pd\.)", line, re.IGNORECASE):
            return "\n".join(l.rstrip() for l in lines[i:]).strip()

    return text.strip()


# ============================================================
# Execute Generated Code
# ============================================================

def run_generated_code(code: str, df: pd.DataFrame) -> pd.DataFrame:
    code = code.strip()
    code = re.sub(r"^\s*```[a-zA-Z0-9_-]*\s*", "", code)
    code = re.sub(r"\s*```\s*$", "", code)

    if (code.startswith('"') and code.endswith('"')) or (code.startswith("'") and code.endswith("'")):
        code = code[1:-1]

    # Fix df.append() calls - convert to pd.concat() properly
    # Handle cases where df.append() contains dictionary data
    code = re.sub(
        r"df\.append\(\s*pd\.DataFrame\(\s*\[\s*({[^}]+})\s*\]\s*\)\s*,?\s*ignore_index\s*=\s*True\s*\)",
        r"df = pd.concat([df, pd.DataFrame([\1])], ignore_index=True)",
        code,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Fallback for simpler df.append patterns
    code = re.sub(
        r"df\.append\(\s*({[^}]+})\s*,?\s*ignore_index\s*=\s*True\s*\)",
        r"df = pd.concat([df, pd.DataFrame([\1])], ignore_index=True)",
        code,
        flags=re.MULTILINE | re.DOTALL
    )

    local = {"df": df, "pd": pd, "np": np}
    
    # Helper function for creating columns with conditions
    def create_column_with_condition(col_name, values_dict):
        """Helper to create a column with conditional values"""
        df[col_name] = df['Name'].apply(lambda x: values_dict.get(x, values_dict.get('default', None)))
    
    globals_safe = {
        "__builtins__": {
            "len": len, "range": range, "min": min, "max": max,
            "list": list, "dict": dict, "tuple": tuple, "set": set,
            "str": str, "int": int, "float": float, "bool": bool,
            "enumerate": enumerate, "zip": zip, "sum": sum,
            "print": print, "__import__": __import__,
        }
    }

    try:
        compiled = compile(code, "<gen>", "exec")
        exec(compiled, globals_safe, local)
    except Exception as e:
        raise RuntimeError(f"generated code execution failed: {e}")

    if "df" not in local:
        raise RuntimeError("generated code must set df")

    return local["df"]


# ============================================================
# Unique Output
# ============================================================

def _unique_output(path: str) -> str:
    base, ext = os.path.splitext(path)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    short = uuid.uuid4().hex[:8]
    return f"{base}_{ts}_{short}{ext}"


# ============================================================
# Correct Ollama Streaming
# ============================================================

def llm_generate(prompt: str, model: str) -> str:
    client = OllamaClient()
    try:
        stream = client.generate(model=model, prompt=prompt, stream=True)
    except TypeError:
        resp = client.generate(model=model, prompt=prompt)
        return resp.get("response", "")

    chunks = []
    for chunk in stream:
        part = chunk.get("response", "")
        if part:
            chunks.append(part)

    return "".join(chunks)


# ============================================================
# Main Logic (with new fixture integration)
# ============================================================

def main(task: str, model: str, input_path: str, output_path: str, inplace: bool, dry: bool, create_fixture: bool) -> None:

    # -------------------------
    # NEW → Create fixture on request
    # -------------------------
    if create_fixture:
        create_fixture_excel(input_path)
        return

    # Auto-create fixture if file missing
    if not os.path.exists(input_path):
        print(f"[Fixture] Input file missing: {input_path}. Creating fixture automatically.")
        create_fixture_excel(input_path)

    df = pd.read_excel(input_path)

    prompt = (
        "You are a data manipulation expert. You have a pandas DataFrame named 'df' with the following structure:\n\n"
        f"Columns: {', '.join(df.columns.astype(str))}\n"
        f"Data types: {df.dtypes.to_dict()}\n"
        f"Number of rows: {len(df)}\n\n"
        f"Data preview:\n{df.to_string()}\n\n"
        "================================================================================\n"
        "TASK INSTRUCTIONS:\n"
        "================================================================================\n"
        "Your task is to modify this DataFrame according to the following requirement:\n"
        f"{task}\n\n"
        "CRITICAL REQUIREMENTS FOR CODE GENERATION:\n"
        "1. Generate ONLY valid, executable Python code - no explanations or markdown\n"
        "2. The code must be syntactically correct and runnable\n"
        "3. Always assign the result back to variable 'df' (e.g., df = ... or df[...] = ...)\n"
        "4. Use proper pandas operations:\n"
        "   - For adding rows: df = pd.concat([df, pd.DataFrame([{...}])], ignore_index=True)\n"
        "   - For adding columns: df['new_col'] = value or df.loc[condition, 'col'] = value\n"
        "   - For filtering: df = df[condition]\n"
        "   - NEVER use deprecated df.append() method\n"
        "5. Handle data types correctly (strings, numbers, booleans)\n"
        "6. Do NOT print anything, write files, or import modules\n"
        "7. Return ONLY the Python code - no additional text\n"
        "8. If creating columns, preserve all existing columns and data\n"
        "9. If assigning values conditionally, use df.loc[condition, 'column'] = value\n"
        "10. Be precise with string values and data types\n\n"
        "Generate the Python code now:"
    )

    resp = llm_generate(prompt, model)
    code = extract_code(resp)
    
    # Log generated code for debugging
    logging.debug(f"Raw LLM response:\n{resp}\n")
    logging.debug(f"Extracted code:\n{code}\n")

    if dry:
        print("----- Generated Code -----")
        print(code)
        print("--------------------------")
        return

    try:
        new_df = run_generated_code(code, df)
    except RuntimeError:
        logging.exception("Generated code failed; fallback needed.")
        new_df = df

    # ================================================
    # If nothing changed, fallback using natural language
    # ================================================

    if new_df.equals(df):  # improved check
        # NATURAL LANGUAGE REMOVE
        nl_remove = re.search(
            r"remove\s+rows?\s+where\s+([A-Za-z0-9_ ]+)\s*(=|equals|is)\s*['\"]?([A-Za-z0-9_ ]+)['\"]?",
            task,
            flags=re.IGNORECASE
        )

        if nl_remove:
            col = nl_remove.group(1).strip()
            value = nl_remove.group(3).strip()

            match_cols = [c for c in df.columns if c.lower() == col.lower()]
            if match_cols:
                col = match_cols[0]
                candidate = df[df[col].astype(str).str.lower() != value.lower()]

                if not candidate.equals(df):
                    if inplace:
                        os.replace(input_path, input_path + ".bak")
                        candidate.to_excel(input_path, index=False)
                    else:
                        uniq = _unique_output(output_path)
                        candidate.to_excel(uniq, index=False)

                    print("[Fallback] Applied natural-language remove.")
                    return

    # ================================================
    # Write result
    # ================================================

    if inplace:
        os.replace(input_path, input_path + ".bak")
        new_df.to_excel(input_path, index=False)
        print(f"[OK] Updated file (backup at {input_path}.bak)")

    else:
        uniq = _unique_output(output_path)
        new_df.to_excel(uniq, index=False)
        print(f"[OK] Wrote output: {uniq}")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Excel Agent: Modify Excel files using natural language instructions"
    )

    parser.add_argument("task", nargs="*", help="Instruction describing how to modify the DataFrame (supports complex strings with special characters)")
    parser.add_argument("--model", default="llama3", help="LLM model to use (default: llama3)")
    parser.add_argument("--input", default="base.xlsx", help="Input Excel file (default: base.xlsx)")
    parser.add_argument("--output", default="modified_output.xlsx", help="Output Excel file prefix (default: modified_output.xlsx)")
    parser.add_argument("--inplace", action="store_true", help="Overwrite input file instead of creating new file")
    parser.add_argument("--dry-run", action="store_true", help="Show generated code without executing")
    parser.add_argument("--create-fixture", action="store_true", help="Create a fixture Excel file for testing")

    args = parser.parse_args()
    
    # Join task arguments back together since nargs="*" splits on spaces
    task = " ".join(args.task) if args.task else ""

    main(
        task,
        args.model,
        args.input,
        args.output,
        args.inplace,
        args.dry_run,
        args.create_fixture
    )
