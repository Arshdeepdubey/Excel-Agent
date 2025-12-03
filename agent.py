import argparse
import logging
import os
import pandas as pd
import re
from typing import Optional
from ollama import Client as OllamaClient
import uuid
from datetime import datetime


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

    code = code.replace("df.append(", "pd.concat([df, pd.DataFrame([")
    if "pd.concat([df, pd.DataFrame([" in code:
        code = re.sub(
            r"pd\.concat\(\[df, pd\.DataFrame\(\[(.*?)\]\)(.*?)\)\)",
            r"pd.concat([df, pd.DataFrame([\1])], ignore_index=True)",
            code
        )

    local = {"df": df, "pd": pd}
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
        "You are given a pandas DataFrame named df. Return only Python code that modifies df and ALWAYS assigns "
        "the final result back to df, e.g., df = df[ ... ]. Do not print anything. Do not write files.\n\n"
        f"Goal: {task}\n\nColumns: {','.join(df.columns.astype(str))}\n\nPreview:\n{df.head(20).to_csv(index=False)}"
    )

    resp = llm_generate(prompt, model)
    code = extract_code(resp)

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
    parser = argparse.ArgumentParser()

    parser.add_argument("task", nargs="?", default="", help="Instruction describing how to modify the DataFrame")
    parser.add_argument("--model", default="llama3")
    parser.add_argument("--input", default="base.xlsx")
    parser.add_argument("--output", default="modified_output.xlsx")
    parser.add_argument("--inplace", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--create-fixture", action="store_true")

    args = parser.parse_args()

    main(
        args.task,
        args.model,
        args.input,
        args.output,
        args.inplace,
        args.dry_run,
        args.create_fixture
    )
