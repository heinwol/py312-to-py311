from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import (
    Any,
    Iterable,
    Literal,
    assert_never,
    cast,
)

from ast_grep_py import Config, Edit, Relation, Rule, SgNode, SgRoot

from py312_to_py311.accessor import TypeParameterNode
from py312_to_py311.syntax_introductions import (
    ClassDefinition,
    FunctionDefinition,
    ISyntaxIntroduction,
    TypeAliasStatement,
)
from py312_to_py311.type_parameters import (
    ConstrainedType,
    IdentifierIntroduction,
    TypeIntroduction,
    UnconstrainedType,
    type_parameter_collect_type_introductions,
)
from py312_to_py311.utils import (
    all_binary,
    argmax,
    flatten,
    intersperse_with,
    separate_into_kinds,
)


def print_children(node: SgNode) -> None:
    for child in node.children():
        print(child.text())
        print("-" * 20)


# def all_statements_introducing_types(node: SgNode) -> list[SgNode]:
#     return node.find_all(
#         any=[
#             Rule(kind="type_alias_statement"),
#             Rule(kind="class_definition"),
#             Rule(kind="function_definition"),
#         ]
#     )


def collect_all_type_introductions(
    root_node: SgNode, types: Sequence[type[ISyntaxIntroduction[Any]]]
) -> list[_TypeIntroductionsWithMeta]:
    result: list[_TypeIntroductionsWithMeta] = []
    for tp in types:
        nodes_with_type = root_node.find_all(kind=tp.kind)  # type: ignore
        for node in nodes_with_type:
            syntax_introduction_node = tp(node)
            type_parameter = syntax_introduction_node.navigate_to_type_parameter()
            if type_parameter is not None:
                result.append(
                    _TypeIntroductionsWithMeta(
                        introductions=type_parameter_collect_type_introductions(
                            type_parameter
                        ),
                        type_parameter_node=type_parameter,
                        syntax_introduction_node=syntax_introduction_node,
                    )
                )
    return result


def delete_type_parameter(
    kind_and_node: TypeParameterNode,
) -> Edit:
    return kind_and_node.node.replace("")


def generate_type_declarations(
    intros_with_nodes: Iterable[_TypeIntroductionsWithMeta],
) -> list[str]:
    all_introductions: list[TypeIntroduction] = flatten(
        nd.introductions for nd in intros_with_nodes
    )

    # filtering duplicates
    all_introductions = list(set(all_introductions))

    assert all_binary(
        (
            lambda lhs, rhs: type(lhs) is not type(rhs)
            or lhs.type_.identifier != lhs.type_.identifier
        ),
        all_introductions,
    )

    kinds: defaultdict[type[TypeIntroduction], list[TypeIntroduction]] = (
        separate_into_kinds(type, all_introductions)
    )

    identifiers = cast(list[IdentifierIntroduction], kinds[IdentifierIntroduction])
    assert all_binary(
        (
            lambda lhs, rhs: lhs.type_.identifier != rhs.type_.identifier
            or (
                type(lhs.type_) is ConstrainedType
                and type(rhs.type_) is ConstrainedType
                and lhs.type_.constraint_text == rhs.type_.constraint_text
            )
            or (
                type(lhs.type_) is UnconstrainedType
                and type(rhs.type_) is UnconstrainedType
            )
        ),
        identifiers,
    )

    kinds_mapped = {k: [it.generate_type_var() for it in v] for k, v in kinds.items()}
    lines_with_declarations = flatten(
        intersperse_with(list(kinds_mapped.values()), ["\n"])
    )
    return lines_with_declarations


def insert_text_alongside_node_with_newline(
    node: SgNode, text: str, operation: Literal["prepend", "append"]
) -> Edit:
    match operation:
        case "append":
            return node.replace(node.text() + "\n" + text)
        case "prepend":
            return node.replace(text + "\n" + node.text())
        case _:
            assert_never(operation)


def append_after_imports(root: SgNode, text: str) -> Edit:
    import_nodes = root.find_all(
        any=[
            Rule(kind="import_statement"),
            Rule(kind="import_from_statement"),
        ]
    )
    if len(import_nodes) == 0:
        return insert_text_alongside_node_with_newline(root, text, "prepend")
    else:
        last_pos_node = argmax(lambda node: node.range().end.line, import_nodes)
        assert last_pos_node is not None
        return insert_text_alongside_node_with_newline(last_pos_node, text, "append")


def process_all(root_node: SgNode) -> list[Edit]:
    all_type_introductions = collect_all_type_introductions(
        root_node, [TypeAliasStatement, ClassDefinition, FunctionDefinition]
    )
    type_declarations = generate_type_declarations(all_type_introductions)
    type_declarations_appended_after_imports = append_after_imports(
        root=root_node, text="\n".join(type_declarations)
    )

    rewrites_of_syntax_introduction = [
        type_introduction_with_meta.syntax_introduction_node.rewrite_generic_params(
            type_introduction_with_meta.introductions
        )
        for type_introduction_with_meta in all_type_introductions
    ]
    return [type_declarations_appended_after_imports] + rewrites_of_syntax_introduction


find_rhs_type_identifier = Config(
    rule=Rule(
        inside=Relation(kind="type", stopBy="end"),
        kind="identifier",
    )
)


@dataclass
class _TypeIntroductionsWithMeta:
    introductions: list[TypeIntroduction]
    type_parameter_node: TypeParameterNode
    syntax_introduction_node: ISyntaxIntroduction[Any]


def main() -> None:
    test_str = """
type NodeProcessed[CalledMethodT: CalledMethod] = TypedNode[
    ProcessedTreeNodeData[CalledMethodBad]
]
"""
    doc = SgRoot(test_str, "python")
    root = doc.root()
    edits = process_all(root)
    print(root.commit_edits(edits))
    # constrained_type__ = root.find(kind="constrained_type").parent().parent() or raises(
    #     ValueError
    # )
    # for match_ in root.find_all(find_rhs_type_identifier):
    #     print(match_.text())

    # print_children(rs)
    # print(root.find())
    # rs.replace()
    # root


if __name__ == "__main__":
    main()
