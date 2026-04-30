"""Modal deployment for the tool-agent FastAPI app.

Deploy with:
    modal deploy modal_app.py

The deployed endpoint will be:
    https://<workspace>--support-agent-fastapi-app.modal.run
"""
import modal

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "anthropic>=0.40",
        "fastapi",
        "asyncpg",
        "pydantic>=2",
        "langfuse>=2.50",
        "opentelemetry-instrumentation-anthropic",
    )
    .add_local_python_source("main", "tools")
)

app = modal.App("support-agent", image=image)


@app.function(
    secrets=[
        modal.Secret.from_name("anthropic-prod"),
        modal.Secret.from_name("postgres-prod"),
        modal.Secret.from_name("langfuse-prod"),
    ],
    timeout=120,
    min_containers=1,   # warm pool
    max_containers=20,
    cpu=1.0,
    memory=1024,
)
@modal.asgi_app()
def fastapi_app():
    from main import app as fastapi  # noqa: WPS433

    return fastapi
