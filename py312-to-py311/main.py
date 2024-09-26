#!/usr/bin/env python

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterator, Sequence
from copy import copy
from dataclasses import dataclass
from functools import reduce
from typing import (
    Any,
    Callable,
    ClassVar,
    Hashable,
    Iterable,
    Literal,
    Never,
    Optional,
    Protocol,
    Self,
    TypeVar,
    assert_never,
    cast,
    final,
)

from ast_grep_py import Config, Edit, Relation, Rule, SgNode, SgRoot

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)


def raises(f: Callable[[], Exception]) -> Never:
    raise f()


def flatten[T](seq: Iterable[Iterable[T]]) -> list[T]:
    return reduce(lambda acc, it: acc + list(it), seq, [])


def separate_into_kinds[T, K: Hashable](
    kind_function: Callable[[T], K], seq: Iterable[T]
) -> defaultdict[K, list[T]]:
    result = defaultdict[K, list[T]](lambda: [])
    for item in seq:
        kind = kind_function(item)
        result[kind].append(item)
    return result


def apply_binary[T, V](func: Callable[[T, T], V], seq: Sequence[T]) -> Iterator[V]:
    for i in range(len(seq)):
        for j in range(i + 1, len(seq)):
            yield func(seq[i], seq[j])


def all_binary[T](relation: Callable[[T, T], bool], seq: Sequence[T]) -> bool:
    return all(apply_binary(relation, seq))


def intersperse_with[T](seq: Sequence[T], val: T) -> list[T]:
    if len(seq) <= 1:
        return list(seq)
    result: list[T] = []
    for i in range(len(seq) - 1):
        result.append(seq[i])
        result.append(copy(val))
    result.append(seq[-1])
    return result


# int.__le__()


class Ord(Protocol):
    def __le__(self: _OrdT, other: _OrdT, /) -> bool: ...


_OrdT = TypeVar("_OrdT", bound=Ord)


def argmax[T, O: Ord](func: Callable[[T], O], seq: Iterable[T]) -> Optional[T]:
    max_value_so_far: Optional[O] = None
    argmax_value: Optional[T] = None
    for elt in seq:
        ord_result = func(elt)
        if max_value_so_far is None or max_value_so_far <= ord_result:
            max_value_so_far = ord_result
            argmax_value = elt
    return argmax_value


# ---------


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


def _parse_maybe_splat(
    kind_and_node: KindAndNode[Literal["type"]],
) -> tuple[type[TypeIntroduction], str]:
    text = kind_and_node.node.text()
    if text.find("**") != -1:
        return (ParamSpecIntroduction, text[2:])
    elif text.find("*") != -1:
        return (TypeVarTupleIntroduction, text[1:])
    else:
        return (IdentifierIntroduction, text)


def _parse_type(node: SgNode) -> TypeIntroduction:
    match node.kind():
        case "constrained_type":
            lhs, rhs = node.children()[0:2]
            lhs = KindAndNode[Literal["type"]]("type", lhs)
            rhs = KindAndNode[Literal["type"]]("type", rhs)
            lhs_type, lhs_identifier = _parse_maybe_splat(lhs)
            assert lhs_type is IdentifierIntroduction
            return IdentifierIntroduction(
                ConstrainedType(
                    identifier=lhs_identifier, constraint_text=rhs.node.text()
                )
            )
        case "identifier" | "splat_type":
            return IdentifierIntroduction(UnconstrainedType(node.text()))
        case _ as t:
            raise ValueError(f"Incorrect type: {t}")


def type_parameter_collect_type_introductions(
    type_parameter: TypeParameterNode,
) -> list[TypeIntroduction]:
    result: list[TypeIntroduction] = []
    for type_ in type_parameter.node.children():
        kinded_type = KindAndNode[Literal["type"]]("type", type_)
        child_of_type = kinded_type.node.child(0)
        if child_of_type is None:
            raise RuntimeError("Somehow child of 'type' is None")
        result.append(_parse_type(child_of_type))
    return result


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
class UnconstrainedType:
    identifier: str

    def generate_type_var(
        self, type_of_constraint: Literal["TypeVar", "TypeVarTuple", "ParamSpec"]
    ) -> str:
        return f'{self.identifier} = {type_of_constraint}("{self.identifier}")'


@dataclass
class ConstrainedType:
    identifier: str
    constraint_text: str

    _regex_for_replacing_in_constraint_text: ClassVar[re.Pattern] = re.compile(
        r"[\s\n]*", flags=re.MULTILINE
    )

    def __post_init__(self) -> None:
        self.constraint_text = "".join(
            self._regex_for_replacing_in_constraint_text.split(self.constraint_text)
        )
        logging.debug(self.constraint_text)

    def generate_type_var(self) -> str:
        return f'{self.identifier} = TypeVar("{self.identifier}", bound="{self.constraint_text}")'


