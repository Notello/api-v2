def init_api(api):
    from .graph import api as graph_ns
    from .upload import api as upload_ns

    api.add_namespace(graph_ns)
    api.add_namespace(upload_ns)
