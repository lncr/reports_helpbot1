from src.core.api.asgi import AsgiConfig

__all__ = ("app",)

app = AsgiConfig().get_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
