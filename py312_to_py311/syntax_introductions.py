from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import (
    Literal,
    Optional,
    final,
)

from ast_grep_py import Edit, SgNode

from py312_to_py311.accessor import (
    KindAndNode,
    NamedChildrenAccessor,
    TypeParameterNode,
)
from py312_to_py311.type_parameters import (
    TypeIntroduction,
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
    """Typical type alias statement looks like this (only named nodes):

    ```
    type_alias_statement [5, 0] - [7, 1]
      type [5, 5] - [5, 47]
        generic_type [5, 5] - [5, 47]
          identifier [5, 5] - [5, 18]
          type_parameter [5, 18] - [5, 47]
            type [5, 19] - [5, 46]
              constrained_type [5, 19] - [5, 46]
                type [5, 19] - [5, 32]
                  identifier [5, 19] - [5, 32]
                type [5, 34] - [5, 46]
                  identifier [5, 34] - [5, 46]
      type [5, 50] - [7, 1]
        generic_type [5, 50] - [7, 1]
          identifier [5, 50] - [5, 59]
          type_parameter [5, 59] - [7, 1]
            type [6, 4] - [6, 42]
              generic_type [6, 4] - [6, 42]
                identifier [6, 4] - [6, 25]
                type_parameter [6, 25] - [6, 42]
                  type [6, 26] - [6, 41]
                    identifier [6, 26] - [6, 41]
    ```
    """

    kind = "type_alias_statement"

    def __init__(self, node: SgNode) -> None:
        super().__init__(node)

    def navigate_to_type_parameter(
        self,
    ) -> Optional[TypeParameterNode]:
        result = (
            NamedChildrenAccessor(self.kind_and_node)
            .named_child(0)
            .unwrap()
            .node.find(kind="type_parameter")
        )
        return (
            None
            if result is None
            else KindAndNode[Literal["type_parameter"]](
                kind="type_parameter", node=result
            )
        )

    def rewrite_generic_params(self, params: Sequence[TypeIntroduction]) -> Edit:
        node = NamedChildrenAccessor(self.kind_and_node)
        id_text = (
            node.named_child(0, functoral=False).unwrap().find(kind="identifier").text()  # type: ignore
        )
        rhs_text = node.named_child(1, functoral=False).unwrap().text()  # type: ignore
        return node.node.replace(f"{id_text}: TypeAlias = {rhs_text}")


@final
class ClassDefinition(ISyntaxIntroduction[Literal["class_definition"]]):
    """Typical class definition looks like this (only named nodes):

    ```
    class_definition [12, 0] - [12, 34]
      name: identifier [12, 6] - [12, 15]
      type_parameters: type_parameter [12, 15] - [12, 26]
        type [12, 16] - [12, 25]
          identifier [12, 16] - [12, 25]
      superclasses: argument_list [12, 26] - [12, 29]
        identifier [12, 27] - [12, 28]
      body: block [12, 31] - [12, 34]
        expression_statement [12, 31] - [12, 34]
          ellipsis [12, 31] - [12, 34]
    ```

    The field `type_parameters` may or may not be present.

    """

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
    """Typical function definition looks like this (only named nodes):

    ```
    function_definition [23, 0] - [24, 18]
      name: identifier [23, 4] - [23, 5]
      type_parameters: type_parameter [23, 5] - [23, 9]
        type [23, 6] - [23, 8]
          splat_type [23, 6] - [23, 8]
            identifier [23, 7] - [23, 8]
      parameters: parameters [23, 9] - [23, 12]
        identifier [23, 10] - [23, 11]
      body: block [24, 1] - [24, 18]
    ```

    The field `type_parameters` may or may not be present.

    """

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
