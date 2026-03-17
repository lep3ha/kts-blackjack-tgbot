"""Simple OpenAPI helpers for aiohttp class-based views."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


@dataclass(slots=True)
class SwaggerDoc:
    summary: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    request_model: type[BaseModel] | None = None
    query_model: type[BaseModel] | None = None
    response_model: type[BaseModel] | None = None
    success_status: int = 200


def swagger_doc(
    *,
    summary: str,
    description: str = "",
    tags: list[str] | None = None,
    request_model: type[BaseModel] | None = None,
    query_model: type[BaseModel] | None = None,
    response_model: type[BaseModel] | None = None,
    success_status: int = 200,
):
    """Attach OpenAPI metadata to aiohttp view methods."""

    def decorator(func):
        func.__swagger_doc__ = SwaggerDoc(
            summary=summary,
            description=description,
            tags=tags or [],
            request_model=request_model,
            query_model=query_model,
            response_model=response_model,
            success_status=success_status,
        )
        return func

    return decorator


def _json_response_schema(data_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "const": True},
            "data": data_schema or {"type": "object"},
        },
        "required": ["success", "data"],
    }
    return payload


def _error_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "const": False},
            "error": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "details": {},
                },
                "required": ["code", "message"],
            },
        },
        "required": ["success", "error"],
    }


def _query_parameters_from_model(model: type[BaseModel]) -> list[dict[str, Any]]:
    schema = model.model_json_schema()
    properties: dict[str, Any] = schema.get("properties", {})
    required: set[str] = set(schema.get("required", []))

    parameters: list[dict[str, Any]] = []
    for name, prop_schema in properties.items():
        parameters.append(
            {
                "name": name,
                "in": "query",
                "required": name in required,
                "schema": prop_schema,
            }
        )
    return parameters


def build_view_paths(routes: list[tuple[str, type]]) -> dict[str, Any]:
    """Build OpenAPI path map from class-based view definitions."""
    paths: dict[str, Any] = {}
    for path, view_cls in routes:
        normalized_path = path
        operations: dict[str, Any] = {}
        for method_name in ("get", "post", "put", "patch", "delete"):
            method = getattr(view_cls, method_name, None)
            if method is None:
                continue

            doc: SwaggerDoc | None = getattr(method, "__swagger_doc__", None)
            if doc is None:
                continue

            operation: dict[str, Any] = {
                "summary": doc.summary,
                "description": doc.description,
                "tags": doc.tags,
                "responses": {
                    str(doc.success_status): {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": _json_response_schema(
                                    doc.response_model.model_json_schema() if doc.response_model else None
                                )
                            }
                        },
                    },
                    "400": {
                        "description": "Client error",
                        "content": {"application/json": {"schema": _error_response_schema()}},
                    },
                    "403": {
                        "description": "Authorization error",
                        "content": {"application/json": {"schema": _error_response_schema()}},
                    },
                    "404": {
                        "description": "Not found",
                        "content": {"application/json": {"schema": _error_response_schema()}},
                    },
                    "409": {
                        "description": "State conflict",
                        "content": {"application/json": {"schema": _error_response_schema()}},
                    },
                    "422": {
                        "description": "Domain validation error",
                        "content": {"application/json": {"schema": _error_response_schema()}},
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {"application/json": {"schema": _error_response_schema()}},
                    },
                },
            }

            if doc.request_model is not None and method_name != "get":
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": doc.request_model.model_json_schema(),
                        }
                    },
                }

            parameters: list[dict[str, Any]] = []
            if "{session_id}" in path:
                parameters.append(
                    {
                        "name": "session_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer", "minimum": 1},
                    }
                )

            if doc.query_model is not None:
                parameters.extend(_query_parameters_from_model(doc.query_model))

            if parameters:
                operation["parameters"] = parameters

            operations[method_name] = operation

        if operations:
            paths[normalized_path] = operations

    return paths
