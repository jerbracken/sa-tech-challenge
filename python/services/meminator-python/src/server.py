import os
import subprocess
import time
from flask import Flask, jsonify, send_file, request

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from download import generate_random_filename, download_image


def configure_opentelemetry():
    resource = Resource.create({
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "meminator"),
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

IMAGE_MAX_WIDTH_PX = 1000
IMAGE_MAX_HEIGHT_PX = 1000


@app.route('/health')
def health():
    return jsonify({"message": "I am here", "status_code": 0})


@app.route('/applyPhraseToPicture', methods=['POST', 'GET'])
def meminate():
    input = request.json or {"phrase": "I got you"}
    phrase = input.get("phrase", "words go here").upper()
    imageUrl = input.get("imageUrl", "http://missing.booo/no-url-here.png")

    current_span = trace.get_current_span()
    current_span.set_attribute("app.phrase", phrase)
    current_span.set_attribute("app.imageUrl", imageUrl)

    with tracer.start_as_current_span("download_image") as span:
        span.set_attribute("app.imageUrl", imageUrl)
        input_image_path = download_image(imageUrl)
        span.set_attribute("app.input_image_path", input_image_path)
        if os.path.exists(input_image_path):
            span.set_attribute("app.input_image_size_bytes", os.path.getsize(input_image_path))

    if not os.path.exists(input_image_path):
        return 'downloaded image file not found', 500

    output_image_path = generate_random_filename(input_image_path)

    current_span.set_attribute("app.phrase_char_count", len(phrase))
    current_span.set_attribute("app.phrase_word_count", len(phrase.split()))

    command = [
        'convert',
        input_image_path,
        '-resize', f'{IMAGE_MAX_WIDTH_PX}x{IMAGE_MAX_HEIGHT_PX}>',
        '-gravity', 'North',
        '-pointsize', '48',
        '-fill', 'white',
        '-undercolor', '#00000080',
        '-font', 'Angkor-Regular',
        '-annotate', '0', phrase,
        output_image_path,
    ]

    with tracer.start_as_current_span("imagemagick_convert") as span:
        span.set_attribute("app.phrase", phrase)
        span.set_attribute("app.max_width_px", IMAGE_MAX_WIDTH_PX)
        span.set_attribute("app.max_height_px", IMAGE_MAX_HEIGHT_PX)
        t0 = time.time()
        result = subprocess.run(command, capture_output=True, text=True)
        span.set_attribute("app.imagick_duration_ms", round((time.time() - t0) * 1000))
        span.set_attribute("app.exit_code", result.returncode)
        if result.returncode != 0:
            span.set_attribute("app.stderr", result.stderr)
            raise Exception("Subprocess failed with return code:", result.returncode)
        if os.path.exists(output_image_path):
            span.set_attribute("app.output_image_size_bytes", os.path.getsize(output_image_path))

    return send_file(output_image_path, mimetype='image/png')


if __name__ == '__main__':
    app.run(port=10117)
