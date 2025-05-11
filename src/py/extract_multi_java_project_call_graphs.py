import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List
import os
import sys

from call_graph import write_graph_output 
import extract_java_project_call_graph 

async def async_extract_java_project_call_graph(project_root: Path, use_lsp: bool=False, executor: ThreadPoolExecutor=ThreadPoolExecutor(max_workers=4)):
    loop = asyncio.get_running_loop()
    graph = await loop.run_in_executor(
            executor,
            extract_java_project_call_graph.extract_java_project_call_graph,
            project_root,
            use_lsp
    ) 
    return graph, project_root

async def main(argv: List[str] | None = None):
    parser = argparse.ArgumentParser("Extract multiple Java call graphs concurrently")
    parser.add_argument("projects", type=Path, help="Path to file that contains list of directories to Java projects.")
    parser.add_argument("--lsp", action="store_true", help="Enable Eclipse JDT LS via multilspy for better resolution")
    parser.add_argument("--output", type=Path, help="Directory where call graph files will be saved.", required=True)
    parser.add_argument("--max-workers", type=int, help="Maximum number of concurrent workers.", default=4)
    args = parser.parse_args(argv)

    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        tasks = []
        with open(args.projects) as f:
            for line in f:
                project_dir = Path(line.strip()).resolve()
                tasks.append(asyncio.create_task(async_extract_java_project_call_graph(project_dir, args.lsp)))

        results = await asyncio.gather(*tasks)
        for graph, project_root in results:
            project_base_name = project_root.name
            project_call_graph_dir = args.output / project_base_name

            try:
                os.mkdir(project_call_graph_dir)
            except OSError as error:
                print(error)

            try:
                write_graph_output(graph, project_call_graph_dir)
            except OSError as error:
                print(f"Failed to write graph for {project_call_graph_dir}")
                print(error)
                sys.exit()

            print(f"\nWrote {project_call_graph_dir.absolute().as_posix()}/call_graph.json and {project_call_graph_dir.absolute().as_posix()}/call_graph.dot ✔")

if __name__ == "__main__":
    asyncio.run(main())
