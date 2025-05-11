from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Dict, List, Set

import networkx as nx

@dataclass
class CallSite:
    target_simple: str
    file_path: Path  # absolute
    line: int  # 0‑based
    column: int  # 0‑based

@dataclass
class FunctionInfo:
    fqn: str
    file_path: str  # relative to project root
    start_line: int
    end_line: int
    calls: Set[str] = field(default_factory=set)  # resolved FQNs or simple ids
    unresolved_sites: List[CallSite] = field(default_factory=list) # for LSP

def build_graph(infos: Dict[str, FunctionInfo]) ->nx.DiGraph:
    G = nx.DiGraph()
    for info in infos.values():
        G.add_node(info.fqn, file=info.file_path, start=info.start_line, end=info.end_line)
        for callee in info.calls:
            G.add_edge(info.fqn, callee)
    return G

def write_graph_output(G: nx.DiGraph, output_dir_path: Path):
    with open(output_dir_path / "call_graph.json", "w", encoding="utf8") as fp:
        json.dump(
            {
                "nodes": [{"id": n, **G.nodes[n]} for n in G.nodes],
                "edges": [{"u": u, "v": v} for u, v in G.edges],
            },
            fp,
            indent=2,
        )
    nx.drawing.nx_pydot.write_dot(G, output_dir_path / "call_graph.dot")
