
from pathlib import Path
from typing import List

def text(node):
    return node.text.decode()


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def pkg_name(tree, query) -> str | None:
    caps = query.captures(tree.root_node)
    return text(caps[0][0]) if caps else None


def class_stack(byte_offset: int, cls_nodes, query) -> List[str]:
    stack: List[str] = []
    for cls in cls_nodes:
        if cls.start_byte <= byte_offset <= cls.end_byte:
            name_node = [n for n, c in query.captures(cls) if c == "cls_name"][0]
            stack.append(text(name_node))
    return stack



