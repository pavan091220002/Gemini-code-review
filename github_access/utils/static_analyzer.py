import os
import subprocess
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import tempfile

from pydantic import BaseModel
from radon.complexity import cc_visit
from radon.metrics import h_visit
from tree_sitter import Parser
from tree_sitter_languages import get_language

logger = logging.getLogger(__name__)

try:
    PYTHON_LANGUAGE = get_language("python")
    GO_LANGUAGE = get_language("go")
    JAVASCRIPT_LANGUAGE = get_language("javascript")
    JAVA_LANGUAGE = get_language("java")
    
    supported_languages = {
        ".py": PYTHON_LANGUAGE,
        ".go": GO_LANGUAGE,
        ".js": JAVASCRIPT_LANGUAGE,
        ".java": JAVA_LANGUAGE,
    }
    logger.info("Tree-sitter languages loaded successfully in static_analyzer.")
except Exception as e:
    logger.error(f"Failed to load Tree-sitter languages in static_analyzer: {str(e)}. AST-based analysis might be limited.", exc_info=True)
    supported_languages = {} 

# Initialize Tree-sitter parser
parser = Parser()

class FunctionSignature(BaseModel):
    name: str
    parameters: List[str]
    return_type: Optional[str] = None

class ClassHierarchy(BaseModel):
    name: str
    parent_classes: List[str]
    methods: List[str]
    attributes: List[str]

class StaticAnalysisResult(BaseModel):
    """
    Represents the comprehensive result of static code analysis.
    """
    cyclomatic_complexity: int
    cognitive_complexity: int
    halstead_metrics: Dict[str, float]
    issues: List[Dict[str, Any]]
    ast_sexp: str
    function_signatures: List[FunctionSignature] = [] 
    class_hierarchies: List[ClassHierarchy] = []     
    module_dependencies: List[str] = []            

