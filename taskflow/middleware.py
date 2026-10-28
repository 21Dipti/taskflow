import threading
import time

_metrics = {
    'total_requests': 0,
    'total_errors': 0,
    'requests_by_method': {},
    'requests_by_path': {},
    'avg_response_time_ms': 0,
    '_total_time': 0,
}
_lock = threading.Lock()


def get_metrics():
    with _lock:
        return {
            'total_requests': _metrics['total_requests'],
            'total_errors': _metrics['total_errors'],
            'requests_by_method': dict(_metrics['requests_by_method']),
            'avg_response_time_ms': round(
                _metrics['_total_time'] / _metrics['total_requests'] * 1000, 2
            ) if _metrics['total_requests'] else 0,
        }


class MetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        elapsed = time.monotonic() - start

        with _lock:
            _metrics['total_requests'] += 1
            _metrics['_total_time'] += elapsed
            method = request.method
            _metrics['requests_by_method'][method] = _metrics['requests_by_method'].get(method, 0) + 1
            if response.status_code >= 400:
                _metrics['total_errors'] += 1

        return response
