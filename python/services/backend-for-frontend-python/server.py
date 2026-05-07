import os
from flask import Flask, jsonify, Response, request
from o11yday_lib import fetch_from_service

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor


def configure_opentelemetry():
    resource = Resource.create({
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "backend-for-frontend"),
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint="https://api.honeycomb.io/v1/traces",
        headers={"x-honeycomb-team": os.environ.get("HONEYCOMB_API_KEY", "")},
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


configure_opentelemetry()
RequestsInstrumentor().instrument()

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

tracer = trace.get_tracer(__name__)


def get_request_region():
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


@app.route('/health')
@app.route('/')
def health():
    return jsonify({"message": "I am here", "status_code": 0})


@app.route('/createPicture', methods=['POST'])
def create_picture():
    with tracer.start_as_current_span("create_picture") as span:
        span.set_attribute("app.user_id", request.headers.get("X-User-ID", "unknown"))
        span.set_attribute("app.session_id", request.headers.get("X-Session-ID", "unknown"))
        span.set_attribute("app.request_region", get_request_region())

        phrase_response = fetch_from_service('phrase-picker')
        image_response = fetch_from_service('image-picker')

        used_phrase_fallback = not (phrase_response and phrase_response.ok)
        used_image_fallback = not (image_response and image_response.ok)

        if used_phrase_fallback:
            span.set_attribute("app.error_category", "UPSTREAM_UNAVAILABLE")

        phrase_result = phrase_response.json() if not used_phrase_fallback else {"phrase": "This is sparta"}
        image_result = image_response.json() if not used_image_fallback else {"imageUrl": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Banana-Single.jpg/1360px-Banana-Single.jpg"}

        span.set_attribute("app.phrase", phrase_result.get("phrase", ""))
        span.set_attribute("app.image_selected", image_result.get("imageUrl", ""))
        span.set_attribute("app.used_phrase_fallback", used_phrase_fallback)
        span.set_attribute("app.used_image_fallback", used_image_fallback)

        body = {**phrase_result, **image_result}
        meminator_response = fetch_from_service('meminator', method="POST", body=body)

        if not meminator_response or not meminator_response.ok or meminator_response.content is None:
            span.set_attribute("app.error_category", "MEMINATOR_FAILED")
            raise Exception(f"Failed to fetch picture from meminator")

        span.set_attribute("app.response_size_bytes", len(meminator_response.content))

        flask_response = Response(
            meminator_response.content,
            status=meminator_response.status_code,
            content_type=meminator_response.headers.get('content-type'),
        )
        return flask_response


if __name__ == '__main__':
    app.run(port=10115)
