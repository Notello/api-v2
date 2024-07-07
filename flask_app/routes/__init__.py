def init_api(api):
    from .graph import api as graph_ns
    from .upload import api as upload_ns
    from .quiz import api as quiz_ns
    from .health import api as health_ns

    api.add_namespace(graph_ns)
    api.add_namespace(upload_ns)
    api.add_namespace(quiz_ns)
    api.add_namespace(health_ns)
