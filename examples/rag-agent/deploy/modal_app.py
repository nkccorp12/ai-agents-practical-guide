"""Modal deployment for the rag-agent FastAPI app.

Deploy with:
    modal deploy modal_app.py
"""
import modal

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "anthropic>=0.40",
        "cohere>=5.10",
        "fastapi",
        "asyncpg",
        "pgvector",
        "pydantic>=2",
        "langfuse>=2.50",
        "opentelemetry-instrumentation-anthropic",
    )
    .add_local_python_source("main", "ingest")
)

app = modal.App("rag-agent", image=image)


@app.function(
    secrets=[
        modal.Secret.from_name("anthropic-prod"),
        modal.Secret.from_name("cohere-prod"),
        modal.Secret.from_name("postgres-prod"),
        modal.Secret.from_name("langfuse-prod"),
    ],
    timeout=60,
    min_containers=2,
    max_containers=30,
    cpu=2.0,
    memory=2048,
)
@modal.asgi_app()
def fastapi_app():
    from main import app as fastapi  # noqa: WPS433

    return fastapi
