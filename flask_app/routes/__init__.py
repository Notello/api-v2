def init_api(api):
    from .graph import api as graph_ns
    from .upload import api as upload_ns
    from .quiz import api as quiz_ns
    from .health import api as health_ns
    from .summary import api as summary_ns
    from .test import api as test_ns

    api.add_namespace(graph_ns)
    api.add_namespace(upload_ns)
    api.add_namespace(quiz_ns)
    api.add_namespace(health_ns)
    api.add_namespace(summary_ns)
    api.add_namespace(test_ns)
