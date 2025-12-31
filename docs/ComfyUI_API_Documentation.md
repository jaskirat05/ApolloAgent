# ComfyUI Backend API Documentation

Complete reference for all exposed ComfyUI backend API endpoints.

## Core Endpoints

### WebSocket
- **`/ws`** - WebSocket connection for real-time updates including status changes, progress, and execution events

### Workflow Execution
- **`POST /prompt`** - Queue a workflow for execution
  - Request body: `{"prompt": {...}, "client_id": "..."}`
  - Response: Returns prompt ID for tracking

- **`GET /prompt`** - Get current prompt queue status

- **`POST /interrupt`** - Stop the currently executing prompt

### Queue Management
- **`GET /queue`** - Retrieve current queue state (running and pending prompts)
  - Returns: `{"queue_running": [...], "queue_pending": [...]}`

- **`POST /queue`** - Delete or clear queue items

- **`DELETE /queue/{id}`** - Remove specific queue item by ID

### History & Results
- **`GET /history`** - Get prompt execution history

- **`GET /history/{prompt_id}`** - Fetch execution history and results for a specific prompt ID
  - Returns: JSON with output data including images with filename and directory

- **`POST /history`** - Delete or clear history items

- **`DELETE /history/{id}`** - Delete specific history entry

### Image Handling
- **`GET /view`** - Retrieve images by filename, subfolder, and type
  - Query params:
    - `filename` - Image filename
    - `subfolder` - Subfolder path
    - `type` - Image type: `input`, `output`, or `temp`

- **`POST /upload/image`** - Upload images
  - Form data with image file and optional target folder

- **`POST /upload/mask`** - Upload masks
  - Form data with mask file and optional target folder

## System & Configuration

### System Information
- **`GET /system_stats`** - Get system and device statistics
  - Returns: Python version, OS information, device info

- **`GET /object_info`** - Get definitions of available nodes
  - Returns: Node definitions with inputs, outputs, and parameters

- **`GET /extensions`** - List available extension URLs

- **`GET /embeddings`** - List available embeddings

### Settings & User Data
- **`GET /settings`** - Retrieve all settings

- **`POST /settings`** - Update all settings

- **`GET /settings/{id}`** - Get specific configuration parameter

- **`POST /settings/{id}`** - Update specific configuration parameter

- **`GET /userdata/{file}`** - Fetch user data files

- **`POST /userdata/{file}`** - Upload user data files

- **`POST /users`** - Create new users

- **`GET /users`** - Get user configuration

## Workflow Example

### 1. Export Workflow in API Format
- Enable dev mode in ComfyUI settings
- Use "Save (API format)" button to export workflow as `workflow_api.json`

### 2. Queue a Prompt
```bash
curl -X POST http://localhost:8188/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": <workflow_api_json>,
    "client_id": "unique-client-id"
  }'
```

### 3. Connect to WebSocket for Updates
```javascript
const ws = new WebSocket('ws://localhost:8188/ws?clientId=unique-client-id');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Status update:', data);
};
```

### 4. Retrieve Results
```bash
curl http://localhost:8188/history/{prompt_id}
```

### 5. Download Generated Images
```bash
curl "http://localhost:8188/view?filename=image.png&subfolder=&type=output"
```

## WebSocket Events

The WebSocket connection (`/ws`) provides real-time events:

- **`status`** - Queue status updates
- **`progress`** - Execution progress (e.g., step count)
- **`executing`** - Node execution updates
- **`executed`** - Node completion with outputs
- **`execution_error`** - Execution errors
- **`execution_cached`** - Cached execution results

## Important Notes

1. **Default Port**: ComfyUI runs on port `8188` by default
2. **API Format Workflows**: Always export workflows using "Save (API format)" for API usage
3. **Client ID**: Use consistent `client_id` for WebSocket connections and prompt submissions to receive updates
4. **No Official Documentation**: As of 2025, there is no comprehensive official API documentation. Refer to source code in `server.py` and `web/scripts/api.js` for implementation details
5. **Authentication**: Standard ComfyUI does not include authentication by default

## References

- [ComfyUI API Endpoints Guide - Learn Code Camp](https://learncodecamp.net/comfyui-api-endpoints-complete-guide/)
- [API documentation · Issue #2110 · comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI/issues/2110)
- [Request for API Endpoints Documentation · Issue #6607 · comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI/issues/6607)
- [How to serve your ComfyUI model behind an API endpoint](https://www.baseten.co/blog/how-to-serve-your-comfyui-model-behind-an-api-endpoint/)
- [Run ComfyUI with an API - ComfyICU API](https://comfy.icu/docs/api)

---

*Last updated: December 23, 2025*
