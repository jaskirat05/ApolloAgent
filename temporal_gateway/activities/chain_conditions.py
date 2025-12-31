"""
Activity: Evaluate chain conditions
"""

from typing import Dict, Any

from temporalio import activity


@activity.defn
async def evaluate_chain_condition(
    condition: str,
    step_results: Dict[str, Any]
) -> bool:
    """
    Activity: Evaluate a chain step condition

    Args:
        condition: Jinja2 condition expression
        step_results: Previous step results

    Returns:
        True if condition passes, False otherwise
    """
    activity.logger.info(f"Evaluating condition: {condition}")

    try:
        from temporal_sdk.chains.interpreter import ChainInterpreter

        interpreter = ChainInterpreter()
        context = interpreter.build_execution_context(step_results)
        result = interpreter.evaluate_condition(condition, context)

        activity.logger.info(f"Condition evaluated to: {result}")
        return result

    except Exception as e:
        activity.logger.error(f"Failed to evaluate condition: {e}")
        raise
