from __future__ import annotations

import ast
import operator


_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class CalculatorTool:
    name = "calculator"
    description = "Evaluate arithmetic expressions safely."
    aliases = {"calc", "math", "calculator"}

    def run(self, expression: str) -> str:
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._evaluate(tree.body)
        except Exception as exc:
            raise ValueError(f"Invalid expression: {expression}") from exc
        return str(result)

    def _evaluate(self, node: ast.AST):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            return _ALLOWED_BINOPS[type(node.op)](self._evaluate(node.left), self._evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
            return _ALLOWED_UNARYOPS[type(node.op)](self._evaluate(node.operand))
        raise ValueError("Only basic arithmetic expressions are allowed.")
