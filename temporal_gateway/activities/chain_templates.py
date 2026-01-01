"""
Activity: Resolve chain templates
"""

from typing import Dict, Any

from temporalio import activity


@activity.defn
async def resolve_chain_templates(
    parameters: Dict[str, Any],
    step_results: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Activity: Resolve Jinja2 templates in parameters using step results

    Args:
        parameters: Parameters with templates like {{ step1.output.video }}
        step_results: Previous step results for context

    Returns:
        Resolved parameters
    """
    activity.logger.info(f"Resolving templates in parameters")

    try:
        from temporal_gateway.chains.interpreter import ChainInterpreter

        interpreter = ChainInterpreter()
        context = interpreter.build_execution_context(step_results)
        resolved = interpreter.resolve_templates(parameters, context)

        activity.logger.info(f"Templates resolved successfully")
        return resolved

    except Exception as e:
        activity.logger.error(f"Failed to resolve templates: {e}")
        raise
