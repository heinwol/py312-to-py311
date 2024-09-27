from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import cached_property
from typing import (
    ClassVar,
    Literal,
)

from ast_grep_py import SgNode

from py312_to_py311.accessor import (
    KindAndNode,
    NamedChildrenAccessor,
    TypeParameterNode,
)
from py312_to_py311.utils import raises


def _parse_maybe_splat(
    kind_and_node: KindAndNode[Literal["type"]]
    | KindAndNode[Literal["constrained_type"]]
    | KindAndNode[Literal["splat_type"]],
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
            lhs, rhs = NamedChildrenAccessor(node).named_children(functoral=False)[0:2]
            lhs = KindAndNode[Literal["type"]]("type", lhs)
            rhs = KindAndNode[Literal["type"]]("type", rhs)
            lhs_type, lhs_identifier = _parse_maybe_splat(lhs)
            assert lhs_type is IdentifierIntroduction
            return IdentifierIntroduction(
                ConstrainedType(
                    identifier=lhs_identifier, _constraint_text=rhs.node.text()
                )
            )
        case "identifier":
            return IdentifierIntroduction(UnconstrainedType(node.text()))
        case "splat_type":
            type_, identifier = _parse_maybe_splat(
                KindAndNode[Literal["splat_type"]]("splat_type", node)
            )
            return type_(UnconstrainedType(identifier))
        case _ as t:
            raise ValueError(f"Incorrect type: {t}")


def type_parameter_collect_type_introductions(
    type_parameter: TypeParameterNode,
) -> list[TypeIntroduction]:
    """`type_parameter` node has all the type parameters as children, e.g.
    ```
    type_parameter [23, 5] - [23, 24]
      type [23, 6] - [23, 7]
        identifier [23, 6] - [23, 7]
      type [23, 9] - [23, 11]
        identifier [23, 9] - [23, 11]
      type [23, 13] - [23, 17]
        constrained_type [23, 13] - [23, 17]
          type [23, 13] - [23, 14]
            identifier [23, 13] - [23, 14]
          type [23, 16] - [23, 17]
            identifier [23, 16] - [23, 17]
      type [23, 19] - [23, 23]
        splat_type [23, 19] - [23, 23]
          identifier [23, 21] - [23, 23]
    ```

    Again, here we only consider named nodes.
    """

    result: list[TypeIntroduction] = []
    for type_ in NamedChildrenAccessor(type_parameter).named_children(functoral=False):
        kinded_type = KindAndNode[Literal["type"]]("type", type_)
        child_of_type = (
            NamedChildrenAccessor(kinded_type)
            .named_child(0)
            .or_else_call(
                lambda: raises(lambda: RuntimeError("Somehow child of 'type' is None"))
            )
            .node
        )
        result.append(_parse_type(child_of_type))
    return result


@dataclass(frozen=True)
class UnconstrainedType:
    """Type parameter for unconstrained type example (only named nodes):
    ```
    type_parameter [23, 5] - [23, 8]
      type [23, 6] - [23, 7]
        identifier [23, 6] - [23, 7]
    ```
    """

    identifier: str

    def generate_type_var(
        self, type_of_constraint: Literal["TypeVar", "TypeVarTuple", "ParamSpec"]
    ) -> str:
        return f'{self.identifier} = {type_of_constraint}("{self.identifier}")'


@dataclass(frozen=True)
class ConstrainedType:
    """Type parameter for constrained type example (only named nodes):
    ```
    type_parameter [12, 15] - [12, 36]
      type [12, 16] - [12, 35]
        constrained_type [12, 16] - [12, 35]
          type [12, 16] - [12, 25]
            identifier [12, 16] - [12, 25]
          type [12, 27] - [12, 35]
            identifier [12, 27] - [12, 35]
    ```
    """

    identifier: str
    _constraint_text: str

    _regex_for_replacing_in_constraint_text: ClassVar[re.Pattern] = re.compile(
        r"[\s\n]*", flags=re.MULTILINE
    )

    @cached_property
    def constraint_text(self) -> str:
        result = "".join(
            self._regex_for_replacing_in_constraint_text.split(self._constraint_text)
        )
        logging.debug(result)
        return result

    # def __post_init__(self) -> None:
    #     self.constraint_text = "".join(
    #         self._regex_for_replacing_in_constraint_text.split(self._constraint_text)
    #     )
    #     logging.debug(self.constraint_text)

    def generate_type_var(self) -> str:
        return f'{self.identifier} = TypeVar("{self.identifier}", bound="{self.constraint_text}")'


@dataclass(frozen=True)
class IdentifierIntroduction:
    type_: UnconstrainedType | ConstrainedType

    def generate_type_var(self) -> str:
        return (
            self.type_.generate_type_var("TypeVar")
            if isinstance(self.type_, UnconstrainedType)
            else self.type_.generate_type_var()
        )


@dataclass(frozen=True)
class TypeVarTupleIntroduction:
    """The node is indistinguishable from `ParamSpecIntroduction`, we need to parse
    `splat_type`'s text explicitly
    ```
    type [23, 19] - [23, 23]
      splat_type [23, 19] - [23, 23]
        identifier [23, 21] - [23, 23]
    ```
    """

    type_: UnconstrainedType

    def generate_type_var(self) -> str:
        return self.type_.generate_type_var("TypeVarTuple")


@dataclass(frozen=True)
class ParamSpecIntroduction:
    """The node is indistinguishable from `TypeVarTupleIntroduction`, we need to parse
    `splat_type`'s text explicitly
    ```
    type [23, 19] - [23, 23]
      splat_type [23, 19] - [23, 23]
        identifier [23, 21] - [23, 23]
    ```
    """

    type_: UnconstrainedType

    def generate_type_var(self) -> str:
        return self.type_.generate_type_var("ParamSpec")


type TypeIntroduction = (
    IdentifierIntroduction | TypeVarTupleIntroduction | ParamSpecIntroduction
)
