from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import (
    Literal,
    Optional,
    final,
)

from ast_grep_py import Edit, SgNode

from py312_to_py311.type_parameters import (
    KindAndNode,
    TypeIntroduction,
    TypeParameterNode,
)


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
