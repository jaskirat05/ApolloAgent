"""
Activity: Get server output files
"""

from typing import Dict, Any

from temporalio import activity


@activity.defn
async def get_server_output_files(
    server_address: str,
    history_data: Dict[str, Any]
) -> list[Dict[str, str]]:
    """
    Activity: Get output file paths on ComfyUI server (for chain execution)

    Args:
        server_address: ComfyUI server address
        history_data: ComfyUI history data

    Returns:
        List of server file paths (not downloaded locally)
    """
    activity.logger.info(f"Extracting server output files")

    try:
        output_files = []
        outputs = history_data.get('outputs', {})

        for node_id, node_output in outputs.items():
            if 'images' in node_output:
                for img_info in node_output['images']:
                    output_files.append({
                        "filename": img_info['filename'],
                        "subfolder": img_info.get('subfolder', ''),
                        "type": img_info.get('type', 'output'),
                        "node_id": node_id
                    })

        activity.logger.info(f"Found {len(output_files)} output file(s)")
        return output_files

    except Exception as e:
        activity.logger.error(f"Failed to get output files: {e}")
        return []