@dataclass
class IdentifierIntroduction:
    type_: UnconstrainedType | ConstrainedType

    def generate_type_var(self) -> str:
        return (
            self.type_.generate_type_var("TypeVar")
            if isinstance(self.type_, UnconstrainedType)
            else self.type_.generate_type_var()
        )


@dataclass
class TypeVarTupleIntroduction:
    type_: UnconstrainedType

    def generate_type_var(self) -> str:
        return self.type_.generate_type_var("TypeVarTuple")


@dataclass
class ParamSpecIntroduction:
    type_: UnconstrainedType

    def generate_type_var(self) -> str:
        return self.type_.generate_type_var("ParamSpec")


type TypeIntroduction = (
    IdentifierIntroduction | TypeVarTupleIntroduction | ParamSpecIntroduction
)


@dataclass
class KindAndNode[K: str]:
    kind: K
    node: SgNode

    def __post_init__(self) -> None:
        logging.debug(f"{self.kind} == {self.node.kind()}")
        assert self.kind == self.node.kind()

    @classmethod
    def find_all(cls, kind: K, node: SgNode) -> list[Self]:
        return [cls(kind=kind, node=node_) for node_ in node.find_all(kind=cls.kind)]


type TypeParameterNode = KindAndNode[Literal["type_parameter"]]


@dataclass
class _TypeIntroductionsWithMeta:
    introductions: list[TypeIntroduction]
    type_parameter_node: TypeParameterNode
    syntax_introduction_node: ISyntaxIntroduction[Any]


class ISyntaxIntroduction[K: str](ABC):
    kind: K

    def __init__(self, node: SgNode) -> None:
        self.kind_and_node = KindAndNode[K](kind=type(self).kind, node=node)

    @abstractmethod
    def navigate_to_type_parameter(
        self,
    ) -> Optional[TypeParameterNode]: ...

    @abstractmethod
    def rewrite_generic_params(self, params: Sequence[TypeIntroduction]) -> Edit:
        """It is safe to assume `Self` instance has some generic parameters. If there are
        none, this method won't be called."""


@final
class TypeAliasStatement(ISyntaxIntroduction[Literal["type_alias_statement"]]):
    kind = "type_alias_statement"

    def __init__(self, node: SgNode) -> None:
        super().__init__(node)

    def navigate_to_type_parameter(
        self,
    ) -> Optional[TypeParameterNode]:
        result = self.kind_and_node.node.child(1).find(kind="type_parameter")  # type: ignore
        return (
            None
            if result is None
            else KindAndNode[Literal["type_parameter"]](
                kind="type_parameter", node=result
            )
        )

    def rewrite_generic_params(self, params: Sequence[TypeIntroduction]) -> Edit:
        node = self.kind_and_node.node
        id_text = node.child(1).find(kind="identifier").text()  # type: ignore
        rhs_text = node.child(2).text()  # type: ignore
        return node.replace(f"{id_text}: TypeAlias = {rhs_text}")


@final
class ClassDefinition(ISyntaxIntroduction[Literal["class_definition"]]):
    kind = "class_definition"

    def __init__(self, node: SgNode) -> None:
        super().__init__(node)

    def navigate_to_type_parameter(
        self,
    ) -> Optional[TypeParameterNode]:
        result = self.kind_and_node.node.field("type_parameters")
        return (
            None
            if result is None
            else KindAndNode[Literal["type_parameter"]](
                kind="type_parameter", node=result
            )
        )

    def rewrite_generic_params(self, params: Sequence[TypeIntroduction]) -> Edit:
        node = self.kind_and_node.node
        name = node.field("name").text()  # type: ignore

        body = node.field("body")
        assert body is not None
        body_text = body.text()
        if node.range().end.line == body.range().start.line:
            body_indent = " "
        else:
            body_indent = "\n" + " " * body.range().start.column

        params_as_str = ", ".join(param.type_.identifier for param in params)

        superclasses = node.field("superclasses")
        if superclasses is None:
            return node.replace(
                f"class {name}(Generic[{params_as_str}]):{body_indent}{body_text}"
            )
        else:
            superclasses_text = superclasses.text()[1:-1]
            return node.replace(
                f"class {name}({superclasses_text}, Generic[{params_as_str}]):{body_indent}{body_text}"
            )


@final
class FunctionDefinition(ISyntaxIntroduction[Literal["function_definition"]]):
    kind = "function_definition"

    def __init__(self, node: SgNode) -> None:
        super().__init__(node)

    def navigate_to_type_parameter(
        self,
    ) -> Optional[TypeParameterNode]:
        result = self.kind_and_node.node.field("type_parameters")
        return (
            None
            if result is None
            else KindAndNode[Literal["type_parameter"]](
                kind="type_parameter", node=result
            )
        )

    def rewrite_generic_params(self, params: Sequence[TypeIntroduction]) -> Edit:
        type_parameter_node = self.navigate_to_type_parameter()
        assert type_parameter_node is not None
        return type_parameter_node.node.replace("")


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
