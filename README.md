# java-cg
A lightweight implementation to capture Java project call graphs. Uses tree-sitter for parsing and optionally uses multilspy (w/ EclipseJDTLS) for type resolution. This call graph is technically an underapproximation.

## Installation/Requirements

The python packages used are located in the `requirements.txt`, install them:
```
pip install -r requirements.txt
```

If you wish for your call graph to be more complete, you will likely want to
perform type resolution. We do type resolution using [multilspy](https://github.com/microsoft/multilspy),
which is a client-library for the [Eclipse JDTLS](https://github.com/eclipse-jdtls/eclipse.jdt.ls).
Multilspy is included in the `requirements.txt`, but to leverage the language server
backend you must install Eclipse JDTLS separately.

## Usage

If you wish to simply capture the call graph for a java project, use the command:
```bash
python3 ./src/py/extract_java_project_call_graph.py <project_path> [--lsp]
```

Using the `--lsp` flag will perform the type resolution, which will make the
call graph much more complete, but it is also significantly more expensive.

If you want to generate multiple call graphs asynchronously, we also include
a very simple script that takes as input a list of project paths:
```bash
python3 ./src/py/extract_multi_java_project_call_graphs.py <projects_list_path> [--lsp]
```
