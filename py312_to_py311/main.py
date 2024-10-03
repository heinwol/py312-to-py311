from __future__ import annotations

from py312_to_py311.rewriting import rewrite_src


def main() -> None:
    test_str = """
type NodeProcessed[CalledMethodT: CalledMethod] = TypedNode[
    ProcessedTreeNodeData[CalledMethodBad]
]
"""

    print(rewrite_src(test_str))
    pass


if __name__ == "__main__":
    main()
