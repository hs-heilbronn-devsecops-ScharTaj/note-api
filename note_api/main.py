# -*- coding: utf-8 -*-
from uuid import uuid4
from typing import List, Optional
from os import getenv
from typing_extensions import Annotated

from fastapi import Depends, FastAPI
from starlette.responses import RedirectResponse
from .backends import Backend, RedisBackend, MemoryBackend, GCSBackend
from .model import Note, CreateNoteRequest
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.trace import SpanKind
import google.auth

import os

# Google Cloud Authentication
if os.getenv("TESTING", "false").lower() == "true":
    # Verwende Dummy-Werte in der Testumgebung
    credentials = None
    project_id = "dummy-project-id"
else:
    # Nutze echte Google-Auth
    credentials, project_id = google.auth.default()

# Google Cloud Authentication
# credentials, project_id = google.auth.default()

# Ressource definieren
resource = Resource.create({"service.name": "note-api"})
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)

# Cloud Trace Exporter einrichten
cloud_trace_exporter = CloudTraceSpanExporter()

# BatchSpanProcessor hinzufügen
span_processor = SimpleSpanProcessor(cloud_trace_exporter)
tracer_provider.add_span_processor(span_processor)


app = FastAPI()
# FastAPI-Instrumentierung aktivieren
FastAPIInstrumentor.instrument_app(app)

# Requests-Instrumentierung aktivieren
RequestsInstrumentor().instrument()


my_backend: Optional[Backend] = None


def get_backend() -> Backend:
    global my_backend  # pylint: disable=global-statement
    if my_backend is None:
        backend_type = getenv('BACKEND', 'memory')
        print(backend_type)
        if backend_type == 'redis':
            my_backend = RedisBackend()
        elif backend_type == 'gcs':
            my_backend = GCSBackend()
        else:
            my_backend = MemoryBackend()
    return my_backend

@app.post('/notes')
def create_note(request: CreateNoteRequest,
                backend: Annotated[Backend, Depends(get_backend)]) -> str:
    with trace.get_tracer(__name__).start_as_current_span(
        "create_note_span", kind=SpanKind.SERVER
    ) as span:
        note_id = str(uuid4())
        backend.set(note_id, request)
        span.set_attribute("note_id", note_id)
        return note_id


@app.get('/')
def redirect_to_notes() -> None:
    return RedirectResponse(url='/notes')


@app.get('/notes')
def get_notes(backend: Annotated[Backend, Depends(get_backend)]) -> List[Note]:
    keys = backend.keys()

    Notes = []
    for key in keys:
        Notes.append(backend.get(key))
    return Notes


@app.get('/notes/{note_id}')
def get_note(note_id: str,
             backend: Annotated[Backend, Depends(get_backend)]) -> Note:
    return backend.get(note_id)


@app.put('/notes/{note_id}')
def update_note(note_id: str,
                request: CreateNoteRequest,
                backend: Annotated[Backend, Depends(get_backend)]) -> None:
    backend.set(note_id, request)


@app.post('/notes')
def create_note(request: CreateNoteRequest,
                backend: Annotated[Backend, Depends(get_backend)]) -> str:
    note_id = str(uuid4())
    backend.set(note_id, request)
    return note_id