def perform_static_analysis(file_content: str, ext: str) -> StaticAnalysisResult:
    """
    Performs static analysis on the given file content using Tree-sitter and external tools.
    Includes AST parsing, complexity metrics, and integration with linters/scanners.
    """
    cyclomatic = 0
    cognitive = 0
    halstead = {}
    issues = []
    ast_sexp = "AST not available for this language or due to parsing error."
    function_signatures = []
    class_hierarchies = []
    module_dependencies = []

    # Tree-sitter for AST and AST-based metrics & Context Extraction
    if ext in supported_languages:
        try:
            parser.set_language(supported_languages[ext])
            code_bytes = bytes(file_content, "utf8")
            tree = parser.parse(code_bytes)
            root_node = tree.root_node
            ast_sexp = root_node.sexp()

            # Basic Cyclomatic Complexity (simplified for general languages via Tree-sitter)
            # For Python, radon's cc_visit is more accurate.
            if ext == ".py":
                try:
                    # radon's cc_visit returns a list of CodeBlock objects
                    blocks = cc_visit(file_content)
                    cyclomatic = sum(block.complexity for block in blocks)
                except Exception as e:
                    logger.warning(f"Radon Cyclomatic Complexity failed for Python: {str(e)}", exc_info=True)
                    # Fallback to Tree-sitter based if radon fails
                    cyclomatic = sum(1 for node in root_node.children if node.type in [
                        "if_statement", "for_statement", "while_statement", "switch_statement", "case_statement", "else_clause", "catch_clause", "do_statement"
                    ])
            else:
                cyclomatic = sum(1 for node in root_node.children if node.type in [
                    "if_statement", "for_statement", "while_statement", "switch_statement", "case_statement", "else_clause", "catch_clause", "do_statement"
                ])


            # Basic Cognitive Complexity (simplified via Tree-sitter)
            # This is a heuristic and not a precise Cognitive Complexity calculation.
            def calculate_cognitive_recursive(node, depth=0):
                nonlocal cognitive

                if node.type in ["if_statement", "for_statement", "while_statement", "switch_statement", "try_statement", "catch_clause", "do_statement"]:
                    cognitive += (depth + 1) # Each level of nesting adds to cognitive complexity
                
                if node.type in ["break_statement", "continue_statement", "return_statement"]:
                    cognitive += 1

                for child in node.children:
                    calculate_cognitive_recursive(child, depth + 1)
            
            calculate_cognitive_recursive(root_node)

            # --- Context Extraction (Function Signatures, Class Hierarchies, Module Dependencies) ---
            if ext == ".py":
                for node in root_node.children:
                    if node.type == 'function_definition':
                        name_node = node.child_by_field_name('name')
                        parameters_node = node.child_by_field_name('parameters')
                        return_type_node = node.child_by_field_name('return_type')

                        name = name_node.text.decode('utf-8') if name_node else 'unknown'
                        params = []
                        if parameters_node:
                            for param_node in parameters_node.children:
                                if param_node.type == 'identifier':
                                    params.append(param_node.text.decode('utf-8'))
                                elif param_node.type == 'typed_parameter':
                                    param_name_node = param_node.child_by_field_name('name')
                                    if param_name_node:
                                        params.append(param_name_node.text.decode('utf-8'))
                        
                        return_type = return_type_node.text.decode('utf-8') if return_type_node else None
                        function_signatures.append(FunctionSignature(name=name, parameters=params, return_type=return_type))

                # Extract Python Class Hierarchies
                for node in root_node.children:
                    if node.type == 'class_definition':
                        name_node = node.child_by_field_name('name')
                        superclasses_node = node.child_by_field_name('superclasses')
                        body_node = node.child_by_field_name('body')

                        name = name_node.text.decode('utf-8') if name_node else 'unknown'
                        parent_classes = []
                        if superclasses_node:
                            for superclass_child in superclasses_node.children:
                                if superclass_child.type == 'identifier':
                                    parent_classes.append(superclass_child.text.decode('utf-8'))
                                elif superclass_child.type == 'attribute':
                                    parent_classes.append(superclass_child.text.decode('utf-8'))

                        methods = []
                        attributes = []
                        if body_node:
                            for class_body_node in body_node.children:
                                if class_body_node.type == 'function_definition':
                                    method_name_node = class_body_node.child_by_field_name('name')
                                    if method_name_node:
                                        methods.append(method_name_node.text.decode('utf-8'))
                                elif class_body_node.type == 'expression_statement':
                                    assignment_node = class_body_node.child(0)
                                    if assignment_node and assignment_node.type == 'assignment':
                                        left_side = assignment_node.child_by_field_name('left')
                                        if left_side and left_side.type == 'attribute':
                                            attribute_name_node = left_side.child_by_field_name('attribute')
                                            if attribute_name_node:
                                                attributes.append(attribute_name_node.text.decode('utf-8'))
                        
                        class_hierarchies.append(ClassHierarchy(name=name, parent_classes=parent_classes, methods=methods, attributes=attributes))

                # Extract Python Module Dependencies (imports)
                for node in root_node.children:
                    if node.type == 'import_statement' or node.type == 'import_from_statement':
                        for child in node.children:
                            if child.type == 'dotted_name':\
                                module_dependencies.append(child.text.decode('utf-8'))
                            elif child.type == 'aliased_import':
                                dotted_name_node = child.child_by_field_name('name')
                                if dotted_name_node:
                                    module_dependencies.append(dotted_name_node.text.decode('utf-8'))
                            elif child.type == 'import_as_clause': 
                                name_node = child.child_by_field_name('name')
                                if name_node:
                                    module_dependencies.append(name_node.text.decode('utf-8'))
                            elif child.type == 'identifier': 
                                module_dependencies.append(child.text.decode('utf-8'))
                module_dependencies = list(sorted(set(module_dependencies)))

            elif ext == ".js":
                for node in root_node.children:
                    if node.type == 'function_declaration' or node.type == 'arrow_function':
                        name_node = node.child_by_field_name('name')
                        parameters_node = node.child_by_field_name('parameters')
                        name = name_node.text.decode('utf-8') if name_node else 'anonymous'
                        params = [p.text.decode('utf-8') for p in parameters_node.children if p.type == 'identifier'] if parameters_node else []
                        function_signatures.append(FunctionSignature(name=name, parameters=params))
                    elif node.type == 'import_statement':
                        source_node = node.child_by_field_name('source')
                        if source_node:
                            module_dependencies.append(source_node.text.decode('utf-8').strip("'\""))
                module_dependencies = list(sorted(set(module_dependencies))) # Remove duplicates

            elif ext == ".java":
                for node in root_node.children:
                    if node.type == 'class_declaration':
                        name_node = node.child_by_field_name('name')
                        class_name = name_node.text.decode('utf-8') if name_node else 'unknown'
                        
                        extends_clause = node.child_by_field_name('superclass')
                        parent_classes = [extends_clause.text.decode('utf-8').split()[-1]] if extends_clause else [] # Extract class name from "extends ClassName"
                        
                        class_methods = []
                        class_attributes = []
                        body_node = node.child_by_field_name('body')
                        if body_node:
                            for member in body_node.children:
                                if member.type == 'method_declaration':
                                    method_name_node = member.child_by_field_name('name')
                                    if method_name_node:
                                        class_methods.append(method_name_node.text.decode('utf-8'))
                                elif member.type == 'field_declaration':
                                    declarator = member.child_by_field_name('declarator')
                                    if declarator and declarator.type == 'variable_declarator':
                                        attr_name_node = declarator.child_by_field_name('name')
                                        if attr_name_node:
                                            class_attributes.append(attr_name_node.text.decode('utf-8'))
                        
                        class_hierarchies.append(ClassHierarchy(name=class_name, parent_classes=parent_classes, methods=class_methods, attributes=class_attributes))
                    elif node.type == 'import_declaration':
                        dotted_name_node = node.child_by_field_name('name')
                        if dotted_name_node:
                            module_dependencies.append(dotted_name_node.text.decode('utf-8'))
                module_dependencies = list(sorted(set(module_dependencies)))


            elif ext == ".go":
                for node in root_node.children:
                    if node.type == 'function_declaration':
                        name_node = node.child_by_field_name('name')
                        parameters_node = node.child_by_field_name('parameters')
                        result_node = node.child_by_field_name('result') 
                        
                        name = name_node.text.decode('utf-8') if name_node else 'unknown'
                        params = []
                        if parameters_node:
                            for param_list_node in parameters_node.children:
                                if param_list_node.type == 'parameter_declaration':
                                    for param_child in param_list_node.children:
                                        if param_child.type == 'identifier':
                                            params.append(param_child.text.decode('utf-8'))
                        
                        return_type = result_node.text.decode('utf-8') if result_node else None
                        function_signatures.append(FunctionSignature(name=name, parameters=params, return_type=return_type))
                    elif node.type == 'import_declaration':
                        for import_spec in node.children:
                            if import_spec.type == 'import_spec':
                                path_node = import_spec.child_by_field_name('path')
                                if path_node:
                                    module_dependencies.append(path_node.text.decode('utf-8').strip('\"'))
                module_dependencies = list(sorted(set(module_dependencies)))


        except Exception as e:
            logger.error(f"Tree-sitter parsing or AST/complexity/context calculation failed for {ext}: {str(e)}", exc_info=True)
            ast_sexp = f"Error generating AST: {str(e)}"
    else:
        logger.warning(f"Tree-sitter not supported for extension: {ext}. Skipping AST and AST-based metrics.")


    if ext == ".py":
        try:
            halstead_data = h_visit(file_content)
            halstead = {
                "length": halstead_data.total.length,
                "vocabulary": halstead_data.total.vocabulary,
                "difficulty": halstead_data.total.difficulty,
                "effort": halstead_data.total.effort
            }
        except Exception as e:
            logger.warning(f"Radon Halstead metrics failed for Python: {str(e)}", exc_info=True)
    else:
        # Simplified Halstead for other languages (conceptual)
        # This requires more sophisticated tokenization for accuracy in a real scenario.
        operators = set(["+", "-", "*", "/", "=", ">", "<", "==", "!=", "&&", "||", "!", "++", "--", "+=", "-=", "*=", "/=", "%=", "&", "|", "^", "~", "<<", ">>", ">>>", "instanceof", "new", "delete", "typeof", "void", "in", "this", "super", "null", "true", "false", "{", "}", "(", ")", "[", "]", ";", ",", "."])
        operands = set()
        operator_count = 0
        operand_count = 0
        
        words = re.findall(r'\b\w+\b|[+\-*/=><!&|~^%{}()[\];,.]', file_content)
        for word in words:
            if word in operators:
                operator_count += 1
            elif word.strip(): # Treat non-operators as operands
                operands.add(word)
                operand_count += 1
        
        n1 = len(operators.intersection(set(words))) # Unique operators found in code
        n2 = len(operands) # Unique operands found in code
        N1 = operator_count
        N2 = operand_count 

        if n1 + n2 > 0: 
            halstead = {
                "length": N1 + N2,
                "vocabulary": n1 + n2,
                "difficulty": (n1 / 2) * (N2 / n2) if n2 > 0 else 0,
                "effort": ((n1 / 2) * (N2 / n2)) * (N1 + N2) if n2 > 0 else 0
            }
        else:
            halstead = {"length": 0, "vocabulary": 0, "difficulty": 0, "effort": 0}

    if ext == ".py":
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=ext, encoding='utf-8') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        try:
            pylint_result = subprocess.run(
                ["pylint", "--output-format=json", temp_file_path], 
                capture_output=True, text=True, check=False
            )
            if pylint_result.stdout:
                try:
                    pylint_issues = json.loads(pylint_result.stdout)
                    issues.extend([
                        {"tool": "pylint", "message": i.get("message"), "line": i.get("line"), "type": i.get("type"), "symbol": i.get("symbol")}
                        for i in pylint_issues
                    ])
                except json.JSONDecodeError:
                    logger.warning(f"Pylint output was not valid JSON for {temp_file_path}: {pylint_result.stdout[:200]}...")
        except Exception as e:
            logger.warning(f"Pylint failed for {temp_file_path}: {str(e)}", exc_info=True)

        try:
            bandit_result = subprocess.run(
                ["bandit", "-r", temp_file_path, "-f", "json"],
                capture_output=True, text=True, check=False
            )
            if bandit_result.stdout:
                try:
                    bandit_output = json.loads(bandit_result.stdout)
                    if "results" in bandit_output:
                        issues.extend([
                            {"tool": "bandit", "message": r.get("issue_text"), "line": r.get("line_number"), "severity": r.get("issue_severity"), "confidence": r.get("issue_confidence")}
                            for r in bandit_output["results"]
                        ])
                except json.JSONDecodeError:
                    logger.warning(f"Bandit output was not valid JSON for {temp_file_path}: {bandit_result.stdout[:200]}...")
            if bandit_result.stderr:
                logger.warning(f"Bandit stderr for {temp_file_path}: {bandit_result.stderr}")
        except FileNotFoundError:
            logger.warning("Bandit not found. Please install it (`pip install bandit`).")
        except Exception as e:
            logger.warning(f"Bandit failed for {temp_file_path}: {str(e)}", exc_info=True)
        finally:
            os.unlink(temp_file_path)


    elif ext == ".js" or ext == ".ts":
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=ext, encoding='utf-8') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        try:
            eslint_result = subprocess.run(
                ["eslint", "--stdin", "--stdin-filename", temp_file_path, "--format=json"], 
                capture_output=True, text=True, check=False
            )
            if eslint_result.stdout:
                try:
                    eslint_output = json.loads(eslint_result.stdout)
                    if eslint_output and isinstance(eslint_output, list) and len(eslint_output) > 0:
                        issues.extend([
                            {"tool": "eslint", "message": m.get("message"), "line": m.get("line"), "severity": m.get("severity")}
                            for m in eslint_output[0].get("messages", [])
                        ])
                except json.JSONDecodeError:
                    logger.warning(f"ESLint output was not valid JSON for {temp_file_path}: {eslint_result.stdout[:200]}...")
        except Exception as e:
            logger.warning(f"ESLint failed for {temp_file_path}: {str(e)}", exc_info=True)
        finally:
            os.unlink(temp_file_path)


    elif ext == ".java":
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=ext, encoding='utf-8') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        try:
            checkstyle_result = subprocess.run(
                ["checkstyle", "-c", "/google_checks.xml", temp_file_path], # Use temp file path
                capture_output=True, text=True, check=False
            )
            if checkstyle_result.stdout:
                try:
                    # Checkstyle output can be XML or plain text. Parsing XML if available.
                    if checkstyle_result.stdout.strip().startswith("<"): # Check if it's XML
                        root = ET.fromstring(checkstyle_result.stdout)
                        for error in root.findall(".//error"):
                            issues.append({
                                "tool": "checkstyle", 
                                "message": error.get("message"), 
                                "line": error.get("line"), 
                                "severity": error.get("severity")
                            })
                    else: # Fallback to parsing plain text output
                        for line in checkstyle_result.stdout.splitlines():
                            match = re.match(r'\[(\w+)\] (.+):(\d+):(.+)', line)
                            if match:
                                issues.append({
                                    "tool": "checkstyle",
                                    "severity": match.group(1),
                                    "message": match.group(4).strip(),
                                    "line": int(match.group(3))
                                })
                except ET.ParseError:
                    logger.warning(f"Checkstyle output was not valid XML for {temp_file_path}: {checkstyle_result.stdout[:200]}...")
            if checkstyle_result.stderr:
                logger.warning(f"Checkstyle stderr for {temp_file_path}: {checkstyle_result.stderr}")
        except FileNotFoundError:
            logger.warning("Checkstyle not found. Please install it and ensure google_checks.xml is accessible.")
        except Exception as e:
            logger.warning(f"Checkstyle failed for {temp_file_path}: {str(e)}", exc_info=True)
        finally:
            os.unlink(temp_file_path)


    # Reuse for License Compliance (general)
    # This tool also requires a file path, so use a temporary file.
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=ext, encoding='utf-8') as temp_file:
        temp_file.write(file_content)
        temp_file_path = temp_file.name
    try:
        reuse_result = subprocess.run(
            ["reuse", "lint", "--json", "--plain", temp_file_path], # Run on temp file
            capture_output=True, text=True, check=False
        )
        if reuse_result.stdout:
            try:
                reuse_output = json.loads(reuse_result.stdout)
                if "issues" in reuse_output:
                    issues.extend([
                        {"tool": "reuse", "message": i.get("message"), "filename": i.get("filename")}
                        for i in reuse_output["issues"]
                    ])
            except json.JSONDecodeError:
                logger.warning(f"Reuse output was not JSON for {temp_file_path}: {reuse_result.stdout[:200]}...")
        if reuse_result.stderr:
            logger.warning(f"Reuse stderr for {temp_file_path}: {reuse_result.stderr}")
    except FileNotFoundError:
        logger.warning("Reuse not found. Please install it (`pip install reuse`).")
    except Exception as e:
        logger.warning(f"Reuse failed for {temp_file_path}: {str(e)}", exc_info=True)
    finally:
        os.unlink(temp_file_path)


    return StaticAnalysisResult(
        cyclomatic_complexity=cyclomatic,
        cognitive_complexity=cognitive,
        halstead_metrics=halstead,
        issues=issues,
        ast_sexp=ast_sexp,
        function_signatures=function_signatures,
        class_hierarchies=class_hierarchies,
        module_dependencies=module_dependencies
    )

