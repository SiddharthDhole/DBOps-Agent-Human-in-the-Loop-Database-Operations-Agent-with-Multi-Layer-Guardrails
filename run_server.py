import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting DBOps Agent API & Live Streaming Server")
    print("=" * 60)
    print("Interactive Web UI: http://localhost:8000")
    print("OpenAPI Swagger UI: http://localhost:8000/docs")
    print("WebSocket Endpoint: ws://localhost:8000/ws/chat/{thread_id}")
    print("=" * 60)
    uvicorn.run("app.api.server:app", host="0.0.0.0", port=8000, reload=True)
