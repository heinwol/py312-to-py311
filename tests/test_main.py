import pytest  # noqa

from py312_to_py311.rewriting import rewrite_src


def test_type_alias_statement_rewrites_correctly() -> None:
    test_str = """
type NodeProcessed[CalledMethodT: CalledMethod] = TypedNode[
    ProcessedTreeNodeData[CalledMethodBad]
]
"""
    result = rewrite_src(test_str)
    expected_result = """
CalledMethodT = TypeVar("CalledMethodT", bound="CalledMethod")
NodeProcessed: TypeAlias = TypedNode[
    ProcessedTreeNodeData[CalledMethodBad]
]
"""
    assert result.strip() == expected_result.strip()
