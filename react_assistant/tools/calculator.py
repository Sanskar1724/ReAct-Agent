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

MAX_EXPRESSION_CHARS = 500
MAX_ABS_RESULT = 1e12
MAX_POW_EXPONENT = 1000


class CalculatorTool:
    name = "calculator"
    description = "Evaluate arithmetic expressions safely (e.g. '18 * 49', '(3+4)/2')."
    aliases = {"calc", "math"}

    def run(self, expression: str) -> str:
        expression = (expression or "").strip().strip("`").strip()
        if not expression:
            raise ValueError("An arithmetic expression is required, e.g. '18 * 49'.")
        if len(expression) > MAX_EXPRESSION_CHARS:
            raise ValueError(f"Expression too long (max {MAX_EXPRESSION_CHARS} chars).")
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._evaluate(tree.body)
        except (ValueError, ZeroDivisionError, OverflowError):
            raise
        except Exception as exc:
            raise ValueError(f"Invalid expression: {expression}") from exc
        if isinstance(result, (int, float)):
            if abs(result) > MAX_ABS_RESULT:
                raise ValueError(f"Result magnitude too large (limit {MAX_ABS_RESULT:g}).")
            if isinstance(result, float) and (result != result or result in (float("inf"), float("-inf"))):
                raise ValueError("Result is not a finite number.")
        return str(result)

    def _evaluate(self, node: ast.AST):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, float) and abs(node.value) > MAX_ABS_RESULT:
                raise ValueError("Literal too large.")
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            if isinstance(node.op, ast.Pow):
                exponent = self._evaluate(node.right)
                base = self._evaluate(node.left)
                if isinstance(exponent, (int, float)) and abs(exponent) > MAX_POW_EXPONENT:
                    raise ValueError(f"Exponent too large (limit {MAX_POW_EXPONENT}).")
                try:
                    return _ALLOWED_BINOPS[type(node.op)](base, exponent)
                except OverflowError as exc:
                    raise ValueError("Exponentiation overflow.") from exc
            return _ALLOWED_BINOPS[type(node.op)](self._evaluate(node.left), self._evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
            return _ALLOWED_UNARYOPS[type(node.op)](self._evaluate(node.operand))
        raise ValueError("Only basic arithmetic (+ - * / // % **) and numbers are allowed.")
