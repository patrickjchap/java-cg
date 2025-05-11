#!/usr/bin/env python3
"""
For generating call graphs for Java projects.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List 

from tqdm import tqdm
from tree_sitter import Parser
from tree_sitter_languages import get_language

from call_graph import build_graph, write_graph_output, FunctionInfo, CallSite
from helpers import text, rel, class_stack, pkg_name

# Optional multilspy import ---------------------------------------------------
try:
    from multilspy import SyncLanguageServer  # type: ignore
    from multilspy.multilspy_config import MultilspyConfig  # type: ignore
    from multilspy.multilspy_logger import MultilspyLogger  # type: ignore

    _MULTILSPY_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    _MULTILSPY_AVAILABLE = False

# ----------------------------------------------------------------------------
# Tree‑sitter setup & queries
# ----------------------------------------------------------------------------
JAVA_LANGUAGE = get_language("java")
PARSER = Parser()
PARSER.set_language(JAVA_LANGUAGE)

PACKAGE_QUERY = JAVA_LANGUAGE.query(
    """
    (package_declaration
        (scoped_identifier) @pkg_name)
    """
)

METHOD_QUERY = JAVA_LANGUAGE.query(
    """
    (method_declaration
        name: (identifier) @meth_name
        body: (block) @body) @meth

    (constructor_declaration
        name: (identifier) @meth_name
        body: (constructor_body) @body) @meth
    """
)

CALL_QUERY = JAVA_LANGUAGE.query(
    """
    (method_invocation
        name: (identifier) @callee)
    """
)

CLASS_QUERY = JAVA_LANGUAGE.query(
    """
    (class_declaration
        name: (identifier) @cls_name)
    """
)

def collect_infos(project_root: Path, use_lsp: bool) -> Dict[str, FunctionInfo]:
    infos: Dict[str, FunctionInfo] = {}
    java_files = list(project_root.rglob("*.java"))

    for java_path in tqdm(java_files, desc="Parsing Java"):
        src_bytes = java_path.read_bytes()
        tree = PARSER.parse(src_bytes)
        pkg = pkg_name(tree, PACKAGE_QUERY)
        cls_nodes = [n for n, _ in CLASS_QUERY.captures(tree.root_node)]

        for node, cap in METHOD_QUERY.captures(tree.root_node):
            if cap != "meth":
                continue
            name_node = [n for n, c in METHOD_QUERY.captures(node) if c == "meth_name"][0]
            body_node = [n for n, c in METHOD_QUERY.captures(node) if c == "body"][0]

            classes = class_stack(node.start_byte, cls_nodes, CLASS_QUERY)
            if not classes:
                classes = [java_path.stem]
            fqn_parts = [pkg] if pkg else []
            fqn_parts.extend(classes or ["<top>"])
            fqn_parts.append(text(name_node))
            fqn = ".".join(fqn_parts)

            info = FunctionInfo(
                fqn=fqn,
                file_path=rel(project_root, java_path),
                start_line=name_node.start_point[0],
                end_line=node.end_point[0],
            )

            # Find call sites
            for callee_node, _ in CALL_QUERY.captures(body_node):
                simple = text(callee_node)
                if use_lsp:
                    info.unresolved_sites.append(
                        CallSite(
                            target_simple=simple,
                            file_path=java_path.resolve(),
                            line=callee_node.start_point[0],
                            column=callee_node.start_point[1],
                        )
                    )
                else:
                    info.calls.add(simple)

            infos[fqn] = info

    return infos


def resolve_with_lsp(infos: Dict[str, FunctionInfo], project_root: Path):
    if not _MULTILSPY_AVAILABLE:
        sys.exit("--lsp requested but multilspy not installed. Run: pip install multilspy")

    config = MultilspyConfig.from_dict({"code_language": "java"})
    logger = MultilspyLogger()
    lsp = SyncLanguageServer.create(config, logger, str(project_root))

    # Index definitions: (abs path, line range) ->FQN
    def_index: Dict[Path, Dict[tuple[int, int], str]] = {}
    for info in infos.values():
        abs_path = (project_root / info.file_path).resolve()
        def_index.setdefault(abs_path, {})[(info.start_line, info.end_line)] = info.fqn

    def locate_fqn(abs_path: Path, line0: int) -> str | None:
        for (s, e), fqn in def_index.get(abs_path, {}).items():
            if s <= line0 <= e:
                return fqn
        return None

    print("\nLaunching Eclipse JDT LS for type resolution …\n")
    with lsp.start_server():
        for info in tqdm(infos.values(), desc="LSP resolving"):
            for cs in info.unresolved_sites:
                try:
                    locs = lsp.request_definition(rel(project_root, cs.file_path), cs.line + 1, cs.column)
                except Exception:
                    continue
                if not locs:
                    continue
                loc = locs[0]  # first match
                uri = loc.get("uri") or loc.get("targetUri")
                if not (uri and uri.startswith("file://")):
                    continue
                abs_def = Path(uri[7:]).resolve()
                rng = loc.get("range") or loc.get("targetRange")
                line0 = (rng or {}).get("start", {}).get("line")
                if line0 is None:
                    continue
                fqn = locate_fqn(abs_def, line0)
                info.calls.add(fqn if fqn else cs.target_simple)
        # Clean up
        for info in infos.values():
            info.unresolved_sites.clear()

def extract_java_project_call_graph(project_root: Path, use_lsp: bool=False):
    print("\n"*100)
    print(project_root)
    if not project_root.is_dir():
        sys.exit(f"Not a directory: {project_root}")

    infos = collect_infos(project_root, use_lsp=use_lsp)
    if use_lsp:
        resolve_with_lsp(infos, project_root)

    return build_graph(infos)


def main(argv: List[str] | None = None):
    ap = argparse.ArgumentParser(description="Extract a Java call graph (optionally type‑resolved via JDT LS)")
    ap.add_argument("project", type=Path, help="Path to Java project root")
    ap.add_argument("--lsp", action="store_true", help="Enable Eclipse JDT LS via multilspy for better resolution")
    ap.add_argument("--output", type=Path, help="Directory where call graph files will be saved.", required=True)
    args = ap.parse_args(argv)

    G = extract_java_project_call_graph(args.project.resolve(), args.lsp)

    roots = [n for n in G.nodes if G.in_degree(n) == 0]
    print("\nRoot functions (entry points):")
    for r in roots:
        print("  " + r)
    
    output = args.output.resolve()
    write_graph_output(G, output)
    print(f"\nWrote {output.absolute().as_posix()}/call_graph.json and {output.absolute().as_posix()}/call_graph.dot ✔")


if __name__ == "__main__":
    main()

