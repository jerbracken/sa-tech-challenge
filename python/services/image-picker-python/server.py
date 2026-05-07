import os
import json
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
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "image-picker"),
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

image_urls = []

with app.app_context():
    try:
        if not os.path.exists("images.json"):
            raise FileNotFoundError("images.json can not be found")

        with open("images.json", 'r') as file:
            data = json.load(file)
            images = data.get("images", [])

        bucket_name = os.environ.get("BUCKET_NAME", "random-pictures")
        image_urls = [f"https://{bucket_name}.s3.amazonaws.com/{image}" for image in images]
        app.logger.info("Images loaded successfully.")

    except Exception as e:
        app.logger.error(f"Failed to load images: {e}")
        images = []


@app.route('/health')
def health():
    return jsonify({"message": "I am here, ready to pick an image", "status_code": 0})


@app.route('/imageUrl')
def get_image_url():
    image_url = choose(image_urls)
    return jsonify({"imageUrl": image_url})


def choose(array):
    with tracer.start_as_current_span("choose") as span:
        result = random.choice(array)
        span.set_attribute("app.chosen_image_url", result)
        span.set_attribute("app.image_count", len(array))
        span.set_attribute("app.image_extension", os.path.splitext(result)[-1].lstrip(".") or "unknown")
        span.set_attribute("app.bucket_name", os.environ.get("BUCKET_NAME", "random-pictures"))
        return result


if __name__ == '__main__':
    app.run(port=10116)
