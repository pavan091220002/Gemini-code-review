import re
from typing import Dict, Any

def find_line_info(diff_text: str, target_line: str) -> Dict[str, Any]:
    """
    Identifies the line, start_line, start_side & side given the diff_text and the target line to be searched for.
    Args:
        diff_text (str): The diff text to search within.
        target_line (str): The line to find in the diff.
    """
        
    lines = diff_text.splitlines()
    old_lineno = 0
    new_lineno = 0
    hunk_old_start = 0
    hunk_new_start = 0

    for line in lines:
        if line.startswith("@@"):
            match = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if match:
                hunk_old_start = old_lineno = int(match.group(1))
                hunk_new_start = new_lineno = int(match.group(2))
            continue

        content = line[1:] if line else "" 
        if line.startswith(" "):
            if content == target_line:
                return {
                    "line": new_lineno,
                    "start_line": hunk_new_start,
                    "start_side": "RIGHT", 
                    "side": "RIGHT"
                }
            old_lineno += 1
            new_lineno += 1
        elif line.startswith("-"): 
            if content == target_line:
                return {
                    "line": old_lineno,
                    "start_line": hunk_old_start,
                    "start_side": "LEFT",
                    "side": "LEFT",
                }
            old_lineno += 1
        elif line.startswith("+"): 
            if content == target_line:
                return {
                    "line": new_lineno,
                    "start_line": hunk_new_start,
                    "start_side": "RIGHT",
                    "side": "RIGHT",
                }
            new_lineno += 1
    
    return {"line": 1, "start_line": 1, "start_side": "RIGHT", "side": "RIGHT"}

