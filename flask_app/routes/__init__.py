
def init_api(api):
    from .graph import api as graph_ns

    api.add_namespace(graph_ns)
