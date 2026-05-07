import os
import random
from flask import Flask, jsonify

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor


def configure_opentelemetry():
    resource = Resource.create({
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "phrase-picker"),
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint="https://api.honeycomb.io/v1/traces",
        headers={"x-honeycomb-team": os.environ.get("HONEYCOMB_API_KEY", "")},
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


configure_opentelemetry()

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

tracer = trace.get_tracer(__name__)

PHRASES = [
    "you're muted",
    "not dead yet",
    "Let them.",
    "Boiling Loves Company!",
    "Must we?",
    "SRE not-sorry",
    "Honeycomb at home",
    "There is no cloud",
    "This is fine",
    "It's a trap!",
    "Not Today",
    "You had one job",
    "bruh",
    "have you tried restarting?",
    "try again after coffee",
    "deploy != release",
    "oh, just the crimes",
    "not a bug, it's a feature",
    "test in prod",
    "who broke the build?",
]


@app.route('/health')
def health():
    return jsonify({"message": "I am here, ready to pick a phrase", "status_code": 0})


@app.route('/phrase')
def get_phrase():
    phrase = choose(PHRASES)
    return jsonify({"phrase": phrase})


def choose(array):
    with tracer.start_as_current_span("choose") as span:
        result = random.choice(array)
        span.set_attribute("app.chosen_phrase", result)
        span.set_attribute("app.phrase_count", len(array))
        return result


if __name__ == '__main__':
    app.run(port=10118)
